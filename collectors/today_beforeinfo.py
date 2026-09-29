from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


JST = timezone(timedelta(hours=9))
DATA_DIR = Path("data")

WIND_DIR = {
    1: "北",
    2: "北北東",
    3: "北東",
    4: "東北東",
    5: "東",
    6: "東南東",
    7: "南東",
    8: "南南東",
    9: "南",
    10: "南南西",
    11: "南西",
    12: "西南西",
    13: "西",
    14: "西北西",
    15: "北西",
    16: "北北西",
}


RACE_FIELDS = [
    "date",
    "venue_code",
    "venue_name",
    "race",
    "race_id",
    "deadline",
    "weather",
    "air_temperature_c",
    "water_temperature_c",
    "wind_speed_mps",
    "wind_direction_code",
    "wind_direction",
    "wave_height_cm",
    "stabilizer",
    "fixed_course",
    "source_url",
    "collected_at",
]

ENTRY_FIELDS = [
    "date",
    "venue_code",
    "venue_name",
    "race",
    "race_id",
    "boat",
    "registration_no",
    "racer_name",
    "weight_kg",
    "exhibition_time",
    "tilt",
    "exhibition_course",
    "exhibition_st_raw",
    "exhibition_st_seconds",
    "exhibition_st_flag",
    "change_parts",
    "is_miss",
    "source_url",
    "collected_at",
]


def clean_text(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", "", value).strip()


def safe_float(value):
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    match = re.search(r"-?\d+(?:\.\d+)?", text)

    if not match:
        return None

    try:
        return float(match.group())
    except ValueError:
        return None


def parse_st(value: str):
    value = clean_text(value)

    if not value:
        return None, ""

    flag = ""

    if value.startswith("F"):
        flag = "F"
        raw = value[1:]
        number = safe_float(raw)

        if number is not None:
            number = -abs(number)

        return number, flag

    if value.startswith("L"):
        flag = "L"
        raw = value[1:]
        number = safe_float(raw)

        if number is not None:
            number = abs(number)

        return number, flag

    if value.startswith("."):
        value = "0" + value

    return safe_float(value), flag


def get_text(node) -> str:
    if node is None:
        return ""
    return node.get_text(" ", strip=True)


def get_base_path(target_date: str) -> Path:
    direct = DATA_DIR / f"program_races_{target_date}.csv"

    if direct.exists():
        return direct

    dt = datetime.strptime(target_date, "%Y%m%d")

    archived = (
        Path("archive")
        / dt.strftime("%Y")
        / dt.strftime("%m")
        / dt.strftime("%d")
        / "pre_race"
        / "base"
        / f"program_races_{target_date}.csv"
    )

    if archived.exists():
        return archived

    raise FileNotFoundError(
        f"当日基本データが見つかりません: {target_date}"
    )


def load_base_races(target_date: str) -> list[dict]:
    path = get_base_path(target_date)

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as f:
        return list(csv.DictReader(f))


def archive_beforeinfo_dir(target_date: str) -> Path:
    dt = datetime.strptime(target_date, "%Y%m%d")

    return (
        Path("archive")
        / dt.strftime("%Y")
        / dt.strftime("%m")
        / dt.strftime("%d")
        / "pre_race"
        / "beforeinfo"
    )


def load_existing_csv(
    data_path: Path,
    archive_path: Path,
) -> list[dict]:

    target = None

    if data_path.exists():
        target = data_path
    elif archive_path.exists():
        target = archive_path

    if target is None:
        return []

    with target.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as f:
        return list(csv.DictReader(f))


def race_datetime(
    target_date: str,
    deadline: str,
) -> datetime:

    return datetime.strptime(
        f"{target_date} {deadline}",
        "%Y%m%d %H:%M",
    ).replace(tzinfo=JST)


def select_races(
    races: list[dict],
    target_date: str,
    mode: str,
    race_id: str | None,
    sample_count: int,
    window_before: int,
    window_after: int,
) -> list[dict]:

    if race_id:
        return [
            row
            for row in races
            if row["race_id"] == race_id
        ]

    if mode == "all":
        return races

    now = datetime.now(JST)

    candidates = []

    for row in races:
        deadline = row.get("deadline", "")

        if not deadline:
            continue

        try:
            race_time = race_datetime(
                target_date,
                deadline,
            )
        except ValueError:
            continue

        minutes = (
            race_time - now
        ).total_seconds() / 60

        row_copy = dict(row)
        row_copy["_minutes"] = minutes

        if mode == "live":
            if (
                -window_before
                <= minutes
                <= window_after
            ):
                candidates.append(row_copy)

        elif mode == "sample":
            if -180 <= minutes <= 90:
                candidates.append(row_copy)

    candidates.sort(
        key=lambda x: abs(x["_minutes"])
    )

    if mode == "sample":
        return candidates[:sample_count]

    return candidates


def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(compatible; boatrace-ai-data-collector/1.0)"
        ),
        "Accept-Language": "ja,en;q=0.8",
    }

    last_error = None

    for attempt in range(1, 4):
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=30,
            )

            response.raise_for_status()

            return response.text

        except Exception as exc:
            last_error = exc

            if attempt < 3:
                time.sleep(attempt * 2)

    raise RuntimeError(
        f"取得失敗: {url} / {last_error}"
    )


def is_no_data(soup: BeautifulSoup) -> bool:
    text = soup.get_text(" ", strip=True)

    return "データがありません" in text


def parse_weather(soup: BeautifulSoup) -> dict:
    root = soup.select_one(".weather1")

    if root is None:
        return {
            "weather": "",
            "air_temperature_c": None,
            "water_temperature_c": None,
            "wind_speed_mps": None,
            "wind_direction_code": None,
            "wind_direction": "",
            "wave_height_cm": None,
        }

    weather_node = root.select_one(
        ".weather1_bodyUnit.is-weather "
        ".weather1_bodyUnitLabelTitle"
    )

    air_node = root.select_one(
        ".weather1_bodyUnit.is-direction "
        ".weather1_bodyUnitLabelData"
    )

    wind_node = root.select_one(
        ".weather1_bodyUnit.is-wind "
        ".weather1_bodyUnitLabelData"
    )

    water_node = root.select_one(
        ".weather1_bodyUnit.is-waterTemperature "
        ".weather1_bodyUnitLabelData"
    )

    wave_node = root.select_one(
        ".weather1_bodyUnit.is-wave "
        ".weather1_bodyUnitLabelData"
    )

    direction_code = None

    direction_node = root.select_one(
        ".weather1_bodyUnit.is-windDirection "
        ".weather1_bodyUnitImage"
    )

    if direction_node:
        classes = " ".join(
            direction_node.get("class", [])
        )

        match = re.search(
            r"is-wind(\d{1,2})",
            classes,
        )

        if match:
            direction_code = int(
                match.group(1)
            )

    return {
        "weather": get_text(weather_node),
        "air_temperature_c": safe_float(
            get_text(air_node)
        ),
        "water_temperature_c": safe_float(
            get_text(water_node)
        ),
        "wind_speed_mps": safe_float(
            get_text(wind_node)
        ),
        "wind_direction_code": direction_code,
        "wind_direction": (
            WIND_DIR.get(
                direction_code,
                "",
            )
            if direction_code
            else ""
        ),
        "wave_height_cm": safe_float(
            get_text(wave_node)
        ),
    }


def parse_flags(soup: BeautifulSoup) -> dict:
    labels = [
        get_text(node)
        for node in soup.select("span.label2")
    ]

    return {
        "stabilizer": (
            "安定板使用" in labels
            or any(
                "安定板" in x
                for x in labels
            )
        ),
        "fixed_course": (
            "進入固定" in labels
            or any(
                "進入固定" in x
                for x in labels
            )
        ),
    }


def parse_exhibition_order(
    soup: BeautifulSoup,
) -> tuple[dict[int, int], dict[int, str]]:

    course_by_boat = {}
    st_by_boat = {}

    blocks = soup.select(
        "div.table1_boatImage1"
    )

    course = 1

    for block in blocks:
        boat_node = block.select_one(
            ".table1_boatImage1Number"
        )

        st_node = block.select_one(
            ".table1_boatImage1Time"
        )

        boat_text = clean_text(
            get_text(boat_node)
        )

        if not boat_text.isdigit():
            continue

        boat = int(boat_text)

        if boat not in range(1, 7):
            continue

        if boat not in course_by_boat:
            course_by_boat[boat] = course
            course += 1

        st_text = clean_text(
            get_text(st_node)
        )

        if st_text:
            st_by_boat[boat] = st_text

    return course_by_boat, st_by_boat


def find_entry_tbodies(
    soup: BeautifulSoup,
):
    tbodies = soup.select(
        "table.is-w748 tbody"
    )

    if len(tbodies) >= 6:
        return tbodies[:6]

    tables = soup.select("div.table1")

    if len(tables) >= 2:
        tbodies = tables[1].select(
            "tbody"
        )

    return tbodies[:6]


def parse_entry_table(
    soup: BeautifulSoup,
):
    course_by_boat, st_by_boat = (
        parse_exhibition_order(soup)
    )

    tbodies = find_entry_tbodies(soup)

    rows = []

    for index, tbody in enumerate(
        tbodies,
        start=1,
    ):
        boat = index

        registration_no = ""
        racer_name = ""

        for link in tbody.select(
            'a[href*="toban="]'
        ):
            href = link.get("href", "")

            match = re.search(
                r"toban=(\d{4})",
                href,
            )

            if match:
                registration_no = (
                    match.group(1)
                )

            name = re.sub(
                r"\s+",
                "",
                get_text(link),
            )

            if name:
                racer_name = name

        first_row = tbody.select_one("tr")

        cells = (
            first_row.select("td")
            if first_row
            else []
        )

        texts = [
            clean_text(
                get_text(cell)
            )
            for cell in cells
        ]

        weight = None
        exhibition_time = None
        tilt = None

        kg_index = None

        for i, text in enumerate(texts):
            if "kg" in text.lower():
                kg_index = i
                break

        if kg_index is not None:
            weight = safe_float(
                texts[kg_index]
            )

            if kg_index + 1 < len(texts):
                exhibition_time = safe_float(
                    texts[kg_index + 1]
                )

            if kg_index + 2 < len(texts):
                tilt = safe_float(
                    texts[kg_index + 2]
                )

        parts = [
            clean_text(get_text(li))
            for li in tbody.select("ul li")
            if clean_text(get_text(li))
        ]

        class_names = tbody.get(
            "class",
            [],
        )

        st_raw = st_by_boat.get(
            boat,
            "",
        )

        st_seconds, st_flag = parse_st(
            st_raw
        )

        rows.append(
            {
                "boat": boat,
                "registration_no": registration_no,
                "racer_name": racer_name,
                "weight_kg": weight,
                "exhibition_time": exhibition_time,
                "tilt": tilt,
                "exhibition_course": (
                    course_by_boat.get(boat)
                ),
                "exhibition_st_raw": st_raw,
                "exhibition_st_seconds": st_seconds,
                "exhibition_st_flag": st_flag,
                "change_parts": ";".join(parts),
                "is_miss": (
                    "is-miss" in class_names
                ),
            }
        )

    return rows


def parse_beforeinfo(
    html: str,
    base: dict,
):
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    if is_no_data(soup):
        return None

    entry_rows = parse_entry_table(
        soup
    )

    if len(entry_rows) != 6:
        return None

    exhibition_count = sum(
        1
        for row in entry_rows
        if row["exhibition_time"]
        is not None
    )

    st_count = sum(
        1
        for row in entry_rows
        if row["exhibition_st_raw"]
    )

    # 直前情報がまだ出揃っていない場合は保存しない。
    # 次回の定期実行で再取得する。
    if (
        exhibition_count < 4
        or st_count < 4
    ):
        return None

    target_date = base["date"]
    venue_code = base["venue_code"]
    race_no = int(base["race"])
    race_id = base["race_id"]

    url = (
        "https://www.boatrace.jp/"
        "owpc/pc/race/beforeinfo"
        f"?hd={target_date}"
        f"&jcd={venue_code}"
        f"&rno={race_no}"
    )

    collected_at = datetime.now(
        JST
    ).isoformat()

    weather = parse_weather(soup)
    flags = parse_flags(soup)

    race_row = {
        "date": target_date,
        "venue_code": venue_code,
        "venue_name": base["venue_name"],
        "race": race_no,
        "race_id": race_id,
        "deadline": base["deadline"],
        **weather,
        **flags,
        "source_url": url,
        "collected_at": collected_at,
    }

    final_entries = []

    for row in entry_rows:
        final_entries.append(
            {
                "date": target_date,
                "venue_code": venue_code,
                "venue_name": base["venue_name"],
                "race": race_no,
                "race_id": race_id,
                **row,
                "source_url": url,
                "collected_at": collected_at,
            }
        )

    return race_row, final_entries


def write_csv(
    path: Path,
    rows: list[dict],
    fields: list[str],
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields,
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    field: row.get(
                        field,
                        "",
                    )
                    for field in fields
                }
            )


def merge_rows(
    old_rows: list[dict],
    new_rows: list[dict],
    key_fields: tuple[str, ...],
):
    merged = {}

    for row in old_rows:
        key = tuple(
            str(row.get(field, ""))
            for field in key_fields
        )

        merged[key] = row

    for row in new_rows:
        key = tuple(
            str(row.get(field, ""))
            for field in key_fields
        )

        merged[key] = row

    result = list(merged.values())

    result.sort(
        key=lambda row: tuple(
            str(row.get(field, ""))
            for field in key_fields
        )
    )

    return result


def validate(
    race_rows: list[dict],
    entry_rows: list[dict],
):
    errors = []

    race_ids = [
        row["race_id"]
        for row in race_rows
    ]

    if len(race_ids) != len(
        set(race_ids)
    ):
        errors.append(
            "beforeinfo race_id重複"
        )

    keys = [
        (
            row["race_id"],
            str(row["boat"]),
        )
        for row in entry_rows
    ]

    if len(keys) != len(set(keys)):
        errors.append(
            "beforeinfo race_id×boat重複"
        )

    count_by_race = {}

    for row in entry_rows:
        race_id = row["race_id"]

        count_by_race[race_id] = (
            count_by_race.get(
                race_id,
                0,
            )
            + 1
        )

    bad = {
        race_id: count
        for race_id, count
        in count_by_race.items()
        if count != 6
    }

    if bad:
        errors.append(
            "6艇揃っていない直前情報: "
            f"{len(bad)}レース"
        )

    return {
        "status": (
            "PASS"
            if not errors
            else "FAIL"
        ),
        "stored_races": len(race_rows),
        "stored_entries": len(entry_rows),
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        default=None,
        help="YYYYMMDD",
    )

    parser.add_argument(
        "--mode",
        choices=[
            "live",
            "sample",
            "all",
        ],
        default="live",
    )

    parser.add_argument(
        "--race-id",
        default=None,
    )

    parser.add_argument(
        "--sample-count",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--window-before",
        type=int,
        default=15,
        help="締切後何分まで対象にするか",
    )

    parser.add_argument(
        "--window-after",
        type=int,
        default=50,
        help="締切何分前から対象にするか",
    )

    args = parser.parse_args()

    target_date = (
        args.date
        if args.date
        else datetime.now(
            JST
        ).strftime("%Y%m%d")
    )

    base_races = load_base_races(
        target_date
    )

    selected = select_races(
        races=base_races,
        target_date=target_date,
        mode=args.mode,
        race_id=args.race_id,
        sample_count=args.sample_count,
        window_before=args.window_before,
        window_after=args.window_after,
    )

    print(
        "========================================"
    )
    print("直前情報収集")
    print(f"対象日: {target_date}")
    print(f"モード: {args.mode}")
    print(
        f"収集候補レース: {len(selected)}"
    )
    print(
        "========================================"
    )

    new_races = []
    new_entries = []

    fetched = 0
    ready = 0
    failed = []

    for base in selected:
        race_no = int(base["race"])

        url = (
            "https://www.boatrace.jp/"
            "owpc/pc/race/beforeinfo"
            f"?hd={target_date}"
            f"&jcd={base['venue_code']}"
            f"&rno={race_no}"
        )

        print(
            f"{base['venue_name']} "
            f"{race_no}R"
        )

        try:
            html = fetch_html(url)
            fetched += 1

            parsed = parse_beforeinfo(
                html,
                base,
            )

            if parsed is None:
                print(
                    "  → 直前情報未確定"
                )
            else:
                race_row, entry_rows = parsed

                new_races.append(
                    race_row
                )

                new_entries.extend(
                    entry_rows
                )

                ready += 1

                print(
                    "  → 取得完了"
                )

        except Exception as exc:
            failed.append(
                {
                    "race_id": (
                        base["race_id"]
                    ),
                    "error": str(exc),
                }
            )

            print(
                f"  → ERROR: {exc}"
            )

        time.sleep(0.4)

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    race_path = (
        DATA_DIR
        / f"beforeinfo_races_{target_date}.csv"
    )

    entry_path = (
        DATA_DIR
        / f"beforeinfo_entries_{target_date}.csv"
    )

    archive_dir = archive_beforeinfo_dir(
        target_date
    )

    old_races = load_existing_csv(
        race_path,
        archive_dir
        / race_path.name,
    )

    old_entries = load_existing_csv(
        entry_path,
        archive_dir
        / entry_path.name,
    )

    merged_races = merge_rows(
        old_races,
        new_races,
        ("race_id",),
    )

    merged_entries = merge_rows(
        old_entries,
        new_entries,
        (
            "race_id",
            "boat",
        ),
    )

    write_csv(
        race_path,
        merged_races,
        RACE_FIELDS,
    )

    write_csv(
        entry_path,
        merged_entries,
        ENTRY_FIELDS,
    )

    validation = validate(
        merged_races,
        merged_entries,
    )

    validation.update(
        {
            "target_date": target_date,
            "mode": args.mode,
            "selected_races": len(
                selected
            ),
            "fetched_races": fetched,
            "new_ready_races": ready,
            "failed_races": failed,
            "created_at": datetime.now(
                JST
            ).isoformat(),
        }
    )

    validation_path = (
        DATA_DIR
        / f"beforeinfo_validation_{target_date}.json"
    )

    validation_path.write_text(
        json.dumps(
            validation,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("")
    print(
        "========================================"
    )
    print("直前情報収集結果")
    print(
        f"候補: {len(selected)}レース"
    )
    print(
        f"取得アクセス: {fetched}レース"
    )
    print(
        f"今回確定: {ready}レース"
    )
    print(
        "累積保存: "
        f"{len(merged_races)}レース / "
        f"{len(merged_entries)}艇"
    )
    print(
        f"検証結果: {validation['status']}"
    )
    print(
        "========================================"
    )

    if validation["errors"]:
        for error in validation["errors"]:
            print(
                f"ERROR: {error}",
                file=sys.stderr,
            )

        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())