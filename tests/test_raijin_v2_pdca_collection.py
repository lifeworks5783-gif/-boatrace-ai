"""Corrected Raijin research PDCA, yesterday rollover, and visible family views."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import run

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collectors"))

from build_family_signal_analysis_page import raijin_v2_pdca_section
from build_family_results_page import raijin_v2_24_metrics


class RaijinV2PDCAContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.output = cls.root / "raijin_all_rank_v2_replay"
        run([
            sys.executable, "-u", "collectors/evaluate_raijin_all_rank_replay.py",
            "--from-date", "20261010", "--to-date", "20261011",
            "--output-dir", str(cls.output),
        ], cwd=ROOT, check=True, capture_output=True, text=True)
        cls.summary = json.loads((cls.output / "summary.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_yesterday_and_today_daily_data_collected(self):
        dates = {x["date"]: x for x in self.summary["by_date"]}
        self.assertEqual(dates["20261010"]["valid_races"], 156)
        self.assertGreater(dates["20261010"]["changed_levels"], 0)
        self.assertIn("20261011", dates)
        for date in ("20261010", "20261011"):
            daily_dir = self.output / "daily" / date
            self.assertTrue((daily_dir / "summary.json").is_file())
            self.assertTrue((daily_dir / "details.csv").is_file())
            daily = json.loads((daily_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(daily["ruleset"], "fujin_raijin_pipeline_v2_20261011")
            self.assertEqual(len(daily["new_by_signal"]), 16)

    def test_previously_missing_karatsu6_now_raijin_level3(self):
        x = self.summary["known_case_202610112306"]
        self.assertEqual(x["old_raijin_level"], 0)
        self.assertEqual(x["new_raijin_level"], 3)
        six = [z for z in x["new_raijin_candidates"] if z["boat"] == 6]
        self.assertEqual(len(six), 1)
        self.assertEqual(six[0]["rank"], 2)
        self.assertGreater(six[0]["rise"], 13)
        self.assertEqual(x["new_actual_rank"], 57)

    def test_16_classes_and_candidate_finishes_are_consistent(self):
        x = self.summary
        rows = x["new_by_signal"]
        self.assertEqual(len(rows), 16)
        self.assertEqual(sum(z["valid_races"] for z in rows.values()), x["valid_races"])
        self.assertEqual(
            sum(z["signal_active_finished_races"] for z in rows.values()),
            x["new"]["signal_active_finished_races"],
        )
        self.assertGreater(x["new_candidate_score_bands"]["60_plus"]["candidate_count"], 0)
        self.assertTrue(x["result_as_input_to_signals"] is False)
        self.assertTrue(x["never_mutate_historical_predictions"])

    def test_new_pdca_visible_and_old_report_distinguished(self):
        section = raijin_v2_pdca_section(self.root)
        self.assertIn("雷神・修正版PDCA（全順位対象）", section)
        self.assertIn("20261010", section)
        self.assertIn("累計・16分類", section)
        self.assertIn("順位制限なし", section)
        m = raijin_v2_24_metrics(self.root, "20261010")
        daily = next(x["new"] for x in self.summary["by_date"] if x["date"] == "20261010")
        self.assertEqual(m["races"], daily["signal_active_finished_races"])
        self.assertEqual(m["hits"], daily["hit24_races"])
        self.assertAlmostEqual(m["recovery_rate"], daily["roi_pct"])


if __name__ == "__main__":
    unittest.main()
