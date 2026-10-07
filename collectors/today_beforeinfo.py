from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup


JST = timezone(timedelta(hours=9))
DATA_DIR = Path("data")

DEFAULT_WINDOW_AFTER = 40
DEFAULT_WINDOW_BEFORE = 0
DEFAULT_REFRESH_WINDOW = 18
DEFAULT_MIN_REFRESH_INTERVAL = 8
DEFAULT_WORKERS = 4

REQUEST_CONNECT_TIMEOUT = 5
REQUEST_READ_TIMEOUT = 12
REQUEST_RETRIES = 2

_THREAD_LOCAL = threading.local()

WIND_DIR = {
    1: "北", 2: "北北東", 3: "北東", 4: "東北東",
    5: "東", 6: "東南東", 7: "南東", 8: "南南東",
    9: "南", 10: "南南西", 11: "南西", 12: "西南西",
    13: "西", 14: "西北西", 15: "北西", 16: "北北西",
}

RACE_FIELDS = [
    "date", "venue_code", "venue_name", "race", "race_id",
    "deadline", "weather", "air_temperature_c",
    "water_temperature_c", "wind_speed_mps",
    "wind_direction_code", "wind_direction", "wave_height_cm",
    "stabilizer", "fixed_course", "source_url", "requested_at", "collected_at",
]

ENTRY_FIELDS = [
    "date", "venue_code", "venue_name", "race", "race_id",
    "boat", "registration_no", "racer_name", "weight_kg",
    "exhibition_time", "tilt", "exhibition_course",
    "exhibition_st_raw", "exhibition_st_seconds",
    "exhibition_st_flag", "change_parts", "is_miss",
    "source_url", "requested_at", "collected_at",
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

    if text.startswith("."):
        text = "0" + text
    elif text.startswith("-."):
        text = "-0" + text[1:]

    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None

    try:
        return float(match.group())
    except ValueError:
        return None


def parse_st(value: str):
    value = clean_text(value).upper()

    if not value:
        return None, ""

    flag = ""

    if value.startswith("F"):
        flag = "F"
        raw = value[1:]
        if raw.startswith("."):
            raw = "0" + raw
        number = safe_float(raw)
        if number is not None:
            number = -abs(number)
        return number, flag

    if value.startswith("L"):
        flag = "L"
        raw = value[1:]
        if raw.startswith("."):
            raw = "0" + raw
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

    daily_cache = (
        Path("daily_inputs")
        / dt.strftime("%Y")
        / dt.strftime("%m")
        / dt.strftime("%d")
        / "base"
        / f"program_races_{target_date}.csv"
    )
    if daily_cache.exists():
        return daily_cache

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

    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def normalize_external_race_id(value: str) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) < 12:
        return ""
    return f"{digits[:8]}-{digits[8:10]}-{digits[10:12]}"


def load_dynamic_deadlines(target_date: str) -> dict[str, str]:
    dt = datetime.strptime(target_date, "%Y%m%d")
    url = (
        "https://raw.githubusercontent.com/"
        "BoatraceCSV/boatracecsv.github.io/main/data/previews/od3/"
        f"{dt:%Y/%m/%d}.csv"
    )

    try:
        response = requests.get(
            url,
            timeout=(REQUEST_CONNECT_TIMEOUT, REQUEST_READ_TIMEOUT),
            headers={"User-Agent": "boatrace-ai-deadline-overlay/1.0"},
        )
        response.raise_for_status()
        rows = csv.DictReader(response.text.lstrip("\ufeff").splitlines())

        latest: dict[str, tuple[str, str]] = {}
        for row in rows:
            race_id = normalize_external_race_id(
                row.get("レースコード", "")
            )
            deadline = str(
                row.get("締切時刻", "")
            ).strip()
            obtained_at = str(
                row.get("取得日時", "")
            ).strip()

            if not race_id or not deadline:
                continue

            previous = latest.get(race_id)
            if previous is None or obtained_at >= previous[0]:
                latest[race_id] = (
                    obtained_at,
                    deadline,
                )

        return {
            race_id: value[1]
            for race_id, value in latest.items()
        }

    except Exception as exc:
        print(
            "WARN: 当日締切時刻の動的取得に失敗: "
            f"{exc}"
        )
        return {}


def apply_dynamic_deadlines(
    races: list[dict],
    target_date: str,
) -> tuple[list[dict], dict[str, str]]:
    overlay = load_dynamic_deadlines(
        target_date
    )

    if not overlay:
        return races, {}

    changed: dict[str, str] = {}
    output = []

    for row in races:
        item = dict(row)
        race_id = str(
            item.get("race_id", "")
        ).strip()
        revised = overlay.get(
            race_id
        )
        original = str(
            item.get("deadline", "")
        ).strip()

        if revised and revised != original:
            item["deadline_original"] = original
            item["deadline"] = revised
            item["deadline_source"] = "live_odds"
            changed[race_id] = (
                f"{original}->{revised}"
            )

        output.append(
            item
        )

    if changed:
        print(
            "当日締切変更を反映:",
            changed,
        )

    return output, changed


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
    if data_path.exists():
        target = data_path
    elif archive_path.exists():
        target = archive_path
    else:
        return []

    with target.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def race_datetime(target_date: str, deadline: str) -> datetime:
    return datetime.strptime(
        f"{target_date} {deadline}",
        "%Y%m%d %H:%M",
    ).replace(tzinfo=JST)


def parse_iso_datetime(value) -> datetime | None:
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(
            str(value).strip().replace("Z", "+00:00")
        )
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)

    return dt.astimezone(JST)


def load_existing_beforeinfo_times(
    target_date: str,
) -> dict[str, datetime | None]:
    """Return the last raw beforeinfo collection time for each race.

    Collection refresh decisions must depend only on collected source data,
    never on whether prediction/scoring succeeded.
    """
    archive_dir = archive_beforeinfo_dir(target_date)
    rows = load_existing_csv(
        DATA_DIR / f"beforeinfo_races_{target_date}.csv",
        archive_dir / f"beforeinfo_races_{target_date}.csv",
    )

    result: dict[str, datetime | None] = {}
    for row in rows:
        race_id = str(row.get("race_id", "")).strip()
        if not race_id:
            continue
        collected_at = parse_iso_datetime(row.get("collected_at"))
        previous = result.get(race_id)
        if collected_at is not None and (
            previous is None or collected_at > previous
        ):
            result[race_id] = collected_at
        elif race_id not in result:
            result[race_id] = None

    return result

def select_races(
    races: list[dict],
    target_date: str,
    mode: str,
    race_id: str | None,
    sample_count: int,
    window_before: int,
    window_after: int,
    refresh_window: int,
    min_refresh_interval: int,
) -> list[dict]:
    if race_id:
        return [
            row
            for row in races
            if row.get("race_id") == race_id
        ]

    if mode == "all":
        return races

    now = datetime.now(JST)

    existing_raw = (
        load_existing_beforeinfo_times(target_date)
        if mode in ("live", "missing")
        else {}
    )

    if mode == "missing":
        candidates = []
        for row in races:
            current_race_id = str(row.get("race_id", "")).strip()
            if current_race_id and current_race_id not in existing_raw:
                row_copy = dict(row)
                row_copy["_selection_reason"] = "missing"
                candidates.append(row_copy)
        return candidates

    candidates = []

    candidates = []

    for row in races:
        deadline = row.get("deadline", "")
        if not deadline:
            continue

        try:
            deadline_dt = race_datetime(
                target_date,
                deadline,
            )
        except ValueError:
            continue

        minutes = (
            deadline_dt - now
        ).total_seconds() / 60.0

        row_copy = dict(row)
        row_copy["_minutes"] = minutes
        row_copy["_selection_reason"] = ""

        if mode == "live":
            if (
                minutes < -window_before
                or minutes > window_after
            ):
                continue

            current_race_id = str(
                row.get("race_id", "")
            ).strip()

            # raw直前情報がまだないレースは最優先で取得。
            # 予測処理の成功・失敗とは完全に独立させる。
            if current_race_id not in existing_raw:
                row_copy["_selection_reason"] = "new"
                candidates.append(row_copy)
                continue

            # raw取得済みで締切がまだ遠いレースは再取得しない
            if minutes > refresh_window:
                continue

            # 手動連打などで同じレースを短時間に再取得しない
            last_collection_at = existing_raw.get(
                current_race_id
            )

            if last_collection_at is not None:
                elapsed_minutes = (
                    now - last_collection_at
                ).total_seconds() / 60.0

                if elapsed_minutes < min_refresh_interval:
                    continue

            row_copy["_selection_reason"] = "refresh"
            candidates.append(row_copy)

        elif mode == "sample":
            if -180 <= minutes <= 90:
                row_copy["_selection_reason"] = "sample"
                candidates.append(row_copy)

    # 締切が近い順
    candidates.sort(
        key=lambda row: row.get("_minutes", 999999)
    )

    if mode == "sample":
        return candidates[:sample_count]

    return candidates


def get_session() -> requests.Session:
    session = getattr(
        _THREAD_LOCAL,
        "session",
        None,
    )

    if session is None:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(compatible; boatrace-ai-data-collector/2.0)"
                ),
                "Accept-Language": "ja,en;q=0.8",
                "Connection": "keep-alive",
            }
        )
        _THREAD_LOCAL.session = session

    return session


def fetch_html(url: str) -> str:
    session = get_session()
    last_error = None

    for attempt in range(1, REQUEST_RETRIES + 1):
        try:
            response = session.get(
                url,
                timeout=(
                    REQUEST_CONNECT_TIMEOUT,
                    REQUEST_READ_TIMEOUT,
                ),
            )
            response.raise_for_status()
            return response.text

        except Exception as exc:
            last_error = exc

            if attempt < REQUEST_RETRIES:
                time.sleep(0.5 * attempt)

    raise RuntimeError(
        f"取得失敗: {url} / {last_error}"
    )


def is_no_data(soup: BeautifulSoup) -> bool:
    return (
        "データがありません"
        in soup.get_text(" ", strip=True)
    )


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
            WIND_DIR.get(direction_code, "")
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
            or any("安定板" in label for label in labels)
        ),
        "fixed_course": (
            "進入固定" in labels
            or any("進入固定" in label for label in labels)
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


def find_entry_tbodies(soup: BeautifulSoup):
    tbodies = soup.select(
        "table.is-w748 tbody"
    )

    if len(tbodies) >= 6:
        return tbodies[:6]

    tables = soup.select("div.table1")

    if len(tables) >= 2:
        tbodies = tables[1].select("tbody")

    return tbodies[:6]


def parse_entry_table(soup: BeautifulSoup):
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
                registration_no = match.group(1)

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
            clean_text(get_text(cell))
            for cell in cells
        ]

        weight = None
        exhibition_time = None
        tilt = None
        kg_index = None

        for i, cell_text in enumerate(texts):
            if "kg" in cell_text.lower():
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
                "exhibition_course": course_by_boat.get(
                    boat
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
    requested_at: str = "",
):
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    if is_no_data(soup):
        return None

    entry_rows = parse_entry_table(soup)

    if len(entry_rows) != 6:
        return None

    exhibition_count = sum(
        1
        for row in entry_rows
        if row["exhibition_time"] is not None
    )

    st_count = sum(
        1
        for row in entry_rows
        if row["exhibition_st_raw"]
    )

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
        "requested_at": requested_at,
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
                "requested_at": requested_at,
                "collected_at": collected_at,
            }
        )

    return race_row, final_entries


def build_url(
    target_date: str,
    base: dict,
) -> str:
    return (
        "https://www.boatrace.jp/"
        "owpc/pc/race/beforeinfo"
        f"?hd={target_date}"
        f"&jcd={base['venue_code']}"
        f"&rno={int(base['race'])}"
    )


def fetch_one(
    base: dict,
    target_date: str,
):
    started = time.monotonic()

    url = build_url(
        target_date,
        base,
    )

    requested_at = datetime.now(JST).isoformat()

    try:
        html = fetch_html(url)

        parsed = parse_beforeinfo(
            html,
            base,
            requested_at=requested_at,
        )

        return {
            "base": base,
            "parsed": parsed,
            "error": None,
            "elapsed_seconds": (
                time.monotonic() - started
            ),
        }

    except Exception as exc:
        return {
            "base": base,
            "parsed": None,
            "error": str(exc),
            "elapsed_seconds": (
                time.monotonic() - started
            ),
        }


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
                    field: row.get(field, "")
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

    if len(race_ids) != len(set(race_ids)):
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
        for race_id, count in count_by_race.items()
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
        choices=["live", "sample", "all", "missing"],
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
        default=DEFAULT_WINDOW_BEFORE,
        help="締切後何分まで対象にするか",
    )

    parser.add_argument(
        "--window-after",
        type=int,
        default=DEFAULT_WINDOW_AFTER,
        help="締切何分前から対象にするか",
    )

    parser.add_argument(
        "--refresh-window",
        type=int,
        default=DEFAULT_REFRESH_WINDOW,
        help=(
            "一度直前予測済みのレースを"
            "再確認する締切前分数"
        ),
    )

    parser.add_argument(
        "--min-refresh-interval",
        type=int,
        default=DEFAULT_MIN_REFRESH_INTERVAL,
        help=(
            "同じレースを再取得する"
            "最小間隔（分）"
        ),
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help="並列取得数。最大4",
    )

    args = parser.parse_args()

    target_date = (
        args.date
        if args.date
        else datetime.now(JST).strftime(
            "%Y%m%d"
        )
    )

    started_all = time.monotonic()

    base_races = load_base_races(
        target_date
    )

    base_races, deadline_changes = apply_dynamic_deadlines(
        base_races,
        target_date,
    )

    selected = select_races(
        races=base_races,
        target_date=target_date,
        mode=args.mode,
        race_id=args.race_id,
        sample_count=args.sample_count,
        window_before=args.window_before,
        window_after=args.window_after,
        refresh_window=args.refresh_window,
        min_refresh_interval=(
            args.min_refresh_interval
        ),
    )

    new_count = sum(
        1
        for row in selected
        if row.get("_selection_reason") == "new"
    )

    refresh_count = sum(
        1
        for row in selected
        if row.get("_selection_reason")
        == "refresh"
    )

    workers = max(
        1,
        min(args.workers, 4),
    )

    print(
        "========================================"
    )
    print("直前情報収集・高速版")
    print(f"対象日: {target_date}")
    print(f"モード: {args.mode}")
    print(
        "対象窓: "
        f"締切{args.window_after}分前"
        "〜"
        f"締切後{args.window_before}分"
    )
    print(f"収集候補: {len(selected)}R")

    if args.mode == "live":
        print(f"  新規: {new_count}R")
        print(
            f"  再確認: {refresh_count}R"
        )

    print(f"並列数: {workers}")
    print(
        "========================================"
    )

    new_races = []
    new_entries = []

    fetched = 0
    ready = 0
    failed = []
    unready_new_races = []
    per_request_seconds = []

    if selected:
        with ThreadPoolExecutor(
            max_workers=workers
        ) as executor:
            futures = {
                executor.submit(
                    fetch_one,
                    base,
                    target_date,
                ): base
                for base in selected
            }

            for future in as_completed(
                futures
            ):
                result = future.result()

                base = result["base"]
                race_no = int(base["race"])
                reason = base.get(
                    "_selection_reason",
                    "",
                )
                elapsed = float(
                    result.get(
                        "elapsed_seconds",
                        0.0,
                    )
                )

                per_request_seconds.append(
                    elapsed
                )

                if result["error"]:
                    failed.append(
                        {
                            "race_id": base[
                                "race_id"
                            ],
                            "error": result[
                                "error"
                            ],
                        }
                    )
                    if reason == "new":
                        unready_new_races.append(base["race_id"])

                    print(
                        f"{base['venue_name']} "
                        f"{race_no}R "
                        f"[{reason}] "
                        f"→ ERROR "
                        f"({elapsed:.1f}s): "
                        f"{result['error']}"
                    )
                    continue

                fetched += 1

                parsed = result["parsed"]

                if parsed is None:
                    if reason == "new":
                        unready_new_races.append(base["race_id"])
                    print(
                        f"{base['venue_name']} "
                        f"{race_no}R "
                        f"[{reason}] "
                        "→ 直前情報未確定 "
                        f"({elapsed:.1f}s)"
                    )
                    continue

                race_row, entry_rows = (
                    parsed
                )

                new_races.append(
                    race_row
                )
                new_entries.extend(
                    entry_rows
                )
                ready += 1

                print(
                    f"{base['venue_name']} "
                    f"{race_no}R "
                    f"[{reason}] "
                    "→ 取得完了 "
                    f"({elapsed:.1f}s)"
                )

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
        archive_dir / race_path.name,
    )

    old_entries = load_existing_csv(
        entry_path,
        archive_dir / entry_path.name,
    )

    merged_races = merge_rows(
        old_races,
        new_races,
        ("race_id",),
    )

    merged_entries = merge_rows(
        old_entries,
        new_entries,
        ("race_id", "boat"),
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

    elapsed_all = (
        time.monotonic()
        - started_all
    )

    average_request_seconds = (
        sum(per_request_seconds)
        / len(per_request_seconds)
        if per_request_seconds
        else 0.0
    )

    max_request_seconds = (
        max(per_request_seconds)
        if per_request_seconds
        else 0.0
    )

    validation.update(
        {
            "target_date": target_date,
            "mode": args.mode,
            "window_after_minutes": (
                args.window_after
            ),
            "window_before_minutes": (
                args.window_before
            ),
            "refresh_window_minutes": (
                args.refresh_window
            ),
            "min_refresh_interval_minutes": (
                args.min_refresh_interval
            ),
            "workers": workers,
            "deadline_changes": deadline_changes,
            "selected_races": len(selected),
            "selected_new_races": new_count,
            "selected_refresh_races": (
                refresh_count
            ),
            "fetched_races": fetched,
            "new_ready_races": ready,
            "unready_new_count": len(set(unready_new_races)),
            "unready_new_races": sorted(set(unready_new_races)),
            "failed_races": failed,
            "average_request_seconds": round(
                average_request_seconds,
                3,
            ),
            "max_request_seconds": round(
                max_request_seconds,
                3,
            ),
            "elapsed_seconds": round(
                elapsed_all,
                3,
            ),
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
    print(f"候補: {len(selected)}R")
    print(f"取得成功: {fetched}R")
    print(f"今回確定: {ready}R")
    print(
        "累積保存: "
        f"{len(merged_races)}R / "
        f"{len(merged_entries)}艇"
    )
    print(
        "平均アクセス時間: "
        f"{average_request_seconds:.2f}秒"
    )
    print(
        "最長アクセス時間: "
        f"{max_request_seconds:.2f}秒"
    )
    print(
        "全体時間: "
        f"{elapsed_all:.2f}秒"
    )
    print(
        "検証結果: "
        f"{validation['status']}"
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
