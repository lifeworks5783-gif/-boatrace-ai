"""Fast publication contract: stable page ownership, no PDCA in critical path."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collectors"))

# The fast publisher runs this test module before updating the public page.
# Import the display regression suite so each publish validates its top-24 UI.
from test_signal_ai_purchase_visibility import SignalAiPurchaseVisibilityTest


class FastFamilyPublishContract(unittest.TestCase):
    def test_fast_lane_uses_saved_canonical_without_research(self):
        fast = (ROOT / ".github/workflows/fast_family_prediction_page.yml").read_text(encoding="utf-8")
        assert "workflow_dispatch:" in fast
        assert "schedule:" not in fast  # no extra polling / quota drain
        assert "build_deadline_prediction_view.py" in fast
        assert "build_family_prediction_page.py" in fast
        assert "fast_publish_status.json" in fast
        assert "CANONICAL_SHA" in fast
        assert "gh api" in fast and "git -C family_public push origin HEAD:main" in fast
        assert "git -C family_public reset --hard origin/main" in fast
        for forbidden in (
            "evaluate_fujin_raijin_history.py",
            "evaluate_signal_pdca_cross.py",
            "evaluate_signal_rank_research.py",
            "build_family_results_page.py",
            "build_family_signal_analysis_page.py",
            "audit_signal_consistency.py",
            "recover_missing_live_for_analysis.py",
        ):
            self.assertNotIn(forbidden, fast)

    def test_v4_keeps_scoring_and_dispatches_fast_publisher(self):
        stage3 = (ROOT / ".github/workflows/v4_stage3_predict.yml").read_text(encoding="utf-8")
        assert "python -u collectors/build_live_prediction.py" in stage3
        assert "python -u collectors/build_latest_prediction_view.py" in stage3
        assert "fast_family_prediction_page.yml" in stage3
        assert "gh workflow run family_prediction_page.yml" not in stage3
        assert "FAST_PUBLICATION_REQUESTED" in stage3

    def test_slow_publisher_preserves_fast_index(self):
        heavy = (ROOT / ".github/workflows/family_prediction_page.yml").read_text(encoding="utf-8")
        assert 'test -s family_public/index.html && [ "$MANUAL_REFRESH" != "true" ]' in heavy
        assert "evaluate_fujin_raijin_history.py" in heavy
        assert "audit_signal_consistency.py" in heavy
        assert "git rebase origin/main" in heavy

    def test_single_page_nav_reuses_existing_shared_theme(self):
        from add_family_navigation import update_page
        with TemporaryDirectory() as d:
            path = Path(d) / "index.html"
            path.write_text(
                '<html><head><style>body{color:inherit}</style></head>'
                '<body><header><h1>最新予想</h1></header></body></html>',
                encoding="utf-8",
            )
            update_page(path, "prediction")
            text = path.read_text(encoding="utf-8")
            self.assertIn('class="family-nav"', text)
            self.assertIn("レース照合", text)
            self.assertIn("結果・成績", text)
            self.assertIn("AI分析", text)
            self.assertIn("family-navigation-v5-unified", text)


if __name__ == "__main__":
    unittest.main()
