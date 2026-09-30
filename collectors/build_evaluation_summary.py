#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


def find_dict(
    obj: Any,
    target_keys: Iterable[str],
) -> Optional[Dict[str, Any]]:

    wanted = {
        str(x).lower()
        for x in target_keys
    }

    if isinstance(obj, dict):

        for key, value in obj.items():

            if (
                str(key).lower()
                in wanted
                and isinstance(
                    value,
                    dict,
                )
            ):
                return value

        for value in obj.values():

            found = find_dict(
                value,
                target_keys,
            )

            if found is not None:
                return found

    elif isinstance(obj, list):

        for value in obj:

            found = find_dict(
                value,
                target_keys,
            )

            if found is not None:
                return found

    return None


def get_value(
    obj: Dict[str, Any],
    keys: Iterable[str],
) -> Any:

    if not isinstance(
        obj,
        dict,
    ):
        return None

    lower_map = {
        str(k).lower(): v
        for k, v in obj.items()
    }

    for key in keys:

        key_lower = str(
            key
        ).lower()

        if key_lower in lower_map:
            return lower_map[
                key_lower
            ]

    return None


def to_number(
    value: Any,
) -> Optional[float]:

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return None

    if isinstance(
        value,
        (
            int,
            float,
        ),
    ):
        return float(
            value
        )

    text = (
        str(value)
        .replace(",", "")
        .replace("%", "")
        .replace("円", "")
        .strip()
    )

    try:
        return float(
            text
        )

    except Exception:
        return None


def fmt_count(
    value: Any,
) -> str:

    num = to_number(
        value
    )

    if num is None:
        return "未算出"

    return f"{int(round(num)):,}"


def fmt_yen(
    value: Any,
) -> str:

    num = to_number(
        value
    )

    if num is None:
        return "未算出"

    return (
        f"{int(round(num)):,}円"
    )


def fmt_percent(
    value: Any,
) -> str:

    num = to_number(
        value
    )

    if num is None:
        return "未算出"

    if 0 <= num <= 1:
        num *= 100

    return f"{num:.1f}%"


def calc_rate(
    hits: Any,
    races: Any,
) -> Optional[float]:

    h = to_number(
        hits
    )

    r = to_number(
        races
    )

    if (
        h is None
        or r is None
        or r == 0
    ):
        return None

    return (
        h / r * 100
    )


def extract_prediction_stage(
    root: Dict[str, Any],
    stage_names: Iterable[str],
) -> Dict[str, Any]:

    stage = find_dict(
        root,
        stage_names,
    )

    if stage is None:
        stage = {}

    races = get_value(
        stage,
        [
            "races",
            "race_count",
            "evaluated_races",
            "total_races",
        ],
    )

    top1_hits = get_value(
        stage,
        [
            "top1_hits",
            "winner_hits",
            "first_hits",
            "first_place_hits",
            "rank1_hits",
        ],
    )

    top1_rate = get_value(
        stage,
        [
            "top1_rate",
            "winner_rate",
            "first_hit_rate",
            "first_place_rate",
            "rank1_hit_rate",
        ],
    )

    top2_hits = get_value(
        stage,
        [
            "top2_hits",
            "top2_capture_hits",
            "top2_captured",
        ],
    )

    top2_rate = get_value(
        stage,
        [
            "top2_rate",
            "top2_capture_rate",
            "top2_hit_rate",
        ],
    )

    top3_hits = get_value(
        stage,
        [
            "top3_hits",
            "top3_capture_hits",
            "top3_captured",
        ],
    )

    top3_rate = get_value(
        stage,
        [
            "top3_rate",
            "top3_capture_rate",
            "top3_hit_rate",
        ],
    )

    if (
        top1_rate is None
        and top1_hits is not None
    ):
        top1_rate = calc_rate(
            top1_hits,
            races,
        )

    if (
        top2_rate is None
        and top2_hits is not None
    ):
        top2_rate = calc_rate(
            top2_hits,
            races,
        )

    if (
        top3_rate is None
        and top3_hits is not None
    ):
        top3_rate = calc_rate(
            top3_hits,
            races,
        )

    return {
        "races":
            races,

        "top1_hits":
            top1_hits,

        "top1_rate":
            top1_rate,

        "top2_hits":
            top2_hits,

        "top2_rate":
            top2_rate,

        "top3_hits":
            top3_hits,

        "top3_rate":
            top3_rate,
    }


def extract_formation_block(
    block: Dict[str, Any],
) -> Dict[str, Any]:

    races = get_value(
        block,
        [
            "races",
            "race_count",
            "total_races",
        ],
    )

    hits = get_value(
        block,
        [
            "hits",
            "hit_count",
            "winning_races",
        ],
    )

    hit_rate = get_value(
        block,
        [
            "hit_rate",
            "hits_rate",
            "accuracy",
        ],
    )

    if hit_rate is None:
        hit_rate = calc_rate(
            hits,
            races,
        )

    points = get_value(
        block,
        [
            "points",
            "total_points",
            "bet_points",
        ],
    )

    investment = get_value(
        block,
        [
            "investment",
            "total_investment",
            "bet_amount",
            "stake",
        ],
    )

    if (
        investment is None
        and points is not None
    ):

        point_num = to_number(
            points
        )

        if point_num is not None:
            investment = (
                point_num * 100
            )

    returns = get_value(
        block,
        [
            "return",
            "returns",
            "total_return",
            "payout",
            "payout_total",
        ],
    )

    profit = get_value(
        block,
        [
            "profit",
            "net_profit",
            "profit_loss",
        ],
    )

    if (
        profit is None
        and investment is not None
        and returns is not None
    ):

        inv = to_number(
            investment
        )

        ret = to_number(
            returns
        )

        if (
            inv is not None
            and ret is not None
        ):
            profit = (
                ret - inv
            )

    recovery = get_value(
        block,
        [
            "recovery_rate",
            "return_rate",
            "roi",
            "recovery",
        ],
    )

    if (
        recovery is None
        and investment is not None
        and returns is not None
    ):

        inv = to_number(
            investment
        )

        ret = to_number(
            returns
        )

        if (
            inv is not None
            and inv != 0
            and ret is not None
        ):
            recovery = (
                ret / inv * 100
            )

    return {
        "races":
            races,

        "hits":
            hits,

        "hit_rate":
            hit_rate,

        "points":
            points,

        "investment":
            investment,

        "returns":
            returns,

        "profit":
            profit,

        "recovery_rate":
            recovery,
    }


def append_prediction_section(
    lines: list[str],
    title: str,
    data: Dict[str, Any],
) -> None:

    lines.append(
        f"## {title}"
    )

    lines.append("")

    lines.append(
        f"- 評価レース数："
        f"{fmt_count(data['races'])}"
    )

    lines.append(
        f"- 1着的中数："
        f"{fmt_count(data['top1_hits'])}"
    )

    lines.append(
        f"- 1着的中率："
        f"{fmt_percent(data['top1_rate'])}"
    )

    lines.append(
        f"- 上位2艇捕捉数："
        f"{fmt_count(data['top2_hits'])}"
    )

    lines.append(
        f"- 上位2艇捕捉率："
        f"{fmt_percent(data['top2_rate'])}"
    )

    lines.append(
        f"- 上位3艇捕捉数："
        f"{fmt_count(data['top3_hits'])}"
    )

    lines.append(
        f"- 上位3艇捕捉率："
        f"{fmt_percent(data['top3_rate'])}"
    )

    lines.append("")


def append_formation_section(
    lines: list[str],
    title: str,
    data: Dict[str, Any],
) -> None:

    lines.append(
        f"## {title}"
    )

    lines.append("")

    lines.append(
        f"- 対象レース数："
        f"{fmt_count(data['races'])}"
    )

    lines.append(
        f"- 的中数："
        f"{fmt_count(data['hits'])}"
    )

    lines.append(
        f"- 的中率："
        f"{fmt_percent(data['hit_rate'])}"
    )

    lines.append(
        f"- 購入点数："
        f"{fmt_count(data['points'])}"
    )

    lines.append(
        f"- 投資額："
        f"{fmt_yen(data['investment'])}"
    )

    lines.append(
        f"- 払戻額："
        f"{fmt_yen(data['returns'])}"
    )

    lines.append(
        f"- 損益："
        f"{fmt_yen(data['profit'])}"
    )

    lines.append(
        f"- 回収率："
        f"{fmt_percent(data['recovery_rate'])}"
    )

    lines.append("")


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        required=True,
        help="YYYYMMDD",
    )

    args = parser.parse_args()

    date = args.date

    year = date[:4]
    month = date[4:6]
    day = date[6:8]

    eval_dir = Path(
        "evaluations"
    ) / year / month / day

    prediction_path = (
        eval_dir
        / f"prediction_evaluation_{date}.json"
    )

    formation_path = (
        eval_dir
        / f"formation_simulation_{date}.json"
    )

    prediction = load_json(
        prediction_path
    )

    formation = load_json(
        formation_path
    )

    if not prediction:
        raise SystemExit(
            f"missing: {prediction_path}"
        )

    if not formation:
        raise SystemExit(
            f"missing: {formation_path}"
        )

    morning = extract_prediction_stage(
        prediction,
        [
            "morning",
            "朝",
            "morning_prediction",
            "morning_predictions",
        ],
    )

    live = extract_prediction_stage(
        prediction,
        [
            "live",
            "直前",
            "live_prediction",
            "live_predictions",
        ],
    )

    overall_raw = find_dict(
        formation,
        [
            "overall",
            "total",
            "summary",
        ],
    )

    if overall_raw is None:
        overall_raw = formation

    overall = extract_formation_block(
        overall_raw
    )

    type_root = find_dict(
        formation,
        [
            "by_formation_type",
            "formation_types",
            "by_type",
        ],
    )

    if type_root is None:
        type_root = {}

    prediction_type_root = find_dict(
        formation,
        [
            "by_prediction_type",
            "prediction_types",
            "by_stage",
        ],
    )

    if prediction_type_root is None:
        prediction_type_root = {}

    lines: list[str] = []

    display_date = (
        f"{date[:4]}/"
        f"{date[4:6]}/"
        f"{date[6:8]}"
    )

    lines.append(
        "# ボートレースAI 予測結果サマリー"
    )

    lines.append("")

    lines.append(
        f"対象日：{display_date}"
    )

    lines.append(
        "最終更新："
        + datetime.now()
        .astimezone()
        .strftime(
            "%Y/%m/%d %H:%M JST"
        )
    )

    lines.append("")

    lines.append(
        "> このページだけ見れば、"
        "当日の朝予測・直前予測・"
        "3連単フォーメーションの"
        "主要成績を確認できます。"
    )

    lines.append("")

    append_prediction_section(
        lines,
        "朝予測",
        morning,
    )

    append_prediction_section(
        lines,
        "直前予測",
        live,
    )

    append_formation_section(
        lines,
        "3連単フォーメーション総合",
        overall,
    )

    if type_root:

        lines.append(
            "## フォーメーションタイプ別"
        )

        lines.append("")

        for key, value in (
            type_root.items()
        ):

            if not isinstance(
                value,
                dict,
            ):
                continue

            data = (
                extract_formation_block(
                    value
                )
            )

            lines.append(
                f"### {key}"
            )

            lines.append("")

            lines.append(
                f"- レース数："
                f"{fmt_count(data['races'])}"
            )

            lines.append(
                f"- 的中数："
                f"{fmt_count(data['hits'])}"
            )

            lines.append(
                f"- 的中率："
                f"{fmt_percent(data['hit_rate'])}"
            )

            lines.append(
                f"- 投資額："
                f"{fmt_yen(data['investment'])}"
            )

            lines.append(
                f"- 払戻額："
                f"{fmt_yen(data['returns'])}"
            )

            lines.append(
                f"- 損益："
                f"{fmt_yen(data['profit'])}"
            )

            lines.append(
                f"- 回収率："
                f"{fmt_percent(data['recovery_rate'])}"
            )

            lines.append("")

    if prediction_type_root:

        lines.append(
            "## 朝／直前フォーメーション別"
        )

        lines.append("")

        for key, value in (
            prediction_type_root.items()
        ):

            if not isinstance(
                value,
                dict,
            ):
                continue

            data = (
                extract_formation_block(
                    value
                )
            )

            lines.append(
                f"### {key}"
            )

            lines.append("")

            lines.append(
                f"- レース数："
                f"{fmt_count(data['races'])}"
            )

            lines.append(
                f"- 的中数："
                f"{fmt_count(data['hits'])}"
            )

            lines.append(
                f"- 的中率："
                f"{fmt_percent(data['hit_rate'])}"
            )

            lines.append(
                f"- 投資額："
                f"{fmt_yen(data['investment'])}"
            )

            lines.append(
                f"- 払戻額："
                f"{fmt_yen(data['returns'])}"
            )

            lines.append(
                f"- 損益："
                f"{fmt_yen(data['profit'])}"
            )

            lines.append(
                f"- 回収率："
                f"{fmt_percent(data['recovery_rate'])}"
            )

            lines.append("")

    lines.append(
        "## 元データ"
    )

    lines.append("")

    lines.append(
        f"- `{prediction_path}`"
    )

    lines.append(
        f"- `{formation_path}`"
    )

    lines.append("")

    lines.append(
        "※ スコアは勝率そのものではなく、"
        "艇同士を比較するための予測スコアです。"
    )

    content = (
        "\n".join(lines)
        + "\n"
    )

    dated_path = (
        eval_dir
        / f"summary_{date}.md"
    )

    latest_path = (
        Path("evaluations")
        / "latest_summary.md"
    )

    dated_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    latest_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dated_path.write_text(
        content,
        encoding="utf-8",
    )

    latest_path.write_text(
        content,
        encoding="utf-8",
    )

    print(
        "評価サマリー生成: PASS"
    )

    print(
        dated_path
    )

    print(
        latest_path
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )