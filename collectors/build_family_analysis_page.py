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

LIVE_LABELS = {

    "exhibition_time": "展示タイム",

    "exhibition_st": "展示ST",

    "exhibition_f": "展示F",

    "course_changed": "展示進入変化",

    "exhibition_course": "展示進入",

    "wind_speed": "風速",

    "wind_direction": "風向",

    "wave_height": "波高",

}

def load_json(path: Path) -> Dict[str, Any]:

    if not path.exists():

        return {}

    try:

        data = json.loads(

            path.read_text(

                encoding="utf-8"

            )

        )

    except Exception:

        return {}

    return (

        data

        if isinstance(

            data,

            dict,

        )

        else {}

    )

def num(

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

            .replace(

                ",",

                "",

            )

            .replace(

                "%",

                "",

            )

            .replace(

                "円",

                "",

            )

            .strip()

        )

    except Exception:

        return None

def fmt_pct(

    value: Any,

) -> str:

    value = num(

        value

    )

    if value is None:

        return "—"

    return (

        f"{value:.1f}%"

    )

def fmt_num(

    value: Any,

    digits: int = 2,

) -> str:

    value = num(

        value

    )

    if value is None:

        return "—"

    return (

        f"{value:.{digits}f}"

        .rstrip("0")

        .rstrip(".")

    )

def fmt_int(

    value: Any,

) -> str:

    value = num(

        value

    )

    if value is None:

        return "—"

    return (

        f"{int(round(value)):,}"

    )

def fmt_yen(

    value: Any,

) -> str:

    value = num(

        value

    )

    if value is None:

        return "—"

    return (

        f"{int(round(value)):,}円"

    )

def date_text(

    value: str,

) -> str:

    value = str(

        value or ""

    )

    if (

        len(value) == 8

        and value.isdigit()

    ):

        return (

            f"{value[:4]}/"

            f"{value[4:6]}/"

            f"{value[6:8]}"

        )

    return (

        value

        or "未分析"

    )

def find_analysis_files(

    root: Path,

) -> List[

    Tuple[

        str,

        Path,

    ]

]:

    found: List[

        Tuple[

            str,

            Path,

        ]

    ] = []

    pattern = re.compile(

        r"score_component_analysis_(\d{8})\.json$"

    )

    for path in root.glob(

        "*/*/*/score_component_analysis_*.json"

    ):

        match = pattern.search(

            path.name

        )

        if match:

            found.append(

                (

                    match.group(

                        1

                    ),

                    path,

                )

            )

    return sorted(

        found,

        key=lambda item:

            item[0],

        reverse=True,

    )

def metric(

    label: str,

    value: str,

    sub: str = "",

) -> str:

    sub_html = (

        (

            '<div class="metric-sub">'

            f"{html.escape(sub)}"

            "</div>"

        )

        if sub

        else ""

    )

    return (

        '<div class="metric">'

        f'<div class="metric-label">{html.escape(label)}</div>'

        f'<div class="metric-value">{html.escape(value)}</div>'

        f"{sub_html}"

        "</div>"

    )

def badge(

    text: str,

    kind: str = "neutral",

) -> str:

    if kind not in {

        "good",

        "warn",

        "neutral",

    }:

        kind = "neutral"

    return (

        f'<span class="badge {kind}">'

        f"{html.escape(text)}"

        "</span>"

    )

def table(

    headers: List[str],

    rows: List[

        List[str]

    ],

) -> str:

    if not rows:

        return (

            '<div class="empty-small">'

            "データはまだありません。"

            "</div>"

        )

    head = "".join(

        f"<th>{html.escape(value)}</th>"

        for value

        in headers

    )

    body = "".join(

        (

            "<tr>"

            + "".join(

                f"<td>{value}</td>"

                for value

                in row

            )

            + "</tr>"

        )

        for row

        in rows

    )

    return (

        '<div class="table-wrap">'

        "<table>"

        f"<thead><tr>{head}</tr></thead>"

        f"<tbody>{body}</tbody>"

        "</table>"

        "</div>"

    )

def strategy_html(

    pdca: Dict[

        str,

        Any,

    ],

) -> str:

    strategy = (

        pdca.get(

            "strategy"

        )

        or {}

    )

    formation = (

        (

            strategy.get(

                "formation"

            )

            or {}

        )

        .get(

            "overall"

        )

        or {}

    )

    box = (

        (

            strategy.get(

                "top3_box"

            )

            or {}

        )

        .get(

            "overall"

        )

        or {}

    )

    rows = [

        [

            "対象レース",

            fmt_int(

                formation.get(

                    "races"

                )

            ),

            fmt_int(

                box.get(

                    "races"

                )

            ),

        ],

        [

            "的中",

            fmt_int(

                formation.get(

                    "hits"

                )

            ),

            fmt_int(

                box.get(

                    "hits"

                )

            ),

        ],

        [

            "的中率",

            fmt_pct(

                formation.get(

                    "hit_rate_pct"

                )

            ),

            fmt_pct(

                box.get(

                    "hit_rate_pct"

                )

            ),

        ],

        [

            "投資額",

            fmt_yen(

                formation.get(

                    "investment"

                )

            ),

            fmt_yen(

                box.get(

                    "investment"

                )

            ),

        ],

        [

            "払戻額",

            fmt_yen(

                formation.get(

                    "return"

                )

            ),

            fmt_yen(

                box.get(

                    "return"

                )

            ),

        ],

        [

            "損益",

            fmt_yen(

                formation.get(

                    "profit"

                )

            ),

            fmt_yen(

                box.get(

                    "profit"

                )

            ),

        ],

        [

            "回収率",

            fmt_pct(

                formation.get(

                    "recovery_rate_pct"

                )

            ),

            fmt_pct(

                box.get(

                    "recovery_rate_pct"

                )

            ),

        ],

    ]

    return table(

        [

            "指標",

            "フォーメーション",

            "上位3艇BOX",

        ],

        [

            [

                html.escape(

                    value

                )

                for value

                in row

            ]

            for row

            in rows

        ],

    )

def quality_html(

    pdca: Dict[

        str,

        Any,

    ],

) -> str:

    quality = (

        pdca.get(

            "prediction_quality"

        )

        or {}

    )

    morning = (

        quality.get(

            "morning"

        )

        or {}

    )

    live = (

        quality.get(

            "live"

        )

        or {}

    )

    rows = [

        [

            "朝予測",

            fmt_int(

                morning.get(

                    "races"

                )

            ),

            fmt_pct(

                morning.get(

                    "top1_win_rate_pct"

                )

            ),

            fmt_pct(

                morning.get(

                    "winner_in_top2_rate_pct"

                )

            ),

            fmt_pct(

                morning.get(

                    "winner_in_top3_rate_pct"

                )

            ),

        ],

        [

            "直前予測",

            fmt_int(

                live.get(

                    "races"

                )

            ),

            fmt_pct(

                live.get(

                    "top1_win_rate_pct"

                )

            ),

            fmt_pct(

                live.get(

                    "winner_in_top2_rate_pct"

                )

            ),

            fmt_pct(

                live.get(

                    "winner_in_top3_rate_pct"

                )

            ),

        ],

    ]

    return table(

        [

            "段階",

            "評価R",

            "1着率",

            "勝者TOP2率",

            "勝者TOP3率",

        ],

        [

            [

                html.escape(

                    value

                )

                for value

                in row

            ]

            for row

            in rows

        ],

    )

def top10_html(

    pdca: Dict[

        str,

        Any,

    ],

) -> str:

    items = (

        pdca.get(

            "feature_consistency_top10"

        )

        or []

    )

    rows: List[

        List[str]

    ] = []

    for (

        index,

        item,

    ) in enumerate(

        items[:10],

        start=1,

    ):

        if not isinstance(

            item,

            dict,

        ):

            continue

        stage = (

            "朝"

            if item.get(

                "stage"

            )

            == "morning"

            else "直前"

        )

        label = (

            item.get(

                "label"

            )

            or LABELS.get(

                item.get(

                    "group"

                ),

                item.get(

                    "group",

                    "—",

                ),

            )

        )

        rows.append(

            [

                str(

                    index

                ),

                html.escape(

                    stage

                ),

                html.escape(

                    str(

                        label

                    )

                ),

                fmt_int(

                    item.get(

                        "days_observed"

                    )

                ),

                fmt_int(

                    item.get(

                        "total_races"

                    )

                ),

                fmt_num(

                    item.get(

                        "avg_abs_spearman"

                    ),

                    3,

                ),

                fmt_pct(

                    item.get(

                        "avg_high_leader_win_rate_pct"

                    )

                ),

            ]

        )

    return table(

        [

            "順位",

            "段階",

            "要素",

            "日数",

            "R数",

            "|順位相関|",

            "高値首位1着率",

        ],

        rows,

    )

