#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


def normalize_date(value: Any) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]

    digits = re.sub(r"\D", "", text)

    return (
        digits[:8]
        if len(digits) >= 8
        else text
    )


def venue(value: Any) -> str:
    try:
        return f"{int(float(value)):02d}"
    except Exception:
        return (
            str(value or "")
            .strip()
            .zfill(2)
        )


def to_float(
    value: Any,
) -> Optional[float]:
    if (
        value is None
        or isinstance(value, bool)
    ):
        return None

    try:
        number = float(
            str(value)
            .strip()
            .replace(",", "")
        )
    except Exception:
        return None

    return (
        number
        if math.isfinite(number)
        else None
    )


def parse_st(
    value: Any,
) -> Tuple[
    Optional[float],
    int,
]:
    text = (
        str(value or "")
        .strip()
        .upper()
        .replace(" ", "")
    )

    if not text:
        return None, 0

    flying = int(
        text.startswith("F")
    )

    late = int(
        text.startswith("L")
    )

    core = (
        text[1:]
        if flying or late
        else text
    )

    if core.startswith("."):
        core = "0" + core

    elif re.fullmatch(
        r"\d{1,2}",
        core,
    ):
        core = "0." + core

    try:
        number = float(core)

    except Exception:
        return None, flying

    if flying:
        number = -abs(number)

    elif late:
        number = abs(number)

    if not (
        -1
        < number
        < 1
    ):
        return None, flying

    return number, flying


def normalize_keys(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    dataframe = dataframe.copy()

    if (
        "date"
        in dataframe.columns
    ):
        dataframe[
            "date"
        ] = (
            dataframe[
                "date"
            ]
            .map(
                normalize_date
            )
            .astype(
                "string"
            )
        )

    if (
        "venue_code"
        in dataframe.columns
    ):
        dataframe[
            "venue_code"
        ] = (
            dataframe[
                "venue_code"
            ]
            .map(
                venue
            )
            .astype(
                "string"
            )
        )

    for column in (
        "race",
        "boat",
    ):
        if (
            column
            in dataframe.columns
        ):
            dataframe[
                column
            ] = (
                pd.to_numeric(
                    dataframe[
                        column
                    ],
                    errors="coerce",
                )
                .astype(
                    "Int64"
                )
            )

    return dataframe


def read_csvs(
    paths: List[Path],
) -> pd.DataFrame:
    frames = []

    for path in paths:
        try:
            frame = pd.read_csv(
                path
            )

        except Exception as exc:
            print(
                "skip:",
                path,
                exc,
            )
            continue

        frame[
            "_source_file"
        ] = str(path)

        frames.append(
            frame
        )

    if not frames:
        return pd.DataFrame()

    return pd.concat(
        frames,
        ignore_index=True,
        sort=False,
    )


def candidate_beforeinfo_files(
    date: str,
    kind: str,
) -> List[Path]:
    year = date[:4]
    month = date[4:6]
    day = date[6:8]

    filename = (
        f"beforeinfo_"
        f"{kind}_"
        f"{date}.csv"
    )

    patterns = [
        f"data/{filename}",
        (
            f"daily_inputs/"
            f"{year}/"
            f"{month}/"
            f"{day}/"
            f"live/**/"
            f"{filename}"
        ),
        (
            f"archive/"
            f"{year}/"
            f"{month}/"
            f"{day}/"
            f"pre_race/"
            f"beforeinfo/**/"
            f"{filename}"
        ),
    ]

    seen = set()
    paths: List[Path] = []

    for pattern in patterns:
        for path in (
            Path(".")
            .glob(
                pattern
            )
        ):
            if (
                path.is_file()
                and str(path)
                not in seen
            ):
                seen.add(
                    str(path)
                )

                paths.append(
                    path
                )

    return sorted(
        paths
    )


def load_beforeinfo(
    date: str,
) -> pd.DataFrame:
    entry_files = (
        candidate_beforeinfo_files(
            date,
            "entries",
        )
    )

    race_files = (
        candidate_beforeinfo_files(
            date,
            "races",
        )
    )

    print(
        "beforeinfo entry files:",
        len(entry_files),
    )

    print(
        "beforeinfo race files:",
        len(race_files),
    )

    entries = read_csvs(
        entry_files
    )

    races = read_csvs(
        race_files
    )

    if entries.empty:
        return pd.DataFrame()

    entries = normalize_keys(
        entries
    )

    if (
        "collected_at"
        in entries.columns
    ):
        entries[
            "_collected"
        ] = pd.to_datetime(
            entries[
                "collected_at"
            ],
            errors="coerce",
        )

    else:
        entries[
            "_collected"
        ] = pd.NaT

    entries = (
        entries
        .sort_values(
            [
                "date",
                "venue_code",
                "race",
                "boat",
                "_collected",
            ],
            na_position="first",
        )
        .drop_duplicates(
            [
                "date",
                "venue_code",
                "race",
                "boat",
            ],
            keep="last",
        )
    )

    live = entries[
        [
            "date",
            "venue_code",
            "race",
            "boat",
        ]
    ].copy()

    if (
        "exhibition_time"
        in entries.columns
    ):
        live[
            "exhibition_time"
        ] = pd.to_numeric(
            entries[
                "exhibition_time"
            ],
            errors="coerce",
        )

    if (
        "exhibition_course"
        in entries.columns
    ):
        live[
            "exhibition_course"
        ] = pd.to_numeric(
            entries[
                "exhibition_course"
            ],
            errors="coerce",
        )

    raw_series = (
        entries[
            "exhibition_st_raw"
        ]
        if (
            "exhibition_st_raw"
            in entries.columns
        )
        else pd.Series(
            "",
            index=entries.index,
        )
    )

    sec_series = (
        pd.to_numeric(
            entries[
                "exhibition_st_seconds"
            ],
            errors="coerce",
        )
        if (
            "exhibition_st_seconds"
            in entries.columns
        )
        else pd.Series(
            float("nan"),
            index=entries.index,
        )
    )

    flag_series = (
        entries[
            "exhibition_st_flag"
        ]
        .astype(str)
        .str.upper()
        if (
            "exhibition_st_flag"
            in entries.columns
        )
        else pd.Series(
            "",
            index=entries.index,
        )
    )

    st_values = []
    f_values = []

    for (
        raw,
        sec,
        flag,
    ) in zip(
        raw_series,
        sec_series,
        flag_series,
    ):
        (
            parsed,
            parsed_f,
        ) = parse_st(
            raw
        )

        if pd.notna(sec):
            st_value = float(
                sec
            )

        else:
            st_value = parsed

        f_flag = int(
            (
                str(flag)
                .upper()
                == "F"
            )
            or (
                str(raw)
                .strip()
                .upper()
                .startswith("F")
            )
            or parsed_f > 0
        )

        st_values.append(
            st_value
        )

        f_values.append(
            f_flag
        )

    live[
        "exhibition_st"
    ] = st_values

    live[
        "exhibition_f"
    ] = f_values

    if not races.empty:
        races = normalize_keys(
            races
        )

        if (
            "collected_at"
            in races.columns
        ):
            races[
                "_collected"
            ] = pd.to_datetime(
                races[
                    "collected_at"
                ],
                errors="coerce",
            )

        else:
            races[
                "_collected"
            ] = pd.NaT

        races = (
            races
            .sort_values(
                [
                    "date",
                    "venue_code",
                    "race",
                    "_collected",
                ],
                na_position="first",
            )
            .drop_duplicates(
                [
                    "date",
                    "venue_code",
                    "race",
                ],
                keep="last",
            )
        )

        weather = races[
            [
                "date",
                "venue_code",
                "race",
            ]
        ].copy()

        for source, target in (
            (
                "wind_speed_mps",
                "wind_speed",
            ),
            (
                "wind_direction",
                "wind_direction",
            ),
            (
                "wind_direction_code",
                "wind_direction_code",
            ),
            (
                "wave_height_cm",
                "wave_height",
            ),
        ):
            if (
                source
                in races.columns
            ):
                weather[
                    target
                ] = races[
                    source
                ]

        live = live.merge(
            weather,
            on=[
                "date",
                "venue_code",
                "race",
            ],
            how="left",
        )

    course = pd.to_numeric(
        live.get(
            "exhibition_course"
        ),
        errors="coerce",
    )

    boat = pd.to_numeric(
        live[
            "boat"
        ],
        errors="coerce",
    )

    live[
        "course_changed"
    ] = (
        (
            course
            != boat
        )
        .where(
            course.notna()
        )
        .astype(
            "Float64"
        )
    )

    return normalize_keys(
        live
    )


def load_results(
    date: str,
) -> pd.DataFrame:
    paths = [
        Path(
            f"data/"
            f"boat_results_"
            f"{date}_all.csv"
        ),
        Path(
            f"archive/"
            f"{date[:4]}/"
            f"{date[4:6]}/"
            f"{date[6:8]}/"
            f"boat_results_"
            f"{date}_all.csv"
        ),
    ]

    path = next(
        (
            item
            for item
            in paths
            if item.exists()
        ),
        None,
    )

    if path is None:
        raise SystemExit(
            "result csv not found"
        )

    dataframe = (
        normalize_keys(
            pd.read_csv(
                path
            )
        )
    )

    dataframe[
        "finish"
    ] = pd.to_numeric(
        dataframe[
            "finish"
        ],
        errors="coerce",
    )

    return (
        dataframe[
            [
                "date",
                "venue_code",
                "race",
                "boat",
                "finish",
            ]
        ]
        .dropna()
        .copy()
    )


def load_morning_scores(
    date: str,
) -> pd.DataFrame:
    path = Path(
        f"evaluations/"
        f"{date[:4]}/"
        f"{date[4:6]}/"
        f"{date[6:8]}/"
        f"score_answer_check_"
        f"boats_{date}.csv"
    )

    if not path.exists():
        raise SystemExit(
            "score answer-check "
            "csv not found"
        )

    dataframe = pd.read_csv(
        path
    )

    dataframe = (
        dataframe[
            dataframe[
                "stage"
            ]
            .astype(str)
            .str.lower()
            == "morning"
        ]
        .copy()
    )

    dataframe = normalize_keys(
        dataframe
    )

    dataframe[
        "total_score"
    ] = pd.to_numeric(
        dataframe[
            "total_score"
        ],
        errors="coerce",
    )

    return (
        dataframe[
            [
                "date",
                "venue_code",
                "race",
                "boat",
                "total_score",
            ]
        ]
        .dropna()
        .copy()
    )


def rank_metric(
    dataframe: pd.DataFrame,
    column: str,
    lower_better: bool = True,
    exclude_f: bool = False,
) -> Dict[str, Any]:
    if (
        column
        not in dataframe.columns
    ):
        return {
            "available": False,
            "reason": (
                "column not found"
            ),
        }

    needed = [
        "date",
        "venue_code",
        "race",
        "finish",
        column,
    ]

    if (
        exclude_f
        and "exhibition_f"
        in dataframe.columns
    ):
        needed.append(
            "exhibition_f"
        )

    work = dataframe[
        needed
    ].copy()

    work[
        column
    ] = pd.to_numeric(
        work[
            column
        ],
        errors="coerce",
    )

    if (
        exclude_f
        and "exhibition_f"
        in work.columns
    ):
        flags = pd.to_numeric(
            work[
                "exhibition_f"
            ],
            errors="coerce",
        ).fillna(0)

        work.loc[
            flags > 0,
            column,
        ] = pd.NA

    work = work.dropna(
        subset=[
            "finish",
            column,
        ]
    )

    rows = []
    correlations = []

    for _, race_data in (
        work.groupby(
            [
                "date",
                "venue_code",
                "race",
            ]
        )
    ):
        if (
            len(
                race_data
            ) < 4
            or race_data[
                column
            ].nunique()
            < 2
        ):
            continue

        ordered = (
            race_data
            .sort_values(
                column,
                ascending=(
                    lower_better
                ),
            )
        )

        best = (
            ordered.iloc[0]
        )

        worst = (
            ordered.iloc[-1]
        )

        rows.append(
            {
                "best_finish": float(
                    best[
                        "finish"
                    ]
                ),
                "worst_finish": float(
                    worst[
                        "finish"
                    ]
                ),
            }
        )

        factor_rank = (
            race_data[
                column
            ]
            .rank(
                method="average",
                ascending=(
                    lower_better
                ),
            )
        )

        correlation = (
            factor_rank
            .corr(
                race_data[
                    "finish"
                ],
                method="spearman",
            )
        )

        if not pd.isna(
            correlation
        ):
            correlations.append(
                float(
                    correlation
                )
            )

    if not rows:
        return {
            "available": True,
            "races": 0,
        }

    return {
        "available": True,
        "races": len(
            rows
        ),
        "best_win_rate_pct": (
            round(
                sum(
                    row[
                        "best_finish"
                    ]
                    == 1
                    for row
                    in rows
                )
                / len(
                    rows
                )
                * 100,
                1,
            )
        ),
        "best_top3_rate_pct": (
            round(
                sum(
                    row[
                        "best_finish"
                    ]
                    <= 3
                    for row
                    in rows
                )
                / len(
                    rows
                )
                * 100,
                1,
            )
        ),
        "worst_win_rate_pct": (
            round(
                sum(
                    row[
                        "worst_finish"
                    ]
                    == 1
                    for row
                    in rows
                )
                / len(
                    rows
                )
                * 100,
                1,
            )
        ),
        "mean_within_race_spearman": (
            round(
                sum(
                    correlations
                )
                / len(
                    correlations
                ),
                4,
            )
            if correlations
            else None
        ),
    }


def binary_metric(
    dataframe: pd.DataFrame,
    column: str,
) -> Dict[str, Any]:
    if (
        column
        not in dataframe.columns
    ):
        return {
            "available": False,
            "reason": (
                "column not found"
            ),
        }

    work = dataframe[
        [
            "finish",
            column,
        ]
    ].copy()

    work[
        column
    ] = pd.to_numeric(
        work[
            column
        ],
        errors="coerce",
    )

    work.dropna(
        inplace=True
    )

    if work.empty:
        return {
            "available": True,
            "boats": 0,
        }

    flagged = work[
        work[
            column
        ] > 0
    ]

    normal = work[
        work[
            column
        ] <= 0
    ]

    return {
        "available": True,
        "boats": len(
            work
        ),
        "flagged_boats": len(
            flagged
        ),
        "flagged_win_rate_pct": (
            round(
                (
                    flagged[
                        "finish"
                    ]
                    == 1
                )
                .mean()
                * 100,
                1,
            )
            if len(
                flagged
            )
            else None
        ),
        "flagged_top3_rate_pct": (
            round(
                (
                    flagged[
                        "finish"
                    ]
                    <= 3
                )
                .mean()
                * 100,
                1,
            )
            if len(
                flagged
            )
            else None
        ),
        "unflagged_win_rate_pct": (
            round(
                (
                    normal[
                        "finish"
                    ]
                    == 1
                )
                .mean()
                * 100,
                1,
            )
            if len(
                normal
            )
            else None
        ),
        "unflagged_top3_rate_pct": (
            round(
                (
                    normal[
                        "finish"
                    ]
                    <= 3
                )
                .mean()
                * 100,
                1,
            )
            if len(
                normal
            )
            else None
        ),
    }


def wind_analysis(
    dataframe: pd.DataFrame,
) -> List[
    Dict[str, Any]
]:
    if (
        "wind_speed"
        not in dataframe.columns
    ):
        return []

    work = (
        dataframe
        .dropna(
            subset=[
                "wind_speed",
                "finish",
            ]
        )
        .copy()
    )

    rows = []

    for _, race_data in (
        work.groupby(
            [
                "date",
                "venue_code",
                "race",
            ]
        )
    ):
        values = (
            pd.to_numeric(
                race_data[
                    "wind_speed"
                ],
                errors="coerce",
            )
            .dropna()
        )

        if values.empty:
            continue

        wind_speed = float(
            values.iloc[0]
        )

        if wind_speed < 3:
            bucket = "0-2m"

        elif wind_speed < 5:
            bucket = "3-4m"

        else:
            bucket = "5m以上"

        boat1 = race_data[
            race_data[
                "boat"
            ]
            == 1
        ]

        if boat1.empty:
            continue

        rows.append(
            {
                "bucket": bucket,
                "boat1_win": int(
                    float(
                        boat1.iloc[
                            0
                        ][
                            "finish"
                        ]
                    )
                    == 1
                ),
            }
        )

    output = []

    for bucket in (
        "0-2m",
        "3-4m",
        "5m以上",
    ):
        values = [
            row
            for row
            in rows
            if row[
                "bucket"
            ]
            == bucket
        ]

        if not values:
            continue

        output.append(
            {
                "bucket": bucket,
                "races": len(
                    values
                ),
                "boat1_win_rate_pct": (
                    round(
                        sum(
                            row[
                                "boat1_win"
                            ]
                            for row
                            in values
                        )
                        / len(
                            values
                        )
                        * 100,
                        1,
                    )
                ),
            }
        )

    return output


def normalize_factor(
    race_data: pd.DataFrame,
    column: str,
    lower_better: bool,
    neutral_mask: Optional[
        pd.Series
    ] = None,
) -> pd.Series:
    values = pd.to_numeric(
        race_data[
            column
        ],
        errors="coerce",
    )

    if neutral_mask is not None:
        values = values.mask(
            neutral_mask
        )

    valid = values.dropna()

    if len(
        valid
    ) < 2:
        return pd.Series(
            0.5,
            index=race_data.index,
        )

    minimum = valid.min()
    maximum = valid.max()

    if (
        pd.isna(minimum)
        or pd.isna(maximum)
        or minimum
        == maximum
    ):
        return pd.Series(
            0.5,
            index=race_data.index,
        )

    result = (
        (
            values
            - minimum
        )
        /
        (
            maximum
            - minimum
        )
    )

    if lower_better:
        result = (
            1
            - result
        )

    return result.fillna(
        0.5
    )


def weight_search(
    dataframe: pd.DataFrame,
) -> Dict[str, Any]:
    if (
        "total_score"
        not in dataframe.columns
    ):
        return {
            "available": False
        }

    time_available = (
        "exhibition_time"
        in dataframe.columns
        and dataframe[
            "exhibition_time"
        ]
        .notna()
        .sum()
        > 0
    )

    st_available = (
        "exhibition_st"
        in dataframe.columns
        and dataframe[
            "exhibition_st"
        ]
        .notna()
        .sum()
        > 0
    )

    f_available = (
        "exhibition_f"
        in dataframe.columns
        and pd.to_numeric(
            dataframe[
                "exhibition_f"
            ],
            errors="coerce",
        )
        .fillna(0)
        .gt(0)
        .any()
    )

    available_factors = []

    if time_available:
        available_factors.append(
            "exhibition_time"
        )

    if st_available:
        available_factors.append(
            "exhibition_st"
        )

    if f_available:
        available_factors.append(
            "exhibition_f"
        )

    if not available_factors:
        return {
            "available": False,
            "available_factors": [],
            "reason": (
                "展示タイム・ST・Fの"
                "有効データなし"
            ),
        }

    work = (
        dataframe
        .dropna(
            subset=[
                "total_score",
                "finish",
            ]
        )
        .copy()
    )

    if work.empty:
        return {
            "available": False,
            "available_factors": (
                available_factors
            ),
        }

    if (
        "exhibition_f"
        not in work.columns
    ):
        work[
            "exhibition_f"
        ] = 0.0

    else:
        work[
            "exhibition_f"
        ] = pd.to_numeric(
            work[
                "exhibition_f"
            ],
            errors="coerce",
        ).fillna(
            0.0
        )

    work[
        "time_norm"
    ] = 0.5

    work[
        "st_norm"
    ] = 0.5

    for _, indexes in (
        work.groupby(
            [
                "date",
                "venue_code",
                "race",
            ]
        )
        .groups
        .items()
    ):
        race_data = (
            work.loc[
                indexes
            ]
        )

        if time_available:
            work.loc[
                indexes,
                "time_norm",
            ] = normalize_factor(
                race_data,
                "exhibition_time",
                True,
            )

        if st_available:
            work.loc[
                indexes,
                "st_norm",
            ] = normalize_factor(
                race_data,
                "exhibition_st",
                True,
                neutral_mask=(
                    race_data[
                        "exhibition_f"
                    ]
                    > 0
                ),
            )

    valid_races = []

    for (
        race_key,
        race_data,
    ) in (
        work.groupby(
            [
                "date",
                "venue_code",
                "race",
            ]
        )
    ):
        if len(
            race_data
        ) >= 4:
            valid_races.append(
                race_key
            )

    valid_set = set(
        valid_races
    )

    work = (
        work[
            work.apply(
                lambda row: (
                    row[
                        "date"
                    ],
                    row[
                        "venue_code"
                    ],
                    row[
                        "race"
                    ],
                )
                in valid_set,
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
        test = work.copy()

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
            "adjusted_score"
        ] = score

        wins = 0
        races = 0

        for _, race_data in (
            test.groupby(
                [
                    "date",
                    "venue_code",
                    "race",
                ]
            )
        ):
            top = (
                race_data
                .sort_values(
                    "adjusted_score",
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

        return (
            wins
            / races
            * 100
            if races
            else 0.0
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
                    time_weight
                    == 0
                    and st_weight
                    == 0
                    and f_penalty
                    == 0
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

    candidates = sorted(
        candidates,
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
        "available_factors": (
            available_factors
        ),
        "races": len(
            valid_races
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


def main() -> int:
    parser = (
        argparse.ArgumentParser()
    )

    parser.add_argument(
        "--date",
        required=True,
    )

    args = parser.parse_args()

    date = normalize_date(
        args.date
    )

    if not re.fullmatch(
        r"\d{8}",
        date,
    ):
        raise SystemExit(
            "--date must be YYYYMMDD"
        )

    print("")
    print(
        "========================================"
    )
    print(
        "直前情報5項目 個別分析開始"
    )
    print(
        "========================================"
    )

    live = load_beforeinfo(
        date
    )

    if live.empty:
        raise SystemExit(
            "直前情報データを"
            "1件も検出できませんでした"
        )

    results = load_results(
        date
    )

    scores = load_morning_scores(
        date
    )

    keys = [
        "date",
        "venue_code",
        "race",
        "boat",
    ]

    dataframe = (
        results
        .merge(
            live,
            on=keys,
            how="left",
        )
        .merge(
            scores,
            on=keys,
            how="left",
        )
    )

    coverage = {}

    for column in (
        "exhibition_time",
        "exhibition_st",
        "exhibition_f",
        "exhibition_course",
        "course_changed",
        "wind_speed",
        "wind_direction",
        "wave_height",
    ):
        coverage[
            column
        ] = (
            int(
                dataframe[
                    column
                ]
                .notna()
                .sum()
            )
            if (
                column
                in dataframe.columns
            )
            else 0
        )

    report = {
        "date": date,
        "coverage": coverage,
        "factors": {
            "exhibition_time": (
                rank_metric(
                    dataframe,
                    "exhibition_time",
                    True,
                )
            ),
            "exhibition_st": (
                rank_metric(
                    dataframe,
                    "exhibition_st",
                    True,
                    exclude_f=True,
                )
            ),
            "exhibition_f": (
                binary_metric(
                    dataframe,
                    "exhibition_f",
                )
            ),
            "course_changed": (
                binary_metric(
                    dataframe,
                    "course_changed",
                )
            ),
        },
        "wind_context": (
            wind_analysis(
                dataframe
            )
        ),
        "weight_search": (
            weight_search(
                dataframe
            )
        ),
    }

    output_dir = (
        Path(
            "evaluations"
        )
        / date[:4]
        / date[4:6]
        / date[6:8]
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_path = (
        output_dir
        / (
            "live_factor_analysis_"
            f"{date}.json"
        )
    )

    markdown_path = (
        output_dir
        / (
            "live_factor_analysis_"
            f"{date}.md"
        )
    )

    csv_path = (
        output_dir
        / (
            "live_factor_answer_check_"
            f"{date}.csv"
        )
    )

    json_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    dataframe.to_csv(
        csv_path,
        index=False,
        encoding="utf-8-sig",
    )

    markdown = [
        (
            "# 直前情報5項目 "
            "個別答え合わせ"
        ),
        "",
        (
            f"対象日："
            f"{date[:4]}/"
            f"{date[4:6]}/"
            f"{date[6:8]}"
        ),
        "",
        "## 取得カバレッジ",
        "",
    ]

    for key, value in (
        coverage.items()
    ):
        markdown.append(
            f"- {key}: {value}"
        )

    markdown += [
        "",
        "## 個別要素分析",
        "",
        "```json",
        json.dumps(
            report[
                "factors"
            ],
            ensure_ascii=False,
            indent=2,
        ),
        "```",
        "",
        "## 風速別",
        "",
        "```json",
        json.dumps(
            report[
                "wind_context"
            ],
            ensure_ascii=False,
            indent=2,
        ),
        "```",
        "",
        (
            "## 展示タイム・"
            "ST・F 重み探索"
        ),
        "",
        (
            "> これは候補探索です。"
            "1日だけの結果で"
            "本番配点は"
            "自動変更しません。"
        ),
        "",
        "```json",
        json.dumps(
            report[
                "weight_search"
            ],
            ensure_ascii=False,
            indent=2,
        ),
        "```",
        "",
    ]

    markdown_path.write_text(
        "\n".join(
            markdown
        )
        + "\n",
        encoding="utf-8",
    )

    print("")
    print(
        "========================================"
    )
    print(
        "直前情報個別分析: PASS"
    )
    print(
        "========================================"
    )

    print("")
    print(
        "coverage:"
    )

    print(
        json.dumps(
            coverage,
            ensure_ascii=False,
            indent=2,
        )
    )

    print("")
    print(
        "weight_search:"
    )

    print(
        json.dumps(
            report[
                "weight_search"
            ],
            ensure_ascii=False,
            indent=2,
        )
    )

    print("")
    print(
        "JSON:",
        json_path
    )

    print(
        "Markdown:",
        markdown_path
    )

    print(
        "CSV:",
        csv_path
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )