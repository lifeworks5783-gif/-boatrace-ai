#!/usr/bin/env python3

from __future__ import annotations

import argparse

import json

import math

from collections import defaultdict

from datetime import datetime, timedelta

from pathlib import Path

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

CORE_LABELS = {

    "frame": "枠・コース",

    "official_racer": "選手公式能力",

    "recent_racer": "選手直近成績",

    "racer_venue": "当地・場適性",

    "motor": "モーター",

    "boat_machine": "ボート",

    "grade": "級別",

    "total_score": "総合スコア",

}

LIVE_LABELS = {

    "exhibition_time": "展示タイム",

    "exhibition_st": "展示ST",

    "exhibition_f": "展示F",

    "course_changed": "展示進入変化",

}

def load_json(

    path: Path,

) -> Dict[str, Any]:

    if not path.exists():

        return {}

    return json.loads(

        path.read_text(

            encoding="utf-8"

        )

    )

def number(

    value: Any,

) -> Optional[float]:

    if (

        value is None

        or isinstance(

            value,

            bool,

        )

    ):

        return None

    try:

        value = float(

            value

        )

    except Exception:

        return None

    if not math.isfinite(

        value

    ):

        return None

    return value

def weighted_average(

    values: List[

        Tuple[

            float,

            float,

        ]

    ],

) -> Optional[float]:

    valid = [

        (

            value,

            weight,

        )

        for (

            value,

            weight,

        )

        in values

        if (

            value is not None

            and weight > 0

        )

    ]

    if not valid:

        return None

    total_weight = sum(

        weight

        for (

            _,

            weight,

        )

        in valid

    )

    if total_weight <= 0:

        return None

    return (

        sum(

            value

            * weight

            for (

                value,

                weight,

            )

            in valid

        )

        / total_weight

    )

def date_range(

    end_date: str,

    days: int,

) -> List[str]:

    end = datetime.strptime(

        end_date,

        "%Y%m%d",

    )

    return [

        (

            end

            - timedelta(

                days=offset

            )

        ).strftime(

            "%Y%m%d"

        )

        for offset in range(

            days - 1,

            -1,

            -1,

        )

    ]

def eval_dir(

    date: str,

) -> Path:

    return (

        Path(

            "evaluations"

        )

        / date[:4]

        / date[4:6]

        / date[6:8]

    )

def summarize_bucket(

    bucket: Dict[

        str,

        float,

    ],

) -> Dict[str, Any]:

    races = int(

        bucket.get(

            "races",

            0,

        )

    )

    hits = int(

        bucket.get(

            "hits",

            0,

        )

    )

    points = int(

        bucket.get(

            "points",

            0,

        )

    )

    investment = int(

        bucket.get(

            "investment",

            0,

        )

    )

    returned = int(

        bucket.get(

            "return",

            0,

        )

    )

    return {

        "races": races,

        "hits": hits,

        "hit_rate_pct": (

            round(

                hits

                / races

                * 100,

                1,

            )

            if races

            else None

        ),

        "points": points,

        "investment": (

            investment

        ),

        "return": returned,

        "profit": (

            returned

            - investment

        ),

        "recovery_rate_pct": (

            round(

                returned

                / investment

                * 100,

                1,

            )

            if investment

            else None

        ),

    }

def aggregate_strategy(

    dates: List[str],

    filename_prefix: str,

) -> Dict[str, Any]:

    total = {

        "races": 0,

        "hits": 0,

        "points": 0,

        "investment": 0,

        "return": 0,

    }

    daily = []

    for date in dates:

        payload = load_json(

            eval_dir(

                date

            )

            / (

                f"{filename_prefix}_"

                f"{date}.json"

            )

        )

        overall = (

            payload.get(

                "overall"

            )

            if isinstance(

                payload,

                dict,

            )

            else None

        )

        if not isinstance(

            overall,

            dict,

        ):

            continue

        row = {

            "races": int(

                overall.get(

                    "races"

                )

                or 0

            ),

            "hits": int(

                overall.get(

                    "hits"

                )

                or 0

            ),

            "points": int(

                overall.get(

                    "points"

                )

                or 0

            ),

            "investment": int(

                overall.get(

                    "investment"

                )

                or 0

            ),

            "return": int(

                overall.get(

                    "return"

                )

                or 0

            ),

        }

        daily.append(

            {

                "date": date,

                **summarize_bucket(

                    row

                ),

            }

        )

        for key in total:

            total[

                key

            ] += row[

                key

            ]

    return {

        "available_days": len(

            daily

        ),

        "overall": (

            summarize_bucket(

                total

            )

        ),

        "daily": daily,

    }

def aggregate_prediction_quality(

    dates: List[str],

) -> Dict[str, Any]:

    output = {}

    for stage in (

        "morning",

        "live",

    ):

        rows = []

        for date in dates:

            payload = load_json(

                eval_dir(

                    date

                )

                / (

                    "prediction_evaluation_"

                    f"{date}.json"

                )

            )

            block = (

                payload.get(

                    stage

                )

                if isinstance(

                    payload,

                    dict,

                )

                else None

            )

            if not isinstance(

                block,

                dict,

            ):

                continue

            races = int(

                block.get(

                    "evaluated_races"

                )

                or 0

            )

            if races <= 0:

                continue

            top1 = number(

                block.get(

                    "top1_win_rate"

                )

            )

            top2 = number(

                block.get(

                    "winner_in_top2_rate"

                )

            )

            top3 = number(

                block.get(

                    "winner_in_top3_rate"

                )

            )

            if (

                top1 is not None

                and top1 <= 1

            ):

                top1 *= 100

            if (

                top2 is not None

                and top2 <= 1

            ):

                top2 *= 100

            if (

                top3 is not None

                and top3 <= 1

            ):

                top3 *= 100

            rows.append(

                {

                    "date": date,

                    "races": races,

                    "top1": top1,

                    "top2": top2,

                    "top3": top3,

                }

            )

        output[

            stage

        ] = {

            "available_days": len(

                rows

            ),

            "races": sum(

                row[

                    "races"

                ]

                for row

                in rows

            ),

            "top1_win_rate_pct": (

                round(

                    weighted_average(

                        [

                            (

                                row[

                                    "top1"

                                ],

                                row[

                                    "races"

                                ],

                            )

                            for row

                            in rows

                            if row[

                                "top1"

                            ]

                            is not None

                        ]

                    ),

                    1,

                )

                if weighted_average(

                    [

                        (

                            row[

                                "top1"

                            ],

                            row[

                                "races"

                            ],

                        )

                        for row

                        in rows

                        if row[

                            "top1"

                        ]

                        is not None

                    ]

                )

                is not None

                else None

            ),

            (

                "winner_in_top2_"

                "rate_pct"

            ): (

                round(

                    weighted_average(

                        [

                            (

                                row[

                                    "top2"

                                ],

                                row[

                                    "races"

                                ],

                            )

                            for row

                            in rows

                            if row[

                                "top2"

                            ]

                            is not None

                        ]

                    ),

                    1,

                )

                if weighted_average(

                    [

                        (

                            row[

                                "top2"

                            ],

                            row[

                                "races"

                            ],

                        )

                        for row

                        in rows

                        if row[

                            "top2"

                        ]

                        is not None

                    ]

                )

                is not None

                else None

            ),

            (

                "winner_in_top3_"

                "rate_pct"

            ): (

                round(

                    weighted_average(

                        [

                            (

                                row[

                                    "top3"

                                ],

                                row[

                                    "races"

                                ],

                            )

                            for row

                            in rows

                            if row[

                                "top3"

                            ]

                            is not None

                        ]

                    ),

                    1,

                )

                if weighted_average(

                    [

                        (

                            row[

                                "top3"

                            ],

                            row[

                                "races"

                            ],

                        )

                        for row

                        in rows

                        if row[

                            "top3"

                        ]

                        is not None

                    ]

                )

                is not None

                else None

            ),

        }

    return output

