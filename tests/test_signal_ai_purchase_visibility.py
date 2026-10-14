"""Regression tests for per-race switching and nested signal-AI ranked picks.

Checks rendering only. Stored canonical predictions and scoring are untouched.
"""
import copy
import itertools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collectors"))

from build_family_prediction_page import build_ai_card, build_race_pair


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
        "prediction_type": "直前",
        "up_signal": {"level": 2, "candidates": [{"boat": 6, "rise": 15.4}]},
        "down_signal": {"level": 0},
        "boats": [{"boat": i, "racer_name": f"選手{i}", "score": 70-i}
                  for i in range(1, 7)],
        "morning_boats": [{"boat": i, "racer_name": f"選手{i}", "score": 60-i}
                          for i in range(1, 7)],
        "formation": {},
        "morning_formation": {},
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
    def test_two_stage_disclosure_24_then_25_to_120(self):
        race = signal_race()
        before = copy.deepcopy(race)
        card = build_ai_card(race, 1)
        self.assertEqual(race, before, "Rendering must not rewrite saved predictions")
        self.assertIn("シグナル専用3連単予測", card)
        self.assertIn('class="ai-combo-details signal-ai-purchase-details">', card)
        self.assertIn('class="ai-combo-details signal-ai-reference-details">', card)
        outer = card.index('<details class="ai-combo-details signal-ai-purchase-details">')
        purchase = card.index('class="signal-ai-purchase-list"')
        inner = card.index('<details class="ai-combo-details signal-ai-reference-details">')
        self.assertLess(outer, purchase)
        self.assertLess(purchase, inner)
        self.assertNotIn(" open", card[outer:inner])
        visible = card[purchase:inner]
        reference = card[inner:card.index("</article>", inner)]
        self.assertEqual(visible.count('class="signal-ai-ticket"'), 24)
        self.assertEqual(reference.count('class="signal-ai-ticket"'), 96)
        self.assertEqual(visible.count(" checked"), 24)
        self.assertEqual(reference.count(" checked"), 0)
        self.assertEqual(reference.count('class="ai-combo-details signal-ai-tier"'), 3)
        self.assertIn("1位 1-2-3", visible)
        self.assertIn("24位", visible)
        self.assertNotIn("25位", visible)
        self.assertIn("25位", reference)
        self.assertIn("120位", reference)
        self.assertNotIn("24位", reference)
        for tier in ("強本線", "本線", "準本線", "中穴", "穴", "大穴"):
            self.assertIn(tier, card)

    def test_shortened_race_rank_range_has_no_fabricated_120th_ticket(self):
        race = signal_race()
        race["signal_ai_prediction"]["all_120_combinations"] = race["signal_ai_prediction"]["all_120_combinations"][:60]
        html = build_ai_card(race, 1)
        self.assertEqual(html.count('class="signal-ai-ticket"'), 60)
        self.assertNotIn('data-rank="120"', html)
        self.assertIn('data-rank="60"', html)

    def test_local_research_ticket_choice_never_changes_scored_24(self):
        source = (ROOT / "collectors" / "build_family_prediction_page.py").read_text(encoding="utf-8")
        self.assertIn("initSignalTickets(ai, pair.dataset.raceId)", source)
        self.assertIn("selected.size >= 24", source)
        self.assertIn("boatrace-signal-ticket-selection:v1:", source)
        self.assertIn("上位24点に戻す", source)
        self.assertIn("従来の24点成績計算・補正ロジック・自動購入は変更しません", source)

    def test_per_race_tabs_and_same_race_lookup(self):
        race = signal_race()
        snapshot = copy.deepcopy(race)
        local = build_race_pair(race, 1)
        ai = build_ai_card(race, 1)
        self.assertEqual(race, snapshot)
        self.assertIn('class="race-pair" data-race-id="20261013-04-10"', local)
        self.assertIn('data-local-view="normal" aria-pressed="true"', local)
        self.assertIn('data-local-view="ai" aria-pressed="false"', local)
        self.assertIn('class="race-local-ai" hidden', local)
        self.assertIn('data-race-id="20261013-04-10"', ai)
        self.assertIn("平和島 10R", local)
        self.assertIn("平和島 10R", ai)
        self.assertIn('data-race-view="朝"', local)
        self.assertIn('data-race-view="直前"', local)

    def test_inline_navigation_uses_inert_template_and_saved_race_id(self):
        source = (ROOT / "collectors" / "build_family_prediction_page.py").read_text(encoding="utf-8")
        self.assertIn('<template id="aiPredictionTemplates">', source)
        self.assertIn('card.dataset.raceId === pair.dataset.raceId', source)
        self.assertIn('source.cloneNode(true)', source)
        self.assertIn('normal.hidden = showAi', source)
        self.assertIn('ai.hidden = !showAi', source)
        self.assertIn('setAttribute("aria-pressed"', source)
        self.assertIn('boatrace-race-view:', source)
        self.assertIn('boatrace-race-details:', source)
        self.assertNotIn('id="aiPredictionPanel"', source)

    def test_normal_ai_stays_separate(self):
        race = signal_race()
        race["up_signal"] = {"level": 0}
        race["signal_ai_prediction"] = {}
        race["ai_score_prediction"] = {
            "position_scores": [{"boat": i} for i in range(1, 7)],
            "all_120_combinations": [{"combination": "1-2-3", "score": 50}],
        }
        ai = build_ai_card(race, 2)
        local = build_race_pair(race, 2)
        self.assertIn("通常AIスコア予測", ai)
        self.assertNotIn("signal-ai-purchase-list", ai)
        self.assertIn('data-race-id="20261013-04-10"', ai)
        self.assertIn('data-local-view="ai"', local)

    def test_missing_signal_tickets_never_fall_back_to_normal_ai(self):
        race = signal_race()
        race["signal_ai_prediction"]["all_120_combinations"] = []
        card = build_ai_card(race, 1)
        self.assertIn("データ修復対象", card)
        self.assertNotIn("通常AIスコア予測", card)
        self.assertNotIn("signal-ai-purchase-list", card)
        self.assertIn('data-race-id="20261013-04-10"', card)


if __name__ == "__main__":
    unittest.main()
