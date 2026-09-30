from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


JST = timezone(
    timedelta(hours=9)
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "朝予測・直前予測・"
            "フォーメーションを実結果と比較"
        )
    )

    parser.add_argument(
        "--date",
        required=True,
    )

    parser.add_argument(
        "--require-live",
        action="store_true",
    )

    return parser.parse_args()


def text(value):
    if value is None:
        return ""
    return str(value).strip()


def to_float(value):
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


def finish_number(value):
    raw = text(value)

    if raw.isdigit():
        number = int(raw)

        if 1 <= number <= 6:
            return number

    return None


def canonical_race_id(value):
    return "".join(
        re.findall(
            r"\d",
            text(value),
        )
    )


def mean(values):
    if not values:
        return None

    return (
        sum(values)
        / len(values)
    )


def rate(
    numerator,
    denominator,
):
    if not denominator:
        return None

    return (
        numerator
        / denominator
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


def load_json(
    path,
    required=True,
):
    path = Path(path)

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


def first_existing_value(
    row,
    keys,
):
    for key in keys:
        value = row.get(key)

        if value not in (
            None,
            "",
        ):
            return value

    return None


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
        / f"boat_results_{target_date}_all.csv"
    )

    result_path = (
        base
        / f"results_{target_date}_all.csv"
    )

    if not boat_path.exists():
        raise RuntimeError(
            f"実結果がありません: {boat_path}"
        )

    by_race = defaultdict(list)

    with boat_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        reader = csv.DictReader(f)

        for row in reader:
            race_key = canonical_race_id(
                row.get("race_id")
            )

            boat = to_int(
                row.get("boat")
            )

            if (
                not race_key
                or boat is None
            ):
                continue

            by_race[
                race_key
            ].append(
                {
                    "boat": boat,
                    "finish": finish_number(
                        row.get("finish")
                    ),
                    "course": to_int(
                        row.get("course")
                    ),
                    "st": text(
                        row.get("st")
                    ),
                }
            )

    payout_map = {}

    if result_path.exists():
        with result_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as f:
            reader = csv.DictReader(f)

            for row in reader:
                race_key = canonical_race_id(
                    row.get("race_id")
                )

                payout_value = (
                    first_existing_value(
                        row,
                        (
                            "trifecta_pay",
                            "trifecta_payout",
                            "sanrentan_pay",
                            "3rentan_pay",
                        ),
                    )
                )

                payout_map[
                    race_key
                ] = to_int(
                    payout_value
                )

    actual = {}

    for race_key, boats in by_race.items():
        top3 = []

        for finish in (
            1,
            2,
            3,
        ):
            winner_boat = next(
                (
                    row["boat"]
                    for row in boats
                    if row["finish"]
                    == finish
                ),
                None,
            )

            if winner_boat is not None:
                top3.append(
                    winner_boat
                )

        actual[
            race_key
        ] = {
            "boats": boats,
            "winner": (
                top3[0]
                if top3
                else None
            ),
            "top3": top3,
            "trifecta": (
                "-".join(
                    map(
                        str,
                        top3,
                    )
                )
                if len(top3) == 3
                else None
            ),
            "trifecta_pay": (
                payout_map.get(
                    race_key
                )
            ),
        }

    return actual


def prediction_map(payload):
    races = (
        payload.get("races")
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
        return {}

    return {
        canonical_race_id(
            race.get("race_id")
        ): race
        for race in races
        if canonical_race_id(
            race.get("race_id")
        )
    }


def ordered_boats(race):
    boats = (
        race.get("boats")
        or []
    )

    rows = [
        row
        for row in boats
        if to_int(
            row.get("boat")
        )
        is not None
    ]

    rows.sort(
        key=lambda row: (
            to_int(
                row.get("rank")
            )
            or 99,
            -(
                to_float(
                    row.get("score")
                )
                or 0
            ),
            to_int(
                row.get("boat")
            )
            or 99,
        )
    )

    return rows


def evaluate_stage(
    name,
    payload,
    actual,
):
    predictions = prediction_map(
        payload
    )

    rows = []

    top1_hits = 0
    top2_hits = 0
    top3_hits = 0
    winner_ranks = []

    for race_key, race in predictions.items():
        truth = actual.get(
            race_key
        )

        if not truth:
            continue

        winner = truth.get(
            "winner"
        )

        if winner is None:
            continue

        boats = ordered_boats(
            race
        )

        if len(boats) != 6:
            continue

        order = [
            to_int(
                row.get("boat")
            )
            for row in boats
        ]

        if winner not in order:
            continue

        winner_rank = (
            order.index(
                winner
            )
            + 1
        )

        top1 = int(
            winner_rank == 1
        )

        top2 = int(
            winner_rank <= 2
        )

        top3 = int(
            winner_rank <= 3
        )

        top1_hits += top1
        top2_hits += top2
        top3_hits += top3
        winner_ranks.append(
            winner_rank
        )

        rows.append(
            {
                "stage": name,
                "race_id": text(
                    race.get(
                        "race_id"
                    )
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
                "race": to_int(
                    race.get("race")
                ),
                "pred_1": order[0],
                "pred_2": order[1],
                "pred_3": order[2],
                "actual_1": winner,
                "actual_2": (
                    truth[
                        "top3"
                    ][1]
                    if len(
                        truth[
                            "top3"
                        ]
                    ) >= 2
                    else None
                ),
                "actual_3": (
                    truth[
                        "top3"
                    ][2]
                    if len(
                        truth[
                            "top3"
                        ]
                    ) >= 3
                    else None
                ),
                "winner_prediction_rank": (
                    winner_rank
                ),
                "top1_hit": top1,
                "winner_in_top2": top2,
                "winner_in_top3": top3,
            }
        )

    total = len(rows)

    summary = {
        "stage": name,
        "prediction_races_in_file": (
            len(predictions)
        ),
        "evaluated_races": total,
        "top1_win_rate": rounded(
            rate(
                top1_hits,
                total,
            )
        ),
        "winner_in_top2_rate": rounded(
            rate(
                top2_hits,
                total,
            )
        ),
        "winner_in_top3_rate": rounded(
            rate(
                top3_hits,
                total,
            )
        ),
        "average_winner_prediction_rank": (
            rounded(
                mean(
                    winner_ranks
                )
            )
        ),
    }

    return summary, rows


def compare_stages(
    morning_rows,
    live_rows,
):
    morning = {
        canonical_race_id(
            row["race_id"]
        ): row
        for row in morning_rows
    }

    live = {
        canonical_race_id(
            row["race_id"]
        ): row
        for row in live_rows
    }

    keys = sorted(
        set(morning)
        & set(live)
    )

    improved = 0
    worsened = 0
    same = 0

    for key in keys:
        before = morning[
            key
        ][
            "winner_prediction_rank"
        ]

        after = live[
            key
        ][
            "winner_prediction_rank"
        ]

        if after < before:
            improved += 1

        elif after > before:
            worsened += 1

        else:
            same += 1

    return {
        "compared_races": len(keys),
        "winner_rank_improved": improved,
        "winner_rank_worsened": worsened,
        "winner_rank_same": same,
        "improved_rate": rounded(
            rate(
                improved,
                len(keys),
            )
        ),
    }


def evaluate_formations(
    payload,
    actual,
):
    races = (
        payload.get("races")
        or []
    )

    details = []

    totals = {
        "races": 0,
        "hits": 0,
        "points": 0,
        "investment": 0,
        "return": 0,
    }

    by_type = defaultdict(
        lambda: {
            "races": 0,
            "hits": 0,
            "points": 0,
            "investment": 0,
            "return": 0,
        }
    )

    by_prediction = defaultdict(
        lambda: {
            "races": 0,
            "hits": 0,
            "points": 0,
            "investment": 0,
            "return": 0,
        }
    )

    for race in races:
        race_key = canonical_race_id(
            race.get("race_id")
        )

        truth = actual.get(
            race_key
        )

        if (
            not truth
            or not truth.get(
                "trifecta"
            )
        ):
            continue

        formation = (
            race.get(
                "formation"
            )
            or {}
        )

        combinations = (
            formation.get(
                "combinations"
            )
            or []
        )

        if not combinations:
            continue

        points = len(
            combinations
        )

        investment = (
            points * 100
        )

        winning_combo = truth[
            "trifecta"
        ]

        hit = int(
            winning_combo
            in combinations
        )

        payout = (
            truth.get(
                "trifecta_pay"
            )
            or 0
        )

        returned = (
            payout
            if hit
            else 0
        )

        profit = (
            returned
            - investment
        )

        formation_type = text(
            formation.get(
                "formation_type"
            )
        ) or "不明"

        prediction_type = text(
            race.get(
                "prediction_type"
            )
        ) or "不明"

        detail = {
            "race_id": text(
                race.get(
                    "race_id"
                )
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
            "race": to_int(
                race.get("race")
            ),
            "prediction_type": (
                prediction_type
            ),
            "formation_type": (
                formation_type
            ),
            "points": points,
            "investment": investment,
            "actual_trifecta": (
                winning_combo
            ),
            "trifecta_payout_100yen": (
                payout
            ),
            "hit": hit,
            "return": returned,
            "profit": profit,
            "combinations": (
                " / ".join(
                    combinations
                )
            ),
        }

        details.append(
            detail
        )

        for bucket in (
            totals,
            by_type[
                formation_type
            ],
            by_prediction[
                prediction_type
            ],
        ):
            bucket[
                "races"
            ] += 1

            bucket[
                "hits"
            ] += hit

            bucket[
                "points"
            ] += points

            bucket[
                "investment"
            ] += investment

            bucket[
                "return"
            ] += returned

    def summarize(bucket):
        investment = bucket[
            "investment"
        ]

        returned = bucket[
            "return"
        ]

        return {
            **bucket,
            "hit_rate": rounded(
                rate(
                    bucket[
                        "hits"
                    ],
                    bucket[
                        "races"
                    ],
                )
            ),
            "average_points_per_race": (
                rounded(
                    rate(
                        bucket[
                            "points"
                        ],
                        bucket[
                            "races"
                        ],
                    )
                )
            ),
            "profit": (
                returned
                - investment
            ),
            "recovery_rate_pct": (
                rounded(
                    (
                        returned
                        / investment
                        * 100
                    )
                    if investment
                    else None,
                    2,
                )
            ),
        }

    return {
        "model_version": text(
            payload.get(
                "model_version"
            )
        ),
        "100yen_per_combination": True,
        "overall": summarize(
            totals
        ),
        "by_formation_type": {
            key: summarize(
                value
            )
            for key, value
            in by_type.items()
        },
        "by_prediction_type": {
            key: summarize(
                value
            )
            for key, value
            in by_prediction.items()
        },
        "details": details,
    }


def write_csv(
    path,
    rows,
):
    if not rows:
        return

    fields = list(
        rows[0].keys()
    )

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
        writer.writerows(rows)


def main():
    args = parse_args()

    target_date = args.date

    try:
        datetime.strptime(
            target_date,
            "%Y%m%d",
        )

        base = (
            Path("predictions")
            / target_date[:4]
            / target_date[4:6]
            / target_date[6:8]
        )

        morning_payload = load_json(
            base
            / (
                f"morning_predictions_"
                f"{target_date}.json"
            )
        )

        live_payload = load_json(
            base
            / "live"
            / (
                f"live_predictions_final_"
                f"{target_date}.json"
            ),
            required=(
                args.require_live
            ),
        )

        formation_payload = load_json(
            base
            / "live"
            / (
                "formation_predictions_final_"
                f"{target_date}.json"
            )
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

        if live_payload:
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

        comparison = compare_stages(
            morning_rows,
            live_rows,
        )

        formation_result = (
            evaluate_formations(
                formation_payload,
                actual,
            )
        )

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
            morning_rows
            + live_rows,
        )

        write_csv(
            output_dir
            / (
                "formation_simulation_"
                f"{target_date}.csv"
            ),
            formation_result[
                "details"
            ],
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
                len(actual)
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
            "formation_simulation": {
                "model_version": (
                    formation_result[
                        "model_version"
                    ]
                ),
                "overall": (
                    formation_result[
                        "overall"
                    ]
                ),
                "by_formation_type": (
                    formation_result[
                        "by_formation_type"
                    ]
                ),
                "by_prediction_type": (
                    formation_result[
                        "by_prediction_type"
                    ]
                ),
            },
            "note": (
                "各買い目100円固定。"
                "当日の結果を見て"
                "予測やフォーメーションを"
                "後から変更していない。"
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

        (
            output_dir
            / (
                "formation_simulation_"
                f"{target_date}.json"
            )
        ).write_text(
            json.dumps(
                formation_result,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(
            "========================================"
        )
        print(
            "予測＋フォーメーション最終評価"
        )
        print(
            "========================================"
        )
        print(
            "朝予測評価:",
            morning_summary[
                "evaluated_races"
            ],
            "R",
        )
        print(
            "直前予測評価:",
            live_summary[
                "evaluated_races"
            ],
            "R",
        )

        overall = (
            formation_result[
                "overall"
            ]
        )

        print(
            "フォーメーション評価:",
            overall[
                "races"
            ],
            "R",
        )
        print(
            "的中:",
            overall[
                "hits"
            ],
            "R",
        )
        print(
            "投資:",
            overall[
                "investment"
            ],
            "円",
        )
        print(
            "払戻:",
            overall[
                "return"
            ],
            "円",
        )
        print(
            "損益:",
            overall[
                "profit"
            ],
            "円",
        )
        print(
            "回収率:",
            overall[
                "recovery_rate_pct"
            ],
            "%",
        )
        print(
            "評価生成: PASS"
        )

        return 0

    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )