#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


FORMATION_KEYS = [
    "overall",
    "total",
    "summary",
]

TYPE_KEYS = [
    "by_formation_type",
    "formation_types",
    "by_type",
]

PREDICTION_TYPE_KEYS = [
    "by_prediction_type",
    "prediction_types",
]


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def find_dict(obj: Any, names: Iterable[str]) -> Optional[Dict[str, Any]]:
    targets = {str(x).lower() for x in names}

    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).lower() in targets and isinstance(value, dict):
                return value
        for value in obj.values():
            found = find_dict(value, names)
            if found is not None:
                return found

    elif isinstance(obj, list):
        for value in obj:
            found = find_dict(value, names)
            if found is not None:
                return found

    return None


def get_value(obj: Dict[str, Any], keys: Iterable[str]) -> Any:
    if not isinstance(obj, dict):
        return None

    lower_map = {str(k).lower(): v for k, v in obj.items()}
    for key in keys:
        key_lower = str(key).lower()
        if key_lower in lower_map:
            return lower_map[key_lower]
    return None


def number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = (
        str(value)
        .replace(",", "")
        .replace("%", "")
        .replace("円", "")
        .strip()
    )

    try:
        return float(text)
    except Exception:
        return None


def fmt_count(value: Any) -> str:
    num = number(value)
    return "—" if num is None else f"{int(round(num)):,}"


def fmt_yen(value: Any) -> str:
    num = number(value)
    return "—" if num is None else f"{int(round(num)):,}円"


def fmt_percent(value: Any) -> str:
    num = number(value)
    if num is None:
        return "—"
    if 0 <= num <= 1:
        num *= 100
    return f"{num:.1f}%"


def calc_rate(hits: Any, races: Any) -> Optional[float]:
    hit_num = number(hits)
    race_num = number(races)
    if hit_num is None or race_num is None or race_num == 0:
        return None
    return hit_num / race_num * 100


def strategy_metrics(block: Dict[str, Any]) -> Dict[str, Any]:
    races = get_value(block, ["races", "race_count", "total_races"])
    hits = get_value(block, ["hits", "hit_count", "winning_races"])

    hit_rate = get_value(block, ["hit_rate", "accuracy", "hits_rate"])
    if hit_rate is None:
        hit_rate = calc_rate(hits, races)

    points = get_value(block, ["points", "total_points", "bet_points"])
    investment = get_value(
        block,
        ["investment", "total_investment", "bet_amount", "stake"],
    )

    if investment is None and points is not None:
        point_num = number(points)
        if point_num is not None:
            investment = point_num * 100

    returns = get_value(
        block,
        [
            "return",
            "returns",
            "total_return",
            "payout",
            "payout_total",
            "return_amount",
        ],
    )

    profit = get_value(block, ["profit", "net_profit", "profit_loss"])
    if profit is None and investment is not None and returns is not None:
        inv = number(investment)
        ret = number(returns)
        if inv is not None and ret is not None:
            profit = ret - inv

    recovery = get_value(
        block,
        [
            "recovery_rate_pct",
            "recovery_rate",
            "return_rate",
            "roi",
            "recovery",
        ],
    )

    if recovery is None and investment is not None and returns is not None:
        inv = number(investment)
        ret = number(returns)
        if inv is not None and inv != 0 and ret is not None:
            recovery = ret / inv * 100

    return {
        "races": races,
        "hits": hits,
        "hit_rate": hit_rate,
        "points": points,
        "investment": investment,
        "returns": returns,
        "profit": profit,
        "recovery_rate": recovery,
    }


def metric_card(label: str, value: str, sub: str = "") -> str:
    sub_html = ""
    if sub:
        sub_html = '<div class="metric-sub">' + html.escape(sub) + "</div>"

    return (
        '<div class="metric">'
        f'<div class="metric-label">{html.escape(label)}</div>'
        f'<div class="metric-value">{html.escape(value)}</div>'
        f"{sub_html}"
        "</div>"
    )


def strategy_html(title: str, subtitle: str, metrics: Dict[str, Any]) -> str:
    cards = [
        metric_card("対象レース", fmt_count(metrics["races"])),
        metric_card(
            "的中",
            fmt_count(metrics["hits"]),
            fmt_percent(metrics["hit_rate"]),
        ),
        metric_card("購入点数", fmt_count(metrics["points"])),
        metric_card("投資額", fmt_yen(metrics["investment"])),
        metric_card("払戻額", fmt_yen(metrics["returns"])),
        metric_card("損益", fmt_yen(metrics["profit"])),
        metric_card("回収率", fmt_percent(metrics["recovery_rate"])),
    ]

    return (
        '<section class="section-card">'
        f"<h2>{html.escape(title)}</h2>"
        f'<div class="section-note">{html.escape(subtitle)}</div>'
        '<div class="metric-grid">'
        + "".join(cards)
        + "</div>"
        "</section>"
    )


def ai_alignment_html(payload: Dict[str, Any]) -> str:
    if not payload:
        return ""

    overall = find_dict(payload, FORMATION_KEYS) or payload
    races = get_value(overall, ["races", "race_count", "total_races"])
    top3_matches = get_value(overall, ["top3_matches"])
    exact_matches = get_value(overall, ["exact_matches"])
    top3_rate = get_value(overall, ["top3_alignment_rate"])
    exact_rate = get_value(overall, ["exact_alignment_rate"])

    if top3_rate is None:
        top3_rate = calc_rate(top3_matches, races)
    if exact_rate is None:
        exact_rate = calc_rate(exact_matches, races)

    cards = [
        metric_card("対象レース", fmt_count(races)),
        metric_card("TOP3整合率", fmt_percent(top3_rate), f"{fmt_count(top3_matches)} / {fmt_count(races)}"),
        metric_card("完全一致率", fmt_percent(exact_rate), f"{fmt_count(exact_matches)} / {fmt_count(races)}"),
    ]

    return (
        '<section class="section-card">'
        "<h2>AIスコア予測・結果成績</h2>"
        '<div class="section-note">'
        "TOP3整合率＝AIスコア最上位予測の3艇と実着1〜3着が順不同で一致。"
        "完全一致率＝1〜3着の順番まで一致。買い目的中率・回収率とは別指標です。"
        "</div>"
        '<div class="metric-grid">'
        + "".join(cards)
        + "</div>"
        "</section>"
    )


def comparison_html(
    formation_metrics: Dict[str, Any],
    box_metrics: Dict[str, Any],
) -> str:
    rows = [
        ("対象レース", fmt_count(formation_metrics["races"]), fmt_count(box_metrics["races"])),
        ("的中", fmt_count(formation_metrics["hits"]), fmt_count(box_metrics["hits"])),
        ("的中率", fmt_percent(formation_metrics["hit_rate"]), fmt_percent(box_metrics["hit_rate"])),
        ("購入点数", fmt_count(formation_metrics["points"]), fmt_count(box_metrics["points"])),
        ("投資額", fmt_yen(formation_metrics["investment"]), fmt_yen(box_metrics["investment"])),
        ("払戻額", fmt_yen(formation_metrics["returns"]), fmt_yen(box_metrics["returns"])),
        ("損益", fmt_yen(formation_metrics["profit"]), fmt_yen(box_metrics["profit"])),
        ("回収率", fmt_percent(formation_metrics["recovery_rate"]), fmt_percent(box_metrics["recovery_rate"])),
    ]

    body = "".join(
        "<tr>"
        f"<th>{html.escape(label)}</th>"
        f"<td>{html.escape(left)}</td>"
        f"<td>{html.escape(right)}</td>"
        "</tr>"
        for label, left, right in rows
    )

    return (
        '<section class="section-card">'
        "<h2>2戦略比較</h2>"
        '<div class="section-note">'
        "フォーメーションと3艇BOXは別会計です。両方を同時購入した収支ではありません。"
        "</div>"
        '<div class="table-scroll">'
        '<table class="compare-table">'
        "<thead><tr><th>指標</th><th>フォーメーション</th><th>上位3艇BOX</th></tr></thead>"
        f"<tbody>{body}</tbody>"
        "</table>"
        "</div>"
        "</section>"
    )


def type_cards_html(title: str, type_root: Dict[str, Any]) -> str:
    cards = []

    for key, value in type_root.items():
        if not isinstance(value, dict):
            continue

        metrics = strategy_metrics(value)
        cards.append(
            '<div class="type-card">'
            f"<h3>{html.escape(str(key))}</h3>"
            '<div class="type-row"><span>的中</span>'
            f"<b>{fmt_count(metrics['hits'])} / {fmt_count(metrics['races'])}</b></div>"
            '<div class="type-row"><span>的中率</span>'
            f"<b>{fmt_percent(metrics['hit_rate'])}</b></div>"
            '<div class="type-row"><span>回収率</span>'
            f"<b>{fmt_percent(metrics['recovery_rate'])}</b></div>"
            '<div class="type-row"><span>損益</span>'
            f"<b>{fmt_yen(metrics['profit'])}</b></div>"
            "</div>"
        )

    if not cards:
        return ""

    return (
        '<section class="section-card">'
        f"<h2>{html.escape(title)}</h2>"
        '<div class="type-grid">'
        + "".join(cards)
        + "</div>"
        "</section>"
    )


def find_dates(root: Path) -> list[str]:
    dates = set()

    for pattern, prefix in (
        ("*/*/*/formation_simulation_*.json", "formation_simulation_"),
        ("*/*/*/top3_box_simulation_*.json", "top3_box_simulation_"),
        ("*/*/*/ai_score_simulation_*.json", "ai_score_simulation_"),
    ):
        for path in root.glob(pattern):
            date = path.stem.replace(prefix, "")
            if len(date) == 8 and date.isdigit():
                dates.add(date)

    return sorted(dates, reverse=True)


def load_day(root: Path, date: str) -> Dict[str, Dict[str, Any]]:
    folder = root / date[:4] / date[4:6] / date[6:8]
    return {
        "formation": load_json(folder / f"formation_simulation_{date}.json"),
        "box": load_json(folder / f"top3_box_simulation_{date}.json"),
        "ai": load_json(folder / f"ai_score_simulation_{date}.json"),
    }


def overall_metrics(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not payload:
        return strategy_metrics({})

    block = find_dict(payload, FORMATION_KEYS)
    if block is None:
        block = payload
    return strategy_metrics(block)


def history_html(root: Path, dates: list[str], latest: str) -> str:
    items = []

    for date in dates[:30]:
        if date == latest:
            continue

        day = load_day(root, date)
        formation = overall_metrics(day["formation"])
        box = overall_metrics(day["box"])

        if not day["formation"] and not day["box"]:
            continue

        display = f"{date[:4]}/{date[4:6]}/{date[6:8]}"

        items.append(
            "<details>"
            f"<summary>{html.escape(display)}</summary>"
            '<div class="history-strategy">'
            '<div class="history-block"><h3>フォーメーション</h3>'
            '<div class="history-grid">'
            + metric_card("的中", fmt_count(formation["hits"]), fmt_percent(formation["hit_rate"]))
            + metric_card("回収率", fmt_percent(formation["recovery_rate"]))
            + metric_card("損益", fmt_yen(formation["profit"]))
            + "</div></div>"
            '<div class="history-block"><h3>上位3艇BOX</h3>'
            '<div class="history-grid">'
            + metric_card("的中", fmt_count(box["hits"]), fmt_percent(box["hit_rate"]))
            + metric_card("回収率", fmt_percent(box["recovery_rate"]))
            + metric_card("損益", fmt_yen(box["profit"]))
            + "</div></div>"
            "</div>"
            "</details>"
        )

    if not items:
        return ""

    return (
        '<section class="section-card">'
        "<h2>過去成績</h2>"
        '<div class="history-list">'
        + "".join(items)
        + "</div>"
        "</section>"
    )


def signal_ai_24_metrics(root: Path, date: str) -> Dict[str, Any]:
    """Simulated 24-point signal purchase ledger, separate from normal AI.

    Uses saved prediction ranks from signal_ai/latest/details.csv, never
    recomputes picks after seeing actual race outcomes.
    """
    ledger = root / "signal_ai" / "latest" / "details.csv"
    if not ledger.is_file():
        return {}
    with ledger.open(encoding="utf-8-sig", newline="") as f:
        rows = [x for x in csv.DictReader(f) if str(x.get("date")) == date]
    if not rows:
        return {}
    n = len(rows)
    wins = [
        x for x in rows
        if str(x.get("hit24")).strip().lower() in ("true", "1")
    ]
    paid = sum(int(float(x.get("payout") or 0)) for x in wins)
    invested = n * 24 * 100
    return {
        "races": n,
        "hits": len(wins),
        "points": n * 24,
        "investment": invested,
        "returns": paid,
        "profit": paid - invested,
        "hit_rate": len(wins) / n if n else None,
        "recovery_rate": 100 * paid / invested if invested else None,
    }


def build_page(evaluation_root: Path) -> str:
    dates = find_dates(evaluation_root)

    if not dates:
        body = """
        <section class="section-card">
          <h2>結果・成績</h2>
          <div class="empty">まだ評価結果がありません。</div>
        </section>
        """
        display_date = "未集計"

    else:
        latest = dates[0]
        day = load_day(evaluation_root, latest)

        formation = day["formation"]
        box = day["box"]
        ai = day["ai"]

        formation_overall = overall_metrics(formation)
        box_overall = overall_metrics(box)
        ai_overall = overall_metrics(ai)
        signal_ai24 = signal_ai_24_metrics(evaluation_root, latest)

        body_parts = [
            strategy_html(
                "3連単フォーメーション",
                "現在の1着強軸・準軸・混戦ルールによる買い目。各買い目100円。",
                formation_overall,
            ),
            strategy_html(
                "AI上位3艇・3連単BOX",
                "AI順位1〜3位の3艇を6通りの3連単BOXで購入。1レース600円固定。",
                box_overall,
            ),
            strategy_html(
                "通常AIスコア予測（専用シグナルAIとは別集計）",
                "従来の通常AIスコア方式の成績です。風神雷神専用AI24点とは混同しません。",
                ai_overall,
            ),
        ]
        if signal_ai24:
            body_parts.insert(0, strategy_html(
                "風神雷神専用AI・購入24点の結果成績",
                "シグナル発動全レースを24点・各100円で仮想購入。保存済み買い目と実着を照合し、投資・払戻・損益・回収率を24点に統一。",
                signal_ai24,
            ))

        ai_alignment = ai_alignment_html(ai)
        if ai_alignment:
            body_parts.append(ai_alignment)

        formation_types = find_dict(formation, TYPE_KEYS)
        if formation_types:
            section = type_cards_html("フォーメーション方式別成績", formation_types)
            if section:
                body_parts.append(section)

        ai_points = find_dict(ai, ["by_points"])
        if ai_points:
            section = type_cards_html("AI購入点数別・収支シミュレーション", ai_points)
            if section:
                body_parts.append(section)

        ai_prediction_types = find_dict(ai, PREDICTION_TYPE_KEYS)
        if ai_prediction_types:
            section = type_cards_html("AIスコア予測・朝／直前別成績", ai_prediction_types)
            if section:
                body_parts.append(section)

        box_prediction_types = find_dict(box, PREDICTION_TYPE_KEYS)
        if box_prediction_types:
            section = type_cards_html("3艇BOX・予測種別成績", box_prediction_types)
            if section:
                body_parts.append(section)

        past = history_html(evaluation_root, dates, latest)
        if past:
            body_parts.append(past)

        body = "".join(body_parts)
        display_date = f"{latest[:4]}/{latest[4:6]}/{latest[6:8]}"

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">\n<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">\n<meta http-equiv="Pragma" content="no-cache">\n<meta http-equiv="Expires" content="0">
<meta http-equiv="refresh" content="300">
<title>ボートレースAI 結果・成績</title>
<style>
:root {{
  color-scheme: light dark;
  --bg: #cddce8;
  --card: #f4f8fb;
  --text: #111827;
  --muted: #667085;
  --line: #c4d4e0;
  --chip: #dfeaf1;
  --primary: #174f7a;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Sans", "Noto Sans JP", sans-serif;
  background: var(--bg);
  color: var(--text);
}}
.wrap {{ width: min(920px, 100%); margin: 0 auto; padding: 16px 12px 48px; }}
header {{ margin-bottom: 12px; }}
h1 {{ margin: 0; font-size: 23px; }}
.meta {{ margin-top: 6px; color: var(--muted); font-size: 13px; }}
.family-nav {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 14px;
  padding: 6px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--card);
}}
.family-nav a {{
  display: block;
  padding: 11px 8px;
  border-radius: 10px;
  text-align: center;
  text-decoration: none;
  color: var(--text);
  font-weight: 800;
}}
.family-nav a.active {{ background: var(--primary); color: white; }}
.section-card {{
  margin-bottom: 12px;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--card);
}}
.section-card h2 {{ margin: 0 0 8px; font-size: 18px; }}
.section-note {{ margin: 0 0 12px; color: var(--muted); font-size: 12px; line-height: 1.6; }}
.metric-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }}
.metric {{ padding: 12px; border-radius: 12px; background: var(--chip); }}
.metric-label {{ color: var(--muted); font-size: 12px; }}
.metric-value {{ margin-top: 4px; font-size: 21px; font-weight: 900; font-variant-numeric: tabular-nums; }}
.metric-sub {{ margin-top: 3px; color: var(--muted); font-size: 12px; }}
.table-scroll {{ overflow-x: auto; }}
.compare-table {{ width: 100%; border-collapse: collapse; min-width: 560px; }}
.compare-table th, .compare-table td {{ padding: 10px 8px; border-bottom: 1px solid var(--line); text-align: right; font-size: 13px; }}
.compare-table th:first-child, .compare-table td:first-child {{ text-align: left; }}
.compare-table thead th {{ color: var(--muted); font-size: 12px; }}
.type-grid {{ display: grid; gap: 8px; }}
.type-card {{ padding: 12px; border-radius: 12px; background: var(--chip); }}
.type-card h3 {{ margin: 0 0 8px; font-size: 16px; }}
.type-row {{ display: flex; justify-content: space-between; gap: 12px; padding: 4px 0; font-size: 14px; }}
.type-row span {{ color: var(--muted); }}
.history-list details {{ margin-top: 8px; padding: 10px 12px; border-radius: 10px; background: var(--chip); }}
.history-list summary {{ cursor: pointer; font-weight: 800; }}
.history-strategy {{ display: grid; gap: 10px; margin-top: 10px; }}
.history-block h3 {{ margin: 0 0 6px; font-size: 14px; }}
.history-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; }}
.history-grid .metric-value {{ font-size: 17px; }}
.empty {{ padding: 30px 10px; text-align: center; color: var(--muted); }}
footer {{ margin-top: 18px; color: var(--muted); font-size: 12px; line-height: 1.6; }}
@media (max-width: 560px) {{
  .family-nav {{ gap: 6px; padding: 5px; }}
  .family-nav a {{ padding: 10px 4px; font-size: 12px; }}
  .history-grid {{ grid-template-columns: 1fr; }}
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #0f1115;
    --card: #171a21;
    --text: #dfeaf1;
    --muted: #a8b0bd;
    --line: #2a3039;
    --chip: #222833;
    --primary: #3b82f6;
  }}
}}
</style>
</head>
<body>
<div class="wrap">
<header>
<h1>ボートレースAI 結果・成績</h1>
<div class="meta">最新評価：{html.escape(display_date)}</div>
</header>
<nav class="family-nav">
<a href="index.html">最新予想</a>
<a href="results.html" class="active">結果・成績</a>
<a href="analysis.html">AI分析</a>
</nav>
{body}
<footer>
このページは自動更新されます。<br>
フォーメーション・3艇BOX・通常AIスコア・風神雷神専用AI24点は別会計で集計しています。<br>
予測・検証結果は将来の結果を保証するものではありません。
</footer>
</div>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluations-root", default="evaluations")
    parser.add_argument("--output-dir", default="_family_site")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    content = build_page(Path(args.evaluations_root))
    output_path = output_dir / "results.html"
    output_path.write_text(content, encoding="utf-8")

    print("家族向け結果ページ生成: PASS")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