def live_factor_html(

    pdca: Dict[

        str,

        Any,

    ],

) -> str:

    summary = (

        pdca.get(

            "live_factor_summary"

        )

        or {}

    )

    factors = (

        summary.get(

            "factors"

        )

        or {}

    )

    cards: List[str] = []

    for key in (

        "exhibition_time",

        "exhibition_st",

    ):

        item = (

            factors.get(

                key

            )

            or {}

        )

        if not item:

            continue

        cards.append(

            '<div class="factor-card">'

            '<div class="factor-head">'

            f"<h3>{html.escape(LIVE_LABELS.get(key, key))}</h3>"

            + badge(

                f"{fmt_int(item.get('races'))}R"

            )

            + "</div>"

            '<div class="factor-grid">'

            "<div>"

            "<span>最良艇1着率</span>"

            f"<b>{fmt_pct(item.get('best_win_rate_pct'))}</b>"

            "</div>"

            "<div>"

            "<span>最良艇3着内率</span>"

            f"<b>{fmt_pct(item.get('best_top3_rate_pct'))}</b>"

            "</div>"

            "<div>"

            "<span>最悪艇1着率</span>"

            f"<b>{fmt_pct(item.get('worst_win_rate_pct'))}</b>"

            "</div>"

            "</div>"

            "</div>"

        )

    for key in (

        "exhibition_f",

        "course_changed",

    ):

        item = (

            factors.get(

                key

            )

            or {}

        )

        if not item:

            continue

        cards.append(

            '<div class="factor-card">'

            '<div class="factor-head">'

            f"<h3>{html.escape(LIVE_LABELS.get(key, key))}</h3>"

            + badge(

                f"{fmt_int(item.get('boats'))}艇"

            )

            + "</div>"

            '<div class="factor-grid">'

            "<div>"

            "<span>該当艇数</span>"

            f"<b>{fmt_int(item.get('flagged_boats'))}</b>"

            "</div>"

            "<div>"

            "<span>集計日数</span>"

            f"<b>{fmt_int(item.get('days'))}</b>"

            "</div>"

            "</div>"

            "</div>"

        )

    if not cards:

        return (

            '<div class="empty-small">'

            "直前要素の累計データはまだありません。"

            "</div>"

        )

    return (

        '<div class="factor-list">'

        + "".join(

            cards

        )

        + "</div>"

    )

def weight_search_html(

    pdca: Dict[

        str,

        Any,

    ],

) -> str:

    summary = (

        pdca.get(

            "live_factor_summary"

        )

        or {}

    )

    pooled = (

        summary.get(

            "pooled_weight_search"

        )

        or {}

    )

    if not pooled.get(

        "available"

    ):

        reason = (

            pooled.get(

                "reason"

            )

            or "データ不足"

        )

        return (

            '<div class="empty-small">'

            "まだ重み探索できません："

            + html.escape(

                str(

                    reason

                )

            )

            + "</div>"

        )

    cards = (

        '<div class="metric-grid mini-grid">'

        + metric(

            "比較レース",

            fmt_int(

                pooled.get(

                    "races"

                )

            ),

        )

        + metric(

            "ベース1着率",

            fmt_pct(

                pooled.get(

                    "baseline_top1_accuracy_pct"

                )

            ),

        )

        + "</div>"

    )

    rows: List[

        List[str]

    ] = []

    for item in (

        pooled.get(

            "best_candidates"

        )

        or []

    )[:10]:

        if not isinstance(

            item,

            dict,

        ):

            continue

        rows.append(

            [

                fmt_int(

                    item.get(

                        "exhibition_time_weight"

                    )

                ),

                fmt_int(

                    item.get(

                        "exhibition_st_weight"

                    )

                ),

                fmt_int(

                    item.get(

                        "f_penalty"

                    )

                ),

                fmt_pct(

                    item.get(

                        "top1_accuracy_pct"

                    )

                ),

                html.escape(

                    f"{fmt_num(item.get('improvement_vs_baseline_pt'), 1)}pt"

                ),

            ]

        )

    return (

        cards

        + table(

            [

                "展示タイム",

                "展示ST",

                "F減点",

                "1着率",

                "改善",

            ],

            rows,

        )

    )

def missing_html(

    pdca: Dict[

        str,

        Any,

    ],

) -> str:

    rows: List[

        List[str]

    ] = []

    for item in (

        pdca.get(

            "missing_data"

        )

        or []

    ):

        if not isinstance(

            item,

            dict,

        ):

            continue

        priority = str(

            item.get(

                "priority"

            )

            or "—"

        )

        kind = (

            "good"

            if priority

            == "良好"

            else (

                "warn"

                if priority

                in {

                    "要改善",

                    "最優先",

                }

                else "neutral"

            )

        )

        factor = str(

            item.get(

                "factor"

            )

            or "—"

        )

        label = (

            LIVE_LABELS.get(

                factor,

                factor,

            )

        )

        rows.append(

            [

                html.escape(

                    label

                ),

                fmt_int(

                    item.get(

                        "coverage"

                    )

                ),

                fmt_pct(

                    item.get(

                        "coverage_rate_pct"

                    )

                ),

                badge(

                    priority,

                    kind,

                ),

            ]

        )

    return table(

        [

            "項目",

            "取得数",

            "取得率",

            "優先度",

        ],

        rows,

    )

def pdca_html(

    pdca: Dict[

        str,

        Any,

    ],

) -> str:

    if not pdca:

        return ""

    target = date_text(

        str(

            pdca.get(

                "target_date"

            )

            or ""

        )

    )

    days = fmt_int(

        pdca.get(

            "window_days"

        )

    )

    available = fmt_int(

        pdca.get(

            "available_day_count"

        )

    )

    policy = (

        pdca.get(

            "policy"

        )

        or {}

    )

    note = str(

        policy.get(

            "note"

        )

        or ""

    )

    return (

        '<section class="section-card pdca-hero">'

        '<div class="title-row">'

        "<div>"

        "<h2>直近7日PDCA</h2>"

        '<div class="small-meta">'

        f"基準日：{html.escape(target)} / "

        f"対象：{html.escape(days)}日 / "

        f"データあり：{html.escape(available)}日"

        "</div>"

        "</div>"

        + badge(

            "自動集計",

            "good",

        )

        + "</div>"

        "<p>"

        "フォーメーションと上位3艇BOXを別会計で比較し、"

        "予測精度・特徴量・直前要素・不足データを"

        "まとめて確認します。"

        "</p>"

        + (

            (

                '<div class="policy-note">'

                f"{html.escape(note)}"

                "</div>"

            )

            if note

            else ""

        )

        + "</section>"

        '<section class="section-card">'

        "<h2>買い方2パターンの累計</h2>"

        + strategy_html(

            pdca

        )

        + "</section>"

        '<section class="section-card">'

        "<h2>朝予測・直前予測の累計精度</h2>"

        + quality_html(

            pdca

        )

        + "</section>"

        '<section class="section-card">'

        "<h2>整合性TOP10</h2>"

        '<p class="section-note">'

        "TOP10外の要素も削除せず、"

        "全件を毎日再評価しています。"

        "</p>"

        + top10_html(

            pdca

        )

        + "</section>"

        '<section class="section-card">'

        "<h2>直前要素の累計</h2>"

        + live_factor_html(

            pdca

        )

        + '<div class="subsection">'

        "<h3>直前重み探索</h3>"

        '<p class="section-note">'

        "候補探索のみです。"

        "本番配点は自動変更しません。"

        "</p>"

        + weight_search_html(

            pdca

        )

        + "</div>"

        "</section>"

        '<section class="section-card">'

        "<h2>不足データ・収集状況</h2>"

        + missing_html(

            pdca

        )

        + "</section>"

    )

def gap_html(

    stage: Dict[

        str,

        Any,

    ],

) -> str:

    calibration = (

        stage.get(

            "score_calibration"

        )

        or {}

    )

    rows: List[

        List[str]

    ] = []

    for item in (

        calibration.get(

            "gap_buckets"

        )

        or []

    ):

        if not isinstance(

            item,

            dict,

        ):

            continue

        rows.append(

            [

                html.escape(

                    str(

                        item.get(

                            "gap_bucket"

                        )

                        or "—"

                    )

                ),

                fmt_int(

                    item.get(

                        "races"

                    )

                ),

                fmt_pct(

                    item.get(

                        "win_rate_pct"

                    )

                ),

                fmt_pct(

                    item.get(

                        "top3_rate_pct"

                    )

                ),

                fmt_num(

                    item.get(

                        "mean_finish"

                    )

                ),

            ]

        )

    return table(

        [

            "スコア差",

            "R数",

            "1着率",

            "3着内率",

            "平均着順",

        ],

        rows,

    )

def groups_html(

    stage: Dict[

        str,

        Any,

    ],

) -> str:

    cards: List[str] = []

    for item in (

        stage.get(

            "groups"

        )

        or []

    ):

        if not isinstance(

            item,

            dict,

        ):

            continue

        label = (

            item.get(

                "label"

            )

            or LABELS.get(

                item.get(

                    "group"

                ),

                item.get(

                    "group",

                    "要素",

                ),

            )

        )

        weight = (

            item.get(

                "current_weight"

            )

        )

        exact = bool(

            item.get(

                "exact_component_available"

            )

        )

        cards.append(

            '<div class="factor-card">'

            '<div class="factor-head">'

            f"<h3>{html.escape(str(label))}</h3>"

            + badge(

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

    return (

        '<div class="factor-list">'

        + "".join(

            cards

        )

        + "</div>"

    )

def stage_html(

    title: str,

    stage: Dict[

        str,

        Any,

    ],

) -> str:

    calibration = (

        stage.get(

            "score_calibration"

        )

        or {}

    )

    meta = (

        stage.get(

            "meta"

        )

        or {}

    )

    metrics = (

        '<div class="metric-grid">'

        + metric(

            "スコア1位の1着率",

            fmt_pct(

                calibration.get(

                    "top_score_win_rate_pct"

                )

            ),

            (

                f"{fmt_int(calibration.get('races'))}R"

            ),

        )

        + metric(

            "スコア1位の3着内率",

            fmt_pct(

                calibration.get(

                    "top_score_top3_rate_pct"

                )

            ),

        )

        + metric(

            "スコア1位の平均着順",

            fmt_num(

                calibration.get(

                    "mean_top_finish"

                )

            ),

        )

        + metric(

            "総合スコア取得艇数",

            fmt_int(

                meta.get(

                    "score_rows"

                )

            ),

            "答え合わせ対象",

        )

        + "</div>"

    )

    return (

        '<section class="section-card">'

        f"<h2>{html.escape(title)}</h2>"

        + metrics

        + '<div class="subsection">'

        "<h3>1位−2位 スコア差別</h3>"

        + gap_html(

            stage

        )

        + "</div>"

        '<div class="subsection">'

        "<h3>配点要素別</h3>"

        + groups_html(

            stage

        )

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

    latest: str,

) -> str:

    rows: List[str] = []

    for (

        date,

        path,

    ) in files[:30]:

        if date == latest:

            continue

        data = load_json(

            path

        )

        stages = (

            data.get(

                "stage_analysis"

            )

            or {}

        )

        morning = (

            (

                stages.get(

                    "morning"

                )

                or {}

            )

            .get(

                "score_calibration"

            )

            or {}

        )

        live = (

            (

                stages.get(

                    "live"

                )

                or {}

            )

            .get(

                "score_calibration"

            )

            or {}

        )

        rows.append(

            "<details>"

            f"<summary>{html.escape(date_text(date))}</summary>"

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

        + "".join(

            rows

        )

        + "</div>"

        "</section>"

    )

def build_page(

    root: Path,

) -> str:

    files = (

        find_analysis_files(

            root

        )

    )

    pdca = load_json(

        root

        / "latest_pdca.json"

    )

    latest_date = ""

    latest_data: Dict[

        str,

        Any,

    ] = {}

    if files:

        (

            latest_date,

            latest_path,

        ) = files[0]

        latest_data = (

            load_json(

                latest_path

            )

        )

    elif pdca:

        latest_date = str(

            pdca.get(

                "target_date"

            )

            or ""

        )

    body: List[str] = []

    if pdca:

        body.append(

            pdca_html(

                pdca

            )

        )

    if latest_data:

        weights = (

            latest_data.get(

                "current_weights"

            )

            or {}

        )

        stages = (

            latest_data.get(

                "stage_analysis"

            )

            or {}

        )

        body.append(

            '<section class="section-card intro-card">'

            "<h2>日次のAI分析</h2>"

            "<p>"

            "予測時点のスコアと実際の着順を照合し、"

            "現在の配点がどこで機能し、"

            "どこで弱いかを確認します。"

            "</p>"

            "<p>"

            "<b>配点は自動変更しません。</b> "

            "日次診断と直近PDCAを"

            "蓄積してから判断します。"

            "</p>"

            "</section>"

        )

        if weights:

            chips = "".join(

                (

                    '<div class="weight-chip">'

                    f"<span>{html.escape(LABELS.get(key, str(key)))}</span>"

                    f"<b>{html.escape(str(value))}点</b>"

                    "</div>"

                )

                for (

                    key,

                    value,

                )

                in weights.items()

            )

            body.append(

                '<section class="section-card">'

                "<h2>現在の配点</h2>"

                f'<div class="weight-grid">{chips}</div>'

                "</section>"

            )

        morning = (

            stages.get(

                "morning"

            )

        )

        if isinstance(

            morning,

            dict,

        ):

            body.append(

                stage_html(

                    "朝予測の診断",

                    morning,

                )

            )

        live = (

            stages.get(

                "live"

            )

        )

        if isinstance(

            live,

            dict,

        ):

            body.append(

                stage_html(

                    "直前予測の診断",

                    live,

                )

            )

        past = (

            history_html(

                files,

                latest_date,

            )

        )

        if past:

            body.append(

                past

            )

    if not body:

        body.append(

            '<section class="section-card">'

            "<h2>AI分析</h2>"

            '<div class="empty">'

            "分析データができると"

            "ここに自動表示されます。"

            "</div>"

            "</section>"

        )

    content = "".join(

        body

    )

    latest_text = (

        date_text(

            latest_date

        )

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

.meta,

.small-meta {{

  margin-top: 6px;

  color: var(--muted);

  font-size: 12px;

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

.section-note,

.pdca-hero p,

.intro-card p {{

  margin: 8px 0;

  color: var(--muted);

  line-height: 1.65;

}}

.title-row {{

  display: flex;

  justify-content:

    space-between;

  align-items:

    flex-start;

  gap: 10px;

}}

.title-row h2 {{

  margin-bottom: 4px;

}}

.policy-note {{

  margin-top: 10px;

  padding: 10px 12px;

  border-radius: 10px;

  background: var(--chip);

  color: var(--muted);

  font-size: 12px;

  line-height: 1.6;

}}

.metric-grid {{

  display: grid;

  grid-template-columns:

    repeat(2, minmax(0, 1fr));

  gap: 8px;

}}

.mini-grid {{

  margin-bottom: 10px;

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

.subsection {{

  margin-top: 18px;

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

  justify-content:

    space-between;

  align-items: center;

  gap: 8px;

}}

.factor-head h3 {{

  margin: 0;

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

.factor-grid span,

.feature-name {{

  color: var(--muted);

}}

.feature-name {{

  margin-top: 9px;

  font-size: 11px;

  overflow-wrap: anywhere;

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

  .title-row {{

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

  最新分析：{html.escape(latest_text)}

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

{content}

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

    parser = (

        argparse.ArgumentParser()

    )

    parser.add_argument(

        "--evaluations-root",

        default="evaluations",

    )

    parser.add_argument(

        "--output-dir",

        default="_family_site",

    )

    args = (

        parser.parse_args()

    )

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