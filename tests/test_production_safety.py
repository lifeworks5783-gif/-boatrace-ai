"""Production guardrails: immutable configuration, historical snapshots, AI fallback."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "collectors"))

import logic_registry
import build_latest_prediction_view as latest
from logic_registry import load_logic, LogicConfigurationError
from prediction_history_guard import preserve_closed_prediction

JST = timezone(timedelta(hours=9))


class ProductionSafetyTest(unittest.TestCase):
    def test_active_logic_has_identical_immutable_snapshot(self):
        for kind in ("morning", "live", "fujin_raijin"):
            cfg = load_logic(kind)
            p = logic_registry.LOGIC_DIR / f"{kind}.json"
            archived = logic_registry.LOGIC_DIR / "versions" / kind / (cfg["model_version"] + ".json")
            self.assertEqual(p.read_bytes(), archived.read_bytes())
            self.assertEqual(len(cfg["_sha256"]), 64)

    def test_mutation_without_new_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            current = json.loads((logic_registry.LOGIC_DIR / "morning.json").read_text(encoding="utf-8"))
            version = current["model_version"]
            (root / "versions" / "morning").mkdir(parents=True)
            original = json.dumps(current, ensure_ascii=False).encode()
            (root / "versions" / "morning" / (version + ".json")).write_bytes(original)
            current["weights"]["grade"] = 30
            current["weights"]["racer_course"] = 30
            (root / "morning.json").write_text(json.dumps(current), encoding="utf-8")
            with patch.object(logic_registry, "LOGIC_DIR", root):
                with self.assertRaises(LogicConfigurationError):
                    load_logic("morning")

    def test_historical_record_is_not_recalculated_on_later_refresh(self):
        prior = {
            "race_id": "20261009-14-01", "deadline": "2026-10-09T12:00:00+09:00",
            "generated_at": "2026-10-09T11:48:00+09:00",
            "prediction_type": "直前", "boats": [{"score": 51}],
            "formation": {"combinations": ["1-2-3"]},
        }
        altered = {
            **prior, "boats": [{"score": 90}],
            "formation": {"combinations": ["6-5-4"]},
            "generated_at": "2026-10-09T12:15:00+09:00",
        }
        self.assertEqual(
            preserve_closed_prediction(prior, altered, datetime(2026, 10, 9, 12, 30, tzinfo=JST)),
            prior,
        )
        self.assertEqual(
            preserve_closed_prediction(prior, altered, datetime(2026, 10, 9, 11, 59, tzinfo=JST)),
            altered,
        )

    def test_proven_predeadline_live_is_allowed_over_morning_after_deadline(self):
        prior = {
            "deadline": "2026-10-09T12:00:00+09:00",
            "generated_at": "2026-10-09T08:00:00+09:00",
            "prediction_type": "朝",
        }
        live = {**prior, "prediction_type": "直前",
                "generated_at": "2026-10-09T11:51:00+09:00"}
        late = {**live, "generated_at": "2026-10-09T12:10:00+09:00"}
        now = datetime(2026, 10, 9, 12, 30, tzinfo=JST)
        self.assertEqual(preserve_closed_prediction(prior, live, now), live)
        self.assertEqual(preserve_closed_prediction(prior, late, now), prior)

    def test_recovery_is_allowed_but_frozen_after_completed_evaluation(self):
        base = {
            "race_id": "a", "deadline": "2026-10-09T12:00:00+09:00",
            "generated_at": "2026-10-09T11:50:00+09:00",
            "prediction_type": "直前",
            "up_signal": {"level": 1}, "down_signal": {"level": 0},
            "signal_ai_prediction": {
                "signal_key": "F0R1",
                "combinations": [{"combination": f"1-2-{x}"} for x in range(1, 25)],
            },
            "retrospective_signal_recovery": True,
        }
        now = datetime(2026, 10, 9, 12, 30, tzinfo=JST)
        replay = {**base, "boats": [{"score": 95}],
                  "prediction_quality": {"status": "recovered_observation"}}
        # Existing official replay is already complete; numerical upgrades do not rewrite it.
        self.assertEqual(preserve_closed_prediction(base, replay, now), base)
        # A missing historical signal prediction may still be fixed from verified official inputs.
        incomplete = {**base, "signal_ai_prediction": {}}
        self.assertEqual(preserve_closed_prediction(incomplete, replay, now), replay)

    def test_normal_ai_default_has_external_immutable_version(self):
        default = latest.DEFAULT_AI_SCORE_CONFIG_PATH
        config = latest.load_ai_score_config("20261009")
        self.assertEqual(config["_source"], str(default))
        self.assertEqual(config["purchase_points"], 8)
        self.assertEqual(config["display_points"], 12)
        archive = default.parent / "versions" / "ai_finish_order_score_v0_20261005.json"
        self.assertEqual(default.read_bytes(), archive.read_bytes())
        with patch.object(latest, "DEFAULT_AI_SCORE_CONFIG_PATH", default.parent / "missing_model.json"):
            with self.assertRaises(FileNotFoundError):
                latest.load_ai_score_config("20261009")


if __name__ == "__main__":
    unittest.main()
