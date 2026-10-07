#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any, Dict


def load_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        x = json.loads(path.read_text(encoding="utf-8"))
        return x if isinstance(x, dict) else {}
    except Exception:
        return {}


def n(v, digits=2):
    if v is None:
        return "—"
    try:
        x = float(v)
        if digits == 0:
            return f"{int(round(x)):,}"
        return f"{x:.{digits}f}".rstrip("0").rstrip(".")
    except Exception:
        return html.escape(str(v))


def pct(v):
    return "—" if v is None else f"{n(v,2)}%"


def yen(v):
    return "—" if v is None else f"{n(v,0)}円"


def card(label, value, sub=""):
    return (
        '<div class="metric"><div class="label">'
        + html.escape(label)
        + '</div><div class="value">'
        + html.escape(value)
        + '</div>'
        + (f'<div class="sub">{html.escape(sub)}</div>' if sub else "")
        + '</div>'
    )


def combo_table(backtest):
    total = backtest.get("total") or {}
    combos = total.get("combinations") or {}
    rows = []
    for f in range(4):
        for r in range(4):
            x = combos.get(f"F{f}_R{r}") or {}
            if not x:
                continue
            rows.append(
                "<tr>"
                f"<td>{html.escape(str(x.get('label') or f'F{f}×R{r}'))}</td>"
                f"<td>{n(x.get('races'),0)}</td>"
                f"<td>{pct(x.get('activation_rate_pct'))}</td>"
                f"<td>{n(x.get('payout_5000plus'),0)}</td>"
                f"<td>{pct(x.get('payout_5000plus_rate_pct'))}</td>"
                f"<td>{n(x.get('manshu'),0)}</td>"
                f"<td>{pct(x.get('manshu_rate_pct'))}</td>"
                f"<td>{yen(x.get('avg_payout'))}</td>"
                "</tr>"
            )
    if not rows:
        return '<div class="empty">組み合わせ集計はまだありません。</div>'
    return (
        '<div class="table-wrap"><table><thead><tr>'
        '<th>組み合わせ</th><th>R数</th><th>全体比</th><th>5千円以上</th><th>5千円以上率</th>'
        '<th>万舟</th><th>万舟率</th><th>平均払戻</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'
    )


def current_signal_ai_table(signal_ai):
    groups = signal_ai.get("by_signal") or {}
    rows = []
    for f in range(4):
        for r in range(4):
            key = f"F{f}R{r}"
            x = groups.get(key) or {}
            if not x:
                continue
            p5 = x.get("payout_5000plus") or {}
            man = x.get("manshu") or {}
            cuts = x.get("rank_cut_hit_rate_pct") or {}
            rows.append(
                "<tr>"
                f"<td>{html.escape(key)}</td>"
                f"<td>{html.escape(str(x.get('rule_text') or '—'))}</td>"
                f"<td>{n(x.get('races'),0)}</td>"
                f"<td>{pct(x.get('hit_rate24_pct'))}</td>"
                f"<td>{n(p5.get('hits24'),0)}/{n(p5.get('races'),0)} ({pct(p5.get('hit_rate24_pct'))})</td>"
                f"<td>{n(man.get('hits24'),0)}/{n(man.get('races'),0)} ({pct(man.get('hit_rate24_pct'))})</td>"
                f"<td>{pct(x.get('roi24_pct'))}</td>"
                f"<td>{pct(cuts.get('6'))}</td>"
                f"<td>{pct(cuts.get('12'))}</td>"
                f"<td>{pct(cuts.get('18'))}</td>"
                f"<td>{pct(cuts.get('24'))}</td>"
                f"<td>{n((x.get('actual_combo_rank') or {}).get('median'))}</td>"
                "</tr>"
            )
    if not rows:
        return '<div class="empty">現行シグナルAI補正の累積結果はまだありません。</div>'
    return (
        '<div class="table-wrap"><table><thead><tr>'
        '<th>シグナル</th><th>採用中補正</th><th>R数</th><th>24点的中率</th>'
        '<th>5千円以上</th><th>万舟</th><th>24点ROI</th>'
        '<th>上位6内</th><th>上位12内</th><th>上位18内</th><th>上位24内</th><th>実着順位中央値</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'
    )


def current_signal_ai_metrics(signal_ai):
    overall = signal_ai.get("overall_if_all_signals_bought24") or {}
    p5 = overall.get("payout_5000plus") or {}
    man = overall.get("manshu") or {}
    policy = signal_ai.get("decision_policy") or {}
    return (
        card("現行補正の評価R", n(overall.get("races"),0), f"{n(signal_ai.get('source_date_count'),0)}日分")
        + card("上位24点的中率", pct(overall.get("hit_rate24_pct")), f"{n(overall.get('hits24'),0)}的中")
        + card("5千円以上的中率", pct(p5.get("hit_rate24_pct")), f"{n(p5.get('hits24'),0)}/{n(p5.get('races'),0)}")
        + card("万舟的中率", pct(man.get("hit_rate24_pct")), f"{n(man.get('hits24'),0)}/{n(man.get('races'),0)}")
        + card("全シグナル24点ROI", pct(overall.get("roi24_pct")), "全シグナルを仮に購入した比較値")
        + card("買い/見送り", "学習中" if not policy.get("purchase_decision_active") else "稼働中", "現時点は全シグナル24候補を保存")
    )


def best_buff(buff):
    top = buff.get("top40_selected_on_training") or []
    if not top:
        return '<div class="empty">バフ・デバフ探索結果はまだありません。</div>'
    rows = []
    for idx, x in enumerate(top[:10], 1):
        p = x.get("params") or {}
        tr = x.get("train") or {}
        va = x.get("validation") or {}
        rows.append(
            "<tr>"
            f"<td>{idx}</td>"
            f"<td>{html.escape(str(p.get('fujin_target') or '—'))}</td>"
            f"<td>{html.escape(str(p.get('fujin_mode') or '—'))} / {n(p.get('fujin_strength'))}</td>"
            f"<td>{n(p.get('raijin_multiplier'))}</td>"
            f"<td>{pct(tr.get('hit_rate_pct'))}</td>"
            f"<td>{n(tr.get('rescued'),0)} / {n(tr.get('lost'),0)}</td>"
            f"<td>{pct(va.get('hit_rate_pct'))}</td>"
            f"<td>{pct(va.get('roi_pct'))}</td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table><thead><tr>'
        '<th>#</th><th>風神対象</th><th>風神補正</th><th>雷神倍率</th>'
        '<th>探索的中率</th><th>救済/損失</th><th>検証的中率</th><th>検証ROI</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'
    )


def point_policy(points):
    ranking = points.get("validation_ranking_of_training_shortlist") or []
    if not ranking:
        return '<div class="empty">6〜24点の強度別探索結果はまだありません。</div>'
    rows = []
    for idx, x in enumerate(ranking[:15], 1):
        p = x.get("point_policy") or {}
        va = x.get("validation") or {}
        latest = x.get("latest") or {}
        rows.append(
            "<tr>"
            f"<td>{idx}</td>"
            f"<td>{p.get('strength_1','—')}</td>"
            f"<td>{p.get('strength_2','—')}</td>"
            f"<td>{p.get('strength_3','—')}</td>"
            f"<td>{p.get('strength_4','—')}</td>"
            f"<td>{p.get('strength_5','—')}</td>"
            f"<td>{p.get('strength_6','—')}</td>"
            f"<td>{pct(va.get('purchase_rate_pct'))}</td>"
            f"<td>{pct(va.get('hit_rate_on_purchased_pct'))}</td>"
            f"<td>{n(va.get('avg_points'))}</td>"
            f"<td>{pct(va.get('roi_pct'))}</td>"
            f"<td>{n(va.get('vs_same_points_no_buff',{}).get('hit_delta'),0)}</td>"
            f"<td>{pct(latest.get('hit_rate_on_purchased_pct'))}</td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table><thead><tr>'
        '<th>#</th><th>強1</th><th>強2</th><th>強3</th><th>強4</th><th>強5</th><th>強6</th>'
        '<th>購入率</th><th>購入R的中率</th><th>平均点数</th><th>検証ROI</th><th>補正純増的中</th><th>最新購入R的中率</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'
    )


def build_page(root: Path) -> str:
    backtest = load_json(root / "fujin_raijin/latest/backtest_summary.json")
    buff = load_json(root / "fujin_raijin/buff_debuff/latest.json")
    points = load_json(root / "fujin_raijin/strength_points/latest.json")
    signal_ai = load_json(root / "signal_ai/latest/summary.json")

    total = backtest.get("total") or {}
    presence = total.get("presence") or {}
    anysig = presence.get("any_signal") or {}
    neither = presence.get("neither") or {}
    p5 = total.get("payout_5000_signal_summary") or {}
    dates = backtest.get("analyzable_dates") or []

    metrics = (
        card("検証レース", n(backtest.get("evaluated_races"),0), f"{len(dates)}日分")
        + card("シグナル発動", n(anysig.get("races"),0), f"発動率 {pct(anysig.get('activation_rate_pct'))}")
        + card("未発動＝見送り", n(neither.get("races"),0), "購入0点")
        + card("発動時5千円以上率", pct(p5.get("signal_5000plus_rate_pct")), f"{n(p5.get('signal_5000plus'),0)}R")
        + card("5千円以上捕捉率", pct(p5.get("signal_capture_rate_of_all_5000plus_pct")), "全5千円以上Rのうちシグナル発動")
    )

    search = points.get("search_space") or {}
    search_text = (
        f"バフ/デバフ候補 {n(search.get('buff_variants'),0)} × "
        f"強度別点数配分 {n(search.get('point_policies'),0)} "
        f"＝ {n(search.get('total_combinations'),0)}通り"
        if search else "強度別6〜24点探索は次回AI分析で生成"
    )

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>風神雷神 AI分析</title>
<style>
:root{{--bg:#f5f7fb;--card:#fff;--text:#182230;--muted:#667085;--line:#e4e7ec;--accent:#155eef;--good:#067647;--warn:#b54708}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans JP",sans-serif}}
.wrap{{max-width:1180px;margin:auto;padding:18px}}header{{margin-bottom:14px}}h1{{font-size:26px;margin:0 0 6px}}h2{{font-size:20px;margin:0 0 12px}}h3{{font-size:16px;margin:16px 0 8px}}
.meta,.note,.sub{{color:var(--muted);font-size:13px}}nav{{display:flex;gap:8px;overflow:auto;margin:14px 0}}nav a{{white-space:nowrap;text-decoration:none;color:var(--text);background:#fff;border:1px solid var(--line);padding:9px 12px;border-radius:10px}}nav a.active{{background:var(--text);color:#fff}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;margin:12px 0;box-shadow:0 1px 2px rgba(16,24,40,.04)}}
.hero{{border:2px solid #b2ccff;background:#eff4ff}}.rule{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}}
.rule>div{{background:#fff;border:1px solid #d1e0ff;border-radius:12px;padding:12px}}.rule b{{display:block;font-size:18px;margin-top:3px}}
.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}.metric{{border:1px solid var(--line);border-radius:12px;padding:12px;background:#fff}}.metric .label{{font-size:12px;color:var(--muted)}}.metric .value{{font-size:22px;font-weight:750;margin:4px 0}}
.table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:12px}}table{{width:100%;border-collapse:collapse;min-width:780px;background:#fff}}th,td{{padding:9px 10px;border-bottom:1px solid var(--line);font-size:13px;text-align:right;white-space:nowrap}}th:first-child,td:first-child{{text-align:left;position:sticky;left:0;background:#fff}}th{{background:#f9fafb}}
.badge{{display:inline-block;padding:4px 8px;border-radius:999px;background:#ecfdf3;color:var(--good);font-size:12px;font-weight:700}}.warn{{background:#fffaeb;color:var(--warn)}}.empty{{padding:18px;color:var(--muted);text-align:center}}
.action{{width:100%;border:0;border-radius:12px;background:var(--accent);color:#fff;padding:13px;font-size:16px;font-weight:700}}footer{{color:var(--muted);font-size:12px;padding:16px 2px 30px}}
</style>
</head>
<body><div class="wrap">
<header><h1>風神雷神 AI分析</h1><div class="meta">現行シグナルAI補正・買い/見送り判定・6〜24点最適化を累積検証</div></header>
<nav><a href="index.html">最新予想</a><a href="results.html">結果・成績</a><a href="analysis.html" class="active">AI分析</a><a href="race_compare.html">レース照合</a></nav>

<section class="card hero">
<h2>第一段階の固定ルール</h2>
<div class="rule">
<div>風神0・雷神0<b>買わない（0点）</b><span class="note">通常予想が良くてもAI分析側では見送り</span></div>
<div>どちらか発動<b>AI評価対象</b><span class="note">現時点は全シグナルで24候補を保存。買い/見送りは蓄積後に判定</span></div>
<div>計算対象<b>3連単120通り</b><span class="note">補正後の艇スコアから全順列を順位付け</span></div>
<div>現在の保存点数<b>上位24点</b><span class="note">今後6/8/10/12/18/24点へ最適化</span></div>
</div>
<p class="note" style="margin-bottom:0">6点は「120通りの上位6点」です。同一3艇の6順列が上位を占めた場合は結果として3艇BOXと同じ形になります。</p>
</section>

<section class="card"><h2>現在の検証母数</h2><div class="metrics">{metrics}</div></section>

<section class="card">
<h2>採用中・シグナルAI補正 Ver.1</h2>
<p class="note">通常の朝・直前スコアは変更せず、各F×Rに対応する採用中のバフ/デバフで6艇を再評価した実成績です。ROIは現時点では該当シグナルをすべて24点購入した場合の比較値で、買い/見送りルール確定前の学習指標です。</p>
<div class="metrics">{current_signal_ai_metrics(signal_ai)}</div>
{current_signal_ai_table(signal_ai)}
</section>

<section class="card">
<h2>風神 × 雷神 組み合わせ別</h2>
<p class="note">発動率・5,000円以上率・万舟率・平均払戻を全16組み合わせで比較。5,000円以上を第一評価ラインとし、未発動はAI購入対象から除外します。</p>
{combo_table(backtest)}
</section>

<section class="card">
<h2>次回補正候補の探索</h2>
<p class="note">上の採用中補正とは別枠です。保存データを使い、次の補正値候補として風神デバフ・雷神バフを探索し、「救えた的中」と「壊した的中」を比較します。</p>
{best_buff(buff)}
</section>

<section class="card">
<h2>買い/見送り・6〜24点候補</h2>
<p class="note">現行補正で24候補を保存しながら、シグナル別に「買う/見送る」と購入点数6〜24点を探索します。最終的には買い判定レースだけの的中率・回収率・万舟捕捉率を本指標にします。</p>
<p class="note">{html.escape(search_text)}</p>
{point_policy(points)}
</section>

<section class="card">
<h2>AI分析を実行</h2>
<p class="note">保存済みの結果前予測を使って、風神雷神判定・過去合算・バフ/デバフ・120通り・強度別点数まで一括再検証します。本番予測は自動変更しません。</p>
<button id="runAiAnalysisButton" class="action" type="button">風神雷神AI分析を開始</button>
<div id="runAiAnalysisStatus" class="meta" style="margin-top:8px">完了後、このページに最新結果が反映されます。</div>
</section>

<footer>このページは風神雷神シグナル専用の検証画面です。過去結果との照合であり、将来の的中を保証するものではありません。</footer>
</div>
<script>
(() => {{
 const b=document.getElementById("runAiAnalysisButton"),s=document.getElementById("runAiAnalysisStatus");
 if(!b||!s)return;
 b.addEventListener("click",async()=>{{
  if(!window.confirm("風神雷神専用AI分析を実行します。よろしいですか？"))return;
  b.disabled=true;s.textContent="風神雷神AI分析を開始しています…";
  try{{
   const r=await fetch("https://boatrace-family-trigger.onrender.com/trigger-analysis",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:"{{}}"}});
   if(r.status!==202)throw new Error("request_failed");
   s.textContent="分析を受け付けました。風神雷神判定・120通り・強度別買い目まで順番に検証します。";
  }}catch(e){{s.textContent="AI分析を開始できませんでした。";b.disabled=false;}}
 }});
}})();
</script>
</body></html>"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--evaluations-root", default="evaluations")
    p.add_argument("--output-dir", default="_family_site")
    a = p.parse_args()
    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "analysis.html"
    path.write_text(build_page(Path(a.evaluations_root)), encoding="utf-8")
    print("風神雷神専用AI分析ページ生成: PASS")
    print(path)


if __name__ == "__main__":
    main()
