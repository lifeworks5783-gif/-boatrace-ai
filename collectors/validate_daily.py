from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


JST = timezone(timedelta(hours=9))

DATA_DIR = Path("data")

VENUES_REQUIRED = {
    "date",
    "venue_code",
    "venue_name",
}

RESULTS_REQUIRED = {
    "date",
    "venue_code",
    "venue_name",
    "race",
    "race_id",
    "trifecta",
    "trifecta_pay",
    "exacta",
    "exacta_pay",
}

BOAT_RESULTS_REQUIRED = {
    "date",
    "venue_code",
    "venue_name",
    "race",
    "race_id",
    "boat",
    "course",
    "registration_no",
    "racer_name",
    "finish",
    "st",
    "race_time",
}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise FileNotFoundError(f"ファイルがありません: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = []

        for row in reader:
            rows.append({
                str(k): "" if v is None else str(v).strip()
                for k, v in row.items()
            })

    return fieldnames, rows


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()


def normalize_race_id(value: str) -> str:
    value = value.strip()

    match = re.fullmatch(
        r"(\d{8})[-_](\d{1,2})[-_](\d{1,2})",
        value,
    )

    if not match:
        return value

    date, venue, race = match.groups()

    return f"{date}_{int(venue):02d}_{int(race):02d}"


def parse_combo(value: str, expected_count: int) -> list[str] | None:
    value = value.strip()

    if not value:
        return None

    nums = re.findall(r"[1-6]", value)

    if len(nums) != expected_count:
        return None

    return nums


def parse_int(value: str) -> int | None:
    value = value.strip().replace(",", "")

    if value == "":
        return None

    if not re.fullmatch(r"-?\d+", value):
        return None

    return int(value)


def is_valid_registration_no(value: str) -> bool:
    return bool(re.fullmatch(r"\d{4}", value.strip()))


def is_valid_boat(value: str) -> bool:
    return value.strip() in {"1", "2", "3", "4", "5", "6"}


def is_valid_course(value: str) -> bool:
    value = value.strip()

    if value == "":
        return True

    return value in {"1", "2", "3", "4", "5", "6"}


def is_valid_st(value: str) -> bool:
    value = value.strip()

    if value == "":
        return True

    # 通常ST
    if re.fullmatch(r"\.\d{2}", value):
        return True

    # F.01 / F.02 等
    if re.fullmatch(r"[FＦ]\.\d{2}", value):
        return True

    # L.01 等の表記が将来出ても元表記保持
    if re.fullmatch(r"[LＬ]\.\d{2}", value):
        return True

    return False


def resolve_target_date(arg_date: str | None) -> str:
    if arg_date:
        if not re.fullmatch(r"\d{8}", arg_date):
            raise ValueError(
                "--date は YYYYMMDD 形式で指定してください"
            )
        return arg_date

    # 毎日4:30 JST実行を前提に前日を対象
    now_jst = datetime.now(JST)
    target = now_jst.date() - timedelta(days=1)

    return target.strftime("%Y%m%d")


def add_error(errors: list[str], message: str) -> None:
    errors.append(message)


def add_warning(warnings: list[str], message: str) -> None:
    warnings.append(message)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="BOAT RACE日次CSV品質検証"
    )

    parser.add_argument(
        "--date",
        help="対象日 YYYYMMDD。省略時はJST前日",
    )

    args = parser.parse_args()

    try:
        target_date = resolve_target_date(args.date)
    except ValueError as e:
        print(f"[ERROR] {e}")
        return 1

    venues_path = DATA_DIR / f"venues_{target_date}.csv"
    results_path = DATA_DIR / f"results_{target_date}_all.csv"
    boats_path = DATA_DIR / f"boat_results_{target_date}_all.csv"

    validation_path = DATA_DIR / f"validation_{target_date}.json"
    manifest_path = DATA_DIR / f"manifest_{target_date}.json"

    errors: list[str] = []
    warnings: list[str] = []

    try:
        venues_fields, venues = read_csv(venues_path)
        results_fields, results = read_csv(results_path)
        boats_fields, boats = read_csv(boats_path)

    except Exception as e:
        print(f"[ERROR] CSV読込失敗: {e}")
        return 1

    # --------------------------------------------------
    # 必須列
    # --------------------------------------------------

    for name, actual, required in [
        ("venues", set(venues_fields), VENUES_REQUIRED),
        ("results", set(results_fields), RESULTS_REQUIRED),
        (
            "boat_results",
            set(boats_fields),
            BOAT_RESULTS_REQUIRED,
        ),
    ]:
        missing = sorted(required - actual)

        if missing:
            add_error(
                errors,
                f"{name}: 必須列不足 {missing}",
            )

    # --------------------------------------------------
    # 対象日
    # --------------------------------------------------

    for name, rows in [
        ("venues", venues),
        ("results", results),
        ("boat_results", boats),
    ]:
        bad_dates = sorted({
            row.get("date", "")
            for row in rows
            if row.get("date", "") != target_date
        })

        if bad_dates:
            add_error(
                errors,
                f"{name}: 対象日不一致 {bad_dates}",
            )

    # --------------------------------------------------
    # race_id正規化
    # --------------------------------------------------

    for row in results:
        row["_race_id_norm"] = normalize_race_id(
            row.get("race_id", "")
        )

    for row in boats:
        row["_race_id_norm"] = normalize_race_id(
            row.get("race_id", "")
        )

    # --------------------------------------------------
    # results race_id重複
    # --------------------------------------------------

    result_ids = [
        row["_race_id_norm"]
        for row in results
    ]

    result_counter = Counter(result_ids)

    result_duplicates = sorted([
        race_id
        for race_id, count in result_counter.items()
        if count > 1
    ])

    if result_duplicates:
        add_error(
            errors,
            f"results race_id重複: "
            f"{len(result_duplicates)}件",
        )

    # --------------------------------------------------
    # boat_results race_id + 艇番重複
    # --------------------------------------------------

    boat_keys = [
        (
            row["_race_id_norm"],
            row.get("boat", ""),
        )
        for row in boats
    ]

    boat_counter = Counter(boat_keys)

    boat_duplicates = sorted([
        key
        for key, count in boat_counter.items()
        if count > 1
    ])

    if boat_duplicates:
        add_error(
            errors,
            f"boat_results race_id+艇番重複: "
            f"{len(boat_duplicates)}件",
        )

    # --------------------------------------------------
    # results / boat_results race_id集合一致
    # --------------------------------------------------

    results_id_set = set(result_ids)

    boats_id_set = {
        row["_race_id_norm"]
        for row in boats
    }

    only_results = sorted(
        results_id_set - boats_id_set
    )

    only_boats = sorted(
        boats_id_set - results_id_set
    )

    if only_results:
        add_error(
            errors,
            f"resultsだけに存在するrace_id: "
            f"{len(only_results)}件",
        )

    if only_boats:
        add_error(
            errors,
            f"boat_resultsだけに存在するrace_id: "
            f"{len(only_boats)}件",
        )

    # --------------------------------------------------
    # 各レース6艇
    # --------------------------------------------------

    boats_by_race: dict[
        str,
        list[dict[str, str]]
    ] = defaultdict(list)

    for row in boats:
        boats_by_race[
            row["_race_id_norm"]
        ].append(row)

    bad_boat_counts = {}

    for race_id, rows in boats_by_race.items():
        if len(rows) != 6:
            bad_boat_counts[race_id] = len(rows)

    if bad_boat_counts:
        add_error(
            errors,
            f"6艇ではないレース: "
            f"{len(bad_boat_counts)}件 "
            f"{bad_boat_counts}",
        )

    # --------------------------------------------------
    # 艇番
    # --------------------------------------------------

    invalid_boats = []

    for row in boats:
        if not is_valid_boat(
            row.get("boat", "")
        ):
            invalid_boats.append(
                (
                    row["_race_id_norm"],
                    row.get("boat", ""),
                )
            )

    if invalid_boats:
        add_error(
            errors,
            f"艇番異常: {len(invalid_boats)}件",
        )

    # --------------------------------------------------
    # 実コース
    # --------------------------------------------------

    invalid_courses = []

    for row in boats:
        if not is_valid_course(
            row.get("course", "")
        ):
            invalid_courses.append(
                (
                    row["_race_id_norm"],
                    row.get("boat", ""),
                    row.get("course", ""),
                )
            )

    if invalid_courses:
        add_error(
            errors,
            f"実コース異常: "
            f"{len(invalid_courses)}件",
        )

    # --------------------------------------------------
    # 登録番号
    # --------------------------------------------------

    invalid_registration = []

    for row in boats:
        value = row.get(
            "registration_no",
            "",
        )

        if not is_valid_registration_no(value):
            invalid_registration.append(
                (
                    row["_race_id_norm"],
                    row.get("boat", ""),
                    value,
                )
            )

    if invalid_registration:
        add_error(
            errors,
            f"登録番号異常: "
            f"{len(invalid_registration)}件",
        )

    # --------------------------------------------------
    # ST表記
    # --------------------------------------------------

    invalid_st = []

    for row in boats:
        value = row.get("st", "")

        if not is_valid_st(value):
            invalid_st.append(
                (
                    row["_race_id_norm"],
                    row.get("boat", ""),
                    value,
                )
            )

    if invalid_st:
        add_error(
            errors,
            f"ST表記異常: {len(invalid_st)}件 "
            f"{invalid_st[:10]}",
        )

    # --------------------------------------------------
    # 払戻
    # --------------------------------------------------

    invalid_payouts = []

    for row in results:
        for column in [
            "trifecta_pay",
            "exacta_pay",
        ]:
            value = row.get(column, "")

            if value == "":
                continue

            parsed = parse_int(value)

            if parsed is None or parsed < 0:
                invalid_payouts.append(
                    (
                        row["_race_id_norm"],
                        column,
                        value,
                    )
                )

    if invalid_payouts:
        add_error(
            errors,
            f"払戻金異常: "
            f"{len(invalid_payouts)}件",
        )

    # --------------------------------------------------
    # finish から着順を取得
    # --------------------------------------------------

    finish_maps = {}

    for race_id, rows in boats_by_race.items():
        finish_map = {}

        for row in rows:
            finish = row.get(
                "finish",
                "",
            ).strip()

            boat = row.get(
                "boat",
                "",
            ).strip()

            if finish in {"1", "2", "3"}:
                if finish in finish_map:
                    # 同着等の可能性があるため
                    finish_map[finish] = None
                else:
                    finish_map[finish] = boat

        finish_maps[race_id] = finish_map

    # --------------------------------------------------
    # 3連単・2連単整合
    # --------------------------------------------------

    trifecta_mismatches = []
    exacta_mismatches = []
    unresolved_finish_checks = []

    for row in results:
        race_id = row["_race_id_norm"]

        finish_map = finish_maps.get(
            race_id,
            {},
        )

        trifecta = parse_combo(
            row.get("trifecta", ""),
            3,
        )

        exacta = parse_combo(
            row.get("exacta", ""),
            2,
        )

        # 1〜3着が一意に確定している時だけ照合
        if all(
            finish_map.get(str(n))
            for n in (1, 2, 3)
        ):
            actual_top3 = [
                finish_map["1"],
                finish_map["2"],
                finish_map["3"],
            ]

            if (
                trifecta is not None
                and trifecta != actual_top3
            ):
                trifecta_mismatches.append(
                    {
                        "race_id": race_id,
                        "csv": trifecta,
                        "finish": actual_top3,
                    }
                )

            actual_top2 = actual_top3[:2]

            if (
                exacta is not None
                and exacta != actual_top2
            ):
                exacta_mismatches.append(
                    {
                        "race_id": race_id,
                        "csv": exacta,
                        "finish": actual_top2,
                    }
                )

        else:
            # 妨・転・失格・同着・不成立等を
            # 勝手に異常扱いしない
            unresolved_finish_checks.append(
                race_id
            )

    if trifecta_mismatches:
        add_error(
            errors,
            f"3連単と着順の不一致: "
            f"{len(trifecta_mismatches)}件",
        )

    if exacta_mismatches:
        add_error(
            errors,
            f"2連単と着順の不一致: "
            f"{len(exacta_mismatches)}件",
        )

    if unresolved_finish_checks:
        add_warning(
            warnings,
            "特殊着順等により着順照合を"
            f"自動確定できないレース: "
            f"{len(set(unresolved_finish_checks))}件",
        )

    # --------------------------------------------------
    # 特殊値集計
    # --------------------------------------------------

    special_finish_counter = Counter()

    for row in boats:
        finish = row.get(
            "finish",
            "",
        ).strip()

        if finish not in {
            "",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
        }:
            special_finish_counter[
                finish
            ] += 1

    special_st_counter = Counter()

    for row in boats:
        st = row.get(
            "st",
            "",
        ).strip()

        if (
            st
            and not re.fullmatch(
                r"\.\d{2}",
                st,
            )
        ):
            special_st_counter[
                st
            ] += 1

    # --------------------------------------------------
    # venues / results整合
    # --------------------------------------------------

    venue_codes = {
        row.get("venue_code", "")
        for row in venues
    }

    result_venue_codes = {
        row.get("venue_code", "")
        for row in results
    }

    missing_venues_in_results = sorted(
        venue_codes - result_venue_codes
    )

    extra_venues_in_results = sorted(
        result_venue_codes - venue_codes
    )

    if missing_venues_in_results:
        add_error(
            errors,
            "venuesにあるがresultsにない場: "
            f"{missing_venues_in_results}",
        )

    if extra_venues_in_results:
        add_error(
            errors,
            "resultsにあるがvenuesにない場: "
            f"{extra_venues_in_results}",
        )

    # --------------------------------------------------
    # 日次件数整合
    # --------------------------------------------------

    venue_count = len(venues)
    race_count = len(results)
    boat_count = len(boats)

    expected_races = venue_count * 12
    expected_boats = race_count * 6

    if race_count != expected_races:
        add_error(
            errors,
            f"レース数不一致: "
            f"{race_count} "
            f"(期待値 {expected_races})",
        )

    if boat_count != expected_boats:
        add_error(
            errors,
            f"艇数不一致: "
            f"{boat_count} "
            f"(期待値 {expected_boats})",
        )

    # --------------------------------------------------
    # validation JSON
    # --------------------------------------------------

    status = "PASS" if not errors else "FAIL"

    validation = {
        "target_date": target_date,
        "status": status,
        "checked_at_jst": datetime.now(
            JST
        ).isoformat(),
        "counts": {
            "venues": venue_count,
            "races": race_count,
            "boats": boat_count,
            "expected_races":
                expected_races,
            "expected_boats":
                expected_boats,
            "result_race_id_duplicates":
                len(result_duplicates),
            "boat_key_duplicates":
                len(boat_duplicates),
            "results_only_race_ids":
                len(only_results),
            "boat_results_only_race_ids":
                len(only_boats),
            "bad_six_boat_races":
                len(bad_boat_counts),
            "invalid_registration_numbers":
                len(invalid_registration),
            "invalid_payouts":
                len(invalid_payouts),
            "trifecta_mismatches":
                len(trifecta_mismatches),
            "exacta_mismatches":
                len(exacta_mismatches),
        },
        "special_values": {
            "finish": dict(
                special_finish_counter
            ),
            "st": dict(
                special_st_counter
            ),
        },
        "warnings": warnings,
        "errors": errors,
    }

    validation_path.write_text(
        json.dumps(
            validation,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------
    # manifest JSON
    # --------------------------------------------------

    manifest = {
        "target_date": target_date,
        "created_at_jst": datetime.now(
            JST
        ).isoformat(),
        "files": [],
    }

    for path, rows in [
        (venues_path, venues),
        (results_path, results),
        (boats_path, boats),
    ]:
        manifest["files"].append({
            "name": path.name,
            "rows": len(rows),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })

    manifest_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------
    # GitHub Actionsログ表示
    # --------------------------------------------------

    print("")
    print("=" * 60)
    print(
        f"BOAT RACE 日次データ検証 "
        f"{target_date}"
    )
    print("=" * 60)

    print(
        f"開催場数 : {venue_count}"
    )

    print(
        f"レース数 : {race_count}"
    )

    print(
        f"艇データ : {boat_count}"
    )

    print(
        f"race_id重複 : "
        f"{len(result_duplicates)}"
    )

    print(
        f"艇キー重複 : "
        f"{len(boat_duplicates)}"
    )

    print(
        f"3連単不一致 : "
        f"{len(trifecta_mismatches)}"
    )

    print(
        f"2連単不一致 : "
        f"{len(exacta_mismatches)}"
    )

    print(
        f"登録番号異常 : "
        f"{len(invalid_registration)}"
    )

    print(
        f"払戻異常 : "
        f"{len(invalid_payouts)}"
    )

    if special_finish_counter:
        print(
            "特殊着順 : "
            f"{dict(special_finish_counter)}"
        )

    if special_st_counter:
        print(
            "特殊ST : "
            f"{dict(special_st_counter)}"
        )

    print("-" * 60)

    for warning in warnings:
        print(
            f"[WARNING] {warning}"
        )

    for error in errors:
        print(
            f"[ERROR] {error}"
        )

    print("-" * 60)
    print(
        f"VALIDATION RESULT: {status}"
    )
    print("=" * 60)

    print(
        f"保存: {validation_path}"
    )

    print(
        f"保存: {manifest_path}"
    )

    # GitHub Actionsでは非0終了コードを失敗として扱う
    if errors:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())