def aggregate_feature_top10(

    dates: List[str],

) -> Tuple[

    List[Dict[str, Any]],

    List[Dict[str, Any]],

]:

    frames = []

    for date in dates:

        path = (

            eval_dir(

                date

            )

            / (

                "score_feature_stats_"

                f"{date}.csv"

            )

        )

        if not path.exists():

            continue

        try:

            frame = pd.read_csv(

                path

            )

        except Exception:

            continue

        if frame.empty:

            continue

        frame[

            "source_date"

        ] = date

        frames.append(

            frame

        )

    if not frames:

        return [], []

    data = pd.concat(

        frames,

        ignore_index=True,

        sort=False,

    )

    output = []

    for (

        stage,

        group,

        column,

    ), block in (

        data.groupby(

            [

                "stage",

                "group",

                "column",

            ],

            dropna=False,

        )

    ):

        races = (

            pd.to_numeric(

                block[

                    "races"

                ],

                errors="coerce",

            )

            .fillna(0)

        )

        corr = pd.to_numeric(

            block[

                "rank_finish_spearman"

            ],

            errors="coerce",

        )

        high_win = pd.to_numeric(

            block[

                "high_leader_win_rate_pct"

            ],

            errors="coerce",

        )

        valid = (

            corr.notna()

            & (

                races > 0

            )

        )

        if not valid.any():

            continue

        total_races = int(

            races[

                valid

            ].sum()

        )

        days_observed = int(

            block.loc[

                valid,

                "source_date",

            ]

            .nunique()

        )

        weighted_abs = (

            (

                corr[

                    valid

                ].abs()

                * races[

                    valid

                ]

            ).sum()

            / races[

                valid

            ].sum()

        )

        weighted_high_win = (

            (

                high_win[

                    valid

                ]

                .fillna(0)

                * races[

                    valid

                ]

            ).sum()

            / races[

                valid

            ].sum()

        )

        output.append(

            {

                "stage": str(

                    stage

                ),

                "group": str(

                    group

                ),

                "label": (

                    CORE_LABELS.get(

                        str(

                            group

                        ),

                        str(

                            group

                        ),

                    )

                ),

                "column": str(

                    column

                ),

                "days_observed": (

                    days_observed

                ),

                "total_races": (

                    total_races

                ),

                "avg_abs_spearman": (

                    round(

                        float(

                            weighted_abs

                        ),

                        4,

                    )

                ),

                (

                    "avg_high_leader_"

                    "win_rate_pct"

                ): (

                    round(

                        float(

                            weighted_high_win

                        ),

                        1,

                    )

                ),

            }

        )

    output.sort(

        key=lambda row: (

            row[

                "avg_abs_spearman"

            ],

            row[

                "days_observed"

            ],

            row[

                "total_races"

            ],

        ),

        reverse=True,

    )

    return (

        output[:10],

        output,

    )

def aggregate_live_factors(

    dates: List[str],

) -> Dict[str, Any]:

    factor_rows: Dict[

        str,

        List[Dict[str, Any]],

    ] = defaultdict(

        list

    )

    coverage: Dict[

        str,

        int,

    ] = defaultdict(

        int

    )

    answer_frames = []

    for date in dates:

        payload = load_json(

            eval_dir(

                date

            )

            / (

                "live_factor_analysis_"

                f"{date}.json"

            )

        )

        if payload:

            for key, value in (

                payload.get(

                    "coverage"

                )

                or {}

            ).items():

                coverage[

                    key

                ] += int(

                    value

                    or 0

                )

            for factor, stat in (

                payload.get(

                    "factors"

                )

                or {}

            ).items():

                if isinstance(

                    stat,

                    dict,

                ):

                    row = dict(

                        stat

                    )

                    row[

                        "date"

                    ] = date

                    factor_rows[

                        factor

                    ].append(

                        row

                    )

        csv_path = (

            eval_dir(

                date

            )

            / (

                "live_factor_"

                "answer_check_"

                f"{date}.csv"

            )

        )

        if csv_path.exists():

            try:

                frame = pd.read_csv(

                    csv_path

                )

                frame[

                    "source_date"

                ] = date

                answer_frames.append(

                    frame

                )

            except Exception:

                pass

    factors = {}

    for factor, rows in (

        factor_rows.items()

    ):

        if factor in (

            "exhibition_time",

            "exhibition_st",

        ):

            valid = [

                row

                for row

                in rows

                if int(

                    row.get(

                        "races"

                    )

                    or 0

                )

                > 0

            ]

            races_total = sum(

                int(

                    row.get(

                        "races"

                    )

                    or 0

                )

                for row

                in valid

            )

            factors[

                factor

            ] = {

                "days": len(

                    rows

                ),

                "races": (

                    races_total

                ),

                "best_win_rate_pct": (

                    round(

                        weighted_average(

                            [

                                (

                                    number(

                                        row.get(

                                            "best_win_rate_pct"

                                        )

                                    ),

                                    int(

                                        row.get(

                                            "races"

                                        )

                                        or 0

                                    ),

                                )

                                for row

                                in valid

                            ]

                        ),

                        1,

                    )

                    if weighted_average(

                        [

                            (

                                number(

                                    row.get(

                                        "best_win_rate_pct"

                                    )

                                ),

                                int(

                                    row.get(

                                        "races"

                                    )

                                    or 0

                                ),

                            )

                            for row

                            in valid

                        ]

                    )

                    is not None

                    else None

                ),

                (

                    "best_top3_rate_pct"

                ): (

                    round(

                        weighted_average(

                            [

                                (

                                    number(

                                        row.get(

                                            "best_top3_rate_pct"

                                        )

                                    ),

                                    int(

                                        row.get(

                                            "races"

                                        )

                                        or 0

                                    ),

                                )

                                for row

                                in valid

                            ]

                        ),

                        1,

                    )

                    if weighted_average(

                        [

                            (

                                number(

                                    row.get(

                                        "best_top3_rate_pct"

                                    )

                                ),

                                int(

                                    row.get(

                                        "races"

                                    )

                                    or 0

                                ),

                            )

                            for row

                            in valid

                        ]

                    )

                    is not None

                    else None

                ),

                (

                    "worst_win_rate_pct"

                ): (

                    round(

                        weighted_average(

                            [

                                (

                                    number(

                                        row.get(

                                            "worst_win_rate_pct"

                                        )

                                    ),

                                    int(

                                        row.get(

                                            "races"

                                        )

                                        or 0

                                    ),

                                )

                                for row

                                in valid

                            ]

                        ),

                        1,

                    )

                    if weighted_average(

                        [

                            (

                                number(

                                    row.get(

                                        "worst_win_rate_pct"

                                    )

                                ),

                                int(

                                    row.get(

                                        "races"

                                    )

                                    or 0

                                ),

                            )

                            for row

                            in valid

                        ]

                    )

                    is not None

                    else None

                ),

            }

        else:

            factors[

                factor

            ] = {

                "days": len(

                    rows

                ),

                "boats": sum(

                    int(

                        row.get(

                            "boats"

                        )

                        or 0

                    )

                    for row

                    in rows

                ),

                "flagged_boats": sum(

                    int(

                        row.get(

                            "flagged_boats"

                        )

                        or 0

                    )

                    for row

                    in rows

                ),

            }

    return {

        "coverage": dict(

            coverage

        ),

        "factors": factors,

        "pooled_weight_search": (

            pooled_weight_search(

                answer_frames

            )

        ),

    }

