"""Contract: a second manual refresh cannot abort the active result/publish chain."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class WorkflowQueueDurability(unittest.TestCase):
    def test_manual_refresh_does_not_cancel_active_comparison(self):
        text = (ROOT / ".github/workflows/intraday_compare.yml").read_text(encoding="utf-8")
        self.assertIn("group: boatrace-intraday-compare", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertNotIn("cancel-in-progress: true", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("canonical_recovery_reconcile.yml", text)

    def test_live_page_publish_is_not_cancelled_by_overlapping_update(self):
        text = (ROOT / ".github/workflows/family_prediction_page.yml").read_text(encoding="utf-8")
        self.assertIn("group: family-prediction-publish", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertNotIn("cancel-in-progress: true", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("race_compare.html", text)

if __name__=="__main__":
    unittest.main()
