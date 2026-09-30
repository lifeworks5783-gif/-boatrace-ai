#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


ALIASES = {
    "exhibition_time": (
        "exhibition_time",
        "tenji_time",
        "display_time",
        "exhibit_time",
        "tenjiTime",
    ),
    "exhibition_st": (
        "exhibition_st",
        "tenji_st",
        "display_st",
        "start_exhibition_st",
        "start_timing",
        "exhibitionStart",
    ),
    "exhibition_course": (
        "exhibition_course",
        "tenji_course",
        "display_course",
        "start_exhibition_course",
        "course",
    ),
    "wind_speed": (
        "wind_speed",
        "windSpeed",
        "wind_mps",
        "windspeed",
    ),
    "wind_direction": (
        "wind_direction",
        "windDirection",
        "wind_dir",
        "wind",
    ),
    "wave_height": (
        "wave_height",
        "waveHeight",
        "wave_cm",
        "wave",
    ),
}

PATH_HINTS = (
    "beforeinfo",
    "before_info",
    "exhibition",
    "tenji",
    "display",
    "start_exhibition",
    "live",
    "prediction_input",
)


def nkey(
    value: Any,
) -> str:

    return re.sub(
        r"[^a-z0-9]+",
        "_",
        str(value)
        .strip()
        .lower(),
    ).strip("_")


def to_float(
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

    if isinstance(
        value,
        (
            int,
            float,
        ),
    ):

        if (
            isinstance(
                value,
                float,
            )
            and math.isnan(
                value
            )
        ):
            return None

        return float(value)

    text = (
        str(value)
        .strip()
        .replace(",", "")
        .replace("秒", "")
        .replace("cm", "")
        .replace("m", "")
    )

    match = re.search(
        r"-?\d+(?:\.\d+)?",
        text,
    )

    if not match:
        return None

    return float(
        match.group()
    )


def parse_st(
    value: Any,
) -> Tuple[
    Optional[float],
    int,
]:

    if value is None:
        return (
            None,
            0,
        )

    text = (
        str(value)
        .strip()
        .upper()
        .replace(" ", "")
    )

    if not text:
        return (
            None,
            0,
        )

    flying = (
        1
        if text.startswith("F")
        else 0
    )

    match = re.search(
        r"\d+(?:\.\d+)?",
        text,
    )

    if not match:
        return (
            None,
            flying,
        )

    number = float(
        match.group()
    )

    if (
        number >= 1
        and "."
        not in match.group()
    ):
        number = (
            number / 100.0
        )

    if flying:
        number = -abs(
            number
        )

    return (
        number,
        flying,
    )


def venue(
    value: Any,
) -> str:

    try:

        return (
            f"{int(float(value)):02d}"
        )

    except Exception:

        return str(
            value or ""
        ).zfill(2)


def iv(
    value: Any,
) -> Optional[int]:

    try:

        return int(
            float(value)
        )

    except Exception:

        return None


def parse_race_id(
    value: Any,
) -> Tuple[
    str,
    str,
    Optional[int],
]:

    match = re.search(
        r"(\d{8})[-_](\d{2})[-_](\d{1,2})",
        str(
            value
            or ""
        ),
    )

    if not match:

        return (
            "",
            "",
            None,
        )

    return (
        match.group(1),
        match.group(2),
        int(
            match.group(3)
        ),
    )


def candidate_files(
    date: str,
) -> List[Path]:

    year = date[:4]
    month = date[4:6]
    day = date[6:8]

    patterns = [
        f"data/**/*{date}*.json",
        f"data/**/*{date}*.csv",

        (
            f"daily_inputs/"
            f"{year}/"
            f"{month}/"
            f"{day}/"
            f"**/*.json"
        ),

        (
            f"daily_inputs/"
            f"{year}/"
            f"{month}/"
            f"{day}/"
            f"**/*.csv"
        ),

        (
            f"predictions/"
            f"{year}/"
            f"{month}/"
            f"{day}/"
            f"live/**/*.json"
        ),

        (
            f"predictions/"
            f"{year}/"
            f"{month}/"
            f"{day}/"
            f"live/**/*.csv"
        ),
    ]

    output = []
    seen = set()

    for pattern in patterns:

        for path in Path(
            "."
        ).glob(
            pattern
        ):

            path_text = str(
                path
            ).lower()

            if (
                not path.is_file()
                or path_text
                in seen
            ):
                continue

            if not any(
                hint in path_text
                for hint
                in PATH_HINTS
            ):
                continue

            if any(
                bad in path_text
                for bad
                in (
                    "result",
                    "evaluation",
                    "formation",
                    "payout",
                )
            ):
                continue

            seen.add(
                path_text
            )

            output.append(
                path
            )

    return output


def walk_records(
    obj: Any,
    date: str,
    source: str,
) -> List[
    Dict[
        str,
        Any,
    ]
]:

    rows = []

    def walk(
        node: Any,
        context: Dict[
            str,
            Any,
        ],
        path: str,
    ) -> None:

        if isinstance(
            node,
            dict,
        ):

            current = dict(
                context
            )

            if "race_id" in node:

                (
                    date_value,
                    venue_value,
                    race_value,
                ) = parse_race_id(
                    node.get(
                        "race_id"
                    )
                )

                if date_value:
                    current[
                        "date"
                    ] = date_value

                if venue_value:
                    current[
                        "venue_code"
                    ] = venue_value

                if race_value is not None:
                    current[
                        "race"
                    ] = race_value

            for (
                key,
                target,
            ) in (
                (
                    "date",
                    "date",
                ),
                (
                    "target_date",
                    "date",
                ),
                (
                    "venue_code",
                    "venue_code",
                ),
                (
                    "jcd",
                    "venue_code",
                ),
                (
                    "race",
                    "race",
                ),
                (
                    "rno",
                    "race",
                ),
            ):

                if (
                    key in node
                    and not isinstance(
                        node[key],
                        (
                            dict,
                            list,
                        ),
                    )
                ):

                    current[
                        target
                    ] = node[key]

            boat = None

            for key in (
                "boat",
                "frame",
                "lane",
                "boat_no",
                "wakuban",
            ):

                if key not in node:
                    continue

                value = iv(
                    node.get(key)
                )

                if (
                    value is not None
                    and 1
                    <= value
                    <= 6
                ):

                    boat = value

                    break

            flat = {}

            def flatten(
                value: Any,
                prefix: str,
            ) -> None:

                if not isinstance(
                    value,
                    dict,
                ):
                    return

                for (
                    child_key,
                    child_value,
                ) in value.items():

                    child_path = (
                        f"{prefix}."
                        f"{nkey(child_key)}"
                        if prefix
                        else nkey(
                            child_key
                        )
                    )

                    if isinstance(
                        child_value,
                        dict,
                    ):

                        flatten(
                            child_value,
                            child_path,
                        )

                    elif not isinstance(
                        child_value,
                        list,
                    ):

                        flat[
                            child_path
                        ] = child_value

            flatten(
                node,
                "",
            )

            features = {}

            for (
                feature_path,
                value,
            ) in flat.items():

                leaf = (
                    feature_path
                    .split(".")[-1]
                )

                path_lower = (
                    feature_path
                    .lower()
                )

                hinted = (
                    any(
                        hint
                        in path_lower
                        for hint
                        in PATH_HINTS
                    )
                    or
                    any(
                        hint
                        in source.lower()
                        for hint
                        in PATH_HINTS
                    )
                )

                if not hinted:
                    continue

                if leaf in [
                    nkey(x)
                    for x
                    in ALIASES[
                        "exhibition_time"
                    ]
                ]:

                    number = to_float(
                        value
                    )

                    if (
                        number is not None
                        and 5
                        < number
                        < 15
                    ):

                        features[
                            "exhibition_time"
                        ] = number

                if leaf in [
                    nkey(x)
                    for x
                    in ALIASES[
                        "exhibition_st"
                    ]
                ]:

                    (
                        number,
                        flying,
                    ) = parse_st(
                        value
                    )

                    if (
                        number is not None
                        and -1
                        < number
                        < 1
                    ):

                        features[
                            "exhibition_st"
                        ] = number

                        features[
                            "exhibition_f"
                        ] = max(
                            features.get(
                                "exhibition_f",
                                0,
                            ),
                            flying,
                        )

                if leaf in [
                    nkey(x)
                    for x
                    in ALIASES[
                        "exhibition_course"
                    ]
                ]:

                    number = iv(
                        value
                    )

                    if (
                        number is not None
                        and 1
                        <= number
                        <= 6
                    ):

                        features[
                            "exhibition_course"
                        ] = number

                if leaf in [
                    nkey(x)
                    for x
                    in ALIASES[
                        "wind_speed"
                    ]
                ]:

                    number = to_float(
                        value
                    )

                    if (
                        number is not None
                        and 0
                        <= number
                        <= 50
                    ):

                        features[
                            "wind_speed"
                        ] = number

                if leaf in [
                    nkey(x)
                    for x
                    in ALIASES[
                        "wave_height"
                    ]
                ]:

                    number = to_float(
                        value
                    )

                    if (
                        number is not None
                        and 0
                        <= number
                        <= 200
                    ):

                        features[
                            "wave_height"
                        ] = number

                if leaf in [
                    nkey(x)
                    for x
                    in ALIASES[
                        "wind_direction"
                    ]
                ]:

                    if (
                        isinstance(
                            value,
                            str,
                        )
                        and value.strip()
                    ):

                        features[
                            "wind_direction"
                        ] = value.strip()

                if (
                    "flying"
                    in leaf
                    or leaf
                    in (
                        "f",
                        "is_f",
                        "exhibition_f",
                        "tenji_f",
                    )
                ):

                    text = (
                        str(value)
                        .strip()
                        .lower()
                    )

                    if (
                        text
                        in (
                            "1",
                            "true",
                            "yes",
                            "f",
                        )
                        or (
                            to_float(
                                value
                            )
                            or 0
                        )
                        > 0
                    ):

                        features[
                            "exhibition_f"
                        ] = 1

            if (
                boat is not None
                and current.get(
                    "race"
                )
                is not None
                and features
            ):

                rows.append(
                    {
                        "date":
                            str(
                                current.get(
                                    "date",
                                    date,
                                )
                            ),

                        "venue_code":
                            venue(
                                current.get(
                                    "venue_code",
                                    "",
                                )
                            ),

                        "race":
                            iv(
                                current.get(
                                    "race"
                                )
                            ),

                        "boat":
                            boat,

                        "source":
                            source,

                        **features,
                    }
                )

            for (
                key,
                value,
            ) in node.items():

                if isinstance(
                    value,
                    (
                        dict,
                        list,
                    ),
                ):

                    child_path = (
                        f"{path}."
                        f"{nkey(key)}"
                        if path
                        else nkey(key)
                    )

                    walk(
                        value,
                        current,
                        child_path,
                    )

        elif isinstance(
            node,
            list,
        ):

            for value in node:

                walk(
                    value,
                    context,
                    path,
                )

    walk(
        obj,
        {
            "date":
                date
        },
        "",
    )

    return rows


def load_recorded_beforeinfo(
    date: str,
) -> pd.DataFrame:

    all_rows = []

    for path in candidate_files(
        date
    ):

        try:

            if (
                path.suffix.lower()
                == ".json"
            ):

                obj = json.loads(
                    path.read_text(
                        encoding="utf-8"
                    )
                )

                all_rows.extend(
                    walk_records(
                        obj,
                        date,
                        str(path),
                    )
                )

            elif (
                path.suffix.lower()
                == ".csv"
            ):

                dataframe = pd.read_csv(
                    path
                )

                columns = {
                    nkey(column):
                        column
                    for column
                    in dataframe.columns
                }

                for (
                    _,
                    row,
                ) in dataframe.iterrows():

                    venue_value = (
                        row.get(
                            columns.get(
                                "venue_code",
                                columns.get(
                                    "jcd",
                                    "",
                                ),
                            ),
                            "",
                        )
                        if (
                            "venue_code"
                            in columns
                            or
                            "jcd"
                            in columns
                        )
                        else ""
                    )

                    race_value = (
                        row.get(
                            columns.get(
                                "race",
                                columns.get(
                                    "rno",
                                    "",
                                ),
                            ),
                            None,
                        )
                        if (
                            "race"
                            in columns
                            or
                            "rno"
                            in columns
                        )
                        else None
                    )

                    boat_value = (
                        row.get(
                            columns.get(
                                "boat",
                                columns.get(
                                    "frame",
                                    columns.get(
                                        "lane",
                                        "",
                                    ),
                                ),
                            ),
                            None,
                        )
                        if (
                            "boat"
                            in columns
                            or
                            "frame"
                            in columns
                            or
                            "lane"
                            in columns
                        )
                        else None
                    )

                    race_number = iv(
                        race_value
                    )

                    boat_number = iv(
                        boat_value
                    )

                    if (
                        race_number is None
                        or boat_number is None
                        or not 1
                        <= boat_number
                        <= 6
                    ):

                        continue

                    features = {}

                    for (
                        canonical,
                        aliases,
                    ) in ALIASES.items():

                        for alias in aliases:

                            alias_key = (
                                nkey(alias)
                            )

                            if (
                                alias_key
                                not in columns
                            ):
                                continue

                            value = row.get(
                                columns[
                                    alias_key
                                ]
                            )

                            if (
                                canonical
                                == "exhibition_st"
                            ):

                                (
                                    number,
                                    flying,
                                ) = parse_st(
                                    value
                                )

                                if number is not None:

                                    features[
                                        "exhibition_st"
                                    ] = number

                                    features[
                                        "exhibition_f"
                                    ] = max(
                                        features.get(
                                            "exhibition_f",
                                            0,
                                        ),
                                        flying,
                                    )

                            elif (
                                canonical
                                == "exhibition_course"
                            ):

                                number = iv(
                                    value
                                )

                                if (
                                    number is not None
                                    and 1
                                    <= number
                                    <= 6
                                ):

                                    features[
                                        canonical
                                    ] = number

                            elif canonical in (
                                "exhibition_time",
                                "wind_speed",
                                "wave_height",
                            ):

                                number = to_float(
                                    value
                                )

                                if number is not None:

                                    features[
                                        canonical
                                    ] = number

                            elif (
                                canonical
                                == "wind_direction"
                                and pd.notna(
                                    value
                                )
                            ):

                                features[
                                    canonical
                                ] = str(value)

                            break

                    if features:

                        all_rows.append(
                            {
                                "date":
                                    date,

                                "venue_code":
                                    venue(
                                        venue_value
                                    ),

                                "race":
                                    race_number,

                                "boat":
                                    boat_number,

                                "source":
                                    str(path),

                                **features,
                            }
                        )

        except Exception:

            continue

    if not all_rows:
        return pd.DataFrame()

    dataframe = pd.DataFrame(
        all_rows
    )

    keys = [
        "date",
        "venue_code",
        "race",
        "boat",
    ]

    feature_columns = [
        column
        for column
        in dataframe.columns
        if column
        not in (
            keys
            + [
                "source"
            ]
        )
    ]

    dataframe[
        "_complete"
    ] = (
        dataframe[
            feature_columns
        ]
        .notna()
        .sum(
            axis=1
        )
    )

    dataframe = (
        dataframe
        .sort_values(
            [
                "_complete",
                "source",
            ]
        )
        .drop_duplicates(
            keys,
            keep="last",
        )
        .drop(
            columns=[
                "_complete"
            ]
        )
    )

    return dataframe


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
            path
            for path
            in paths
            if path.exists()
        ),
        None,
    )

    if path is None:

        raise SystemExit(
            "result csv not found"
        )

    dataframe = pd.read_csv(
        path
    )

    for column in (
        "race",
        "boat",
        "finish",
    ):

        dataframe[
            column
        ] = pd.to_numeric(
            dataframe[
                column
            ],
            errors="coerce",
        )

    dataframe[
        "date"
    ] = (
        dataframe[
            "date"
        ]
        .astype(str)
        .str.replace(
            ".0",
            "",
            regex=False,
        )
    )

    dataframe[
        "venue_code"
    ] = (
        dataframe[
            "venue_code"
        ]
        .map(
            venue
        )
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
    )


def load_base_scores(
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
            "score answer-check csv not found"
        )

    dataframe = pd.read_csv(
        path
    )

    dataframe = dataframe[
        dataframe[
            "stage"
        ].astype(str)
        == "morning"
    ].copy()

    dataframe[
        "venue_code"
    ] = (
        dataframe[
            "venue_code"
        ]
        .map(
            venue
        )
    )

    for column in (
        "race",
        "boat",
        "total_score",
    ):

        dataframe[
            column
        ] = pd.to_numeric(
            dataframe[
                column
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
    )


def rank_metric(
    dataframe: pd.DataFrame,
    column: str,
    lower_better: bool = True,
) -> Dict[str, Any]:

    work = (
        dataframe[
            [
                "venue_code",
                "race",
                "boat",
                "finish",
                column,
            ]
        ]
        .dropna()
        .copy()
    )

    rows = []
    correlations = []

    for (
        _,
        race_data,
    ) in work.groupby(
        [
            "venue_code",
            "race",
        ]
    ):

        if (
            len(
                race_data
            )
            < 4
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
                ascending=lower_better,
            )
        )

        best = (
            ordered.iloc[0]
        )

        worst = (
            ordered.iloc[-1]
        )

        rows.append(
            (
                best[
                    "finish"
                ],
                worst[
                    "finish"
                ],
            )
        )

        feature_rank = (
            ordered[
                column
            ]
            .rank(
                ascending=lower_better,
                method="average",
            )
        )

        correlation = (
            feature_rank
            .corr(
                ordered[
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
        return {}

    return {
        "races":
            len(rows),

        "best_win_rate_pct":
            round(
                sum(
                    best == 1
                    for best, _
                    in rows
                )
                / len(rows)
                * 100,
                1,
            ),

        "best_top3_rate_pct":
            round(
                sum(
                    best <= 3
                    for best, _
                    in rows
                )
                / len(rows)
                * 100,
                1,
            ),

        "worst_win_rate_pct":
            round(
                sum(
                    worst == 1
                    for _, worst
                    in rows
                )
                / len(rows)
                * 100,
                1,
            ),

        "mean_within_race_spearman":
            (
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

    work = (
        dataframe[
            [
                "finish",
                column,
            ]
        ]
        .dropna()
        .copy()
    )

    if work.empty:
        return {}

    flagged = work[
        work[
            column
        ].astype(float)
        > 0
    ]

    normal = work[
        work[
            column
        ].astype(float)
        <= 0
    ]

    return {
        "boats":
            len(work),

        "flagged_boats":
            len(flagged),

        "flagged_win_rate_pct":
            (
                round(
                    (
                        flagged[
                            "finish"
                        ]
                        == 1
                    ).mean()
                    * 100,
                    1,
                )
                if len(
                    flagged
                )
                else None
            ),

        "flagged_top3_rate_pct":
            (
                round(
                    (
                        flagged[
                            "finish"
                        ]
                        <= 3
                    ).mean()
                    * 100,
                    1,
                )
                if len(
                    flagged
                )
                else None
            ),

        "unflagged_win_rate_pct":
            (
                round(
                    (
                        normal[
                            "finish"
                        ]
                        == 1
                    ).mean()
                    * 100,
                    1,
                )
                if len(
                    normal
                )
                else None
            ),

        "unflagged_top3_rate_pct":
            (
                round(
                    (
                        normal[
                            "finish"
                        ]
                        <= 3
                    ).mean()
                    * 100,
                    1,
                )
                if len(
                    normal
                )
                else None
            ),
    }


def normalize_within_race(
    dataframe: pd.DataFrame,
    column: str,
    lower_better: bool,
) -> pd.Series:

    values = pd.to_numeric(
        dataframe[
            column
        ],
        errors="coerce",
    )

    if (
        values
        .notna()
        .sum()
        < 2
    ):

        return pd.Series(
            0.0,
            index=dataframe.index,
        )

    minimum = values.min()
    maximum = values.max()

    if maximum == minimum:

        return pd.Series(
            0.5,
            index=dataframe.index,
        )

    normalized = (
        values
        - minimum
    ) / (
        maximum
        - minimum
    )

    if lower_better:

        return (
            1
            - normalized
        )

    return normalized


def simulate(
    dataframe: pd.DataFrame,
) -> Dict[str, Any]:

    required = [
        "total_score",
        "finish",
        "exhibition_time",
        "exhibition_st",
    ]

    work = (
        dataframe
        .dropna(
            subset=required
        )
        .copy()
    )

    if work.empty:
        return {}

    eligible = []

    for (
        race_key,
        race_data,
    ) in work.groupby(
        [
            "venue_code",
            "race",
        ]
    ):

        if len(
            race_data
        ) >= 4:

            eligible.append(
                race_key
            )

    if not eligible:
        return {}

    eligible_set = set(
        eligible
    )

    work = work[
        work.apply(
            lambda row:
                (
                    row[
                        "venue_code"
                    ],
                    row[
                        "race"
                    ],
                )
                in eligible_set,
            axis=1,
        )
    ].copy()

    work[
        "time_norm"
    ] = 0.0

    work[
        "st_norm"
    ] = 0.0

    for (
        _,
        index,
    ) in work.groupby(
        [
            "venue_code",
            "race",
        ]
    ).groups.items():

        race_data = (
            work.loc[index]
        )

        work.loc[
            index,
            "time_norm",
        ] = normalize_within_race(
            race_data,
            "exhibition_time",
            True,
        )

        work.loc[
            index,
            "st_norm",
        ] = normalize_within_race(
            race_data,
            "exhibition_st",
            True,
        )

    if (
        "exhibition_f"
        not in work
    ):

        work[
            "exhibition_f"
        ] = 0.0

    else:

        work[
            "exhibition_f"
        ] = (
            pd.to_numeric(
                work[
                    "exhibition_f"
                ],
                errors="coerce",
            )
            .fillna(0)
        )

    def accuracy(
        time_weight: int,
        st_weight: int,
        f_penalty: int,
    ) -> float:

        test = work.copy()

        test[
            "adjusted_score"
        ] = (
            test[
                "total_score"
            ]
            + time_weight
            * test[
                "time_norm"
            ]
            + st_weight
            * test[
                "st_norm"
            ]
            - f_penalty
            * test[
                "exhibition_f"
            ]
        )

        wins = 0
        races = 0

        for (
            _,
            race_data,
        ) in test.groupby(
            [
                "venue_code",
                "race",
            ]
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
                top[
                    "finish"
                ]
                == 1
            )

            races += 1

        if races == 0:
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

    candidates = []

    for time_weight in (
        0,
        2,
        4,
        6,
        8,
        10,
        12,
    ):

        for st_weight in (
            0,
            2,
            4,
            6,
            8,
            10,
            12,
        ):

            for f_penalty in (
                0,
                2,
                4,
                6,
                8,
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

                candidates.append(
                    {
                        "exhibition_time_weight":
                            time_weight,

                        "exhibition_st_weight":
                            st_weight,

                        "f_penalty":
                            f_penalty,

                        "top1_accuracy_pct":
                            round(
                                accuracy(
                                    time_weight,
                                    st_weight,
                                    f_penalty,
                                ),
                                1,
                            ),
                    }
                )

    candidates = sorted(
        candidates,
        key=lambda item:
            (
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
        "races":
            len(
                eligible
            ),

        "baseline_top1_accuracy_pct":
            round(
                baseline,
                1,
            ),

        "best_candidates":
            candidates[:10],
    }


def wind_buckets(
    dataframe: pd.DataFrame,
) -> List[
    Dict[str, Any]
]:

    if (
        "wind_speed"
        not in dataframe
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

    if work.empty:
        return []

    rows = []

    for (
        _,
        race_data,
    ) in work.groupby(
        [
            "venue_code",
            "race",
        ]
    ):

        wind_speed = float(
            race_data[
                "wind_speed"
            ]
            .dropna()
            .iloc[0]
        )

        if wind_speed < 3:

            bucket = (
                "0-2m"
            )

        elif wind_speed < 5:

            bucket = (
                "3-4m"
            )

        else:

            bucket = (
                "5m以上"
            )

        frame1 = race_data[
            race_data[
                "boat"
            ]
            == 1
        ]

        rows.append(
            (
                bucket,
                int(
                    len(
                        frame1
                    )
                    and frame1.iloc[
                        0
                    ][
                        "finish"
                    ]
                    == 1
                ),
            )
        )

    output = []

    for bucket in (
        "0-2m",
        "3-4m",
        "5m以上",
    ):

        values = [
            result
            for (
                row_bucket,
                result,
            ) in rows
            if row_bucket
            == bucket
        ]

        if not values:
            continue

        output.append(
            {
                "bucket":
                    bucket,

                "races":
                    len(
                        values
                    ),

                "boat1_win_rate_pct":
                    round(
                        sum(
                            values
                        )
                        / len(
                            values
                        )
                        * 100,
                        1,
                    ),
            }
        )

    return output


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        required=True,
    )

    args = parser.parse_args()

    date = args.date

    live = (
        load_recorded_beforeinfo(
            date
        )
    )

    if live.empty:

        raise SystemExit(
            "recorded beforeinfo/live features not found"
        )

    results = load_results(
        date
    )

    base_scores = load_base_scores(
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
            base_scores,
            on=keys,
            how="left",
        )
    )

    report = {
        "date":
            date,

        "source_files":
            sorted(
                live[
                    "source"
                ]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            ),

        "coverage":
            {},

        "factors":
            {},
    }

    for column in (
        "exhibition_time",
        "exhibition_st",
        "exhibition_f",
        "exhibition_course",
        "wind_speed",
        "wave_height",
    ):

        report[
            "coverage"
        ][
            column
        ] = (
            int(
                dataframe[
                    column
                ]
                .notna()
                .sum()
            )
            if column
            in dataframe
            else 0
        )

    if (
        "exhibition_course"
        in dataframe
    ):

        dataframe[
            "course_changed"
        ] = (
            pd.to_numeric(
                dataframe[
                    "exhibition_course"
                ],
                errors="coerce",
            )
            !=
            pd.to_numeric(
                dataframe[
                    "boat"
                ],
                errors="coerce",
            )
        ).astype(float)

    report[
        "factors"
    ][
        "exhibition_time"
    ] = (
        rank_metric(
            dataframe,
            "exhibition_time",
            True,
        )
        if "exhibition_time"
        in dataframe
        else {}
    )

    report[
        "factors"
    ][
        "exhibition_st"
    ] = (
        rank_metric(
            dataframe,
            "exhibition_st",
            True,
        )
        if "exhibition_st"
        in dataframe
        else {}
    )

    report[
        "factors"
    ][
        "exhibition_f"
    ] = (
        binary_metric(
            dataframe,
            "exhibition_f",
        )
        if "exhibition_f"
        in dataframe
        else {}
    )

    report[
        "factors"
    ][
        "course_changed"
    ] = (
        binary_metric(
            dataframe,
            "course_changed",
        )
        if "course_changed"
        in dataframe
        else {}
    )

    report[
        "wind_context"
    ] = wind_buckets(
        dataframe
    )

    report[
        "weight_search"
    ] = simulate(
        dataframe
    )

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

    json_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    markdown = [
        "# 直前情報5項目 個別答え合わせ",
        "",
        (
            f"対象日："
            f"{date[:4]}/"
            f"{date[4:6]}/"
            f"{date[6:8]}"
        ),
        "",
        "## 取得件数",
        "",
    ]

    for (
        key,
        value,
    ) in report[
        "coverage"
    ].items():

        markdown.append(
            f"- {key}: {value}艇"
        )

    markdown += [
        "",
        "## 個別要素",
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
        "## 重み探索（探索用・1日分）",
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
    ]

    markdown_path = (
        output_dir
        / (
            "live_factor_analysis_"
            f"{date}.md"
        )
    )

    markdown_path.write_text(
        "\n".join(
            markdown
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "直前情報個別分析: PASS"
    )

    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )