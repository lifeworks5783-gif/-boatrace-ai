"""Protect the independent results page from slow-PDCA and audit gates."""
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


class IndependentComparePublicationContract(unittest.TestCase):
    def test_only_compare_html_is_published(self):
        w = (ROOT / ".github/workflows/race_compare_fast.yml").read_text(encoding="utf-8")
        self.assertIn("collectors/build_family_race_compare_page.py", w)
        self.assertIn("cp ../_race_compare_fast/race_compare.html race_compare.html", w)
        self.assertIn("git add -- race_compare.html", w)
        self.assertNotIn("git add -A", w)
        self.assertNotIn("collectors/evaluate_fujin_raijin_history.py", w)
        self.assertNotIn("collectors/audit_signal_consistency.py", w)
        self.assertIn("cancel-in-progress: false", w)

    def test_result_save_dispatches_before_canonical_reconciliation(self):
        w = (ROOT / ".github/workflows/intraday_compare.yml").read_text(encoding="utf-8")
        dispatch = w.index("gh workflow run race_compare_fast.yml")
        reconcile = w.index("gh workflow run canonical_recovery_reconcile.yml")
        self.assertLess(dispatch, reconcile)
        self.assertIn("if: env.RESULT_COUNT != '0'", w)
        self.assertIn("--ref main -f target_date=", w)

    def test_recovered_live_requires_explicit_provenance(self):
        s = (ROOT / "collectors/build_family_race_compare_page.py").read_text(encoding="utf-8")
        self.assertIn('manifest.get("result_leakage") is False', s)
        self.assertIn('manifest.get("treat_recovered_as_observation") is True', s)
        self.assertIn('stage": "live_recovered_analysis"', s)
        self.assertIn('recovered_after_result', s)


if __name__ == "__main__":
    unittest.main()
