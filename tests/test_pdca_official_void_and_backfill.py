"""Regression: 2026-10-08 official backfill vs. non-established trifecta."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collectors"))
from evaluate_raijin_all_rank_replay import official_results
from evaluate_signal_pdca_cross import cross, METHODS


class HistoricalSettlementTests(unittest.TestCase):
    def test_official_backfill_is_not_treated_as_missing(self):
        results = official_results("20261008")
        self.assertEqual(results["202610082012"], {"actual": "1-3-2", "payout": 1130})

    def test_naruto_trifecta_void_is_not_a_zero_payout_loss(self):
        results = official_results("20261008")
        self.assertEqual(results["202610081405"], {"actual": None, "payout": 0})
        sample = {"key": "F0R3", "payout": 0, "signal": True,
                  "trifecta_void": True, "methods": {name: None for name in METHODS}}
        group = cross([sample])["F0R3"]
        self.assertEqual(group["races"], 1)
        self.assertEqual(group["trifecta_void"], 1)
        for method in METHODS:
            self.assertEqual(group["methods"][method]["investment"], 0)
            self.assertEqual(group["methods"][method]["races"], 0)

    def test_replay_keeps_pre_result_predictions_and_settles_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "v2"
            subprocess.run(
                [sys.executable, "collectors/evaluate_raijin_all_rank_replay.py",
                 "--from-date", "20261008", "--to-date", "20261008",
                 "--output-dir", str(out)],
                cwd=ROOT, check=True, capture_output=True, text=True,
            )
            with (out / "details.csv").open(encoding="utf-8-sig", newline="") as stream:
                entries = {row["race_id"]: row for row in csv.DictReader(stream)}
            wk = entries["202610082012"]
            na = entries["202610081405"]
            self.assertEqual(wk["actual"], "1-3-2")
            self.assertEqual(int(wk["payout"]), 1130)
            self.assertTrue(1 <= int(wk["new_actual_rank"]) <= 120)
            self.assertEqual(na["actual"], "")
            self.assertEqual(na["new_actual_rank"], "")
            self.assertEqual(int(na["payout"]), 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["last_completed_date"], "20261008")

    def test_conflicting_backfills_fail_closed(self):
        # Conflict handling is essential when a later archive includes the
        # same race with a different payout; never trust the backfill silently.
        source = (ROOT / "collectors/evaluate_raijin_all_rank_replay.py").read_text(encoding="utf-8")
        self.assertIn("Official result/backfill conflict", source)
        self.assertIn("Unverified official result backfill", source)


if __name__ == "__main__":
    unittest.main()
