"""Guarantee manual all-race repair updates PDCA from the SAME canonical V2."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
class CanonicalPdcaOrderTests(unittest.TestCase):
    def test_all_finished_race_recovery_recalculates_pdca_after_v2(self):
        s=(ROOT/'.github/workflows/canonical_recovery_reconcile.yml').read_text()
        code=s.index('python -u collectors/build_latest_prediction_view.py --date "$TARGET_DATE"')
        pdca=s.index('python -u collectors/evaluate_fujin_raijin_history.py --date "$TARGET_DATE"')
        audit=s.index('python -u collectors/audit_signal_consistency.py')
        stage=s.index('git add evaluations/fujin_raijin/latest/backtest_details.csv')
        commit=s.index('git commit -m "Sync verified official live recovery')
        self.assertLess(code,pdca)
        self.assertLess(pdca,audit)
        self.assertLess(audit,stage)
        self.assertLess(stage,commit)
        self.assertIn('git add "evaluations/${TARGET_DATE:0:4}/${TARGET_DATE:4:2}/${TARGET_DATE:6:2}/fujin_raijin_combo_${TARGET_DATE}.json"',s)
        self.assertIn('automatic_collection_enabled',s)
    def test_display_and_saved_pdca_share_the_same_rank_gate(self):
        src=(ROOT/'collectors/evaluate_down_signal.py').read_text()
        self.assertIn('verified_signal_rank_gate_by_race',src)
        self.assertIn('fujin_raijin_pipeline_v2_20261011',src)
        src=(ROOT/'collectors/audit_signal_consistency.py').read_text()
        self.assertIn('saved_signal_not_equal_to_pdca',src)
        self.assertIn('archived_raijin_rank_gate',src)

if __name__=='__main__': unittest.main()
