#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd


WEIGHTS = {
    "frame": 28,
    "official_racer": 18,
    "recent_racer": 22,
    "racer_venue": 8,
    "motor": 14,
    "boat_machine": 5,
    "grade": 5,
}

LABEL = {
    "frame": "枠・コース",
    "official_racer": "選手公式能力",
    "recent_racer": "選手直近成績",
    "racer_venue": "当地・場適性",
    "motor": "モーター",
    "boat_machine": "ボート",
    "grade": "級別",
    "live_beforeinfo": "直前・展示",
}

COMP_ALIASES = {
    "frame": {
        "frame_score",
        "frame_points",
        "course_score",
        "course_points",
    },

    "official_racer": {
        "official_racer_score",
        "official_score",
        "racer_official_score",
    },

    "recent_racer": {
        "recent_racer_score",
        "recent_score",
        "racer_recent_score",
    },

    "racer_venue": {
        "racer_venue_score",
        "venue_score",
        "local_score",
        "racer_local_score",
    },

    "motor": {
        "motor_score",
        "motor_points",
    },

    "boat_machine": {
        "boat_machine_score",
        "boat_score",
        "boat_points",
    },

    "grade": {
        "grade_score",
        "grade_points",
        "class_score",
    },
}

OUTCOME_WORDS = (
    "finish",
    "result",
    "payout",
    "return",
    "race_time",
    "actual_st",
    "winner",
    "trifecta",
    "exacta",
)

ID_LEAVES = {
    "date",
    "venue_code",
    "race",
    "rno",
    "boat",
    "frame",
    "registration_no",
    "motor_no",
    "boat_no",
    "age",
    "series_day",
    "distance_m",
}


def nkey(
    value: Any,
) -> str:

    return re.sub(
        r"[^a-z0-9_]+",
        "_",
        str(value)
        .strip()
        .lower(),
    ).strip("_")


def num(
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
            and math.isnan(value)
        ):
            return None

        return float(value)

    try:

        return float(
            str(value)
            .strip()
            .replace(",", "")
            .replace("%", "")
        )

    except Exception:

        return None


def flatten_numeric(
    obj: Any,
    prefix: str = "",
) -> Dict[str, float]:

    out: Dict[
        str,
        float,
    ] = {}

    if isinstance(
        obj,
        dict,
    ):

        for key, value in obj.items():

            path = (
                f"{prefix}.{nkey(key)}"
                if prefix
                else nkey(key)
            )

            if isinstance(
                value,
                dict,
            ):

                out.update(
                    flatten_numeric(
                        value,
                        path,
                    )
                )

            elif not isinstance(
                value,
                list,
            ):

                value_num = num(
                    value
                )

                if value_num is not None:

                    out[path] = (
                        value_num
                    )

    return out


def venue(
    value: Any,
) -> str:

    text = str(
        value
    ).strip()

    try:

        return (
            f"{int(float(text)):02d}"
        )

    except Exception:

        return text.zfill(2)


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


def load_json(
    path: Path,
) -> Any:

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(
            file
        )


def boat_records(
    root: Any,
    default_date: str,
) -> List[
    Dict[str, Any]
]:

    rows: List[
        Dict[str, Any]
    ] = []

    def walk(
        node: Any,
        context: Dict[
            str,
            Any,
        ],
    ) -> None:

        if isinstance(
            node,
            dict,
        ):

            current = dict(
                context
            )

            if "race_id" in node:

                date_value, venue_value, race_value = (
                    parse_race_id(
                        node.get(
                            "race_id"
                        )
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

            for source, destination in (
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
                    source
                    in node
                    and not isinstance(
                        node[source],
                        (
                            dict,
                            list,
                        ),
                    )
                ):

                    current[
                        destination
                    ] = node[source]

            boat_number = None

            for boat_key in (
                "boat",
                "frame",
                "lane",
            ):

                if (
                    boat_key
                    in node
                    and not isinstance(
                        node[
                            boat_key
                        ],
                        (
                            dict,
                            list,
                        ),
                    )
                ):

                    candidate = iv(
                        node[
                            boat_key
                        ]
                    )

                    if (
                        candidate
                        is not None
                        and 1
                        <= candidate
                        <= 6
                    ):

                        boat_number = (
                            candidate
                        )

                        break

            if (
                boat_number
                is not None
                and current.get(
                    "race"
                )
                is not None
            ):

                rows.append(
                    {
                        "date":
                            str(
                                current.get(
                                    "date",
                                    default_date,
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
                            boat_number,

                        "raw":
                            node,
                    }
                )

            for value in node.values():

                if isinstance(
                    value,
                    (
                        dict,
                        list,
                    ),
                ):

                    walk(
                        value,
                        current,
                    )

        elif isinstance(
            node,
            list,
        ):

            for value in node:

                walk(
                    value,
                    context,
                )

    walk(
        root,
        {
            "date":
                default_date
        },
    )

    dedup: Dict[
        Tuple[
            str,
            str,
            int,
            int,
        ],
        Dict[
            str,
            Any,
        ],
    ] = {}

    for row in rows:

        if row[
            "race"
        ] is None:

            continue

        key = (
            row[
                "date"
            ],
            row[
                "venue_code"
            ],
            int(
                row[
                    "race"
                ]
            ),
            int(
                row[
                    "boat"
                ]
            ),
        )

        score_hint = any(
            key_name
            in row[
                "raw"
            ]
            for key_name
            in (
                "score",
                "total_score",
                "final_score",
                "prediction_score",
                "score_components",
                "components",
                "breakdown",
            )
        )

        if (
            key
            not in dedup
            or score_hint
        ):

            dedup[
                key
            ] = row

    return list(
        dedup.values()
    )


def discover(
    patterns: Iterable[
        str
    ],
) -> List[Path]:

    output = []
    seen = set()

    for pattern in patterns:

        for path in Path(
            "."
        ).glob(
            pattern
        ):

            if (
                path.is_file()
                and str(path)
                not in seen
            ):

                seen.add(
                    str(path)
                )

                output.append(
                    path
                )

    return output


def choose_file(
    date: str,
    stage: str,
    kind: str,
) -> Optional[Path]:

    year = date[:4]
    month = date[4:6]
    day = date[6:8]

    if kind == "prediction":

        patterns = [
            (
                f"predictions/"
                f"{year}/"
                f"{month}/"
                f"{day}/"
                f"{stage}/"
                f"**/*final*.json"
            ),

            (
                f"predictions/"
                f"{year}/"
                f"{month}/"
                f"{day}/"
                f"{stage}/"
                f"**/*prediction*.json"
            ),

            (
                f"data/"
                f"*{stage}*"
                f"predictions*"
                f"{date}*.json"
            ),
        ]

    else:

        patterns = [
            (
                f"data/"
                f"prediction_input_"
                f"enriched_"
                f"{stage}_"
                f"{date}.json"
            ),

            (
                f"data/"
                f"prediction_input_"
                f"{stage}_"
                f"{date}.json"
            ),

            (
                f"daily_inputs/"
                f"{year}/"
                f"{month}/"
                f"{day}/"
                f"{stage}/"
                f"**/*enriched*.json"
            ),

            (
                f"daily_inputs/"
                f"{year}/"
                f"{month}/"
                f"{day}/"
                f"{stage}/"
                f"**/*prediction_input*.json"
            ),
        ]

    candidates = []

    for path in discover(
        patterns
    ):

        try:

            count = len(
                boat_records(
                    load_json(
                        path
                    ),
                    date,
                )
            )

            if kind == "input":

                bonus = (
                    1
                    if "enriched"
                    in path.name.lower()
                    else 0
                )

            else:

                bonus = (
                    1
                    if "final"
                    in path.name.lower()
                    else 0
                )

            candidates.append(
                (
                    bonus,
                    count,
                    path,
                )
            )

        except Exception:

            pass

    if not candidates:

        return None

    return max(
        candidates,
        key=lambda value: (
            value[0],
            value[1],
        ),
    )[2]


def total_score(
    raw: Dict[
        str,
        Any,
    ],
) -> Optional[float]:

    for key in (
        "total_score",
        "final_score",
        "prediction_score",
        "score",
    ):

        if key in raw:

            value = num(
                raw[key]
            )

            if value is not None:

                return value

    flat = flatten_numeric(
        raw
    )

    for leaf in (
        "total_score",
        "final_score",
        "prediction_score",
        "score",
    ):

        for path, value in flat.items():

            if (
                path.split(
                    "."
                )[-1]
                == leaf
                and "component"
                not in path
                and "breakdown"
                not in path
            ):

                return value

    return None


def component_scores(
    raw: Dict[
        str,
        Any,
    ],
) -> Dict[
    str,
    float,
]:

    sources = []

    for key in (
        "score_components",
        "component_scores",
        "components",
        "breakdown",
        "score_breakdown",
    ):

        if isinstance(
            raw.get(
                key
            ),
            dict,
        ):

            sources.append(
                raw[
                    key
                ]
            )

    sources.append(
        raw
    )

    output: Dict[
        str,
        float,
    ] = {}

    for group, aliases in (
        COMP_ALIASES.items()
    ):

        for source in sources:

            for path, value in (
                flatten_numeric(
                    source
                ).items()
            ):

                if (
                    path.split(
                        "."
                    )[-1]
                    in aliases
                ):

                    output[
                        group
                    ] = value

                    break

            if group in output:

                break

    return output


def grade_value(
    value: Any,
) -> Optional[float]:

    return {
        "A1": 4.0,
        "A2": 3.0,
        "B1": 2.0,
        "B2": 1.0,
    }.get(
        str(
            value
            or ""
        )
        .strip()
        .upper()
    )


def feature_group(
    path: str,
) -> Optional[str]:

    path_lower = (
        path.lower()
    )

    leaf = (
        path_lower
        .split(".")[-1]
    )

    if (
        any(
            word
            in path_lower
            for word
            in OUTCOME_WORDS
        )
        or leaf
        in ID_LEAVES
    ):

        return None

    if (
        "beforeinfo"
        in path_lower
    ):

        return (
            "live_beforeinfo"
        )

    if (
        "history.racer_30d"
        in path_lower
        or
        "history.racer_90d"
        in path_lower
        or
        "recent"
        in path_lower
    ):

        return (
            "recent_racer"
        )

    if (
        "history.motor_30d"
        in path_lower
        or
        "history.motor_90d"
        in path_lower
    ):

        return "motor"

    if (
        "official_stats.local_"
        in path_lower
        or
        "local_win"
        in path_lower
        or
        "local_top"
        in path_lower
    ):

        return (
            "racer_venue"
        )

    if (
        "official_stats.national_"
        in path_lower
        or
        "national_win"
        in path_lower
        or
        "national_top"
        in path_lower
    ):

        return (
            "official_racer"
        )

    if (
        path_lower.startswith(
            "motor."
        )
        or
        ".motor."
        in path_lower
    ):

        return "motor"

    if (
        "boat_machine"
        in path_lower
    ):

        return (
            "boat_machine"
        )

    return None


def input_frame(
    path: Optional[Path],
    date: str,
) -> pd.DataFrame:

    if path is None:

        return pd.DataFrame()

    rows = []

    for record in boat_records(
        load_json(
            path
        ),
        date,
    ):

        raw = record[
            "raw"
        ]

        row: Dict[
            str,
            Any,
        ] = {
            "date":
                record[
                    "date"
                ],

            "venue_code":
                record[
                    "venue_code"
                ],

            "race":
                record[
                    "race"
                ],

            "boat":
                record[
                    "boat"
                ],
        }

        row[
            "feature.frame.frame_advantage"
        ] = (
            7
            - int(
                record[
                    "boat"
                ]
            )
        )

        racer = (
            raw.get(
                "racer"
            )
            if isinstance(
                raw.get(
                    "racer"
                ),
                dict,
            )
            else {}
        )

        grade = grade_value(
            racer.get(
                "grade"
            )
        )

        if grade is not None:

            row[
                "feature.grade.grade_numeric"
            ] = grade

        for key, value in (
            flatten_numeric(
                raw
            ).items()
        ):

            group = feature_group(
                key
            )

            if group:

                row[
                    f"feature."
                    f"{group}."
                    f"{key}"
                ] = value

        rows.append(
            row
        )

    return pd.DataFrame(
        rows
    )


def prediction_frame(
    path: Optional[Path],
    date: str,
) -> pd.DataFrame:

    if path is None:

        return pd.DataFrame()

    rows = []

    for record in boat_records(
        load_json(
            path
        ),
        date,
    ):

        row: Dict[
            str,
            Any,
        ] = {
            "date":
                record[
                    "date"
                ],

            "venue_code":
                record[
                    "venue_code"
                ],

            "race":
                record[
                    "race"
                ],

            "boat":
                record[
                    "boat"
                ],

            "total_score":
                total_score(
                    record[
                        "raw"
                    ]
                ),
        }

        for group, value in (
            component_scores(
                record[
                    "raw"
                ]
            ).items()
        ):

            row[
                f"component.{group}"
            ] = value

        rows.append(
            row
        )

    return pd.DataFrame(
        rows
    )


def results_frame(
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

        raise FileNotFoundError(
            f"boat_results_"
            f"{date}_all.csv "
            f"not found"
        )

    dataframe = pd.read_csv(
        path
    )

    required = {
        "date",
        "venue_code",
        "race",
        "boat",
        "finish",
    }

    if not required.issubset(
        dataframe.columns
    ):

        raise ValueError(
            "result columns missing: "
            + str(
                sorted(
                    required
                    - set(
                        dataframe.columns
                    )
                )
            )
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

    dataframe[
        "race"
    ] = pd.to_numeric(
        dataframe[
            "race"
        ],
        errors="coerce",
    )

    dataframe[
        "boat"
    ] = pd.to_numeric(
        dataframe[
            "boat"
        ],
        errors="coerce",
    )

    dataframe[
        "finish_num"
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
                "finish_num",
            ]
        ]
        .dropna()
    )


def stage_frame(
    date: str,
    stage: str,
    result: pd.DataFrame,
) -> Tuple[
    pd.DataFrame,
    Dict[str, Any],
]:

    input_path = choose_file(
        date,
        stage,
        "input",
    )

    prediction_path = choose_file(
        date,
        stage,
        "prediction",
    )

    input_data = input_frame(
        input_path,
        date,
    )

    prediction_data = (
        prediction_frame(
            prediction_path,
            date,
        )
    )

    keys = [
        "date",
        "venue_code",
        "race",
        "boat",
    ]

    dataframe = (
        result.copy()
    )

    if not input_data.empty:

        dataframe = (
            dataframe.merge(
                input_data,
                on=keys,
                how="left",
            )
        )

    if not prediction_data.empty:

        dataframe = (
            dataframe.merge(
                prediction_data,
                on=keys,
                how="left",
            )
        )

    meta = {
        "input_file":
            (
                str(
                    input_path
                )
                if input_path
                else None
            ),

        "prediction_file":
            (
                str(
                    prediction_path
                )
                if prediction_path
                else None
            ),

        "score_rows":
            (
                int(
                    pd.to_numeric(
                        dataframe[
                            "total_score"
                        ],
                        errors="coerce",
                    )
                    .notna()
                    .sum()
                )
                if "total_score"
                in dataframe
                else 0
            ),

        "component_columns":
            [
                column
                for column
                in dataframe.columns
                if column.startswith(
                    "component."
                )
            ],
    }

    return (
        dataframe,
        meta,
    )


def feature_stat(
    dataframe: pd.DataFrame,
    column: str,
) -> Optional[
    Dict[str, Any]
]:

    work = dataframe[
        [
            "venue_code",
            "race",
            "finish_num",
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

    work = work.dropna()

    if (
        len(work)
        < 30
        or work[
            column
        ].nunique()
        < 2
    ):

        return None

    work[
        "race_key"
    ] = (
        work[
            "venue_code"
        ].astype(str)
        + "-"
        + work[
            "race"
        ].astype(str)
    )

    work[
        "rank_high"
    ] = (
        work.groupby(
            "race_key"
        )[
            column
        ]
        .rank(
            method="average",
            ascending=False,
        )
    )

    correlation = (
        work[
            "rank_high"
        ]
        .corr(
            work[
                "finish_num"
            ],
            method="spearman",
        )
    )

    high_finish = []
    low_finish = []

    for _, race_data in (
        work.groupby(
            "race_key"
        )
    ):

        if len(
            race_data
        ) < 2:

            continue

        high_finish.append(
            float(
                race_data
                .sort_values(
                    column,
                    ascending=False,
                )
                .iloc[0][
                    "finish_num"
                ]
            )
        )

        low_finish.append(
            float(
                race_data
                .sort_values(
                    column
                )
                .iloc[0][
                    "finish_num"
                ]
            )
        )

    if not high_finish:

        return None

    return {
        "column":
            column,

        "rows":
            int(
                len(work)
            ),

        "races":
            len(
                high_finish
            ),

        "rank_finish_spearman":
            (
                None
                if pd.isna(
                    correlation
                )
                else round(
                    float(
                        correlation
                    ),
                    4,
                )
            ),

        "high_leader_win_rate_pct":
            round(
                sum(
                    value == 1
                    for value
                    in high_finish
                )
                / len(
                    high_finish
                )
                * 100,
                1,
            ),

        "low_leader_win_rate_pct":
            round(
                sum(
                    value == 1
                    for value
                    in low_finish
                )
                / len(
                    low_finish
                )
                * 100,
                1,
            ),

        "high_leader_top3_rate_pct":
            round(
                sum(
                    value <= 3
                    for value
                    in high_finish
                )
                / len(
                    high_finish
                )
                * 100,
                1,
            ),

        "low_leader_top3_rate_pct":
            round(
                sum(
                    value <= 3
                    for value
                    in low_finish
                )
                / len(
                    low_finish
                )
                * 100,
                1,
            ),
    }


def score_calibration(
    dataframe: pd.DataFrame,
) -> Dict[str, Any]:

    if (
        "total_score"
        not in dataframe
    ):

        return {}

    work = dataframe[
        [
            "venue_code",
            "race",
            "boat",
            "finish_num",
            "total_score",
        ]
    ].copy()

    work[
        "total_score"
    ] = pd.to_numeric(
        work[
            "total_score"
        ],
        errors="coerce",
    )

    work = work.dropna()

    rows = []

    for (
        venue_code,
        race_number,
    ), race_data in work.groupby(
        [
            "venue_code",
            "race",
        ]
    ):

        if len(
            race_data
        ) < 2:

            continue

        race_data = (
            race_data
            .sort_values(
                "total_score",
                ascending=False,
            )
        )

        first = (
            race_data.iloc[0]
        )

        second = (
            race_data.iloc[1]
        )

        rows.append(
            {
                "venue_code":
                    venue_code,

                "race":
                    int(
                        race_number
                    ),

                "top_boat":
                    int(
                        first[
                            "boat"
                        ]
                    ),

                "top_score":
                    float(
                        first[
                            "total_score"
                        ]
                    ),

                "gap":
                    float(
                        first[
                            "total_score"
                        ]
                        - second[
                            "total_score"
                        ]
                    ),

                "top_finish":
                    float(
                        first[
                            "finish_num"
                        ]
                    ),

                "top_win":
                    int(
                        first[
                            "finish_num"
                        ]
                        == 1
                    ),

                "top3":
                    int(
                        first[
                            "finish_num"
                        ]
                        <= 3
                    ),
            }
        )

    result = pd.DataFrame(
        rows
    )

    if result.empty:

        return {}

    result[
        "gap_bucket"
    ] = pd.cut(
        result[
            "gap"
        ],
        [
            -1e9,
            5,
            10,
            15,
            1e9,
        ],
        labels=[
            "0-5未満",
            "5-10未満",
            "10-15未満",
            "15以上",
        ],
        right=False,
    )

    buckets = []

    for label in (
        "0-5未満",
        "5-10未満",
        "10-15未満",
        "15以上",
    ):

        bucket = result[
            result[
                "gap_bucket"
            ].astype(str)
            == label
        ]

        if bucket.empty:

            continue

        buckets.append(
            {
                "gap_bucket":
                    label,

                "races":
                    len(
                        bucket
                    ),

                "win_rate_pct":
                    round(
                        bucket[
                            "top_win"
                        ].mean()
                        * 100,
                        1,
                    ),

                "top3_rate_pct":
                    round(
                        bucket[
                            "top3"
                        ].mean()
                        * 100,
                        1,
                    ),

                "mean_finish":
                    round(
                        bucket[
                            "top_finish"
                        ].mean(),
                        2,
                    ),
            }
        )

    return {
        "races":
            len(
                result
            ),

        "top_score_win_rate_pct":
            round(
                result[
                    "top_win"
                ].mean()
                * 100,
                1,
            ),

        "top_score_top3_rate_pct":
            round(
                result[
                    "top3"
                ].mean()
                * 100,
                1,
            ),

        "mean_top_finish":
            round(
                result[
                    "top_finish"
                ].mean(),
                2,
            ),

        "gap_buckets":
            buckets,

        "race_rows":
            rows,
    }


def group_of_column(
    column: str,
) -> str:

    if column.startswith(
        "component."
    ):

        return (
            column.split(
                ".",
                1,
            )[1]
        )

    if column.startswith(
        "feature."
    ):

        return (
            column.split(
                ".",
                2,
            )[1]
        )

    return "total_score"


def group_summary(
    stats: List[
        Dict[str, Any]
    ],
) -> List[
    Dict[str, Any]
]:

    output = []

    for group in (
        list(
            WEIGHTS
        )
        + [
            "live_beforeinfo"
        ]
    ):

        subset = [
            item
            for item
            in stats
            if item[
                "group"
            ]
            == group
        ]

        best = max(
            subset,
            key=lambda item:
                abs(
                    item[
                        "rank_finish_spearman"
                    ]
                    or 0
                ),
            default=None,
        )

        output.append(
            {
                "group":
                    group,

                "label":
                    LABEL.get(
                        group,
                        group,
                    ),

                "current_weight":
                    WEIGHTS.get(
                        group
                    ),

                "features_tested":
                    len(
                        subset
                    ),

                "exact_component_available":
                    any(
                        item[
                            "kind"
                        ]
                        == "exact_component"
                        for item
                        in subset
                    ),

                "best_feature":
                    (
                        best[
                            "column"
                        ]
                        if best
                        else None
                    ),

                "best_abs_spearman":
                    (
                        round(
                            abs(
                                best[
                                    "rank_finish_spearman"
                                ]
                            ),
                            4,
                        )
                        if (
                            best
                            and best[
                                "rank_finish_spearman"
                            ]
                            is not None
                        )
                        else None
                    ),

                "best_high_leader_win_rate_pct":
                    (
                        best[
                            "high_leader_win_rate_pct"
                        ]
                        if best
                        else None
                    ),

                "best_low_leader_win_rate_pct":
                    (
                        best[
                            "low_leader_win_rate_pct"
                        ]
                        if best
                        else None
                    ),
            }
        )

    return output


def redundancy(
    dataframe: pd.DataFrame,
    stats: List[
        Dict[str, Any]
    ],
) -> List[
    Dict[str, Any]
]:

    representatives: Dict[
        str,
        str,
    ] = {}

    for group in WEIGHTS:

        exact = (
            f"component."
            f"{group}"
        )

        if exact in dataframe.columns:

            representatives[
                group
            ] = exact

            continue

        subset = [
            item
            for item
            in stats
            if (
                item[
                    "group"
                ]
                == group
                and item[
                    "column"
                ].startswith(
                    f"feature."
                    f"{group}."
                )
                and item[
                    "rank_finish_spearman"
                ]
                is not None
            )
        ]

        if subset:

            best = max(
                subset,
                key=lambda item:
                    abs(
                        item[
                            "rank_finish_spearman"
                        ]
                    ),
            )

            representatives[
                group
            ] = best[
                "column"
            ]

    output = []

    groups = list(
        representatives
    )

    for i in range(
        len(groups)
    ):

        for j in range(
            i + 1,
            len(groups),
        ):

            group_a = (
                groups[i]
            )

            group_b = (
                groups[j]
            )

            column_a = (
                representatives[
                    group_a
                ]
            )

            column_b = (
                representatives[
                    group_b
                ]
            )

            work = dataframe[
                [
                    "venue_code",
                    "race",
                    column_a,
                    column_b,
                ]
            ].copy()

            work[
                column_a
            ] = pd.to_numeric(
                work[
                    column_a
                ],
                errors="coerce",
            )

            work[
                column_b
            ] = pd.to_numeric(
                work[
                    column_b
                ],
                errors="coerce",
            )

            work = work.dropna()

            if len(
                work
            ) < 30:

                continue

            work[
                "race_key"
            ] = (
                work[
                    "venue_code"
                ].astype(str)
                + "-"
                + work[
                    "race"
                ].astype(str)
            )

            work[
                "rank_a"
            ] = (
                work.groupby(
                    "race_key"
                )[
                    column_a
                ]
                .rank(
                    method="average",
                    ascending=False,
                )
            )

            work[
                "rank_b"
            ] = (
                work.groupby(
                    "race_key"
                )[
                    column_b
                ]
                .rank(
                    method="average",
                    ascending=False,
                )
            )

            correlation = (
                work[
                    "rank_a"
                ]
                .corr(
                    work[
                        "rank_b"
                    ],
                    method="spearman",
                )
            )

            if pd.isna(
                correlation
            ):

                continue

            correlation = float(
                correlation
            )

            output.append(
                {
                    "group_a":
                        group_a,

                    "group_b":
                        group_b,

                    "label_a":
                        LABEL[
                            group_a
                        ],

                    "label_b":
                        LABEL[
                            group_b
                        ],

                    "rank_spearman":
                        round(
                            correlation,
                            4,
                        ),

                    "high_overlap_flag":
                        abs(
                            correlation
                        )
                        >= 0.70,
                }
            )

    return sorted(
        output,
        key=lambda item:
            abs(
                item[
                    "rank_spearman"
                ]
            ),
        reverse=True,
    )


def table(
    headers: List[str],
    rows: List[
        List[Any]
    ],
) -> List[str]:

    output = [
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

    output += [
        "| "
        + " | ".join(
            str(
                value
            )
            for value
            in row
        )
        + " |"
        for row
        in rows
    ]

    return output


def show(
    value: Any,
    suffix: str = "",
) -> str:

    if value is None:

        return "—"

    return (
        f"{value}{suffix}"
    )


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        required=True,
    )

    args = parser.parse_args()

    date = args.date

    if not re.fullmatch(
        r"\d{8}",
        date,
    ):

        raise SystemExit(
            "--date must be YYYYMMDD"
        )

    results = results_frame(
        date
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

    all_frames = []
    all_stats = []

    stages: Dict[
        str,
        Any,
    ] = {}

    for stage in (
        "morning",
        "live",
    ):

        dataframe, meta = (
            stage_frame(
                date,
                stage,
                results,
            )
        )

        all_frames.append(
            dataframe.assign(
                stage=stage
            )
        )

        stats = []

        columns = [
            column
            for column
            in dataframe.columns
            if (
                column.startswith(
                    "feature."
                )
                or
                column.startswith(
                    "component."
                )
            )
        ]

        if (
            "total_score"
            in dataframe.columns
        ):

            columns.append(
                "total_score"
            )

        for column in columns:

            stat = feature_stat(
                dataframe,
                column,
            )

            if stat:

                stat[
                    "stage"
                ] = stage

                stat[
                    "group"
                ] = (
                    group_of_column(
                        column
                    )
                )

                if column.startswith(
                    "component."
                ):

                    stat[
                        "kind"
                    ] = (
                        "exact_component"
                    )

                elif column.startswith(
                    "feature."
                ):

                    stat[
                        "kind"
                    ] = (
                        "raw_feature_proxy"
                    )

                else:

                    stat[
                        "kind"
                    ] = (
                        "total_score"
                    )

                stats.append(
                    stat
                )

                all_stats.append(
                    stat
                )

        calibration = (
            score_calibration(
                dataframe
            )
        )

        if calibration.get(
            "race_rows"
        ):

            pd.DataFrame(
                calibration[
                    "race_rows"
                ]
            ).to_csv(
                output_dir
                / (
                    f"score_gap_races_"
                    f"{stage}_"
                    f"{date}.csv"
                ),
                index=False,
                encoding="utf-8-sig",
            )

        stages[
            stage
        ] = {
            "meta":
                meta,

            "score_calibration":
                {
                    key: value
                    for key, value
                    in calibration.items()
                    if key
                    != "race_rows"
                },

            "groups":
                group_summary(
                    stats
                ),

            "redundancy":
                redundancy(
                    dataframe,
                    stats,
                ),
        }

    pd.concat(
        all_frames,
        ignore_index=True,
        sort=False,
    ).to_csv(
        output_dir
        / (
            f"score_answer_check_"
            f"boats_{date}.csv"
        ),
        index=False,
        encoding="utf-8-sig",
    )

    if all_stats:

        pd.DataFrame(
            all_stats
        ).to_csv(
            output_dir
            / (
                f"score_feature_stats_"
                f"{date}.csv"
            ),
            index=False,
            encoding="utf-8-sig",
        )

    report = {
        "date":
            date,

        "current_weights":
            WEIGHTS,

        "stage_analysis":
            stages,

        "note":
            (
                "Descriptive answer-check only. "
                "Actual finish is evaluation "
                "target only and is never fed "
                "back into pre-race features."
            ),
    }

    (
        output_dir
        / (
            f"score_component_"
            f"analysis_{date}.json"
        )
    ).write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [
        "# スコア配分・実レース結果 自動答え合わせ",
        "",
        (
            f"対象日："
            f"{date[:4]}/"
            f"{date[4:6]}/"
            f"{date[6:8]}"
        ),
        "",
        (
            "> 配点を自動変更するレポートではありません。"
            "予測時点の情報と実際の着順を照合し、"
            "配点見直しの根拠を蓄積します。"
        ),
        "",
        "## 現在の配点",
        "",
    ]

    lines += table(
        [
            "要素",
            "配点",
        ],
        [
            [
                LABEL[
                    key
                ],
                f"{value}点",
            ]
            for key, value
            in WEIGHTS.items()
        ],
    )

    for stage, title in (
        (
            "morning",
            "朝予測",
        ),
        (
            "live",
            "直前予測",
        ),
    ):

        info = stages[
            stage
        ]

        meta = info[
            "meta"
        ]

        calibration = (
            info[
                "score_calibration"
            ]
        )

        lines += [
            "",
            f"## {title}",
            "",
            (
                f"- 予測ファイル："
                f"`{meta.get('prediction_file') or '未検出'}`"
            ),
            (
                f"- 入力ファイル："
                f"`{meta.get('input_file') or '未検出'}`"
            ),
            (
                f"- 総合スコア取得艇数："
                f"{meta.get('score_rows', 0)}艇"
            ),
            (
                f"- 正確な構成要素点の列数："
                f"{len(meta.get('component_columns', []))}列"
            ),
            "",
        ]

        if calibration:

            lines += [
                "### 総合スコアの答え合わせ",
                "",
                (
                    f"- スコア1位艇の1着率："
                    f"**{show(calibration.get('top_score_win_rate_pct'), '%')}**"
                ),
                (
                    f"- スコア1位艇の3着内率："
                    f"**{show(calibration.get('top_score_top3_rate_pct'), '%')}**"
                ),
                (
                    f"- スコア1位艇の平均着順："
                    f"**{show(calibration.get('mean_top_finish'))}**"
                ),
                "",
                "#### 1位−2位スコア差別",
                "",
            ]

            lines += table(
                [
                    "スコア差",
                    "R数",
                    "1着率",
                    "3着内率",
                    "平均着順",
                ],
                [
                    [
                        row[
                            "gap_bucket"
                        ],
                        row[
                            "races"
                        ],
                        (
                            f"{row['win_rate_pct']}%"
                        ),
                        (
                            f"{row['top3_rate_pct']}%"
                        ),
                        row[
                            "mean_finish"
                        ],
                    ]
                    for row
                    in calibration.get(
                        "gap_buckets",
                        [],
                    )
                ],
            )

        lines += [
            "",
            "### 配点要素別診断",
            "",
        ]

        lines += table(
            [
                "要素",
                "現配点",
                "検証項目",
                "構成点",
                "最も関連が強い指標",
                "|順位相関|",
                "高値首位1着率",
                "低値首位1着率",
            ],
            [
                [
                    group[
                        "label"
                    ],
                    (
                        f"{group['current_weight']}点"
                        if group[
                            "current_weight"
                        ]
                        is not None
                        else "—"
                    ),
                    group[
                        "features_tested"
                    ],
                    (
                        "あり"
                        if group[
                            "exact_component_available"
                        ]
                        else
                        "なし（代理指標）"
                    ),
                    (
                        group[
                            "best_feature"
                        ]
                        or "—"
                    ),
                    show(
                        group[
                            "best_abs_spearman"
                        ]
                    ),
                    show(
                        group[
                            "best_high_leader_win_rate_pct"
                        ],
                        "%",
                    ),
                    show(
                        group[
                            "best_low_leader_win_rate_pct"
                        ],
                        "%",
                    ),
                ]
                for group
                in info[
                    "groups"
                ]
            ],
        )

        if info[
            "redundancy"
        ]:

            lines += [
                "",
                "### 要素どうしの重複チェック",
                "",
            ]

            lines += table(
                [
                    "要素A",
                    "要素B",
                    "順位相関",
                    "判定",
                ],
                [
                    [
                        row[
                            "label_a"
                        ],
                        row[
                            "label_b"
                        ],
                        row[
                            "rank_spearman"
                        ],
                        (
                            "重複強め"
                            if row[
                                "high_overlap_flag"
                            ]
                            else "—"
                        ),
                    ]
                    for row
                    in info[
                        "redundancy"
                    ]
                ],
            )

    lines += [
        "",
        "## 注意",
        "",
        (
            "- 1日分だけでは配点を確定しません。"
            "数日〜数週間の同じ指標を蓄積して"
            "再現性を確認します。"
        ),
        (
            "- `構成点なし（代理指標）` は、"
            "現在の予測JSONに実際の加点内訳が"
            "保存されていないため、予測前の元データで"
            "代用しています。"
        ),
        (
            "- 実際の着順は評価対象としてのみ使用し、"
            "予測入力には戻しません。"
        ),
        "",
    ]

    markdown = (
        "\n".join(
            lines
        )
        + "\n"
    )

    (
        output_dir
        / (
            f"score_component_"
            f"analysis_{date}.md"
        )
    ).write_text(
        markdown,
        encoding="utf-8",
    )

    Path(
        "evaluations/"
        "latest_score_analysis.md"
    ).write_text(
        markdown,
        encoding="utf-8",
    )

    print(
        "スコア配分・実レース結果の自動答え合わせ: PASS"
    )

    print(
        output_dir
        / (
            f"score_component_"
            f"analysis_{date}.md"
        )
    )

    print(
        "evaluations/latest_score_analysis.md"
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )