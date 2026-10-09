"""Production-contract tests: model parity, one source, no silent AI fallback."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "collectors"))

from logic_registry import load_logic, logic_identity, LogicConfigurationError
from race_prediction_store import audit_race, audit_canonical, signal_key, tickets24
from build_family_race_compare_page import ai_score_result_html, load_archive_result_fallback
from build_latest_prediction_view import (
    build_up_signal, build_down_signal, build_signal_ai_prediction,
    load_signal_ai_config, build_formation,
)


def six_boats():
    return [
        {"boat": i, "rank": i, "score": score, "morning_score_reference": before}
        for i, (score, before) in enumerate([
            (79, 80), (66, 66), (58, 58),
            (54, 43), (43, 43), (31, 31),
        ], 1)
    ]


class LogicContractTest(unittest.TestCase):
    def test_separate_versioned_files_preserve_adopted_parameters(self):
        morning = load_logic("morning")
        live = load_logic("live")
        signal = load_logic("fujin_raijin")
        self.assertEqual(morning["weights"], {
            "racer_course": 40, "grade": 20, "motor": 20, "boat": 5,
            "national_top2": 15,
        })
        self.assertEqual(live["weights"], {
            "structural": 80, "exhibition_time": 6, "exhibition_st": 14,
        })
        self.assertEqual(morning["grade_prior"], {
            "A1": 1, "A2": .75, "B1": .45, "B2": .25,
        })
        self.assertEqual(live["exhibition_st"]["f_score"], 0.4)
        self.assertEqual(signal["purchase"]["signal_points"], 24)
        self.assertEqual(signal["purchase"]["unit_yen"], 100)
        for config in (morning, live, signal):
            identity = logic_identity(config)
            self.assertEqual(len(identity["config_sha256"]), 64)
            self.assertTrue(identity["model_version"])

    def test_formation_rules_are_versioned_and_numerically_unchanged(self):
        formation = load_logic("formation")
        self.assertEqual(formation["model_version"], "formation_gap_flow_v2")
        self.assertEqual(formation["maximum_points"], {
            "strong_first": 12, "semi_anchor": 8, "mixed": 12,
        })
        cases = [
            ([80, 76, 60, 48, 40, 30], "1・2着折返し＋3着流し", 8),
            ([75, 60, 45, 40, 35, 30], "1・2着固定＋3着流し", 4),
            ([79, 66, 58, 54, 43, 31], "1着固定＋相手流し", 12),
            ([80, 73, 70, 60, 50, 40], "準軸", 8),
            ([80, 78, 75, 74, 70, 66], "混戦", 12),
        ]
        for scores, kind, count in cases:
            with self.subTest(kind=kind):
                boats = [{"boat": i, "score": v} for i, v in enumerate(scores, 1)]
                predicted = build_formation(boats)
                self.assertEqual(predicted["formation_type"], kind)
                self.assertEqual(predicted["model_version"], formation["model_version"])
                self.assertEqual(predicted["points"], count)
                self.assertEqual(predicted["investment_100yen"], count * 100)

    def test_fujin_raijin_uses_same_live_scores_for_signal_and_tickets(self):
        boats = six_boats()
        raijin = build_up_signal(boats)
        fujin = build_down_signal(boats)
        self.assertEqual(raijin["level"], 3)
        self.assertEqual(fujin["level"], 0)
        model = build_signal_ai_prediction(
            boats, raijin, fujin, load_signal_ai_config()
        )
        self.assertEqual(model["signal_key"], "F0R3")
        self.assertEqual(model["points"], 24)
        self.assertEqual(len(model["all_120_combinations"]), 120)
        self.assertEqual(len(set(x["combination"] for x in model["all_120_combinations"])), 120)
        self.assertEqual(len(model["combinations"]), 24)
        self.assertEqual(model["logic_identity"]["config_path"], "config/logic/fujin_raijin.json")

    def test_24_ticket_signal_overrides_normal_8_only_for_display_accounting(self):
        boats = six_boats()
        raijin = build_up_signal(boats)
        fujin = build_down_signal(boats)
        signal = build_signal_ai_prediction(boats, raijin, fujin, load_signal_ai_config())
        normal = {"ai_score_prediction": {
            "points": 8,
            "all_120_combinations": [
                {"combination": "1-2-3", "score": 4.0}
            ] * 12,
        }}
        race = {
            "race_id": "202610090101", "up_signal": raijin,
            "down_signal": fujin, "signal_ai_prediction": signal,
        }
        audit = audit_race(race)
        self.assertEqual(audit["signal_ai_status"], "ready")
        self.assertEqual(len(tickets24(race)), 24)
        chosen = tickets24(race)[0]
        html = ai_score_result_html(
            normal, chosen, 3270,
            {**audit, "signal_ai_prediction": signal},
        )
        self.assertIn("風神雷神専用AI予想", html)
        self.assertIn("購入24点", html)
        self.assertIn("2,400円", html)
        self.assertIn("870円", html)
        self.assertNotIn("購入8点", html)

    def test_missing_signal_tickets_never_fall_back_to_normal_8(self):
        race = {"race_id": "202610090101", "up_signal": {"level": 2},
                "down_signal": {"level": 0}}
        state = audit_race(race)
        self.assertEqual(state["signal_ai_status"], "missing_or_invalid_signal_24")
        self.assertEqual(signal_key(race), "F0R2")
        markup = ai_score_result_html(
            {"ai_score_prediction": {
                "points": 8, "combinations": [{"combination": "1-2-3"}],
            }}, "1-2-3", 9000,
            {**state, "signal_ai_prediction": {}},
        )
        self.assertIn("修復中", markup)
        self.assertNotIn("購入8点", markup)

    def test_official_result_backfill_preserves_invalid_trifecta(self):
        restored = load_archive_result_fallback("20261008")
        # Wakamatsu 12R: the actual official 3連単 was 1-3-2, 1,130円.
        self.assertEqual(restored["202610082012"]["actual"], [1, 3, 2])
        self.assertEqual(restored["202610082012"]["payout"], 1130)
        # Naruto 5R: only two legal finishers; 3連単 is 不成立.
        self.assertNotIn("202610081405", restored)

    def test_audit_counts_all_signals_not_only_saved_tickets(self):
        r1 = {"race_id": "a", "up_signal": {"level": 2}, "down_signal": {"level": 0}}
        r2 = {"race_id": "b", "up_signal": {"level": 0}, "down_signal": {"level": 0}}
        summary = audit_canonical({"target_date": "20261009", "races": [r1, r2]})
        self.assertEqual(summary["active_signals"], 1)
        self.assertEqual(summary["missing_signal_24"], 1)
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["pending_signal_observation"], 0)


if __name__ == "__main__":
    unittest.main()
