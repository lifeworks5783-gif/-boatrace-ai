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

FORBIDDEN_KEYS = {
    "finish",
    "actual_course",
    "actual_st",
    "race_time",
    "trifecta",
    "trifecta_pay",
    "exacta",
    "exacta_pay",
    "payout",
    "着順",
    "実コース",
    "実ST",
    "レースタイム",
    "払戻",
    "決まり手",
}


def fnum(v):
    if v is None or str(v).strip() == "":
        return None

    try:
        x = float(str(v).strip())

        if math.isnan(x):
            return None

        return x

    except (ValueError, TypeError):
        return None


def inum(v):
    x = fnum(v)

    if x is None:
        return None

    return int(x)


def bval(v):
    if isinstance(v, bool):
        return v

    return str(v).strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "t",
    }


def read_csv(path):
    with Path(path).open(
        "r",
        encoding="utf-8",
        newline="",
    ) as f:
        return list(
            csv.DictReader(f)
        )


def write_json(
    path,
    obj,
):
    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            obj,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def day_dir(
    yyyymmdd,
):
    d = datetime.strptime(
        yyyymmdd,
        "%Y%m%d",
    )

    return (
        Path("archive")
        / d.strftime("%Y")
        / d.strftime("%m")
        / d.strftime("%d")
    )


def find_file(
    yyyymmdd,
    name,
    subdir,
    required=True,
):
    direct = (
        DATA_DIR
        / name
    )

    if direct.exists():
        return direct

    archived = (
        day_dir(
            yyyymmdd
        )
        / subdir
        / name
    )

    if archived.exists():
        return archived

    if required:
        raise FileNotFoundError(
            f"必要ファイルが見つかりません: {name}"
        )

    return None


def rank_map(
    boats,
    getter,
    reverse,
):
    values = []

    for boat in boats:
        value = getter(
            boat
        )

        if value is not None:
            values.append(
                (
                    boat["boat"],
                    value,
                )
            )

    values.sort(
        key=lambda x: x[1],
        reverse=reverse,
    )

    out = {}
    previous = None
    rank = 0

    for index, (
        boat_no,
        value,
    ) in enumerate(
        values,
        start=1,
    ):
        if (
            previous is None
            or value != previous
        ):
            rank = index

        out[
            boat_no
        ] = rank

        previous = value

    return out


def build_race(
    race,
    base_map,
    before_race_map,
    before_entry_map,
    stage,
):
    race_id = (
        race["race_id"]
    )

    live_race = (
        before_race_map.get(
            race_id
        )
    )

    boats = []

    for boat_no in range(
        1,
        7,
    ):
        base = (
            base_map.get(
                (
                    race_id,
                    boat_no,
                )
            )
        )

        if base is None:
            continue

        live = (
            before_entry_map.get(
                (
                    race_id,
                    boat_no,
                )
            )
        )

        boats.append(
            {
                "boat": boat_no,

                "racer": {
                    "registration_no": inum(
                        base.get(
                            "registration_no"
                        )
                    ),
                    "name": base.get(
                        "racer_name",
                        "",
                    ),
                    "age": inum(
                        base.get(
                            "age"
                        )
                    ),
                    "branch": base.get(
                        "branch",
                        "",
                    ),
                    "grade": base.get(
                        "grade",
                        "",
                    ),
                    "official_f_count": inum(
                        base.get(
                            "f_count"
                        )
                    ),
                    "official_l_count": inum(
                        base.get(
                            "l_count"
                        )
                    ),
                    "official_avg_st": fnum(
                        base.get(
                            "official_avg_st"
                        )
                    ),
                    "official_fl_available": (
                        base.get("f_count") not in (None, "")
                        and base.get("l_count") not in (None, "")
                    ),
                },

                "official_stats": {
                    "national_win_rate": fnum(
                        base.get(
                            "national_win_rate"
                        )
                    ),
                    "national_top2_rate": fnum(
                        base.get(
                            "national_top2_rate"
                        )
                    ),
                    "local_win_rate": fnum(
                        base.get(
                            "local_win_rate"
                        )
                    ),
                    "local_top2_rate": fnum(
                        base.get(
                            "local_top2_rate"
                        )
                    ),
                },

                "motor": {
                    "motor_no": inum(
                        base.get(
                            "motor_no"
                        )
                    ),
                    "official_top2_rate": fnum(
                        base.get(
                            "motor_top2_rate"
                        )
                    ),
                },

                "boat_machine": {
                    "boat_no": inum(
                        base.get(
                            "boat_no"
                        )
                    ),
                    "official_top2_rate": fnum(
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

                "morning_weight_kg": fnum(
                    base.get(
                        "weight_kg"
                    )
                ),

                "beforeinfo": {
                    "available": (
                        live is not None
                    ),

                    "weight_kg": (
                        fnum(
                            live.get(
                                "weight_kg"
                            )
                        )
                        if live
                        else None
                    ),

                    "exhibition_time": (
                        fnum(
                            live.get(
                                "exhibition_time"
                            )
                        )
                        if live
                        else None
                    ),

                    "tilt": (
                        fnum(
                            live.get(
                                "tilt"
                            )
                        )
                        if live
                        else None
                    ),

                    "exhibition_course": (
                        inum(
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
                        fnum(
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
                        bval(
                            live.get(
                                "is_miss"
                            )
                        )
                        if live
                        else False
                    ),
                },

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
        )

    national_rank = rank_map(
        boats,
        lambda b: b[
            "official_stats"
        ][
            "national_win_rate"
        ],
        True,
    )

    local_rank = rank_map(
        boats,
        lambda b: b[
            "official_stats"
        ][
            "local_win_rate"
        ],
        True,
    )

    motor_rank = rank_map(
        boats,
        lambda b: b[
            "motor"
        ][
            "official_top2_rate"
        ],
        True,
    )

    exhibition_rank = rank_map(
        boats,
        lambda b: b[
            "beforeinfo"
        ][
            "exhibition_time"
        ],
        False,
    )

    for boat in boats:
        boat_no = (
            boat["boat"]
        )

        boat[
            "relative"
        ] = {
            "national_win_rank": national_rank.get(
                boat_no
            ),
            "local_win_rank": local_rank.get(
                boat_no
            ),
            "motor_top2_rank": motor_rank.get(
                boat_no
            ),
            "exhibition_time_rank": exhibition_rank.get(
                boat_no
            ),
        }

    weather = None

    if live_race:
        weather = {
            "weather": live_race.get(
                "weather",
                "",
            ),
            "air_temperature_c": fnum(
                live_race.get(
                    "air_temperature_c"
                )
            ),
            "water_temperature_c": fnum(
                live_race.get(
                    "water_temperature_c"
                )
            ),
            "wind_speed_mps": fnum(
                live_race.get(
                    "wind_speed_mps"
                )
            ),
            "wind_direction_code": inum(
                live_race.get(
                    "wind_direction_code"
                )
            ),
            "wind_direction": live_race.get(
                "wind_direction",
                "",
            ),
            "wave_height_cm": fnum(
                live_race.get(
                    "wave_height_cm"
                )
            ),
            "stabilizer": bval(
                live_race.get(
                    "stabilizer"
                )
            ),
        }

    return {
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
        "race": inum(
            race.get(
                "race"
            )
        ),
        "race_name": race.get(
            "race_name",
            "",
        ),
        "distance_m": inum(
            race.get(
                "distance_m"
            )
        ),
        "deadline": (
            live_race.get("deadline")
            if live_race and live_race.get("deadline")
            else race.get("deadline", "")
        ),
        "deadline_source": (
            live_race.get("deadline_source")
            if live_race and live_race.get("deadline_source")
            else "morning_program"
        ),
        "beforeinfo_requested_at": (
            live_race.get("requested_at", "")
            if live_race
            else ""
        ),
        "beforeinfo_collected_at": (
            live_race.get("collected_at", "")
            if live_race
            else ""
        ),
        "series_day": inum(
            race.get(
                "series_day"
            )
        ),
        "fixed_course": (
            bval(
                live_race.get(
                    "fixed_course"
                )
            )
            if live_race
            else bval(
                race.get(
                    "fixed_course"
                )
            )
        ),
        "prediction_stage": stage,
        "beforeinfo_status": (
            "ready"
            if live_race
            else "not_available"
        ),
        "weather": weather,
        "history_status": {
            "racer_30d": "not_built_yet",
            "racer_90d": "not_built_yet",
            "motor_30d": "not_built_yet",
            "motor_90d": "not_built_yet",
        },
        "boats": boats,
    }


def scan_forbidden(
    obj,
):
    found = []

    if isinstance(
        obj,
        dict,
    ):
        for key, value in obj.items():

            if key in FORBIDDEN_KEYS:
                found.append(
                    key
                )

            found.extend(
                scan_forbidden(
                    value
                )
            )

    elif isinstance(
        obj,
        list,
    ):
        for value in obj:
            found.extend(
                scan_forbidden(
                    value
                )
            )

    return found


def validate(
    races,
):
    errors = []

    race_ids = [
        race["race_id"]
        for race in races
    ]

    if len(
        race_ids
    ) != len(
        set(
            race_ids
        )
    ):
        errors.append(
            "prediction_input race_id重複"
        )

    for race in races:

        if len(
            race["boats"]
        ) != 6:
            errors.append(
                f"{race['race_id']}: 6艇揃っていません"
            )

        elif {
            boat["boat"]
            for boat
            in race["boats"]
        } != {
            1,
            2,
            3,
            4,
            5,
            6,
        }:
            errors.append(
                f"{race['race_id']}: 艇番1～6が不完全"
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
                    f"{race['race_id']}: 直前情報が6艇揃っていません"
                )

    leak = (
        scan_forbidden(
            races
        )
    )

    if leak:
        errors.append(
            "結果情報リーク候補を検出: "
            + ", ".join(
                leak[:10]
            )
        )

    live_count = sum(
        1
        for race in races
        if race[
            "beforeinfo_status"
        ]
        == "ready"
    )

    morning_count = (
        len(races)
        - live_count
    )

    warnings = []

    if morning_count:
        warnings.append(
            f"直前情報未取得: {morning_count}レース"
        )

    return {
        "status": (
            "PASS"
            if not errors
            else "FAIL"
        ),
        "race_count": len(
            races
        ),
        "beforeinfo_ready_races": live_count,
        "morning_only_races": morning_count,
        "errors": errors,
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "BOAT RACE prediction_input generator"
        )
    )

    parser.add_argument(
        "--date",
        default=None,
        help="対象日 YYYYMMDD",
    )

    parser.add_argument(
        "--stage",
        choices=[
            "morning",
            "live",
        ],
        default="morning",
    )

    args = parser.parse_args()

    target_date = (
        args.date
        or datetime.now(
            JST
        ).strftime(
            "%Y%m%d"
        )
    )

    stage = (
        args.stage
    )

    base_races = read_csv(
        find_file(
            target_date,
            f"program_races_{target_date}.csv",
            "pre_race/base",
            True,
        )
    )

    fl_entries_path = find_file(
        target_date,
        f"program_entries_fl_{target_date}.csv",
        "pre_race/base",
        False,
    )

    base_entries = read_csv(
        fl_entries_path
        if fl_entries_path
        else find_file(
            target_date,
            f"program_entries_{target_date}.csv",
            "pre_race/base",
            True,
        )
    )

    before_races_path = find_file(
        target_date,
        f"beforeinfo_races_{target_date}.csv",
        "pre_race/beforeinfo",
        False,
    )

    before_entries_path = find_file(
        target_date,
        f"beforeinfo_entries_{target_date}.csv",
        "pre_race/beforeinfo",
        False,
    )

    before_races = (
        read_csv(
            before_races_path
        )
        if before_races_path
        else []
    )

    before_entries = (
        read_csv(
            before_entries_path
        )
        if before_entries_path
        else []
    )

    base_map = {
        (
            row["race_id"],
            inum(
                row.get(
                    "boat"
                )
            ),
        ): row
        for row in base_entries
    }

    before_race_map = {
        row["race_id"]: row
        for row in before_races
    }

    before_entry_map = {
        (
            row["race_id"],
            inum(
                row.get(
                    "boat"
                )
            ),
        ): row
        for row in before_entries
    }

    races = [
        build_race(
            race,
            base_map,
            before_race_map,
            before_entry_map,
            stage,
        )
        for race in base_races
    ]

    races.sort(
        key=lambda race: (
            race[
                "venue_code"
            ],
            race[
                "race"
            ],
        )
    )

    check = validate(
        races
    )

    generated_at = (
        datetime.now(
            JST
        ).isoformat()
    )

    package = {
        "schema_version": "1.3",
        "target_date": target_date,
        "prediction_stage": stage,
        "generated_at": generated_at,
        "important_rule": (
            "予測時点で判明している情報のみ。"
            "着順・実ST・払戻等の結果情報は含めない。"
        ),
        "history_note": (
            "この段階では履歴結合前。enrich_prediction_input.pyで30日・90日履歴を接続する。"
            "公式F/Lファイルが存在する場合はF/L保有数・公式平均STを接続済み。"
            "未取得値は0ではなくavailable=false/nullで管理。"
        ),
        "race_count": len(
            races
        ),
        "beforeinfo_ready_races": check[
            "beforeinfo_ready_races"
        ],
        "races": races,
    }

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_json(
        DATA_DIR
        / (
            f"prediction_input_"
            f"{stage}_"
            f"{target_date}.json"
        ),
        package,
    )

    individual_dir = (
        DATA_DIR
        / "prediction_input"
        / target_date
        / stage
    )

    for race in races:
        write_json(
            individual_dir
            / f"{race['race_id']}.json",
            {
                "schema_version": "1.3",
                "target_date": target_date,
                "prediction_stage": stage,
                "generated_at": generated_at,
                "race": race,
            },
        )

    check.update(
        {
            "target_date": target_date,
            "prediction_stage": stage,
            "generated_at": generated_at,
        }
    )

    write_json(
        DATA_DIR
        / (
            f"prediction_input_validation_"
            f"{stage}_"
            f"{target_date}.json"
        ),
        check,
    )

    print(
        "========================================"
    )
    print(
        "予測入力データ生成"
    )
    print(
        f"対象日: {target_date}"
    )
    print(
        f"ステージ: {stage}"
    )
    print(
        f"レース数: {check['race_count']}"
    )
    print(
        "直前情報あり: "
        f"{check['beforeinfo_ready_races']}"
    )
    print(
        "朝データのみ: "
        f"{check['morning_only_races']}"
    )
    print(
        f"検証結果: {check['status']}"
    )
    print(
        "========================================"
    )

    for warning in (
        check[
            "warnings"
        ]
    ):
        print(
            f"WARNING: {warning}"
        )

    if check[
        "errors"
    ]:
        for error in (
            check[
                "errors"
            ]
        ):
            print(
                f"ERROR: {error}",
                file=sys.stderr,
            )

        return 1

    print(
        "prediction_input生成 PASS"
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )