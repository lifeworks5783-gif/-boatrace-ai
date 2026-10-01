#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd


# 現在の morning_heuristic_v2 配点
WEIGHTS = {
    "frame": 31,
    "official_racer": 17,
    "recent_racer": 20,
    "racer_venue": 10,
    "motor": 14,
    "boat_machine": 4,
    "grade": 4,
}

LABEL = {
    "frame": "枠・コース",
    "official_racer": "選手公式能力",
    "recent_racer": "選手直近成績",
    "racer_venue": "当地・場適性",
    "motor": "モーター",
    "boat_machine": "ボート",
    "grade": "級別",
    "total_score": "総合スコア",
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


def nkey(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9_]+",
        "_",
        str(value).strip().lower(),
    ).strip("_")


def to_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None

    try:
        number = float(
            str(value)
            .strip()
            .replace(",", "")
            .replace("%", "")
        )
    except Exception:
        return None

    if not math.isfinite(number):
        return None

    return number


def to_int(value: Any) -> Optional[int]:
    number = to_float(value)

    if number is None:
        return None

    return int(number)


def venue(value: Any) -> str:
    try:
        return f"{int(float(value)):02d}"
    except Exception:
        return str(value or "").strip().zfill(2)


def flatten(
    obj: Any,
    prefix: str = "",
) -> Dict[str, Any]:
    output: Dict[str, Any] = {}

    if not isinstance(obj, dict):
        return output

    for key, value in obj.items():
        path = (
            f"{prefix}.{nkey(key)}"
            if prefix
            else nkey(key)
        )

        if isinstance(value, dict):
            output.update(
                flatten(
                    value,
                    path,
                )
            )

        elif not isinstance(value, list):
            output[path] = value

    return output


def parse_race_id(
    value: Any,
) -> Tuple[
    str,
    str,
    Optional[int],
]:
    match = re.search(
        r"(\d{8})[-_](\d{2})[-_](\d{1,2})",
        str(value or ""),
    )

    if not match:
        return "", "", None

    return (
        match.group(1),
        match.group(2),
        int(match.group(3)),
    )


