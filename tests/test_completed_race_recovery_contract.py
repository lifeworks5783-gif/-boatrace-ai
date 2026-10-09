"""Check canonical completed-race recovery across the race-comparison display."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collectors"))
from build_family_race_compare_page import (
    load_predictions, prediction_html, evaluate_top3, signal_payout_badge
)
from race_prediction_store import audit_race


class CompletedRaceRecoveryContract(unittest.TestCase):
    def test_all_recovered_live_races_have_scored_comparison_records(self):
        d = "20261009"
        manifest_path = ROOT / "evaluations/2026/10/09/recovery/live_recovery_manifest_20261009.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        morning, live, canonical = load_predictions(ROOT / "predictions", d)
        restored = manifest.get("recovered_races") or []
        self.assertGreater(len(restored), 0, "No completed-race recoveries were read")
        for race_id in restored:
            code = re.sub(r"\D", "", str(race_id))[:12]
            with self.subTest(race=code):
                self.assertIn(code, live)
                self.assertIn(code, canonical)
                live_boats = live[code].get("boats") or []
                self.assertEqual(len(live_boats), 6)
                self.assertEqual(
                    {str(b.get("boat")) for b in live_boats},
                    {"1", "2", "3", "4", "5", "6"},
                )
                self.assertTrue(all(
                    float(b["score"]) == float(b["score"])
                    for b in live_boats
                ))
                html = prediction_html(live[code])
                self.assertNotIn("予測なし", html)
                self.assertIsNotNone(evaluate_top3(live[code], [1, 2, 3]))
                state = audit_race(canonical[code]["raw"])
                if state["signal_key"]:
                    self.assertEqual(state["signal_ai_status"], "ready")
        print("COMPLETED_RACE_LIVE_DISPLAY_PASS", len(restored))

    def test_edogawa_8r_exact_user_regression(self):
        d = "20261009"
        _, live, canonical = load_predictions(ROOT / "predictions", d)
        code = "202610090308"
        self.assertIn(code, live)
        self.assertIn(code, canonical)
        pred = live[code]
        self.assertEqual([str(x["boat"]) for x in pred["top3"]], ["2", "1", "4"])
        self.assertTrue(all(x.get("score") is not None for x in pred["top3"]))
        html = prediction_html(pred)
        self.assertIn("89.5", html)
        self.assertNotIn("予測なし", html)
        self.assertIsNotNone(evaluate_top3(pred, [4, 3, 2]))
        source = canonical[code]["raw"]
        self.assertEqual((source.get("up_signal") or {}).get("level"), 1)
        self.assertEqual(audit_race(source)["signal_ai_status"], "ready")
        self.assertTrue(source.get("retrospective_signal_recovery"))
        badge = signal_payout_badge(
            5450, source.get("up_signal"), source.get("down_signal"),
            audit_race(source),
        )
        self.assertIn("事後捕捉", badge)
        self.assertNotIn("未判定", badge)
        print("EDOGAWA_8R_RECOVERY_DISPLAY_PASS", code)

    def test_explicit_after_recovery_family_publication_contract(self):
        canonical = (ROOT / ".github/workflows/canonical_recovery_reconcile.yml").read_text(encoding="utf-8")
        family = (ROOT / ".github/workflows/family_prediction_page.yml").read_text(encoding="utf-8")
        self.assertIn("actions: write", canonical)
        self.assertIn("gh workflow run family_prediction_page.yml", canonical)
        self.assertLess(
            canonical.index("git push origin HEAD:main"),
            canonical.index("gh workflow run family_prediction_page.yml"),
        )
        self.assertIn("if: steps.date.outputs.run == 'true'", canonical)
        self.assertNotIn('      - "公式直前復旧データを共通予測正本へ反映"', family)
        self.assertIn("gh workflow run family_prediction_page.yml", canonical)


if __name__ == "__main__":
    unittest.main()
