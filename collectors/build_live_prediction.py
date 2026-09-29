from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import build_morning_prediction as morning


JST = timezone(timedelta(hours=9))

MODEL_VERSION = "live_heuristic_v1"

LIVE_WEIGHTS = {
    "morning_base": 70.0,
    "exhibition_course": 8.0,
    "racer_course": 7.0,
    "exhibition_time": 8.0,
    "exhibition_st": 7.0,
}

FORBIDDEN_CURRENT_RESULT_KEYS = {
    "finish",
    "result",
    "race_time",
    "actual_st",
    "actual_course",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="直前情報を使ってBOAT RACE最終予測を生成"
    )

    parser.add_argument(
        "--date",
        required=True,
        help="対象日 YYYYMMDD",
    )

    parser.add_argument(
        "--input",
        default=None,
    )

    parser.add_argument(
        "--output-dir",
        default="data",
    )

    parser.add_argument(
        "--now",
        default=None,
        help="検証用現在時刻 ISO8601",
    )

    return parser.parse_args()


def text(value):
    if value is None:
        return ""

    return str(value).strip()


def to_float(value):
    if value is None or isinstance(value, bool):
        return None

    try:
        number = float(value)

    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    return number


def to_int(value):
    number = to_float(value)

    if number is None:
        return None

    return int(number)


def first_value(mapping, keys):
    if not isinstance(mapping, dict):
        return None

    for key in keys:
        value = mapping.get(key)

        if value not in (None, ""):
            return value

    return None


def boat_beforeinfo(boat):
    info = boat.get("beforeinfo")

    if isinstance(info, dict):
        return info

    return {}


def get_exhibition_course(boat):
    info = boat_beforeinfo(boat)

    value = first_value(
        info,
        (
            "exhibition_course",
            "course",
            "tenji_course",
            "display_course",
        ),
    )

    if value in (None, ""):
        value = first_value(
            boat,
            (
                "exhibition_course",
                "tenji_course",
            ),
        )

    course = to_int(value)

    if course in {1, 2, 3, 4, 5, 6}:
        return course

    return None


def get_exhibition_time(boat):
    info = boat_beforeinfo(boat)

    value = first_value(
        info,
        (
            "exhibition_time",
            "tenji_time",
            "display_time",
        ),
    )

    if value in (None, ""):
        value = first_value(
            boat,
            (
                "exhibition_time",
                "tenji_time",
            ),
        )

    number = to_float(value)

    if number is None:
        return None

    if 5.0 <= number <= 10.0:
        return number

    return None


def parse_exhibition_st(value):
    raw = text(value).upper().replace(" ", "")

    if not raw:
        return None

    if raw.startswith("L"):
        return None

    if raw.startswith("F"):
        raw = raw[1:]

        if raw.startswith("."):
            raw = "0" + raw

        try:
            return -abs(float(raw))

        except ValueError:
            return None

    if raw.startswith("."):
        raw = "0" + raw

    try:
        number = float(raw)

    except ValueError:
        return None

    if -0.30 <= number <= 1.00:
        return number

    return None


def get_exhibition_st(boat):
    info = boat_beforeinfo(boat)

    value = first_value(
        info,
        (
            "exhibition_st",
            "tenji_st",
            "display_st",
            "st",
        ),
    )

    if value in (None, ""):
        value = first_value(
            boat,
            (
                "exhibition_st",
                "tenji_st",
            ),
        )

    return parse_exhibition_st(value)


def get_tilt(boat):
    info = boat_beforeinfo(boat)

    value = first_value(
        info,
        (
            "tilt",
            "tilt_angle",
        ),
    )

    if value in (None, ""):
        value = first_value(
            boat,
            (
                "tilt",
                "tilt_angle",
            ),
        )

    return to_float(value)


def parse_now(value):
    if not value:
        return datetime.now(JST)

    raw = value.strip().replace(
        "Z",
        "+00:00",
    )

    dt = datetime.fromisoformat(raw)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)

    return dt.astimezone(JST)


