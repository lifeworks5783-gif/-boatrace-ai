"""Cumulative 5k payout history must be honest, paired and presentation-only."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "collectors"))
from signal_high_payout_display import (
    parse_cumulative, load_cumulative, combined_badge, combination_table,
)

ROOT = Path(__file__).resolve().parents[1]


def synthetic():
    groups = {}
    for f in range(4):
        for r in range(4):
            groups[f"F{f}R{r}"] = {
                "races": 20, "payout_ge5000": 8, "payout_ge10000": 2
            }
    groups["F3R3"] = {"races": 1, "payout_ge5000": 0, "payout_ge10000": 0}
    groups["F0R1"] = {"races": 100, "payout_ge5000": 37, "payout_ge10000": 20}
    all_rows = sum(g["races"] for g in groups.values())
    all_h5 = sum(g["payout_ge5000"] for g in groups.values())
    all_h10 = sum(g["payout_ge10000"] for g in groups.values())
    return {
        "model_version": "fujin_raijin_pipeline_v2_20261011",
        "source_coverage": {"available_dates": ["20261012", "20261013"]},
        "periods": {"all": {"races": all_rows,
                            "payout_ge5000": all_h5,
                            "payout_ge10000": all_h10,
                            "by_signal": groups}}
    }


class PairedCumulativeRateTests(unittest.TestCase):
    def test_all_sixteen_are_paired_and_denominators_match(self):
        h = parse_cumulative(synthetic())
        self.assertIsNotNone(h)
        self.assertEqual(len(h["groups"]), 16)
        self.assertEqual(h["groups"]["F0R1"], {"n": 100, "high5": 37, "high10": 20})
        self.assertEqual(h["groups"]["F3R3"]["n"], 1)
        self.assertEqual(sum(g["n"] for g in h["groups"].values()), h["n"])

    def test_marginal_raijin_or_fujin_is_never_substituted(self):
        h = parse_cumulative(synthetic())
        html = combined_badge(0, 1, h)
        self.assertIn('data-signal="F0R1"', html)
        self.assertIn('data-history-races="100"', html)
        self.assertIn("37.0%", html)
        self.assertIn("37/100R", html)
        self.assertNotIn("F1R0", html)
        self.assertIn("10,000円以上", html)
        self.assertIn("2026/10/12〜2026/10/13", html)
        self.assertIn("個別レースの確定予測確率ではありません", html)
        self.assertEqual(combined_badge(0, 0, h), "")

    def test_small_sample_never_claims_zero_percent_confidence(self):
        h = parse_cumulative(synthetic())
        html = combined_badge(3, 3, h)
        self.assertIn("母数不足 1R", html)
        self.assertIn("0/1R", html)
        self.assertNotIn("0.0%", html)
        html_small = combined_badge(1, 2, h)
        self.assertIn("少数参考", html_small)

    def test_corrupt_or_stale_inputs_fail_closed_without_false_zero(self):
        p = synthetic()
        p["periods"]["all"]["by_signal"]["F0R1"]["payout_ge5000"] = 101
        self.assertIsNone(parse_cumulative(p))
        self.assertIsNone(parse_cumulative({"model_version": "legacy"}))
        self.assertIsNone(parse_cumulative({}))
        missing = combined_badge(1, 1, None)
        self.assertIn("集計待ち", missing)
        self.assertNotIn("0.0%", missing)
        self.assertNotIn("今回の個別レースの確定", missing)

    def test_full_analysis_table_contains_all_sixteen_and_baseline(self):
        h = parse_cumulative(synthetic())
        panel = combination_table(h)
        self.assertEqual(panel.count('<tr data-signal="'), 16)
        self.assertIn('data-signal="F0R0"', panel)
        self.assertIn('data-signal="F3R3"', panel)
        self.assertIn("37.0%", panel)
        self.assertIn("母数不足（10R未満）", panel)
        self.assertIn("5,000円以上発生実績（累計）", panel)
        self.assertIn("F0R0は両方未発動", panel)
        self.assertNotIn("ROI", panel)
        self.assertNotIn("回収率", panel)

    def test_real_saved_summary_and_consistency(self):
        p = ROOT / "evaluations/signal_payout_rank_distribution/latest/summary.json"
        if not p.is_file():
            self.skipTest("Repository checkout omitted historic summary")
        data = json.loads(p.read_text(encoding="utf-8"))
        h = parse_cumulative(data)
        self.assertIsNotNone(h)
        self.assertEqual(h["high5"], sum(x["high5"] for x in h["groups"].values()))
        self.assertEqual(h["high10"], sum(x["high10"] for x in h["groups"].values()))
        self.assertTrue(h["dates"][0] <= h["dates"][1])
        for k, group in h["groups"].items():
            self.assertIn(k, data["periods"]["all"]["by_signal"])
            badge = combined_badge(int(k[1]), int(k[3]), h)
            if k != "F0R0":
                self.assertIn(f'data-signal="{k}"', badge)
                self.assertIn(f'data-history-high5="{group["high5"]}"', badge)

    def test_signal_icons_remain_in_race_title_history_stays_below(self):
        from build_family_prediction_page import (
            signal_marker, signal_high5_history_line, build_card, build_ai_card,
        )
        h = parse_cumulative(synthetic())
        race = {
            "race_id": "202610140101", "venue_name": "桐生", "race": 7,
            "deadline": "2026-10-14T18:00:00+09:00",
            "prediction_type": "直前",
            "down_signal": {"level": 2, "metrics": {}},
            "up_signal": {"level": 1, "candidates": []},
        }
        with patch("build_family_prediction_page.load_cumulative", return_value=h):
            icons = signal_marker(race)
            history = signal_high5_history_line(race)
            normal = build_card(race, 1)
            with patch("build_family_prediction_page.audit_race", return_value={
                "signal_key": "F2R1", "signal_ai_status": "ready"
            }):
                ai = build_ai_card(race, 1)
            with patch("build_family_prediction_page.audit_race", return_value={
                "signal_key": "F2R1", "signal_ai_status": "repair_needed"
            }):
                ai_repair = build_ai_card(race, 1)
        self.assertIn("💨", icons)
        self.assertIn("⚡", icons)
        self.assertIn("fujin-raijin-stack", icons)
        self.assertNotIn("signal-high5-history", icons)
        self.assertNotIn("37.0%", icons)
        self.assertIn('class="signal-history-line"', history)
        self.assertIn('data-signal="F2R1"', history)

        import re
        # Marker stays WITHIN title, separate history block is immediately
        # AFTER title in its original race-main (not part of icon group).
        for page in (normal, ai, ai_repair):
            pattern = (
                r'<div class="race-name">[^<]*桐生 7R'
                r'<span class="fujin-raijin-stack".*?</span>'
                r'</div>\s*<div class="signal-history-line">'
                r'<span class="signal-high5-history[^"]*".*?'
                r'data-signal="F2R1"'
            )
            self.assertRegex(page, re.compile(pattern, re.DOTALL))
            self.assertEqual(page.count('class="signal-history-line"'), 1)
            self.assertEqual(page.count('data-signal="F2R1"'), 1)
            # Title must be closed before historic rate starts.
            title = page.split('<div class="race-name">', 1)[1].split('</div>', 1)[0]
            self.assertIn("fujin-raijin-stack", title)
            self.assertNotIn("signal-high5-history", title)

    def test_no_signal_does_not_add_a_history_line(self):
        from build_family_prediction_page import signal_marker, signal_high5_history_line
        race = {"up_signal": {"level": 0}, "down_signal": {"level": 0}}
        self.assertEqual(signal_marker(race), "")
        self.assertEqual(signal_high5_history_line(race), "")


if __name__ == "__main__":
    unittest.main()
