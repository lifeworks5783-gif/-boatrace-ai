"""Regression guards for the production refactor. No HTTP and no result input."""
import itertools
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collectors"))
import production_config
from build_canonical_race_records import canonicalize, signal_key
import build_latest_prediction_view as latest
import build_family_race_compare_page as comparison


def sample_race(code="20261009-01-01", active=True, stored=False):
    rows = [{"rank": i, "boat": i, "score": float(100 - i * 9),
             "morning_score_reference": float(100 - i * 9 - (11 if i == 4 else 0))}
            for i in range(1, 7)]
    signal = latest.build_up_signal(rows) if active else {"level": 0}
    down = {"level": 0, "available": True}
    result = {
        "race_id": code, "prediction_type": "直前",
        "prediction_quality": {"status": "normal", "recovery_needed": False},
        "boats": rows, "up_signal": signal, "down_signal": down,
        "ai_score_prediction": {"points": 8, "combinations": []},
        "signal_ai_prediction": None,
    }
    if stored and active:
        result["signal_ai_prediction"] = latest.build_signal_ai_prediction(
            rows, signal, down, latest.load_signal_ai_config()
        )
    return result


class ConfigRegression(unittest.TestCase):
    def test_registry_and_weights(self):
        configs = {k: production_config.load_config(k)[0] for k in production_config.KINDS}
        self.assertEqual(configs["morning"]["grade_prior"], {"A1": 1, "A2": .75, "B1": .45, "B2": .25})
        self.assertEqual(configs["morning"]["score_weights"], {
            "racer_course": .40, "grade": .20, "motor": .20,
            "boat": .05, "national_top2": .15
        })
        self.assertEqual(configs["live"]["score_weights"], {
            "structural": .80, "exhibition_time": .06, "exhibition_st": .14
        })
        self.assertEqual(configs["purchase"]["signal_ai"]["purchase_points"], 24)

    def test_morning_scores_identical_for_samples(self):
        cfg, _ = production_config.load_config("morning")
        random.seed(11)
        for _ in range(100):
            cwin, ctop2, ctop3, cst, grade, motor_win, motor_top3, boat_top2, boat_top3, nat = (
                random.random() for k in range(10)
            )
            old_c = .40*cwin+.20*ctop2+.30*ctop3+.10*cst
            old_m = .40*motor_win+.60*motor_top3
            old_b = .50*boat_top2+.50*boat_top3
            old = 100*(.40*old_c+.20*grade+.20*old_m+.05*old_b+.15*nat)
            nw, mw, bw, ow = (cfg[x] for x in (
                "racer_course_weights", "motor_weights", "boat_weights", "score_weights"
            ))
            c = nw["course_win"]*cwin+nw["course_top2"]*ctop2+nw["course_top3"]*ctop3+nw["course_avg_st"]*cst
            m = mw["motor_win"]*motor_win+mw["motor_top3"]*motor_top3
            b = bw["boat_top2"]*boat_top2+bw["boat_top3"]*boat_top3
            new = 100*(ow["racer_course"]*c+ow["grade"]*grade+ow["motor"]*m+ow["boat"]*b+ow["national_top2"]*nat)
            self.assertEqual(old, new)

    def test_live_scores_identical_for_samples(self):
        cfg, _ = production_config.load_config("live")
        w = cfg["score_weights"]
        for a,b,c in [(10,0.4,0.8), (95,1,0), (62,0.5,0.4), (50,0.5,0.5)]:
            self.assertEqual(round(100*(.80*a/100+.06*b+.14*c),2),
                             round(100*(w["structural"]*a/100+w["exhibition_time"]*b+w["exhibition_st"]*c),2))


class CanonicalContract(unittest.TestCase):
    def _canonical(self, rows):
        return canonicalize(rows, target_date="20261009", config_manifest=production_config.loaded_manifest())

    def test_signal_replays_24_from_saved_scores_only(self):
        race = sample_race(stored=False)
        result = self._canonical([race])[0]
        self.assertTrue(result["canonical_signal_key"])
        self.assertEqual(result["canonical_strategy"], "signal_ai_24")
        self.assertEqual(len(result["signal_ai_prediction"]["all_120_combinations"]), 120)
        self.assertEqual(len({x["combination"] for x in result["signal_ai_prediction"]["combinations"]}), 24)
        self.assertEqual(result["signal_ai_replay"]["original_ticket_record"], False)
        self.assertEqual(result["ai_score_prediction"]["points"], 8)

    def test_already_saved_tickets_remain_unchanged(self):
        race = sample_race(stored=True)
        before = json.dumps(race["signal_ai_prediction"], sort_keys=True)
        result = self._canonical([race])[0]
        self.assertEqual(json.dumps(result["signal_ai_prediction"], sort_keys=True), before)
        self.assertNotIn("signal_ai_replay", result)

    def test_missing_live_scores_does_not_fall_back_to_normal_eight(self):
        race = sample_race(stored=False)
        race["boats"] = []
        result = self._canonical([race])[0]
        self.assertEqual(result["canonical_strategy"], "signal_ai_unresolved")
        self.assertIn("missing_24_signal_tickets", result["canonical_quality"]["flags"])

    def test_no_signal_remains_normal(self):
        race = sample_race(active=False)
        result = self._canonical([race])[0]
        self.assertIsNone(result["canonical_signal_key"])
        self.assertEqual(result["canonical_strategy"], "normal_ai")

    def test_missing_live_signal_is_pending_not_normal_ai(self):
        race = sample_race(active=False)
        race["prediction_quality"] = {"status": "fallback", "recovery_needed": True}
        result = self._canonical([race])[0]
        self.assertEqual(result["canonical_strategy"], "live_signal_pending_recovery")
        self.assertIn("live_signal_pending_recovery", result["canonical_quality"]["flags"])

    def test_duplicate_ids_rejected(self):
        r = sample_race()
        with self.assertRaises(ValueError):
            self._canonical([r,r])

    def test_completed_reader_prefers_canonical(self):
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp) / "2026/10/09/canonical"
            d.mkdir(parents=True)
            p = d / "race_predictions_20261009.json"
            p.write_text('{"races":[]}', encoding="utf-8")
            self.assertEqual(comparison.locate_formation_file(temp,"20261009"), p)

    def test_markers_and_24_ticket_decision_share_same_key(self):
        r = sample_race(stored=True)
        can = self._canonical([r])[0]
        self.assertEqual(signal_key(can), can["signal_ai_prediction"]["signal_key"])


if __name__ == "__main__":
    unittest.main()
