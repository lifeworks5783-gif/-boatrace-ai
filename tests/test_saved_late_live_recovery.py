"""Prove predeadline official exhibition + late scoring is retrospective, not a bet."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collectors"))

from recovery_live_overlay import join_verified_late_saved_live
from build_latest_prediction_view import build_up_signal, build_down_signal
from prediction_history_guard import preserve_closed_prediction
from datetime import datetime, timezone, timedelta

DATE = "20261010"
IDS = {
    "20261010-02-05", "20261010-08-06",
    "20261010-18-09", "20261010-23-10",
}
TIMELY_IDS = {"20261010-09-06", "20261010-16-05", "20261010-22-05"}


class SavedLateLiveRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / "predictions" / "2026" / "10" / "10" / "live" / "live_predictions_final_20261010.json"
        cls.races = {r["race_id"]: r for r in json.loads(path.read_text(encoding="utf-8"))["races"]}

    def test_four_delayed_predictions_recovered_without_changing_three_genuine(self):
        joined, patched = join_verified_late_saved_live(self.races, DATE)
        self.assertEqual(set(patched), IDS)
        self.assertEqual(set(joined), IDS | TIMELY_IDS)
        for rid in TIMELY_IDS:
            self.assertIs(joined[rid], self.races[rid])
        for rid in IDS:
            row = joined[rid]
            quality = row["prediction_quality"]
            self.assertEqual(quality["status"], "recovered_observation")
            self.assertEqual(quality["provenance"], "saved_pre_deadline_official_beforeinfo")
            self.assertTrue(quality["prediction_generated_after_deadline"])
            self.assertTrue(quality["retrospective_simulation_only"])
            self.assertIs(quality["result_leakage"], False)
            self.assertEqual(len(row["boats"]), 6)
            self.assertTrue(quality["source"].startswith("daily_inputs/"))
            self.assertEqual(row["boats"], self.races[rid]["boats"])
            self.assertTrue(build_up_signal(row["boats"], quality)["available"])
            self.assertTrue(build_down_signal(row["boats"], quality)["available"])

    def test_predeadline_generated_scores_stay_genuine(self):
        timely = dict(self.races["20261010-18-09"])
        timely["generated_at"] = "2026-10-10T12:41:00+09:00"
        joined, patched = join_verified_late_saved_live({"20261010-18-09": timely}, DATE)
        self.assertEqual(patched, [])
        self.assertIs(joined["20261010-18-09"], timely)

    def test_unmatched_starter_cannot_be_certified(self):
        altered = dict(self.races["20261010-18-09"])
        boats = [dict(b) for b in altered["boats"]]
        boats[0]["registration_no"] = "999999"
        altered["boats"] = boats
        joined, patched = join_verified_late_saved_live({"20261010-18-09": altered}, DATE)
        self.assertEqual(patched, [])
        self.assertIs(joined["20261010-18-09"], altered)

    def test_guard_accepts_verified_recovery_but_not_unverified_late_score(self):
        previous = {
            "race_id": "20261010-18-09", "prediction_type": "直前",
            "deadline": "2026-10-10T12:42:00+09:00",
            "generated_at": "2026-10-10T12:40:00+09:00",
            "prediction_quality": {"status": "fallback"},
            "formation": {"combinations": ["1-2-3"]},
        }
        recovered = {
            **previous,
            "generated_at": "2026-10-10T12:55:52+09:00",
            "prediction_quality": {"status": "recovered_observation"},
        }
        now = datetime(2026, 10, 10, 13, 20, tzinfo=timezone(timedelta(hours=9)))
        self.assertIs(preserve_closed_prediction(previous, recovered, now), recovered)
        unchecked = {**recovered, "prediction_quality": {"status": "normal"}}
        self.assertIs(preserve_closed_prediction(previous, unchecked, now), previous)


if __name__ == "__main__":
    unittest.main()
