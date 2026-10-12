"""Exceptional official race states are first-class observations, not fetch failures."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"collectors"))
from collectors.official_race_conditions import classify_race
import build_latest_prediction_view as latest

def boats(scratches=(),n=6):
    return [{"boat":i,"is_miss":i in scratches,
             "exhibition_course":i,"exhibition_st_raw":".03"} for i in range(1,n+1)]

class OfficialRaceConditionTests(unittest.TestCase):
    def test_normal_six(self):
        x=classify_race(entries=boats())
        self.assertTrue(x["collection_accept"])
        self.assertTrue(x["signal_24_product_possible"])
        self.assertEqual(x["active_lanes"],[1,2,3,4,5,6])
    def test_official_scratch_with_original_six_rows_still_modelable(self):
        x=classify_race(entries=boats(scratches=(4,)))
        self.assertTrue(x["signal_24_product_possible"])
        self.assertEqual(x["verified_scratches"],[4])
        self.assertIn("scratch",{v["code"] for v in x["events"]})
    def test_five_rows_without_official_scratch_is_not_assumed_clean(self):
        x=classify_race(entries=boats(n=5))
        self.assertTrue(x["collection_accept"])
        self.assertFalse(x["signal_24_product_possible"])
        self.assertIn(6,x["unresolved_missing_lanes"])
    def test_four_active_with_two_official_scratches_still_exact_24(self):
        x=classify_race(entries=boats(scratches=(2,5)))
        self.assertEqual(len(x["active_lanes"]),4)
        self.assertTrue(x["signal_24_product_possible"])
    def test_three_active_cannot_issue_fixed_24_but_normal_research_possible(self):
        x=classify_race(entries=boats(scratches=(2,5,6)))
        self.assertTrue(x["can_compute_normal_if_features_exist"])
        self.assertFalse(x["signal_24_product_possible"])
    def test_disqualification_midrace_does_not_erase_prestart_evidence(self):
        x=classify_race(entries=boats(),actual_results=[
            {"boat":3,"remark":"途中失格"},
            {"boat":4,"remark":"転覆"},
            {"boat":5,"remark":"F01"}])
        stages={y["code"]:y["stage"] for y in x["events"]}
        self.assertEqual(stages["race_disqualification"],"result_record")
        self.assertEqual(stages["race_nonfinish"],"after_start")
        self.assertEqual(stages["race_flying_start"],"after_start")
        self.assertTrue(x["collection_accept"])
    def test_cancellation_and_abandoned(self):
        x=classify_race(entries=[],official_status="レース中止 競走不成立")
        kinds={y["code"] for y in x["events"]}
        self.assertIn("race_cancelled",kinds)
        self.assertIn("race_abandoned",kinds)
        self.assertFalse(x["can_compute_normal_if_features_exist"])
        self.assertTrue(x["collection_accept"])
    def test_exhibition_f_l_are_not_race_result_f_l(self):
        x=classify_race(entries=[
            {**r,"exhibition_st_raw":("F.03" if r["boat"]==1 else "L.05" if r["boat"]==2 else ".09")}
            for r in boats()])
        kinds={y["code"] for y in x["events"]}
        self.assertIn("exhibition_false_start",kinds)
        self.assertIn("exhibition_late_start",kinds)
        self.assertNotIn("race_flying_start",kinds)
        self.assertNotIn("race_late_start",kinds)
    def test_past_irregular_official_result_abbreviations_are_preserved(self):
        results=[{"boat":1,"rank":"欠"},{"boat":2,"rank":"失"},
                 {"boat":3,"rank":"転"},{"boat":4,"rank":"落"},
                 {"boat":5,"rank":"妨"},{"boat":6,"rank":"不"}]
        x=classify_race(entries=boats(),actual_results=results)
        codes={y["code"] for y in x["events"]}
        for name in ("scratch","race_disqualification","race_nonfinish","race_abandoned"):
            self.assertIn(name,codes)
        self.assertTrue(x["collection_accept"])
        self.assertTrue(all(y["stage"]=="result_record" for y in x["events"]))

    def test_wide_f_l_notation_and_three_digit_boat_machine_numbers(self):
        b=boats()
        b[0]["boat_no"]=150
        b[1]["boat_no"]=129
        b[2]["boat_no"]=171
        x=classify_race(entries=b,actual_results=[
            {"boat":1,"rank":"Ｆ.01"},{"boat":2,"rank":"Ｌ.03"}])
        self.assertTrue(x["signal_24_product_possible"])
        codes={y["code"] for y in x["events"]}
        self.assertIn("race_flying_start",codes)
        self.assertIn("race_late_start",codes)
        self.assertFalse(x["unresolved_missing_lanes"])

    def test_real_raijin_fujin_and_signal_24_support_five_active_starters(self):
        scored=[
            {"boat":1,"score":82.0,"morning_score_reference":60.0},
            {"boat":2,"score":70.0,"morning_score_reference":73.0},
            {"boat":4,"score":60.0,"morning_score_reference":62.0},
            {"boat":5,"score":52.0,"morning_score_reference":52.0},
            {"boat":6,"score":48.0,"morning_score_reference":48.0}]
        quality={"verified_scratched_boats":[3]}
        self.assertTrue(latest.signal_field_is_verified(scored,quality))
        up=latest.build_up_signal(scored,quality,outside_live_top3=False)
        down=latest.build_down_signal(scored,quality)
        self.assertTrue(up.get("available"))
        self.assertTrue(down.get("available"))
        self.assertGreater(up.get("level",0),0)
        result=latest.build_signal_ai_prediction(scored,up,down,latest.load_signal_ai_config())
        self.assertEqual(len(result["combinations"]),24)
        self.assertEqual(len(result["all_120_combinations"]),60)
        self.assertTrue(result["normal_prediction_unchanged"])
        self.assertIsNotNone(latest.build_formation(scored))

    def test_real_signal_24_handles_four_active_when_two_explicit_scratches(self):
        scored=[
            {"boat":1,"score":82.0,"morning_score_reference":60.0},
            {"boat":3,"score":70.0,"morning_score_reference":73.0},
            {"boat":4,"score":62.0,"morning_score_reference":63.0},
            {"boat":6,"score":55.0,"morning_score_reference":55.0}]
        quality={"verified_scratched_boats":[2,5]}
        self.assertTrue(latest.signal_field_is_verified(scored,quality))
        up=latest.build_up_signal(scored,quality,outside_live_top3=False)
        down=latest.build_down_signal(scored,quality)
        self.assertTrue(down["available"])
        self.assertTrue(up["available"])
        assert up.get("level",0)>0
        signal=latest.build_signal_ai_prediction(scored,up,down,latest.load_signal_ai_config())
        self.assertEqual(len(signal["combinations"]),24)
        self.assertEqual(len(signal["all_120_combinations"]),24)
        self.assertTrue(signal["normal_prediction_unchanged"])

    def test_missing_boat_without_official_confirmation_keeps_signal_pending(self):
        scored=[{"boat":i,"score":80-i*2,"morning_score_reference":65.0} for i in range(1,6)]
        self.assertFalse(latest.signal_field_is_verified(scored,{}))
        self.assertFalse(latest.build_up_signal(scored,{}).get("available"))
        self.assertFalse(latest.build_down_signal(scored,{}).get("available"))

    def test_weather_equipment_and_unknown_st_do_not_block_capture(self):
        rows=boats()
        rows[3]["change_parts"]="ピストン交換"
        rows[4]["exhibition_st_raw"]="NEW_FORMAT"
        x=classify_race(entries=rows)
        self.assertTrue(x["collection_accept"])
        self.assertIn("exhibition_unknown",{y["code"] for y in x["events"]})
        self.assertIn("weather_or_equipment_change",{y["code"] for y in x["events"]})

if __name__=="__main__":unittest.main()
