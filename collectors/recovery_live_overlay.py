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
    snapshot_dir = root / "daily_inputs" / date[:4] / date[4:6] / date[6:8] / "live"
    # The latest 'official retry' contains ONLY the newly targeted races.
    # Earlier official beforeinfo snapshots remain authoritative for an
    # already-finished/scratched race: consult ALL saved capture paths.
    evidence_files = ([official_entries] if official_entries.is_file() else [])
    if snapshot_dir.is_dir():
        evidence_files += list(snapshot_dir.rglob(f"beforeinfo_entries_{date}.csv"))
    verified_scratches = defaultdict(set)
    for evidence in evidence_files:
        with evidence.open(encoding="utf-8-sig", newline="") as stream:
            for item in csv.DictReader(stream):
                code = str(item.get("race_id") or "")
                source = str(item.get("source_url") or "")
                if (
                    str(item.get("is_miss") or "").lower() == "true"
                    and source.startswith("https://www.boatrace.jp/owpc/pc/race/beforeinfo?")
                ):
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


def join_verified_late_saved_live(existing_live: dict, date: str, root: Path = ROOT) -> tuple[dict, list[str]]:
    """Recover *scores* made after deadline from official before-deadline raw snapshots.

    Some valid official exhibition captures were committed before deadline, but
    live prediction generation did not run until the race had finished. These
    scores are usable for retrospective PDCA and normal signal reconstruction,
    NEVER as genuine predictions generated or bets placed before deadline.

    Do not use any results, odds or payouts. Never alter a timely scored race.
    """
    from copy import deepcopy
    from datetime import datetime, timedelta, timezone

    if len(date) != 8 or not date.isdigit():
        raise RecoverySafetyError("Invalid recovery date")
    jst = timezone(timedelta(hours=9))

    def time_value(raw):
        try:
            t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return t if t.tzinfo else t.replace(tzinfo=jst)
        except (ValueError, TypeError):
            return None

    def deadline_value(raw):
        t = time_value(raw)
        if t is not None:
            return t
        try:
            return datetime.strptime(date + " " + str(raw).strip(), "%Y%m%d %H:%M").replace(tzinfo=jst)
        except (ValueError, TypeError):
            return None

    day_root = root / "daily_inputs" / date[:4] / date[4:6] / date[6:8] / "live"
    proofs = {}
    for race_path in sorted(day_root.glob(f"raw/**/beforeinfo_races_{date}.csv")):
        entry_path = race_path.with_name(f"beforeinfo_entries_{date}.csv")
        if not entry_path.is_file():
            continue
        with race_path.open(encoding="utf-8-sig", newline="") as h:
            race_rows = list(csv.DictReader(h))
        with entry_path.open(encoding="utf-8-sig", newline="") as h:
            entries = defaultdict(list)
            for entry in csv.DictReader(h):
                entries[str(entry.get("race_id") or "")].append(entry)

        for meta in race_rows:
            rid = str(meta.get("race_id") or "")
            deadline = deadline_value(meta.get("deadline"))
            collected = time_value(meta.get("collected_at"))
            source = str(meta.get("source_url") or "")
            boats = entries.get(rid, [])
            if (not deadline or not collected or collected >= deadline
                    or not source.startswith("https://www.boatrace.jp/owpc/pc/race/beforeinfo?")
                    or len(boats) != 6):
                continue
            if {str(v.get("boat") or "") for v in boats} != {"1","2","3","4","5","6"}:
                continue
            if any(
                not str(v.get("source_url") or "").startswith("https://www.boatrace.jp/owpc/pc/race/beforeinfo?")
                or not (time_value(v.get("collected_at")) and time_value(v.get("collected_at")) < deadline)
                or not (str(v.get("is_miss") or "").lower() in {"true","1","yes"}
                        or all(str(v.get(k) or "").strip() for k in ("exhibition_course","exhibition_time","exhibition_st_raw")))
                for v in boats
            ):
                continue
            if rid not in proofs or collected < proofs[rid][0]:
                proofs[rid] = (collected, deadline, entry_path, boats)

    joined = dict(existing_live)
    patched = []

    # Rolling live_predictions_final is regenerated by subsequent manual
    # updates, and its generated_at can become later than the actual finish.
    # Reuse an IMMUTABLE originally saved pre-deadline snapshot when one exists.
    # Otherwise a genuine original live prediction would be falsely relabeled
    # as a retrospective replay on every later button press.
    snapshot_root = (
        root / "predictions" / date[:4] / date[4:6] / date[6:8]
        / "live" / "snapshots"
    )
    originals = {}
    for snapshot in sorted(snapshot_root.glob(f"*/live_predictions_current_{date}.json")):
        try:
            payload = json.loads(snapshot.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for record in payload.get("races") or []:
            rid = str(record.get("race_id") or "")
            proof = proofs.get(rid)
            if rid not in existing_live or not proof:
                continue
            stamp = time_value(record.get("generated_at"))
            _, deadline, _, official_boats = proof
            if not stamp or stamp > deadline:
                continue
            quality = record.get("prediction_quality") or {}
            scored = record.get("boats") or []
            if (quality.get("status") in {"fallback", "recovered_observation"}
                    or quality.get("signal_blocked") is True
                    or len(scored) != 6
                    or any(safe_float(v.get("score")) is None for v in scored)):
                continue
            official_by_boat = {int(v["boat"]): v for v in official_boats}
            if {int(v.get("boat") or 0) for v in scored} != set(range(1, 7)):
                continue
            if any(
                str(v.get("registration_no") or "").strip()
                != str(official_by_boat[int(v["boat"])].get("registration_no") or "").strip()
                for v in scored
            ):
                continue
            if rid not in originals or stamp > originals[rid][0]:
                originals[rid] = (stamp, record)

    for rid, race in existing_live.items():
        if rid in originals:
            joined[rid] = deepcopy(originals[rid][1])
            continue
        proof = proofs.get(rid)
        if not proof:
            continue
        _, deadline, entry_path, original_boats = proof
        scored_at = time_value(race.get("generated_at"))
        if scored_at is None or scored_at <= deadline:
            # Genuine original pre-deadline prediction: leave it unchanged.
            continue
        quality = race.get("prediction_quality") or {}
        if quality.get("status") == "recovered_observation":
            continue
        scored_boats = race.get("boats") or []
        if len(scored_boats) != 6 or any(safe_float(v.get("score")) is None for v in scored_boats):
            continue
        official_by_boat = {int(v["boat"]): v for v in original_boats}
        if {int(v.get("boat") or 0) for v in scored_boats} != set(range(1,7)):
            continue
        if any(
            str(v.get("registration_no") or "").strip() != str(official_by_boat[int(v["boat"])].get("registration_no") or "").strip()
            for v in scored_boats
        ):
            continue
        copied = deepcopy(race)
        copied["prediction_stage"] = "live_recovered_observation"
        copied["prediction_quality"] = {
            "status": "recovered_observation",
            "mark": "↻",
            "label": "公式直前情報から事後再計算",
            "provenance": "saved_pre_deadline_official_beforeinfo",
            "source": str(entry_path.relative_to(root)),
            "result_leakage": False,
            "prediction_generated_after_deadline": True,
            "retrospective_simulation_only": True,
            "recovery_needed": False,
            "signal_blocked": False,
            "verified_scratched_boats": [
                int(v["boat"]) for v in original_boats
                if str(v.get("is_miss") or "").lower() in {"true","1","yes"}
            ],
            "original_score_generated_at": race.get("generated_at"),
        }
        joined[rid] = copied
        patched.append(rid)
    return joined, patched