def parse_deadline(
    target_date,
    race,
):
    value = first_value(
        race,
        (
            "deadline",
            "deadline_time",
            "close_time",
            "cutoff_time",
        ),
    )

    if value in (None, ""):
        return None

    raw = text(value)

    try:
        dt = datetime.fromisoformat(
            raw.replace(
                "Z",
                "+00:00",
            )
        )

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)

        return dt.astimezone(JST)

    except ValueError:
        pass

    base_date = datetime.strptime(
        target_date,
        "%Y%m%d",
    ).date()

    for fmt in (
        "%H:%M:%S",
        "%H:%M",
        "%H%M",
    ):
        try:
            t = datetime.strptime(
                raw,
                fmt,
            ).time()

            return datetime.combine(
                base_date,
                t,
                tzinfo=JST,
            )

        except ValueError:
            pass

    for fmt in (
        "%Y%m%d%H%M",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
    ):
        try:
            dt = datetime.strptime(
                raw,
                fmt,
            )

            return dt.replace(
                tzinfo=JST
            )

        except ValueError:
            pass

    return None


def validate_no_current_results(payload):
    violations = []

    races = payload.get("races")

    if not isinstance(races, list):
        return [
            "racesがlistではありません"
        ]

    for race in races:
        race_id = text(
            race.get("race_id")
        )

        boats = race.get("boats")

        if not isinstance(boats, list):
            violations.append(
                f"{race_id}: boats不正"
            )

            continue

        for boat in boats:
            lane = boat.get("boat")

            found = (
                FORBIDDEN_CURRENT_RESULT_KEYS
                & set(boat.keys())
            )

            for key in found:
                violations.append(
                    f"{race_id} "
                    f"{lane}号艇: "
                    f"当日結果キー {key} を検出"
                )

    return violations


def rank_scores(
    values,
    lower_better=True,
):
    valid = {
        lane: value
        for lane, value in values.items()
        if value is not None
    }

    if not valid:
        return {}

    unique = sorted(
        set(valid.values()),
        reverse=not lower_better,
    )

    if len(unique) == 1:
        return {
            lane: 0.5
            for lane in valid
        }

    result = {}

    for lane, value in valid.items():
        pos = unique.index(value)

        result[lane] = (
            1.0
            - (
                pos
                / (
                    len(unique)
                    - 1
                )
            )
        )

    return result


def racer_course_score(boat):
    history = (
        boat.get("history")
        or {}
    )

    block = (
        history.get("racer_course")
        or {}
    )

    features = block.get(
        "features"
    )

    summary, source = (
        morning.select_window(
            features,
            minimum_short_starts=2,
        )
    )

    score = morning.performance_score(
        summary
    )

    return (
        score,
        source,
        morning.summary_starts(
            summary
        ),
    )


def component(
    name,
    raw,
    weight,
    source,
):
    if raw is None:
        return {
            "name": name,
            "available": False,
            "raw_score_0_1": None,
            "weight": weight,
            "weighted_points": 0.0,
            "source": source,
        }

    value = morning.clamp(
        float(raw)
    )

    return {
        "name": name,
        "available": True,
        "raw_score_0_1": round(
            value,
            6,
        ),
        "weight": weight,
        "weighted_points": round(
            value * weight,
            4,
        ),
        "source": source,
    }


def score_race(race):
    boats = race.get("boats")

    if (
        not isinstance(boats, list)
        or len(boats) != 6
    ):
        raise RuntimeError(
            "6艇ではないレースがあります: "
            f"{race.get('race_id')}"
        )

    raw_by_lane = {}

    time_values = {}

    st_values = {}

    for boat in boats:
        lane = to_int(
            boat.get("boat")
        )

        if lane not in {
            1,
            2,
            3,
            4,
            5,
            6,
        }:
            raise RuntimeError(
                "艇番異常: "
                f"{race.get('race_id')} "
                f"{boat.get('boat')}"
            )

        morning_row = (
            morning.score_boat(
                boat
            )
        )

        course = (
            get_exhibition_course(
                boat
            )
        )

        exhibition_time = (
            get_exhibition_time(
                boat
            )
        )

        exhibition_st = (
            get_exhibition_st(
                boat
            )
        )

        tilt = get_tilt(
            boat
        )

        (
            course_hist_score,
            course_hist_source,
            course_hist_starts,
        ) = racer_course_score(
            boat
        )

        raw_by_lane[lane] = {
            "morning": morning_row,
            "course": course,
            "exhibition_time": (
                exhibition_time
            ),
            "exhibition_st": (
                exhibition_st
            ),
            "tilt": tilt,
            "course_hist_score": (
                course_hist_score
            ),
            "course_hist_source": (
                course_hist_source
            ),
            "course_hist_starts": (
                course_hist_starts
            ),
        }

        if exhibition_time is not None:
            time_values[
                lane
            ] = exhibition_time

        if exhibition_st is not None:
            st_values[
                lane
            ] = max(
                exhibition_st,
                0.0,
            )

    time_rank = rank_scores(
        time_values,
        lower_better=True,
    )

    st_rank = rank_scores(
        st_values,
        lower_better=True,
    )

    scored = []

    for lane in sorted(
        raw_by_lane
    ):
        raw = raw_by_lane[
            lane
        ]

        course = raw[
            "course"
        ]

        course_prior = (
            morning.FRAME_PRIOR.get(
                course
            )
            if course is not None
            else None
        )

        components = {
            "morning_base": component(
                "morning_base",
                raw["morning"]["score"]
                / 100.0,
                LIVE_WEIGHTS[
                    "morning_base"
                ],
                "朝予測と同じ事前情報・履歴評価",
            ),

            "exhibition_course": component(
                "exhibition_course",
                course_prior,
                LIVE_WEIGHTS[
                    "exhibition_course"
                ],
                (
                    f"展示進入コース={course}"
                    if course is not None
                    else "展示進入未取得"
                ),
            ),

            "racer_course": component(
                "racer_course",
                raw[
                    "course_hist_score"
                ],
                LIVE_WEIGHTS[
                    "racer_course"
                ],
                (
                    "選手×実展示コース履歴 "
                    f"source="
                    f"{raw['course_hist_source']} "
                    f"starts="
                    f"{raw['course_hist_starts']}"
                ),
            ),

            "exhibition_time": component(
                "exhibition_time",
                time_rank.get(
                    lane
                ),
                LIVE_WEIGHTS[
                    "exhibition_time"
                ],
                (
                    "展示タイム="
                    f"{raw['exhibition_time']}"
                ),
            ),

            "exhibition_st": component(
                "exhibition_st",
                st_rank.get(
                    lane
                ),
                LIVE_WEIGHTS[
                    "exhibition_st"
                ],
                (
                    "展示ST="
                    f"{raw['exhibition_st']}"
                ),
            ),
        }

        available_weight = sum(
            item["weight"]
            for item
            in components.values()
            if item["available"]
        )

        weighted_points = sum(
            item[
                "weighted_points"
            ]
            for item
            in components.values()
            if item["available"]
        )

        score = (
            (
                weighted_points
                / available_weight
            )
            * 100.0
            if available_weight > 0
            else 0.0
        )

        coverage = (
            available_weight
            / sum(
                LIVE_WEIGHTS.values()
            )
            * 100.0
        )

        morning_row = raw[
            "morning"
        ]

        scored.append(
            {
                "boat": lane,

                "registration_no": (
                    morning_row.get(
                        "registration_no"
                    )
                ),

                "racer_name": (
                    morning_row.get(
                        "racer_name"
                    )
                ),

                "grade": (
                    morning_row.get(
                        "grade"
                    )
                ),

                "motor_no": (
                    morning_row.get(
                        "motor_no"
                    )
                ),

                "boat_no": (
                    morning_row.get(
                        "boat_no"
                    )
                ),

                "score": round(
                    score,
                    2,
                ),

                "morning_score_reference": (
                    morning_row.get(
                        "score"
                    )
                ),

                "data_coverage_pct": round(
                    coverage,
                    1,
                ),

                "exhibition_course": (
                    course
                ),

                "exhibition_time": (
                    raw[
                        "exhibition_time"
                    ]
                ),

                "exhibition_st": (
                    raw[
                        "exhibition_st"
                    ]
                ),

                "tilt": (
                    raw[
                        "tilt"
                    ]
                ),

                "components": (
                    components
                ),
            }
        )

    scored.sort(
        key=lambda row: (
            -row["score"],
            row["boat"],
        )
    )

    for rank, row in enumerate(
        scored,
        start=1,
    ):
        row[
            "rank"
        ] = rank

    return scored


def race_context(race):
    keys = (
        "weather",
        "weather_code",
        "air_temperature",
        "temperature",
        "water_temperature",
        "wind_speed",
        "wind_direction",
        "wave_height",
    )

    result = {}

    for key in keys:
        value = race.get(key)

        if value not in (
            None,
            "",
        ):
            result[
                key
            ] = value

    nested = race.get(
        "beforeinfo"
    )

    if isinstance(
        nested,
        dict,
    ):
        for key in keys:
            value = nested.get(
                key
            )

            if (
                value not in (
                    None,
                    "",
                )
                and key not in result
            ):
                result[
                    key
                ] = value

    return result


