"""Raijin must detect +7.5 rises regardless of final live rank (v2)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "collectors"))
from logic_registry import load_logic
from build_latest_prediction_view import (
    build_up_signal, build_down_signal, build_signal_ai_prediction, load_signal_ai_config,
)
from evaluate_down_signal import signal_from_rows


def rows(scores, mornings):
    return [
        {"boat": index, "rank": index, "score": score,
         "morning_score_reference": morning}
        for index, (score, morning) in enumerate(zip(scores, mornings), 1)
    ]


class RaijinAllRankContractTest(unittest.TestCase):
    def test_versioned_flag_and_no_other_threshold_changes(self):
        rules = load_logic("fujin_raijin")
        self.assertEqual(rules["model_version"], "fujin_raijin_pipeline_v2_20261011")
        self.assertIs(rules["detection"]["raijin"]["outside_live_top3"], False)
        self.assertEqual(rules["detection"]["raijin"]["min_rise"], 7.5)
        self.assertEqual(rules["detection"]["raijin"]["level2_rise"], 10)
        self.assertEqual(rules["detection"]["raijin"]["level3_score"], 50)

    def test_karatsu6_top3_boat_plus_13_9_is_raijin_lv3(self):
        # Officially saved 2026-10-11 Karatsu 6R style numbers, in live-score order.
        boats = rows(
            [73.2, 69.3, 66.1, 43.8, 24.2, 23.3],
            [69.5, 55.4, 76.6, 57.3, 25.2, 16.0],
        )
        up = build_up_signal(boats)
        down = build_down_signal(boats)
        self.assertEqual(up["level"], 3)
        self.assertEqual(down["level"], 0)
        self.assertEqual([item["boat"] for item in up["candidates"]], [2])
        self.assertEqual(up["candidates"][0]["rank"], 2)
        self.assertAlmostEqual(up["candidates"][0]["rise"], 13.9)
        self.assertEqual(signal_from_rows(boats)["raijin_level"], up["level"])
        self.assertEqual(signal_from_rows(boats)["raijin_candidates"], up["candidates"])
        ai = build_signal_ai_prediction(boats, up, down, load_signal_ai_config())
        self.assertEqual(ai["signal_key"], "F0R3")
        self.assertEqual(len(ai["combinations"]), 24)

    def test_every_rank_is_eligible_but_threshold_still_applies(self):
        for rank in range(1, 7):
            scores = [90, 80, 70, 60, 40, 30]
            mornings = list(scores)
            mornings[rank - 1] -= 8
            up = build_up_signal(rows(scores, mornings))
            with self.subTest(rank=rank):
                self.assertEqual(up["level"], 3 if scores[rank - 1] >= 50 else 1)
                self.assertEqual(up["candidates"][0]["rank"], rank)

    def test_level_two_even_if_first_place_without_score_50(self):
        boats = rows([49, 48, 40, 35, 25, 15], [36, 48, 40, 35, 25, 15])
        self.assertEqual(build_up_signal(boats)["level"], 2)

    def test_under_75_never_activates_even_with_score_above_50(self):
        boats = rows([90, 75, 63, 45, 35, 10], [83, 75, 63, 45, 35, 10])
        self.assertEqual(build_up_signal(boats)["level"], 0)


if __name__ == "__main__":
    unittest.main()
