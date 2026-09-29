from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


JST = timezone(timedelta(hours=9))


def parse_args():
    parser = argparse.ArgumentParser(
        description="スマホ確認用の最新予想一覧を生成"
    )
    parser.add_argument(
        "--date",
        required=True,
        help="対象日 YYYYMMDD",
    )
    parser.add_argument(
        "--now",
        default=None,
        help="現在時刻 ISO8601。省略時は日本時間の現在時刻",
    )
    return parser.parse_args()


def text(value):
    if value is None:
        return ""
    return str(value).strip()


def to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_now(value):
    if not value:
        return datetime.now(JST)

    raw = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(raw)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)

    return dt.astimezone(JST)


def load_json(path, required=False):
    path = Path(path)

    if not path.exists():
        if required:
            raise RuntimeError(f"ファイルがありません: {path}")
        return None

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def first_value(mapping, keys):
    if not isinstance(mapping, dict):
        return None

    for key in keys:
        value = mapping.get(key)

        if value not in (None, ""):
            return value

    return None


def parse_deadline(target_date, value):
    raw = text(value)

    if not raw:
        return None

    try:
        dt = datetime.fromisoformat(
            raw.replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)

        return dt.astimezone(JST)

    except ValueError:
        pass

    day = datetime.strptime(
        target_date,
        "%Y%m%d",
    ).date()

    for fmt in (
        "%H:%M:%S",
        "%H:%M",
        "%H%M",
    ):
        try:
            tm = datetime.strptime(
                raw,
                fmt,
            ).time()

            return datetime.combine(
                day,
                tm,
                tzinfo=JST,
            )

        except ValueError:
            pass

    for fmt in (
        "%Y%m%d%H%M",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
    ):
        try:
            dt = datetime.strptime(
                raw,
                fmt,
            )
            return dt.replace(tzinfo=JST)

        except ValueError:
            pass

    return None


def load_program_deadlines(target_date):
    path = (
        Path("daily_inputs")
        / target_date[:4]
        / target_date[4:6]
        / target_date[6:8]
        / f"program_races_{target_date}.csv"
    )

    result = {}

    if not path.exists():
        return result

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        reader = csv.DictReader(f)

        for row in reader:
            race_id = text(
                row.get("race_id")
            )

            deadline = first_value(
                row,
                (
                    "deadline",
                    "deadline_time",
                    "close_time",
                    "cutoff_time",
                ),
            )

            if race_id and deadline:
                result[race_id] = deadline

    return result


def prediction_map(payload):
    if not isinstance(payload, dict):
        return {}

    races = payload.get("races")

    if not isinstance(races, list):
        return {}

    result = {}

    for race in races:
        race_id = text(
            race.get("race_id")
        )

        if race_id:
            result[race_id] = race

    return result


def ranked_boats(race):
    boats = race.get("boats") or []

    rows = [
        boat
        for boat in boats
        if to_int(
            boat.get("boat")
        )
        is not None
    ]

    def sort_key(boat):
        rank = to_int(
            boat.get("rank")
        )

        score = to_float(
            boat.get("score")
        )

        boat_no = to_int(
            boat.get("boat")
        ) or 99

        if rank is not None:
            return (
                0,
                rank,
                boat_no,
            )

        return (
            1,
            -(score or 0),
            boat_no,
        )

    rows.sort(
        key=sort_key
    )

    return rows


def racer_label(boat):
    boat_no = to_int(
        boat.get("boat")
    )

    racer_name = text(
        boat.get("racer_name")
    )

    score = to_float(
        boat.get("score")
    )

    if boat_no is None:
        return "-"

    label = f"{boat_no}号艇"

    if racer_name:
        label += f" {racer_name}"

    if score is not None:
        label += f" ({score:.1f})"

    return label


def race_deadline_raw(
    race,
    program_deadlines,
):
    race_id = text(
        race.get("race_id")
    )

    value = first_value(
        race,
        (
            "deadline",
            "deadline_time",
            "close_time",
            "cutoff_time",
        ),
    )

    if value not in (None, ""):
        return value

    return program_deadlines.get(
        race_id
    )


def main():
    args = parse_args()

    target_date = args.date
    now = parse_now(args.now)

    datetime.strptime(
        target_date,
        "%Y%m%d",
    )

    base = (
        Path("predictions")
        / target_date[:4]
        / target_date[4:6]
        / target_date[6:8]
    )

    morning_path = (
        base
        / f"morning_predictions_{target_date}.json"
    )

    live_path = (
        base
        / "live"
        / f"live_predictions_final_{target_date}.json"
    )

    morning_payload = load_json(
        morning_path,
        required=True,
    )

    live_payload = load_json(
        live_path,
        required=False,
    )

    morning = prediction_map(
        morning_payload
    )

    live = prediction_map(
        live_payload
    )

    program_deadlines = (
        load_program_deadlines(
            target_date
        )
    )

    race_ids = sorted(
        set(morning)
        | set(live)
    )

    upcoming = []

    for race_id in race_ids:
        if race_id in live:
            race = live[race_id]
            prediction_type = "直前"
        else:
            race = morning[race_id]
            prediction_type = "朝"

        deadline_raw = (
            race_deadline_raw(
                race,
                program_deadlines,
            )
        )

        deadline = parse_deadline(
            target_date,
            deadline_raw,
        )

        if (
            deadline is not None
            and deadline <= now
        ):
            continue

        boats = ranked_boats(race)

        if len(boats) < 3:
            continue

        upcoming.append(
            {
                "race_id": race_id,
                "venue_code": text(
                    race.get("venue_code")
                ),
                "venue_name": text(
                    race.get("venue_name")
                ),
                "race": to_int(
                    race.get("race")
                ),
                "deadline_raw": text(
                    deadline_raw
                ),
                "deadline_dt": deadline,
                "prediction_type": (
                    prediction_type
                ),
                "top3": boats[:3],
                "strength": text(
                    race.get("strength")
                ),
            }
        )

    upcoming.sort(
        key=lambda row: (
            row["deadline_dt"]
            or datetime.max.replace(
                tzinfo=JST
            ),
            row["venue_code"],
            row["race"] or 99,
        )
    )

    live_count = sum(
        1
        for row in upcoming
        if row["prediction_type"]
        == "直前"
    )

    morning_count = (
        len(upcoming)
        - live_count
    )

    grouped = defaultdict(list)

    for row in upcoming:
        venue = (
            row["venue_name"]
            or row["venue_code"]
            or "会場不明"
        )

        grouped[venue].append(row)

    lines = []

    lines.append(
        "# ボートレースAI 最新予想"
    )
    lines.append("")
    lines.append(
        f"**最終更新："
        f"{now.strftime('%Y/%m/%d %H:%M')} JST**"
    )
    lines.append("")
    lines.append(
        f"対象日："
        f"{target_date[:4]}/"
        f"{target_date[4:6]}/"
        f"{target_date[6:8]}"
    )
    lines.append("")
    lines.append(
        "直前予測が取得できているレースは"
        "**直前予測を優先**し、"
        "未取得のレースは朝予測を表示しています。"
    )
    lines.append("")
    lines.append(
        f"- 締切前の表示対象："
        f"**{len(upcoming)}レース**"
    )
    lines.append(
        f"- 直前予測："
        f"**{live_count}レース**"
    )
    lines.append(
        f"- 朝予測："
        f"**{morning_count}レース**"
    )
    lines.append("")
    lines.append(
        "> ※表示スコアは現行モデルの"
        "比較用スコアであり、"
        "勝率そのものではありません。"
    )
    lines.append("")

    if not upcoming:
        lines.append(
            "現在、締切前の表示対象レースはありません。"
        )

    else:
        for venue, races in grouped.items():
            lines.append(
                f"## {venue}"
            )
            lines.append("")
            lines.append(
                "| 締切 | R | 種別 | ◎ | ○ | ▲ |"
            )
            lines.append(
                "|---|---:|---|---|---|---|"
            )

            for row in races:
                deadline = row[
                    "deadline_dt"
                ]

                deadline_label = (
                    deadline.strftime(
                        "%H:%M"
                    )
                    if deadline
                    else (
                        row["deadline_raw"]
                        or "不明"
                    )
                )

                race_no = (
                    row["race"]
                    if row["race"]
                    is not None
                    else "-"
                )

                top3 = row["top3"]

                lines.append(
                    "| "
                    f"{deadline_label}"
                    " | "
                    f"{race_no}"
                    " | "
                    f"{row['prediction_type']}"
                    " | "
                    f"{racer_label(top3[0])}"
                    " | "
                    f"{racer_label(top3[1])}"
                    " | "
                    f"{racer_label(top3[2])}"
                    " |"
                )

            lines.append("")

    output_md = (
        Path("predictions")
        / "latest.md"
    )

    output_json = (
        Path("predictions")
        / "latest.json"
    )

    output_md.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_md.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    machine_rows = []

    for row in upcoming:
        deadline = row["deadline_dt"]

        machine_rows.append(
            {
                "race_id": (
                    row["race_id"]
                ),
                "venue_code": (
                    row["venue_code"]
                ),
                "venue_name": (
                    row["venue_name"]
                ),
                "race": row["race"],
                "deadline": (
                    deadline.isoformat()
                    if deadline
                    else row[
                        "deadline_raw"
                    ]
                ),
                "prediction_type": (
                    row[
                        "prediction_type"
                    ]
                ),
                "top3": [
                    {
                        "rank": index,
                        "boat": to_int(
                            boat.get("boat")
                        ),
                        "racer_name": text(
                            boat.get(
                                "racer_name"
                            )
                        ),
                        "score": to_float(
                            boat.get("score")
                        ),
                    }
                    for index, boat
                    in enumerate(
                        row["top3"],
                        start=1,
                    )
                ],
            }
        )

    output_json.write_text(
        json.dumps(
            {
                "target_date": target_date,
                "generated_at": (
                    now.isoformat()
                ),
                "upcoming_race_count": (
                    len(upcoming)
                ),
                "live_race_count": (
                    live_count
                ),
                "morning_race_count": (
                    morning_count
                ),
                "races": machine_rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "========================================"
    )
    print(
        "スマホ用 最新予想一覧"
    )
    print(
        "========================================"
    )
    print(
        "表示対象:",
        len(upcoming),
        "R",
    )
    print(
        "直前予測:",
        live_count,
        "R",
    )
    print(
        "朝予測:",
        morning_count,
        "R",
    )
    print(
        "出力: predictions/latest.md"
    )
    print(
        "出力: predictions/latest.json"
    )
    print(
        "最新予想一覧生成: PASS"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())