"""Versioned read-side diagnostics; tests never contact official website."""
import copy
import unittest
from raw_collector.parser_audit import audit_parsed_beforeinfo,st_semantics

def six():
    rows=[]
    for n in range(1,7):
        rows.append({
            "boat":n,"registration_no":f"{4000+n}",
            "racer_name":f"テスト選手{n}",
            "exhibition_time":6.70+0.01*n,
            "exhibition_course":n,
            "exhibition_st_raw":f".0{n}",
            "exhibition_st_seconds":0.01*n,
            "exhibition_st_flag":"","is_miss":False
        })
    weather={"air_temperature_c":26.0,"water_temperature_c":24.0,
             "wind_speed_mps":4.0,"wave_height_cm":4.0}
    identity={str(n):f"{4000+n}" for n in range(1,7)}
    return rows,weather,identity

class ParserAuditContractTests(unittest.TestCase):
    def test_complete_realistic_structure_is_ready(self):
        rows,weather,identities=six()
        audit=audit_parsed_beforeinfo(rows,weather,identities)
        self.assertEqual(audit["schema"],"boatrace-parser-audit-v1")
        self.assertTrue(audit["ready_live_inputs"])
        self.assertEqual(audit["issues"],[])

    def test_f_notation_is_negative_and_valid_for_current_logic(self):
        rows,weather,identities=six()
        rows[1]["exhibition_st_raw"]="F.04"
        rows[1]["exhibition_st_seconds"]=-0.04
        rows[1]["exhibition_st_flag"]="F"
        self.assertEqual(st_semantics("F.04"),"exhibition_false_start")
        self.assertTrue(audit_parsed_beforeinfo(rows,weather,identities)["ready_live_inputs"])

    def test_l_notation_must_not_be_misread_as_normal_positive_start(self):
        rows,weather,identities=six()
        rows[0]["exhibition_st_raw"]="L.05"
        rows[0]["exhibition_st_seconds"]=0.05
        rows[0]["exhibition_st_flag"]="L"
        audit=audit_parsed_beforeinfo(rows,weather,identities)
        self.assertFalse(audit["ready_live_inputs"])
        self.assertIn("late_st_not_usable_in_live_score",[x["code"] for x in audit["issues"]])

    def test_unknown_notation_blocks_scoring_without_deleting_source(self):
        rows,weather,identities=six()
        rows[2]["exhibition_st_raw"]="INVALID.04"
        audit=audit_parsed_beforeinfo(rows,weather,identities)
        self.assertFalse(audit["ready_live_inputs"])
        self.assertEqual([x for x in audit["issues"] if x["code"]=="unknown_st_notation"][0]["boat"],3)

    def test_duplicate_course_does_not_pass_as_six_valid_courses(self):
        rows,weather,identities=six()
        rows[5]["exhibition_course"]=1
        audit=audit_parsed_beforeinfo(rows,weather,identities)
        self.assertFalse(audit["ready_live_inputs"])
        self.assertIn("duplicate_exhibition_course",[x["code"] for x in audit["issues"]])

    def test_registration_conflict_or_missing_history_reference(self):
        rows,weather,identities=six()
        rows[0]["registration_no"]="9999"
        audit=audit_parsed_beforeinfo(rows,weather,identities)
        self.assertFalse(audit["ready_live_inputs"])
        self.assertIn("program_registration_mismatch",[x["code"] for x in audit["issues"]])
        missing=audit_parsed_beforeinfo(*six()[:2],expected={})
        self.assertIn("program_six_registrations_not_verified",[x["code"] for x in missing["issues"]])

    def test_missing_weather_or_bad_start_do_not_become_zero_values(self):
        rows,weather,identities=six()
        weather["wave_height_cm"]=None
        rows[4]["exhibition_st_raw"]=".12"
        rows[4]["exhibition_st_seconds"]=float("nan")
        audit=audit_parsed_beforeinfo(rows,weather,identities)
        self.assertFalse(audit["ready_live_inputs"])
        codes={x["code"] for x in audit["issues"]}
        self.assertIn("weather_field_missing",codes)
        self.assertIn("st_seconds_mismatch",codes)

if __name__=="__main__":
    unittest.main()
