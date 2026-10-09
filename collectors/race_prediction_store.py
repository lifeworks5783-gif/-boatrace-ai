"""Single source of truth for race predictions, used before and after the race.

The existing formation_predictions_final_<date>.json already contains morning
snapshots, latest live scores, normal AI, Fujin/Raijin and its dedicated AI.
Read that ONE file in both views. Results/payouts are separate observations;
they must never be fed back to create an allegedly pre-deadline prediction.
"""
from __future__ import annotations

import json
from pathlib import Path


def canonical_path(date: str, root: str | Path = "predictions") -> Path:
    if len(date) != 8 or not date.isdigit():
        raise ValueError("Date must be YYYYMMDD")
    return (
        Path(root) / date[:4] / date[4:6] / date[6:8] / "live"
        / f"formation_predictions_final_{date}.json"
    )


def signal_key(race: dict) -> str | None:
    fujin = int((race.get("down_signal") or {}).get("level") or 0)
    raijin = int((race.get("up_signal") or {}).get("level") or 0)
    return f"F{fujin}R{raijin}" if fujin or raijin else None


def tickets24(race: dict) -> list[str]:
    prediction = race.get("signal_ai_prediction") or {}
    combos = prediction.get("all_120_combinations") or prediction.get("combinations") or []
    out = []
    for item in combos[:24]:
        if isinstance(item, dict):
            item = item.get("combination")
        out.append(str(item or ""))
    return out


def audit_race(race: dict) -> dict:
    key = signal_key(race)
    signal_prediction = race.get("signal_ai_prediction") or {}
    status = "ready"
    if key:
        picks = tickets24(race)
        if (
            signal_prediction.get("signal_key") != key
            or len(picks) != 24
            or len(set(picks)) != 24
            or any(len(p.split("-")) != 3 for p in picks)
        ):
            status = "missing_or_invalid_signal_24"
    elif (
        (race.get("up_signal") or {}).get("available") is False
        or (race.get("down_signal") or {}).get("available") is False
    ):
        status = "signal_not_yet_observable"
    return {
        "race_id": str(race.get("race_id") or ""),
        "signal_key": key,
        "signal_ai_status": status,
        "stage": race.get("prediction_type"),
        "recovered_after_result": bool(race.get("retrospective_signal_recovery")),
        "signal_detected_at_original_deadline": race.get("signal_detected_at_original_deadline"),
    }


def load_canonical(date: str, root: str | Path = "predictions") -> dict:
    path = canonical_path(date, root)
    if not path.is_file():
        raise FileNotFoundError(f"Canonical pre-result prediction missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if str(payload.get("target_date")) != date:
        raise ValueError(f"Canonical prediction date mismatch: {path}")
    races = payload.get("races")
    if not isinstance(races, list):
        raise ValueError(f"Canonical races missing: {path}")
    seen: set[str] = set()
    for race in races:
        identifier = str(race.get("race_id") or "")
        if not identifier or identifier in seen:
            raise ValueError(f"Duplicate/invalid race id: {identifier!r}")
        seen.add(identifier)
    return payload


def audit_canonical(payload: dict) -> dict:
    records = [audit_race(race) for race in payload["races"]]
    return {
        "date": payload["target_date"],
        "total": len(records),
        "active_signals": sum(bool(r["signal_key"]) for r in records),
        "missing_signal_24": sum(r["signal_ai_status"] == "missing_or_invalid_signal_24" for r in records),
        "pending_signal_observation": sum(r["signal_ai_status"] == "signal_not_yet_observable" for r in records),
        "details": records,
    }
