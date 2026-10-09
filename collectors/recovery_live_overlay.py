"""Verified live beforeinfo recovery overlay for the ONE canonical prediction.

Only six-boat saved official beforeinfo-derived LIVE SCORES enter this layer.
No race results, actual order, payouts or odds are read. A retrospective
simulation must never be relabeled as a pre-deadline placed bet.
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

from logic_registry import ROOT


class RecoverySafetyError(ValueError):
    pass


def safe_float(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def load_verified_recovered_live(date: str, root: Path = ROOT) -> dict:
    if len(date) != 8 or not date.isdigit():
        raise RecoverySafetyError("Invalid recovery date")
    folder = root / "evaluations" / date[:4] / date[4:6] / date[6:8] / "recovery"
    manifest_path = folder / f"live_recovery_manifest_{date}.json"
    if not manifest_path.exists():
        return {}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("status") not in {"complete", "partial"}
        or manifest.get("treat_recovered_as_observation") is not True
        or manifest.get("result_leakage") is not False
    ):
        raise RecoverySafetyError("Recovery manifest lacks verified no-result-leakage attestations")
    csv_path = root / str(manifest.get("merged_live_csv") or "")
    if not csv_path.is_file() or folder not in csv_path.resolve().parents:
        raise RecoverySafetyError("Verified recovery CSV path invalid")
    expected_ids = set(str(x) for x in (manifest.get("recovered_races") or []))
    if not expected_ids:
        return {}
    grouped = defaultdict(list)
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            race_id = str(row.get("race_id") or "")
            digits = "".join(x for x in race_id if x.isdigit())
            if len(digits) != 12 or not digits.startswith(date):
                continue
            if digits not in expected_ids:
                continue
            rank = int(row.get("rank") or 0)
            boat = int(row.get("boat") or 0)
            score = safe_float(row.get("score"))
            morning = safe_float(row.get("morning_score_reference"))
            if rank not in range(1, 7) or boat not in range(1, 7):
                raise RecoverySafetyError(f"Invalid rank/boat in recovery: {race_id}")
            if score is None or morning is None:
                raise RecoverySafetyError(f"Missing saved live/morning scores: {race_id}")
            grouped[race_id].append({
                "rank": rank,
                "boat": boat,
                "racer_name": str(row.get("racer_name") or ""),
                "score": score,
                "morning_score_reference": morning,
                "grade": str(row.get("grade") or ""),
                "registration_no": str(row.get("registration_no") or ""),
                "motor_no": row.get("motor_no"),
                "boat_no": row.get("boat_no"),
                "exhibition_course": row.get("exhibition_course"),
                "exhibition_time": safe_float(row.get("exhibition_time")),
                "exhibition_st": safe_float(row.get("exhibition_st")),
                "exhibition_f": str(row.get("exhibition_f")).strip().lower() == "true",
            })
    # A race can legitimately have fewer than six ACTIVE boats. Verify each
    # omitted number is explicitly marked is_miss in the saved official
    # beforeinfo entries; never turn an unobserved boat into an assumed scratch.
    official_entries = folder / f"official_retry_beforeinfo_entries_{date}.csv"
    verified_scratches = defaultdict(set)
    if official_entries.is_file():
        with official_entries.open(encoding="utf-8-sig", newline="") as stream:
            for item in csv.DictReader(stream):
                code = str(item.get("race_id") or "")
                if str(item.get("is_miss") or "").lower() == "true":
                    number = int(item.get("boat") or 0)
                    if number in range(1, 7):
                        verified_scratches[code].add(number)
    result = {}
    for race_id, boats in grouped.items():
        n = len(boats)
        active = {x["boat"] for x in boats}
        missing = set(range(1,7)) - active
        if (
            n < 3 or n > 6
            or {x["rank"] for x in boats} != set(range(1, n + 1))
            or len(active) != n
            or (missing and missing != verified_scratches.get(race_id, set()))
        ):
            raise RecoverySafetyError(f"Unverified missing/duplicate boat scores: {race_id}")
        boats.sort(key=lambda x: x["rank"])
        result[race_id] = {
            "race_id": race_id,
            "boats": boats,
            "prediction_stage": "live_recovered_observation",
            "prediction_quality": {
                "status": "recovered_observation",
                "provenance": "post_result_official_beforeinfo",
                "source": str(csv_path.relative_to(root)),
                "result_leakage": False,
                "prediction_generated_after_deadline": True,
                "retrospective_simulation_only": True,
                "recovery_needed": False,
                "mark": "↻",
                "verified_scratched_boats": sorted(missing),
            },
        }
    expected_missed = expected_ids - {
        "".join(x for x in race_id if x.isdigit()) for race_id in result
    }
    if expected_missed:
        raise RecoverySafetyError(f"Manifest lists missing recovered races: {sorted(expected_missed)}")
    return result


def join_verified_recovery(existing_live: dict, date: str, root: Path = ROOT) -> tuple[dict, list[str]]:
    """Never overwrite genuine pre-deadline live data with retrospective scores."""
    joined = dict(existing_live)
    patched = []
    for race_id, recovered in load_verified_recovered_live(date, root).items():
        old = joined.get(race_id)
        quality = (old or {}).get("prediction_quality") or {}
        if old and quality.get("status") not in {"fallback", "recovered_observation"}:
            continue
        joined[race_id] = recovered
        patched.append(race_id)
    return joined, patched
