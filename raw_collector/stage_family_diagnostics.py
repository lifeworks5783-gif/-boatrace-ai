"""Optional research diagnostic page integration for existing four-tab publisher.

No output without Drive-verified normalized evidence; no change to nav tab count.
Designed as a separate link within AI analysis, not a replacement for results.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from raw_collector.diagnostics_view import build_page,summarize_quality

def stage(repo_root:Path,site:Path,day:str)->dict:
    if not re.fullmatch(r"\d{8}",day):
        raise ValueError("invalid_target_date")
    path=repo_root/"normalized"/day[:4]/day[4:6]/day[6:8]/"races.json"
    if not path.is_file():
        return {"status":"skipped_no_verified_research_data","date":day}
    payload=json.loads(path.read_text(encoding="utf-8"))
    if payload.get("source_archive")!="private_google_drive_verified":
        return {"status":"skipped_original_not_archived","date":day}
    if any(row.get("source",{}).get("drive_raw_verified") is not True
           for row in payload.get("races",[])):
        return {"status":"skipped_original_not_archived","date":day}
    status=summarize_quality(payload)
    if status["total"]==0:
        return {"status":"skipped_no_race_records","date":day}
    analysis=site/"analysis.html"
    if not analysis.is_file():
        raise FileNotFoundError("research_analysis_page_missing")
    html=analysis.read_text(encoding="utf-8")
    nav=re.search(r'<nav\s+class=["\']family-nav["\'][^>]*>.*?</nav>',html,flags=re.S|re.I)
    if nav is None:
        raise ValueError("research_page_navigation_unavailable")
    if 'href="raw_diagnostics.html"' in html:
        raise ValueError("research_diagnostic_link_already_exists")
    staged=build_page(path,site)
    link=('<div class="notice" data-research-raw-quality="v1">'
          '<a href="raw_diagnostics.html">研究用・データ読み取り診断を見る</a>'
          '（収集成功・読み取り異常・原本の保存状態を分けて確認）</div>')
    html=html[:nav.end()]+"\n"+link+html[nav.end():]
    analysis.write_text(html,encoding="utf-8")
    return {"status":"staged_verified_research_diagnostics","date":day,
            "count":status["total"],"ready":status["ready"],
            "needs_review":status["needs_review"],"page":staged["page"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=True)
    p.add_argument("--repo-root",type=Path,default=Path("."))
    p.add_argument("--site-dir",type=Path,default=Path("_family_site"))
    x=p.parse_args()
    print(json.dumps(stage(x.repo_root,x.site_dir,x.date),ensure_ascii=False))
if __name__=="__main__":
    main()
