#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


LABELS = {
    "frame": "枠・コース",
    "official_racer": "選手公式能力",
    "recent_racer": "選手直近成績",
    "racer_venue": "当地・場適性",
    "motor": "モーター",
    "boat_machine": "ボート",
    "grade": "級別",
    "live_beforeinfo": "直前・展示",
}

STAGE_LABELS = {
    "morning": "朝予測の診断",
    "live": "直前予測の診断",
}


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    return (
        data
        if isinstance(data, dict)
        else {}
    )


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

    try:
        return float(
            str(value)
            .replace(",", "")
            .replace("%", "")
            .strip()
        )

    except Exception:
        return None


def fmt_pct(
    value: Any,
) -> str:

    num = to_float(value)

    if num is None:
        return "—"

    return f"{num:.1f}%"


def fmt_num(
    value: Any,
    digits: int = 2,
) -> str:

    num = to_float(value)

    if num is None:
        return "—"

    text = (
        f"{num:.{digits}f}"
    )

    return (
        text
        .rstrip("0")
        .rstrip(".")
    )


def fmt_int(
    value: Any,
) -> str:

    num = to_float(value)

    if num is None:
        return "—"

    return (
        f"{int(round(num)):,}"
    )


def extract_date(
    path: Path,
) -> Optional[str]:

    match = re.search(
        r"score_component_analysis_(\d{8})\.json$",
        path.name,
    )

    if not match:
        return None

    return match.group(1)


def find_analysis_files(
    root: Path,
) -> List[
    Tuple[
        str,
        Path,
    ]
]:

    found = []

    for path in root.glob(
        "*/*/*/score_component_analysis_*.json"
    ):

        date = extract_date(
            path
        )

        if date:
            found.append(
                (
                    date,
                    path,
                )
            )

    return sorted(
        found,
        key=lambda x: x[0],
        reverse=True,
    )


def metric(
    label: str,
    value: str,
    sub: str = "",
) -> str:

    sub_html = ""

    if sub:
        sub_html = (
            '<div class="metric-sub">'
            + html.escape(sub)
            + "</div>"
        )

    return (
        '<div class="metric">'
        f'<div class="metric-label">{html.escape(label)}</div>'
        f'<div class="metric-value">{html.escape(value)}</div>'
        f"{sub_html}"
        "</div>"
    )


def status_badge(
    text: str,
    kind: str = "neutral",
) -> str:

    safe_kind = (
        kind
        if kind
        in {
            "good",
            "warn",
            "neutral",
        }
        else "neutral"
    )

    return (
        f'<span class="badge {safe_kind}">'
        f"{html.escape(text)}"
        "</span>"
    )


def build_notes(
    stage: Dict[str, Any],
) -> List[str]:

    notes = []

    calibration = (
        stage.get(
            "score_calibration"
        )
        or {}
    )

    groups = (
        stage.get("groups")
        or []
    )

    redundancy = (
        stage.get(
            "redundancy"
        )
        or []
    )

    buckets = [
        item
        for item
        in calibration.get(
            "gap_buckets",
            [],
        )
        if isinstance(
            item,
            dict,
        )
    ]

    usable = [
        item
        for item
        in buckets
        if (
            to_float(
                item.get("races")
            )
            or 0
        )
        >= 5
    ]

    if len(usable) >= 2:

        low = usable[0]
        high = usable[-1]

        low_rate = to_float(
            low.get(
                "win_rate_pct"
            )
        )

        high_rate = to_float(
            high.get(
                "win_rate_pct"
            )
        )

        if (
            low_rate is not None
            and high_rate is not None
        ):

            diff = (
                high_rate
                - low_rate
            )

            if diff >= 8:

                notes.append(
                    "この日だけを見ると、"
                    "スコア差が大きい帯の"
                    "1着率は小さい帯より"
                    f"{diff:.1f}pt高く、"
                    "スコア差が自信度として"
                    "機能している可能性があります。"
                )

            elif diff <= -8:

                notes.append(
                    "この日だけを見ると、"
                    "スコア差が大きい帯の"
                    "1着率が小さい帯より"
                    f"{abs(diff):.1f}pt低く、"
                    "「差が大きい＝強軸」の判定は"
                    "再確認が必要です。"
                )

            else:

                notes.append(
                    "この日だけでは、"
                    "スコア差が大きいほど"
                    "1着率が明確に上がる形は"
                    "確認できませんでした。"
                )

    tested = [
        item
        for item
        in groups
        if (
            isinstance(
                item,
                dict,
            )
            and item.get(
                "features_tested"
            )
        )
    ]

    exact = [
        item
        for item
        in tested
        if item.get(
            "exact_component_available"
        )
    ]

    if tested:

        if (
            len(exact)
            == len(tested)
        ):

            notes.append(
                "配点要素は実際の加点内訳で"
                "診断できています。"
            )

        else:

            notes.append(
                "配点要素のうち実際の加点内訳で"
                f"直接診断できたのは"
                f"{len(exact)}/{len(tested)}要素です。"
                "残りは予測前の元データを使った"
                "代理診断です。"
            )

        strongest = max(
            tested,
            key=lambda item:
                to_float(
                    item.get(
                        "best_abs_spearman"
                    )
                )
                or -1,
        )

        strength = to_float(
            strongest.get(
                "best_abs_spearman"
            )
        )

        if strength is not None:

            label = (
                strongest.get(
                    "label"
                )
                or LABELS.get(
                    strongest.get(
                        "group"
                    ),
                    strongest.get(
                        "group",
                        "",
                    ),
                )
            )

            notes.append(
                "この日の要素別診断で"
                "最も着順との関連が大きかったのは"
                f"「{label}」"
                f"（|順位相関|={strength:.3f}）でした。"
            )

    high_overlap = [
        item
        for item
        in redundancy
        if (
            isinstance(
                item,
                dict,
            )
            and item.get(
                "high_overlap_flag"
            )
        )
    ]

    if high_overlap:

        names = []

        for item in (
            high_overlap[:3]
        ):

            names.append(
                f"{item.get('label_a', '要素A')}"
                "×"
                f"{item.get('label_b', '要素B')}"
            )

        notes.append(
            "重複が強めと判定された"
            "組み合わせがあります："
            + "、".join(names)
            + "。二重評価になっていないか"
            "継続確認します。"
        )

    elif redundancy:

        notes.append(
            "現時点では、要素間で"
            "強い重複判定は出ていません。"
        )

    if not notes:

        notes.append(
            "分析データがまだ十分ではありません。"
            "次回以降の答え合わせで蓄積します。"
        )

    return notes


def gap_table(
    stage: Dict[str, Any],
) -> str:

    calibration = (
        stage.get(
            "score_calibration"
        )
        or {}
    )

    buckets = (
        calibration.get(
            "gap_buckets"
        )
        or []
    )

    if not buckets:

        return (
            '<div class="empty-small">'
            "スコア差別データはまだありません。"
            "</div>"
        )

    rows = []

    for row in buckets:

        if not isinstance(
            row,
            dict,
        ):
            continue

        rows.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('gap_bucket', '—')))}</td>"
            f"<td>{fmt_int(row.get('races'))}</td>"
            f"<td>{fmt_pct(row.get('win_rate_pct'))}</td>"
            f"<td>{fmt_pct(row.get('top3_rate_pct'))}</td>"
            f"<td>{fmt_num(row.get('mean_finish'))}</td>"
            "</tr>"
        )

    return (
        '<div class="table-wrap">'
        "<table>"
        "<thead>"
        "<tr>"
        "<th>スコア差</th>"
        "<th>R数</th>"
        "<th>1着率</th>"
        "<th>3着内率</th>"
        "<th>平均着順</th>"
        "</tr>"
        "</thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody>"
        "</table>"
        "</div>"
    )


def group_cards(
    stage: Dict[str, Any],
) -> str:

    groups = (
        stage.get("groups")
        or []
    )

    cards = []

    for item in groups:

        if not isinstance(
            item,
            dict,
        ):
            continue

        label = str(
            item.get("label")
            or LABELS.get(
                item.get("group"),
                item.get(
                    "group",
                    "要素",
                ),
            )
        )

        weight = item.get(
            "current_weight"
        )

        exact = bool(
            item.get(
                "exact_component_available"
            )
        )

        high_rate = to_float(
            item.get(
                "best_high_leader_win_rate_pct"
            )
        )

        low_rate = to_float(
            item.get(
                "best_low_leader_win_rate_pct"
            )
        )

        diff_text = "—"

        if (
            high_rate is not None
            and low_rate is not None
        ):

            diff_text = (
                f"{high_rate - low_rate:+.1f}pt"
            )

        cards.append(
            '<div class="factor-card">'
            '<div class="factor-head">'
            f"<h3>{html.escape(label)}</h3>"
            + status_badge(
                (
                    "直接診断"
                    if exact
                    else "代理指標"
                ),
                (
                    "good"
                    if exact
                    else "warn"
                ),
            )
            + "</div>"
            '<div class="factor-grid">'
            "<div>"
            "<span>現配点</span>"
            f"<b>{html.escape(str(weight) + '点' if weight is not None else '—')}</b>"
            "</div>"
            "<div>"
            "<span>検証項目数</span>"
            f"<b>{fmt_int(item.get('features_tested'))}</b>"
            "</div>"
            "<div>"
            "<span>|順位相関|</span>"
            f"<b>{fmt_num(item.get('best_abs_spearman'), 3)}</b>"
            "</div>"
            "<div>"
            "<span>高値側1着率</span>"
            f"<b>{fmt_pct(item.get('best_high_leader_win_rate_pct'))}</b>"
            "</div>"
            "<div>"
            "<span>低値側1着率</span>"
            f"<b>{fmt_pct(item.get('best_low_leader_win_rate_pct'))}</b>"
            "</div>"
            "<div>"
            "<span>高値−低値</span>"
            f"<b>{html.escape(diff_text)}</b>"
            "</div>"
            "</div>"
            '<div class="feature-name">'
            "代表指標："
            f"{html.escape(str(item.get('best_feature') or '—'))}"
            "</div>"
            "</div>"
        )

    if not cards:

        return (
            '<div class="empty-small">'
            "要素別診断はまだありません。"
            "</div>"
        )

    return "".join(cards)


def redundancy_html(
    stage: Dict[str, Any],
) -> str:

    rows = []

    for item in (
        stage.get(
            "redundancy"
        )
        or []
    ):

        if not isinstance(
            item,
            dict,
        ):
            continue

        flag = bool(
            item.get(
                "high_overlap_flag"
            )
        )

        rows.append(
            '<div class="overlap-row">'
            "<div>"
            f"<b>{html.escape(str(item.get('label_a', '要素A')))}</b>"
            "<span> × </span>"
            f"<b>{html.escape(str(item.get('label_b', '要素B')))}</b>"
            "</div>"
            '<div class="overlap-right">'
            f"<span>相関 {fmt_num(item.get('rank_spearman'), 3)}</span>"
            + status_badge(
                (
                    "重複強め"
                    if flag
                    else "通常"
                ),
                (
                    "warn"
                    if flag
                    else "neutral"
                ),
            )
            + "</div>"
            "</div>"
        )

    if not rows:

        return (
            '<div class="empty-small">'
            "重複チェック結果はまだありません。"
            "</div>"
        )

    return "".join(rows)


def stage_section(
    stage_key: str,
    stage: Dict[str, Any],
) -> str:

    calibration = (
        stage.get(
            "score_calibration"
        )
        or {}
    )

    meta = (
        stage.get("meta")
        or {}
    )

    notes = build_notes(
        stage
    )

    cards = "".join(
        [
            metric(
                "スコア1位の1着率",
                fmt_pct(
                    calibration.get(
                        "top_score_win_rate_pct"
                    )
                ),
                (
                    f"{fmt_int(calibration.get('races'))}R"
                ),
            ),

            metric(
                "スコア1位の3着内率",
                fmt_pct(
                    calibration.get(
                        "top_score_top3_rate_pct"
                    )
                ),
            ),

            metric(
                "スコア1位の平均着順",
                fmt_num(
                    calibration.get(
                        "mean_top_finish"
                    )
                ),
            ),

            metric(
                "総合スコア取得艇数",
                fmt_int(
                    meta.get(
                        "score_rows"
                    )
                ),
                "答え合わせ対象",
            ),
        ]
    )

    note_html = "".join(
        (
            f"<li>{html.escape(note)}</li>"
        )
        for note in notes
    )

    return (
        '<section class="section-card">'
        f"<h2>{html.escape(STAGE_LABELS.get(stage_key, stage_key))}</h2>"
        f'<div class="metric-grid">{cards}</div>'

        '<div class="subsection">'
        "<h3>この日の観察メモ</h3>"
        f'<ul class="notes">{note_html}</ul>'
        "</div>"

        '<div class="subsection">'
        "<h3>1位−2位 スコア差別</h3>"
        + gap_table(stage)
        + "</div>"

        '<div class="subsection">'
        "<h3>配点要素別</h3>"
        '<div class="factor-list">'
        + group_cards(stage)
        + "</div>"
        "</div>"

        '<div class="subsection">'
        "<h3>要素どうしの重複</h3>"
        + redundancy_html(stage)
        + "</div>"

        "</section>"
    )


def history_html(
    files: List[
        Tuple[
            str,
            Path,
        ]
    ],
    latest_date: str,
) -> str:

    rows = []

    for date, path in (
        files[:30]
    ):

        if date == latest_date:
            continue

        data = load_json(
            path
        )

        stage_analysis = (
            data.get(
                "stage_analysis"
            )
            or {}
        )

        morning = (
            (
                stage_analysis.get(
                    "morning"
                )
                or {}
            ).get(
                "score_calibration"
            )
            or {}
        )

        live = (
            (
                stage_analysis.get(
                    "live"
                )
                or {}
            ).get(
                "score_calibration"
            )
            or {}
        )

        display = (
            f"{date[:4]}/"
            f"{date[4:6]}/"
            f"{date[6:8]}"
        )

        rows.append(
            "<details>"
            f"<summary>{html.escape(display)}</summary>"
            '<div class="history-grid">'
            + metric(
                "朝・1着率",
                fmt_pct(
                    morning.get(
                        "top_score_win_rate_pct"
                    )
                ),
            )
            + metric(
                "直前・1着率",
                fmt_pct(
                    live.get(
                        "top_score_win_rate_pct"
                    )
                ),
            )
            + metric(
                "朝・3着内率",
                fmt_pct(
                    morning.get(
                        "top_score_top3_rate_pct"
                    )
                ),
            )
            + metric(
                "直前・3着内率",
                fmt_pct(
                    live.get(
                        "top_score_top3_rate_pct"
                    )
                ),
            )
            + "</div>"
            "</details>"
        )

    if not rows:
        return ""

    return (
        '<section class="section-card">'
        "<h2>過去の分析</h2>"
        '<div class="history-list">'
        + "".join(rows)
        + "</div>"
        "</section>"
    )


def build_page(
    root: Path,
) -> str:

    files = find_analysis_files(
        root
    )

    if not files:

        display_date = (
            "未分析"
        )

        body = (
            '<section class="section-card">'
            "<h2>AI分析</h2>"
            '<div class="empty">'
            "スコア答え合わせが完了すると、"
            "ここに自動表示されます。"
            "</div>"
            "</section>"
        )

    else:

        latest_date, latest_path = (
            files[0]
        )

        data = load_json(
            latest_path
        )

        display_date = (
            f"{latest_date[:4]}/"
            f"{latest_date[4:6]}/"
            f"{latest_date[6:8]}"
        )

        weights = (
            data.get(
                "current_weights"
            )
            or {}
        )

        stage_analysis = (
            data.get(
                "stage_analysis"
            )
            or {}
        )

        weight_cards = []

        for key, value in (
            weights.items()
        ):

            weight_cards.append(
                '<div class="weight-chip">'
                f"<span>{html.escape(LABELS.get(key, str(key)))}</span>"
                f"<b>{html.escape(str(value))}点</b>"
                "</div>"
            )

        body_parts = [
            (
                '<section class="section-card intro-card">'
                "<h2>AI分析について</h2>"
                "<p>"
                "予測時点のスコアと実際の着順を照合し、"
                "現在の配点がどこで機能し、"
                "どこで弱いかを確認するページです。"
                "</p>"
                "<p>"
                "<b>ここでは配点を自動変更しません。</b> "
                "日ごとの診断を蓄積し、"
                "変更は別途判断します。"
                "</p>"
                "</section>"
            ),

            (
                '<section class="section-card">'
                "<h2>現在の配点</h2>"
                '<div class="weight-grid">'
                + "".join(
                    weight_cards
                )
                + "</div>"
                "</section>"
            ),
        ]

        for stage_key in (
            "morning",
            "live",
        ):

            stage = (
                stage_analysis.get(
                    stage_key
                )
            )

            if isinstance(
                stage,
                dict,
            ):

                body_parts.append(
                    stage_section(
                        stage_key,
                        stage,
                    )
                )

        past = history_html(
            files,
            latest_date,
        )

        if past:
            body_parts.append(
                past
            )

        body = "".join(
            body_parts
        )

    return f"""<!doctype html>
<html lang="ja">

<head>

<meta charset="utf-8">

<meta
  name="viewport"
  content="width=device-width, initial-scale=1"
>

<meta
  name="robots"
  content="noindex,nofollow"
>

<meta
  http-equiv="refresh"
  content="300"
>

<title>
  ボートレースAI 分析
</title>

<style>

:root {{
  color-scheme: light dark;

  --bg: #f4f6f8;
  --card: #ffffff;
  --text: #111827;
  --muted: #667085;
  --line: #e5e7eb;
  --chip: #f3f4f6;
  --primary: #2563eb;

  --good-bg: #ecfdf3;
  --good-text: #027a48;

  --warn-bg: #fff7ed;
  --warn-text: #b54708;
}}

* {{
  box-sizing: border-box;
}}

body {{
  margin: 0;

  font-family:
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    "Hiragino Sans",
    "Noto Sans JP",
    sans-serif;

  background: var(--bg);
  color: var(--text);
}}

.wrap {{
  width: min(920px, 100%);
  margin: 0 auto;
  padding: 16px 12px 48px;
}}

header {{
  margin-bottom: 12px;
}}

h1 {{
  margin: 0;
  font-size: 23px;
}}

.meta {{
  margin-top: 6px;

  color: var(--muted);
  font-size: 13px;
}}

.family-nav {{
  display: grid;

  grid-template-columns:
    repeat(3, minmax(0, 1fr));

  gap: 8px;

  margin-bottom: 14px;
  padding: 6px;

  border:
    1px solid
    var(--line);

  border-radius: 14px;

  background: var(--card);
}}

.family-nav a {{
  display: block;

  padding: 11px 6px;

  border-radius: 10px;

  text-align: center;
  text-decoration: none;

  color: var(--text);

  font-size: 14px;
  font-weight: 800;
}}

.family-nav a.active {{
  background: var(--primary);
  color: white;
}}

.section-card {{
  margin-bottom: 12px;
  padding: 14px;

  border:
    1px solid
    var(--line);

  border-radius: 14px;

  background: var(--card);
}}

.section-card h2 {{
  margin: 0 0 12px;

  font-size: 18px;
}}

.section-card h3 {{
  margin: 0 0 10px;

  font-size: 15px;
}}

.intro-card p {{
  margin: 8px 0;

  color: var(--muted);

  line-height: 1.65;
}}

.metric-grid {{
  display: grid;

  grid-template-columns:
    repeat(2, minmax(0, 1fr));

  gap: 8px;
}}

.metric {{
  padding: 12px;

  border-radius: 12px;

  background: var(--chip);
}}

.metric-label {{
  color: var(--muted);

  font-size: 12px;
}}

.metric-value {{
  margin-top: 4px;

  font-size: 21px;
  font-weight: 900;

  font-variant-numeric:
    tabular-nums;
}}

.metric-sub {{
  margin-top: 3px;

  color: var(--muted);

  font-size: 12px;
}}

.weight-grid {{
  display: grid;

  grid-template-columns:
    repeat(2, minmax(0, 1fr));

  gap: 8px;
}}

.weight-chip {{
  display: flex;

  justify-content:
    space-between;

  gap: 8px;

  padding: 11px 12px;

  background: var(--chip);

  border-radius: 12px;
}}

.weight-chip span {{
  color: var(--muted);

  font-size: 13px;
}}

.weight-chip b {{
  font-size: 14px;
}}

.subsection {{
  margin-top: 18px;
}}

.notes {{
  margin: 0;

  padding-left: 20px;

  line-height: 1.7;
}}

.notes li + li {{
  margin-top: 6px;
}}

.table-wrap {{
  overflow-x: auto;

  border:
    1px solid
    var(--line);

  border-radius: 12px;
}}

table {{
  width: 100%;

  border-collapse: collapse;

  min-width: 560px;

  font-size: 13px;
}}

th,
td {{
  padding: 10px 8px;

  border-bottom:
    1px solid
    var(--line);

  text-align: right;

  white-space: nowrap;
}}

th:first-child,
td:first-child {{
  text-align: left;
}}

tr:last-child td {{
  border-bottom: 0;
}}

.factor-list {{
  display: grid;

  gap: 8px;
}}

.factor-card {{
  padding: 12px;

  background: var(--chip);

  border-radius: 12px;
}}

.factor-head {{
  display: flex;

  align-items: center;

  justify-content:
    space-between;

  gap: 8px;
}}

.factor-head h3 {{
  margin: 0;
}}

.badge {{
  display: inline-block;

  padding: 4px 7px;

  border-radius: 999px;

  font-size: 11px;
  font-weight: 800;

  background: var(--chip);
  color: var(--muted);
}}

.badge.good {{
  background: var(--good-bg);
  color: var(--good-text);
}}

.badge.warn {{
  background: var(--warn-bg);
  color: var(--warn-text);
}}

.factor-grid {{
  display: grid;

  grid-template-columns:
    repeat(2, minmax(0, 1fr));

  gap: 7px;

  margin-top: 10px;
}}

.factor-grid div {{
  display: flex;

  justify-content:
    space-between;

  gap: 8px;

  font-size: 13px;
}}

.factor-grid span {{
  color: var(--muted);
}}

.feature-name {{
  margin-top: 9px;

  color: var(--muted);

  font-size: 11px;

  overflow-wrap: anywhere;
}}

.overlap-row {{
  display: flex;

  justify-content:
    space-between;

  align-items: center;

  gap: 8px;

  padding: 10px 0;

  border-bottom:
    1px solid
    var(--line);

  font-size: 13px;
}}

.overlap-row:last-child {{
  border-bottom: 0;
}}

.overlap-right {{
  display: flex;

  align-items: center;

  gap: 7px;

  color: var(--muted);
}}

.history-list details {{
  margin-top: 8px;

  padding: 10px 12px;

  border-radius: 10px;

  background: var(--chip);
}}

.history-list summary {{
  cursor: pointer;

  font-weight: 800;
}}

.history-grid {{
  display: grid;

  grid-template-columns:
    repeat(2, minmax(0, 1fr));

  gap: 6px;

  margin-top: 10px;
}}

.empty {{
  padding: 30px 10px;

  text-align: center;

  color: var(--muted);
}}

.empty-small {{
  padding: 8px 0;

  color: var(--muted);

  font-size: 13px;
}}

footer {{
  margin-top: 18px;

  color: var(--muted);

  font-size: 12px;

  line-height: 1.6;
}}

@media (
  max-width: 560px
) {{

  .family-nav a {{
    padding: 10px 4px;

    font-size: 12px;
  }}

  .factor-grid {{
    grid-template-columns: 1fr;
  }}

  .overlap-row {{
    align-items: flex-start;

    flex-direction: column;
  }}

}}

@media (
  prefers-color-scheme: dark
) {{

  :root {{
    --bg: #0f1115;
    --card: #171a21;
    --text: #f3f4f6;
    --muted: #a8b0bd;
    --line: #2a3039;
    --chip: #222833;
    --primary: #3b82f6;

    --good-bg: #123524;
    --good-text: #75e0a7;

    --warn-bg: #3a2815;
    --warn-text: #fdb022;
  }}

}}

</style>

</head>

<body>

<div class="wrap">

<header>

<h1>
  ボートレースAI 分析
</h1>

<div class="meta">
  最新分析：{html.escape(display_date)}
</div>

</header>

<nav class="family-nav">

<a href="index.html">
  最新予想
</a>

<a href="results.html">
  結果・成績
</a>

<a
  href="analysis.html"
  class="active"
>
  AI分析
</a>

</nav>

{body}

<footer>

分析は過去結果との答え合わせです。
将来の結果を保証するものではありません。

<br>

配点変更は自動実行せず、
複数日分を確認してから判断します。

</footer>

</div>

</body>

</html>
"""


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--evaluations-root",
        default="evaluations",
    )

    parser.add_argument(
        "--output-dir",
        default="_family_site",
    )

    args = parser.parse_args()

    output_dir = Path(
        args.output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        output_dir
        / "analysis.html"
    )

    output_path.write_text(
        build_page(
            Path(
                args.evaluations_root
            )
        ),
        encoding="utf-8",
    )

    print(
        "家族向けAI分析ページ生成: PASS"
    )

    print(
        output_path
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )