"""Guard against false 'non-trigger' labels after verified manual live recovery."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collectors"))

from audit_signal_consistency import audit, published_cards


class SignalConsistencyAuditTests(unittest.TestCase):
    def test_saved_scores_and_independent_pdca_agree_on_all_finished_races(self):
        result = audit("20261010", ROOT, None)
        self.assertEqual(result["status"], "PASS", result["inconsistencies"][:8])
        self.assertGreater(result["finished_races"], 0)
        self.assertEqual(result["finished_races"], result["validated"])
        self.assertGreater(result["signal_active"], 0)
        self.assertGreater(result["validated_no_signal"], 0)
        self.assertEqual(
            result["signal_active"] + result["validated_no_signal"],
            result["finished_races"],
        )
        self.assertIs(result["result_used_to_calculate_scores"], False)

    def test_falsely_erased_signal_is_detected_instead_of_published(self):
        # Simulate the old failure: scores still imply Fujin/Raijin, but
        # the checker falsely resets its signal flag to no-trigger.
        with patch("audit_signal_consistency.build_up_signal",
                   return_value={"available": True, "level": 0, "active": False}):
            result = audit("20261010", ROOT, None)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any(
            x.get("error") == "saved_signal_not_equal_to_score_recompute"
            for x in result["inconsistencies"]
        ))

    def test_publication_will_be_blocked_if_html_loses_icons(self):
        # Rendered public comparison cards must match real signal levels.
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "race_compare.html"
            path.write_text('<article class="race-card">'
                '<div class="race-title">戸田 1R</div></article>',
                encoding="utf-8")
            result = audit("20261010", ROOT, path)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(
                x.get("error") in ("missing_public_race_card", "public_signal_icons_do_not_match")
                for x in result["inconsistencies"]
            ))

    def test_production_publication_check_is_wired_after_render(self):
        text = (ROOT / ".github/workflows/family_prediction_page.yml").read_text(encoding="utf-8")
        self.assertIn("audit_signal_consistency.py", text)
        self.assertLess(text.index("レース照合ページを生成"),
                        text.index("audit_signal_consistency.py"))
        self.assertLess(text.index("audit_signal_consistency.py"),
                        text.index("公開リポジトリへ保存"))


if __name__ == "__main__":
    unittest.main()
