"""Karatsu 10R incident contract; prepared only, no production replay by test."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collectors"))

from recovery_live_overlay import load_verified_recovered_live
from build_latest_prediction_view import (
    build_up_signal, build_down_signal, build_signal_ai_prediction,
    load_signal_ai_config,
)
from race_prediction_store import audit_race
from build_family_race_compare_page import signal_payout_badge


class Karatsu10SignalRecoveryTest(unittest.TestCase):
    def test_official_replay_qualifies_as_raijin_level1_with_two_candidates(self):
        row = load_verified_recovered_live("20261009")["20261009-23-10"]
        boats = row["boats"]
        self.assertEqual(len(boats), 6)
        by_number = {x["boat"]: x for x in boats}
        self.assertAlmostEqual(
            by_number[5]["score"] - by_number[5]["morning_score_reference"], 9.98,
            places=2,
        )
        self.assertAlmostEqual(
            by_number[6]["score"] - by_number[6]["morning_score_reference"], 9.42,
            places=2,
        )
        fujin = build_down_signal(boats, row["prediction_quality"])
        raijin = build_up_signal(boats, row["prediction_quality"])
        self.assertTrue(raijin["available"])
        self.assertTrue(raijin["active"])
        self.assertEqual(raijin["level"], 1)  # +9.98 displays +10.0, but <10 unrounded
        self.assertEqual([x["boat"] for x in raijin["candidates"]], [5, 6])
        self.assertEqual(fujin["level"], 0)
        dedicated = build_signal_ai_prediction(
            boats, raijin, fujin, load_signal_ai_config()
        )
        self.assertEqual(dedicated["signal_key"], "F0R1")
        self.assertEqual(dedicated["points"], 24)
        self.assertEqual(len(dedicated["combinations"]), 24)
        self.assertEqual(len(dedicated["all_120_combinations"]), 120)
        self.assertEqual(audit_race({
            "race_id": "20261009-23-10",
            "up_signal": raijin,
            "down_signal": fujin,
            "signal_ai_prediction": dedicated,
        })["signal_ai_status"], "ready")

    def test_unobservable_cannot_be_called_nontrigger(self):
        unavailable = {"available": False, "level": 0,
                       "suppressed_reason": "fallback_prediction"}
        label = signal_payout_badge(5200, unavailable, unavailable,
                                   {"signal_ai_status": "signal_not_yet_observable"})
        self.assertIn("未判定", label)
        self.assertNotIn("未発動", label)

    def test_valid_observation_without_signal_is_true_nontrigger(self):
        observed = {"available": True, "level": 0}
        label = signal_payout_badge(5200, observed, observed, {"signal_ai_status": "ready"})
        self.assertIn("未発動", label)

    def test_reconstructed_catch_is_marked_retrospective(self):
        raijin = {"available": True, "level": 1}
        fujin = {"available": True, "level": 0}
        retro = signal_payout_badge(5200, raijin, fujin, {
            "signal_key": "F0R1", "recovered_after_result": True,
        })
        self.assertIn("事後捕捉", retro)
        self.assertNotIn("未発動", retro)

    def test_intraday_workflow_explicitly_dispatches_reconciliation(self):
        workflow = (ROOT / ".github/workflows/intraday_compare.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("gh workflow run canonical_recovery_reconcile.yml", workflow)
        self.assertIn("target_date=", workflow)
        family = (ROOT / ".github/workflows/family_prediction_page.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("公式直前復旧データを共通予測正本へ反映", family)


if __name__ == "__main__":
    unittest.main()
