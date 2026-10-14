"""Buy/skip research must never learn from the chronological holdout."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collectors"))
from evaluate_signal_buy_skip_holdout import (
    POLICIES, choose_policy, metrics, run, should_buy
)
from evaluate_signal_24_temporal_holdout import load_evidence


def race(date, i, signal, actual_rank=3, payout=2000):
    return {
        "date": date, "race_id": f"{date}{i:04d}", "signal": signal,
        "active": signal != "F0R0", "rank": actual_rank if signal != "F0R0" else 0,
        "payout": payout, "max_rank": 120, "provenance": "saved_csv_unclassified",
    }


class BuySkipHoldoutTests(unittest.TestCase):
    def test_gate_must_use_only_predetermined_signal_levels(self):
        for name in POLICIES:
            self.assertFalse(should_buy("F0R0", name))
        self.assertFalse(should_buy("F0R3", "fujin_any"))
        self.assertTrue(should_buy("F3R0", "fujin_any"))
        self.assertTrue(should_buy("F1R3", "all_signal"))
        self.assertEqual(len(POLICIES), 14)

    def test_skipped_result_pays_nothing_but_accounts_for_missed_high_payout(self):
        pool = [race("20261001", 1, "F0R3", 2, 25000),
                race("20261001", 2, "F1R0", 1, 3000),
                race("20261001", 3, "F1R3", 50, 20000),
                race("20261001", 4, "F0R0", 0, 100000)]
        m = metrics(pool, "fujin_any")
        self.assertEqual(m["purchased_races"], 2)
        self.assertEqual(m["skipped_races"], 1)
        self.assertEqual(m["avoided_stakes_yen"], 2400)
        self.assertEqual(m["investment_yen"], 4800)
        self.assertEqual(m["return_yen"], 3000)
        self.assertEqual(m["skipped_wins24"], 1)
        self.assertEqual(m["skipped_wins24_return_yen"], 25000)
        self.assertEqual(m["skipped_payout_ge10000_races"], 1)
        self.assertEqual(m["purchased_payout_ge10000_races"], 1)

    def test_train_only_policy_selection_cannot_read_holdout(self):
        dates = ["20261001", "20261002", "20261003", "20261004"]
        data = []
        for i in range(100):
            date = dates[i // 25]
            sig = "F1R0" if i % 2 == 0 else "F0R3"
            rank = 1 if sig == "F1R0" else 60
            data.append(race(date, i, sig, rank, 10000))
        result1 = run(data)
        changed = [dict(r, rank=90, payout=100) if r["date"] in dates[2:]
                   else r for r in data]
        result2 = run(changed)
        self.assertEqual(result1["locked_rule"], result2["locked_rule"])
        self.assertEqual(result1["comparison"]["train_candidate"],
                         result2["comparison"]["train_candidate"])
        self.assertNotEqual(result1["comparison"]["holdout_candidate"],
                            result2["comparison"]["holdout_candidate"])
        self.assertEqual(result1["training_dates"][-1], "20261002")
        self.assertEqual(result1["holdout_dates"][0], "20261003")

    def test_weak_training_returns_to_baseline_instead_of_zero_bets(self):
        data = [race("20261001", x, "F0R1", 35, 20000) for x in range(20)]
        chosen, reason = choose_policy(data)
        self.assertEqual(chosen, "all_signal")
        self.assertEqual(reason, "no_training_rule_met_predeclared_gate")

    def test_actual_project_evidence_and_dates_when_available(self):
        path = ROOT / "evaluations/signal_payout_rank_distribution/latest/race_evidence.csv"
        if not path.is_file():
            self.skipTest("No historical evidence in checkout")
        data = run(load_evidence(path))
        self.assertEqual(len(data["all_predeclared_rule_comparisons"]), 14)
        self.assertEqual(len(data["by_signal"]), 16)
        self.assertEqual(data["data_audit"]["all_rows"], 1831 if
                         data["training_dates"][0] == "20260930" and
                         data["holdout_dates"][-1] == "20261013" else
                         data["data_audit"]["all_rows"])
        self.assertLess(data["training_dates"][-1], data["holdout_dates"][0])
        for phase in ("train", "holdout"):
            prefix = "train" if phase == "train" else "holdout"
            base = data["comparison"][prefix + "_baseline"]
            cand = data["comparison"][prefix + "_candidate"]
            self.assertEqual(base["eligible_races"], cand["eligible_races"])
            self.assertEqual(cand["purchased_races"] + cand["skipped_races"],
                             base["eligible_races"])
            self.assertEqual(cand["investment_yen"] + cand["avoided_stakes_yen"],
                             base["investment_yen"])
            self.assertLessEqual(cand["return_yen"], base["return_yen"])
            self.assertEqual(base["purchased_races"], base["eligible_races"])
        self.assertEqual(data["by_signal"]["F0R0"]["proposed_decision"], "not_applicable")
        self.assertIn(data["locked_rule"], POLICIES)


if __name__ == "__main__":
    unittest.main()
