"""Integrity tests: chronological split, equal tickets, no result-informed policy."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collectors"))
from evaluate_signal_24_temporal_holdout import (
    POLICIES, choose, evaluate, load_evidence, run, select_tickets
)


def sample(date, n, rank, signal="F0R2", payout=20000, max_rank=120):
    return {
        "date": date, "race_id": f"{date}{n:04d}", "signal": signal,
        "active": signal != "F0R0", "rank": rank if signal != "F0R0" else 0,
        "payout": payout, "max_rank": max_rank, "provenance": "post_result_official_beforeinfo"
    }


class TestSignal24TemporalHoldout(unittest.TestCase):
    def test_all_policies_24_distinct_and_shortened_60_fills_exactly(self):
        self.assertEqual(len(POLICIES), 8)
        for name in POLICIES:
            for n in (24, 60, 120):
                ranks = select_tickets(name, n)
                self.assertEqual(len(ranks), 24)
                self.assertEqual(len(set(ranks)), 24)
                self.assertTrue(all(1 <= x <= n for x in ranks))

    def test_heldout_rank_changes_do_not_change_selected_policy(self):
        dates = ["20261001", "20261002", "20261003", "20261004"]
        data = [sample(dates[i // 25], i, 26 if i < 50 else 1) for i in range(100)]
        first = run(data)
        self.assertNotEqual(first["by_signal"]["F0R2"]["proposed_policy"], "top24")
        changed = [dict(x, rank=120, payout=100) if x["date"] >= "20261003"
                   else x for x in data]
        second = run(changed)
        self.assertEqual(first["by_signal"]["F0R2"]["proposed_policy"],
                         second["by_signal"]["F0R2"]["proposed_policy"])
        self.assertNotEqual(first["overall"]["holdout"]["candidate"]["return_yen"],
                            second["overall"]["holdout"]["candidate"]["return_yen"])

    def test_sparse_signal_stays_baseline_without_future_peeking(self):
        data = [sample("20261001", n, 26) for n in range(6)]
        policy, reason = choose(data)
        self.assertEqual((policy, reason), ("top24", "insufficient_training_races"))

    def test_f0r0_not_purchased_and_heldout_dates_after_training(self):
        data = [sample(d, i, 0, "F0R0", payout=2000) for i, d in
                enumerate(["20261001", "20261002", "20261003", "20261004"])]
        data += [sample(d, i+30, 5) for i, d in
                 enumerate(["20261001", "20261002", "20261003", "20261004"])]
        result = run(data)
        self.assertEqual(result["by_signal"]["F0R0"]["proposed_policy"], "no_bet")
        self.assertEqual(result["audit"]["normal_not_purchased"], 4)
        self.assertLess(result["date_split"]["train_end"], result["date_split"]["holdout_start"])

    def test_payout_and_spend_use_same_24x100_stakes(self):
        evidence = [sample("20261001", 1, 1, payout=5000),
                    sample("20261001", 2, 40, payout=20000)]
        m = evaluate(evidence, "top24")
        self.assertEqual((m["races"], m["hits"], m["stake_yen"],
                          m["return_yen"], m["roi_pct"]), (2, 1, 4800, 5000, 104.17))

    def test_duplicate_and_bad_signal_rank_are_rejected(self):
        header = ["date","race_id","signal_key","active","rank","max_rank","payout","provenance"]
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "evidence.csv"
            def save(lines):
                with p.open("w", encoding="utf-8", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=header)
                    w.writeheader()
                    w.writerows(lines)
            row = dict(date="20261001", race_id="202610010101", signal_key="F0R2",
                       active="1", rank="2", max_rank="120", payout="900",
                       provenance="saved_live")
            save([row, row])
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                load_evidence(p)
            save([dict(row, rank="121")])
            with self.assertRaisesRegex(ValueError, "Missing result rank"):
                load_evidence(p)

    def test_actual_project_saved_rank_evidence_when_available(self):
        p = ROOT / "evaluations/signal_payout_rank_distribution/latest/race_evidence.csv"
        if not p.exists():
            self.skipTest("No actual saved project data checkout")
        data = run(load_evidence(p))
        self.assertEqual(len(data["by_signal"]), 16)
        self.assertEqual(len(data["policy_catalog"]), 8)
        self.assertEqual(data["audit"]["normal_not_purchased"] +
                         data["overall"]["all_retrospective"]["baseline"]["races"],
                         data["audit"]["unique_rows"])
        self.assertLess(data["date_split"]["train_end"], data["date_split"]["holdout_start"])
        for signal, row in data["by_signal"].items():
            if signal != "F0R0":
                self.assertEqual(row["holdout"]["baseline"]["stake_yen"],
                                 row["holdout"]["candidate"]["stake_yen"])
        self.assertEqual(data["overall"]["holdout"]["baseline"]["races"],
                         data["overall"]["holdout"]["candidate"]["races"])


if __name__ == "__main__":
    unittest.main()
