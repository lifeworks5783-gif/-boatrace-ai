from __future__ import annotations

import argparse
import csv
import json
import sys

from collections import defaultdict
from build_venue_course_features import build_venue_course_features
from datetime import datetime, timedelta, timezone
from pathlib import Path


JST = timezone(
    timedelta(
        hours=9
    )
)

ARCHIVE_DIR = Path(
    "archive"
)

FEATURE_DIR = Path(
    "features"
)


CORE_REQUIRED = {
    "date",
    "venue_code",
    "venue_name",
    "race",
    "race_id",
    "boat",
    "course",
    "registration_no",
    "racer_name",
    "finish",
    "st",
}


STAT_FIELDS = [
    "starts",
    "finish_samples",
    "avg_finish",
    "win_rate",
    "top2_rate",
    "top3_rate",
    "st_samples",
    "avg_st",
    "f_count",
    "f_rate",
    "l_count",
    "l_rate",
    "exhibition_samples",
    "avg_exhibition",
]


def parse_args():

    parser = argparse.ArgumentParser(
        description=(
            "BOAT RACE履歴から"
            "予測用30日・90日特徴量を生成"
        )
    )

    parser.add_argument(
        "--as-of",
        dest="as_of",
        default=None,
        help=(
            "予測基準日 YYYYMMDD。"
            "この日以降の結果は使用しない。"
            "省略時は日本時間の当日"
        ),
    )

    parser.add_argument(
        "--archive-dir",
        default=str(
            ARCHIVE_DIR
        ),
    )

    parser.add_argument(
        "--output-dir",
        default=str(
            FEATURE_DIR
        ),
    )

    return parser.parse_args()


def parse_date(
    value,
):

    value = str(
        value
    ).strip()

    for fmt in (
        "%Y%m%d",
        "%Y-%m-%d",
    ):

        try:

            return datetime.strptime(
                value,
                fmt,
            ).date()

        except ValueError:

            pass

    return None


def text(
    value,
):

    if value is None:

        return ""

    return str(
        value
    ).strip()


def to_int(
    value,
):

    value = text(
        value
    )

    if not value:

        return None

    try:

        return int(
            float(
                value
            )
        )

    except ValueError:

        return None


def to_float(
    value,
):

    value = text(
        value
    )

    if not value:

        return None

    try:

        return float(
            value
        )

    except ValueError:

        return None


def parse_finish(
    value,
):

    value = text(
        value
    ).upper()

    if value.isdigit():

        number = int(
            value
        )

        if (
            1
            <= number
            <= 6
        ):

            return number

    return None


def parse_st(
    value,
):

    value = (
        text(
            value
        )
        .upper()
        .replace(
            " ",
            "",
        )
    )

    if not value:

        return (
            None,
            False,
            False,
        )

    if value.startswith(
        "F"
    ):

        return (
            None,
            True,
            False,
        )

    if value.startswith(
        "L"
    ):

        return (
            None,
            False,
            True,
        )

    if value.startswith(
        "."
    ):

        value = (
            "0"
            + value
        )

    try:

        number = float(
            value
        )

    except ValueError:

        return (
            None,
            False,
            False,
        )

    if (
        -0.30
        <= number
        <= 1.00
    ):

        return (
            number,
            False,
            False,
        )

    return (
        None,
        False,
        False,
    )


def parse_exhibition(
    value,
):

    number = to_float(
        value
    )

    if number is None:

        return None

    if (
        5.0
        <= number
        <= 10.0
    ):

        return number

    return None


def mean_or_none(
    values,
):

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
    denominator,
):

    if denominator <= 0:

        return None

    return (
        count
        / denominator
    )


def rounded(
    value,
    digits=5,
):

    if value is None:

        return ""

    return round(
        value,
        digits,
    )


def load_history(
    archive_dir,
    as_of_date,
):

    files = sorted(
        Path(
            archive_dir
        ).glob(
            "*/*/*/boat_results_*_all.csv"
        )
    )

    if not files:

        raise RuntimeError(
            "archiveに艇別履歴がありません"
        )

    history = []

    seen = set()

    duplicate_keys = []

    used_files = []

    excluded_future_rows = 0


    for path in files:

        file_used = False

        with path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as f:

            reader = csv.DictReader(
                f
            )

            fields = set(
                reader.fieldnames
                or []
            )

            missing = (
                CORE_REQUIRED
                - fields
            )

            if missing:

                raise RuntimeError(
                    "必須列不足: "
                    f"{path} "
                    f"{sorted(missing)}"
                )


            for raw in reader:

                race_date = parse_date(
                    raw.get(
                        "date"
                    )
                )

                if race_date is None:

                    raise RuntimeError(
                        "日付異常: "
                        f"{path} "
                        f"{raw.get('date')}"
                    )


                # -------------------------------------------------
                # 最重要：結果漏洩防止
                #
                # 予測基準日 as_of 当日と、
                # それより未来の結果は絶対に使用しない。
                # -------------------------------------------------

                if (
                    race_date
                    >= as_of_date
                ):

                    excluded_future_rows += 1

                    continue


                race_id = text(
                    raw.get(
                        "race_id"
                    )
                )

                lane = to_int(
                    raw.get(
                        "boat"
                    )
                )

                key = (
                    race_id,
                    lane,
                )

                if key in seen:

                    duplicate_keys.append(
                        key
                    )

                    continue

                seen.add(
                    key
                )


                registration_no = text(
                    raw.get(
                        "registration_no"
                    )
                )

                if not registration_no:

                    continue


                (
                    st_value,
                    is_f,
                    is_l,
                ) = parse_st(
                    raw.get(
                        "st"
                    )
                )


                row = {
                    "date": race_date,

                    "date_text": (
                        race_date.strftime(
                            "%Y%m%d"
                        )
                    ),

                    "venue_code": (
                        text(
                            raw.get(
                                "venue_code"
                            )
                        ).zfill(
                            2
                        )
                    ),

                    "venue_name": text(
                        raw.get(
                            "venue_name"
                        )
                    ),

                    "race": to_int(
                        raw.get(
                            "race"
                        )
                    ),

                    "race_id": race_id,

                    "lane": lane,

                    "course": to_int(
                        raw.get(
                            "course"
                        )
                    ),

                    "registration_no": (
                        registration_no
                    ),

                    "racer_name": text(
                        raw.get(
                            "racer_name"
                        )
                    ),

                    "motor_no": to_int(
                        raw.get(
                            "motor_no"
                        )
                    ),

                    "boat_no": to_int(
                        raw.get(
                            "boat_no"
                        )
                    ),

                    "exhibition_time": (
                        parse_exhibition(
                            raw.get(
                                "exhibition_time"
                            )
                        )
                    ),

                    "finish": parse_finish(
                        raw.get(
                            "finish"
                        )
                    ),

                    "st_value": (
                        st_value
                    ),

                    "is_f": (
                        is_f
                    ),

                    "is_l": (
                        is_l
                    ),
                }


                history.append(
                    row
                )

                file_used = True


        if file_used:

            used_files.append(
                str(
                    path
                )
            )


    if duplicate_keys:

        raise RuntimeError(
            "履歴にrace_id×艇番重複があります: "
            f"{len(duplicate_keys)}件 "
            f"{duplicate_keys[:5]}"
        )


    if not history:

        raise RuntimeError(
            "予測基準日より前の履歴がありません"
        )


    history.sort(
        key=lambda row: (
            row[
                "date"
            ],

            row[
                "venue_code"
            ],

            row[
                "race"
            ]
            or 0,

            row[
                "lane"
            ]
            or 0,
        )
    )


    return (
        history,
        used_files,
        excluded_future_rows,
    )


def summarize(
    rows,
):

    starts = len(
        rows
    )


    finishes = [
        row[
            "finish"
        ]
        for row
        in rows
        if row[
            "finish"
        ]
        is not None
    ]


    st_values = [
        row[
            "st_value"
        ]
        for row
        in rows
        if row[
            "st_value"
        ]
        is not None
    ]


    exhibitions = [
        row[
            "exhibition_time"
        ]
        for row
        in rows
        if row[
            "exhibition_time"
        ]
        is not None
    ]


    win_count = sum(
        (
            row[
                "finish"
            ]
            == 1
        )
        for row
        in rows
    )


    top2_count = sum(
        (
            row[
                "finish"
            ]
            is not None
            and row[
                "finish"
            ]
            <= 2
        )
        for row
        in rows
    )


    top3_count = sum(
        (
            row[
                "finish"
            ]
            is not None
            and row[
                "finish"
            ]
            <= 3
        )
        for row
        in rows
    )


    f_count = sum(
        row[
            "is_f"
        ]
        for row
        in rows
    )


    l_count = sum(
        row[
            "is_l"
        ]
        for row
        in rows
    )


    return {
        "starts": (
            starts
        ),

        "finish_samples": (
            len(
                finishes
            )
        ),

        "avg_finish": rounded(
            mean_or_none(
                finishes
            )
        ),

        "win_rate": rounded(
            rate(
                win_count,
                starts,
            )
        ),

        "top2_rate": rounded(
            rate(
                top2_count,
                starts,
            )
        ),

        "top3_rate": rounded(
            rate(
                top3_count,
                starts,
            )
        ),

        "st_samples": (
            len(
                st_values
            )
        ),

        "avg_st": rounded(
            mean_or_none(
                st_values
            )
        ),

        "f_count": (
            f_count
        ),

        "f_rate": rounded(
            rate(
                f_count,
                starts,
            )
        ),

        "l_count": (
            l_count
        ),

        "l_rate": rounded(
            rate(
                l_count,
                starts,
            )
        ),

        "exhibition_samples": (
            len(
                exhibitions
            )
        ),

        "avg_exhibition": rounded(
            mean_or_none(
                exhibitions
            )
        ),
    }


def prefixed(
    prefix,
    summary,
):

    return {
        (
            f"{prefix}_{key}"
        ): summary[
            key
        ]
        for key
        in STAT_FIELDS
    }


def rows_in_days(
    rows,
    as_of_date,
    days,
):

    start_date = (
        as_of_date
        - timedelta(
            days=days
        )
    )

    return [
        row
        for row
        in rows
        if (
            start_date
            <= row[
                "date"
            ]
            < as_of_date
        )
    ]


def trend_value(
    short_summary,
    long_summary,
    key,
):

    short = short_summary.get(
        key,
        ""
    )

    long = long_summary.get(
        key,
        ""
    )

    if (
        short == ""
        or long == ""
    ):

        return ""

    return round(
        float(
            short
        )
        - float(
            long
        ),
        5,
    )


def trend_fields(
    d30,
    d90,
):

    return {
        "trend_win_rate_30v90": (
            trend_value(
                d30,
                d90,
                "win_rate",
            )
        ),

        "trend_top2_rate_30v90": (
            trend_value(
                d30,
                d90,
                "top2_rate",
            )
        ),

        "trend_top3_rate_30v90": (
            trend_value(
                d30,
                d90,
                "top3_rate",
            )
        ),

        "trend_avg_finish_30v90": (
            trend_value(
                d30,
                d90,
                "avg_finish",
            )
        ),

        "trend_avg_st_30v90": (
            trend_value(
                d30,
                d90,
                "avg_st",
            )
        ),

        "trend_avg_exhibition_30v90": (
            trend_value(
                d30,
                d90,
                "avg_exhibition",
            )
        ),
    }


def latest_racer_name(
    rows,
):

    for row in reversed(
        rows
    ):

        if row[
            "racer_name"
        ]:

            return row[
                "racer_name"
            ]

    return ""


def latest_venue_name(
    rows,
):

    for row in reversed(
        rows
    ):

        if row[
            "venue_name"
        ]:

            return row[
                "venue_name"
            ]

    return ""


def build_racer_features(
    history,
    as_of_date,
):

    groups = defaultdict(
        list
    )


    for row in history:

        groups[
            row[
                "registration_no"
            ]
        ].append(
            row
        )


    output = []


    for registration_no in sorted(
        groups
    ):

        rows = groups[
            registration_no
        ]


        last5_rows = (
            rows[
                -5:
            ]
        )


        last10_rows = (
            rows[
                -10:
            ]
        )


        rows30 = rows_in_days(
            rows,
            as_of_date,
            30,
        )


        rows90 = rows_in_days(
            rows,
            as_of_date,
            90,
        )


        last5 = summarize(
            last5_rows
        )


        last10 = summarize(
            last10_rows
        )


        d30 = summarize(
            rows30
        )


        d90 = summarize(
            rows90
        )


        output.append(
            {
                "as_of_date": (
                    as_of_date.strftime(
                        "%Y%m%d"
                    )
                ),

                "registration_no": (
                    registration_no
                ),

                "racer_name": (
                    latest_racer_name(
                        rows
                    )
                ),

                "history_first_date": (
                    rows[
                        0
                    ][
                        "date_text"
                    ]
                ),

                "history_last_date": (
                    rows[
                        -1
                    ][
                        "date_text"
                    ]
                ),

                "history_starts": (
                    len(
                        rows
                    )
                ),

                **prefixed(
                    "last5",
                    last5,
                ),

                **prefixed(
                    "last10",
                    last10,
                ),

                **prefixed(
                    "d30",
                    d30,
                ),

                **prefixed(
                    "d90",
                    d90,
                ),

                **trend_fields(
                    d30,
                    d90,
                ),
            }
        )


    return output


def build_racer_course_features(
    history,
    as_of_date,
):

    groups = defaultdict(
        list
    )


    for row in history:

        course = row[
            "course"
        ]

        if course not in {
            1,
            2,
            3,
            4,
            5,
            6,
        }:

            continue


        groups[
            (
                row[
                    "registration_no"
                ],
                course,
            )
        ].append(
            row
        )


    output = []


    for key in sorted(
        groups
    ):

        (
            registration_no,
            course,
        ) = key


        rows = groups[
            key
        ]


        d30 = summarize(
            rows_in_days(
                rows,
                as_of_date,
                30,
            )
        )


        d90 = summarize(
            rows_in_days(
                rows,
                as_of_date,
                90,
            )
        )


        output.append(
            {
                "as_of_date": (
                    as_of_date.strftime(
                        "%Y%m%d"
                    )
                ),

                "registration_no": (
                    registration_no
                ),

                "racer_name": (
                    latest_racer_name(
                        rows
                    )
                ),

                "course": (
                    course
                ),

                **prefixed(
                    "d30",
                    d30,
                ),

                **prefixed(
                    "d90",
                    d90,
                ),

                **trend_fields(
                    d30,
                    d90,
                ),
            }
        )


    return output


def build_racer_venue_features(
    history,
    as_of_date,
):

    groups = defaultdict(
        list
    )


    for row in history:

        groups[
            (
                row[
                    "registration_no"
                ],
                row[
                    "venue_code"
                ],
            )
        ].append(
            row
        )


    output = []


    for key in sorted(
        groups
    ):

        (
            registration_no,
            venue_code,
        ) = key


        rows = groups[
            key
        ]


        d30 = summarize(
            rows_in_days(
                rows,
                as_of_date,
                30,
            )
        )


        d90 = summarize(
            rows_in_days(
                rows,
                as_of_date,
                90,
            )
        )


        output.append(
            {
                "as_of_date": (
                    as_of_date.strftime(
                        "%Y%m%d"
                    )
                ),

                "registration_no": (
                    registration_no
                ),

                "racer_name": (
                    latest_racer_name(
                        rows
                    )
                ),

                "venue_code": (
                    venue_code
                ),

                "venue_name": (
                    latest_venue_name(
                        rows
                    )
                ),

                **prefixed(
                    "d30",
                    d30,
                ),

                **prefixed(
                    "d90",
                    d90,
                ),

                **trend_fields(
                    d30,
                    d90,
                ),
            }
        )


    return output


def build_equipment_features(
    history,
    as_of_date,
    equipment_field,
):

    groups = defaultdict(
        list
    )


    for row in history:

        equipment_no = row.get(
            equipment_field
        )


        if equipment_no is None:

            continue


        # モーター番号・ボート番号は
        # 場ごとに別物なので、
        # venue_codeとの複合キーで管理する。

        groups[
            (
                row[
                    "venue_code"
                ],
                equipment_no,
            )
        ].append(
            row
        )


    output = []


    for key in sorted(
        groups
    ):

        (
            venue_code,
            equipment_no,
        ) = key


        rows = groups[
            key
        ]


        rows30 = rows_in_days(
            rows,
            as_of_date,
            30,
        )


        rows90 = rows_in_days(
            rows,
            as_of_date,
            90,
        )


        d30 = summarize(
            rows30
        )


        d90 = summarize(
            rows90
        )


        unique_racers_30 = len(
            {
                row[
                    "registration_no"
                ]
                for row
                in rows30
            }
        )


        unique_racers_90 = len(
            {
                row[
                    "registration_no"
                ]
                for row
                in rows90
            }
        )


        output.append(
            {
                "as_of_date": (
                    as_of_date.strftime(
                        "%Y%m%d"
                    )
                ),

                "venue_code": (
                    venue_code
                ),

                "venue_name": (
                    latest_venue_name(
                        rows
                    )
                ),

                equipment_field: (
                    equipment_no
                ),

                "history_first_date": (
                    rows[
                        0
                    ][
                        "date_text"
                    ]
                ),

                "history_last_date": (
                    rows[
                        -1
                    ][
                        "date_text"
                    ]
                ),

                "history_starts": (
                    len(
                        rows
                    )
                ),

                "d30_unique_racers": (
                    unique_racers_30
                ),

                "d90_unique_racers": (
                    unique_racers_90
                ),

                **prefixed(
                    "d30",
                    d30,
                ),

                **prefixed(
                    "d90",
                    d90,
                ),

                **trend_fields(
                    d30,
                    d90,
                ),
            }
        )


    return output


def write_csv(
    path,
    rows,
):

    path = Path(
        path
    )


    if not rows:

        raise RuntimeError(
            f"出力行が0件です: {path}"
        )


    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    fieldnames = list(
        rows[
            0
        ].keys()
    )


    with path.open(
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


    if args.as_of:

        as_of_date = parse_date(
            args.as_of
        )


        if as_of_date is None:

            print(
                "ERROR: "
                "--as-ofはYYYYMMDD形式です",
                file=sys.stderr,
            )

            return 1


    else:

        as_of_date = (
            datetime.now(
                JST
            ).date()
        )


    try:

        (
            history,
            source_files,
            excluded_future_rows,
        ) = load_history(
            args.archive_dir,
            as_of_date,
        )


        racer_features = (
            build_racer_features(
                history,
                as_of_date,
            )
        )


        racer_course_features = (
            build_racer_course_features(
                history,
                as_of_date,
            )
        )


        racer_venue_features = (
            build_racer_venue_features(
                history,
                as_of_date,
            )
        )


        motor_features = (
            build_equipment_features(
                history,
                as_of_date,
                "motor_no",
            )
        )


        boat_features = (
            build_equipment_features(
                history,
                as_of_date,
                "boat_no",
            )
        )


        output_dir = Path(
            args.output_dir
        )


        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )


        write_csv(
            output_dir
            / "racer_features.csv",
            racer_features,
        )


        write_csv(
            output_dir
            / "racer_course_features.csv",
            racer_course_features,
        )


        write_csv(
            output_dir
            / "racer_venue_features.csv",
            racer_venue_features,
        )

        venue_course_features = build_venue_course_features(
            history, as_of_date, summarize, rows_in_days, prefixed, trend_fields, latest_venue_name
        )
        write_csv(
            output_dir / "venue_course_features.csv",
            venue_course_features,
        )


        write_csv(
            output_dir
            / "motor_features.csv",
            motor_features,
        )


        write_csv(
            output_dir
            / "boat_features.csv",
            boat_features,
        )


        minimum_date = min(
            row[
                "date"
            ]
            for row
            in history
        )


        maximum_date = max(
            row[
                "date"
            ]
            for row
            in history
        )


        yesterday = (
            as_of_date
            - timedelta(
                days=1
            )
        )


        stale_days = max(
            (
                yesterday
                - maximum_date
            ).days,
            0,
        )


        manifest = {
            "generated_at": (
                datetime.now(
                    JST
                ).isoformat()
            ),

            "as_of_date": (
                as_of_date.strftime(
                    "%Y%m%d"
                )
            ),

            "leakage_guard": (
                "Only rows with result date "
                "< as_of_date are used."
            ),

            "history_min_date": (
                minimum_date.strftime(
                    "%Y%m%d"
                )
            ),

            "history_max_date": (
                maximum_date.strftime(
                    "%Y%m%d"
                )
            ),

            "history_stale_days": (
                stale_days
            ),

            "source_files_used": (
                len(
                    source_files
                )
            ),

            "history_rows_used": (
                len(
                    history
                )
            ),

            "same_day_or_future_rows_excluded": (
                excluded_future_rows
            ),

            "outputs": {
                "racer_features": (
                    len(
                        racer_features
                    )
                ),

                "racer_course_features": (
                    len(
                        racer_course_features
                    )
                ),

                "racer_venue_features": (
                    len(
                        racer_venue_features
                    )
                ),

                "venue_course_features": (
                    len(
                        venue_course_features
                    )
                ),

                "motor_features": (
                    len(
                        motor_features
                    )
                ),

                "boat_features": (
                    len(
                        boat_features
                    )
                ),
            },

            "definitions": {
                "rates": (
                    "win/top2/top3 rates use "
                    "all starts as denominator"
                ),

                "avg_finish": (
                    "numeric finishes 1-6 only"
                ),

                "avg_st": (
                    "numeric valid ST only; "
                    "F/L are excluded from avg_st "
                    "and stored as f_rate/l_rate"
                ),

                "motor_identity": (
                    "venue_code + motor_no"
                ),

                "boat_identity": (
                    "venue_code + boat_no"
                ),
            },
        }


        manifest_path = (
            output_dir
            / "history_features_manifest.json"
        )


        manifest_path.write_text(
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


        print(
            "========================================"
        )

        print(
            "履歴特徴量生成"
        )

        print(
            "========================================"
        )


        print(
            "予測基準日:",
            manifest[
                "as_of_date"
            ],
        )


        print(
            "使用履歴:",
            manifest[
                "history_min_date"
            ],
            "～",
            manifest[
                "history_max_date"
            ],
        )


        print(
            "履歴艇数:",
            len(
                history
            ),
        )


        print(
            "選手特徴量:",
            len(
                racer_features
            ),
        )


        print(
            "選手×コース特徴量:",
            len(
                racer_course_features
            ),
        )


        print(
            "選手×場特徴量:",
            len(
                racer_venue_features
            ),
        )


        print(
            "モーター特徴量:",
            len(
                motor_features
            ),
        )


        print(
            "ボート特徴量:",
            len(
                boat_features
            ),
        )


        print(
            "履歴鮮度遅延:",
            stale_days,
            "日",
        )


        print(
            "当日・未来結果除外:",
            excluded_future_rows,
            "艇",
        )


        if stale_days > 0:

            print(
                "WARNING: "
                "前日までの結果が"
                "完全には反映されていません"
            )


        print("")

        print(
            "リーク防止: PASS"
        )

        print(
            "履歴特徴量生成: PASS"
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