from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


JST = timezone(timedelta(hours=9))

MODEL_VERSION = "morning_heuristic_v1"

# ---------------------------------------------------------
# 初期モデルの重み
#
# 合計100。
# 10月1日以降の予測→実結果を蓄積した後、
# バックテストで調整することを前提とする。
# ---------------------------------------------------------

WEIGHTS = {
    "frame": 28.0,
    "official_racer": 18.0,
    "recent_racer": 22.0,
    "racer_venue": 8.0,
    "motor": 14.0,
    "boat_machine": 5.0,
    "grade": 5.0,
}


# ---------------------------------------------------------
# 朝段階の枠番評価
#
# これは「実コース」ではない。
# 未確定の進入コースを推測して使用しない。
# ---------------------------------------------------------

FRAME_PRIOR = {
    1: 1.00,
    2: 0.72,
    3: 0.62,
    4: 0.58,
    5: 0.46,
    6: 0.38,
}


GRADE_PRIOR = {
    "A1": 1.00,
    "A2": 0.78,
    "B1": 0.48,
    "B2": 0.30,
}


# ---------------------------------------------------------
# 当日結果の混入防止
# ---------------------------------------------------------

FORBIDDEN_CURRENT_RESULT_KEYS = {
    "finish",
    "result",
    "race_time",
    "actual_st",
    "actual_course",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "履歴結合済み当日データから"
            "朝予測スコアを生成"
        )
    )

    parser.add_argument(
        "--date",
        required=True,
        help="対象日 YYYYMMDD",
    )

    parser.add_argument(
        "--input",
        default=None,
        help=(
            "入力JSON。省略時は "
            "data/prediction_input_enriched_"
            "morning_YYYYMMDD.json"
        ),
    )

    parser.add_argument(
        "--output-dir",
        default="data",
    )

    return parser.parse_args()


def text(value):
    if value is None:
        return ""

    return str(value).strip()


def to_float(value):
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        number = float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None

    if not math.isfinite(
        number
    ):
        return None

    return number


def to_int(value):
    number = to_float(
        value
    )

    if number is None:
        return None

    return int(
        number
    )


def clamp(
    value,
    low=0.0,
    high=1.0,
):
    return max(
        low,
        min(
            high,
            value,
        ),
    )


def rate01(value):
    number = to_float(
        value
    )

    if number is None:
        return None

    return clamp(
        number
    )


def percent01(value):
    number = to_float(
        value
    )

    if number is None:
        return None

    return clamp(
        number / 100.0
    )


def winrate10(value):
    number = to_float(
        value
    )

    if number is None:
        return None

    return clamp(
        number / 10.0
    )


def finish_score(value):
    number = to_float(
        value
    )

    if number is None:
        return None

    # 1着=1.0
    # 6着付近=低評価
    return clamp(
        (
            7.0
            - number
        )
        / 6.0
    )


def st_score(value):
    number = to_float(
        value
    )

    if number is None:
        return None

    # STは小さいほど高評価。
    # 0.10前後を高く、
    # 0.30以降を低く評価。
    return clamp(
        1.0
        - (
            number
            / 0.35
        )
    )


def weighted_mean(items):
    numerator = 0.0
    denominator = 0.0

    for value, weight in items:

        if value is None:
            continue

        numerator += (
            float(value)
            * float(weight)
        )

        denominator += float(
            weight
        )

    if denominator <= 0:
        return None

    return (
        numerator
        / denominator
    )


def summary_starts(summary):
    if not isinstance(
        summary,
        dict,
    ):
        return 0

    value = to_int(
        summary.get(
            "starts"
        )
    )

    if value is None:
        return 0

    return value


def performance_score(summary):
    if not isinstance(
        summary,
        dict,
    ):
        return None

    if summary_starts(
        summary
    ) <= 0:
        return None

    return weighted_mean(
        [
            (
                rate01(
                    summary.get(
                        "win_rate"
                    )
                ),
                0.25,
            ),
            (
                rate01(
                    summary.get(
                        "top2_rate"
                    )
                ),
                0.25,
            ),
            (
                rate01(
                    summary.get(
                        "top3_rate"
                    )
                ),
                0.20,
            ),
            (
                finish_score(
                    summary.get(
                        "avg_finish"
                    )
                ),
                0.20,
            ),
            (
                st_score(
                    summary.get(
                        "avg_st"
                    )
                ),
                0.10,
            ),
        ]
    )


def select_window(
    feature_block,
    short_name="d30",
    long_name="d90",
    minimum_short_starts=3,
):
    if not isinstance(
        feature_block,
        dict,
    ):
        return (
            None,
            "none",
        )

    short = feature_block.get(
        short_name
    )

    long = feature_block.get(
        long_name
    )

    # 30日に十分なサンプルがあれば30日優先
    if (
        isinstance(
            short,
            dict,
        )
        and summary_starts(
            short
        )
        >= minimum_short_starts
    ):
        return (
            short,
            short_name,
        )

    # 30日不足なら90日へフォールバック
    if (
        isinstance(
            long,
            dict,
        )
        and summary_starts(
            long
        )
        > 0
    ):
        return (
            long,
            long_name,
        )

    # 90日もなければ、
    # 少数サンプルでも30日を最後に使用
    if (
        isinstance(
            short,
            dict,
        )
        and summary_starts(
            short
        )
        > 0
    ):
        return (
            short,
            short_name,
        )

    return (
        None,
        "none",
    )


def official_racer_score(
    official_stats,
):
    if not isinstance(
        official_stats,
        dict,
    ):
        return None

    return weighted_mean(
        [
            (
                winrate10(
                    official_stats.get(
                        "national_win_rate"
                    )
                ),
                0.35,
            ),
            (
                winrate10(
                    official_stats.get(
                        "local_win_rate"
                    )
                ),
                0.30,
            ),
            (
                percent01(
                    official_stats.get(
                        "national_top2_rate"
                    )
                ),
                0.20,
            ),
            (
                percent01(
                    official_stats.get(
                        "local_top2_rate"
                    )
                ),
                0.15,
            ),
        ]
    )


def recent_racer_score(
    racer_features,
):
    if not isinstance(
        racer_features,
        dict,
    ):
        return (
            None,
            {},
        )

    last5 = racer_features.get(
        "last5"
    )

    last10 = racer_features.get(
        "last10"
    )

    d30 = racer_features.get(
        "d30"
    )

    d90 = racer_features.get(
        "d90"
    )

    score = weighted_mean(
        [
            (
                performance_score(
                    last5
                ),
                0.25,
            ),
            (
                performance_score(
                    last10
                ),
                0.20,
            ),
            (
                performance_score(
                    d30
                ),
                0.35,
            ),
            (
                performance_score(
                    d90
                ),
                0.20,
            ),
        ]
    )

    sample_info = {
        "last5_starts": (
            summary_starts(
                last5
            )
        ),

        "last10_starts": (
            summary_starts(
                last10
            )
        ),

        "d30_starts": (
            summary_starts(
                d30
            )
        ),

        "d90_starts": (
            summary_starts(
                d90
            )
        ),
    }

    return (
        score,
        sample_info,
    )


def trend_adjustment(
    racer_features,
):
    if not isinstance(
        racer_features,
        dict,
    ):
        return 0.0

    trend = racer_features.get(
        "trend_30v90"
    )

    if not isinstance(
        trend,
        dict,
    ):
        return 0.0

    values = []

    for key, weight in (
        (
            "win_rate_30v90",
            0.35,
        ),
        (
            "top2_rate_30v90",
            0.35,
        ),
        (
            "top3_rate_30v90",
            0.30,
        ),
    ):

        number = to_float(
            trend.get(
                key
            )
        )

        if number is not None:

            values.append(
                (
                    number,
                    weight,
                )
            )

    rate_trend = weighted_mean(
        values
    )

    finish_trend = to_float(
        trend.get(
            "avg_finish_30v90"
        )
    )

    st_trend = to_float(
        trend.get(
            "avg_st_30v90"
        )
    )

    adjustment = 0.0

    if rate_trend is not None:

        adjustment += (
            clamp(
                rate_trend,
                -0.30,
                0.30,
            )
            / 0.30
        ) * 2.0

    # 平均着順は小さくなれば改善
    if finish_trend is not None:

        adjustment += (
            clamp(
                -finish_trend,
                -1.5,
                1.5,
            )
            / 1.5
        ) * 0.7

    # 平均STも小さくなれば改善
    if st_trend is not None:

        adjustment += (
            clamp(
                -st_trend,
                -0.08,
                0.08,
            )
            / 0.08
        ) * 0.3

    return clamp(
        adjustment,
        -3.0,
        3.0,
    )


def discipline_penalty(
    racer_features,
):
    if not isinstance(
        racer_features,
        dict,
    ):
        return 0.0

    d90 = racer_features.get(
        "d90"
    )

    if not isinstance(
        d90,
        dict,
    ):
        return 0.0

    f_rate = (
        rate01(
            d90.get(
                "f_rate"
            )
        )
        or 0.0
    )

    l_rate = (
        rate01(
            d90.get(
                "l_rate"
            )
        )
        or 0.0
    )

    return min(
        6.0,
        (
            f_rate
            * 30.0
        )
        + (
            l_rate
            * 15.0
        ),
    )


def equipment_score(
    official_top2,
    history_features,
):
    (
        history_summary,
        source,
    ) = select_window(
        history_features,
        minimum_short_starts=2,
    )

    score = weighted_mean(
        [
            (
                percent01(
                    official_top2
                ),
                0.45,
            ),
            (
                performance_score(
                    history_summary
                ),
                0.55,
            ),
        ]
    )

    return (
        score,
        source,
        summary_starts(
            history_summary
        ),
    )


def grade_score(
    grade,
):
    return GRADE_PRIOR.get(
        text(
            grade
        ).upper()
    )


def component_entry(
    name,
    value,
    weight,
    source,
):
    if value is None:

        return {
            "name": name,
            "available": False,
            "raw_score_0_1": None,
            "weight": weight,
            "weighted_points": 0.0,
            "source": source,
        }

    value = clamp(
        float(
            value
        )
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
            value
            * weight,
            4,
        ),

        "source": source,
    }


def score_boat(
    boat,
):
    lane = to_int(
        boat.get(
            "boat"
        )
    )

    racer = (
        boat.get(
            "racer"
        )
        or {}
    )

    official_stats = (
        boat.get(
            "official_stats"
        )
        or {}
    )

    motor = (
        boat.get(
            "motor"
        )
        or {}
    )

    boat_machine = (
        boat.get(
            "boat_machine"
        )
        or {}
    )

    history = (
        boat.get(
            "history"
        )
        or {}
    )

    racer_overall = (
        history.get(
            "racer_overall"
        )
        or {}
    )

    racer_features = (
        racer_overall.get(
            "features"
        )
    )

    racer_venue = (
        history.get(
            "racer_venue"
        )
        or {}
    )

    racer_venue_features = (
        racer_venue.get(
            "features"
        )
    )

    motor_history = (
        history.get(
            "motor"
        )
        or {}
    )

    motor_features = (
        motor_history.get(
            "features"
        )
    )

    boat_history = (
        history.get(
            "boat_machine"
        )
        or {}
    )

    boat_features = (
        boat_history.get(
            "features"
        )
    )

    frame_value = (
        FRAME_PRIOR.get(
            lane
        )
    )

    official_value = (
        official_racer_score(
            official_stats
        )
    )

    (
        recent_value,
        recent_samples,
    ) = recent_racer_score(
        racer_features
    )

    (
        venue_summary,
        venue_source,
    ) = select_window(
        racer_venue_features,
        minimum_short_starts=2,
    )

    venue_value = (
        performance_score(
            venue_summary
        )
    )

    (
        motor_value,
        motor_source,
        motor_starts,
    ) = equipment_score(
        motor.get(
            "official_top2_rate"
        ),
        motor_features,
    )

    (
        boat_value,
        boat_source,
        boat_starts,
    ) = equipment_score(
        boat_machine.get(
            "official_top2_rate"
        ),
        boat_features,
    )

    grade_value = (
        grade_score(
            racer.get(
                "grade"
            )
        )
    )

    components = {
        "frame": component_entry(
            "frame",
            frame_value,
            WEIGHTS[
                "frame"
            ],
            (
                "枠番のみ。"
                "未確定の進入コースは不使用"
            ),
        ),

        "official_racer": component_entry(
            "official_racer",
            official_value,
            WEIGHTS[
                "official_racer"
            ],
            (
                "当日番組の全国・"
                "当地勝率/2連率"
            ),
        ),

        "recent_racer": component_entry(
            "recent_racer",
            recent_value,
            WEIGHTS[
                "recent_racer"
            ],
            (
                "直近5走・10走・"
                "30日・90日履歴 "
                f"{recent_samples}"
            ),
        ),

        "racer_venue": component_entry(
            "racer_venue",
            venue_value,
            WEIGHTS[
                "racer_venue"
            ],
            (
                "選手×競艇場履歴 "
                f"source={venue_source} "
                f"starts="
                f"{summary_starts(venue_summary)}"
            ),
        ),

        "motor": component_entry(
            "motor",
            motor_value,
            WEIGHTS[
                "motor"
            ],
            (
                "公式モーター2連率＋履歴 "
                f"source={motor_source} "
                f"starts={motor_starts}"
            ),
        ),

        "boat_machine": component_entry(
            "boat_machine",
            boat_value,
            WEIGHTS[
                "boat_machine"
            ],
            (
                "公式ボート2連率＋履歴 "
                f"source={boat_source} "
                f"starts={boat_starts}"
            ),
        ),

        "grade": component_entry(
            "grade",
            grade_value,
            WEIGHTS[
                "grade"
            ],
            "当日番組の級別",
        ),
    }

    available_weight = sum(
        item[
            "weight"
        ]
        for item
        in components.values()
        if item[
            "available"
        ]
    )

    weighted_points = sum(
        item[
            "weighted_points"
        ]
        for item
        in components.values()
        if item[
            "available"
        ]
    )

    if available_weight <= 0:
        base_score = 0.0

    else:
        # 欠損項目は0点扱いにせず、
        # 使用可能な項目の重みだけで再正規化。
        base_score = (
            weighted_points
            / available_weight
        ) * 100.0

    trend_points = (
        trend_adjustment(
            racer_features
        )
    )

    penalty = (
        discipline_penalty(
            racer_features
        )
    )

    final_score = clamp(
        (
            base_score
            + trend_points
            - penalty
        )
        / 100.0
    ) * 100.0

    coverage_pct = (
        available_weight
        / sum(
            WEIGHTS.values()
        )
        * 100.0
    )

    return {
        "boat": lane,

        "registration_no": (
            racer.get(
                "registration_no"
            )
        ),

        "racer_name": (
            racer.get(
                "name"
            )
        ),

        "grade": (
            racer.get(
                "grade"
            )
        ),

        "motor_no": (
            motor.get(
                "motor_no"
            )
        ),

        "boat_no": (
            boat_machine.get(
                "boat_no"
            )
        ),

        "score": round(
            final_score,
            2,
        ),

        "base_score": round(
            base_score,
            2,
        ),

        "trend_adjustment_points": round(
            trend_points,
            2,
        ),

        "f_l_penalty_points": round(
            penalty,
            2,
        ),

        "data_coverage_pct": round(
            coverage_pct,
            1,
        ),

        "components": (
            components
        ),

        "note": (
            "scoreは的中確率ではなく、"
            "朝時点の相対評価用スコア"
        ),
    }


def validate_current_day_no_results(
    payload,
):
    violations = []

    races = payload.get(
        "races"
    )

    if not isinstance(
        races,
        list,
    ):
        return [
            "racesがlistではありません"
        ]

    for race in races:

        race_id = text(
            race.get(
                "race_id"
            )
        )

        boats = race.get(
            "boats"
        )

        if not isinstance(
            boats,
            list,
        ):

            violations.append(
                f"{race_id}: boats不正"
            )

            continue

        for boat in boats:

            lane = boat.get(
                "boat"
            )

            found = (
                FORBIDDEN_CURRENT_RESULT_KEYS
                & set(
                    boat.keys()
                )
            )

            for key in found:

                violations.append(
                    f"{race_id} "
                    f"{lane}号艇: "
                    f"当日結果キー "
                    f"{key} を検出"
                )

    return violations


def prediction_strength(
    ranked,
):
    if len(
        ranked
    ) < 2:

        return {
            "top1_top2_gap": None,
            "top1_top3_gap": None,
        }

    top1 = ranked[
        0
    ][
        "score"
    ]

    top2 = ranked[
        1
    ][
        "score"
    ]

    top3 = (
        ranked[
            2
        ][
            "score"
        ]
        if len(
            ranked
        )
        >= 3
        else None
    )

    return {
        "top1_top2_gap": round(
            top1
            - top2,
            2,
        ),

        "top1_top3_gap": (
            round(
                top1
                - top3,
                2,
            )
            if top3 is not None
            else None
        ),
    }


def write_csv(
    path,
    rows,
):
    fieldnames = [
        "target_date",
        "venue_code",
        "venue_name",
        "race",
        "race_id",
        "rank",
        "boat",
        "registration_no",
        "racer_name",
        "grade",
        "motor_no",
        "boat_no",
        "score",
        "base_score",
        "trend_adjustment_points",
        "f_l_penalty_points",
        "data_coverage_pct",
    ]

    with Path(
        path
    ).open(
        "w",
        encoding="utf-8",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(
            rows
        )


def main():
    args = parse_args()

    target_date = (
        args.date
    )

    try:
        datetime.strptime(
            target_date,
            "%Y%m%d",
        )

    except ValueError:

        print(
            "ERROR: "
            "--dateはYYYYMMDD形式です",
            file=sys.stderr,
        )

        return 1

    output_dir = Path(
        args.output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    if args.input:

        input_path = Path(
            args.input
        )

    else:

        input_path = (
            output_dir
            / (
                "prediction_input_enriched_"
                "morning_"
                f"{target_date}.json"
            )
        )

    output_json = (
        output_dir
        / (
            f"morning_predictions_"
            f"{target_date}.json"
        )
    )

    output_csv = (
        output_dir
        / (
            f"morning_predictions_"
            f"{target_date}.csv"
        )
    )

    validation_json = (
        output_dir
        / (
            "morning_predictions_validation_"
            f"{target_date}.json"
        )
    )

    if not input_path.exists():

        print(
            "ERROR: "
            f"入力ファイルがありません: "
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
                "入力JSONのtarget_dateが"
                "指定日と一致しません"
            )

        if text(
            payload.get(
                "prediction_stage"
            )
        ) != "morning":

            raise RuntimeError(
                "朝予測以外の"
                "prediction_inputです"
            )

        history_manifest = (
            payload.get(
                "history_feature_manifest"
            )
            or {}
        )

        if text(
            history_manifest.get(
                "as_of_date"
            )
        ) != target_date:

            raise RuntimeError(
                "履歴特徴量のas_of_dateが"
                "対象日と一致しません"
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
                "結果漏洩の可能性があります: "
                f"history_max_date="
                f"{history_max_date}"
            )

        violations = (
            validate_current_day_no_results(
                payload
            )
        )

        if violations:

            raise RuntimeError(
                "当日結果データ混入を検出: "
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

        prediction_races = []

        csv_rows = []

        all_scores = []

        all_coverages = []

        for race in races:

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
                )
                != 6
            ):

                raise RuntimeError(
                    "6艇ではないレースがあります: "
                    f"{race.get('race_id')}"
                )

            scored = [
                score_boat(
                    boat
                )
                for boat in boats
            ]

            scored.sort(
                key=lambda row: (
                    -row[
                        "score"
                    ],
                    (
                        row[
                            "boat"
                        ]
                        if row[
                            "boat"
                        ]
                        is not None
                        else 99
                    ),
                )
            )

            for rank, row in enumerate(
                scored,
                start=1,
            ):

                row[
                    "rank"
                ] = rank

                all_scores.append(
                    row[
                        "score"
                    ]
                )

                all_coverages.append(
                    row[
                        "data_coverage_pct"
                    ]
                )

                csv_rows.append(
                    {
                        "target_date": (
                            target_date
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

                        "rank": (
                            rank
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

                        "base_score": (
                            row[
                                "base_score"
                            ]
                        ),

                        "trend_adjustment_points": (
                            row[
                                "trend_adjustment_points"
                            ]
                        ),

                        "f_l_penalty_points": (
                            row[
                                "f_l_penalty_points"
                            ]
                        ),

                        "data_coverage_pct": (
                            row[
                                "data_coverage_pct"
                            ]
                        ),
                    }
                )

            prediction_races.append(
                {
                    "race_id": (
                        race.get(
                            "race_id"
                        )
                    ),

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

                    "morning_order": [
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
                        in scored[
                            :3
                        ]
                    ],

                    "strength": (
                        prediction_strength(
                            scored
                        )
                    ),

                    "boats": (
                        scored
                    ),
                }
            )

        result = {
            "schema_version": "1.0",

            "model_version": (
                MODEL_VERSION
            ),

            "target_date": (
                target_date
            ),

            "prediction_stage": (
                "morning"
            ),

            "generated_at": (
                datetime.now(
                    JST
                ).isoformat()
            ),

            "score_note": (
                "scoreは的中確率ではなく、"
                "朝時点の特徴量を統合した"
                "相対評価スコア。"
                "未確定の進入コース・展示・"
                "当日結果は不使用。"
            ),

            "leakage_guard": {
                "history_max_date": (
                    history_max_date
                ),

                "current_day_result_keys_checked": (
                    sorted(
                        FORBIDDEN_CURRENT_RESULT_KEYS
                    )
                ),

                "status": "PASS",
            },

            "weights": (
                WEIGHTS
            ),

            "frame_prior": (
                FRAME_PRIOR
            ),

            "race_count": (
                len(
                    prediction_races
                )
            ),

            "boat_count": (
                len(
                    csv_rows
                )
            ),

            "races": (
                prediction_races
            ),
        }

        output_json.write_text(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        write_csv(
            output_csv,
            csv_rows,
        )

        if len(
            prediction_races
        ) != 144:

            raise RuntimeError(
                "レース数が144ではありません: "
                f"{len(prediction_races)}"
            )

        if len(
            csv_rows
        ) != 864:

            raise RuntimeError(
                "艇数が864ではありません: "
                f"{len(csv_rows)}"
            )

        ranks_by_race = {}

        for row in csv_rows:

            ranks_by_race.setdefault(
                row[
                    "race_id"
                ],
                set(),
            ).add(
                row[
                    "rank"
                ]
            )

        bad_rank_races = [
            race_id
            for race_id, ranks
            in ranks_by_race.items()
            if ranks
            != {
                1,
                2,
                3,
                4,
                5,
                6,
            }
        ]

        if bad_rank_races:

            raise RuntimeError(
                "順位1～6が揃わない"
                "レースがあります: "
                f"{bad_rank_races[:5]}"
            )

        min_score = min(
            all_scores
        )

        max_score = max(
            all_scores
        )

        avg_score = (
            sum(
                all_scores
            )
            / len(
                all_scores
            )
        )

        avg_coverage = (
            sum(
                all_coverages
            )
            / len(
                all_coverages
            )
        )

        validation = {
            "status": "PASS",

            "model_version": (
                MODEL_VERSION
            ),

            "target_date": (
                target_date
            ),

            "prediction_stage": (
                "morning"
            ),

            "race_count": (
                len(
                    prediction_races
                )
            ),

            "boat_count": (
                len(
                    csv_rows
                )
            ),

            "history_max_date": (
                history_max_date
            ),

            "score_min": round(
                min_score,
                2,
            ),

            "score_max": round(
                max_score,
                2,
            ),

            "score_average": round(
                avg_score,
                2,
            ),

            "average_data_coverage_pct": round(
                avg_coverage,
                1,
            ),

            "current_day_result_leakage": 0,

            "course_used": False,

            "exhibition_used": False,

            "note": (
                "初期ルールベースモデル。"
                "10月1日以降の予測→結果を保存し、"
                "バックテストで重みを改善する前提。"
            ),
        }

        validation_json.write_text(
            json.dumps(
                validation,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(
            "========================================"
        )

        print(
            "朝予測スコア生成"
        )

        print(
            "========================================"
        )

        print(
            "モデル:",
            MODEL_VERSION,
        )

        print(
            "対象日:",
            target_date,
        )

        print(
            "レース数:",
            len(
                prediction_races
            ),
        )

        print(
            "艇数:",
            len(
                csv_rows
            ),
        )

        print(
            "平均データ充足率:",
            f"{avg_coverage:.1f}%",
        )

        print(
            "スコア範囲:",
            f"{min_score:.2f}",
            "～",
            f"{max_score:.2f}",
        )

        print(
            "履歴最終日:",
            history_max_date,
        )

        print(
            "当日結果漏洩:",
            "0",
        )

        print(
            "未確定進入コース使用:",
            "なし",
        )

        print(
            "展示情報使用:",
            "なし",
        )

        print("")

        print(
            "朝予測生成: PASS"
        )

        print(
            "出力JSON:",
            output_json,
        )

        print(
            "出力CSV:",
            output_csv,
        )

        print(
            "検証JSON:",
            validation_json,
        )

        print(
            "========================================"
        )

        return 0

    except Exception as exc:

        failure = {
            "status": "FAIL",

            "model_version": (
                MODEL_VERSION
            ),

            "target_date": (
                target_date
            ),

            "error": str(
                exc
            ),

            "generated_at": (
                datetime.now(
                    JST
                ).isoformat()
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