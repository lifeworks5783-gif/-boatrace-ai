"""Button-only neutral LIVE fallback: calculate first, warn, replay later.

Synthetic partials are generated from six starters; actual saved morning scores
are immutable as inputs and no result/finishing-order fields are supplied.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"collectors"))
import build_live_prediction as live
import build_latest_prediction_view as latest
import build_family_prediction_page as family
import build_family_race_compare_page as compare
from recover_missing_live_for_analysis import partial_race_ids

COMPONENTS=("racer_course","grade","motor","boat","national_top2")
ORIGINAL=[76.8,63.2,61.2,48.7,44.3,5.8]


def fixture(missing=(), all_missing=False):
    """Mock legitimate prior morning numeric records and partial official source."""
    boats=[]
    for lane in range(1,7):
        neutral=all_missing or lane in missing
        boats.append({
            "boat":lane,"racer":{"name":f"選手{lane}","registration_no":4000+lane},
            "motor":{},"boat_machine":{},
            "beforeinfo":{"exhibition_course":None if neutral else lane,
                          "exhibition_time":None if neutral else 6.70 + lane*.02,
                          "exhibition_st_raw":"" if neutral else f".{10+lane:02d}",
                          "is_miss":False}
        })
    race={"race_id":"20261009-10-10","date":"20261009","venue_code":"10",
          "venue_name":"三国","race":10,"deadline":"15:06", "boats":boats}
    morning={"boats":[
        {"boat":i, "score":score,
         "components":{k:{"raw_score_0_1":.5} for k in COMPONENTS}}
        for i,score in enumerate(ORIGINAL,1)
    ]}
    details={i:{"score":v,**{k:.5 for k in COMPONENTS}} for i,v in enumerate(ORIGINAL,1)}
    return race,morning,details


def score_with_fixture(missing=(), all_missing=False):
    race,morning,details=fixture(missing,all_missing)
    with patch.object(live.morning,"provisional_details",return_value=(details,[])),\
         patch.object(live,"personal_st_delta_score",return_value=.65):
        scored=live.score_race(race, None, saved_morning_race=morning)
    return scored


class NeutralLiveFallbackTests(unittest.TestCase):
    def test_only_missing_st_entrant_is_neutral(self):
        scored=score_with_fixture((3,))
        by={b["boat"]:b for b in scored}
        self.assertEqual(by[3]["score"],ORIGINAL[2])
        self.assertEqual(by[3]["morning_score_reference"],ORIGINAL[2])
        self.assertTrue(by[3]["score_fallback"])
        self.assertEqual(by[3]["score_fallback_reasons"],["exhibition_course","exhibition_time","exhibition_st"])
        self.assertFalse(by[1]["score_fallback"])
        self.assertNotEqual(by[1]["score"],ORIGINAL[0])
        self.assertEqual(len(scored),6)

    def test_all_six_missing_are_exact_original_morning(self):
        scored=score_with_fixture(all_missing=True)
        self.assertEqual({b["boat"]:b["score"] for b in scored},dict(enumerate(ORIGINAL,1)))
        self.assertEqual(sum(bool(b["score_fallback"]) for b in scored),6)

    def test_unmissing_official_does_not_change_existing_formula(self):
        scored=score_with_fixture()
        self.assertEqual(len(scored),6)
        self.assertFalse(any(b["score_fallback"] for b in scored))
        for b in scored:
            self.assertIsNotNone(b["exhibition_st"])
            self.assertIsNotNone(b["exhibition_time"])

    def test_signal_is_never_false_nontrigger_on_neutral_scores(self):
        scored=score_with_fixture((3,))
        quality={"status":"fallback","recovery_needed":True,"signal_blocked":True,
                 "boat_fallbacks":[{"boat":3,"reasons":["exhibition_st"]}]}
        up=latest.build_up_signal(scored,quality)
        down=latest.build_down_signal(scored,quality)
        self.assertFalse(up["available"])
        self.assertFalse(down["available"])
        self.assertEqual(up["level"],0)
        self.assertEqual(down["level"],0)
        self.assertIsNone(latest.build_signal_ai_prediction(
            scored,up,down,latest.load_signal_ai_config()))
        # A recovered fully observed score is not blocked by a structural
        # history fallback alone: warning source != live signal eligibility.
        restored=score_with_fixture()
        permitted={"status":"fallback","recovery_needed":True,"signal_blocked":False,
                   "fallback_source":"saved_morning_structural_component"}
        self.assertTrue(latest.build_up_signal(restored,permitted)["available"])
        self.assertTrue(latest.build_down_signal(restored,permitted)["available"])

    def test_each_display_has_race_triangle_and_only_affected_racer_marks(self):
        scored=score_with_fixture((3,))
        row={"race_id":"20261009-10-10","venue_name":"三国","race":10,
             "deadline":"15:06","prediction_type":"直前",
             "prediction_quality":{"status":"fallback","recovery_needed":True,
                                   "signal_blocked":True,"reason":["3号艇:exhibition_st"]},
             "boats":scored,
             "morning_boats":[{"boat":i,"score":v} for i,v in enumerate(ORIGINAL,1)]}
        html=family.build_card(row,1)
        self.assertIn("直前・補完",html)
        self.assertIn('class="quality-warning"',html)
        self.assertIn("boat-neutral",html)
        self.assertEqual(html.count("boat-neutral"),2)  # top pick + six-score chip

        raw={"boats":scored,"prediction_quality":row["prediction_quality"]}
        finished={"top3":[{"boat":b["boat"],"score":b["score"],"name":b["racer_name"]}
                          for b in scored[:3]],
                  "boats":scored,"raw":raw,
                  "prediction_quality":row["prediction_quality"]}
        self.assertIn("▲",compare.prediction_quality_warning(finished))
        cmp_html=compare.all_scores_html(finished,"直前予測")
        self.assertEqual(cmp_html.count("quality-warning"),1)
        self.assertIn("3号艇",cmp_html)

    def test_neutral_is_recovery_pending_and_provenance_retained(self):
        rows=[
            {"race_id":"20261009-10-10","boat":1,"score_fallback":"False"},
            {"race_id":"20261009-10-10","boat":3,"score_fallback":"True"},
            {"race_id":"20261009-23-10","boat":4,"score_fallback":"False"}
        ]
        self.assertEqual(partial_race_ids(rows),{"202610091010"})
        rows[1]["score_fallback"]="False"
        self.assertEqual(partial_race_ids(rows),set())

if __name__=="__main__":
    unittest.main()
