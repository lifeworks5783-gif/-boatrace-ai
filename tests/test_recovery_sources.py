"""Official retry must remain cumulative and replayable after later batches."""
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "collectors"))

from recover_missing_live_for_analysis import merge_official_snapshots, unverified_canonical_race_ids
from recovery_live_overlay import load_verified_recovered_live, ROOT


class RecoverySourceTest(unittest.TestCase):
    def test_old_official_scratched_starter_survives_new_retry_batch(self):
        old = [
            {"race_id": "20261009-23-03", "boat": "4", "is_miss": "True"},
            {"race_id": "20261009-23-03", "boat": "1", "is_miss": "False"},
        ]
        new = [
            {"race_id": "20261009-14-01", "boat": "1", "is_miss": "False"},
            {"race_id": "20261009-23-03", "boat": "1", "is_miss": "False"},
        ]
        combined = merge_official_snapshots(old, new, boat_key=True)
        self.assertEqual(len(combined), 3)
        scratched = [x for x in combined if x["race_id"] == "20261009-23-03" and x["boat"] == "4"]
        self.assertEqual(len(scratched), 1)
        self.assertEqual(scratched[0]["is_miss"], "True")

    def test_canonical_morning_or_fallback_enters_recovery_queue(self):
        rows = [
            {"race_id": "20261013-04-06", "prediction_type": "朝", "quality_status": "normal"},
            {"race_id": "20261013-11-05", "prediction_type": "朝", "quality_status": "normal"},
            {"race_id": "20261013-12-12", "prediction_type": "直前", "quality_status": "fallback"},
            {"race_id": "20261013-19-05", "prediction_type": "直前", "quality_status": "fallback"},
            {"race_id": "20261013-19-12", "prediction_type": "直前", "quality_status": "normal"},
            {"race_id": "20261013-04-03", "prediction_type": "直前", "quality_status": "recovered_observation"},
        ]
        self.assertEqual(unverified_canonical_race_ids(rows), {
            "202610130406", "202610131105", "202610131212", "202610131905"
        })

    def test_current_verified_recovery_has_all_manifest_races(self):
        date = "20261009"
        folder = ROOT / "evaluations" / "2026" / "10" / "09" / "recovery"
        manifest = json.loads((folder / f"live_recovery_manifest_{date}.json").read_text(encoding="utf-8"))
        recovered = load_verified_recovered_live(date)
        self.assertEqual(
            {"".join(c for c in key if c.isdigit()) for key in recovered},
            set(manifest["recovered_races"]),
        )
        self.assertEqual(
            recovered["20261009-23-03"]["prediction_quality"]["verified_scratched_boats"],
            [4],
        )


if __name__ == "__main__":
    unittest.main()
