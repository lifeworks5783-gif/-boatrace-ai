"""Regression tests for always-visible signal AI purchase ranks.

Only the family presentation changes; canonical predictions must stay intact.
"""
import copy
import itertools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collectors"))

from build_family_prediction_page import build_ai_card


def signal_race():
    combinations = [
        {"combination": "-".join(map(str, boats)), "score": 100 - idx * .1}
        for idx, boats in enumerate(itertools.permutations(range(1, 7), 3))
    ]
    return {
        "race_id": "20261013-04-10",
        "venue_name": "平和島",
        "race": 10,
        "deadline": "2026-10-13T15:04:00+09:00",
        "up_signal": {"level": 2, "candidates": [{"boat": 6, "rise": 15.4}]},
        "down_signal": {"level": 0},
        "boats": [{"boat": i, "racer_name": f"選手{i}", "score": 70-i}
                  for i in range(1, 7)],
        "signal_ai_prediction": {
            "signal_key": "F0R2",
            "boat_scores": [
                {"boat": i, "normal_score": 70-i,
                 "signal_adjustment": 26.9 if i == 6 else 0,
                 "signal_ai_score": 70-i+(26.9 if i == 6 else 0),
                 "signal_ai_rank": i}
                for i in range(1, 7)
            ],
            "all_120_combinations": combinations,
        },
    }


class SignalAiPurchaseVisibilityTest(unittest.TestCase):
    def test_signal_top_24_visible_reference_25_to_50_collapsed(self):
        race = signal_race()
        before = copy.deepcopy(race)
        card = build_ai_card(race, 1)
        self.assertEqual(race, before, "Rendering must not rewrite the saved predictions")
        self.assertIn("シグナル専用3連単予測・上位24点", card)
        self.assertIn('class="ai-combos signal-ai-purchase-list"', card)
        visible = card.split('class="ai-combos signal-ai-purchase-list"', 1)[1].split("<details", 1)[0]
        reference = card.split("参考順位25〜50位を見る（購入対象外）", 1)[1].split("</details>", 1)[0]
        self.assertEqual(visible.count('<div class="ai-combo">'), 24)
        self.assertEqual(reference.count('<div class="ai-combo">'), 26)
        self.assertIn("1位 1-2-3", visible)
        self.assertIn("24位", visible)
        self.assertNotIn("25位", visible)
        self.assertIn("25位", reference)
        self.assertIn("50位", reference)
        self.assertNotIn("24位", reference)
        self.assertLess(card.index('class="ai-combos signal-ai-purchase-list"'), card.index("<details"))

    def test_normal_ai_stays_separate(self):
        race = signal_race()
        race["up_signal"] = {"level": 0}
        race["signal_ai_prediction"] = {}
        race["ai_score_prediction"] = {
            "position_scores": [{"boat": i} for i in range(1, 7)],
            "all_120_combinations": [{"combination": "1-2-3", "score": 50}],
        }
        card = build_ai_card(race, 2)
        self.assertIn("通常AIスコア予測", card)
        self.assertNotIn("signal-ai-purchase-list", card)

    def test_missing_signal_tickets_never_fall_back_to_normal_ai(self):
        race = signal_race()
        race["signal_ai_prediction"]["all_120_combinations"] = []
        card = build_ai_card(race, 1)
        self.assertIn("データ修復対象", card)
        self.assertNotIn("通常AIスコア予測", card)
        self.assertNotIn("signal-ai-purchase-list", card)


if __name__ == "__main__":
    unittest.main()
