"""Optional research diagnostic page integration for existing four-tab publisher.

Uses Drive-verified normalized evidence when present, otherwise safely reports\nexisting decoded research CSV. No change to the four-tab navigation.
Designed as a separate link within AI analysis, not a replacement for results.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from raw_collector.diagnostics_view import build_page,summarize_quality
from raw_collector.saved_research_view import write_saved_diagnostics

def stage(repo_root:Path,site:Path,day:str)->dict:
    if not re.fullmatch(r"\d{8}",day):
        raise ValueError("invalid_target_date")
    path=repo_root/"normalized"/day[:4]/day[4:6]/day[6:8]/"races.json"
    mode="saved_research_csv"
    status={}
    if path.is_file():
        payload=json.loads(path.read_text(encoding="utf-8"))
        if payload.get("source_archive")=="private_google_drive_verified" and all(
            row.get("source",{}).get("drive_raw_verified") is True
            for row in payload.get("races",[])):
            status=summarize_quality(payload)
            if status["total"]:
                mode="verified_drive_raw"
    if mode=="saved_research_csv":
        from raw_collector.saved_research_adapter import diagnose_saved_day
        status=diagnose_saved_day(repo_root,day)
        if not status.get("races"):
            return {"status":"skipped_no_saved_research_data","date":day}
    analysis=site/"analysis.html"
    if not analysis.is_file():
        raise FileNotFoundError("research_analysis_page_missing")
    html=analysis.read_text(encoding="utf-8")
    nav=re.search(r'<nav\s+class=["\']family-nav["\'][^>]*>.*?</nav>',html,flags=re.S|re.I)
    if nav is None:
        raise ValueError("research_page_navigation_unavailable")
    if 'href="raw_diagnostics.html"' in html:
        raise ValueError("research_diagnostic_link_already_exists")
    if mode=="verified_drive_raw":
        staged=build_page(path,site)
        label="研究用・データ読み取り診断を見る"
        explanation="原本照合済みデータの読取と保存状態"
    else:
        saved=write_saved_diagnostics(repo_root,day,site)
        staged={"page":str(site/"raw_diagnostics.html")}
        label="研究用・保存データ診断を見る"
        explanation="出走表・直前保存・予測の有無（原本の保存確認ではありません）"
    link=('<div class="notice" data-research-raw-quality="v1">'
          '<a href="raw_diagnostics.html">'+label+'</a>'
          '（'+explanation+'）</div>')
    html=html[:nav.end()]+"\n"+link+html[nav.end():]
    analysis.write_text(html,encoding="utf-8")
    if mode=="verified_drive_raw":
        return {"status":"staged_verified_research_diagnostics","date":day,
                "count":status["total"],"ready":status["ready"],
                "needs_review":status["needs_review"],"page":staged["page"]}
    return {"status":"staged_saved_research_diagnostics","date":day,
            "count":len(status["races"]), "source_kind":"decoded_research_files_not_official_html",
            "page":staged["page"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=True)
    p.add_argument("--repo-root",type=Path,default=Path("."))
    p.add_argument("--site-dir",type=Path,default=Path("_family_site"))
    x=p.parse_args()
    print(json.dumps(stage(x.repo_root,x.site_dir,x.date),ensure_ascii=False))
if __name__=="__main__":
    main()
