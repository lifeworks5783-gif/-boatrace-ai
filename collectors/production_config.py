"""Versioned production settings with strict validation and reproducible hashes.

The four configs are baseline snapshots until consumers explicitly wire them.
Historical calculations must pin their config version rather than follow active.json.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KINDS = ("morning", "live", "signal", "purchase")


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_config(kind, *, registry=None, root=ROOT):
    if kind not in KINDS:
        raise ValueError("unknown production config: " + str(kind))
    root = Path(root).resolve()
    manifest = _json(Path(registry) if registry is not None else root / "config/production/active.json")
    rel = manifest["models"][kind]
    location = (root / rel).resolve()
    if not location.is_relative_to(root):
        raise ValueError("config must remain within repository")
    raw = location.read_bytes()
    config = json.loads(raw.decode("utf-8"))
    if config.get("schema_version") != 1 or not config.get("model_id"):
        raise ValueError("invalid config schema " + rel)
    _validate(kind, config)
    return config, {"model_id": config["model_id"], "source": rel,
                    "sha256": hashlib.sha256(raw).hexdigest()}


def _positive_weights(weights, name):
    if not weights or any(float(x) < 0 for x in weights.values()):
        raise ValueError(name + " has missing/negative weights")
    if abs(sum(float(x) for x in weights.values()) - 1.0) > 1e-9:
        raise ValueError(name + " weights must total 1")


def _validate(kind, config):
    if kind == "morning":
        for name in ("score_weights", "racer_course_weights", "motor_weights", "boat_weights"):
            _positive_weights(config[name], name)
        if sorted(config["grade_prior"]) != ["A1", "A2", "B1", "B2"]:
            raise ValueError("grade prior incomplete")
    elif kind == "live":
        _positive_weights(config["score_weights"], "live.score_weights")
        if float(config["st_delta_denominator_seconds"]) <= 0:
            raise ValueError("ST denominator must be positive")
    elif kind == "signal":
        if float(config["raijin"]["rise_min"]) <= 0:
            raise ValueError("Raijin threshold invalid")
        if int(config["fujin"]["level_cap"]) != 3:
            raise ValueError("Fujin level cap invalid")
    elif kind == "purchase":
        if int(config["stake_yen_per_ticket"]) != 100:
            raise ValueError("unexpected ticket unit stake")
        if int(config["signal_ai"]["purchase_points"]) != 24:
            raise ValueError("signal 24-ticket policy invalid")
        _positive_weights(config["signal_ai"]["ranking_formula"], "signal ranking")


def loaded_manifest(root=ROOT):
    return {kind: load_config(kind, root=root)[1] for kind in KINDS}
