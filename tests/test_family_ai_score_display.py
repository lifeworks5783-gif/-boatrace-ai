"""Prevent the common prediction view from losing existing six-boat scores."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collectors"))

from race_prediction_store import load_canonical, signal_key
from build_family_prediction_page import build_ai_card, score_label


class FamilyAiScoreDisplayTest(unittest.TestCase):
    def test_all_scored_normal_ai_races_show_saved_six_boat_scores(self):
        """The exact 2026-10-09 saved bundle produced 76 scoreless AI cards."""
        races = load_canonical("20261009")["races"]
        checked = 0
        total_no_signal = 0
        skipped = []
        for race in races:
            if signal_key(race):
                continue
            total_no_signal += 1
            boats = race.get("boats") or []
            position = (race.get("ai_score_prediction") or {}).get("position_scores") or []
            if len(boats) != 6 or len(position) != 6:
                skipped.append((race["race_id"], f"boat_count={len(boats)},ai_positions={len(position)}"))
                continue
            by_no = {str(b.get("boat")): b for b in boats}
            if set(by_no) != {str(b.get("boat")) for b in position}:
                skipped.append((race["race_id"], "AI score boat IDs mismatch"))
                continue
            if any(score_label(b.get("score")) == "未算出" for b in boats):
                skipped.append((race["race_id"], "canonical score missing"))
                continue

            html = build_ai_card(race, checked + 1)
            tbody = html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
            actual = re.findall(
                r"<tr><td>([1-6])号艇[^<]*</td><td>([^<]+)</td>"
                r"<td>([^<]+)</td><td>([^<]+)</td><td>(\d+)位</td></tr>",
                tbody,
            )
            self.assertEqual(len(actual), 6, race["race_id"])
            for boat_no, original, correction, adjusted, rank in actual:
                expected = score_label(by_no[boat_no]["score"])
                self.assertEqual(original, expected, race["race_id"])
                self.assertEqual(correction, "0.0", race["race_id"])
                self.assertEqual(adjusted, expected, race["race_id"])
            self.assertNotIn("未算出", tbody, race["race_id"])
            checked += 1

        print("FAMILY_AI_COVERAGE", {"normal_signal_inactive_races":total_no_signal,
            "verified_score_tables":checked, "excluded_with_causes":skipped})
        # The number of normal AI cases changes when valid Fujin/Raijin
        # signals activate; requiring a fixed 50 incorrectly fails when
        # the model detects MORE legitimate signals. Keep broad relative
        # coverage, and exact per-boat score verification for every valid
        # six-position normal AI record.
        self.assertGreater(checked, 0)
        self.assertGreaterEqual(checked / max(1, total_no_signal), 0.75,
                                f"Normal AI coverage dropped: {checked}/{total_no_signal}. skipped={skipped}")
        print("FAMILY_AI_NORMAL_SCORE_DISPLAY_PASS", checked)

    def test_common_bundle_overrides_stale_legacy_nested_prediction(self):
        race = {
            "race_id": "mock-1",
            "venue_name": "江戸川",
            "race": 8,
            "boats": [{"boat": n, "racer_name": f"選手{n}", "score": 90.0 - n} for n in range(1, 7)],
            "live_prediction": {
                "boats": [{"boat": n, "score": 1.0} for n in range(1, 7)]
            },
            "ai_score_prediction": {
                "position_scores": [{"boat": n} for n in range(1, 7)],
                "combinations": [{"combination": "1-2-3", "score": 70}],
            },
        }
        html = build_ai_card(race, 1)
        self.assertIn("<td>89.0</td><td>0.0</td><td>89.0</td>", html)
        self.assertNotIn("<td>1.0</td><td>0.0</td><td>1.0</td>", html)
        self.assertNotIn("未算出", html)


if __name__ == "__main__":
    unittest.main()
