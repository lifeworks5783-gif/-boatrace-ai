"""Versioned, fail-closed scoring configuration shared by all pipeline stages.

The code controls *how* inputs are processed. JSON controls the adopted
numerical logic. Every generated record must retain its model/hash provenance.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGIC_DIR = ROOT / "config" / "logic"
LOGIC_TYPES = {"morning", "live", "fujin_raijin", "formation"}


class LogicConfigurationError(ValueError):
    pass


def load_logic(kind: str) -> dict:
    if kind not in LOGIC_TYPES:
        raise LogicConfigurationError(f"Unknown logic kind: {kind!r}")
    path = LOGIC_DIR / f"{kind}.json"
    if not path.is_file():
        raise LogicConfigurationError(f"Required logic configuration missing: {path}")
    data_bytes = path.read_bytes()
    try:
        config = json.loads(data_bytes)
    except (ValueError, UnicodeDecodeError) as exc:
        raise LogicConfigurationError(f"Invalid logic JSON {path}") from exc
    if not isinstance(config, dict) or config.get("schema_version") != 1:
        raise LogicConfigurationError(f"Invalid logic schema: {path}")
    if not isinstance(config.get("model_version"), str) or not config["model_version"]:
        raise LogicConfigurationError(f"Missing model_version: {path}")
    # Every adopted numerical model has a byte-for-byte archived original.
    # The current pointer may advance, but an existing version must not mutate.
    version = config["model_version"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", version):
        raise LogicConfigurationError(f"Invalid model version path: {version!r}")
    archive = LOGIC_DIR / "versions" / kind / f"{version}.json"
    if not archive.is_file() or archive.read_bytes() != data_bytes:
        raise LogicConfigurationError(
            f"Immutable logic snapshot missing or changed: {archive}. "
            "Create a NEW model_version and snapshot instead of changing an adopted model."
        )
    if kind in {"morning", "live"}:
        weights = config.get("weights")
        if not isinstance(weights, dict) or not weights:
            raise LogicConfigurationError(f"Missing weights: {path}")
        if not all(type(v) in (int, float) and v >= 0 for v in weights.values()):
            raise LogicConfigurationError(f"Invalid weight in {path}")
        if abs(sum(weights.values()) - 100) > 1e-8:
            raise LogicConfigurationError(f"Weights must total 100 in {path}")
    elif kind == "formation":
        thresholds = config.get("thresholds")
        points = config.get("maximum_points")
        if not isinstance(thresholds, dict) or not isinstance(points, dict):
            raise LogicConfigurationError("Formation thresholds or point limits missing")
        required = ("close_first_gap_lt", "strong_first_gap_gte",
                    "strong_second_gap_gte", "semi_anchor_gap_gte")
        if not all(type(thresholds.get(k)) in (int, float) and thresholds[k] >= 0 for k in required):
            raise LogicConfigurationError("Formation threshold invalid")
        if not thresholds["close_first_gap_lt"] <= thresholds["semi_anchor_gap_gte"] <= thresholds["strong_first_gap_gte"]:
            raise LogicConfigurationError("Formation thresholds out of order")
        if not all(type(points.get(k)) is int and points[k] > 0 for k in ("strong_first", "semi_anchor", "mixed")):
            raise LogicConfigurationError("Formation point limit invalid")
        if type(config.get("unit_yen")) is not int or config["unit_yen"] <= 0:
            raise LogicConfigurationError("Formation ticket unit invalid")
    elif kind == "fujin_raijin":
        detection = config.get("detection") or {}
        if not all(k in detection for k in ("raijin", "fujin")):
            raise LogicConfigurationError("Both signal detection rules are required")
        purchase = config.get("purchase") or {}
        if purchase.get("signal_points") != 24 or purchase.get("unit_yen") != 100:
            raise LogicConfigurationError("Active signal must evaluate 24 tickets at 100 yen")
        positions = ((config.get("scoring") or {}).get("combination_position_weights") or {})
        if set(positions) != {"first", "second", "third"} or abs(sum(positions.values()) - 1.0) > 1e-8:
            raise LogicConfigurationError("Signal combination weights must sum to 1")
        corrections = (config.get("scoring") or {}).get("correction_config_path")
        if not corrections or not (ROOT / corrections).is_file():
            raise LogicConfigurationError("Signal correction configuration missing")
    return {
        **config,
        "_source": str(path.relative_to(ROOT)),
        "_sha256": hashlib.sha256(data_bytes).hexdigest(),
    }


def logic_identity(config: dict) -> dict:
    return {
        "model_version": config["model_version"],
        "config_path": config["_source"],
        "config_sha256": config["_sha256"],
        "effective_date": config.get("effective_date"),
    }
