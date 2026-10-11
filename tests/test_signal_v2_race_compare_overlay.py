"""Regression: screenshot-reported 2026-10-11 Karatsu 6R and Edogawa 1R."""
from __future__ import annotations

import csv
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"collectors"))
from signal_v2_research_overlay import finished_v2_overlays
from build_family_race_compare_page import (
    load_saved_score_rows, load_predictions, nontrigger_signal_diagnostic_html,
    signal_recheck_pending_html,
)

class SavedSignalPresentationTests(unittest.TestCase):
    def test_karatsu_6r_research_replay_is_raijin_level3(self):
        # The old public explanation claimed rank2 boat6 must be excluded.
        r=finished_v2_overlays("20261011",root=ROOT)
        key="202610112306"
        self.assertIn(key,r)
        item=r[key]
        self.assertEqual(item["model_version"],"fujin_raijin_pipeline_v2_20261011")
        self.assertEqual(item["signal_key"],"F0R3")
        self.assertEqual(item["up_signal"]["level"],3)
        self.assertEqual(item["down_signal"]["level"],0)
        boat6=next(x for x in item["up_signal"]["candidates"] if x["boat"]==6)
        self.assertEqual(boat6["rank"],2)
        self.assertAlmostEqual(boat6["rise"],13.95,places=2)
        self.assertEqual(len(item["signal_ai_prediction"]["combinations"]),24)
        self.assertEqual(item["corrected_actual_rank"],57)
        self.assertTrue(item["research_only"])
        self.assertTrue(item["recovered_after_result"])
        self.assertEqual(signal_recheck_pending_html(None,item),"")
    def test_unavailable_edogawa_morning_only_never_becomes_false_signal(self):
        # In the attached screenshot this was morning-score fallback (all +/-0).
        _,_,formations=load_predictions(ROOT/"predictions","20261011")
        r=formations.get("202610110301")
        self.assertIsNotNone(r)
        raw=r.get("raw") or {}
        self.assertEqual(raw.get("prediction_quality",{}).get("status"),"fallback")
        self.assertIn("再照合待ち",signal_recheck_pending_html(r))
        research=finished_v2_overlays("20261011",root=ROOT)
        if "202610110301" in research:
            # Future recovered official six-boat data are allowed to resolve it.
            self.assertEqual(signal_recheck_pending_html(r,research["202610110301"]),"")
        else:
            self.assertIsNone(research.get("202610110301"))
    def test_v2_nontrigger_explanation_has_no_archived_rank_exclusion(self):
        d=nontrigger_signal_diagnostic_html(
            {"available":True,"level":0,"thresholds":{"level1_rise_min":7.5,
             "outside_live_top3":False}},
            {"available":True,"level":0,"metrics":{"rank1_delta":0,
             "top3_delta_sum":0,"gap_1_2":0}})
        self.assertIn("直前順位を問わず",d)
        self.assertNotIn("直前上位3艇以外",d)

if __name__=="__main__":
    unittest.main()