def load_json(
    path: Path,
) -> Any:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def boat_records(
    root: Any,
    default_date: str,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    def walk(
        node: Any,
        context: Dict[str, Any],
    ) -> None:
        if isinstance(node, dict):
            current = dict(context)

            if "race_id" in node:
                (
                    race_date,
                    race_venue,
                    race_no,
                ) = parse_race_id(
                    node.get("race_id")
                )

                if race_date:
                    current["date"] = race_date

                if race_venue:
                    current["venue_code"] = race_venue

                if race_no is not None:
                    current["race"] = race_no

            for source, target in (
                ("date", "date"),
                ("target_date", "date"),
                ("venue_code", "venue_code"),
                ("jcd", "venue_code"),
                ("race", "race"),
                ("rno", "race"),
            ):
                if (
                    source in node
                    and not isinstance(
                        node[source],
                        (dict, list),
                    )
                ):
                    current[target] = node[source]

            boat_no = None

            for key in (
                "boat",
                "frame",
                "lane",
            ):
                if (
                    key in node
                    and not isinstance(
                        node[key],
                        (dict, list),
                    )
                ):
                    candidate = to_int(
                        node[key]
                    )

                    if (
                        candidate is not None
                        and 1 <= candidate <= 6
                    ):
                        boat_no = candidate
                        break

            if (
                boat_no is not None
                and current.get("race") is not None
            ):
                rows.append(
                    {
                        "date": str(
                            current.get(
                                "date",
                                default_date,
                            )
                        ),
                        "venue_code": venue(
                            current.get(
                                "venue_code",
                                "",
                            )
                        ),
                        "race": to_int(
                            current.get("race")
                        ),
                        "boat": boat_no,
                        "raw": node,
                    }
                )

            for child in node.values():
                if isinstance(
                    child,
                    (dict, list),
                ):
                    walk(
                        child,
                        current,
                    )

        elif isinstance(node, list):
            for child in node:
                walk(
                    child,
                    context,
                )

    walk(
        root,
        {
            "date": default_date
        },
    )

    dedup: Dict[
        Tuple[
            str,
            str,
            int,
            int,
        ],
        Dict[str, Any],
    ] = {}

    for row in rows:
        if row["race"] is None:
            continue

        key = (
            row["date"],
            row["venue_code"],
            int(row["race"]),
            int(row["boat"]),
        )

        score_hint = any(
            name in row["raw"]
            for name in (
                "score",
                "total_score",
                "final_score",
                "prediction_score",
                "score_components",
                "component_scores",
                "components",
                "breakdown",
                "score_breakdown",
            )
        )

        if (
            key not in dedup
            or score_hint
        ):
            dedup[key] = row

    return list(
        dedup.values()
    )


def discover(
    patterns: Iterable[str],
) -> List[Path]:
    output: List[Path] = []
    seen = set()

    for pattern in patterns:
        for path in Path(".").glob(
            pattern
        ):
            if (
                path.is_file()
                and str(path) not in seen
            ):
                seen.add(
                    str(path)
                )
                output.append(path)

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
        if stage == "morning":
            patterns = [
                (
                    f"predictions/"
                    f"{year}/{month}/{day}/"
                    f"morning_predictions_{date}.json"
                ),
                (
                    f"predictions/"
                    f"{year}/{month}/{day}/"
                    f"morning/**/*final*.json"
                ),
                (
                    f"predictions/"
                    f"{year}/{month}/{day}/"
                    f"morning/**/*prediction*.json"
                ),
                (
                    f"data/"
                    f"*morning*predictions*"
                    f"{date}*.json"
                ),
            ]

        else:
            patterns = [
                (
                    f"predictions/"
                    f"{year}/{month}/{day}/"
                    f"live/"
                    f"live_predictions_final_{date}.json"
                ),
                (
                    f"predictions/"
                    f"{year}/{month}/{day}/"
                    f"live/**/*final*.json"
                ),
                (
                    f"predictions/"
                    f"{year}/{month}/{day}/"
                    f"live/**/*prediction*.json"
                ),
                (
                    f"data/"
                    f"*live*predictions*"
                    f"{date}*.json"
                ),
            ]

    else:
        patterns = [
            (
                f"data/"
                f"prediction_input_enriched_"
                f"{stage}_{date}.json"
            ),
            (
                f"data/"
                f"prediction_input_"
                f"{stage}_{date}.json"
            ),
            (
                f"daily_inputs/"
                f"{year}/{month}/{day}/"
                f"{stage}/"
                f"**/*enriched*.json"
            ),
            (
                f"daily_inputs/"
                f"{year}/{month}/{day}/"
                f"{stage}/"
                f"**/*prediction_input*.json"
            ),
            (
                f"daily_inputs/"
                f"{year}/{month}/{day}/"
                f"**/*{stage}*enriched*.json"
            ),
            (
                f"daily_inputs/"
                f"{year}/{month}/{day}/"
                f"**/*{stage}*prediction_input*.json"
            ),
        ]

    candidates = []

    for path in discover(
        patterns
    ):
        try:
            count = len(
                boat_records(
                    load_json(path),
                    date,
                )
            )

            bonus = 0

            if (
                kind == "prediction"
                and "final"
                in path.name.lower()
            ):
                bonus += 2

            if (
                kind == "input"
                and "enriched"
                in path.name.lower()
            ):
                bonus += 1

            candidates.append(
                (
                    bonus,
                    count,
                    path,
                )
            )

        except Exception:
            continue

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda item: (
            item[0],
            item[1],
        ),
    )[2]


def total_score(
    raw: Dict[str, Any],
) -> Optional[float]:
    for key in (
        "total_score",
        "final_score",
        "prediction_score",
        "score",
    ):
        if key in raw:
            value = to_float(
                raw[key]
            )

            if value is not None:
                return value

    for path, value in flatten(
        raw
    ).items():
        leaf = path.split(".")[-1]

        if leaf not in (
            "total_score",
            "final_score",
            "prediction_score",
            "score",
        ):
            continue

        if (
            "component" in path
            or "breakdown" in path
        ):
            continue

        number = to_float(
            value
        )

        if number is not None:
            return number

    return None


def component_scores(
    raw: Dict[str, Any],
) -> Dict[str, float]:
    sources: List[
        Dict[str, Any]
    ] = []

    for key in (
        "score_components",
        "component_scores",
        "components",
        "breakdown",
        "score_breakdown",
    ):
        if isinstance(
            raw.get(key),
            dict,
        ):
            sources.append(
                raw[key]
            )

    sources.append(raw)

    output: Dict[
        str,
        float,
    ] = {}

    for group, aliases in (
        COMP_ALIASES.items()
    ):
        for source in sources:
            for path, value in flatten(
                source
            ).items():
                if (
                    path.split(".")[-1]
                    not in aliases
                ):
                    continue

                number = to_float(
                    value
                )

                if number is not None:
                    output[group] = number
                    break

            if group in output:
                break

    return output


def feature_group(
    path: str,
) -> Optional[str]:
    lower = path.lower()

    if any(
        word in lower
        for word in (
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
    ):
        return None

    if (
        "history.racer_30d"
        in lower
        or "history.racer_90d"
        in lower
        or "recent"
        in lower
    ):
        return "recent_racer"

    if (
        "history.motor_30d"
        in lower
        or "history.motor_90d"
        in lower
    ):
        return "motor"

    if (
        "official_stats.local_"
        in lower
        or "local_win"
        in lower
        or "local_top"
        in lower
    ):
        return "racer_venue"

    if (
        "official_stats.national_"
        in lower
        or "national_win"
        in lower
        or "national_top"
        in lower
    ):
        return "official_racer"

    if (
        lower.startswith("motor.")
        or ".motor."
        in lower
    ):
        return "motor"

    if "boat_machine" in lower:
        return "boat_machine"

    return None


def input_frame(
    path: Optional[Path],
    date: str,
) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()

    rows = []

    for record in boat_records(
        load_json(path),
        date,
    ):
        raw = record["raw"]

        row: Dict[
            str,
            Any,
        ] = {
            "date": record["date"],
            "venue_code": record[
                "venue_code"
            ],
            "race": record["race"],
            "boat": record["boat"],
            (
                "feature.frame."
                "frame_advantage"
            ): (
                7
                - int(
                    record["boat"]
                )
            ),
        }

        for key, value in flatten(
            raw
        ).items():
            group = feature_group(
                key
            )

            number = to_float(
                value
            )

            if (
                group
                and number is not None
            ):
                row[
                    f"feature."
                    f"{group}."
                    f"{key}"
                ] = number

        rows.append(row)

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
        load_json(path),
        date,
    ):
        row: Dict[
            str,
            Any,
        ] = {
            "date": record["date"],
            "venue_code": record[
                "venue_code"
            ],
            "race": record["race"],
            "boat": record["boat"],
            "total_score": total_score(
                record["raw"]
            ),
        }

        for group, value in (
            component_scores(
                record["raw"]
            ).items()
        ):
            row[
                f"component.{group}"
            ] = value

        rows.append(row)

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
            item
            for item in paths
            if item.exists()
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

    missing = (
        required
        - set(
            dataframe.columns
        )
    )

    if missing:
        raise ValueError(
            "result columns missing: "
            + str(
                sorted(missing)
            )
        )

    dataframe["date"] = (
        dataframe["date"]
        .astype(str)
        .str.replace(
            ".0",
            "",
            regex=False,
        )
    )

    dataframe[
        "venue_code"
    ] = dataframe[
        "venue_code"
    ].map(
        venue
    )

    dataframe["race"] = (
        pd.to_numeric(
            dataframe["race"],
            errors="coerce",
        )
    )

    dataframe["boat"] = (
        pd.to_numeric(
            dataframe["boat"],
            errors="coerce",
        )
    )

    dataframe[
        "finish_num"
    ] = pd.to_numeric(
        dataframe["finish"],
        errors="coerce",
    )

    return dataframe[
        [
            "date",
            "venue_code",
            "race",
            "boat",
            "finish_num",
        ]
    ].dropna()


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

    dataframe = result.copy()

    if not input_data.empty:
        dataframe = dataframe.merge(
            input_data,
            on=keys,
            how="left",
        )

    if not prediction_data.empty:
        dataframe = dataframe.merge(
            prediction_data,
            on=keys,
            how="left",
        )

    meta = {
        "input_file": (
            str(input_path)
            if input_path
            else None
        ),
        "prediction_file": (
            str(prediction_path)
            if prediction_path
            else None
        ),
        "score_rows": (
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
            if (
                "total_score"
                in dataframe.columns
            )
            else 0
        ),
        "component_columns": [
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
            "date",
            "venue_code",
            "race",
            "finish_num",
            column,
        ]
    ].copy()

    work[column] = (
        pd.to_numeric(
            work[column],
            errors="coerce",
        )
    )

    work = work.dropna()

    if (
        len(work) < 30
        or work[column].nunique()
        < 2
    ):
        return None

    work["race_key"] = (
        work["date"].astype(str)
        + "-"
        + work[
            "venue_code"
        ].astype(str)
        + "-"
        + work["race"].astype(str)
    )

    work["rank_high"] = (
        work.groupby(
            "race_key"
        )[column]
        .rank(
            method="average",
            ascending=False,
        )
    )

    correlation = (
        work["rank_high"]
        .corr(
            work["finish_num"],
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
                    column,
                    ascending=True,
                )
                .iloc[0][
                    "finish_num"
                ]
            )
        )

    if not high_finish:
        return None

    return {
        "column": column,
        "rows": int(
            len(work)
        ),
        "races": len(
            high_finish
        ),
        "rank_finish_spearman": (
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
        "high_leader_win_rate_pct": (
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
            )
        ),
        "low_leader_win_rate_pct": (
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
            )
        ),
        "high_leader_top3_rate_pct": (
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
            )
        ),
        "low_leader_top3_rate_pct": (
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
            )
        ),
    }


def score_calibration(
    dataframe: pd.DataFrame,
) -> Dict[str, Any]:
    if (
        "total_score"
        not in dataframe.columns
    ):
        return {}

    work = dataframe[
        [
            "date",
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
        work["total_score"],
        errors="coerce",
    )

    work = work.dropna()

    rows = []

    for (
        race_date,
        venue_code,
        race_no,
    ), race_data in (
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
                "date": race_date,
                "venue_code": (
                    venue_code
                ),
                "race": int(
                    race_no
                ),
                "top_boat": int(
                    first["boat"]
                ),
                "top_score": float(
                    first[
                        "total_score"
                    ]
                ),
                "gap": float(
                    first[
                        "total_score"
                    ]
                    - second[
                        "total_score"
                    ]
                ),
                "top_finish": float(
                    first[
                        "finish_num"
                    ]
                ),
                "top_win": int(
                    first[
                        "finish_num"
                    ]
                    == 1
                ),
                "top3": int(
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
        result["gap"],
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
                "gap_bucket": label,
                "races": len(
                    bucket
                ),
                "win_rate_pct": (
                    round(
                        bucket[
                            "top_win"
                        ].mean()
                        * 100,
                        1,
                    )
                ),
                "top3_rate_pct": (
                    round(
                        bucket[
                            "top3"
                        ].mean()
                        * 100,
                        1,
                    )
                ),
                "mean_finish": (
                    round(
                        bucket[
                            "top_finish"
                        ].mean(),
                        2,
                    )
                ),
            }
        )

    return {
        "races": len(
            result
        ),
        "top_score_win_rate_pct": (
            round(
                result[
                    "top_win"
                ].mean()
                * 100,
                1,
            )
        ),
        "top_score_top3_rate_pct": (
            round(
                result[
                    "top3"
                ].mean()
                * 100,
                1,
            )
        ),
        "mean_top_finish": (
            round(
                result[
                    "top_finish"
                ].mean(),
                2,
            )
        ),
        "gap_buckets": buckets,
        "race_rows": rows,
    }


def group_of_column(
    column: str,
) -> str:
    if column.startswith(
        "component."
    ):
        return column.split(
            ".",
            1,
        )[1]

    if column.startswith(
        "feature."
    ):
        return column.split(
            ".",
            2,
        )[1]

    return "total_score"


def group_summary(
    stats: List[
        Dict[str, Any]
    ],
) -> List[
    Dict[str, Any]
]:
    output = []

    for group in list(
        WEIGHTS
    ):
        subset = [
            item
            for item in stats
            if item["group"]
            == group
        ]

        best = max(
            subset,
            key=lambda item: abs(
                item[
                    "rank_finish_spearman"
                ]
                or 0
            ),
            default=None,
        )

        output.append(
            {
                "group": group,
                "label": LABEL.get(
                    group,
                    group,
                ),
                "current_weight": (
                    WEIGHTS.get(
                        group
                    )
                ),
                "features_tested": (
                    len(
                        subset
                    )
                ),
                (
                    "exact_component_"
                    "available"
                ): any(
                    item[
                        "kind"
                    ]
                    == (
                        "exact_component"
                    )
                    for item
                    in subset
                ),
                "best_feature": (
                    best[
                        "column"
                    ]
                    if best
                    else None
                ),
                "best_abs_spearman": (
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
                (
                    "best_high_leader_"
                    "win_rate_pct"
                ): (
                    best[
                        "high_leader_win_rate_pct"
                    ]
                    if best
                    else None
                ),
                (
                    "best_low_leader_"
                    "win_rate_pct"
                ): (
                    best[
                        "low_leader_win_rate_pct"
                    ]
                    if best
                    else None
                ),
            }
        )

    return output


def markdown_table(
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

    for row in rows:
        output.append(
            "| "
            + " | ".join(
                str(value)
                for value
                in row
            )
            + " |"
        )

    return output


def show(
    value: Any,
    suffix: str = "",
) -> str:
    if value is None:
        return "—"

    return (
        f"{value}"
        f"{suffix}"
    )


def main() -> int:
    parser = (
        argparse.ArgumentParser()
    )

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
        (
            dataframe,
            meta,
        ) = stage_frame(
            date,
            stage,
            results,
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
                or column.startswith(
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

            if not stat:
                continue

            stat[
                "stage"
            ] = stage

            stat[
                "group"
            ] = group_of_column(
                column
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
                ] = "total_score"

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
                    f"{stage}_{date}.csv"
                ),
                index=False,
                encoding="utf-8-sig",
            )

        stages[
            stage
        ] = {
            "meta": meta,
            "score_calibration": {
                key: value
                for key, value
                in calibration.items()
                if key
                != "race_rows"
            },
            "groups": (
                group_summary(
                    stats
                )
            ),
        }

    if all_frames:
        pd.concat(
            all_frames,
            ignore_index=True,
            sort=False,
        ).to_csv(
            output_dir
            / (
                "score_answer_check_"
                f"boats_{date}.csv"
            ),
            index=False,
            encoding="utf-8-sig",
        )

    stat_columns = [
        "column",
        "rows",
        "races",
        "rank_finish_spearman",
        "high_leader_win_rate_pct",
        "low_leader_win_rate_pct",
        "high_leader_top3_rate_pct",
        "low_leader_top3_rate_pct",
        "stage",
        "group",
        "kind",
    ]

    if all_stats:
        stats_frame = pd.DataFrame(
            all_stats
        )

    else:
        stats_frame = pd.DataFrame(
            columns=stat_columns
        )

    stats_frame.to_csv(
        output_dir
        / (
            "score_feature_stats_"
            f"{date}.csv"
        ),
        index=False,
        encoding="utf-8-sig",
    )

    report = {
        "date": date,
        "model_version": (
            "morning_heuristic_v2"
        ),
        "current_weights": WEIGHTS,
        "stage_analysis": stages,
        "note": (
            "Descriptive answer-check only. "
            "Actual finish is evaluation "
            "target only and is never fed "
            "back into pre-race features."
        ),
    }

    (
        output_dir
        / (
            "score_component_"
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
        (
            "# スコア配分・"
            "実レース結果 自動答え合わせ"
        ),
        "",
        (
            f"対象日："
            f"{date[:4]}/"
            f"{date[4:6]}/"
            f"{date[6:8]}"
        ),
        "",
        (
            "> 配点を自動変更する"
            "レポートではありません。"
            "予測時点の情報と"
            "実際の着順を照合し、"
            "配点見直しの根拠を"
            "蓄積します。"
        ),
        "",
        (
            "## 現在の配点"
            "（morning_heuristic_v2）"
        ),
        "",
    ]

    lines += markdown_table(
        [
            "要素",
            "配点",
        ],
        [
            [
                LABEL[key],
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

        calibration = info[
            "score_calibration"
        ]

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
                (
                    "### 総合スコアの"
                    "答え合わせ"
                ),
                "",
                (
                    "- スコア1位艇の1着率："
                    f"**{show(calibration.get('top_score_win_rate_pct'), '%')}**"
                ),
                (
                    "- スコア1位艇の3着内率："
                    f"**{show(calibration.get('top_score_top3_rate_pct'), '%')}**"
                ),
                (
                    "- スコア1位艇の平均着順："
                    f"**{show(calibration.get('mean_top_finish'))}**"
                ),
                "",
                "#### 1位−2位スコア差別",
                "",
            ]

            lines += markdown_table(
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

        lines += markdown_table(
            [
                "要素",
                "現配点",
                "検証項目",
                "構成点",
                (
                    "最も関連が"
                    "強い指標"
                ),
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
                        else (
                            "なし"
                            "（代理指標）"
                        )
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

    lines += [
        "",
        "## 注意",
        "",
        (
            "- 1日分だけでは"
            "配点を確定しません。"
            "7日・30日など"
            "複数日の再現性を"
            "確認します。"
        ),
        (
            "- `構成点なし（代理指標）` は、"
            "予測JSONに実際の"
            "加点内訳がないため、"
            "予測前の元データで"
            "代用しています。"
        ),
        (
            "- 実際の着順は"
            "評価対象としてのみ使用し、"
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
            "score_component_"
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
        "スコア配分・実レース結果の"
        "自動答え合わせ: PASS"
    )

    print(
        output_dir
        / (
            "score_component_"
            f"analysis_{date}.md"
        )
    )

    print(
        "evaluations/"
        "latest_score_analysis.md"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )