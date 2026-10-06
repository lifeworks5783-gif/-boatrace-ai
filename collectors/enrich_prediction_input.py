from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


JST = timezone(
    timedelta(
        hours=9
    )
)

TREND_PREFIX = "trend_"


def parse_args():
    parser = argparse.ArgumentParser(
        description="当日予測入力へ30日・90日履歴特徴量を結合"
    )

    parser.add_argument(
        "--date",
        required=True,
        help="対象日 YYYYMMDD",
    )

    parser.add_argument(
        "--stage",
        default="morning",
        choices=[
            "morning",
            "live",
        ],
        help="予測段階",
    )

    parser.add_argument(
        "--data-dir",
        default="data",
    )

    parser.add_argument(
        "--features-dir",
        default="features",
    )

    return parser.parse_args()


def text(value):
    if value is None:
        return ""

    return str(
        value
    ).strip()


def int_key(value):
    value = text(
        value
    )

    if not value:
        return ""

    try:
        return str(
            int(
                float(
                    value
                )
            )
        )

    except ValueError:
        return value


def venue_key(value):
    value = int_key(
        value
    )

    if not value:
        return ""

    return value.zfill(
        2
    )


def smart_value(value):
    value = text(
        value
    )

    if value == "":
        return None

    try:
        if any(
            char in value
            for char in (
                ".",
                "e",
                "E",
            )
        ):
            return float(
                value
            )

        return int(
            value
        )

    except ValueError:
        return value


def load_csv(path):
    path = Path(
        path
    )

    if not path.exists():
        raise RuntimeError(
            f"特徴量ファイルがありません: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        return list(
            csv.DictReader(
                f
            )
        )


def make_index(
    rows,
    key_func,
    label,
):
    index = {}

    duplicates = []

    for row in rows:
        key = key_func(
            row
        )

        if (
            not key
            or any(
                part == ""
                for part in key
            )
        ):
            continue

        if key in index:
            duplicates.append(
                key
            )

            continue

        index[
            key
        ] = row

    if duplicates:
        raise RuntimeError(
            f"{label}特徴量にキー重複があります: "
            f"{len(duplicates)}件 "
            f"{duplicates[:5]}"
        )

    return index


def group_by_prefix(
    row,
    prefix,
):
    if row is None:
        return None

    result = {}

    for key, value in row.items():
        if key.startswith(
            prefix
        ):
            result[
                key[
                    len(
                        prefix
                    ):
                ]
            ] = smart_value(
                value
            )

    return result


def trend_group(row):
    if row is None:
        return None

    result = {}

    for key, value in row.items():
        if key.startswith(
            TREND_PREFIX
        ):
            result[
                key[
                    len(
                        TREND_PREFIX
                    ):
                ]
            ] = smart_value(
                value
            )

    return result


def overall_racer_payload(
    row,
):
    if row is None:
        return None

    return {
        "registration_no": int_key(
            row.get(
                "registration_no"
            )
        ),

        "racer_name": text(
            row.get(
                "racer_name"
            )
        ),

        "history_first_date": text(
            row.get(
                "history_first_date"
            )
        ),

        "history_last_date": text(
            row.get(
                "history_last_date"
            )
        ),

        "history_starts": smart_value(
            row.get(
                "history_starts"
            )
        ),

        "last5": group_by_prefix(
            row,
            "last5_",
        ),

        "last10": group_by_prefix(
            row,
            "last10_",
        ),

        "d30": group_by_prefix(
            row,
            "d30_",
        ),

        "d90": group_by_prefix(
            row,
            "d90_",
        ),

        "trend_30v90": trend_group(
            row
        ),
    }


def scoped_payload(
    row,
):
    if row is None:
        return None

    return {
        "d30": group_by_prefix(
            row,
            "d30_",
        ),

        "d90": group_by_prefix(
            row,
            "d90_",
        ),

        "trend_30v90": trend_group(
            row
        ),
    }


def has_starts(
    payload,
    window,
):
    if not payload:
        return False

    section = payload.get(
        window
    )

    if not section:
        return False

    starts = section.get(
        "starts"
    )

    return (
        isinstance(
            starts,
            (
                int,
                float,
            ),
        )
        and starts > 0
    )


def load_feature_manifest(
    features_dir,
    target_date,
):
    path = (
        Path(
            features_dir
        )
        / "history_features_manifest.json"
    )

    if not path.exists():
        raise RuntimeError(
            f"特徴量manifestがありません: {path}"
        )

    data = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if text(
        data.get(
            "as_of_date"
        )
    ) != target_date:
        raise RuntimeError(
            "特徴量の基準日が当日データと一致しません: "
            f"features={data.get('as_of_date')} "
            f"target={target_date}"
        )

    history_max_date = text(
        data.get(
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
            f"history_max_date={history_max_date} "
            f"target_date={target_date}"
        )

    return data


def load_feature_indexes(
    features_dir,
):
    features_dir = Path(
        features_dir
    )

    racer_rows = load_csv(
        features_dir
        / "racer_features.csv"
    )

    racer_course_rows = load_csv(
        features_dir
        / "racer_course_features.csv"
    )

    racer_venue_rows = load_csv(
        features_dir
        / "racer_venue_features.csv"
    )

    motor_rows = load_csv(
        features_dir
        / "motor_features.csv"
    )

    boat_rows = load_csv(
        features_dir
        / "boat_features.csv"
    )

    racer_index = make_index(
        racer_rows,
        lambda row: (
            int_key(
                row.get(
                    "registration_no"
                )
            ),
        ),
        "選手",
    )

    racer_course_index = make_index(
        racer_course_rows,
        lambda row: (
            int_key(
                row.get(
                    "registration_no"
                )
            ),

            int_key(
                row.get(
                    "course"
                )
            ),
        ),
        "選手×コース",
    )

    racer_venue_index = make_index(
        racer_venue_rows,
        lambda row: (
            int_key(
                row.get(
                    "registration_no"
                )
            ),

            venue_key(
                row.get(
                    "venue_code"
                )
            ),
        ),
        "選手×場",
    )

    motor_index = make_index(
        motor_rows,
        lambda row: (
            venue_key(
                row.get(
                    "venue_code"
                )
            ),

            int_key(
                row.get(
                    "motor_no"
                )
            ),
        ),
        "モーター",
    )

    boat_index = make_index(
        boat_rows,
        lambda row: (
            venue_key(
                row.get(
                    "venue_code"
                )
            ),

            int_key(
                row.get(
                    "boat_no"
                )
            ),
        ),
        "ボート",
    )

    return {
        "racer": racer_index,

        "racer_course": (
            racer_course_index
        ),

        "racer_venue": (
            racer_venue_index
        ),

        "motor": motor_index,

        "boat": boat_index,
    }


def current_course(
    boat,
):
    beforeinfo = (
        boat.get(
            "beforeinfo"
        )
        or {}
    )

    course = beforeinfo.get(
        "exhibition_course"
    )

    course_key = int_key(
        course
    )

    if course_key in {
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
    }:
        return course_key

    return ""


def enrich_boat(
    boat,
    venue_code,
    indexes,
):
    racer = (
        boat.get(
            "racer"
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

    registration_no = int_key(
        racer.get(
            "registration_no"
        )
    )

    motor_no = int_key(
        motor.get(
            "motor_no"
        )
    )

    boat_no = int_key(
        boat_machine.get(
            "boat_no"
        )
    )

    course = current_course(
        boat
    )

    racer_row = (
        indexes[
            "racer"
        ].get(
            (
                registration_no,
            )
        )
    )

    racer_venue_row = (
        indexes[
            "racer_venue"
        ].get(
            (
                registration_no,
                venue_code,
            )
        )
    )

    racer_course_row = None

    if course:
        racer_course_row = (
            indexes[
                "racer_course"
            ].get(
                (
                    registration_no,
                    course,
                )
            )
        )

    motor_row = (
        indexes[
            "motor"
        ].get(
            (
                venue_code,
                motor_no,
            )
        )
    )

    boat_row = (
        indexes[
            "boat"
        ].get(
            (
                venue_code,
                boat_no,
            )
        )
    )

    racer_payload = (
        overall_racer_payload(
            racer_row
        )
    )

    racer_venue_payload = (
        scoped_payload(
            racer_venue_row
        )
    )

    racer_course_payload = (
        scoped_payload(
            racer_course_row
        )
    )

    motor_payload = (
        scoped_payload(
            motor_row
        )
    )

    boat_payload = (
        scoped_payload(
            boat_row
        )
    )

    if not course:
        course_reason = (
            "current_course_not_known_yet"
        )

    elif racer_course_row is None:
        course_reason = (
            "no_matching_history"
        )

    else:
        course_reason = ""

    history = {
        "racer_30d_available": (
            has_starts(
                racer_payload,
                "d30",
            )
        ),

        "racer_90d_available": (
            has_starts(
                racer_payload,
                "d90",
            )
        ),

        "motor_30d_available": (
            has_starts(
                motor_payload,
                "d30",
            )
        ),

        "motor_90d_available": (
            has_starts(
                motor_payload,
                "d90",
            )
        ),

        "racer_30d": (
            racer_payload.get(
                "d30"
            )
            if racer_payload
            else None
        ),

        "racer_90d": (
            racer_payload.get(
                "d90"
            )
            if racer_payload
            else None
        ),

        "motor_30d": (
            motor_payload.get(
                "d30"
            )
            if motor_payload
            else None
        ),

        "motor_90d": (
            motor_payload.get(
                "d90"
            )
            if motor_payload
            else None
        ),

        "boat_30d_available": (
            has_starts(
                boat_payload,
                "d30",
            )
        ),

        "boat_90d_available": (
            has_starts(
                boat_payload,
                "d90",
            )
        ),

        "boat_30d": (
            boat_payload.get(
                "d30"
            )
            if boat_payload
            else None
        ),

        "boat_90d": (
            boat_payload.get(
                "d90"
            )
            if boat_payload
            else None
        ),

        "racer_overall": {
            "available": (
                racer_payload
                is not None
            ),

            "features": (
                racer_payload
            ),
        },

        "racer_venue": {
            "available": (
                racer_venue_payload
                is not None
            ),

            "venue_code": (
                venue_code
            ),

            "features": (
                racer_venue_payload
            ),
        },

        "racer_course": {
            "available": (
                racer_course_payload
                is not None
            ),

            "current_course": (
                int(
                    course
                )
                if course
                else None
            ),

            "reason_if_unavailable": (
                course_reason
            ),

            "features": (
                racer_course_payload
            ),
        },

        "motor": {
            "available": (
                motor_payload
                is not None
            ),

            "venue_code": (
                venue_code
            ),

            "motor_no": (
                int(
                    motor_no
                )
                if motor_no
                else None
            ),

            "features": (
                motor_payload
            ),
        },

        "boat_machine": {
            "available": (
                boat_payload
                is not None
            ),

            "venue_code": (
                venue_code
            ),

            "boat_no": (
                int(
                    boat_no
                )
                if boat_no
                else None
            ),

            "features": (
                boat_payload
            ),
        },
    }

    boat[
        "history"
    ] = history

    return {
        "racer_30d": (
            history[
                "racer_30d_available"
            ]
        ),

        "racer_90d": (
            history[
                "racer_90d_available"
            ]
        ),

        "racer_venue": (
            history[
                "racer_venue"
            ][
                "available"
            ]
        ),

        "racer_course": (
            history[
                "racer_course"
            ][
                "available"
            ]
        ),

        "motor_30d": (
            history[
                "motor_30d_available"
            ]
        ),

        "motor_90d": (
            history[
                "motor_90d_available"
            ]
        ),

        "boat_30d": (
            history[
                "boat_30d_available"
            ]
        ),

        "boat_90d": (
            history[
                "boat_90d_available"
            ]
        ),
    }


def main():
    args = parse_args()

    target_date = args.date

    stage = args.stage

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

    data_dir = Path(
        args.data_dir
    )

    features_dir = Path(
        args.features_dir
    )

    input_path = (
        data_dir
        / (
            f"prediction_input_"
            f"{stage}_"
            f"{target_date}.json"
        )
    )

    output_path = (
        data_dir
        / (
            f"prediction_input_enriched_"
            f"{stage}_"
            f"{target_date}.json"
        )
    )

    validation_path = (
        data_dir
        / (
            f"prediction_input_enriched_validation_"
            f"{stage}_"
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
        feature_manifest = (
            load_feature_manifest(
                features_dir,
                target_date,
            )
        )

        indexes = (
            load_feature_indexes(
                features_dir
            )
        )

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
                "prediction_inputのtarget_dateが"
                "指定日と一致しません"
            )

        races = payload.get(
            "races"
        )

        if not isinstance(
            races,
            list,
        ):
            raise RuntimeError(
                "prediction_inputのracesが不正です"
            )

        coverage = {
            "boats": 0,

            "racer_30d": 0,

            "racer_90d": 0,

            "racer_venue": 0,

            "racer_course": 0,

            "motor_30d": 0,

            "motor_90d": 0,

            "boat_30d": 0,

            "boat_90d": 0,
        }

        course_known_boats = 0

        for race in races:
            venue_code = venue_key(
                race.get(
                    "venue_code"
                )
            )

            race_counts = {
                "racer_30d": 0,

                "racer_90d": 0,

                "racer_venue": 0,

                "racer_course": 0,

                "motor_30d": 0,

                "motor_90d": 0,

                "boat_30d": 0,

                "boat_90d": 0,
            }

            boats = race.get(
                "boats"
            )

            if not isinstance(
                boats,
                list,
            ):
                raise RuntimeError(
                    "boatsが不正です: "
                    f"{race.get('race_id')}"
                )

            for boat in boats:
                coverage[
                    "boats"
                ] += 1

                if current_course(
                    boat
                ):
                    course_known_boats += 1

                flags = enrich_boat(
                    boat,
                    venue_code,
                    indexes,
                )

                for key, available in (
                    flags.items()
                ):
                    if available:
                        coverage[
                            key
                        ] += 1

                        race_counts[
                            key
                        ] += 1

            race[
                "history_status"
            ] = {
                key: (
                    f"{value}/"
                    f"{len(boats)}"
                )
                for key, value
                in race_counts.items()
            }

        payload[
            "schema_version"
        ] = "1.4"

        payload[
            "history_note"
        ] = (
            "選手・モーター・ボートの30日/90日履歴特徴量を接続済み。"
            "予測基準日当日以降の結果は不使用。"
            "朝は枠番を想定コースとして本番計算側で選手×コースを参照し、"
            "直前はexhibition_courseで上書きする。"
            "beforeinfoの展示ST/展示タイム/部品交換とrace.weatherの環境情報も保持する。"
        )

        payload[
            "history_feature_manifest"
        ] = {
            "as_of_date": (
                feature_manifest.get(
                    "as_of_date"
                )
            ),

            "history_min_date": (
                feature_manifest.get(
                    "history_min_date"
                )
            ),

            "history_max_date": (
                feature_manifest.get(
                    "history_max_date"
                )
            ),

            "history_stale_days": (
                feature_manifest.get(
                    "history_stale_days"
                )
            ),

            "leakage_guard": (
                feature_manifest.get(
                    "leakage_guard"
                )
            ),
        }

        payload[
            "generated_at_enriched"
        ] = datetime.now(
            JST
        ).isoformat()

        warnings = []

        errors = []

        total_boats = coverage[
            "boats"
        ]

        if total_boats == 0:
            errors.append(
                "艇データが0件です"
            )

        for key in (
            "racer_30d",
            "racer_90d",
            "motor_30d",
            "motor_90d",
        ):
            if coverage[
                key
            ] == 0:
                errors.append(
                    f"{key}の接続件数が0です"
                )

        if total_boats:
            for key in (
                "racer_30d",
                "racer_90d",
                "racer_venue",
                "motor_30d",
                "motor_90d",
                "boat_30d",
                "boat_90d",
            ):
                missing = (
                    total_boats
                    - coverage[
                        key
                    ]
                )

                if missing > 0:
                    warnings.append(
                        f"{key}未接続: "
                        f"{missing}/"
                        f"{total_boats}艇"
                    )

        if (
            stage == "morning"
            and course_known_boats == 0
        ):
            warnings.append(
                "朝予測では現在コース未確定のため"
                "選手×コース特徴量は未使用"
            )

        validation = {
            "status": (
                "PASS"
                if not errors
                else "FAIL"
            ),

            "target_date": (
                target_date
            ),

            "prediction_stage": (
                stage
            ),

            "race_count": (
                len(
                    races
                )
            ),

            "boat_count": (
                total_boats
            ),

            "course_known_boats": (
                course_known_boats
            ),

            "coverage": (
                coverage
            ),

            "history_as_of_date": (
                feature_manifest.get(
                    "as_of_date"
                )
            ),

            "history_max_date": (
                feature_manifest.get(
                    "history_max_date"
                )
            ),

            "history_stale_days": (
                feature_manifest.get(
                    "history_stale_days"
                )
            ),

            "errors": (
                errors
            ),

            "warnings": (
                warnings
            ),

            "generated_at": (
                datetime.now(
                    JST
                ).isoformat()
            ),
        }

        output_path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        validation_path.write_text(
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
            "当日予測入力 × 履歴特徴量 結合"
        )

        print(
            "========================================"
        )

        print(
            "対象日:",
            target_date,
        )

        print(
            "予測段階:",
            stage,
        )

        print(
            "レース数:",
            len(
                races
            ),
        )

        print(
            "艇数:",
            total_boats,
        )

        print(
            "選手30日接続:",
            f"{coverage['racer_30d']}/"
            f"{total_boats}",
        )

        print(
            "選手90日接続:",
            f"{coverage['racer_90d']}/"
            f"{total_boats}",
        )

        print(
            "選手×場接続:",
            f"{coverage['racer_venue']}/"
            f"{total_boats}",
        )

        print(
            "現在コース判明:",
            f"{course_known_boats}/"
            f"{total_boats}",
        )

        print(
            "選手×コース接続:",
            f"{coverage['racer_course']}/"
            f"{total_boats}",
        )

        print(
            "モーター30日接続:",
            f"{coverage['motor_30d']}/"
            f"{total_boats}",
        )

        print(
            "モーター90日接続:",
            f"{coverage['motor_90d']}/"
            f"{total_boats}",
        )

        print(
            "ボート30日接続:",
            f"{coverage['boat_30d']}/"
            f"{total_boats}",
        )

        print(
            "ボート90日接続:",
            f"{coverage['boat_90d']}/"
            f"{total_boats}",
        )

        print(
            "履歴最終日:",
            feature_manifest.get(
                "history_max_date"
            ),
        )

        print(
            "履歴鮮度遅延:",
            feature_manifest.get(
                "history_stale_days"
            ),
        )

        print(
            "結果漏洩防止: PASS"
        )

        print(
            "出力:",
            output_path,
        )

        print(
            "検証:",
            validation_path,
        )

        print(
            "========================================"
        )

        if errors:
            print(
                "結合結果: FAIL"
            )

            for error in errors:
                print(
                    "ERROR:",
                    error,
                )

            return 1

        print(
            "結合結果: PASS"
        )

        if warnings:
            print("")

            print(
                "警告:"
            )

            for warning in warnings:
                print(
                    "-",
                    warning,
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