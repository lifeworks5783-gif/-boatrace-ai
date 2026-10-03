from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


JST = timezone(timedelta(hours=9))


def parse_args():
    parser = argparse.ArgumentParser(
        description="締切が近い順のスマホ用予想一覧を生成"
    )
    parser.add_argument(
        "--date",
        required=True,
        help="対象日 YYYYMMDD",
    )
    return parser.parse_args()


def text(value):
    if value is None:
        return ""
    return str(value).strip()


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def score_label(value):
    score = to_float(value)

    if score is None:
        return "未算出"

    return f"{score:.1f}"


def deadline_dt(value):
    raw = text(value)

    if not raw:
        return datetime.max.replace(
            tzinfo=JST
        )

    try:
        dt = datetime.fromisoformat(
            raw.replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=JST
            )

        return dt.astimezone(JST)

    except ValueError:
        return datetime.max.replace(
            tzinfo=JST
        )


def deadline_label(value):
    dt = deadline_dt(value)

    if dt.year == datetime.max.year:
        return text(value) or "不明"

    return dt.strftime("%H:%M")


def racer_label(boat):
    boat_no = boat.get("boat")

    racer_name = text(
        boat.get("racer_name")
    )

    score = score_label(
        boat.get("score")
    )

    label = f"{boat_no}号艇"

    if racer_name:
        label += f" {racer_name}"

    label += f" ({score})"

    return label


def compact_scores(boats):
    parts = []

    for index, boat in enumerate(
        boats,
        start=1,
    ):
        parts.append(
            f"{index}位 "
            f"{boat.get('boat')}号艇 "
            f"{score_label(boat.get('score'))}"
        )

    return " ＞ ".join(parts)


def candidates_text(values):
    if not values:
        return "なし"

    return "・".join(
        str(value)
        for value in values
    )


def main():
    args = parse_args()

    target_date = args.date

    datetime.strptime(
        target_date,
        "%Y%m%d",
    )

    source_path = Path(
        "predictions"
    ) / target_date[:4] / target_date[4:6] / target_date[6:8] / "live" / f"formation_predictions_final_{target_date}.json"

    if not source_path.exists():
        source_path = Path(
            "predictions/latest.json"
        )

    if not source_path.exists():
        raise RuntimeError(
            "predictions/latest.json がありません"
        )

    payload = json.loads(
        source_path.read_text(
            encoding="utf-8"
        )
    )

    if text(
        payload.get("target_date")
    ) != target_date:
        raise RuntimeError(
            "latest.json の対象日が一致しません"
        )

    races = payload.get("races") or []

    # 家族ページでは締切後も当日に予測したフォーメーションを残す。
    # latest.json は締切前だけなので、可能なら formation_predictions_final を正本にする。
    races = sorted(
        races,
        key=lambda race: (
            deadline_dt(
                race.get("deadline")
            ),
            text(
                race.get("venue_code")
            ),
            race.get("race") or 99,
        ),
    )

    lines = []

    lines.append(
        "# 締切順・最新予想"
    )

    lines.append("")

    generated_at = text(
        payload.get("generated_at")
    )

    try:
        generated_dt = datetime.fromisoformat(
            generated_at.replace(
                "Z",
                "+00:00",
            )
        )

        if generated_dt.tzinfo is None:
            generated_dt = generated_dt.replace(
                tzinfo=JST
            )

        generated_label = (
            generated_dt
            .astimezone(JST)
            .strftime(
                "%Y/%m/%d %H:%M"
            )
        )

    except ValueError:
        generated_label = (
            generated_at
            or "不明"
        )

    lines.append(
        f"**最終更新："
        f"{generated_label} JST**"
    )

    lines.append("")

    lines.append(
        "会場に関係なく、"
        "**締切が近い順**に表示しています。"
    )

    lines.append("")

    lines.append(
        f"本日の予測："
        f"**{len(races)}レース**（終了済みを含む）"
    )

    lines.append("")

    lines.append(
        "> 「直前」は展示等を反映済み、"
        "「朝」は朝予測です。"
    )

    lines.append("")

    lines.append(
        "> スコアは勝率ではなく、"
        "AIモデル内の比較用スコアです。"
    )

    lines.append("")

    for index, race in enumerate(
        races,
        start=1,
    ):
        venue = (
            text(
                race.get("venue_name")
            )
            or text(
                race.get("venue_code")
            )
            or "会場不明"
        )

        race_no = (
            race.get("race")
            if race.get("race")
            is not None
            else "-"
        )

        prediction_type = (
            text(
                race.get(
                    "prediction_type"
                )
            )
            or "不明"
        )

        boats = (
            race.get("boats")
            or []
        )

        formation = (
            race.get("formation")
            or {}
        )

        lines.append(
            f"## {index}. "
            f"{deadline_label(race.get('deadline'))} "
            f"{venue} {race_no}R "
            f"【{prediction_type}】"
        )

        lines.append("")

        if len(boats) >= 3:
            lines.append(
                f"**◎ {racer_label(boats[0])}**"
            )

            lines.append("")

            lines.append(
                f"○ {racer_label(boats[1])}"
            )

            lines.append("")

            lines.append(
                f"▲ {racer_label(boats[2])}"
            )

            lines.append("")

        if boats:
            lines.append(
                "**全6艇スコア（予測順位順）**"
            )

            lines.append("")

            lines.append(
                compact_scores(boats)
            )

            lines.append("")

        points = (
            formation.get("points")
            or 0
        )

        if points > 0:
            lines.append(
                f"**3連単："
                f"{formation.get('formation_type', '不明')} / "
                f"{points}点 / "
                f"{formation.get('investment_100yen', 0)}円**"
            )

            lines.append("")

            lines.append(
                "1着："
                + candidates_text(
                    formation.get(
                        "first_candidates"
                    )
                )
            )

            lines.append("")

            lines.append(
                "2着："
                + candidates_text(
                    formation.get(
                        "second_candidates"
                    )
                )
            )

            lines.append("")

            lines.append(
                "3着："
                + candidates_text(
                    formation.get(
                        "third_candidates"
                    )
                )
            )

            lines.append("")

            lines.append(
                "買い目："
                + " / ".join(
                    formation.get(
                        "combinations"
                    )
                    or []
                )
            )

        else:
            lines.append(
                "**3連単："
                "スコア不足のため生成なし**"
            )

        lines.append("")

        lines.append("---")

        lines.append("")

    output_md = Path(
        "predictions/latest_by_deadline.md"
    )

    output_json = Path(
        "predictions/latest_by_deadline.json"
    )

    output_md.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    output_json.write_text(
        json.dumps(
            {
                "target_date": target_date,
                "generated_at": (
                    payload.get(
                        "generated_at"
                    )
                ),
                "sort_order": (
                    "deadline_ascending"
                ),
                "race_count": len(races),
                "races": races,
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
        "締切順・最新予想一覧"
    )

    print(
        "========================================"
    )

    print(
        "表示レース:",
        len(races),
    )

    print(
        "predictions/latest_by_deadline.md: PASS"
    )

    print(
        "predictions/latest_by_deadline.json: PASS"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )