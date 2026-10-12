"""Read-only research data-quality dashboard from normalized observations.

No network access. No scoring, recovery, or alteration of official raw data.
This is a standalone optional research page; does NOT change the four family tabs.
"""
from __future__ import annotations
import argparse
import html
import json
import re
from collections import Counter
from pathlib import Path

SCHEMA="boatrace-normalized-v1"
STATUSES={
    "ready_live_inputs":("読取正常","good"),
    "incomplete_live_inputs":("項目不足","warn"),
    "participant_identity_not_verified":("選手照合不一致","bad"),
    "schedule_missing":("朝番組不足","warn"),
    "unparsed":("読取不能","bad"),
}
ISSUES={
    "parser_not_yet_run":"未解析",
    "parser_no_exhibition_data":"展示データを読み取れません",
    "parser_unhandled_exception":"HTMLの解釈中にエラー",
    "schedule_missing":"該当レースの朝番組がありません",
    "boat_count_incomplete":"6艇のデータが揃いません",
    "invalid_boat_number":"艇番を確認できません",
    "duplicate_boat_number":"艇番が重複",
    "invalid_exhibition_course":"展示進入コース不明",
    "duplicate_exhibition_course":"展示進入コースが重複",
    "missing_registration":"選手登録番号がありません",
    "duplicate_registration":"登録番号が重複",
    "program_registration_mismatch":"朝番組と登録番号が不一致",
    "program_six_registrations_not_verified":"朝番組6艇との照合未完了",
    "official_scratch_requires_special_handling":"公式欠場あり・特別処理が必要",
    "invalid_exhibition_time":"展示タイム欠損・異常",
    "unknown_st_notation":"展示STの未知の表記",
    "missing_exhibition_st":"展示STがありません",
    "late_st_not_usable_in_live_score":"展示STがL表記・数値補正に使用不可",
    "st_seconds_mismatch":"展示STの原文と数値が不一致",
    "false_start_flag_mismatch":"展示Fの解釈が不一致",
    "weather_field_missing":"気象項目がありません",
    "weather_value_outside_plausible_bounds":"気象値の範囲を確認してください",
}
FIELDS={
    "air_temperature_c":"気温","water_temperature_c":"水温",
    "wind_speed_mps":"風速","wave_height_cm":"波高",
    "exhibition_time":"展示タイム","exhibition_st_raw":"展示ST",
    "exhibition_st_seconds":"展示ST数値",
    "exhibition_course":"展示進入","registration_no":"登録番号",
    "boat":"艇番","boats":"出走6艇","beforeinfo":"公式直前情報",
    "program_races":"朝番組","exhibition_st_flag":"展示STのF表記",
    "is_miss":"欠場",
}
def e(v): return html.escape(str(v if v is not None else ""),quote=True)
def valid_day(x): return bool(re.fullmatch(r"\d{8}",str(x or "")))

def summarize_quality(payload:dict)->dict:
    if payload.get("schema")!=SCHEMA or not valid_day(payload.get("date")):
        raise ValueError("unsupported_research_normalized_schema")
    rows=payload.get("races")
    if not isinstance(rows,list): raise ValueError("invalid_race_records")
    counts=Counter()
    issues=Counter()
    status_rows=[]
    for row in rows:
        rid=str(row.get("race_id") or "")
        if not re.fullmatch(r"\d{8}-\d{2}-(?:0[1-9]|1[0-2])",rid) or rid[:8]!=payload["date"]:
            raise ValueError("invalid_quality_race_id")
        state=str(row.get("parse_status") or "unparsed")
        if state not in STATUSES: state="unparsed"
        diag=row.get("diagnostics") or {}
        item_issues=diag.get("issues") or []
        if not isinstance(item_issues,list):item_issues=[{"code":"parser_unhandled_exception","field":"beforeinfo"}]
        counts[state]+=1
        source=row.get("source") or {}
        origin=str(source.get("source_url") or "")
        raw_sha=str(source.get("raw_sha256") or "")
        verified=source.get("drive_raw_verified") is True
        has_source=bool(origin and re.fullmatch(r"[0-9a-f]{64}",raw_sha))
        if not has_source:
            issues["source_identity_unverified"]+=1
        for issue in item_issues:
            issues[str(issue.get("code") or "unknown_issue")]+=1
        status_rows.append({
            "race_id":rid,"status":state,"issues":item_issues,
            "boats":len(row.get("boats") or []),
            "has_source":has_source,"drive_verified":verified,
            "raw_sha256":raw_sha,"source_url":origin,
            "collected_at":str(source.get("collected_at") or ""),
            "parser":str(source.get("parser") or ""),
            "last_ready":row.get("last_ready"),
        })
    status_rows.sort(key=lambda x:x["race_id"])
    return {
        "date":payload["date"],"total":len(rows),
        "ready":counts["ready_live_inputs"],
        "needs_review":len(rows)-counts["ready_live_inputs"],
        "not_collected_count":None,  # Without schedule, NEVER imply 100% coverage.
        "drive_verified_count":sum(r["drive_verified"] for r in status_rows),
        "issues_by_code":dict(sorted(issues.items())),
        "races":status_rows,
    }

