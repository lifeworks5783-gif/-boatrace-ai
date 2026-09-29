from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


REQUIRED_COLUMNS = {
    "motor_no",
    "boat_no",
    "exhibition_time",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="拡張済みBOAT RACE履歴データを検証"
    )

    parser.add_argument(
        "--start",
        required=True,
        help="開始日 YYYYMMDD",
    )

    parser.add_argument(
        "--end",
        required=True,
        help="終了日 YYYYMMDD",
    )

    return parser.parse_args()


def read_target_files(
    start_date: int,
    end_date: int,
):
    files = []

    for path in Path("archive").glob(
        "*/*/*/boat_results_*_all.csv"
    ):
        match = re.search(
            r"boat_results_(\d{8})_all\.csv$",
            path.name,
        )

        if not match:
            continue

        date_value = int(
            match.group(1)
        )

        if (
            start_date
            <= date_value
            <= end_date
        ):
            files.append(
                path
            )

    return sorted(
        files
    )


def main():
    args = parse_args()

    start_date = int(
        args.start
    )

    end_date = int(
        args.end
    )

    files = read_target_files(
        start_date,
        end_date,
    )

    total_rows = 0

    motor_rows = 0
    boat_rows = 0
    exhibition_rows = 0

    bad_motor = []
    bad_boat = []
    bad_exhibition = []

    missing_columns = []

    for path in files:

        with path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as f:

            reader = csv.DictReader(
                f
            )

            columns = set(
                reader.fieldnames
                or []
            )

            if not REQUIRED_COLUMNS.issubset(
                columns
            ):
                missing_columns.append(
                    str(path)
                )

                continue

            for row in reader:

                total_rows += 1

                race_id = str(
                    row.get(
                        "race_id",
                        "",
                    )
                ).strip()

                lane = str(
                    row.get(
                        "boat",
                        "",
                    )
                ).strip()

                motor = str(
                    row.get(
                        "motor_no",
                        "",
                    )
                ).strip()

                boat_no = str(
                    row.get(
                        "boat_no",
                        "",
                    )
                ).strip()

                exhibition = str(
                    row.get(
                        "exhibition_time",
                        "",
                    )
                ).strip()

                if motor:
                    motor_rows += 1

                    try:
                        value = int(
                            float(
                                motor
                            )
                        )

                        if not (
                            1
                            <= value
                            <= 999
                        ):
                            bad_motor.append(
                                (
                                    race_id,
                                    lane,
                                    motor,
                                )
                            )

                    except ValueError:
                        bad_motor.append(
                            (
                                race_id,
                                lane,
                                motor,
                            )
                        )

                if boat_no:
                    boat_rows += 1

                    try:
                        value = int(
                            float(
                                boat_no
                            )
                        )

                        if not (
                            1
                            <= value
                            <= 999
                        ):
                            bad_boat.append(
                                (
                                    race_id,
                                    lane,
                                    boat_no,
                                )
                            )

                    except ValueError:
                        bad_boat.append(
                            (
                                race_id,
                                lane,
                                boat_no,
                            )
                        )

                if exhibition:
                    exhibition_rows += 1

                    try:
                        value = float(
                            exhibition
                        )

                        if not (
                            5.0
                            <= value
                            <= 10.0
                        ):
                            bad_exhibition.append(
                                (
                                    race_id,
                                    lane,
                                    exhibition,
                                )
                            )

                    except ValueError:
                        bad_exhibition.append(
                            (
                                race_id,
                                lane,
                                exhibition,
                            )
                        )

    print(
        "========================================"
    )

    print(
        "100日履歴 拡張項目検証"
    )

    print(
        "========================================"
    )

    print(
        f"対象期間: "
        f"{args.start} ～ {args.end}"
    )

    print(
        f"対象履歴ファイル: "
        f"{len(files)}"
    )

    print(
        f"総艇データ: "
        f"{total_rows}"
    )

    print(
        f"motor_no取得: "
        f"{motor_rows}"
    )

    print(
        f"boat_no取得: "
        f"{boat_rows}"
    )

    print(
        f"exhibition_time取得: "
        f"{exhibition_rows}"
    )

    print(
        f"motor_no値異常: "
        f"{len(bad_motor)}"
    )

    print(
        f"boat_no値異常: "
        f"{len(bad_boat)}"
    )

    print(
        f"exhibition_time値異常: "
        f"{len(bad_exhibition)}"
    )

    print(
        "拡張項目不足ファイル: "
        f"{len(missing_columns)}"
    )

    if missing_columns:
        print("")
        print(
            "拡張項目不足ファイル:"
        )

        for item in (
            missing_columns[:10]
        ):
            print(
                item
            )

    if bad_motor:
        print("")
        print(
            "motor_no異常・先頭10件:"
        )

        for item in (
            bad_motor[:10]
        ):
            print(
                item
            )

    if bad_boat:
        print("")
        print(
            "boat_no異常・先頭10件:"
        )

        for item in (
            bad_boat[:10]
        ):
            print(
                item
            )

    if bad_exhibition:
        print("")
        print(
            "exhibition_time異常・先頭10件:"
        )

        for item in (
            bad_exhibition[:10]
        ):
            print(
                item
            )

    expected_days = (
        end_date
        - start_date
    )

    # YYYYMMDD同士の単純減算は日数ではないので、
    # 今回は指定された100日バックフィルの
    # ファイル数を直接確認する。
    if len(
        files
    ) != 100:
        print(
            "ERROR: "
            "対象100日分の履歴ファイルが揃っていません",
            file=sys.stderr,
        )

        return 1

    if missing_columns:
        print(
            "ERROR: "
            "拡張3項目がないファイルがあります",
            file=sys.stderr,
        )

        return 1

    if total_rows == 0:
        print(
            "ERROR: 艇データが0件です",
            file=sys.stderr,
        )

        return 1

    if motor_rows == 0:
        print(
            "ERROR: motor_noが全件欠損です",
            file=sys.stderr,
        )

        return 1

    if boat_rows == 0:
        print(
            "ERROR: boat_noが全件欠損です",
            file=sys.stderr,
        )

        return 1

    if exhibition_rows == 0:
        print(
            "ERROR: exhibition_timeが全件欠損です",
            file=sys.stderr,
        )

        return 1

    if bad_motor:
        print(
            "ERROR: motor_noに異常値があります",
            file=sys.stderr,
        )

        return 1

    if bad_boat:
        print(
            "ERROR: boat_noに異常値があります",
            file=sys.stderr,
        )

        return 1

    if bad_exhibition:
        print(
            "ERROR: exhibition_timeに異常値があります",
            file=sys.stderr,
        )

        return 1

    print("")
    print(
        "========================================"
    )

    print(
        "100日履歴 拡張項目検証 PASS"
    )

    print(
        "========================================"
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )