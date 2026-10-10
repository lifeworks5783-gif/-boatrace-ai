"""One button is one ORDERED update through final race comparison and pages."""
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collectors"))

import dispatch_wait_workflow as dw


class ManualButtonFullRefreshContract(TestCase):
    def test_v3_one_button_waits_for_every_stage(self):
        s = (ROOT / ".github/workflows/fast_live_collection_v3.yml").read_text(encoding="utf-8")
        steps = [
            "--workflow live_prediction_0930.yml",
            "--workflow intraday_compare.yml",
            "--workflow canonical_recovery_reconcile.yml",
            "--workflow family_prediction_page.yml",
        ]
        self.assertEqual(sum(k in s for k in steps), 4)
        self.assertEqual([s.index(x) for x in steps], sorted(s.index(x) for x in steps))
        self.assertEqual(s.count("dispatch_wait_workflow.py"), 4)
        self.assertIn("--input button_pipeline=true", s)
        self.assertIn("--input skip_family_publish=true", s)
        self.assertIn("--input manual_refresh=true", s)
        self.assertIn("cancel-in-progress: false", s)
        self.assertNotIn("cancel-in-progress: true", s)
        # Result refresh must not be conditional on NEW live exhibitions.
        section = s[s.index("name: 最新の公式結果を再取得"):s.index("name: 照合結果を共通正本へ反映")]
        self.assertNotIn("if:", section)

    def test_pipeline_defers_both_premature_publishers(self):
        comparison = (ROOT / ".github/workflows/intraday_compare.yml").read_text(encoding="utf-8")
        canonical = (ROOT / ".github/workflows/canonical_recovery_reconcile.yml").read_text(encoding="utf-8")
        live = (ROOT / ".github/workflows/live_prediction_0930.yml").read_text(encoding="utf-8")
        family = (ROOT / ".github/workflows/family_full_refresh.yml").read_text(encoding="utf-8")
        self.assertIn("!inputs.button_pipeline", comparison)
        self.assertIn("!inputs.skip_family_publish", canonical)
        self.assertIn("env.RAW_READY != 'true'", live)
        self.assertIn("cancel-in-progress: false", live)
        self.assertIn("cancel-in-progress: false", family)
        self.assertIn("gh workflow run fast_live_collection_v3.yml", family)

    def test_failed_child_aborts_full_pipeline(self):
        result = {
            "status": "completed",
            "conclusion": "failure",
            "id": 123,
        }
        with patch.object(dw, "gh", return_value='') as gh:
            gh.side_effect = [
                '[{"databaseId":100}]',  # latest existing run
                "",  # launch
                '[{"databaseId":101},{"databaseId":100}]',  # new run registered
                __import__("json").dumps(result),  # child finished with failure
            ]
            with self.assertRaisesRegex(RuntimeError, "NOT complete"):
                dw.dispatch_wait("owner/repo", "test.yml", 10, [])
        self.assertEqual(gh.call_count, 4)

    def test_successful_child_unblocks_next_stage(self):
        result = {"status": "completed", "conclusion": "success", "id": 101}
        with patch.object(dw, "gh", side_effect=[
            '[{"databaseId":100}]',
            "",
            '[{"databaseId":101},{"databaseId":100}]',
            __import__("json").dumps(result),
        ]) as gh:
            number = dw.dispatch_wait("owner/repo", "test.yml", 10, ["approved=true"])
        self.assertEqual(number, 101)
        self.assertIn("-f", gh.call_args_list[1].args)
        self.assertIn("approved=true", gh.call_args_list[1].args)

    def test_actual_page_reload_waits_for_published_completion_marker(self):
        publisher = (ROOT / ".github/workflows/family_prediction_page.yml").read_text(encoding="utf-8")
        frontend = (ROOT / "collectors/build_family_prediction_page.py").read_text(encoding="utf-8")
        self.assertIn("manual_refresh_status.json", publisher)
        self.assertIn("if: inputs.manual_refresh", publisher)
        self.assertIn("manual_refresh_completed", publisher)
        self.assertIn("manual_refresh_status.json", frontend)
        self.assertIn("readManualPublish", frontend)
        self.assertNotIn("window.location.reload(), 65000", frontend)

    def test_disabled_auto_research_stays_manual(self):
        s = (ROOT / "config/research_audit_policy.json").read_text(encoding="utf-8")
        self.assertIn('"automatic_collection_enabled": false', s)
