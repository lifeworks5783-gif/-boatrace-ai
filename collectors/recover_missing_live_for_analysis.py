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
    if not production_live.is_file():
        raise RuntimeError(f"production live prediction missing: {production_live}")
    if not program.is_file():
        raise RuntimeError(f"program races missing: {program}")

    original_rows = read_csv(production_live)
    expected_rows = read_csv(program)
    expected = race_ids(expected_rows)
    original = race_ids(original_rows)
    missing_before = sorted(expected - original)

    out_dir = Path("evaluations") / y / m / day / "recovery"
    out_dir.mkdir(parents=True, exist_ok=True)
    recovered_csv = out_dir / f"recovered_live_predictions_{d}.csv"
    merged_csv = out_dir / f"merged_live_predictions_{d}.csv"
    manifest_path = out_dir / f"live_recovery_manifest_{d}.json"

    # すでに復旧済みなら再取得せず再利用する。
    if recovered_csv.is_file():
        recovered_rows = read_csv(recovered_csv)
    elif missing_before:
        copy_base_if_needed(d)

        # 結果・払戻はこの復旧入力には使わない。
        # 欠損していたレースだけを BOAT RACE公式 beforeinfo から再取得する。
        # 全144Rの再アクセスを避け、既知の収集不具合で欠けた対象だけを復旧する。
        import today_beforeinfo as tbi

        missing_set = set(missing_before)
        target_bases = [
            row for row in expected_rows
            if normalize_race_id(row.get("race_id")) in missing_set
        ]
        race_rows = []
        entry_rows = []
        retry_errors = []
        for base in target_bases:
            result = tbi.fetch_one(base, d)
            if result.get("parsed") is None:
                retry_errors.append({
                    "race_id": normalize_race_id(base.get("race_id")),
                    "error": result.get("error"),
                })
                continue
            race_row, entries = result["parsed"]
            race_rows.append(race_row)
            entry_rows.extend(entries)

        if retry_errors:
            print("official beforeinfo retry errors:", json.dumps(retry_errors, ensure_ascii=False))

        tbi.write_csv(
            Path("data") / f"beforeinfo_races_{d}.csv",
            race_rows,
            tbi.RACE_FIELDS,
        )
        tbi.write_csv(
            Path("data") / f"beforeinfo_entries_{d}.csv",
            entry_rows,
            tbi.ENTRY_FIELDS,
        )
        validation = {
            "date": d,
            "mode": "analysis_recovery",
            "requested_races": len(target_bases),
            "ready_races": len(race_rows),
            "entry_rows": len(entry_rows),
            "errors": retry_errors,
            "provenance": "post_result_retry_due_known_live_collection_bug",
        }
        (Path("data") / f"beforeinfo_validation_{d}.json").write_text(
            json.dumps(validation, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        for name in (
            f"beforeinfo_races_{d}.csv",
            f"beforeinfo_entries_{d}.csv",
            f"beforeinfo_validation_{d}.json",
        ):
            src = Path("data") / name
            if src.is_file():
                shutil.copy2(src, out_dir / f"official_retry_{name}")

        # 過去結果特徴量は必ず対象日より前だけで作る。
        run("collectors/build_prediction_input.py", "--date", d, "--stage", "live")
        run("collectors/build_history_features.py", "--as-of", d)
        run("collectors/enrich_prediction_input.py", "--date", d, "--stage", "live")
        run(
            "collectors/build_live_prediction.py",
            "--date", d,
            "--historical-backfill",
            "--output-dir", "data",
        )

        rebuilt = Path("data") / f"live_predictions_final_{d}.csv"
        if not rebuilt.is_file():
            raise RuntimeError(f"reconstructed live CSV missing: {rebuilt}")
        rebuilt_rows = read_csv(rebuilt)
        recovered_rows = [
            row for row in rebuilt_rows
            if normalize_race_id(row.get("race_id")) in set(missing_before)
        ]
        fields = list(rebuilt_rows[0].keys()) if rebuilt_rows else []
        if fields:
            write_csv(recovered_csv, recovered_rows, fields)
    else:
        recovered_rows = []

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
    still_missing = sorted(expected - merged_ids)
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
        "production_live_races_before": len(original),
        "missing_before": missing_before,
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

    if still_missing:
        raise RuntimeError(
            "AI分析用の直前予測復旧が未完了: " + ",".join(still_missing)
        )


if __name__ == "__main__":
    main()
