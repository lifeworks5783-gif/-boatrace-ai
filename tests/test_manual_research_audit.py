"""Manual research mode: verified official replay is valid even after the deadline."""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "collectors"))
from research_audit_policy import load_policy, score_integrity, audit_research_predictions


def valid_race(rid, status="recovered_observation", restored=True):
    return {
        "race_id": rid,
        "prediction_type": "直前",
        "generated_at": "2026-10-10T15:00:00+09:00",
        "deadline": "2026-10-10T12:00:00+09:00",
        "retrospective_score_recovery": restored,
        "prediction_quality": {
            "status": status, "result_leakage": False,
            "provenance": "post_result_official_beforeinfo",
        },
        "boats": [{"boat": n, "score": 77.0 - n} for n in range(1, 7)],
        "up_signal": {"available": True, "level": 0},
        "down_signal": {"available": True, "level": 0},
    }


class ManualResearchAuditTests(unittest.TestCase):
    def test_policy_declares_offline_manual_operation(self):
        p = load_policy(REPO)
        self.assertEqual(p["mode"], "manual_research")
        self.assertIs(p["automatic_collection_enabled"], False)

    def test_reconstructed_official_scores_valid_regardless_of_generation_time(self):
        r = valid_race("20261010-02-05")
        self.assertEqual(score_integrity(r), (True, "valid_official_research_prediction"))

    def test_race_not_finished_is_not_an_audit_failure(self):
        old = valid_race("20261010-02-05")
        pending = {"race_id":"20261010-02-06", "prediction_type":"朝", "boats":[]}
        payload = {"races":[old, pending]}
        q = audit_research_predictions(payload, {"20261010-02-05"})
        self.assertEqual(q["research_status"], "PASS")
        self.assertEqual(q["valid_research_races"], 1)
        self.assertEqual(q["manual_official_reconstruction_races"], 1)
        self.assertEqual(q["requires_manual_completion"], 0)
        self.assertEqual(q["not_yet_finished_races_excluded_from_error"], 1)
        self.assertIs(q["historical_bet_claimed_for_recovered_scores"], False)

    def test_real_missing_data_stays_visible_not_fabricated(self):
        no_score = valid_race("20261010-18-09")
        no_score["boats"][0].pop("score")
        q = audit_research_predictions({"races":[no_score]}, {"20261010-18-09"})
        self.assertEqual(q["research_status"], "MANUAL_RECONCILIATION_PENDING")
        self.assertEqual(q["requires_manual_completion"], 1)

    def test_live_capture_fallback_only_invalid_until_official_scored(self):
        missing = valid_race("20261010-23-10", "fallback")
        self.assertEqual(score_integrity(missing)[0], False)

    def test_genuine_saved_live_is_just_as_valid(self):
        r = valid_race("20261010-09-06", status="normal", restored=False)
        self.assertTrue(score_integrity(r)[0])


if __name__ == "__main__":
    unittest.main()
