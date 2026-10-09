"""Regression for actual trifecta ranking within unchanged signal AI 24-point buy set."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collectors"))
from race_prediction_store import load_canonical, audit_race
from build_family_race_compare_page import signal_actual_combo_rank, ai_score_result_html


class SignalActualRankDisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.races = load_canonical("20261009")["races"]

    def signal_race(self, expected_total):
        for race in self.races:
            if not audit_race(race).get("signal_key"):
                continue
            ai = race.get("signal_ai_prediction") or {}
            if ai.get("valid_combination_count") == expected_total and len(ai.get("all_120_combinations") or []) == expected_total:
                return race
        self.fail(f"No saved official {expected_total}-combination signal race")

    def test_real_120_full_ranking_hit_and_miss_before_opening(self):
        race = self.signal_race(120)
        ai = race["signal_ai_prediction"]
        canonical = {"signal_key":ai["signal_key"], "signal_ai_prediction":ai}
        first = ai["all_120_combinations"][16]["combination"]
        outside = ai["all_120_combinations"][41]["combination"]
        self.assertEqual(signal_actual_combo_rank(ai, first), (17,120))
        self.assertEqual(signal_actual_combo_rank(ai, outside), (42,120))
        hit = ai_score_result_html({}, first, 4800, canonical)
        miss = ai_score_result_html({}, outside, 4800, canonical)
        self.assertIn("signal-rank-hit", hit.split("</summary>")[0])
        self.assertIn("的中・実着17位／120通り",hit.split("</summary>")[0])
        self.assertIn("signal-rank-miss",miss.split("</summary>")[0])
        self.assertIn("不的中・実着42位／120通り",miss.split("</summary>")[0])
        self.assertIn("投資 <b>2,400円</b>",miss)
        self.assertIn("払戻 <b>0円</b>",miss)

    def test_official_scratch_five_starters_uses_60(self):
        race = self.signal_race(60)
        ai = race["signal_ai_prediction"]
        canonical = {"signal_key":ai["signal_key"],"signal_ai_prediction":ai}
        first = ai["all_120_combinations"][3]["combination"]
        last = ai["all_120_combinations"][45]["combination"]
        self.assertEqual(signal_actual_combo_rank(ai,first),(4,60))
        self.assertEqual(signal_actual_combo_rank(ai,last),(46,60))
        hit = ai_score_result_html({},first,2200,canonical)
        miss = ai_score_result_html({},last,2200,canonical)
        self.assertIn("的中・実着4位／60通り",hit.split("</summary>")[0])
        self.assertIn("不的中・実着46位／60通り",miss.split("</summary>")[0])

    def test_incomplete_24_list_never_claims_120_rank(self):
        race=self.signal_race(120)
        ai=dict(race["signal_ai_prediction"])
        ai["all_120_combinations"]=ai["all_120_combinations"][:24]
        self.assertEqual(signal_actual_combo_rank(ai,ai["combinations"][0]["combination"]),(None,None))
        html=ai_score_result_html({},ai["combinations"][0]["combination"],3200,
             {"signal_key":ai["signal_key"],"signal_ai_prediction":ai})
        self.assertIn("実着順位未取得",html.split("</summary>")[0])
        self.assertNotIn("実着1位／120",html)

    def test_no_prediction_or_result_does_not_invent_rank(self):
        race=self.signal_race(120)
        ai=race["signal_ai_prediction"]
        self.assertEqual(signal_actual_combo_rank(ai, None),(None,None))
        self.assertEqual(signal_actual_combo_rank({}, "1-2-3"),(None,None))
        self.assertEqual(signal_actual_combo_rank(ai, "9-9-9"),(None,None))


if __name__=="__main__":
    unittest.main()
