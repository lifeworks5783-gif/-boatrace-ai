from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def normalize_race_id(value):
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return digits[:12] if len(digits) >= 12 else ""


def race_ids(rows):
    return {
        normalize_race_id(row.get("race_id"))
        for row in rows
        if normalize_race_id(row.get("race_id"))
    }


def partial_race_ids(rows):
    """Provisional morning-neutral scores must NEVER satisfy official recovery."""
    return {
        normalize_race_id(row.get("race_id")) for row in rows
        if str(row.get("score_fallback") or "").strip().lower() in {"true", "yes", "1"}
        and normalize_race_id(row.get("race_id"))
    }


def run(script: str, *args: str):
    cmd = [sys.executable, "-u", script, *args]
    print("RUN", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def copy_base_if_needed(d: str):
    y, m, day = d[:4], d[4:6], d[6:8]
    base = Path("daily_inputs") / y / m / day / "base"
    data = Path("data")
    data.mkdir(parents=True, exist_ok=True)
    for name in (
        f"program_races_{d}.csv",
        f"program_entries_{d}.csv",
        f"program_entries_fl_{d}.csv",
    ):
        src = base / name
        dst = data / name
        if src.is_file() and not dst.is_file():
            shutil.copy2(src, dst)


def write_csv(path: Path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({key: row.get(key, "") for key in fieldnames})


def merge_official_snapshots(previous, incoming, *, boat_key=False):
    """Keep prior official retry evidence when only NEW races are fetched.

    Race-ID + boat is immutable for one day's original official exhibition;
    a later retry must not erase an earlier verified scratched starter.
    """
    merged = {}
    for row in [*previous, *incoming]:
        rid = normalize_race_id(row.get("race_id"))
        if not rid:
            continue
        number = str(row.get("boat") or "").strip() if boat_key else ""
        if boat_key and number not in {"1", "2", "3", "4", "5", "6"}:
            raise ValueError(f"Invalid official boat in {rid}: {number!r}")
        merged[(rid, number)] = row
    return [merged[key] for key in sorted(merged)]


def main():
    p = argparse.ArgumentParser(
        description="既知の当日収集不具合で欠けた直前予測を、公式beforeinfoだけからAI分析用に復旧"
    )
    p.add_argument("--date", required=True)
    args = p.parse_args()
    d = args.date
    y, m, day = d[:4], d[4:6], d[6:8]

    production_live = (
        Path("predictions") / y / m / day / "live" / f"live_predictions_final_{d}.csv"
    )
    program = Path("daily_inputs") / y / m / day / "base" / f"program_races_{d}.csv"
    if not program.is_file():
        raise RuntimeError(f"program races missing: {program}")

    # The production live CSV may genuinely be absent after an upstream morning
    # outage.  Do not abort recovery just because the file was never created.
    # No synthetic pre-deadline prediction is written; recovered observations
    # remain separately labeled as retrospective in the recovery manifest.
    original_rows = read_csv(production_live) if production_live.is_file() else []
    if not production_live.is_file():
        print(f"WARN: no original saved live prediction; official recovery only: {production_live}", flush=True)
    expected_rows = read_csv(program)
    expected = race_ids(expected_rows)
    original = race_ids(original_rows)
    # Saved neutral scores are NOT verified official live observations.
    # Keep them in the recovery queue until complete original exhibition
    # evidence is obtained; a stored 0-delta placeholder is not success.
    partial_ids = partial_race_ids(original_rows)
    verified_original = original - partial_ids
    # Recover only finished races; future races never count as an inactive signal.
    result_path = Path("archive") / y / m / day / f"results_{d}_all.csv"
    finished = (race_ids(read_csv(result_path)) & expected) if result_path.is_file() else set()
    missing_before = sorted(finished - verified_original)

    out_dir = Path("evaluations") / y / m / day / "recovery"
    out_dir.mkdir(parents=True, exist_ok=True)
    recovered_csv = out_dir / f"recovered_live_predictions_{d}.csv"
    merged_csv = out_dir / f"merged_live_predictions_{d}.csv"
    manifest_path = out_dir / f"live_recovery_manifest_{d}.json"

    # Keep historical recovery across repeated button presses.
    recovered_rows = read_csv(recovered_csv) if recovered_csv.is_file() else []
    pending = sorted(set(missing_before) - race_ids(recovered_rows))
    retry_errors = []

    if pending:
        copy_base_if_needed(d)
        import today_beforeinfo as tbi
        from concurrent.futures import ThreadPoolExecutor

        pending_set = set(pending)
        target_bases = [
            row for row in expected_rows
            if normalize_race_id(row.get("race_id")) in pending_set
        ]

        # Reuse already saved official pre-race data first, never morning fallback.
        live_root = Path("daily_inputs") / y / m / day / "live"
        cached = {}
        if live_root.exists():
            for entries_path in sorted(live_root.glob("**/beforeinfo_entries_*.csv")):
                races_path = entries_path.with_name(f"beforeinfo_races_{d}.csv")
                if not races_path.is_file():
                    continue
                try:
                    grouped = {}
                    for row in read_csv(entries_path):
                        rid = normalize_race_id(row.get("race_id"))
                        if rid in pending_set:
                            grouped.setdefault(rid, []).append(row)
                    race_map = {
                        normalize_race_id(row.get("race_id")): row
                        for row in read_csv(races_path)
                    }
                    for rid, rows in grouped.items():
                        if rid not in race_map or len(rows) != 6:
                            continue
                        if {str(row.get("boat", "")).strip() for row in rows} != {
                            "1", "2", "3", "4", "5", "6"
                        }:
                            continue
                        if all(
                            str(row.get("is_miss", "")).lower() in ("true", "1", "yes")
                            or all(str(row.get(k, "")).strip() for k in (
                                "exhibition_course", "exhibition_time", "exhibition_st_raw"
                            ))
                            for row in rows
                        ):
                            cached[rid] = (race_map[rid], rows)
                except Exception as exc:
                    print(f"WARN: saved official beforeinfo read: {entries_path}: {exc}")

        to_fetch = [
            base for base in target_bases
            if normalize_race_id(base.get("race_id")) not in cached
        ]
        fetched = {}
        if to_fetch:
            with ThreadPoolExecutor(max_workers=4) as pool:
                for result in pool.map(lambda base: tbi.fetch_one(base, d), to_fetch):
                    rid = normalize_race_id(result["base"].get("race_id"))
                    if result.get("parsed") is None:
                        retry_errors.append({"race_id": rid, "error": result.get("error")})
                    else:
                        fetched[rid] = result["parsed"]

        observed = {**cached, **fetched}
        race_rows = []
        entry_rows = []
        for base in target_bases:
            rid = normalize_race_id(base.get("race_id"))
            if rid in observed:
                race_row, entries = observed[rid]
                race_rows.append(race_row)
                entry_rows.extend(entries)

        if retry_errors:
            print("official beforeinfo retry errors:", json.dumps(retry_errors, ensure_ascii=False))
        tbi.write_csv(Path("data") / f"beforeinfo_races_{d}.csv", race_rows, tbi.RACE_FIELDS)
        tbi.write_csv(Path("data") / f"beforeinfo_entries_{d}.csv", entry_rows, tbi.ENTRY_FIELDS)
        validation = {
            "date": d, "mode": "completed_race_recovery",
            "requested_races": len(target_bases),
            "cached_official_races": len(cached),
            "new_official_races": len(fetched),
            "ready_races": len(race_rows),
            "entry_rows": len(entry_rows),
            "errors": retry_errors,
            "provenance": "saved_beforeinfo_or_official_historical_retrieval",
        }
        (Path("data") / f"beforeinfo_validation_{d}.json").write_text(
            json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        for name in (
            f"beforeinfo_races_{d}.csv",
            f"beforeinfo_entries_{d}.csv",
            f"beforeinfo_validation_{d}.json",
        ):
            src = Path("data") / name
            if not src.is_file():
                continue
            dst = out_dir / f"official_retry_{name}"
            if name.startswith("beforeinfo_entries_"):
                merged = merge_official_snapshots(
                    read_csv(dst) if dst.is_file() else [],
                    read_csv(src),
                    boat_key=True,
                )
                write_csv(dst, merged, tbi.ENTRY_FIELDS)
            elif name.startswith("beforeinfo_races_"):
                merged = merge_official_snapshots(
                    read_csv(dst) if dst.is_file() else [],
                    read_csv(src),
                )
                write_csv(dst, merged, tbi.RACE_FIELDS)
            else:
                shutil.copy2(src, dst)

        if race_rows:
            # As-of features only. Results and payouts are never prediction inputs.
            run("collectors/build_prediction_input.py", "--date", d, "--stage", "live")
            run("collectors/build_history_features.py", "--as-of", d)
            run("collectors/enrich_prediction_input.py", "--date", d, "--stage", "live")
            run("collectors/build_live_prediction.py", "--date", d, "--historical-backfill", "--output-dir", "data")

            rebuilt = Path("data") / f"live_predictions_final_{d}.csv"
            if rebuilt.is_file():
                rebuilt_rows = read_csv(rebuilt)
                by_key = {
                    (normalize_race_id(row.get("race_id")), str(row.get("boat") or "")): row
                    for row in recovered_rows
                }
                rebuilt_by_race = {}
                for row in rebuilt_rows:
                    rid = normalize_race_id(row.get("race_id"))
                    rebuilt_by_race.setdefault(rid, []).append(row)
                for rid, rows in rebuilt_by_race.items():
                    if rid not in pending_set:
                        continue
                    # Recovery may NOT certify a new neutral placeholder as
                    # official data. Leave the race pending for a later retry.
                    if any(str(x.get("score_fallback") or "").strip().lower() in {"true", "yes", "1"}
                           for x in rows):
                        retry_errors.append({"race_id": rid, "error": "official beforeinfo still partial; neutral score pending"})
                        continue
                    for row in rows:
                        by_key[(rid, str(row.get("boat") or ""))] = row
                recovered_rows = list(by_key.values())
                if recovered_rows:
                    write_csv(recovered_csv, recovered_rows, list(recovered_rows[0].keys()))

    recovered_ids = race_ids(recovered_rows)
    merged_by_key = {}
    for row in original_rows:
        key = (normalize_race_id(row.get("race_id")), str(row.get("boat") or ""))
        merged_by_key[key] = row
    for row in recovered_rows:
        rid = normalize_race_id(row.get("race_id"))
        if rid in set(missing_before):
            key = (rid, str(row.get("boat") or ""))
            merged_by_key[key] = row

    merged_rows = list(merged_by_key.values())
    merged_rows.sort(
        key=lambda r: (
            normalize_race_id(r.get("race_id")),
            int(float(r.get("rank") or 99)),
            int(float(r.get("boat") or 99)),
        )
    )
    fields = []
    for row in original_rows + recovered_rows:
        for key in row.keys():
            if key not in fields:
                fields.append(key)
    write_csv(merged_csv, merged_rows, fields)

    merged_ids = race_ids(merged_rows)
    still_missing = sorted(finished - (verified_original | recovered_ids))
    recovered_target_ids = sorted(set(missing_before) & recovered_ids)

    manifest = {
        "date": d,
        "status": "complete" if not still_missing else "partial",
        "known_collection_bug": True,
        "treat_recovered_as_observation": True,
        "production_prediction_file_unchanged": True,
        "result_leakage": False,
        "recovery_input": "BOAT RACE official beforeinfo only; results/payouts are not prediction inputs",
        "provenance": "post_result_retry_due_known_live_collection_bug",
        "expected_races": len(expected),
        "finished_races_targeted": len(finished),
        "not_yet_finished_races": len(expected - finished),
        "production_live_races_before": len(original),
        "missing_before": missing_before,
        "neutral_live_rows_pending_recovery": sorted(partial_ids & finished),
        "official_retry_errors": retry_errors,
        "recovered_races": recovered_target_ids,
        "merged_analysis_races": len(merged_ids),
        "still_missing": still_missing,
        "merged_live_csv": str(merged_csv),
        "recovered_live_csv": str(recovered_csv),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))

    # Never collapse an uncollected race into a false "signal inactive".
    if still_missing:
        print("RETRY_NEEDED (excluded from signal denominator):", ",".join(still_missing))


if __name__ == "__main__":
    main()
