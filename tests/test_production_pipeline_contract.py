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
from build_canonical_race_records import canonicalize, signal_key, hydrate_recovered_live
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

    def test_legacy_score_provenance_is_not_guessed(self):
        race = sample_race(stored=True)
        race["score_model_version"] = "previous_saved_live_model"
        can = self._canonical([race])[0]
        provenance = can["canonical_model_manifest"]
        self.assertEqual(provenance["source_score_model_version"], "previous_saved_live_model")
        self.assertFalse(provenance["source_score_config_identified"])
        self.assertIsNone(provenance["source_score_logic_config"])

    def test_restored_official_live_replays_signal_but_preserves_normal_bet(self):
        first = sample_race(active=False)
        first["prediction_quality"] = {"status":"fallback","recovery_needed":True}
        first["formation"] = {"points":8,"combinations":["1-2-3"]}
        before_bet = json.dumps(first["formation"],sort_keys=True)
        before_normal = json.dumps(first["ai_score_prediction"],sort_keys=True)
        recovered = sample_race(active=True)
        recovered["prediction_quality"] = {
            "status":"recovered_observation",
            "provenance":"post_result_official_beforeinfo",
            "result_leakage":False
        }
        with tempfile.TemporaryDirectory() as d:
            fp = Path(d)/"predictions/2026/10/09/live/live_predictions_final_20261009.json"
            fp.parent.mkdir(parents=True)
            fp.write_text(json.dumps({
                "target_date":"20261009",
                "model_version":"verified_historical_recovery_model",
                "races":[recovered]
            }),encoding="utf-8")
            hydrated = hydrate_recovered_live(
                [first],date="20261009",root=Path(d),
                signal_ai_config=latest.load_signal_ai_config()
            )
        final = self._canonical(hydrated)[0]
        self.assertEqual(final["canonical_strategy"],"signal_ai_24")
        self.assertEqual(len(final["signal_ai_prediction"]["combinations"]),24)
        self.assertEqual(json.dumps(final["formation"],sort_keys=True),before_bet)
        self.assertEqual(json.dumps(final["ai_score_prediction"],sort_keys=True),before_normal)
        self.assertFalse(final["signal_ai_replay"]["original_ticket_record"])
        self.assertTrue(final["historical_bet_preserved"])
        self.assertEqual(final["score_model_version"],"verified_historical_recovery_model")

    def test_recovery_manifest_csv_replays_signal_without_touching_normal_bet(self):
        first = sample_race(active=False)
        first["prediction_quality"] = {"status":"fallback","recovery_needed":True}
        first["formation"] = {"points":8,"combinations":["1-2-3"]}
        observations = sample_race(active=True)["boats"]
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)/"evaluations/2026/10/09/recovery"
            base.mkdir(parents=True)
            (base/"live_recovery_manifest_20261009.json").write_text(json.dumps({
                "date":"20261009", "status":"partial",
                "treat_recovered_as_observation":True,
                "result_leakage":False,
                "recovered_races":["202610090101"]
            }),encoding="utf-8")
            import csv
            with (base/"merged_live_predictions_20261009.csv").open("w",newline="",encoding="utf-8") as fh:
                writer=csv.DictWriter(fh,fieldnames=[
                    "race_id","boat","rank","score","morning_score_reference","racer_name"
                ])
                writer.writeheader()
                for o in observations:
                    writer.writerow({
                        "race_id":"20261009-01-01",
                        "boat":o["boat"],
                        "rank":o["rank"],
                        "score":o["score"],
                        "morning_score_reference":o["morning_score_reference"],
                        "racer_name":"保存済み選手",
                    })
            hydrated=hydrate_recovered_live(
                [first],date="20261009",root=Path(folder),
                signal_ai_config=latest.load_signal_ai_config()
            )
        final=self._canonical(hydrated)[0]
        self.assertEqual(final["canonical_strategy"],"signal_ai_24")
        self.assertTrue(final["historical_bet_preserved"])
        self.assertEqual(final["formation"],first["formation"])
        self.assertEqual(final["ai_score_prediction"],first["ai_score_prediction"])
        self.assertFalse(final["signal_ai_replay"]["original_ticket_record"])
        self.assertFalse(final["canonical_model_manifest"]["source_score_config_identified"])

    def test_unverified_restored_live_does_not_enter_canonical(self):
        first = sample_race(active=False)
        first["prediction_quality"] = {"status":"fallback","recovery_needed":True}
        recovered = sample_race(active=True)
        recovered["prediction_quality"] = {
            "status":"recovered_observation",
            "provenance":"post_result_official_beforeinfo",
            "result_leakage":True
        }
        with tempfile.TemporaryDirectory() as d:
            fp = Path(d)/"predictions/2026/10/09/live/live_predictions_final_20261009.json"
            fp.parent.mkdir(parents=True)
            fp.write_text(json.dumps({"target_date":"20261009","races":[recovered]}),encoding="utf-8")
            hydrated = hydrate_recovered_live(
                [first],date="20261009",root=Path(d),
                signal_ai_config=latest.load_signal_ai_config()
            )
        self.assertEqual(self._canonical(hydrated)[0]["canonical_strategy"],
                         "live_signal_pending_recovery")

    def test_original_score_config_is_preserved(self):
        race = sample_race(stored=True)
        race["score_logic_config"] = {"model_id":"live_v1","sha256":"012345"}
        can = self._canonical([race])[0]
        self.assertTrue(can["canonical_model_manifest"]["source_score_config_identified"])
        self.assertEqual(can["canonical_model_manifest"]["source_score_logic_config"],race["score_logic_config"])

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
