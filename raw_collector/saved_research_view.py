"""Research-only quality view generated from EXISTING decoded CSV and predictions.

No official HTML is in this view. Saved data presence != historical predeadline
proof. Only direct raw originals plus trustworthy timestamps can establish that.
"""
from __future__ import annotations
import html
import json
from pathlib import Path
from raw_collector.saved_research_adapter import diagnose_saved_day

ISSUES={
 "saved_program_entries_not_six":"朝番組の6艇照合が未完了",
 "saved_live_entries_incomplete":"直前の保存済み艇数が不足",
 "only_reconstructed_after_result":"結果後に取得した復旧データのみ",
 "predeadline_capture_not_confirmed":"締切前取得の原本が未確認",
 "predeadline_capture_time_not_independently_verified":"保存済み原版の取得時刻は未検証",
 "morning_prediction_file_unreadable_or_missing":"朝予測ファイルがない／読めない",
 "morning_prediction_not_saved_for_race":"朝予測に該当レースがない",
 "live_prediction_file_unreadable_or_missing":"直前予測ファイルがない／読めない",
 "live_prediction_not_saved_for_race":"直前予測に該当レースがない",
 "canonical_file_unreadable_or_missing":"共通正本がない／読めない",
 "canonical_prediction_not_saved_for_race":"共通正本に該当レースがない",
}
STATE={
 "original_folder_saved_unverified_time":"保存済み原版（時刻未検証）",
 "post_result_recovery_only":"結果後の復旧のみ",
 "historical_capture_time_unverified":"旧形式・取得時刻不明",
 "no_saved_beforeinfo":"直前の保存記録なし",
}
def h(x):return html.escape(str(x if x is not None else ""),quote=True)
def make_html(data):
    if data.get("schema")!="boatrace-saved-diagnostics-v1":
        raise ValueError("unsupported_saved_diagnostics")
    date=h(data["date"])
    summary=data["summary"]
    total=summary.get("total",0)
    cards=[
        ("対象レース",total),("朝番組6艇",summary.get("morning_six",0)),
        ("直前予測保存",summary.get("live_prediction_saved",0)),
        ("結果後復旧のみ",summary.get("recovered_only",0))
    ]
    metric="".join(f'<div class="stat"><span>{h(label)}</span><b>{int(n)}R</b></div>' for label,n in cards)
    sections=[]
    for race in data.get("races",[]):
        state=race.get("beforeinfo_state","no_saved_beforeinfo")
        issues=race.get("issues",[])
        items="".join(f'<li>{h(ISSUES.get(x.get("code"),x.get("code")))}</li>' for x in issues)
        flags=[
            ("朝番組",f'{race.get("morning_entry_count",0)}/6艇'),
            ("旧形式・原版",f'{race.get("original_folder_boats",0)}/6艇'),
            ("結果後復旧",f'{race.get("reconstructed_after_result_boats",0)}/6艇'),
            ("朝予測","保存あり" if race.get("morning_prediction_saved") else "未確認"),
            ("直前予測","保存あり" if race.get("live_prediction_saved") else "未確認"),
            ("共通正本","保存あり" if race.get("canonical_prediction_saved") else "未確認"),
        ]
        flagtext=" ／ ".join(f'{h(label)}：{h(val)}' for label,val in flags)
        sections.append(
            f'<details><summary><strong>{h(race["race_id"])}</strong>　'
            f'{h(STATE.get(state,state))}</summary>'
            f'<p>{flagtext}</p><ul>{items or "<li>追加の問題記録なし</li>"}</ul></details>'
        )
    empty=('<p>公式番組の保存がありません。取得成功・全レース正常とは判定できません。</p>'
           if not sections else "")
    return f"""<!doctype html><html lang="ja"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>研究用データ保存診断 {date}</title>
<style>
:root{{color-scheme:light dark}}body{{margin:0;background:#f4f6fa;color:#19283b;font:14px/1.65 system-ui,sans-serif}}
main{{max-width:960px;margin:auto;padding:18px 13px 70px}}
header,.notice,details,.stat{{border:1px solid #d5ddea;background:#fff;border-radius:12px;padding:12px}}
.notice{{border-left:4px solid #aa7713;margin:12px 0}}
h1{{font-size:22px;margin:0}}.stats{{display:grid;grid-template-columns:repeat(2,1fr);gap:9px;margin:15px 0}}
.stat span{{display:block;font-size:12px;color:#546477}}.stat b{{font-size:23px}}
details{{margin:8px 0}}summary{{cursor:pointer;font-weight:700}}
ul{{margin:8px 0 0;padding-left:22px}}
@media(prefers-color-scheme:dark){{body{{background:#101820;color:#edf2f8}}header,.notice,details,.stat{{background:#172536;border-color:#3c4c5f}}.stat span{{color:#b5c3d1}}}}
</style></head><body><main>
<header><h1>研究用データ保存診断 {date}</h1></header>
<p class="notice">この画面はGitHub研究版の既存CSV・保存済み予測を確認したものです。
公式ページの生HTML原本は検証できておらず、Google Driveにも永続保存されたとは扱いません。
結果後に復旧したデータを当時の直前取得・シグナル実績として扱いません。
本画面は保存状況の検査であり、予測の的中や完全性の保証ではありません。</p>
<div class="stats">{metric}</div>
<p>保存済み公式番組を母数にした調査です。公式の開催全レースを網羅しているかは別途監査が必要です。</p>
{empty}{''.join(sections)}
</main></body></html>"""

def write_saved_diagnostics(root:Path,day:str,out_dir:Path):
    report=diagnose_saved_day(root,day)
    out_dir.mkdir(parents=True,exist_ok=True)
    (out_dir/"raw_diagnostics.html").write_text(make_html(report),encoding="utf-8")
    (out_dir/"raw_diagnostics_summary.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report