def pooled_weight_search(

    frames: List[

        pd.DataFrame

    ],

) -> Dict[str, Any]:

    if not frames:

        return {

            "available": False,

            "reason": (

                "answer-check CSVなし"

            ),

        }

    data = pd.concat(

        frames,

        ignore_index=True,

        sort=False,

    )

    required = {

        "source_date",

        "venue_code",

        "race",

        "boat",

        "finish",

        "total_score",

    }

    if not required.issubset(

        data.columns

    ):

        return {

            "available": False,

            "reason": "必要列不足",

            "missing": sorted(

                required

                - set(

                    data.columns

                )

            ),

        }

    for column in (

        "finish",

        "total_score",

        "exhibition_time",

        "exhibition_st",

        "exhibition_f",

    ):

        if column in data.columns:

            data[

                column

            ] = pd.to_numeric(

                data[

                    column

                ],

                errors="coerce",

            )

    data = data.dropna(

        subset=[

            "finish",

            "total_score",

        ]

    ).copy()

    if data.empty:

        return {

            "available": False,

            "reason": (

                "有効行なし"

            ),

        }

    time_available = (

        "exhibition_time"

        in data.columns

        and data[

            "exhibition_time"

        ]

        .notna()

        .sum()

        > 0

    )

    st_available = (

        "exhibition_st"

        in data.columns

        and data[

            "exhibition_st"

        ]

        .notna()

        .sum()

        > 0

    )

    f_available = (

        "exhibition_f"

        in data.columns

        and data[

            "exhibition_f"

        ]

        .fillna(0)

        .gt(0)

        .any()

    )

    if not any(

        (

            time_available,

            st_available,

            f_available,

        )

    ):

        return {

            "available": False,

            "reason": (

                "直前要素データなし"

            ),

        }

    if (

        "exhibition_f"

        not in data.columns

    ):

        data[

            "exhibition_f"

        ] = 0.0

    data[

        "exhibition_f"

    ] = (

        data[

            "exhibition_f"

        ]

        .fillna(0.0)

    )

    data[

        "time_norm"

    ] = 0.5

    data[

        "st_norm"

    ] = 0.5

    group_cols = [

        "source_date",

        "venue_code",

        "race",

    ]

    def normalize(

        series: pd.Series,

        lower_better: bool,

        mask: Optional[

            pd.Series

        ] = None,

    ) -> pd.Series:

        values = pd.to_numeric(

            series,

            errors="coerce",

        )

        if mask is not None:

            values = values.mask(

                mask

            )

        valid = values.dropna()

        if (

            len(

                valid

            ) < 2

            or valid.min()

            == valid.max()

        ):

            return pd.Series(

                0.5,

                index=series.index,

            )

        result = (

            (

                values

                - valid.min()

            )

            /

            (

                valid.max()

                - valid.min()

            )

        )

        if lower_better:

            result = 1 - result

        return result.fillna(

            0.5

        )

    for _, indexes in (

        data.groupby(

            group_cols

        )

        .groups

        .items()

    ):

        race_data = (

            data.loc[

                indexes

            ]

        )

        if time_available:

            data.loc[

                indexes,

                "time_norm",

            ] = normalize(

                race_data[

                    "exhibition_time"

                ],

                True,

            )

        if st_available:

            data.loc[

                indexes,

                "st_norm",

            ] = normalize(

                race_data[

                    "exhibition_st"

                ],

                True,

                mask=(

                    race_data[

                        "exhibition_f"

                    ]

                    > 0

                ),

            )

    valid_keys = {

        key

        for key, block

        in data.groupby(

            group_cols

        )

        if len(

            block

        ) >= 4

    }

    data = (

        data[

            data.apply(

                lambda row: (

                    row[

                        "source_date"

                    ],

                    row[

                        "venue_code"

                    ],

                    row[

                        "race"

                    ],

                )

                in valid_keys,

                axis=1,

            )

        ]

        .copy()

    )

    def accuracy(

        time_weight: int,

        st_weight: int,

        f_penalty: int,

    ) -> float:

        test = data.copy()

        score = (

            test[

                "total_score"

            ]

            .astype(float)

        )

        if time_available:

            score = (

                score

                + time_weight

                * test[

                    "time_norm"

                ]

            )

        if st_available:

            score = (

                score

                + st_weight

                * test[

                    "st_norm"

                ]

            )

        if f_available:

            score = (

                score

                - f_penalty

                * test[

                    "exhibition_f"

                ]

            )

        test[

            "adjusted"

        ] = score

        wins = 0

        races = 0

        for _, block in (

            test.groupby(

                group_cols

            )

        ):

            top = (

                block

                .sort_values(

                    "adjusted",

                    ascending=False,

                )

                .iloc[0]

            )

            wins += int(

                float(

                    top[

                        "finish"

                    ]

                )

                == 1

            )

            races += 1

        if not races:

            return 0.0

        return (

            wins

            / races

            * 100

        )

    baseline = accuracy(

        0,

        0,

        0,

    )

    time_grid = (

        (

            0,

            2,

            4,

            6,

            8,

            10,

            12,

        )

        if time_available

        else (0,)

    )

    st_grid = (

        (

            0,

            2,

            4,

            6,

            8,

            10,

            12,

        )

        if st_available

        else (0,)

    )

    f_grid = (

        (

            0,

            2,

            4,

            6,

            8,

        )

        if f_available

        else (0,)

    )

    candidates = []

    for time_weight in (

        time_grid

    ):

        for st_weight in (

            st_grid

        ):

            for f_penalty in (

                f_grid

            ):

                if (

                    time_weight == 0

                    and st_weight == 0

                    and f_penalty == 0

                ):

                    continue

                current = accuracy(

                    time_weight,

                    st_weight,

                    f_penalty,

                )

                candidates.append(

                    {

                        (

                            "exhibition_"

                            "time_weight"

                        ): time_weight,

                        (

                            "exhibition_"

                            "st_weight"

                        ): st_weight,

                        "f_penalty": (

                            f_penalty

                        ),

                        (

                            "top1_"

                            "accuracy_pct"

                        ): round(

                            current,

                            1,

                        ),

                        (

                            "improvement_"

                            "vs_baseline_pt"

                        ): round(

                            current

                            - baseline,

                            1,

                        ),

                    }

                )

    candidates.sort(

        key=lambda item: (

            item[

                "top1_accuracy_pct"

            ],

            -(

                item[

                    "exhibition_time_weight"

                ]

                + item[

                    "exhibition_st_weight"

                ]

                + item[

                    "f_penalty"

                ]

            ),

        ),

        reverse=True,

    )

    return {

        "available": True,

        "races": len(

            valid_keys

        ),

        (

            "baseline_top1_"

            "accuracy_pct"

        ): round(

            baseline,

            1,

        ),

        "best_candidates": (

            candidates[:10]

        ),

    }

