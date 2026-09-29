from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


JST = timezone(
    timedelta(
        hours=9
    )
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "朝予測・直前予測を"
            "実結果と比較"
        )
    )

    parser.add_argument(
        "--date",
        required=True,
        help="YYYYMMDD",
    )

    parser.add_argument(
        "--require-live",
        action="store_true",
    )

    return parser.parse_args()


def text(value):
    if value is None:
        return ""

    return str(
        value
    ).strip()


def number(value):
    try:
        result = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    if not math.isfinite(
        result
    ):
        return None

    return result


def integer(value):
    value = number(
        value
    )

    if value is None:
        return None

    return int(
        value
    )


def normal_finish(value):
    value = text(
        value
    )

    if value.isdigit():
        finish = int(
            value
        )

        if (
            1
            <= finish
            <= 6
        ):
            return finish

    return None


def mean(values):
    if not values:
        return None

    return (
        sum(
            values
        )
        / len(
            values
        )
    )


def rate(
    count,
    total,
):
    if total <= 0:
        return None

    return (
        count
        / total
    )


def rounded(
    value,
    digits=5,
):
    if value is None:
        return None

    return round(
        value,
        digits,
    )


def pearson(
    xs,
    ys,
):
    if (
        len(xs) < 3
        or len(xs)
        != len(ys)
    ):
        return None

    mean_x = mean(
        xs
    )

    mean_y = mean(
        ys
    )

    dx = [
        value - mean_x
        for value
        in xs
    ]

    dy = [
        value - mean_y
        for value
        in ys
    ]

    denominator = math.sqrt(
        sum(
            value * value
            for value
            in dx
        )
        * sum(
            value * value
            for value
            in dy
        )
    )

    if denominator == 0:
        return None

    return (
        sum(
            x * y
            for x, y
            in zip(
                dx,
                dy,
            )
        )
        / denominator
    )


def load_json(
    path,
    required=True,
):
    path = Path(
        path
    )

    if not path.exists():
        if required:
            raise RuntimeError(
                f"ファイルがありません: {path}"
            )

        return None

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def load_actual(
    target_date,
):
    base = (
        Path("archive")
        / target_date[:4]
        / target_date[4:6]
        / target_date[6:8]
    )

    boat_path = (
        base
        / (
            f"boat_results_"
            f"{target_date}_all.csv"
        )
    )

    result_path = (
        base
        / (
            f"results_"
            f"{target_date}_all.csv"
        )
    )

    if not boat_path.exists():
        raise RuntimeError(
            f"実結果がありません: {boat_path}"
        )

    by_race = defaultdict(
        list
    )

    with boat_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        reader = csv.DictReader(
            f
        )

        for row in reader:

            race_id = text(
                row.get(
                    "race_id"
                )
            )

            boat = integer(
                row.get(
                    "boat"
                )
            )

            if (
                not race_id
                or boat is None
            ):
                continue

            by_race[
                race_id
            ].append(
                {
                    "boat": boat,

                    "finish": (
                        normal_finish(
                            row.get(
                                "finish"
                            )
                        )
                    ),

                    "finish_raw": (
                        text(
                            row.get(
                                "finish"
                            )
                        )
                    ),

                    "course": integer(
                        row.get(
                            "course"
                        )
                    ),

                    "st": text(
                        row.get(
                            "st"
                        )
                    ),
                }
            )

    payouts = {}

    if result_path.exists():

        with result_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as f:

            reader = csv.DictReader(
                f
            )

            for row in reader:

                payouts[
                    text(
                        row.get(
                            "race_id"
                        )
                    )
                ] = {
                    "trifecta": text(
                        row.get(
                            "trifecta"
                        )
                    ),

                    "trifecta_pay": integer(
                        row.get(
                            "trifecta_pay"
                        )
                    ),

                    "exacta": text(
                        row.get(
                            "exacta"
                        )
                    ),

                    "exacta_pay": integer(
                        row.get(
                            "exacta_pay"
                        )
                    ),
                }

    actual = {}

    for race_id, rows in (
        by_race.items()
    ):

        winner = next(
            (
                row[
                    "boat"
                ]
                for row
                in rows
                if row[
                    "finish"
                ]
                == 1
            ),
            None,
        )

        top3 = []

        for finish in (
            1,
            2,
            3,
        ):

            boat = next(
                (
                    row[
                        "boat"
                    ]
                    for row
                    in rows
                    if row[
                        "finish"
                    ]
                    == finish
                ),
                None,
            )

            if boat is not None:
                top3.append(
                    boat
                )

        actual[
            race_id
        ] = {
            "winner": winner,

            "top3": top3,

            "boats": rows,

            "payout": (
                payouts.get(
                    race_id,
                    {},
                )
            ),
        }

    return actual


def prediction_map(
    payload,
):
    races = (
        payload.get(
            "races"
        )
        if isinstance(
            payload,
            dict,
        )
        else None
    )

    if not isinstance(
        races,
        list,
    ):
        raise RuntimeError(
            "予測JSONのracesが不正です"
        )

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


def ordered_boats(
    race,
):
    boats = (
        race.get(
            "boats"
        )
        or []
    )

    rows = [
        boat
        for boat
        in boats
        if integer(
            boat.get(
                "boat"
            )
        )
        is not None
    ]

    rows.sort(
        key=lambda boat: (
            integer(
                boat.get(
                    "rank"
                )
            )
            or 99,

            integer(
                boat.get(
                    "boat"
                )
            )
            or 99,
        )
    )

    return rows


def evaluate_stage(
    stage_name,
    payload,
    actual,
):
    predictions = prediction_map(
        payload
    )

    rows = []

    winner_ranks = []

    top1_hits = 0
    top2_capture = 0
    top3_capture = 0

    top3_set_hits = 0
    top3_order_hits = 0
    top3_overlap_sum = 0

    gap_hit = []
    gap_miss = []

    for race_id, truth in (
        actual.items()
    ):

        winner = truth.get(
            "winner"
        )

        if (
            winner is None
            or race_id
            not in predictions
        ):
            continue

        race = predictions[
            race_id
        ]

        ranked = ordered_boats(
            race
        )

        if len(
            ranked
        ) != 6:
            continue

        order = [
            integer(
                boat.get(
                    "boat"
                )
            )
            for boat
            in ranked
        ]

        scores = [
            number(
                boat.get(
                    "score"
                )
            )
            for boat
            in ranked
        ]

        if winner not in order:
            continue

        winner_rank = (
            order.index(
                winner
            )
            + 1
        )

        predicted_top3 = (
            order[:3]
        )

        actual_top3 = (
            truth.get(
                "top3"
            )
            or []
        )

        overlap = (
            len(
                set(
                    predicted_top3
                )
                & set(
                    actual_top3
                )
            )
            if actual_top3
            else 0
        )

        gap12 = None

        if (
            len(
                scores
            )
            >= 2
            and scores[0]
            is not None
            and scores[1]
            is not None
        ):

            gap12 = (
                scores[0]
                - scores[1]
            )

            if winner_rank == 1:
                gap_hit.append(
                    gap12
                )

            else:
                gap_miss.append(
                    gap12
                )

        if winner_rank == 1:
            top1_hits += 1

        if winner_rank <= 2:
            top2_capture += 1

        if winner_rank <= 3:
            top3_capture += 1

        winner_ranks.append(
            winner_rank
        )

        if len(
            actual_top3
        ) == 3:

            if (
                set(
                    predicted_top3
                )
                == set(
                    actual_top3
                )
            ):
                top3_set_hits += 1

            if (
                predicted_top3
                == actual_top3
            ):
                top3_order_hits += 1

            top3_overlap_sum += (
                overlap
            )

        rows.append(
            {
                "stage": (
                    stage_name
                ),

                "race_id": (
                    race_id
                ),

                "venue_code": text(
                    race.get(
                        "venue_code"
                    )
                ),

                "venue_name": text(
                    race.get(
                        "venue_name"
                    )
                ),

                "race": integer(
                    race.get(
                        "race"
                    )
                ),

                "pred_1": (
                    order[0]
                ),

                "pred_2": (
                    order[1]
                ),

                "pred_3": (
                    order[2]
                ),

                "actual_1": (
                    winner
                ),

                "actual_2": (
                    actual_top3[1]
                    if len(
                        actual_top3
                    )
                    >= 2
                    else None
                ),

                "actual_3": (
                    actual_top3[2]
                    if len(
                        actual_top3
                    )
                    >= 3
                    else None
                ),

                "winner_prediction_rank": (
                    winner_rank
                ),

                "top1_hit": int(
                    winner_rank
                    == 1
                ),

                "winner_in_top2": int(
                    winner_rank
                    <= 2
                ),

                "winner_in_top3": int(
                    winner_rank
                    <= 3
                ),

                "top3_overlap": (
                    overlap
                ),

                "top3_set_hit": int(
                    len(
                        actual_top3
                    )
                    == 3
                    and set(
                        predicted_top3
                    )
                    == set(
                        actual_top3
                    )
                ),

                "top3_order_hit": int(
                    len(
                        actual_top3
                    )
                    == 3
                    and predicted_top3
                    == actual_top3
                ),

                "top1_top2_gap": (
                    rounded(
                        gap12,
                        3,
                    )
                ),
            }
        )

    evaluated = len(
        rows
    )

    complete_top3 = sum(
        1
        for row
        in rows
        if (
            row[
                "actual_2"
            ]
            is not None
            and row[
                "actual_3"
            ]
            is not None
        )
    )

    summary = {
        "stage": (
            stage_name
        ),

        "prediction_races_in_file": (
            len(
                predictions
            )
        ),

        "evaluated_races": (
            evaluated
        ),

        "top1_win_rate": rounded(
            rate(
                top1_hits,
                evaluated,
            )
        ),

        "winner_in_top2_rate": rounded(
            rate(
                top2_capture,
                evaluated,
            )
        ),

        "winner_in_top3_rate": rounded(
            rate(
                top3_capture,
                evaluated,
            )
        ),

        "average_winner_prediction_rank": (
            rounded(
                mean(
                    winner_ranks
                )
            )
        ),

        "top3_set_hit_rate": rounded(
            rate(
                top3_set_hits,
                complete_top3,
            )
        ),

        "top3_exact_order_rate": rounded(
            rate(
                top3_order_hits,
                complete_top3,
            )
        ),

        "average_top3_overlap": rounded(
            rate(
                top3_overlap_sum,
                complete_top3,
            )
        ),

        "avg_gap_when_top1_hit": rounded(
            mean(
                gap_hit
            )
        ),

        "avg_gap_when_top1_miss": rounded(
            mean(
                gap_miss
            )
        ),
    }

    return (
        summary,
        rows,
    )


def compare_stages(
    morning_rows,
    live_rows,
):
    morning = {
        row[
            "race_id"
        ]: row
        for row
        in morning_rows
    }

    live = {
        row[
            "race_id"
        ]: row
        for row
        in live_rows
    }

    race_ids = sorted(
        set(
            morning
        )
        & set(
            live
        )
    )

    improved = 0
    worsened = 0
    same = 0

    top1_gain = 0
    top1_loss = 0

    top3_gain = 0
    top3_loss = 0

    details = []

    for race_id in race_ids:

        morning_row = morning[
            race_id
        ]

        live_row = live[
            race_id
        ]

        before = (
            morning_row[
                "winner_prediction_rank"
            ]
        )

        after = (
            live_row[
                "winner_prediction_rank"
            ]
        )

        if after < before:
            improved += 1

        elif after > before:
            worsened += 1

        else:
            same += 1

        if (
            morning_row[
                "top1_hit"
            ]
            == 0
            and live_row[
                "top1_hit"
            ]
            == 1
        ):
            top1_gain += 1

        if (
            morning_row[
                "top1_hit"
            ]
            == 1
            and live_row[
                "top1_hit"
            ]
            == 0
        ):
            top1_loss += 1

        if (
            morning_row[
                "winner_in_top3"
            ]
            == 0
            and live_row[
                "winner_in_top3"
            ]
            == 1
        ):
            top3_gain += 1

        if (
            morning_row[
                "winner_in_top3"
            ]
            == 1
            and live_row[
                "winner_in_top3"
            ]
            == 0
        ):
            top3_loss += 1

        details.append(
            {
                "race_id": (
                    race_id
                ),

                "morning_winner_rank": (
                    before
                ),

                "live_winner_rank": (
                    after
                ),

                "rank_change": (
                    before
                    - after
                ),
            }
        )

    total = len(
        race_ids
    )

    return {
        "compared_races": (
            total
        ),

        "winner_rank_improved": (
            improved
        ),

        "winner_rank_worsened": (
            worsened
        ),

        "winner_rank_same": (
            same
        ),

        "improved_rate": rounded(
            rate(
                improved,
                total,
            )
        ),

        "top1_net_gain": (
            top1_gain
            - top1_loss
        ),

        "top3_net_gain": (
            top3_gain
            - top3_loss
        ),

        "details": (
            details
        ),
    }


def component_analysis(
    payload,
    actual,
):
    predictions = prediction_map(
        payload
    )

    bucket = defaultdict(
        lambda: {
            "winner": [],
            "nonwinner": [],
            "xs": [],
            "ys": [],
            "pick_hits": 0,
            "pick_races": 0,
        }
    )

    for race_id, race in (
        predictions.items()
    ):

        truth = actual.get(
            race_id
        )

        winner = (
            truth.get(
                "winner"
            )
            if truth
            else None
        )

        if winner is None:
            continue

        boats = ordered_boats(
            race
        )

        component_names = set()

        for boat in boats:

            components = (
                boat.get(
                    "components"
                )
            )

            if isinstance(
                components,
                dict,
            ):
                component_names.update(
                    components.keys()
                )

        for component_name in (
            component_names
        ):

            available = []

            for boat in boats:

                component_data = (
                    (
                        boat.get(
                            "components"
                        )
                        or {}
                    ).get(
                        component_name
                    )
                    or {}
                )

                raw_score = number(
                    component_data.get(
                        "raw_score_0_1"
                    )
                )

                boat_number = integer(
                    boat.get(
                        "boat"
                    )
                )

                if (
                    raw_score is None
                    or boat_number
                    is None
                ):
                    continue

                finish = next(
                    (
                        item[
                            "finish"
                        ]
                        for item
                        in truth[
                            "boats"
                        ]
                        if item[
                            "boat"
                        ]
                        == boat_number
                    ),
                    None,
                )

                if finish is not None:

                    bucket[
                        component_name
                    ][
                        "xs"
                    ].append(
                        raw_score
                    )

                    bucket[
                        component_name
                    ][
                        "ys"
                    ].append(
                        (
                            7
                            - finish
                        )
                        / 6.0
                    )

                if boat_number == winner:

                    bucket[
                        component_name
                    ][
                        "winner"
                    ].append(
                        raw_score
                    )

                else:

                    bucket[
                        component_name
                    ][
                        "nonwinner"
                    ].append(
                        raw_score
                    )

                available.append(
                    (
                        raw_score,
                        boat_number,
                    )
                )

            if available:

                available.sort(
                    key=lambda item: (
                        -item[0],
                        item[1],
                    )
                )

                bucket[
                    component_name
                ][
                    "pick_races"
                ] += 1

                if (
                    available[0][1]
                    == winner
                ):
                    bucket[
                        component_name
                    ][
                        "pick_hits"
                    ] += 1

    weights = (
        payload.get(
            "weights"
        )
        or {}
    )

    output = {}

    for component_name, data in sorted(
        bucket.items()
    ):

        winner_mean = mean(
            data[
                "winner"
            ]
        )

        nonwinner_mean = mean(
            data[
                "nonwinner"
            ]
        )

        gap = (
            None
            if (
                winner_mean
                is None
                or nonwinner_mean
                is None
            )
            else (
                winner_mean
                - nonwinner_mean
            )
        )

        correlation = pearson(
            data[
                "xs"
            ],
            data[
                "ys"
            ],
        )

        observations = len(
            data[
                "xs"
            ]
        )

        if observations < 100:

            diagnostic = (
                "insufficient_sample"
            )

        elif (
            correlation is not None
            and correlation >= 0.12
            and gap is not None
            and gap >= 0.04
        ):

            diagnostic = (
                "increase_candidate"
            )

        elif (
            (
                correlation is not None
                and correlation <= 0.02
            )
            or (
                gap is not None
                and gap < 0
            )
        ):

            diagnostic = (
                "decrease_candidate"
            )

        else:

            diagnostic = (
                "hold"
            )

        output[
            component_name
        ] = {
            "current_weight": (
                weights.get(
                    component_name
                )
            ),

            "boat_observations": (
                observations
            ),

            "eligible_races": (
                data[
                    "pick_races"
                ]
            ),

            "component_top_pick_win_rate": (
                rounded(
                    rate(
                        data[
                            "pick_hits"
                        ],
                        data[
                            "pick_races"
                        ],
                    )
                )
            ),

            "winner_mean_raw_score": (
                rounded(
                    winner_mean
                )
            ),

            "nonwinner_mean_raw_score": (
                rounded(
                    nonwinner_mean
                )
            ),

            "winner_nonwinner_gap": (
                rounded(
                    gap
                )
            ),

            "correlation_with_finish_strength": (
                rounded(
                    correlation
                )
            ),

            "diagnostic_only": (
                diagnostic
            ),
        }

    return output


def write_csv(
    path,
    rows,
):
    if not rows:
        return

    fields = list(
        rows[
            0
        ].keys()
    )

    with Path(
        path
    ).open(
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
            "ERROR: --dateはYYYYMMDD形式です",
            file=sys.stderr,
        )

        return 1

    prediction_dir = (
        Path("predictions")
        / target_date[:4]
        / target_date[4:6]
        / target_date[6:8]
    )

    morning_path = (
        prediction_dir
        / (
            f"morning_predictions_"
            f"{target_date}.json"
        )
    )

    live_path = (
        prediction_dir
        / "live"
        / (
            f"live_predictions_final_"
            f"{target_date}.json"
        )
    )

    try:

        morning_payload = load_json(
            morning_path,
            required=True,
        )

        live_payload = load_json(
            live_path,
            required=(
                args.require_live
            ),
        )

        actual = load_actual(
            target_date
        )

        (
            morning_summary,
            morning_rows,
        ) = evaluate_stage(
            "morning",
            morning_payload,
            actual,
        )

        if (
            morning_summary[
                "evaluated_races"
            ]
            == 0
        ):
            raise RuntimeError(
                "朝予測を評価できる"
                "レースが0件です"
            )

        if live_payload is not None:

            (
                live_summary,
                live_rows,
            ) = evaluate_stage(
                "live",
                live_payload,
                actual,
            )

        else:

            live_summary = {
                "stage": "live",
                "evaluated_races": 0,
            }

            live_rows = []

        if (
            args.require_live
            and live_summary.get(
                "evaluated_races",
                0,
            )
            == 0
        ):
            raise RuntimeError(
                "直前予測を評価できる"
                "レースが0件です"
            )

        if live_rows:

            comparison = (
                compare_stages(
                    morning_rows,
                    live_rows,
                )
            )

        else:

            comparison = {
                "compared_races": 0,
            }

        output_dir = (
            Path("evaluations")
            / target_date[:4]
            / target_date[4:6]
            / target_date[6:8]
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        write_csv(
            output_dir
            / (
                "prediction_evaluation_"
                f"{target_date}.csv"
            ),
            (
                morning_rows
                + live_rows
            ),
        )

        evaluation = {
            "status": "PASS",

            "target_date": (
                target_date
            ),

            "generated_at": (
                datetime.now(
                    JST
                ).isoformat()
            ),

            "actual_races_available": (
                len(
                    actual
                )
            ),

            "morning": (
                morning_summary
            ),

            "live": (
                live_summary
            ),

            "morning_vs_live": (
                comparison
            ),

            "note": (
                "予測後に取得した実結果のみで評価。"
                "この処理では重みを変更しない。"
            ),
        }

        (
            output_dir
            / (
                "prediction_evaluation_"
                f"{target_date}.json"
            )
        ).write_text(
            json.dumps(
                evaluation,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        component = {
            "status": "PASS",

            "target_date": (
                target_date
            ),

            "generated_at": (
                datetime.now(
                    JST
                ).isoformat()
            ),

            "morning_components": (
                component_analysis(
                    morning_payload,
                    actual,
                )
            ),

            "live_components": (
                component_analysis(
                    live_payload,
                    actual,
                )
                if live_payload
                else {}
            ),

            "interpretation": {
                "increase_candidate": (
                    "単日診断では寄与が比較的強い候補。"
                    "自動で重み変更しない。"
                ),

                "decrease_candidate": (
                    "単日診断では寄与が弱い候補。"
                    "自動で重み変更しない。"
                ),

                "hold": (
                    "現時点では維持候補。"
                ),

                "insufficient_sample": (
                    "サンプル不足。判断保留。"
                ),
            },
        }

        (
            output_dir
            / (
                "score_component_analysis_"
                f"{target_date}.json"
            )
        ).write_text(
            json.dumps(
                component,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(
            "========================================"
        )

        print(
            "9/30 予測実績評価"
        )

        print(
            "========================================"
        )

        print(
            "実結果レース:",
            len(
                actual
            ),
        )

        print(
            "朝予測評価:",
            morning_summary[
                "evaluated_races"
            ],
            "R",
        )

        print(
            "朝1位予測1着率:",
            morning_summary[
                "top1_win_rate"
            ],
        )

        print(
            "朝TOP3勝者捕捉率:",
            morning_summary[
                "winner_in_top3_rate"
            ],
        )

        print(
            "直前予測評価:",
            live_summary.get(
                "evaluated_races",
                0,
            ),
            "R",
        )

        if live_rows:

            print(
                "直前1位予測1着率:",
                live_summary[
                    "top1_win_rate"
                ],
            )

            print(
                "直前TOP3勝者捕捉率:",
                live_summary[
                    "winner_in_top3_rate"
                ],
            )

            print(
                "朝→直前 勝者順位改善:",
                comparison.get(
                    "winner_rank_improved",
                    0,
                ),
                "R",
            )

            print(
                "朝→直前 勝者順位悪化:",
                comparison.get(
                    "winner_rank_worsened",
                    0,
                ),
                "R",
            )

        print(
            "重み自動変更: なし"
        )

        print(
            "評価生成: PASS"
        )

        print(
            "========================================"
        )

        return 0

    except Exception as exc:

        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    sys.exit(
        main()
    )