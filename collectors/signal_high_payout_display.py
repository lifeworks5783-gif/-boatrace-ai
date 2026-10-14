"""Read-only presentation of cumulative F0..3 x R0..3 5,000-yen payout frequency.

IMPORTANT: This is P(actual payout >= 5000 | historically recorded combined
Fujin/Raijin levels), NOT today's calibrated race probability, a win rate,
a 24-ticket return estimate, or advice to purchase. Never modify signals.
"""
from __future__ import annotations

import html
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUMMARY = ROOT / "evaluations/signal_payout_rank_distribution/latest/summary.json"
MODEL_VERSION = "fujin_raijin_pipeline_v2_20261011"
MIN_OBSERVED_FOR_PERCENT = 10
MIN_OBSERVED_FOR_STANDARD = 30


def parse_cumulative(payload):
    """Fail closed on missing/inconsistent or untrusted rate denominators."""
    if not isinstance(payload, dict) or payload.get("model_version") != MODEL_VERSION:
        return None
    all_time = (payload.get("periods") or {}).get("all") or {}
    groups = all_time.get("by_signal") or {}
    dates = (payload.get("source_coverage") or {}).get("available_dates") or []
    if len(groups) != 16 or not dates or sorted(dates) != dates:
        return None
    out = {}
    total = 0
    high5_total = 0
    high10_total = 0
    for f in range(4):
        for r in range(4):
            key = f"F{f}R{r}"
            record = groups.get(key)
            if not isinstance(record, dict):
                return None
            try:
                n = int(record["races"])
                high5 = int(record["payout_ge5000"])
                high10 = int(record["payout_ge10000"])
            except (TypeError, ValueError, KeyError):
                return None
            if n < 0 or not 0 <= high10 <= high5 <= n:
                return None
            out[key] = {"n": n, "high5": high5, "high10": high10}
            total += n
            high5_total += high5
            high10_total += high10
    if (total != all_time.get("races")
            or high5_total != all_time.get("payout_ge5000")
            or high10_total != all_time.get("payout_ge10000")):
        return None
    return {"dates": (dates[0], dates[-1]), "groups": out,
            "n": total, "high5": high5_total, "high10": high10_total}


@lru_cache(maxsize=4)
def load_cumulative(path=None):
    source = Path(path) if path is not None else DEFAULT_SUMMARY
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return parse_cumulative(payload)


def freq(count, n):
    return f"{count * 100 / n:.1f}%" if n else "—"


def short_date(date):
    if len(str(date)) == 8 and str(date).isdigit():
        return f"{date[:4]}/{date[4:6]}/{date[6:]}"
    return "不明"


def combined_badge(level_f, level_r, history):
    """One compact badge adjacent to a dual-signal display, never two rates."""
    if not level_f and not level_r:
        return ""
    key = f"F{int(level_f)}R{int(level_r)}"
    if history is None or key not in history.get("groups", {}):
        return ('<span class="signal-high5-history unavailable" '
                'title="風神×雷神の累積集計は未取得です。未取得を0%と解釈しません。">'
                f'<span class="signal-high5-title">{key} 5千円以上実績</span> '
                '<strong>集計待ち</strong></span>')
    row = history["groups"][key]
    n, h5, h10 = row["n"], row["high5"], row["high10"]
    coverage = "〜".join(short_date(x) for x in history["dates"])
    title = (f"風神×雷神 {key}｜保存済み累積 {coverage}｜"
             f"実際の3連単払戻5,000円以上 {h5}/{n}R、"
             f"10,000円以上 {h10}/{n}R。"
             "事後復元を含む過去の実績割合であり、"
             "今回の個別レースの確定予測確率ではありません。"
             "的中率・回収率・購入推奨ではありません。")
    if n < MIN_OBSERVED_FOR_PERCENT:
        count_label = f"母数不足 {n}R"
        cls = "low-sample"
    else:
        count_label = f"{freq(h5,n)}"
        cls = "low-sample" if n < MIN_OBSERVED_FOR_STANDARD else ""
    sample = "・少数参考" if n < MIN_OBSERVED_FOR_STANDARD else ""
    return (
        f'<span class="signal-high5-history {cls}" title="{html.escape(title, quote=True)}"'
        f' data-signal="{key}" data-history-races="{n}"'
        f' data-history-high5="{h5}">'
        f'<span class="signal-high5-title">{key} 5千円以上実績</span> '
        f'<strong>{html.escape(count_label)}</strong>'
        f'<small>（{h5}/{n}R{sample}）</small></span>'
    )


def combination_table(history):
    """Cumulative 16-combination frequency; no ticket/ROI metrics."""
    if history is None:
        return ('<section class="card" id="fujin-raijin-high5-cumulative">'
                '<h2>風神×雷神16組・5千円以上発生実績</h2>'
                '<p class="note">累積データを確認できません。未取得を0%と表示しません。</p></section>')
    dates = "〜".join(short_date(x) for x in history["dates"])
    rows = []
    for f in range(4):
        for r in range(4):
            key = f"F{f}R{r}"
            d = history["groups"][key]
            n, high5, high10 = d["n"], d["high5"], d["high10"]
            if n < MIN_OBSERVED_FOR_PERCENT:
                p5, p10, note = "—", "—", "母数不足（10R未満）"
            else:
                p5, p10 = freq(high5, n), freq(high10, n)
                note = "少数参考値" if n < MIN_OBSERVED_FOR_STANDARD else "実績値"
            rows.append(
                f'<tr data-signal="{key}"><th scope="row">{key}</th>'
                f'<td>{n}R</td><td>{high5}R</td><td><strong>{p5}</strong></td>'
                f'<td>{high10}R</td><td>{p10}</td>'
                f'<td>{html.escape(note)}</td></tr>'
            )
    all_pct = freq(history["high5"], history["n"])
    return (
        '<section class="card" id="fujin-raijin-high5-cumulative">'
        '<h2>風神×雷神16組・5,000円以上発生実績（累計）</h2>'
        f'<p class="note">保存済み評価期間：{dates}／全{history["n"]}R。'
        f'全体の5千円以上発生率は{all_pct}です。'
        '風神と雷神を必ず組み合わせた F0〜3×R0〜3 を表示します。'
        '<strong>「5千円以上率」＝その組み合わせに該当したレースで'
        '実際に3連単払戻が5千円以上となった割合</strong>。'
        'シグナルが捕捉した全高配当の割合（捕捉率）とは異なります。'
        'F0R0は両方未発動の比較対象です。</p>'
        '<div class="table-wrap"><table>'
        '<thead><tr><th>風神×雷神</th><th>対象R</th>'
        '<th>5千円以上R</th><th>5千円以上率</th>'
        '<th>万舟R</th><th>万舟率</th><th>標本</th></tr></thead>'
        '<tbody>' + "".join(rows) + '</tbody></table></div>'
        '<p class="note">5千円以上率は過去の条件付き実績割合であり、'
        '今日の各レースの確定確率や購入推奨ではありません。'
        '10R未満は割合非表示、30R未満は少数参考値。'
        '過去再構成データが含まれるため、その時点で事前発動していたことを'
        'すべて証明したものではありません。'
        '今後の新規照合データが累計に追加されると数値が更新されます。</p>'
        '</section>'
    )