def missing_data_summary(

    live_summary: Dict[

        str,

        Any,

    ],

    expected_boats: int,

) -> List[

    Dict[str, Any]

]:

    coverage = (

        live_summary.get(

            "coverage"

        )

        or {}

    )

    factors = [

        "exhibition_time",

        "exhibition_st",

        "exhibition_f",

        "exhibition_course",

        "wind_speed",

        "wind_direction",

        "wave_height",

    ]

    rows = []

    for key in factors:

        count = int(

            coverage.get(

                key

            )

            or 0

        )

        rate = (

            count

            / expected_boats

            * 100

            if expected_boats

            else 0.0

        )

        rows.append(

            {

                "factor": key,

                "coverage": count,

                (

                    "coverage_"

                    "rate_pct"

                ): round(

                    rate,

                    1,

                ),

                "priority": (

                    "最優先"

                    if rate < 25

                    else (

                        "要改善"

                        if rate < 70

                        else "良好"

                    )

                ),

            }

        )

    return rows

def markdown_table(

    headers: List[str],

    rows: List[

        List[Any]

    ],

) -> List[str]:

    lines = [

        "| "

        + " | ".join(

            headers

        )

        + " |",

        "| "

        + " | ".join(

            [

                "---"

                for _

                in headers

            ]

        )

        + " |",

    ]

    for row in rows:

        lines.append(

            "| "

            + " | ".join(

                str(

                    value

                )

                for value

                in row

            )

            + " |"

        )

    return lines

def main() -> int:

    parser = (

        argparse.ArgumentParser()

    )

    parser.add_argument(

        "--date",

        required=True,

    )

    parser.add_argument(

        "--days",

        type=int,

        default=7,

    )

    args = parser.parse_args()

    dates = date_range(

        args.date,

        args.days,

    )

    formation = aggregate_strategy(

        dates,

        "formation_simulation",

    )

    top3_box = aggregate_strategy(

        dates,

        "top3_box_simulation",

    )

    ai_score = aggregate_strategy(

        dates,

        "ai_score_simulation",

    )

    quality = (

        aggregate_prediction_quality(

            dates

        )

    )

    (

        top10,

        all_features,

    ) = aggregate_feature_top10(

        dates

    )

    live = (

        aggregate_live_factors(

            dates

        )

    )

    expected_boats = 0

    for date in dates:

        path = (

            eval_dir(

                date

            )

            / (

                "score_answer_check_"

                f"boats_{date}.csv"

            )

        )

        if not path.exists():

            continue

        try:

            frame = pd.read_csv(

                path

            )

            morning = frame[

                frame[

                    "stage"

                ]

                .astype(str)

                .str.lower()

                == "morning"

            ]

            expected_boats += len(

                morning

            )

        except Exception:

            pass

    missing = (

        missing_data_summary(

            live,

            expected_boats,

        )

    )

    available_dates = sorted(

        {

            date

            for date

            in dates

            if any(

                [

                    (

                        eval_dir(

                            date

                        )

                        / (

                            "prediction_evaluation_"

                            f"{date}.json"

                        )

                    ).exists(),

                    (

                        eval_dir(

                            date

                        )

                        / (

                            "score_component_"

                            f"analysis_{date}.json"

                        )

                    ).exists(),

                    (

                        eval_dir(

                            date

                        )

                        / (

                            "live_factor_analysis_"

                            f"{date}.json"

                        )

                    ).exists(),

                ]

            )

        }

    )

    report = {

        "target_date": (

            args.date

        ),

        "window_days": (

            args.days

        ),

        "requested_dates": (

            dates

        ),

        "available_dates": (

            available_dates

        ),

        (

            "available_day_count"

        ): len(

            available_dates

        ),

        "strategy": {

            "formation": formation,

            "top3_box": top3_box,

            "ai_score": ai_score,

        },

        (

            "prediction_quality"

        ): quality,

        (

            "feature_consistency_top10"

        ): top10,

        (

            "feature_consistency_all"

        ): all_features,

        (

            "live_factor_summary"

        ): live,

        "missing_data": (

            missing

        ),

        "policy": {

            (

                "auto_change_weights"

            ): False,

            "note": (

                "全特徴量を保存・集計し、"

                "TOP10だけに固定しない。"

                "配点変更は7日以上の"

                "再現性を確認してから"

                "候補として扱う。"

            ),

        },

    }

    Path(

        "evaluations"

    ).mkdir(

        parents=True,

        exist_ok=True,

    )

    json_path = Path(

        "evaluations/"

        "latest_pdca.json"

    )

    md_path = Path(

        "evaluations/"

        "latest_pdca.md"

    )

    json_path.write_text(

        json.dumps(

            report,

            ensure_ascii=False,

            indent=2,

        ),

        encoding="utf-8",

    )

    lines = [

        (

            "# ボートレースAI "

            "7日PDCAレポート"

        ),

        "",

        (

            f"基準日："

            f"{args.date[:4]}/"

            f"{args.date[4:6]}/"

            f"{args.date[6:8]}"

        ),

        (

            f"対象期間："

            f"直近{args.days}日"

        ),

        (

            f"評価データあり："

            f"{len(available_dates)}日"

        ),

        "",

        (

            "> 配点は自動変更しません。"

            "全特徴量を継続保存し、"

            "TOP10外の要素も"

            "毎日再評価します。"

        ),

        "",

        "## 1. 買い方3戦略の累計",

        "",

    ]

    formation_total = (

        formation[

            "overall"

        ]

    )

    box_total = (

        top3_box[

            "overall"

        ]

    )

    ai_total = (

        ai_score[

            "overall"

        ]

    )

    lines += markdown_table(

        [

            "指標",

            "フォーメーション",

            "上位3艇BOX",

            "AIスコア予測",

        ],

        [

            [

                "対象R",

                formation_total[

                    "races"

                ],

                box_total[

                    "races"

                ],

                ai_total["races"],
            ],

            [

                "的中",

                formation_total[

                    "hits"

                ],

                box_total[

                    "hits"

                ],

                ai_total["hits"],
            ],

            [

                "的中率",

                (

                    f"{formation_total['hit_rate_pct']}%"

                    if formation_total[

                        "hit_rate_pct"

                    ]

                    is not None

                    else "—"

                ),

                (

                    f"{box_total['hit_rate_pct']}%"

                    if box_total[

                        "hit_rate_pct"

                    ]

                    is not None

                    else "—"

                ),

                (f"{ai_total['hit_rate_pct']}%" if ai_total["hit_rate_pct"] is not None else "—"),
            ],

            [

                "投資",

                (

                    f"{formation_total['investment']:,}円"

                ),

                (

                    f"{box_total['investment']:,}円"

                ),

            ],

            [

                "払戻",

                (

                    f"{formation_total['return']:,}円"

                ),

                (

                    f"{box_total['return']:,}円"

                ),

            ],

            [

                "損益",

                (

                    f"{formation_total['profit']:,}円"

                ),

                (

                    f"{box_total['profit']:,}円"

                ),

            ],

            [

                "回収率",

                (

                    f"{formation_total['recovery_rate_pct']}%"

                    if formation_total[

                        "recovery_rate_pct"

                    ]

                    is not None

                    else "—"

                ),

                (

                    f"{box_total['recovery_rate_pct']}%"

                    if box_total[

                        "recovery_rate_pct"

                    ]

                    is not None

                    else "—"

                ),

                (f"{ai_total['recovery_rate_pct']}%" if ai_total["recovery_rate_pct"] is not None else "—"),
            ],

        ],

    )

    lines += [

        "",

        "## 2. 予測精度累計",

        "",

    ]

    lines += markdown_table(

        [

            "段階",

            "評価R",

            "1着率",

            "勝者TOP2率",

            "勝者TOP3率",

        ],

        [

            [

                "朝",

                quality[

                    "morning"

                ][

                    "races"

                ],

                (

                    f"{quality['morning']['top1_win_rate_pct']}%"

                    if quality[

                        "morning"

                    ][

                        "top1_win_rate_pct"

                    ]

                    is not None

                    else "—"

                ),

                (

                    f"{quality['morning']['winner_in_top2_rate_pct']}%"

                    if quality[

                        "morning"

                    ][

                        "winner_in_top2_rate_pct"

                    ]

                    is not None

                    else "—"

                ),

                (

                    f"{quality['morning']['winner_in_top3_rate_pct']}%"

                    if quality[

                        "morning"

                    ][

                        "winner_in_top3_rate_pct"

                    ]

                    is not None

                    else "—"

                ),

            ],

            [

                "直前",

                quality[

                    "live"

                ][

                    "races"

                ],

                (

                    f"{quality['live']['top1_win_rate_pct']}%"

                    if quality[

                        "live"

                    ][

                        "top1_win_rate_pct"

                    ]

                    is not None

                    else "—"

                ),

                (

                    f"{quality['live']['winner_in_top2_rate_pct']}%"

                    if quality[

                        "live"

                    ][

                        "winner_in_top2_rate_pct"

                    ]

                    is not None

                    else "—"

                ),

                (

                    f"{quality['live']['winner_in_top3_rate_pct']}%"

                    if quality[

                        "live"

                    ][

                        "winner_in_top3_rate_pct"

                    ]

                    is not None

                    else "—"

                ),

            ],

        ],

    )

    lines += [

        "",

        (

            "## 3. 直近期間の"

            "整合性TOP10"

        ),

        "",

        (

            "※ TOP10外もJSONに"

            "全件保存し、"

            "翌日以降も再評価します。"

        ),

        "",

    ]

    if top10:

        lines += markdown_table(

            [

                "順位",

                "段階",

                "要素",

                "日数",

                "R数",

                (

                    "平均|順位相関|"

                ),

                (

                    "高値首位"

                    "1着率"

                ),

            ],

            [

                [

                    index + 1,

                    row[

                        "stage"

                    ],

                    row[

                        "label"

                    ],

                    row[

                        "days_observed"

                    ],

                    row[

                        "total_races"

                    ],

                    row[

                        "avg_abs_spearman"

                    ],

                    (

                        f"{row['avg_high_leader_win_rate_pct']}%"

                    ),

                ]

                for index, row

                in enumerate(

                    top10

                )

            ],

        )

    else:

        lines.append(

            (

                "まだ比較可能な"

                "特徴量データが"

                "ありません。"

            )

        )

    lines += [

        "",

        "## 4. 直前要素の累計",

        "",

    ]

    factor_rows = []

    for key in (

        "exhibition_time",

        "exhibition_st",

    ):

        item = (

            live[

                "factors"

            ].get(

                key,

                {},

            )

        )

        factor_rows.append(

            [

                LIVE_LABELS[

                    key

                ],

                item.get(

                    "races",

                    0,

                ),

                (

                    f"{item.get('best_win_rate_pct')}%"

                    if item.get(

                        "best_win_rate_pct"

                    )

                    is not None

                    else "—"

                ),

                (

                    f"{item.get('worst_win_rate_pct')}%"

                    if item.get(

                        "worst_win_rate_pct"

                    )

                    is not None

                    else "—"

                ),

            ]

        )

    lines += markdown_table(

        [

            "要素",

            "R数",

            "最良艇1着率",

            "最悪艇1着率",

        ],

        factor_rows,

    )

    pooled = (

        live.get(

            "pooled_weight_search"

        )

        or {}

    )

    lines += [

        "",

        (

            "### 直近期間をまとめた"

            "直前重み探索"

        ),

        "",

    ]

    if pooled.get(

        "available"

    ):

        lines.append(

            (

                "- ベース1着率："

                f"{pooled.get('baseline_top1_accuracy_pct')}%"

            )

        )

        lines.append(

            (

                "- 比較R数："

                f"{pooled.get('races')}"

            )

        )

        lines.append(

            ""

        )

        lines += markdown_table(

            [

                "展示タイム",

                "展示ST",

                "F減点",

                "1着率",

                "改善pt",

            ],

            [

                [

                    row[

                        "exhibition_time_weight"

                    ],

                    row[

                        "exhibition_st_weight"

                    ],

                    row[

                        "f_penalty"

                    ],

                    (

                        f"{row['top1_accuracy_pct']}%"

                    ),

                    row[

                        "improvement_vs_baseline_pt"

                    ],

                ]

                for row

                in (

                    pooled.get(

                        "best_candidates"

                    )

                    or []

                )[:10]

            ],

        )

    else:

        lines.append(

            (

                "- まだ探索不可："

                f"{pooled.get('reason', 'データ不足')}"

            )

        )

    lines += [

        "",

        (

            "## 5. 不足データ・"

            "収集状況"

        ),

        "",

    ]

    lines += markdown_table(

        [

            "項目",

            "取得数",

            "取得率",

            "優先度",

        ],

        [

            [

                row[

                    "factor"

                ],

                row[

                    "coverage"

                ],

                (

                    f"{row['coverage_rate_pct']}%"

                ),

                row[

                    "priority"

                ],

            ]

            for row

            in missing

        ],

    )

    lines += [

        "",

        "## 6. PDCA運用ルール",

        "",

        (

            "- 毎日："

            "前日結果と予測を照合。"

        ),

        (

            "- 毎日："

            "フォーメーションと"

            "3艇BOX・AIスコア予測を別会計で集計。"

        ),

        (

            "- 毎日："

            "全特徴量を再評価し、"

            "TOP10を更新。"

        ),

        (

            "- 直近7日："

            "重み候補・不足データ・"

            "再現性を確認。"

        ),

        (

            "- 本番配点："

            "自動変更しない。"

            "複数日の再現性を"

            "確認してから"

            "変更候補として扱う。"

        ),

        "",

    ]

    md_path.write_text(

        "\n".join(

            lines

        )

        + "\n",

        encoding="utf-8",

    )

    print(

        "7日PDCAレポート生成: PASS"

    )

    print(

        json_path

    )

    print(

        md_path

    )

    return 0

if __name__ == "__main__":

    raise SystemExit(

        main()

    )