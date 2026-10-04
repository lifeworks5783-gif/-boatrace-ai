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

FACTOR_JA = {
    "course_top2": "コース別2連対率",
    "grade": "級別",
    "course_win": "コース別1着率",
    "course_top3": "コース別3連対率",
    "national_top2": "全国2連対率",
    "national_win": "全国1着率",
    "national_top3": "全国3連対率",
    "venue_top3": "当地3連対率",
    "venue_course_top2": "当地コース別2連対率",
    "venue_course_top3": "当地コース別3連対率",
    "venue_course_win": "当地コース別1着率",
    "venue_win": "当地1着率",
    "parts_changed": "部品交換",
    "f_flag": "F（フライング）",
    "tilt": "チルト",
    "course_avg_st": "コース別平均ST",
    "national_avg_st": "全国平均ST",
    "venue_avg_st": "当地平均ST",
    "motor_top2": "モーター2連対率",
    "motor_top3": "モーター3連対率",
    "boat_top2": "ボート2連対率",
    "boat_top3": "ボート3連対率",
    "exhibition_time": "展示タイム",
    "exhibition_st": "展示ST",
    "exhibition_st_f_penalized": "展示ST・F補正後",
    "boat_d90_top2": "ボート直近90日2連対率",
    "boat_d90_top3": "ボート直近90日3連対率",
    "boat_d90_win": "ボート直近90日1着率",
    "motor_d90_top2": "モーター直近90日2連対率",
    "motor_d90_top3": "モーター直近90日3連対率",
    "motor_d90_win": "モーター直近90日1着率",
    "boat_official_top2": "ボート公式2連対率",
    "motor_official_top2": "モーター公式2連対率",
    "motor_d30_win": "モーター直近30日1着率",
    "motor_d30_top2": "モーター直近30日2連対率",
    "motor_d30_top3": "モーター直近30日3連対率",
}

def factor_ja(value: Any) -> str:
    key = str(value or "—")
    return FACTOR_JA.get(key, LABELS.get(key, key))

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


ANALYSIS_LABELS = {
    "course":"枠・コース","official":"公式能力","recent":"直近成績","venue":"当地・場適性",
    "motor":"モーター","boat":"ボート","grade":"級別","series":"今節成績",
    "live_course":"展示進入コース","exST":"展示ST","exTime":"展示タイム",
    "course_x_venue":"コース×場","course_x_official":"コース×公式能力",
    "grade_x_official":"級別×公式能力","official_x_recent":"公式能力×直近成績",
}

def fixed_alignment_table(items):
    rows=[]
    for key,item in items.items():
        if not isinstance(item,dict): continue
        e=item.get("eligible_races") or 0
        def cell(matches_key,pct_key):
            m=item.get(matches_key) or 0
            return f"{fmt_int(m)}/{fmt_int(e)}R = <b>{fmt_pct(item.get(pct_key))}</b>" if e else "—"
        rows.append([
            html.escape(ANALYSIS_LABELS.get(key,key)),
            cell("top3_matches","top3_alignment_pct"),
            cell("exact_matches","exact_alignment_pct"),
            cell("top1_matches","top1_accuracy_pct"),
            fmt_yen(item.get("investment")),
            fmt_yen(item.get("return")),
            fmt_yen(item.get("profit")),
            fmt_pct(item.get("recovery_rate_pct")),
        ])
    return table(["要素","TOP3整合率（3連複型）","完全一致整合率（3連単型）","1着的中率","投資","払戻","収支","回収率"],rows)

def formation_type_table(payload):
    rows=[]
    for key,item in (payload.get("by_formation_type") or {}).items():
        races=item.get("races") or 0;hits=item.get("hits") or 0
        rate=(hits/races*100) if races else None
        rows.append([
            html.escape(str(key)),fmt_int(races),fmt_int(hits),fmt_pct(rate),
            fmt_int(item.get("points")),fmt_yen(item.get("investment")),
            fmt_yen(item.get("return")),fmt_yen(item.get("profit")),
            fmt_pct(item.get("recovery_rate_pct")),
        ])
    return table(["区分","R数","的中","的中率","点数","投資","払戻","収支","回収率"],rows)

