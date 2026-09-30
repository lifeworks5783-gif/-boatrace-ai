#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


# =========================================================
# 設定
# =========================================================

LIVE_HINTS = (
    "beforeinfo",
    "before_info",
    "exhibition",
    "tenji",
    "display",
    "start_exhibition",
    "start_display",
    "live",
)

DATE_KEYS = (
    "date",
    "target_date",
    "hd",
)

VENUE_KEYS = (
    "venue_code",
    "jcd",
    "stadium_code",
)

RACE_KEYS = (
    "race",
    "rno",
    "race_no",
)

BOAT_KEYS = (
    "boat",
    "frame",
    "lane",
    "wakuban",
    "waku",
    "frame_no",
    "lane_no",
    "boat_number",
)

TIME_KEYS = {
    "exhibition_time",
    "tenji_time",
    "display_time",
    "exhibit_time",
    "tenjitime",
    "displaytime",
}

ST_KEYS = {
    "exhibition_st",
    "tenji_st",
    "display_st",
    "start_exhibition_st",
    "start_display_st",
    "start_timing",
    "start_time",
    "starttiming",
    "st",
}

COURSE_KEYS = {
    "exhibition_course",
    "tenji_course",
    "display_course",
    "start_exhibition_course",
    "start_display_course",
    "course",
}

WIND_SPEED_KEYS = {
    "wind_speed",
    "windspeed",
    "wind_mps",
}

WIND_DIRECTION_KEYS = {
    "wind_direction",
    "winddirection",
    "wind_dir",
    "wind",
}

WAVE_KEYS = {
    "wave_height",
    "waveheight",
    "wave_cm",
    "wave",
}


SEEN_LIVE_KEYS: set[str] = set()


# =========================================================
# 基本変換
# =========================================================


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


def normalize_date(
    value: Any,
) -> str:

    text = (
        str(value or "")
        .strip()
    )

    if text.endswith(
        ".0"
    ):
        text = text[:-2]

    digits = re.sub(
        r"\D",
        "",
        text,
    )

    if len(
        digits
    ) >= 8:
        return digits[:8]

    return text


def venue(
    value: Any,
) -> str:

    try:

        return (
            f"{int(float(value)):02d}"
        )

    except Exception:

        return (
            str(
                value or ""
            )
            .strip()
            .zfill(2)
        )


