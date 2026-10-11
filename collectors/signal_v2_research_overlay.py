"""Research-only overlay for a finished race's CORRECTED rank-free Raijin v2.

Original canonical (possibly rank-gated v1) is immutable. A research overlay is
only returned with verified saved six-boat scores and independent V2 replay
parity. Never use official finish or payout to generate a signal or tickets.
"""
from __future__ import annotations

import csv
from pathlib import Path

from build_latest_prediction_view import (
    build_up_signal, build_down_signal, build_signal_ai_prediction,
    load_signal_ai_config, signal_field_is_verified, SIGNAL_LOGIC,
)
from evaluate_signal_ai_performance import load_live, _signal_inputs
from evaluate_down_signal import verified_signal_quality_by_race, normalize_race_id


def replay_rows(date, root=Path(".")):
    path = root / "evaluations/raijin_all_rank_v2_replay/daily" / date / "details.csv"
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return {normalize_race_id(row["race_id"]): row for row in csv.DictReader(stream)}


def finished_v2_overlays(date, *, root=Path(".")):
    """Read-only. No projection for unverified, missing, or unfinished scores."""
    root = Path(root)
    if not (root / "config/logic/fujin_raijin.json").exists():
        return {}
    if SIGNAL_LOGIC["model_version"] != "fujin_raijin_pipeline_v2_20261011":
        raise RuntimeError("Unexpected active signal detector: cannot project historical v2")
    replay = replay_rows(date, root)
    if not replay:
        return {}
    config = load_signal_ai_config()
    observations = load_live(date)
    qualities = verified_signal_quality_by_race(date)
    results = {}
    for race_id, item in replay.items():
        # An unfinished race must NEVER become a retrospectively diagnosed signal.
        actual = str(item.get("actual") or "").strip()
        if not actual:
            continue
        saved = observations.get(race_id)
        if not saved:
            raise RuntimeError(f"V2 replay has a finished race without six-boat observation: {race_id}")
        ranked = sorted(saved, key=lambda row: (
            int(float(row.get("rank") or 99)), int(float(row.get("boat") or 99))
        ))
        boats = _signal_inputs(ranked)
        quality = qualities.get(race_id) or {}
        if not signal_field_is_verified(boats, quality):
            # Replay may include excluded races without verified scores.
            continue
        up = build_up_signal(boats, quality, outside_live_top3=False)
        down = build_down_signal(boats, quality)
        expected_up = int(item["new_raijin_level"])
        expected_down = int(item["fujin_level"])
        if int(up["level"]) != expected_up or int(down["level"]) != expected_down:
            raise RuntimeError(f"Research replay / current detector drift: {race_id}")
        active = bool(expected_up or expected_down)
        if active != (str(item["new_active"]) == "True"):
            raise RuntimeError(f"Research replay / active flag drift: {race_id}")
        ai = build_signal_ai_prediction(boats, up, down, config)
        if active:
            if not ai or len(ai["combinations"]) != 24:
                raise RuntimeError(f"Research signal-24 missing: {race_id}")
            combos = ai["all_120_combinations"]
            rank = next((i for i, entry in enumerate(combos, start=1)
                         if entry["combination"] == actual), None)
            if rank is None or rank != int(item["new_actual_rank"]):
                raise RuntimeError(f"Research signal actual 120-rank drift: {race_id}")
            hit = any(c["combination"] == actual for c in ai["combinations"])
            if hit != (str(item["new_hit24"]) == "True"):
                raise RuntimeError(f"Research signal-24 hit drift: {race_id}")
        elif ai is not None:
            raise RuntimeError(f"F0R0 unexpectedly generated signal tickets: {race_id}")
        results[race_id] = {
            "up_signal": up, "down_signal": down,
            "signal_ai_prediction": ai or {},
            "signal_key": (f"F{expected_down}R{expected_up}" if active else None),
            "signal_ai_status": "ready" if active else "inactive",
            "recovered_after_result": True,
            "research_only": True,
            "model_version": SIGNAL_LOGIC["model_version"],
            "provenance": item.get("provenance") or "retrospective_replay",
            "corrected_actual_rank": int(item["new_actual_rank"]) if active else None,
        }
    return results