def write_csv(
    path,
    rows,
):
    fields = [
        "target_date",
        "generated_at",
        "venue_code",
        "venue_name",
        "race",
        "race_id",
        "deadline",
        "rank",
        "boat",
        "registration_no",
        "racer_name",
        "grade",
        "motor_no",
        "boat_no",
        "score",
        "morning_score_reference",
        "data_coverage_pct",
        "exhibition_course",
        "exhibition_time",
        "exhibition_st",
        "tilt",
    ]

    with Path(path).open(
        "w",
        encoding="utf-8",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fields,
        )

        writer.writeheader()

        writer.writerows(
            rows
        )


def load_existing_final(
    target_date,
):
    path = (
        Path("predictions")
        / target_date[:4]
        / target_date[4:6]
        / target_date[6:8]
        / "live"
        / (
            "live_predictions_final_"
            f"{target_date}.json"
        )
    )

    if not path.exists():
        return {}

    try:
        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception:
        return {}

    races = data.get(
        "races"
    )

    if not isinstance(
        races,
        list,
    ):
        return {}

    return {
        text(
            race.get(
                "race_id"
            )
        ): race
        for race
        in races
        if text(
            race.get(
                "race_id"
            )
        )
    }


def main():
    args = parse_args()

    target_date = args.date

    try:
        datetime.strptime(
            target_date,
            "%Y%m%d",
        )

    except ValueError:
        print(
            "ERROR: --dateはYYYYMMDD形式です",
            file=sys.stderr,
        )

        return 1

    now = parse_now(
        args.now
    )

    output_dir = Path(
        args.output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    input_path = (
        Path(args.input)
        if args.input
        else (
            output_dir
            / (
                "prediction_input_enriched_live_"
                f"{target_date}.json"
            )
        )
    )

    current_json = (
        output_dir
        / (
            "live_predictions_current_"
            f"{target_date}.json"
        )
    )

    current_csv = (
        output_dir
        / (
            "live_predictions_current_"
            f"{target_date}.csv"
        )
    )

    validation_json = (
        output_dir
        / (
            "live_predictions_validation_current_"
            f"{target_date}.json"
        )
    )

    final_json = (
        output_dir
        / (
            "live_predictions_final_"
            f"{target_date}.json"
        )
    )

    final_csv = (
        output_dir
        / (
            "live_predictions_final_"
            f"{target_date}.csv"
        )
    )

    if not input_path.exists():
        print(
            "ERROR: 入力ファイルがありません: "
            f"{input_path}",
            file=sys.stderr,
        )

        return 1

    try:
        payload = json.loads(
            input_path.read_text(
                encoding="utf-8"
            )
        )

        if text(
            payload.get(
                "target_date"
            )
        ) != target_date:
            raise RuntimeError(
                "target_date不一致"
            )

        if text(
            payload.get(
                "prediction_stage"
            )
        ) != "live":
            raise RuntimeError(
                "live用prediction_inputではありません"
            )

        history_manifest = (
            payload.get(
                "history_feature_manifest"
            )
            or {}
        )

        history_max_date = text(
            history_manifest.get(
                "history_max_date"
            )
        )

        if (
            history_max_date
            and history_max_date
            >= target_date
        ):
            raise RuntimeError(
                "結果漏洩の可能性があります"
            )

        violations = (
            validate_no_current_results(
                payload
            )
        )

        if violations:
            raise RuntimeError(
                "当日結果混入: "
                f"{violations[:5]}"
            )

        races = payload.get(
            "races"
        )

        if not isinstance(
            races,
            list,
        ):
            raise RuntimeError(
                "racesが不正です"
            )

        predicted_races = []

        csv_rows = []

        skipped_after_deadline = []

        skipped_no_live_data = []

        for race in races:
            race_id = text(
                race.get(
                    "race_id"
                )
            )

            boats = race.get(
                "boats"
            )

            if (
                not isinstance(
                    boats,
                    list,
                )
                or len(
                    boats
                ) != 6
            ):
                continue

            deadline = (
                parse_deadline(
                    target_date,
                    race,
                )
            )

            if (
                deadline is not None
                and now >= deadline
            ):
                skipped_after_deadline.append(
                    race_id
                )

                continue

            time_count = sum(
                get_exhibition_time(
                    boat
                )
                is not None
                for boat
                in boats
            )

            course_count = sum(
                get_exhibition_course(
                    boat
                )
                is not None
                for boat
                in boats
            )

            st_count = sum(
                get_exhibition_st(
                    boat
                )
                is not None
                for boat
                in boats
            )

            if (
                time_count < 5
                or course_count < 5
            ):
                skipped_no_live_data.append(
                    race_id
                )

                continue

            scored = score_race(
                race
            )

            predicted_race = {
                "race_id": race_id,

                "date": (
                    race.get(
                        "date"
                    )
                ),

                "venue_code": (
                    race.get(
                        "venue_code"
                    )
                ),

                "venue_name": (
                    race.get(
                        "venue_name"
                    )
                ),

                "race": (
                    race.get(
                        "race"
                    )
                ),

                "race_name": (
                    race.get(
                        "race_name"
                    )
                ),

                "deadline": (
                    race.get(
                        "deadline"
                    )
                ),

                "generated_at": (
                    now.isoformat()
                ),

                "live_data_counts": {
                    "exhibition_time": (
                        time_count
                    ),

                    "exhibition_course": (
                        course_count
                    ),

                    "exhibition_st": (
                        st_count
                    ),
                },

                "weather_water": (
                    race_context(
                        race
                    )
                ),

                "live_order": [
                    row[
                        "boat"
                    ]
                    for row
                    in scored
                ],

                "top3_boats": [
                    row[
                        "boat"
                    ]
                    for row
                    in scored[:3]
                ],

                "strength": (
                    morning.prediction_strength(
                        scored
                    )
                ),

                "boats": (
                    scored
                ),
            }

            predicted_races.append(
                predicted_race
            )

            for row in scored:
                csv_rows.append(
                    {
                        "target_date": (
                            target_date
                        ),

                        "generated_at": (
                            now.isoformat()
                        ),

                        "venue_code": (
                            race.get(
                                "venue_code"
                            )
                        ),

                        "venue_name": (
                            race.get(
                                "venue_name"
                            )
                        ),

                        "race": (
                            race.get(
                                "race"
                            )
                        ),

                        "race_id": (
                            race_id
                        ),

                        "deadline": (
                            race.get(
                                "deadline"
                            )
                        ),

                        "rank": (
                            row[
                                "rank"
                            ]
                        ),

                        "boat": (
                            row[
                                "boat"
                            ]
                        ),

                        "registration_no": (
                            row[
                                "registration_no"
                            ]
                        ),

                        "racer_name": (
                            row[
                                "racer_name"
                            ]
                        ),

                        "grade": (
                            row[
                                "grade"
                            ]
                        ),

                        "motor_no": (
                            row[
                                "motor_no"
                            ]
                        ),

                        "boat_no": (
                            row[
                                "boat_no"
                            ]
                        ),

                        "score": (
                            row[
                                "score"
                            ]
                        ),

                        "morning_score_reference": (
                            row[
                                "morning_score_reference"
                            ]
                        ),

                        "data_coverage_pct": (
                            row[
                                "data_coverage_pct"
                            ]
                        ),

                        "exhibition_course": (
                            row[
                                "exhibition_course"
                            ]
                        ),

                        "exhibition_time": (
                            row[
                                "exhibition_time"
                            ]
                        ),

                        "exhibition_st": (
                            row[
                                "exhibition_st"
                            ]
                        ),

                        "tilt": (
                            row[
                                "tilt"
                            ]
                        ),
                    }
                )

        status = (
            "PASS"
            if predicted_races
            else "NO_DATA"
        )

        validation = {
            "status": status,

            "model_version": (
                MODEL_VERSION
            ),

            "target_date": (
                target_date
            ),

            "generated_at": (
                now.isoformat()
            ),

            "input_race_count": (
                len(
                    races
                )
            ),

            "prediction_race_count": (
                len(
                    predicted_races
                )
            ),

            "prediction_boat_count": (
                len(
                    csv_rows
                )
            ),

            "skipped_after_deadline": (
                skipped_after_deadline
            ),

            "skipped_no_live_data": (
                skipped_no_live_data
            ),

            "history_max_date": (
                history_max_date
            ),

            "current_day_result_leakage": 0,

            "errors": [],
        }

        validation_json.write_text(
            json.dumps(
                validation,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        if not predicted_races:
            print(
                "========================================"
            )

            print(
                "直前予測: 現在対象レースなし"
            )

            print(
                "========================================"
            )

            print(
                "入力候補:",
                len(
                    races
                ),
            )

            print(
                "処理結果: NO_DATA"
            )

            return 0

        snapshot = {
            "schema_version": "1.0",

            "model_version": (
                MODEL_VERSION
            ),

            "target_date": (
                target_date
            ),

            "prediction_stage": "live",

            "generated_at": (
                now.isoformat()
            ),

            "weights": (
                LIVE_WEIGHTS
            ),

            "race_count": (
                len(
                    predicted_races
                )
            ),

            "boat_count": (
                len(
                    csv_rows
                )
            ),

            "races": (
                predicted_races
            ),
        }

        current_json.write_text(
            json.dumps(
                snapshot,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        write_csv(
            current_csv,
            csv_rows,
        )

        final_map = (
            load_existing_final(
                target_date
            )
        )

        for race in predicted_races:
            final_map[
                text(
                    race.get(
                        "race_id"
                    )
                )
            ] = race

        final_races = sorted(
            final_map.values(),
            key=lambda race: (
                text(
                    race.get(
                        "venue_code"
                    )
                ),
                to_int(
                    race.get(
                        "race"
                    )
                )
                or 0,
            ),
        )

        final_rows = []

        for race in final_races:
            for row in race.get(
                "boats",
                [],
            ):
                final_rows.append(
                    {
                        "target_date": (
                            target_date
                        ),

                        "generated_at": (
                            race.get(
                                "generated_at"
                            )
                        ),

                        "venue_code": (
                            race.get(
                                "venue_code"
                            )
                        ),

                        "venue_name": (
                            race.get(
                                "venue_name"
                            )
                        ),

                        "race": (
                            race.get(
                                "race"
                            )
                        ),

                        "race_id": (
                            race.get(
                                "race_id"
                            )
                        ),

                        "deadline": (
                            race.get(
                                "deadline"
                            )
                        ),

                        "rank": (
                            row.get(
                                "rank"
                            )
                        ),

                        "boat": (
                            row.get(
                                "boat"
                            )
                        ),

                        "registration_no": (
                            row.get(
                                "registration_no"
                            )
                        ),

                        "racer_name": (
                            row.get(
                                "racer_name"
                            )
                        ),

                        "grade": (
                            row.get(
                                "grade"
                            )
                        ),

                        "motor_no": (
                            row.get(
                                "motor_no"
                            )
                        ),

                        "boat_no": (
                            row.get(
                                "boat_no"
                            )
                        ),

                        "score": (
                            row.get(
                                "score"
                            )
                        ),

                        "morning_score_reference": (
                            row.get(
                                "morning_score_reference"
                            )
                        ),

                        "data_coverage_pct": (
                            row.get(
                                "data_coverage_pct"
                            )
                        ),

                        "exhibition_course": (
                            row.get(
                                "exhibition_course"
                            )
                        ),

                        "exhibition_time": (
                            row.get(
                                "exhibition_time"
                            )
                        ),

                        "exhibition_st": (
                            row.get(
                                "exhibition_st"
                            )
                        ),

                        "tilt": (
                            row.get(
                                "tilt"
                            )
                        ),
                    }
                )

        final_payload = {
            "schema_version": "1.0",

            "model_version": (
                MODEL_VERSION
            ),

            "target_date": (
                target_date
            ),

            "prediction_stage": (
                "live_final"
            ),

            "updated_at": (
                now.isoformat()
            ),

            "race_count": (
                len(
                    final_races
                )
            ),

            "boat_count": (
                len(
                    final_rows
                )
            ),

            "selection_rule": (
                "同一race_idは締切前に取得した"
                "最新の直前予測で更新"
            ),

            "races": (
                final_races
            ),
        }

        final_json.write_text(
            json.dumps(
                final_payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        write_csv(
            final_csv,
            final_rows,
        )

        print(
            "========================================"
        )

        print(
            "直前予測生成"
        )

        print(
            "========================================"
        )

        print(
            "モデル:",
            MODEL_VERSION,
        )

        print(
            "今回予測:",
            f"{len(predicted_races)}R",
        )

        print(
            "最終予測累積:",
            f"{len(final_races)}R",
        )

        print(
            "履歴最終日:",
            history_max_date,
        )

        print(
            "当日結果漏洩: 0"
        )

        print(
            "直前予測生成: PASS"
        )

        return 0

    except Exception as exc:
        failure = {
            "status": "FAIL",

            "target_date": (
                target_date
            ),

            "error": (
                str(exc)
            ),

            "generated_at": (
                now.isoformat()
            ),
        }

        validation_json.write_text(
            json.dumps(
                failure,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    sys.exit(
        main()
    )