def to_int(
    value: Any,
) -> Optional[int]:

    try:

        return int(
            float(value)
        )

    except Exception:

        return None


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

        return float(
            value
        )

    text = (
        str(value)
        .strip()
        .replace(",", "")
        .replace("秒", "")
        .replace("cm", "")
    )

    match = re.search(
        r"-?\d+(?:\.\d+)?",
        text,
    )

    if not match:

        return None

    try:

        return float(
            match.group()
        )

    except Exception:

        return None


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
        if text.startswith(
            "F"
        )
        else 0
    )

    late = (
        1
        if text.startswith(
            "L"
        )
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

    # "09" → 0.09 などに対応
    if (
        number >= 1
        and "."
        not in match.group()
    ):

        number = (
            number / 100
        )

    if flying:

        number = (
            -abs(
                number
            )
        )

    elif late:

        number = (
            abs(
                number
            )
        )

    if not (
        -1
        < number
        < 1
    ):

        return (
            None,
            flying,
        )

    return (
        number,
        flying,
    )


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
            value or ""
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


def normalize_merge_keys(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:

    dataframe = (
        dataframe.copy()
    )

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
            not in dataframe.columns
        ):
            continue

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


# =========================================================
# 直前データファイル探索
# =========================================================


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

        for path in (
            Path(".")
            .glob(
                pattern
            )
        ):

            if not path.is_file():

                continue

            text = (
                str(path)
                .lower()
            )

            if text in seen:

                continue

            if not any(
                hint in text
                for hint
                in LIVE_HINTS
            ):

                continue

            if any(
                bad in text
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
                text
            )

            output.append(
                path
            )

    return sorted(
        output
    )


# =========================================================
# JSON解析
# =========================================================


def flatten_dict(
    value: Any,
    prefix: str = "",
) -> Dict[
    str,
    Any,
]:

    output = {}

    if not isinstance(
        value,
        dict,
    ):

        return output

    for (
        key,
        child,
    ) in value.items():

        child_key = (
            nkey(
                key
            )
        )

        child_path = (
            f"{prefix}.{child_key}"
            if prefix
            else child_key
        )

        if isinstance(
            child,
            dict,
        ):

            output.update(
                flatten_dict(
                    child,
                    child_path,
                )
            )

        elif not isinstance(
            child,
            list,
        ):

            output[
                child_path
            ] = child

    return output


def is_live_context(
    feature_path: str,
    source: str,
) -> bool:

    combined = (
        feature_path.lower()
        + " "
        + source.lower()
    )

    return any(
        hint in combined
        for hint
        in LIVE_HINTS
    )


def extract_features(
    raw: Dict[
        str,
        Any,
    ],
    source: str,
) -> Dict[
    str,
    Any,
]:

    flat = (
        flatten_dict(
            raw
        )
    )

    features: Dict[
        str,
        Any,
    ] = {}

    for (
        path,
        value,
    ) in flat.items():

        leaf = (
            path
            .split(".")[-1]
        )

        lower_path = (
            path.lower()
        )

        live_context = (
            is_live_context(
                lower_path,
                source,
            )
        )

        # 後で項目名が分からなくても確認できるよう保存
        if any(
            token in lower_path
            for token
            in (
                "st",
                "start",
                "tenji",
                "display",
                "exhibition",
                "wind",
                "wave",
            )
        ):

            SEEN_LIVE_KEYS.add(
                path
            )

        # -------------------------
        # 展示タイム
        # -------------------------

        time_candidate = (
            leaf
            in TIME_KEYS
            or (
                leaf
                in (
                    "time",
                    "time_value",
                )
                and live_context
            )
        )

        if time_candidate:

            number = (
                to_float(
                    value
                )
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

        # -------------------------
        # 展示ST
        # -------------------------

        st_candidate = (
            leaf
            in ST_KEYS
            or (
                leaf.endswith(
                    "_st"
                )
                and live_context
            )
            or (
                leaf
                in (
                    "start",
                    "start_value",
                )
                and live_context
            )
        )

        if (
            st_candidate
            and live_context
        ):

            (
                st_value,
                flying,
            ) = parse_st(
                value
            )

            if (
                st_value
                is not None
            ):

                features[
                    "exhibition_st"
                ] = st_value

                features[
                    "exhibition_f"
                ] = max(
                    int(
                        features.get(
                            "exhibition_f",
                            0,
                        )
                    ),
                    flying,
                )

        # -------------------------
        # 展示進入
        # -------------------------

        course_candidate = (
            leaf
            in COURSE_KEYS
            or (
                leaf.endswith(
                    "_course"
                )
                and live_context
            )
        )

        if (
            course_candidate
            and live_context
        ):

            number = (
                to_int(
                    value
                )
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

        # -------------------------
        # 風速
        # -------------------------

        if (
            leaf
            in WIND_SPEED_KEYS
        ):

            number = (
                to_float(
                    value
                )
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

        # -------------------------
        # 風向
        # -------------------------

        if (
            leaf
            in WIND_DIRECTION_KEYS
        ):

            text = (
                str(
                    value or ""
                )
                .strip()
            )

            if text:

                features[
                    "wind_direction"
                ] = text

        # -------------------------
        # 波高
        # -------------------------

        if (
            leaf
            in WAVE_KEYS
        ):

            number = (
                to_float(
                    value
                )
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

        # -------------------------
        # 展示F
        # -------------------------

        if (
            leaf
            in (
                "f",
                "is_f",
                "flying",
                "exhibition_f",
                "tenji_f",
            )
            or
            "flying"
            in leaf
        ):

            text = (
                str(
                    value or ""
                )
                .strip()
                .lower()
            )

            number = (
                to_float(
                    value
                )
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
                    number
                    is not None
                    and number
                    > 0
                )
            ):

                features[
                    "exhibition_f"
                ] = 1

    return features


def update_context(
    node: Dict[
        str,
        Any,
    ],
    context: Dict[
        str,
        Any,
    ],
) -> Dict[
    str,
    Any,
]:

    current = dict(
        context
    )

    if "race_id" in node:

        (
            race_date,
            race_venue,
            race_no,
        ) = parse_race_id(
            node.get(
                "race_id"
            )
        )

        if race_date:

            current[
                "date"
            ] = race_date

        if race_venue:

            current[
                "venue_code"
            ] = race_venue

        if (
            race_no
            is not None
        ):

            current[
                "race"
            ] = race_no

    normalized = {
        nkey(key):
            value
        for (
            key,
            value,
        ) in node.items()
        if not isinstance(
            value,
            (
                dict,
                list,
            ),
        )
    }

    for key in DATE_KEYS:

        key_name = (
            nkey(
                key
            )
        )

        if (
            key_name
            in normalized
        ):

            current[
                "date"
            ] = normalized[
                key_name
            ]

            break

    for key in VENUE_KEYS:

        key_name = (
            nkey(
                key
            )
        )

        if (
            key_name
            in normalized
        ):

            current[
                "venue_code"
            ] = normalized[
                key_name
            ]

            break

    for key in RACE_KEYS:

        key_name = (
            nkey(
                key
            )
        )

        if (
            key_name
            in normalized
        ):

            current[
                "race"
            ] = normalized[
                key_name
            ]

            break

    for key in BOAT_KEYS:

        key_name = (
            nkey(
                key
            )
        )

        if (
            key_name
            not in normalized
        ):

            continue

        boat = (
            to_int(
                normalized[
                    key_name
                ]
            )
        )

        if (
            boat is not None
            and 1
            <= boat
            <= 6
        ):

            current[
                "boat"
            ] = boat

            break

    return current


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
    ) -> None:

        if isinstance(
            node,
            dict,
        ):

            current = (
                update_context(
                    node,
                    context,
                )
            )

            features = (
                extract_features(
                    node,
                    source,
                )
            )

            race_no = (
                to_int(
                    current.get(
                        "race"
                    )
                )
            )

            boat_no = (
                to_int(
                    current.get(
                        "boat"
                    )
                )
            )

            if (
                race_no
                is not None
                and features
            ):

                rows.append(
                    {
                        "date":
                            normalize_date(
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
                            race_no,

                        "boat":
                            boat_no,

                        "source":
                            source,

                        **features,
                    }
                )

            for child in (
                node.values()
            ):

                if isinstance(
                    child,
                    (
                        dict,
                        list,
                    ),
                ):

                    walk(
                        child,
                        current,
                    )

        elif isinstance(
            node,
            list,
        ):

            for child in node:

                walk(
                    child,
                    context,
                )

    walk(
        obj,
        {
            "date":
                date
        },
    )

    return rows


# =========================================================
# CSV解析
# =========================================================


def find_column(
    columns: Dict[
        str,
        str,
    ],
    names: Tuple[
        str,
        ...,
    ],
) -> Optional[str]:

    for name in names:

        key = (
            nkey(
                name
            )
        )

        if key in columns:

            return columns[
                key
            ]

    return None


def read_csv_rows(
    path: Path,
    date: str,
) -> List[
    Dict[
        str,
        Any,
    ]
]:

    try:

        dataframe = (
            pd.read_csv(
                path
            )
        )

    except Exception:

        return []

    columns = {
        nkey(column):
            column
        for column
        in dataframe.columns
    }

    date_column = (
        find_column(
            columns,
            DATE_KEYS,
        )
    )

    venue_column = (
        find_column(
            columns,
            VENUE_KEYS,
        )
    )

    race_column = (
        find_column(
            columns,
            RACE_KEYS,
        )
    )

    boat_column = (
        find_column(
            columns,
            BOAT_KEYS,
        )
    )

    if (
        race_column
        is None
    ):

        return []

    rows = []

    for (
        _,
        source_row,
    ) in dataframe.iterrows():

        race_no = (
            to_int(
                source_row.get(
                    race_column
                )
            )
        )

        if (
            race_no
            is None
        ):

            continue

        boat_no = None

        if (
            boat_column
            is not None
        ):

            candidate = (
                to_int(
                    source_row.get(
                        boat_column
                    )
                )
            )

            if (
                candidate
                is not None
                and 1
                <= candidate
                <= 6
            ):

                boat_no = (
                    candidate
                )

        raw = {
            str(column):
                source_row.get(
                    column
                )
            for column
            in dataframe.columns
        }

        features = (
            extract_features(
                raw,
                str(
                    path
                ),
            )
        )

        if not features:

            continue

        rows.append(
            {
                "date":
                    normalize_date(
                        source_row.get(
                            date_column
                        )
                    )
                    if (
                        date_column
                        is not None
                    )
                    else date,

                "venue_code":
                    venue(
                        source_row.get(
                            venue_column
                        )
                    )
                    if (
                        venue_column
                        is not None
                    )
                    else "",

                "race":
                    race_no,

                "boat":
                    boat_no,

                "source":
                    str(
                        path
                    ),

                **features,
            }
        )

    return rows


# =========================================================
# 直前データ統合
# =========================================================


def last_non_null(
    series: pd.Series,
) -> Any:

    clean = (
        series.dropna()
    )

    if clean.empty:

        return None

    return clean.iloc[-1]


def load_live_features(
    date: str,
) -> pd.DataFrame:

    rows = []

    files = (
        candidate_files(
            date
        )
    )

    print(
        "candidate files:",
        len(
            files
        ),
    )

    for path in files:

        try:

            if (
                path.suffix.lower()
                == ".json"
            ):

                obj = (
                    json.loads(
                        path.read_text(
                            encoding="utf-8"
                        )
                    )
                )

                rows.extend(
                    walk_records(
                        obj,
                        date,
                        str(
                            path
                        ),
                    )
                )

            elif (
                path.suffix.lower()
                == ".csv"
            ):

                rows.extend(
                    read_csv_rows(
                        path,
                        date,
                    )
                )

        except Exception as exc:

            print(
                "skip:",
                path,
                exc,
            )

    if not rows:

        return (
            pd.DataFrame()
        )

    dataframe = (
        pd.DataFrame(
            rows
        )
    )

    dataframe = (
        normalize_merge_keys(
            dataframe
        )
    )

    race_keys = [
        "date",
        "venue_code",
        "race",
    ]

    boat_keys = (
        race_keys
        + [
            "boat"
        ]
    )

    feature_columns = [
        column
        for column
        in (
            "exhibition_time",
            "exhibition_st",
            "exhibition_f",
            "exhibition_course",
            "wind_speed",
            "wind_direction",
            "wave_height",
        )
        if (
            column
            in dataframe.columns
        )
    ]

    boat_rows = (
        dataframe[
            dataframe[
                "boat"
            ]
            .notna()
        ]
        .copy()
    )

    if boat_rows.empty:

        return (
            pd.DataFrame()
        )

    # 複数ファイルの情報を艇単位で統合
    aggregation = {
        column:
            last_non_null
        for column
        in feature_columns
    }

    aggregation[
        "source"
    ] = last_non_null

    boat_rows = (
        boat_rows
        .groupby(
            boat_keys,
            dropna=False,
            as_index=False,
        )
        .agg(
            aggregation
        )
    )

    # 風・波などレース単位の値を全艇へ配る
    weather_columns = [
        column
        for column
        in (
            "wind_speed",
            "wind_direction",
            "wave_height",
        )
        if (
            column
            in dataframe.columns
        )
    ]

    if weather_columns:

        weather = (
            dataframe[
                race_keys
                + weather_columns
            ]
            .groupby(
                race_keys,
                dropna=False,
                as_index=False,
            )
            .agg(
                {
                    column:
                        last_non_null
                    for column
                    in weather_columns
                }
            )
        )

        boat_rows = (
            boat_rows
            .merge(
                weather,
                on=race_keys,
                how="left",
                suffixes=(
                    "",
                    "_race",
                ),
            )
        )

        for column in (
            weather_columns
        ):

            race_column = (
                f"{column}_race"
            )

            if (
                race_column
                not in boat_rows.columns
            ):

                continue

            if (
                column
                not in boat_rows.columns
            ):

                boat_rows[
                    column
                ] = (
                    boat_rows[
                        race_column
                    ]
                )

            else:

                boat_rows[
                    column
                ] = (
                    boat_rows[
                        column
                    ]
                    .combine_first(
                        boat_rows[
                            race_column
                        ]
                    )
                )

            boat_rows.drop(
                columns=[
                    race_column
                ],
                inplace=True,
            )

    return (
        normalize_merge_keys(
            boat_rows
        )
    )


# =========================================================
# 結果
# =========================================================


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

    dataframe = (
        pd.read_csv(
            path
        )
    )

    dataframe = (
        normalize_merge_keys(
            dataframe
        )
    )

    dataframe[
        "finish"
    ] = (
        pd.to_numeric(
            dataframe[
                "finish"
            ],
            errors="coerce",
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
        .copy()
    )


# =========================================================
# 朝スコア
# =========================================================


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
            "score answer-check csv not found"
        )

    dataframe = (
        pd.read_csv(
            path
        )
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

    dataframe = (
        normalize_merge_keys(
            dataframe
        )
    )

    dataframe[
        "total_score"
    ] = (
        pd.to_numeric(
            dataframe[
                "total_score"
            ],
            errors="coerce",
        )
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


# =========================================================
# 個別要素分析
# =========================================================


def rank_metric(
    dataframe: pd.DataFrame,
    column: str,
    lower_better: bool = True,
) -> Dict[
    str,
    Any,
]:

    if (
        column
        not in dataframe.columns
    ):

        return {
            "available":
                False,
            "reason":
                "column not found",
        }

    work = (
        dataframe[
            [
                "venue_code",
                "race",
                "finish",
                column,
            ]
        ]
        .copy()
    )

    work[
        column
    ] = (
        pd.to_numeric(
            work[
                column
            ],
            errors="coerce",
        )
    )

    work.dropna(
        inplace=True
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
            or
            race_data[
                column
            ]
            .nunique()
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
            {
                "best_finish":
                    float(
                        best[
                            "finish"
                        ]
                    ),

                "worst_finish":
                    float(
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
                ascending=lower_better,
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
            "available":
                True,
            "races":
                0,
        }

    return {
        "available":
            True,

        "races":
            len(
                rows
            ),

        "best_win_rate_pct":
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
            ),

        "best_top3_rate_pct":
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
            ),

        "worst_win_rate_pct":
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
) -> Dict[
    str,
    Any,
]:

    if (
        column
        not in dataframe.columns
    ):

        return {
            "available":
                False,
            "reason":
                "column not found",
        }

    work = (
        dataframe[
            [
                "finish",
                column,
            ]
        ]
        .copy()
    )

    work[
        column
    ] = (
        pd.to_numeric(
            work[
                column
            ],
            errors="coerce",
        )
    )

    work.dropna(
        inplace=True
    )

    if work.empty:

        return {
            "available":
                True,
            "boats":
                0,
        }

    flagged = (
        work[
            work[
                column
            ]
            > 0
        ]
    )

    normal = (
        work[
            work[
                column
            ]
            <= 0
        ]
    )

    return {
        "available":
            True,

        "boats":
            len(
                work
            ),

        "flagged_boats":
            len(
                flagged
            ),

        "flagged_win_rate_pct":
            (
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

        "flagged_top3_rate_pct":
            (
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

        "unflagged_win_rate_pct":
            (
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

        "unflagged_top3_rate_pct":
            (
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


# =========================================================
# 展示進入
# =========================================================


def build_course_changed(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:

    dataframe = (
        dataframe.copy()
    )

    if (
        "exhibition_course"
        not in dataframe.columns
    ):

        return dataframe

    course = (
        pd.to_numeric(
            dataframe[
                "exhibition_course"
            ],
            errors="coerce",
        )
    )

    boat = (
        pd.to_numeric(
            dataframe[
                "boat"
            ],
            errors="coerce",
        )
    )

    dataframe[
        "course_changed"
    ] = (
        (
            course
            != boat
        )
        & course.notna()
    ).astype(float)

    return dataframe


# =========================================================
# 風速分析
# =========================================================


def wind_analysis(
    dataframe: pd.DataFrame,
) -> List[
    Dict[
        str,
        Any,
    ]
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

    for (
        _,
        race_data,
    ) in work.groupby(
        [
            "venue_code",
            "race",
        ]
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

        if (
            wind_speed
            < 3
        ):

            bucket = (
                "0-2m"
            )

        elif (
            wind_speed
            < 5
        ):

            bucket = (
                "3-4m"
            )

        else:

            bucket = (
                "5m以上"
            )

        boat1 = (
            race_data[
                race_data[
                    "boat"
                ]
                == 1
            ]
        )

        if boat1.empty:

            continue

        rows.append(
            {
                "bucket":
                    bucket,

                "boat1_win":
                    int(
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
                "bucket":
                    bucket,

                "races":
                    len(
                        values
                    ),

                "boat1_win_rate_pct":
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
                    ),
            }
        )

    return output


# =========================================================
# 重み探索
# =========================================================


def normalize_factor(
    race_data: pd.DataFrame,
    column: str,
    lower_better: bool,
) -> pd.Series:

    values = (
        pd.to_numeric(
            race_data[
                column
            ],
            errors="coerce",
        )
    )

    if (
        values
        .notna()
        .sum()
        < 2
    ):

        return (
            pd.Series(
                0.5,
                index=race_data.index,
            )
        )

    minimum = (
        values.min()
    )

    maximum = (
        values.max()
    )

    if (
        pd.isna(
            minimum
        )
        or
        pd.isna(
            maximum
        )
        or
        minimum
        == maximum
    ):

        return (
            pd.Series(
                0.5,
                index=race_data.index,
            )
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

    return (
        result
        .fillna(
            0.5
        )
    )


def weight_search(
    dataframe: pd.DataFrame,
) -> Dict[
    str,
    Any,
]:

    if (
        "total_score"
        not in dataframe.columns
    ):

        return {
            "available":
                False,
        }

    time_available = (
        "exhibition_time"
        in dataframe.columns
        and
        dataframe[
            "exhibition_time"
        ]
        .notna()
        .sum()
        > 0
    )

    st_available = (
        "exhibition_st"
        in dataframe.columns
        and
        dataframe[
            "exhibition_st"
        ]
        .notna()
        .sum()
        > 0
    )

    f_available = (
        "exhibition_f"
        in dataframe.columns
        and
        dataframe[
            "exhibition_f"
        ]
        .fillna(0)
        .astype(float)
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
            "available":
                False,

            "available_factors":
                [],

            "reason":
                (
                    "展示タイム・ST・Fの"
                    "有効データなし"
                ),
        }

    required = [
        "total_score",
        "finish",
    ]

    if time_available:

        required.append(
            "exhibition_time"
        )

    if st_available:

        required.append(
            "exhibition_st"
        )

    work = (
        dataframe
        .dropna(
            subset=required
        )
        .copy()
    )

    if work.empty:

        return {
            "available":
                False,

            "available_factors":
                available_factors,
        }

    work[
        "time_norm"
    ] = 0.5

    work[
        "st_norm"
    ] = 0.5

    for (
        _,
        indexes,
    ) in work.groupby(
        [
            "venue_code",
            "race",
        ]
    ).groups.items():

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
            )

    if (
        "exhibition_f"
        not in work.columns
    ):

        work[
            "exhibition_f"
        ] = 0

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

    valid_races = []

    for (
        race_key,
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
            >= 4
        ):

            valid_races.append(
                race_key
            )

    valid_set = set(
        valid_races
    )

    work = (
        work[
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

        test = (
            work.copy()
        )

        score = (
            test[
                "total_score"
            ]
            .astype(float)
        )

        if time_available:

            score = (
                score
                +
                time_weight
                *
                test[
                    "time_norm"
                ]
            )

        if st_available:

            score = (
                score
                +
                st_weight
                *
                test[
                    "st_norm"
                ]
            )

        if f_available:

            score = (
                score
                -
                f_penalty
                *
                test[
                    "exhibition_f"
                ]
            )

        test[
            "adjusted_score"
        ] = score

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
                float(
                    top[
                        "finish"
                    ]
                )
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

    baseline = (
        accuracy(
            0,
            0,
            0,
        )
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
        else (
            0,
        )
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
        else (
            0,
        )
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
        else (
            0,
        )
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
                    and
                    st_weight
                    == 0
                    and
                    f_penalty
                    == 0
                ):

                    continue

                current = (
                    accuracy(
                        time_weight,
                        st_weight,
                        f_penalty,
                    )
                )

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
                                current,
                                1,
                            ),

                        "improvement_vs_baseline_pt":
                            round(
                                current
                                - baseline,
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
                    +
                    item[
                        "exhibition_st_weight"
                    ]
                    +
                    item[
                        "f_penalty"
                    ]
                ),
            ),
        reverse=True,
    )

    return {
        "available":
            True,

        "available_factors":
            available_factors,

        "races":
            len(
                valid_races
            ),

        "baseline_top1_accuracy_pct":
            round(
                baseline,
                1,
            ),

        "best_candidates":
            candidates[
                :10
            ],
    }


# =========================================================
# メイン
# =========================================================


def main() -> int:

    parser = (
        argparse.ArgumentParser()
    )

    parser.add_argument(
        "--date",
        required=True,
    )

    args = (
        parser.parse_args()
    )

    date = (
        normalize_date(
            args.date
        )
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

    live = (
        load_live_features(
            date
        )
    )

    if live.empty:

        raise SystemExit(
            "直前情報データを"
            "1件も検出できませんでした"
        )

    results = (
        load_results(
            date
        )
    )

    scores = (
        load_morning_scores(
            date
        )
    )

    keys = [
        "date",
        "venue_code",
        "race",
        "boat",
    ]

    # 全結合キーを念のため再統一
    live = (
        normalize_merge_keys(
            live
        )
    )

    results = (
        normalize_merge_keys(
            results
        )
    )

    scores = (
        normalize_merge_keys(
            scores
        )
    )

    print("")
    print(
        "results:",
        len(
            results
        )
    )

    print(
        "live:",
        len(
            live
        )
    )

    print(
        "morning scores:",
        len(
            scores
        )
    )

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

    dataframe = (
        build_course_changed(
            dataframe
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
        "date":
            date,

        "coverage":
            coverage,

        "detected_live_columns":
            list(
                live.columns
            ),

        "diagnostics":
            {
                "seen_live_keys":
                    sorted(
                        SEEN_LIVE_KEYS
                    )[:500],
            },

        "factors":
            {
                "exhibition_time":
                    rank_metric(
                        dataframe,
                        "exhibition_time",
                        True,
                    ),

                "exhibition_st":
                    rank_metric(
                        dataframe,
                        "exhibition_st",
                        True,
                    ),

                "exhibition_f":
                    binary_metric(
                        dataframe,
                        "exhibition_f",
                    ),

                "course_changed":
                    binary_metric(
                        dataframe,
                        "course_changed",
                    ),
            },

        "wind_context":
            wind_analysis(
                dataframe
            ),

        "weight_search":
            weight_search(
                dataframe
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
        "# 直前情報5項目 個別答え合わせ",
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

    for (
        key,
        value,
    ) in coverage.items():

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
        "## 展示タイム・ST・F 重み探索",
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