def fixed_20261002_html(root: Path) -> str:
    align=load_json(root/"2026"/"10"/"02"/"backfill_alignment"/"alignment_summary_20261002.json")
    formation=load_json(root/"2026"/"10"/"02"/"formation_simulation_20261002.json")
    if not align: return ""
    overall=align.get("overall") or {}
    return (
      '<section class="section-card pdca-hero">'
      '<div class="title-row"><div><h2>10/2 固定定義・AI分析</h2>'
      '<div class="small-meta">TOP3整合率＝3艇順不同一致（3連複型） / 完全一致整合率＝1〜3着の順番まで一致（3連単型） / 1着的中率＝予測1位が実着1着</div></div>'
      + badge("168R検証","good") + '</div>'
      '<div class="metric-grid mini-grid">'
      + metric("従来総合TOP3整合率",fmt_pct(overall.get("alignment_pct")),f"{fmt_int(overall.get('matches'))}/{fmt_int(overall.get('races'))}R")
      + metric("集計期間","10/2開始","本日・7日・累計を今後自動蓄積")
      + '</div>'
      '<p class="section-note">固定定義の蓄積開始が10/2のため、現時点では本日・直近7日・累計は同じ10/2の値です。9/30・10/1の旧表示は変更しません。</p>'
      '</section>'
      '<section class="section-card"><h2>朝・基本データ：各要素3指標</h2>'
      '<p class="section-note">各要素だけで6艇を順位付け。収支はそのTOP3を3連単6点BOX、100円/点で検証。</p>'
      + fixed_alignment_table(align.get("morning_single_components") or {}) + '</section>'
      '<section class="section-card"><h2>直前データ：各要素3指標</h2>'
      '<p class="section-note">展示進入・展示ST・展示タイムを単独評価。取得できないレースは母数から除外。</p>'
      + fixed_alignment_table(align.get("live_single_components") or {}) + '</section>'
      '<section class="section-card"><h2>掛け合わせ分析</h2>'
      '<p class="section-note">現段階は2要素を50:50で合成。コース×場などの相乗効果をTOP3整合率・完全一致整合率・1着的中率とBOX収支で比較。</p>'
      + fixed_alignment_table(align.get("pair_components") or {}) + '</section>'
      '<section class="section-card"><h2>フォーメーション区分別・収支シミュレーション</h2>'
      '<p class="section-note">1着強軸・準軸・混戦を別集計。各買い目100円。</p>'
      + formation_type_table(formation) + '</section>'
    )

