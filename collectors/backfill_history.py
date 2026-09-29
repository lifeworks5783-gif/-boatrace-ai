from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import daily_results_fast as fast


JST = timezone(timedelta(hours=9))

ARCHIVE_DIR = Path("archive")
HISTORY_DIR = Path("history")


def archive_dir(
    target_date: str,
) -> Path:

    dt = datetime.strptime(
        target_date,
        "%Y%m%d",
    )

    return (
        ARCHIVE_DIR
        / dt.strftime("%Y")
        / dt.strftime("%m")
        / dt.strftime("%d")
    )


def required_files(
    target_date: str,
) -> list[str]:

    return [
        f"venues_{target_date}.csv",
        f"results_{target_date}_all.csv",
        f"boat_results_{target_date}_all.csv",
    ]


def already_exists(
    target_date: str,
) -> bool:

    dest = archive_dir(
        target_date
    )

    return all(
        (
            dest
            / filename
        ).exists()
        for filename
        in required_files(
            target_date
        )
    )


def save_day(
    target_date: str,
    venues,
    races,
    boats,
):

    dest = archive_dir(
        target_date
    )

    dest.mkdir(
        parents=True,
        exist_ok=True,
    )

    fast.write_csv(
        dest
        / f"venues_{target_date}.csv",
        venues,
        fast.VENUE_FIELDS,
    )

    fast.write_csv(
        dest
        / f"results_{target_date}_all.csv",
        races,
        fast.RESULT_FIELDS,
    )

    fast.write_csv(
        dest
        / f"boat_results_{target_date}_all.csv",
        boats,
        fast.BOAT_FIELDS,
    )


def collect_one_day(
    target_date: str,
):

    url = fast.build_url(
        target_date
    )

    archive_bytes = fast.fetch(
        url
    )

    payload = fast.extract_lzh(
        archive_bytes
    )

    (
        venues,
        races,
        boats,
    ) = fast.parse_payload(
        payload,
        target_date,
    )

    fast.basic_validate(
        venues,
        races,
        boats,
    )

    save_day(
        target_date,
        venues,
        races,
        boats,
    )

    return {
        "date": target_date,
        "venue_count": len(
            venues
        ),
        "race_count": len(
            races
        ),
        "boat_count": len(
            boats
        ),
        "source_url": url,
    }


def date_range(
    start_date,
    end_date,
):

    current = start_date

    while current <= end_date:

        yield current

        current += timedelta(
            days=1
        )


def main():

    parser = argparse.ArgumentParser(
        description=(
            "BOAT RACE公式Kファイルから"
            "過去結果を一括バックフィル"
        )
    )

    parser.add_argument(
        "--days",
        type=int,
        default=100,
        help=(
            "終了日から遡る日数。"
            "標準100日"
        ),
    )

    parser.add_argument(
        "--start",
        default=None,
        help=(
            "開始日 YYYYMMDD。"
            "指定時はdaysより優先"
        ),
    )

    parser.add_argument(
        "--end",
        default=None,
        help=(
            "終了日 YYYYMMDD。"
            "省略時は日本時間の前日"
        ),
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "既存日も再取得する"
        ),
    )

    parser.add_argument(
        "--sleep",
        type=float,
        default=0.7,
        help=(
            "日付間の待機秒数"
        ),
    )

    args = parser.parse_args()

    if args.days <= 0:
        print(
            "ERROR: --daysは1以上にしてください",
            file=sys.stderr,
        )

        return 1

    if args.end:
        try:
            end_date = datetime.strptime(
                args.end,
                "%Y%m%d",
            ).date()

        except ValueError:
            print(
                "ERROR: --endはYYYYMMDD形式です",
                file=sys.stderr,
            )

            return 1

    else:
        end_date = (
            datetime.now(
                JST
            )
            - timedelta(
                days=1
            )
        ).date()

    if args.start:
        try:
            start_date = datetime.strptime(
                args.start,
                "%Y%m%d",
            ).date()

        except ValueError:
            print(
                "ERROR: --startはYYYYMMDD形式です",
                file=sys.stderr,
            )

            return 1

    else:
        start_date = (
            end_date
            - timedelta(
                days=args.days - 1
            )
        )

    if start_date > end_date:
        print(
            "ERROR: 開始日が終了日より後です",
            file=sys.stderr,
        )

        return 1

    print(
        "========================================"
    )

    print(
        "過去競走成績バックフィル"
    )

    print(
        f"開始日: {start_date:%Y%m%d}"
    )

    print(
        f"終了日: {end_date:%Y%m%d}"
    )

    print(
        f"force: {args.force}"
    )

    print(
        "========================================"
    )

    report = {
        "started_at": datetime.now(
            JST
        ).isoformat(),

        "start_date": start_date.strftime(
            "%Y%m%d"
        ),

        "end_date": end_date.strftime(
            "%Y%m%d"
        ),

        "success": [],
        "skipped": [],
        "failed": [],
    }

    total_days = (
        (
            end_date
            - start_date
        ).days
        + 1
    )

    for index, day in enumerate(
        date_range(
            start_date,
            end_date,
        ),
        start=1,
    ):

        target_date = day.strftime(
            "%Y%m%d"
        )

        print("")
        print(
            "----------------------------------------"
        )

        print(
            f"[{index}/{total_days}] "
            f"{target_date}"
        )

        if (
            not args.force
            and already_exists(
                target_date
            )
        ):
            print(
                "既存データあり → SKIP"
            )

            report[
                "skipped"
            ].append(
                target_date
            )

            continue

        try:
            result = collect_one_day(
                target_date
            )

            report[
                "success"
            ].append(
                result
            )

            print(
                "PASS "
                f"{result['venue_count']}場 / "
                f"{result['race_count']}R / "
                f"{result['boat_count']}艇"
            )

        except Exception as exc:

            message = str(
                exc
            )

            report[
                "failed"
            ].append(
                {
                    "date": target_date,
                    "error": message,
                }
            )

            print(
                f"FAILED: {message}"
            )

        time.sleep(
            max(
                args.sleep,
                0,
            )
        )

    report[
        "finished_at"
    ] = datetime.now(
        JST
    ).isoformat()

    report[
        "success_days"
    ] = len(
        report[
            "success"
        ]
    )

    report[
        "skipped_days"
    ] = len(
        report[
            "skipped"
        ]
    )

    report[
        "failed_days"
    ] = len(
        report[
            "failed"
        ]
    )

    HISTORY_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path = (
        HISTORY_DIR
        / (
            "backfill_report_"
            f"{start_date:%Y%m%d}_"
            f"{end_date:%Y%m%d}.json"
        )
    )

    report_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("")
    print(
        "========================================"
    )

    print(
        "バックフィル結果"
    )

    print(
        "新規取得成功: "
        f"{report['success_days']}日"
    )

    print(
        "既存スキップ: "
        f"{report['skipped_days']}日"
    )

    print(
        "取得失敗: "
        f"{report['failed_days']}日"
    )

    print(
        f"レポート: {report_path}"
    )

    print(
        "========================================"
    )

    # 一部の日付が取得できなくても、
    # 全体のデータは保存して後で再取得できる。
    # 大量バックフィルを無駄にしないため、
    # 失敗率が高い場合だけFAILにする。

    attempted = (
        report[
            "success_days"
        ]
        + report[
            "failed_days"
        ]
    )

    if attempted > 0:

        failure_rate = (
            report[
                "failed_days"
            ]
            / attempted
        )

        if failure_rate > 0.10:
            print(
                "ERROR: "
                "取得失敗率が10%を超えています",
                file=sys.stderr,
            )

            return 1

    print(
        "バックフィル PASS"
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )