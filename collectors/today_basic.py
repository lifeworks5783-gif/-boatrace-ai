from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import lhafile


# ============================================================
# 基本設定
# ============================================================

JST = timezone(timedelta(hours=9))
DATA_DIR = Path("data")

VENUES = {
    "01": "桐生",
    "02": "戸田",
    "03": "江戸川",
    "04": "平和島",
    "05": "多摩川",
    "06": "浜名湖",
    "07": "蒲郡",
    "08": "常滑",
    "09": "津",
    "10": "三国",
    "11": "びわこ",
    "12": "住之江",
    "13": "尼崎",
    "14": "鳴門",
    "15": "丸亀",
    "16": "児島",
    "17": "宮島",
    "18": "徳山",
    "19": "下関",
    "20": "若松",
    "21": "芦屋",
    "22": "福岡",
    "23": "唐津",
    "24": "大村",
}


# ============================================================
# 正規化
# ============================================================

ZEN_TO_HAN = str.maketrans(
    "０１２３４５６７８９"
    "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"
    "：－．",
    "0123456789"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    ":-.",
)


def normalize_text(value: str) -> str:
    return value.translate(ZEN_TO_HAN).replace("　", " ")


def decode_cp932(data: bytes) -> str:
    return data.decode("cp932", errors="replace").strip()


def clean_name(value: str) -> str:
    return value.replace("　", "").replace(" ", "").strip()


def safe_int(data: bytes):
    value = normalize_text(decode_cp932(data)).strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def safe_float(data: bytes):
    value = normalize_text(decode_cp932(data)).strip()
    if not value or value in {"-", "--", "---"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


# ============================================================
# URL
# ============================================================

def build_source_url(target_date: str) -> str:
    dt = datetime.strptime(target_date, "%Y%m%d")
    yyyymm = dt.strftime("%Y%m")
    yymmdd = dt.strftime("%y%m%d")

    return (
        f"https://www1.mbrace.or.jp/"
        f"od2/B/{yyyymm}/b{yymmdd}.lzh"
    )


# ============================================================
# ダウンロード
# ============================================================

def download_file(url: str, retries: int = 3) -> bytes:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(compatible; boatrace-ai-data-collector/1.0)"
        )
    }

    last_error = None

    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(
                url,
                headers=headers,
            )

            with urllib.request.urlopen(
                request,
                timeout=60,
            ) as response:
                data = response.read()

            if not data:
                raise RuntimeError("ダウンロードファイルが空です")

            return data

        except urllib.error.HTTPError as exc:
            last_error = exc

            if exc.code == 404:
                raise RuntimeError(
                    f"番組表が見つかりません: {url}"
                ) from exc

        except Exception as exc:
            last_error = exc

        if attempt < retries:
            time.sleep(3 * attempt)

    raise RuntimeError(
        f"番組表ダウンロード失敗: {last_error}"
    )


# ============================================================
# LZH解凍
# ============================================================

def extract_lzh(archive_bytes: bytes) -> bytes:
    try:
        archive = lhafile.LhaFile(
            io.BytesIO(archive_bytes)
        )

        names = archive.namelist()

        if not names:
            raise RuntimeError(
                "LZH内にファイルがありません"
            )

        extracted = []

        for name in sorted(names):
            data = archive.read(name)

            if data:
                extracted.append(data)

        payload = b"".join(extracted)

        if not payload:
            raise RuntimeError(
                "LZH解凍後のデータが空です"
            )

        return payload

    except Exception as exc:
        raise RuntimeError(
            f"LZH解凍失敗: {exc}"
        ) from exc


# ============================================================
# 番組表パーサー
# ============================================================

STADIUM_BEGIN = re.compile(
    rb"^(\d{2})BBGN\s*$"
)

STADIUM_END = re.compile(
    rb"^(\d{2})BEND\s*$"
)

ENTRY_ROW = re.compile(
    rb"^[1-6] ?\d{4}"
)

RACE_HEADER = re.compile(
    r"^\s*"
    r"(?P<race>\d{1,2})R"
    r"\s*"
    r"(?P<title>.*?)"
    r"\s*H(?P<distance>\d{3,4})m"
    r"\s*電話投票締切予定"
    r"\s*(?P<hour>\d{1,2}):(?P<minute>\d{2})"
)

SERIES_DAY = re.compile(
    r"第\s*(\d+)\s*日"
)


def parse_entry_line(line: bytes) -> dict:
    # 固定長データのため、文字ではなく
    # CP932のバイト位置で切り出す
    return {
        "boat": safe_int(line[0:1]),
        "registration_no": safe_int(line[2:6]),
        "racer_name": clean_name(
            decode_cp932(line[6:14])
        ),
        "age": safe_int(line[14:16]),
        "branch": decode_cp932(line[16:20]).replace(
            "　", ""
        ),
        "weight_kg": safe_float(line[20:22]),
        "grade": decode_cp932(line[22:24]),
        "national_win_rate": safe_float(line[24:29]),
        "national_top2_rate": safe_float(line[29:35]),
        "local_win_rate": safe_float(line[35:40]),
        "local_top2_rate": safe_float(line[40:46]),
        "motor_no": safe_int(line[46:49]),
        "motor_top2_rate": safe_float(line[49:55]),
        "boat_no": safe_int(line[55:58]),
        "boat_top2_rate": safe_float(line[58:64]),
        "series_results_raw": decode_cp932(line[64:76]),
        "early_race_raw": decode_cp932(line[76:79]),
    }


def parse_program(
    payload: bytes,
    target_date: str,
    source_url: str,
    collected_at: str,
):
    races = []
    entries = []

    current_venue = None
    current_race = None
    current_series_day = None

    for raw_line in payload.splitlines():
        begin = STADIUM_BEGIN.match(raw_line)

        if begin:
            current_venue = begin.group(1).decode("ascii")
            current_race = None
            current_series_day = None
            continue

        if STADIUM_END.match(raw_line):
            current_venue = None
            current_race = None
            current_series_day = None
            continue

        if current_venue is None:
            continue

        decoded = decode_cp932(raw_line)
        normalized = normalize_text(decoded)

        day_match = SERIES_DAY.search(normalized)

        if day_match:
            try:
                current_series_day = int(
                    day_match.group(1)
                )
            except ValueError:
                pass

        header_match = RACE_HEADER.match(normalized)

        if header_match:
            race_no = int(
                header_match.group("race")
            )

            race_id = (
                f"{target_date}-"
                f"{current_venue}-"
                f"{race_no:02d}"
            )

            title = (
                header_match.group("title")
                .replace("進入固定", "")
                .strip()
            )

            deadline = (
                f"{int(header_match.group('hour')):02d}:"
                f"{int(header_match.group('minute')):02d}"
            )

            current_race = {
                "date": target_date,
                "venue_code": current_venue,
                "venue_name": VENUES.get(
                    current_venue,
                    "",
                ),
                "race": race_no,
                "race_id": race_id,
                "race_name": title,
                "distance_m": int(
                    header_match.group("distance")
                ),
                "deadline": deadline,
                "fixed_course": (
                    "進入固定" in normalized
                ),
                "series_day": current_series_day,
                "source_url": source_url,
                "collected_at": collected_at,
            }

            races.append(current_race)
            continue

        if not ENTRY_ROW.match(raw_line):
            continue

        if len(raw_line) < 64:
            continue

        if current_race is None:
            continue

        parsed = parse_entry_line(raw_line)

        row = {
            "date": target_date,
            "venue_code": current_venue,
            "venue_name": VENUES.get(
                current_venue,
                "",
            ),
            "race": current_race["race"],
            "race_id": current_race["race_id"],
            **parsed,
            "source_url": source_url,
            "collected_at": collected_at,
        }

        entries.append(row)

    return races, entries


# ============================================================
# CSV出力
# ============================================================

def write_csv(
    path: Path,
    rows: list[dict],
    fieldnames: list[str],
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(row)


# ============================================================
# 品質検証
# ============================================================

def validate_data(
    target_date: str,
    races: list[dict],
    entries: list[dict],
):
    errors = []
    warnings = []

    race_ids = [
        row["race_id"]
        for row in races
    ]

    if not races:
        errors.append(
            "レースデータが0件です"
        )

    if not entries:
        errors.append(
            "出走艇データが0件です"
        )

    duplicate_race_ids = (
        len(race_ids)
        - len(set(race_ids))
    )

    if duplicate_race_ids:
        errors.append(
            f"race_id重複: {duplicate_race_ids}件"
        )

    entry_keys = [
        (
            row["race_id"],
            row["boat"],
        )
        for row in entries
    ]

    duplicate_entry_keys = (
        len(entry_keys)
        - len(set(entry_keys))
    )

    if duplicate_entry_keys:
        errors.append(
            "race_id×boat重複: "
            f"{duplicate_entry_keys}件"
        )

    race_counts = {}

    for row in entries:
        race_id = row["race_id"]

        race_counts[race_id] = (
            race_counts.get(
                race_id,
                0,
            )
            + 1
        )

    bad_race_counts = {
        race_id: count
        for race_id, count in race_counts.items()
        if count != 6
    }

    if bad_race_counts:
        errors.append(
            "6艇揃っていないレース: "
            f"{len(bad_race_counts)}件"
        )

    race_id_set = set(race_ids)
    entry_race_id_set = set(race_counts.keys())

    missing_entries = (
        race_id_set
        - entry_race_id_set
    )

    extra_entries = (
        entry_race_id_set
        - race_id_set
    )

    if missing_entries:
        errors.append(
            "出走艇が存在しないrace_id: "
            f"{len(missing_entries)}件"
        )

    if extra_entries:
        errors.append(
            "レース基本に存在しない出走艇race_id: "
            f"{len(extra_entries)}件"
        )

    invalid_boats = [
        row
        for row in entries
        if row["boat"]
        not in {1, 2, 3, 4, 5, 6}
    ]

    if invalid_boats:
        errors.append(
            "艇番異常: "
            f"{len(invalid_boats)}件"
        )

    invalid_registration = [
        row
        for row in entries
        if (
            row["registration_no"] is None
            or len(
                str(row["registration_no"])
            )
            != 4
        )
    ]

    if invalid_registration:
        errors.append(
            "登録番号異常: "
            f"{len(invalid_registration)}件"
        )

    unknown_venues = sorted(
        {
            row["venue_code"]
            for row in races
            if row["venue_code"]
            not in VENUES
        }
    )

    if unknown_venues:
        errors.append(
            "未知の場コード: "
            + ",".join(unknown_venues)
        )

    venue_codes = sorted(
        {
            row["venue_code"]
            for row in races
        }
    )

    missing_optional = {
        "national_win_rate": 0,
        "national_top2_rate": 0,
        "local_win_rate": 0,
        "local_top2_rate": 0,
        "motor_no": 0,
        "motor_top2_rate": 0,
        "boat_no": 0,
        "boat_top2_rate": 0,
    }

    for row in entries:
        for key in missing_optional:
            if row.get(key) in {
                None,
                "",
            }:
                missing_optional[key] += 1

    for key, count in missing_optional.items():
        if count:
            warnings.append(
                f"{key} 欠損: {count}件"
            )

    expected_entries = (
        len(races) * 6
    )

    if len(entries) != expected_entries:
        errors.append(
            "レース数×6と出走艇数が不一致: "
            f"{expected_entries} expected / "
            f"{len(entries)} actual"
        )

    return {
        "status": (
            "PASS"
            if not errors
            else "FAIL"
        ),
        "target_date": target_date,
        "venue_count": len(venue_codes),
        "venue_codes": venue_codes,
        "race_count": len(races),
        "entry_count": len(entries),
        "duplicate_race_ids": duplicate_race_ids,
        "duplicate_entry_keys": duplicate_entry_keys,
        "bad_race_counts": bad_race_counts,
        "errors": errors,
        "warnings": warnings,
    }


# ============================================================
# ハッシュ
# ============================================================

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


# ============================================================
# メイン
# ============================================================

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="対象日 YYYYMMDD",
    )

    args = parser.parse_args()

    if args.date:
        target_date = args.date
    else:
        target_date = datetime.now(
            JST
        ).strftime("%Y%m%d")

    try:
        datetime.strptime(
            target_date,
            "%Y%m%d",
        )
    except ValueError:
        print(
            "日付形式が不正です。YYYYMMDDで指定してください。",
            file=sys.stderr,
        )
        return 1

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    collected_at = datetime.now(
        JST
    ).isoformat()

    source_url = build_source_url(
        target_date
    )

    print("========================================")
    print("当日全国番組表収集")
    print(f"対象日: {target_date}")
    print(f"取得元: {source_url}")
    print("========================================")

    try:
        archive_bytes = download_file(
            source_url
        )

        source_sha256 = hashlib.sha256(
            archive_bytes
        ).hexdigest()

        payload = extract_lzh(
            archive_bytes
        )

        races, entries = parse_program(
            payload=payload,
            target_date=target_date,
            source_url=source_url,
            collected_at=collected_at,
        )

    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 1

    race_path = (
        DATA_DIR
        / f"program_races_{target_date}.csv"
    )

    entry_path = (
        DATA_DIR
        / f"program_entries_{target_date}.csv"
    )

    validation_path = (
        DATA_DIR
        / f"program_validation_{target_date}.json"
    )

    manifest_path = (
        DATA_DIR
        / f"program_manifest_{target_date}.json"
    )

    race_fields = [
        "date",
        "venue_code",
        "venue_name",
        "race",
        "race_id",
        "race_name",
        "distance_m",
        "deadline",
        "fixed_course",
        "series_day",
        "source_url",
        "collected_at",
    ]

    entry_fields = [
        "date",
        "venue_code",
        "venue_name",
        "race",
        "race_id",
        "boat",
        "registration_no",
        "racer_name",
        "age",
        "branch",
        "weight_kg",
        "grade",
        "national_win_rate",
        "national_top2_rate",
        "local_win_rate",
        "local_top2_rate",
        "motor_no",
        "motor_top2_rate",
        "boat_no",
        "boat_top2_rate",
        "series_results_raw",
        "early_race_raw",
        "source_url",
        "collected_at",
    ]

    write_csv(
        race_path,
        races,
        race_fields,
    )

    write_csv(
        entry_path,
        entries,
        entry_fields,
    )

    validation = validate_data(
        target_date,
        races,
        entries,
    )

    validation["source_url"] = source_url
    validation["source_sha256"] = source_sha256
    validation["collected_at"] = collected_at

    validation_path.write_text(
        json.dumps(
            validation,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    manifest = {
        "target_date": target_date,
        "created_at": collected_at,
        "source": {
            "url": source_url,
            "sha256": source_sha256,
        },
        "files": [
            {
                "name": race_path.name,
                "rows": len(races),
                "bytes": race_path.stat().st_size,
                "sha256": sha256_file(
                    race_path
                ),
            },
            {
                "name": entry_path.name,
                "rows": len(entries),
                "bytes": entry_path.stat().st_size,
                "sha256": sha256_file(
                    entry_path
                ),
            },
            {
                "name": validation_path.name,
                "bytes": validation_path.stat().st_size,
                "sha256": sha256_file(
                    validation_path
                ),
            },
        ],
    }

    manifest_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("")
    print("========================================")
    print("収集結果")
    print(
        f"開催場数: {validation['venue_count']}"
    )
    print(
        f"レース数: {validation['race_count']}"
    )
    print(
        f"出走艇数: {validation['entry_count']}"
    )
    print(
        f"検証結果: {validation['status']}"
    )
    print("========================================")

    if validation["warnings"]:
        print("")
        print("WARNINGS")

        for warning in validation["warnings"]:
            print(f"- {warning}")

    if validation["errors"]:
        print("")
        print("ERRORS")

        for error in validation["errors"]:
            print(f"- {error}")

        return 1

    print("")
    print("当日基本データ収集 PASS")

    return 0


if __name__ == "__main__":
    sys.exit(main())