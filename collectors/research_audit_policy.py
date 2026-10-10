"""Research audit policy for intentionally manual data collection.

A verified official beforeinfo replay is VALID for research scoring even when
the automation ran after deadline. Timestamp provenance is retained; it is
not evidence of a historical placed bet. Actual results never affect scoring.
"""
from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path

from race_prediction_store import audit_race


def load_policy(repo_root: Path = Path(".")) -> dict:
    path = repo_root / "config" / "research_audit_policy.json"
    if not path.is_file():
        raise FileNotFoundError(f"Research audit policy not found: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("mode") != "manual_research" or value.get("automatic_collection_enabled") is not False:
        raise ValueError("Unsupported research audit policy; do not guess collection mode")
    return value


def normalize_race_id(value: object) -> str:
    text = str(value or "").strip()
    m = re.fullmatch(r"(\d{8})[-_](\d{1,2})[-_](\d{1,2})", text)
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else text


def finished_result_ids(date: str, repo_root: Path = Path(".")) -> set[str]:
    src = repo_root / "archive" / date[:4] / date[4:6] / date[6:8] / f"results_{date}_all.csv"
    if not src.is_file():
        return set()
    with src.open("r", encoding="utf-8-sig", newline="") as f:
        return {normalize_race_id(row.get("race_id")) for row in csv.DictReader(f)
                if row.get("race_id")}


def score_integrity(race: dict) -> tuple[bool, str]:
    """Ignore timestamps and backfill provenance; inspect research data itself."""
    quality = race.get("prediction_quality") or {}
    if quality.get("status") == "fallback" or quality.get("signal_blocked") is True:
        return False, "live_score_fallback"
    if str(race.get("prediction_type") or "") != "直前":
        return False, "live_score_not_yet_reconciled"
    boats = race.get("boats") or []
    if len(boats) != 6:
        # Allow officially confirmed scratches only, never assume a missing boat.
        scratched = set(quality.get("verified_scratched_boats") or [])
        active = {int(b.get("boat") or 0) for b in boats}
        if not (len(boats) >= 4 and active | scratched == set(range(1, 7))
                and not active & scratched):
            return False, "unverified_boat_coverage"
    observed = []
    for boat in boats:
        try:
            no = int(boat.get("boat"))
            score = float(boat.get("score"))
        except (TypeError, ValueError):
            return False, "missing_boat_score"
        if no not in range(1, 7) or not math.isfinite(score):
            return False, "invalid_boat_score"
        observed.append(no)
    if len(observed) != len(set(observed)):
        return False, "duplicate_boat"
    for key in ("up_signal", "down_signal"):
        if (race.get(key) or {}).get("available") is not True:
            return False, "signal_not_yet_reconciled"
    signal_audit = audit_race(race)
    if signal_audit["signal_ai_status"] != "ready":
        return False, "missing_or_invalid_signal_picks"
    return True, "valid_official_research_prediction"


def audit_research_predictions(payload: dict, finished: set[str]) -> dict:
    """Count ONLY completed races. Never infer a failure from disabled automation."""
    by_id = {normalize_race_id(r.get("race_id")): r for r in payload.get("races", [])
             if isinstance(r, dict) and r.get("race_id")}
    valid_ids = []
    incomplete = []
    manually_reconstructed = []
    for rid in sorted(finished):
        race = by_id.get(rid)
        if race is None:
            incomplete.append({"race_id": rid, "reason": "no_canonical_race"})
            continue
        ok, reason = score_integrity(race)
        if ok:
            valid_ids.append(rid)
            if bool(race.get("retrospective_score_recovery")) or (
                (race.get("prediction_quality") or {}).get("status") == "recovered_observation"
            ):
                manually_reconstructed.append(rid)
        else:
            incomplete.append({"race_id": rid, "reason": reason})
    pending = len(set(by_id) - finished)
    return {
        "mode": "manual_research",
        "automatic_collection_enabled": False,
        "result_races": len(finished),
        "valid_research_races": len(valid_ids),
        "valid_research_race_ids": valid_ids,
        "manual_official_reconstruction_races": len(manually_reconstructed),
        "manual_official_reconstruction_ids": manually_reconstructed,
        "requires_manual_completion": len(incomplete),
        "research_incomplete": incomplete,
        "not_yet_finished_races_excluded_from_error": pending,
        "research_status": "PASS" if not incomplete else "MANUAL_RECONCILIATION_PENDING",
        "historical_bet_claimed_for_recovered_scores": False,
        "timestamp_is_not_a_research_validity_failure": True,
    }