def render_dashboard(payload:dict)->str:
    summary=summarize_quality(payload)
    unarchived=(payload.get("source_archive")!="private_google_drive_verified")
    title=f"研究用・読み取り診断　{summary['date']}"
    source_note=("【検証専用】原本はGitHub Actionsの一時保管です。Googleドライブへの永続保存は未確認。"
                 " この画面は予測実績・実購入判定ではありません。" if unarchived else
                 "Googleドライブ原本照合済みデータ。収集対象全レースを網羅したという意味ではありません。")
    badges=[]
    for text,n in [("診断対象",summary["total"]),("読取正常",summary["ready"]),("要確認",summary["needs_review"]),
                   ("Drive原本照合済",summary["drive_verified_count"])]:
        badges.append(f'<div class="metric"><span>{e(text)}</span><strong>{n}R</strong></div>')
    rows=[]
    for item in summary["races"]:
        state,label= item["status"], STATUSES[item["status"]][0]
        color=STATUSES[item["status"]][1]
        kinds=[]
        for problem in item["issues"]:
            code=str(problem.get("code") or "unknown_issue")
            field=str(problem.get("field") or "")
            boat=problem.get("boat")
            part=(f"{e(boat)}号艇・" if boat is not None else "")
            kinds.append(f'<li>{part}{e(ISSUES.get(code,"未登録のエラー"))} '
                f'<small>（{e(FIELDS.get(field,field))} / {e(code)}）</small></li>')
        # No claim of complete coverage when input has zero records.
        issue_html="<ul>"+ "".join(kinds)+"</ul>" if kinds else "—"
        archive="Drive照合済み" if item["drive_verified"] else "永続保存未確認"
        last=""
        if item.get("last_ready"):
            old=item["last_ready"]
            last=(f'<div class="last">最後の正常読取：{e((old.get("source") or {}).get("collected_at") or "時刻不明")}'
                  "（以前の観測であり、現在の表示値ではありません）</div>")
        evidence=(f'<details><summary>原本の照合情報</summary>'
                  f'<div>取得時刻：{e(item["collected_at"]) or "不明"}</div>'
                  f'<div>SHA256：<code>{e(item["raw_sha256"]) or "未記録"}</code></div>'
                  f'<div>解読ルール：{e(item["parser"]) or "未記録"}</div>'
                  f'<div>保存状況：{e(archive)}</div>'
                  f'</details>')
        rows.append(f'<article class="race"><div class="head"><h2>{e(item["race_id"])}</h2>'
                    f'<span class="state {e(color)}">{e(label)}</span></div>'
                    f'<p>艇データ：{item["boats"]}/6 ｜ 原本情報：{"記録あり" if item["has_source"] else "未照合"}'
                    f' ｜ {e(archive)}</p>{issue_html}{last}{evidence}</article>')
    no_data=('<p class="notice">診断対象データがありません。0件は「全レース正常」の意味ではありません。</p>'
             if not rows else "")
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><style>
:root {{color-scheme:light dark}}
body {{font:14px/1.65 system-ui,-apple-system,sans-serif;margin:0;background:#f3f6fa;color:#182537}}
main {{max-width:960px;margin:auto;padding:20px 14px 60px}}
header,article,.metric,.notice {{border:1px solid #d6dfeb;border-radius:12px;background:#fff;padding:15px}}
h1 {{font-size:24px;margin:0 0 5px}} h2 {{font-size:17px;margin:0}}
.small,small,details {{color:#526275;font-size:12px}}
.notice {{border-left:4px solid #a26a12;margin-top:14px}}
.metrics {{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:12px 0}}
.metric span {{display:block;color:#526275}} .metric strong {{font-size:22px}}
.race {{margin:10px 0}} .head {{display:flex;justify-content:space-between;align-items:center;gap:8px}}
.race p {{margin:7px 0}} .state {{font-size:12px;font-weight:800;padding:3px 8px;border-radius:8px}}
.good {{color:#1b6535;background:#dcfce7}} .warn {{color:#805b0c;background:#fff3d3}}
.bad {{color:#8d2430;background:#ffe8eb}} .last {{padding:6px 9px;background:#f7f0dc}}
li {{margin:3px 0}} details {{padding-top:8px;overflow-wrap:anywhere}}
code {{font-family:monospace;font-size:11px;overflow-wrap:anywhere}}
@media(max-width:560px) {{.metrics{{grid-template-columns:repeat(2,1fr)}}h1{{font-size:21px}}}}
@media(prefers-color-scheme:dark) {{body{{background:#101820;color:#edf2f8}}header,article,.metric,.notice{{background:#172536;border-color:#3c4c5f}}.small,small,details,.metric span{{color:#b5c3d1}}.last{{background:#43381d}}.good{{background:#173b26;color:#b7eac3}}.warn{{background:#463918;color:#ffe099}}.bad{{background:#47252d;color:#ffd2d7}}}}
</style></head>
<body><main><header><h1>{e(title)}</h1><p class="small">原本収集と解読の成否を分けた研究用表示です。通常AI／風神雷神の発動を直接変更しません。</p></header>
<p class="notice">{e(source_note)}</p><div class="metrics">{''.join(badges)}</div>
<p class="small">注：対象レースの母数は、この入力JSONに含まれる件数です。公式開催レース全体の取得率ではありません。</p>
{no_data}{''.join(rows)}</main></body></html>"""

def build_page(normalized_file:Path,output_dir:Path)->dict:
    payload=json.loads(normalized_file.read_text(encoding="utf-8"))
    quality=summarize_quality(payload)
    output_dir.mkdir(parents=True,exist_ok=True)
    page=output_dir/"raw_diagnostics.html"
    summary=output_dir/"raw_diagnostics_summary.json"
    page.write_text(render_dashboard(payload),encoding="utf-8")
    summary.write_text(json.dumps(quality,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return {"page":str(page),"summary":str(summary),"total":quality["total"],
            "ready":quality["ready"],"needs_review":quality["needs_review"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    opts=p.parse_args()
    result=build_page(opts.input,opts.output_dir)
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__": main()