def current_pdca_html(root: Path) -> str:
 single=load_json(root/"all_candidate_single_factors"/"summary.json")
 inc=load_json(root/"pdca_incremental_latest"/"summary.json")
 if not single and not inc:return ""
 parts=['<section class="section-card"><h2>最新PDCA：単体要素の日別安定性</h2><p class="section-note">蓄積済みの日付を日別に比較。平均だけでなく最高−最低の振れ幅も確認し、単日の上振れ・下振れを区別します。</p>']
 if single:
  rows=[]
  for x in sorted(single.get("results",[]),key=lambda z:(-(z.get("daily_top3_avg_pct") or -1))):
   bd=x.get("by_date",{})
   rows.append([html.escape(factor_ja(x.get("factor","—"))),*[fmt_pct((bd.get(d) or {}).get("top3_pct")) for d in ["20260930","20261001","20261002","20261003"]],fmt_pct(x.get("daily_top3_avg_pct")),html.escape(f"{fmt_num(x.get('top3_spread_pt'),2)}pt")])
  headers=["要素","9/30","10/1","10/2","10/3","4日平均","振れ幅"]
  raw=table(headers,rows)
  raw=raw.replace('<div class="table-wrap">','<div class="table-wrap pdca-sticky-table">',1)
  parts.append(raw)
 if inc:
  parts.append('<div class="subsection"><h3>AI分析：補正PDCA</h3><p class="section-note">現在の選手基礎B1（コース1着40＋2連対20＋3連対30＋平均ST10）を基準に検証。第1段階では全国2連対率15%が4日すべてで改善し、×→○14件・○→×3件、純改善+11件。これを第2段階の新基準にしています。</p>')
  best={}
  for x in inc.get("stage2_results",[]):
   k=x.get("factor")
   if k not in best or x.get("net_flips",-999)>best[k].get("net_flips",-999):best[k]=x
  rows=[]
  for x in sorted(best.values(),key=lambda z:z.get("net_flips",-999),reverse=True):
   bd=x.get("by_date",{})
   rows.append([html.escape(factor_ja(x.get("factor"))),f"{x.get('weight_pct')}%",*[fmt_pct((bd.get(d) or {}).get("new_pct")) for d in ["20260930","20261001","20261002","20261003"]],fmt_pct(x.get("daily_avg_top3_pct")),str(x.get("total_x_to_o")),str(x.get("total_o_to_x")),f"{x.get('net_flips'):+d}"])
  parts.append(table(["第2補正","重み","9/30","10/1","10/2","10/3","4日平均","×→○","○→×","純改善"],rows))
  parts.append('<div class="policy-note"><b>現時点のAI判断：</b> B1＋全国2連対率15%に対して、今回試した第2補正はすべて純改善が0以下でした。したがって第2補正はまだ追加せず、1週間分まで同じ条件で継続検証します。単日成績だけでは配点変更しません。</div></div>')
 parts.append("</section>")
 return "".join(parts)

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

    current_pdca = current_pdca_html(root)
    if current_pdca:
        body.append(current_pdca)

    fixed = fixed_20261002_html(root)
    if fixed:
        body.append(fixed)

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

    action_panel = """
    <section class="section-card analysis-action-card" id="analysisActionCard">
      <h2>AI分析を実行</h2>
      <p class="section-note">保存済みの予測・結果データを使って、既存のPDCA分析を実行します。配点は自動変更しません。</p>
      <button id="runAiAnalysisButton" class="analysis-action-button" type="button">AI分析を開始</button>
      <div id="runAiAnalysisStatus" class="small-meta">ボタンを押したときだけ分析を開始します。</div>
    </section>
    """

    content = action_panel + "".join(

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

.analysis-action-button {{
  width: 100%;
  min-height: 48px;
  border: 0;
  border-radius: 10px;
  background: var(--primary);
  color: #ffffff;
  font-size: 16px;
  font-weight: 900;
  cursor: pointer;
}}

.analysis-action-button:disabled {{
  opacity: .6;
  cursor: wait;
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

.pdca-sticky-table {{
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}}

.pdca-sticky-table table {{
  width: max-content;
  min-width: 100%;
}}

.pdca-sticky-table th:first-child,
.pdca-sticky-table td:first-child {{
  position: sticky;
  left: 0;
  z-index: 3;
  min-width: 190px;
  background: var(--card);
  box-shadow: 1px 0 0 var(--line);
}}

.pdca-sticky-table th:last-child,
.pdca-sticky-table td:last-child {{
  position: sticky;
  right: 0;
  z-index: 3;
  min-width: 84px;
  background: var(--card);
  box-shadow: -1px 0 0 var(--line);
}}

.pdca-sticky-table th:first-child,
.pdca-sticky-table th:last-child {{
  z-index: 4;
}}

.pdca-sticky-table th:not(:first-child):not(:last-child),
.pdca-sticky-table td:not(:first-child):not(:last-child) {{
  min-width: 82px;
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

<script>
(() => {{
  const button = document.getElementById("runAiAnalysisButton");
  const status = document.getElementById("runAiAnalysisStatus");
  if (!button || !status) return;
  button.addEventListener("click", async () => {{
    if (!window.confirm("本日の全レース終了後のPDCA分析を開始します。よろしいですか？")) return;
    button.disabled = true;
    status.textContent = "AI分析を開始しています…";
    try {{
      const response = await fetch("https://boatrace-family-trigger.onrender.com/trigger-analysis", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: "{{}}"
      }});
      if (response.status !== 202) throw new Error("request_failed");
      status.textContent = "AI分析を受け付けました。完了後、このページに結果が反映されます。";
    }} catch (error) {{
      status.textContent = "AI分析を開始できませんでした。少し時間をおいて再度お試しください。";
      button.disabled = false;
    }}
  }});
}})();
</script>

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