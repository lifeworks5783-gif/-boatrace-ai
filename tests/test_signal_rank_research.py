"""Regression contract for research-only Fujin/Raijin 120-ticket ranking attribution."""
from __future__ import annotations
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import run

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "collectors"))
from evaluate_signal_rank_research import prepare_matrix, split_date

class SignalRankingAttributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temporary.name) / "research"
        p = run([
            sys.executable, "collectors/evaluate_signal_rank_research.py",
            "--from-date","20261010","--to-date","20261011",
            "--output-dir",str(cls.out),
            "--no-combination-details",
        ],cwd=ROOT,text=True,capture_output=True)
        if p.returncode:
            raise AssertionError(f"Rank research failed: {p.stdout[-2000:]} {p.stderr[-3500:]}")
        cls.payload = json.loads((cls.out / "summary.json").read_text(encoding="utf-8"))
    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_historical_baseline_exactly_matches_replay(self):
        x=self.payload
        self.assertTrue(x["baseline_full_replay_verified"])
        self.assertEqual(x["model_version"],"signal_rank_diagnostic_v1_20261011")
        self.assertTrue(x["no_production_prediction_changes"])
        self.assertFalse(x["result_as_scoring_input"])
        d=x["comparisons"]["by_date"]["20261010"]["by_method"]["signal_score"]
        self.assertEqual(d["races"],142)
        self.assertEqual(d["hits24"],80)
        self.assertEqual(d["roi_pct"],70.36)
        self.assertEqual(len(x["comparisons"]["by_signal"]),16)

    def test_no_accidental_selection_of_high_deltas_from_results(self):
        x=self.payload
        methods=x["methods"]
        self.assertIn("morning_delta",methods)
        self.assertIn("live_delta",methods)
        self.assertIn("shortlist48_live_delta",methods)
        a=x["overall"]["by_method"]["signal_score"]
        self.assertEqual(a["races"],154)  # 10/10 142 + 10/11 as captured in the frozen replay
        self.assertEqual(a["hits24"],89)
        self.assertTrue(x["real_bets_preserved"])
        self.assertGreater(
            x["overall"]["diagnostic"]["actual_rank_distribution"]["25-36"],0
        )

    def test_each_completed_race_has_attributed_realized_ranks(self):
        with (self.out/"race_diagnostics.csv").open(encoding="utf-8-sig",newline="") as f:
            rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),154)
        for row in rows:
            self.assertAlmostEqual(
                float(row["change_exhibition"])+float(row["change_signal"]),
                float(row["change_total"]),places=2,
            )
            self.assertEqual(
                int(row["rank_uplift_exhibition"])+int(row["rank_uplift_signal"]),
                int(row["rank_uplift_total"]),
            )
            positions=json.loads(row["method_ranks"])
            self.assertTrue(all(1 <= int(pos) <= int(row["combination_count"])
                                for pos in positions.values()))
            self.assertEqual(
                positions["signal_score"],int(row["rank_signal"]),
            )
        self.assertTrue(
            (self.out/"daily"/"20261010"/"summary.json").is_file()
        )

    def test_dataset_split_is_fixed(self):
        cfg=json.loads((ROOT/"config/research/signal_rank_diagnostic_v1_20261011.json").read_text())
        self.assertEqual(split_date("20261006",cfg),"train_exploratory")
        self.assertEqual(split_date("20261009",cfg),"validation_exploratory")
        self.assertEqual(split_date("20261010",cfg),"historical_check_not_unseen")
        self.assertEqual(split_date("20261012",cfg),"prospective_after_freeze")

    def test_missing_config_or_active_signal_fails_closed(self):
        with self.assertRaises((KeyError,TypeError)):
            prepare_matrix([],{"level":1},{"level":0},{},{"methods":{}})


if __name__ == "__main__":
    unittest.main()
