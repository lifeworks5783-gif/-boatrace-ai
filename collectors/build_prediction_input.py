from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


JST = timezone(timedelta(hours=9))

DATA_DIR = Path("data")


# ============================================================
# 予測時点では絶対に混入させない結果系データ
# ============================================================

FORBIDDEN_KEYS = {
    "finish",
    "着順",
    "actual_course",
    "実コース",
    "actual_st",
    "実ST",
    "race_time",
    "レースタイム",
    "trifecta",
    "trifecta_pay",
    "exacta",
    "exacta_pay",
    "payout",
    "払戻",
    "決まり手",
}


# ============================================================
# 基本ユーティリティ
# ============================================================

def safe_float(value):
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    try:
        number = float(text)

        if math.isnan(number):
            return None

        return number

    except (ValueError, TypeError):
        return None


def safe_int(value):
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    try:
        return int(float(text))

    except (ValueError, TypeError):
        return None


def safe_bool(value):
    if isinstance(value, bool):
        return value

    if value is None:
        return False

    text = str(value).strip().lower()

    return text in {
        "true",
        "1",
        "yes",
        "y",
        "t",
    }


def mean(values):
    valid = [
        value
        for value in values
        if value is not None
    ]

    if not valid:
        return None

    return sum(valid) / len(valid)


def round_or_none(
    value,
    digits=3,
):
    if value is None:
        return None

    return round(value, digits)


def read_csv(path: Path) -> list[dict]:
    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as f:
        return list(csv.DictReader(f))


# ============================================================
# ファイル探索
# ============================================================

def archive_day_dir(
    target_date: str,
) -> Path:

    dt = datetime.strptime(
        target_date,
        "%Y%m%d",
    )

    return (
        Path("archive")
        / dt.strftime("%Y")
        / dt.strftime("%m")
        / dt.strftime("%d")
    )


def find_file(
    target_date: str,
    filename: str,
    archive_subdir: str,
    required: bool = True,
):
    direct = DATA_DIR / filename

    if direct.exists():
        return direct

    archived = (
        archive_day_dir(target_date)
        / archive_subdir
        / filename
    )

    if archived.exists():
        return archived

    if required:
        raise FileNotFoundError(
            f"必要ファイルが見つかりません: "
            f"{filename}"
        )

    return None


# ============================================================
# ランク計算
# ============================================================

def rank_desc(
    boats: list[dict],
    field: str,
):
    pairs = []

    for boat in boats:
        value = safe_float(
            boat.get(field)
        )

        if value is not None:
            pairs.append(
                (
                    boat["boat"],
                    value,
                )
            )

    pairs.sort(
        key=lambda x: x[1],
        reverse=True,
    )

    result = {}

    current_rank = 0
    previous_value = None

    for index, (
        boat_no,
        value,
    ) in enumerate(
        pairs,
        start=1,
    ):
        if (
            previous_value is None
            or value != previous_value
        ):
            current_rank = index

        result[boat_no] = current_rank
        previous_value = value

    return result


def rank_asc(
    boats: list[dict],
    field: str,
):
    pairs = []

    for boat in boats:
        value = safe_float(
            boat.get(field)
        )

        if value is not None:
            pairs.append(
                (
                    boat["boat"],
                    value,
                )
            )

    pairs.sort(
        key=lambda x: x[1]
    )

    result = {}

    current_rank = 0
    previous_value = None

    for index, (
        boat_no,
        value,
    ) in enumerate(
        pairs,
        start=1,
    ):
        if (
            previous_value is None
            or value != previous_value
        ):
            current_rank = index

        result[boat_no] = current_rank
        previous_value = value

    return result


# ============================================================
# データ結合
# ============================================================

def build_beforeinfo_maps(
    race_rows: list[dict],
    entry_rows: list[dict],
):
    race_map = {
        row["race_id"]: row
        for row in race_rows
    }

    entry_map = {
        (
            row["race_id"],
            safe_int(row["boat"]),
        ): row
        for row in entry_rows
    }

    return race_map, entry_map


def build_base_entry_map(
    rows: list[dict],
):
    return {
        (
            row["race_id"],
            safe_int(row["boat"]),
        ): row
        for row in rows
    }


# ============================================================
# 1レース分を予測入力化
# ============================================================

def build_race(
    race: dict,
    base_entry_map: dict,
    before_race_map: dict,
    before_entry_map: dict,
    stage: str,
):
    race_id = race["race_id"]

    live_race = before_race_map.get(
        race_id
    )

    boats = []

    for boat_no in range(1, 7):
        base = base_entry_map.get(
            (
                race_id,
                boat_no,
            )
        )

        if base is None:
            continue

        live = before_entry_map.get(
            (
                race_id,
                boat_no,
            )
        )

        row = {
            "boat": boat_no,

            "racer": {
                "registration_no": safe_int(
                    base.get(
                        "registration_no"
                    )
                ),
                "name": base.get(
                    "racer_name",
                    "",
                ),
                "age": safe_int(
                    base.get("age")
                ),
                "branch": base.get(
                    "branch",
                    "",
                ),
                "grade": base.get(
                    "grade",
                    "",
                ),
            },

            "official_stats": {
                "national_win_rate": safe_float(
                    base.get(
                        "national_win_rate"
                    )
                ),
                "national_top2_rate": safe_float(
                    base.get(
                        "national_top2_rate"
                    )
                ),
                "local_win_rate": safe_float(
                    base.get(
                        "local_win_rate"
                    )
                ),
                "local_top2_rate": safe_float(
                    base.get(
                        "local_top2_rate"
                    )
                ),
            },

            "motor": {
                "motor_no": safe_int(
                    base.get(
                        "motor_no"
                    )
                ),
                "official_top2_rate": safe_float(
                    base.get(
                        "motor_top2_rate"
                    )
                ),
            },

            "boat_machine": {
                "boat_no": safe_int(
                    base.get(
                        "boat_no"
                    )
                ),
                "official_top2_rate": safe_float(
                    base.get(
                        "boat_top2_rate"
                    )
                ),
            },

            "series": {
                "results_raw": base.get(
                    "series_results_raw",
                    "",
                ),
                "early_race_raw": base.get(
                    "early_race_raw",
                    "",
                ),
            },

            "morning_weight_kg": safe_float(
                base.get(
                    "weight_kg"
                )
            ),

            "beforeinfo": {
                "available": (
                    live is not None
                ),
                "weight_kg": (
                    safe_float(
                        live.get(
                            "weight_kg"
                        )
                    )
                    if live
                    else None
                ),
                "exhibition_time": (
                    safe_float(
                        live.get(
                            "exhibition_time"
                        )
                    )
                    if live
                    else None
                ),
                "tilt": (
                    safe_float(
                        live.get("tilt")
                    )
                    if live
                    else None
                ),
                "exhibition_course": (
                    safe_int(
                        live.get(
                            "exhibition_course"
                        )
                    )
                    if live
                    else None
                ),
                "exhibition_st_raw": (
                    live.get(
                        "exhibition_st_raw",
                        "",
                    )
                    if live
                    else ""
                ),
                "exhibition_st_seconds": (
                    safe_float(
                        live.get(
                            "exhibition_st_seconds"
                        )
                    )
                    if live
                    else None
                ),
                "exhibition_st_flag": (
                    live.get(
                        "exhibition_st_flag",
                        "",
                    )
                    if live
                    else ""
                ),
                "change_parts": (
                    live.get(
                        "change_parts",
                        "",
                    )
                    if live
                    else ""
                ),
                "is_miss": (
                    safe_bool(
                        live.get(
                            "is_miss"
                        )
                    )
                    if live
                    else False
                ),
            },

            # 30日・90日履歴は
            # 次の開発段階でGitHub集計値を接続する。
            # 「0」ではなく unavailable とする。
            "history": {
                "racer_30d_available": False,
                "racer_90d_available": False,
                "motor_30d_available": False,
                "motor_90d_available": False,

                "racer_30d": None,
                "racer_90d": None,
                "motor_30d": None,
                "motor_90d": None,
            },
        }

        boats.append(row)

    # ========================================================
    # レース内相対評価
    # ========================================================

    flat_boats = []

    for boat in boats:
        flat_boats.append(
            {
                "boat": boat["boat"],

                "national_win_rate":
                    boat[
                        "official_stats"
                    ][
                        "national_win_rate"
                    ],

                "local_win_rate":
                    boat[
                        "official_stats"
                    ][
                        "local_win_rate"
                    ],

                "motor_top2_rate":
                    boat[
                        "motor"
                    ][
                        "official_top2_rate"
                    ],

                "boat_top2_rate":
                    boat[
                        "boat_machine"
                    ][
                        "official_top2_rate"
                    ],

                "exhibition_time":
                    boat[
                        "beforeinfo"
                    ][
                        "exhibition_time"
                    ],
            }
        )

    national_rank = rank_desc(
        flat_boats,
        "national_win_rate",
    )

    local_rank = rank_desc(
        flat_boats,
        "local_win_rate",
    )

    motor_rank = rank_desc(
        flat_boats,
        "motor_top2_rate",
    )

    boat_rank = rank_desc(
        flat_boats,
        "boat_top2_rate",
    )

    exhibition_rank = rank_asc(
        flat_boats,
        "exhibition_time",
    )

    national_mean = mean(
        [
            item[
                "national_win_rate"
            ]
            for item in flat_boats
        ]
    )

    local_mean = mean(
        [
            item[
                "local_win_rate"
            ]
            for item in flat_boats
        ]
    )

    motor_mean = mean(
        [
            item[
                "motor_top2_rate"
            ]
            for item in flat_boats
        ]
    )

    boat_mean = mean(
        [
            item[
                "boat_top2_rate"
            ]
            for item in flat_boats
        ]
    )

    exhibition_mean = mean(
        [
            item[
                "exhibition_time"
            ]
            for item in flat_boats
        ]
    )

    for boat in boats:
        boat_no = boat["boat"]

        national = (
            boat[
                "official_stats"
            ][
                "national_win_rate"
            ]
        )

        local = (
            boat[
                "official_stats"
            ][
                "local_win_rate"
            ]
        )

        motor = (
            boat[
                "motor"
            ][
                "official_top2_rate"
            ]
        )

        boat_rate = (
            boat[
                "boat_machine"
            ][
                "official_top2_rate"
            ]
        )

        exhibition = (
            boat[
                "beforeinfo"
            ][
                "exhibition_time"
            ]
        )

        boat["relative"] = {
            "national_win_rank":
                national_rank.get(
                    boat_no
                ),

            "local_win_rank":
                local_rank.get(
                    boat_no
                ),

            "motor_top2_rank":
                motor_rank.get(
                    boat_no
                ),

            "boat_top2_rank":
                boat_rank.get(
                    boat_no
                ),

            "exhibition_time_rank":
                exhibition_rank.get(
                    boat_no
                ),

            "national_win_vs_field":
                round_or_none(
                    (
                        national
                        - national_mean
                    )
                    if (
                        national is not None
                        and national_mean
                        is not None
                    )
                    else None
                ),

            "local_win_vs_field":
                round_or_none(
                    (
                        local
                        - local_mean
                    )
                    if (
                        local is not None
                        and local_mean
                        is not None
                    )
                    else None
                ),

            "motor_top2_vs_field":
                round_or_none(
                    (
                        motor
                        - motor_mean
                    )
                    if (
                        motor is not None
                        and motor_mean
                        is not None
                    )
                    else None
                ),

            "boat_top2_vs_field":
                round_or_none(
                    (
                        boat_rate
                        - boat_mean
                    )
                    if (
                        boat_rate is not None
                        and boat_mean
                        is not None
                    )
                    else None
                ),

            # 展示タイムは小さい方が良いため
            # 平均 - 本艇 とする。
            # 正なら場内平均より速い。
            "exhibition_time_advantage":
                round_or_none(
                    (
                        exhibition_mean
                        - exhibition
                    )
                    if (
                        exhibition
                        is not None
                        and exhibition_mean
                        is not None
                    )
                    else None,
                    3,
                ),
        }

    # ========================================================
    # 直前情報
    # ========================================================

    before_available = (
        live_race is not None
    )

    weather = None

    if live_race:
        weather = {
            "weather": live_race.get(
                "weather",
                "",
            ),
            "air_temperature_c": safe_float(
                live_race.get(
                    "air_temperature_c"
                )
            ),
            "water_temperature_c": safe_float(
                live_race.get(
                    "water_temperature_c"
                )
            ),
            "wind_speed_mps": safe_float(
                live_race.get(
                    "wind_speed_mps"
                )
            ),
            "wind_direction_code": safe_int(
                live_race.get(
                    "wind_direction_code"
                )
            ),
            "wind_direction": live_race.get(
                "wind_direction",
                "",
            ),
            "wave_height_cm": safe_float(
                live_race.get(
                    "wave_height_cm"
                )
            ),
            "stabilizer": safe_bool(
                live_race.get(
                    "stabilizer"
                )
            ),
        }

    race_object = {
        "race_id": race_id,
        "date": race.get(
            "date",
            "",
        ),
        "venue_code": race.get(
            "venue_code",
            "",
        ),
        "venue_name": race.get(
            "venue_name",
            "",
        ),
        "race": safe_int(
            race.get("race")
        ),
        "race_name": race.get(
            "race_name",
            "",
        ),
        "distance_m": safe_int(
            race.get(
                "distance_m"
            )
        ),
        "deadline": race.get(
            "deadline",
            "",
        ),
        "series_day": safe_int(
            race.get(
                "series_day"
            )
        ),
        "fixed_course": (
            safe_bool(
                live_race.get(
                    "fixed_course"
                )
            )
            if live_race
            else safe_bool(
                race.get(
                    "fixed_course"
                )
            )
        ),

        "prediction_stage": stage,

        "beforeinfo_status": (
            "ready"
            if before_available
            else "not_available"
        ),

        "weather": weather,

        "field_summary": {
            "national_win_rate_mean":
                round_or_none(
                    national_mean
                ),

            "local_win_rate_mean":
                round_or_none(
                    local_mean
                ),

            "motor_top2_rate_mean":
                round_or_none(
                    motor_mean
                ),

            "boat_top2_rate_mean":
                round_or_none(
                    boat_mean
                ),

            "exhibition_time_mean":
                round_or_none(
                    exhibition_mean,
                    3,
                ),
        },

        "history_status": {
            "racer_30d": "not_built_yet",
            "racer_90d": "not_built_yet",
            "motor_30d": "not_built_yet",
            "motor_90d": "not_built_yet",
        },

        "boats": boats,
    }

    return race_object


# ============================================================
# リーク検査
# ============================================================

def scan_forbidden_keys(
    obj,
    path="root",
):
    found = []

    if isinstance(
        obj,
        dict,
    ):
        for key, value in obj.items():
            if key in FORBIDDEN_KEYS:
                found.append(
                    f"{path}.{key}"
                )

            found.extend(
                scan_forbidden_keys(
                    value,
                    f"{path}.{key}",
                )
            )

    elif isinstance(
        obj,
        list,
    ):
        for index, value in enumerate(obj):
            found.extend(
                scan_forbidden_keys(
                    value,
                    f"{path}[{index}]",
                )
            )

    return found


# ============================================================
# 全体検証
# ============================================================

def validate_output(
    races: list[dict],
):
    errors = []
    warnings = []

    race_ids = [
        race["race_id"]
        for race in races
    ]

    if len(race_ids) != len(
        set(race_ids)
    ):
        errors.append(
            "prediction_input race_id重複"
        )

    for race in races:
        if len(
            race["boats"]
        ) != 6:
            errors.append(
                f"{race['race_id']}: "
                "6艇揃っていません"
            )

        boat_numbers = [
            boat["boat"]
            for boat in race["boats"]
        ]

        if set(
            boat_numbers
        ) != {
            1, 2, 3, 4, 5, 6
        }:
            errors.append(
                f"{race['race_id']}: "
                "艇番1～6が不完全"
            )

        if (
            race[
                "beforeinfo_status"
            ]
            == "ready"
        ):
            ready_count = sum(
                1
                for boat
                in race["boats"]
                if boat[
                    "beforeinfo"
                ][
                    "available"
                ]
            )

            if ready_count != 6:
                errors.append(
                    f"{race['race_id']}: "
                    "直前情報が6艇揃っていません"
                )

    forbidden = scan_forbidden_keys(
        races
    )

    if forbidden:
        errors.append(
            "結果情報リーク候補を検出: "
            + ", ".join(
                forbidden[:10]
            )
        )

    morning_only = sum(
        1
        for race in races
        if race[
            "beforeinfo_status"
        ]
        != "ready"
    )

    ready = (
        len(races)
        - morning_only
    )

    if morning_only:
        warnings.append(
            f"直前情報未取得: "
            f"{morning_only}レース"
        )

    return {
        "status": (
            "PASS"
            if not errors
            else "FAIL"
        ),
        "race_count": len(races),
        "beforeinfo_ready_races": ready,
        "morning_only_races": morning_only,
        "errors": errors,
        "warnings": warnings,
    }


# ============================================================
# JSON出力
# ============================================================

def write_json(
    path: Path,
    data,
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        default=None,
        help="YYYYMMDD",
    )

    parser.add_argument(
        "--stage",
        choices=[
            "morning",
            "live",
        ],
       