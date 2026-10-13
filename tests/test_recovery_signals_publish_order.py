"""End-to-end recovery contracts, with real 2026-10-13 replay evidence."""
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "collectors"))
from recovery_live_overlay import load_verified_recovered_live
from build_latest_prediction_view import (
    build_up_signal, build_down_signal, build_signal_ai_prediction,
    load_signal_ai_config,
)
from race_prediction_store import audit_race
from build_family_race_compare_page import signal_payout_badge

IDS = {"20261013-13-11","20261013-22-10","20261013-04-11"}


class RecoverySignalsCommitBeforeAggregateAudit(unittest.TestCase):
    def test_verified_oct13_races_generate_signals_from_scores_only(self):
        saved = load_verified_recovered_live("20261013")
        self.assertTrue(IDS <= set(saved))
        for race_id in IDS:
            row=saved[race_id]
            self.assertEqual(row["prediction_quality"]["status"], "recovered_observation")
            self.assertTrue(row["prediction_quality"]["retrospective_simulation_only"])
            self.assertTrue(row["prediction_quality"]["prediction_generated_after_deadline"])
            self.assertEqual(len(row["boats"]),6)
            up=build_up_signal(row["boats"],row["prediction_quality"],outside_live_top3=False)
            down=build_down_signal(row["boats"],row["prediction_quality"])
            self.assertTrue(up["available"])
            self.assertTrue(down["available"])
            ai=build_signal_ai_prediction(row["boats"],up,down,load_signal_ai_config())
            if up["level"] or down["level"]:
                self.assertEqual(len(ai["combinations"]),24)
                self.assertEqual(len(ai["all_120_combinations"]),120)
                self.assertEqual(audit_race({
                    "race_id":race_id,"up_signal":up,"down_signal":down,
                    "signal_ai_prediction":ai
                })["signal_ai_status"],"ready")
                badge=signal_payout_badge(5200,up,down,{
                    "recovered_after_result":True,"signal_key":ai["signal_key"]
                })
                self.assertIn("事後捕捉",badge)
            else:
                self.assertIsNone(ai)

    def test_unrelated_global_audit_does_not_block_commit(self):
        w=(ROOT / ".github/workflows/canonical_recovery_reconcile.yml").read_text(encoding="utf-8")
        self.assertIn('SIGNAL_RECOVERY_AUDIT=FAIL',w)
        self.assertLess(w.index('SIGNAL_RECOVERY_AUDIT=FAIL'),
                        w.index('git add "predictions/'))
        self.assertLess(w.index('git push origin HEAD:main'),
                        w.index('gh workflow run race_compare_fast.yml'))
        self.assertLess(w.index('gh workflow run race_compare_fast.yml'),
                        w.index('gh workflow run family_prediction_page.yml'))
        self.assertLess(w.index('gh workflow run family_prediction_page.yml'),
                        w.index('復旧後の全体監査異常を通知'))

    def test_comparison_provenance_is_not_ordinary_live(self):
        text=(ROOT / "collectors/build_family_race_compare_page.py").read_text(encoding="utf-8")
        self.assertIn('quality.get("retrospective_simulation_only") is True',text)
        self.assertIn('"recovered_after_result": reconstructed',text)


if __name__=="__main__":
    unittest.main()
