"""Attach read-only saved research quality page to the existing AI analysis tab.

Uses research CSV and prediction files. No Drive OAuth or official page HTTP fetch.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from raw_collector.saved_research_view import write_saved_diagnostics

def stage(root:Path,site:Path,day:str)->dict:
    if not re.fullmatch(r"\d{8}",day):raise ValueError("invalid_date")
    page=site/"analysis.html"
    if not page.is_file():raise FileNotFoundError("analysis_page_missing")
    original=page.read_text(encoding="utf-8")
    nav=re.search(r'<nav\s+class=["\']family-nav["\'][^>]*>.*?</nav>',original,re.I|re.S)
    if nav is None:raise ValueError("expected_four_tab_navigation_missing")
    if 'data-research-saved-quality="v1"' in original:
        raise ValueError("quality_link_already_inserted")
    # No durable page or link if there is no saved official race schedule.
    from raw_collector.saved_research_adapter import diagnose_saved_day
    diagnostics=diagnose_saved_day(root,day)
    if not diagnostics["races"]:
        return {"status":"skipped_no_saved_program","date":day}
    report=write_saved_diagnostics(root,day,site)
    link=('<div class="notice" data-research-saved-quality="v1">'
          '<a href="raw_diagnostics.html">研究用・保存データ診断（朝・直前・復旧・予測）</a>'
          '　<span>生HTML原本の保管確認とは別です</span></div>')
    page.write_text(original[:nav.end()]+"\n"+link+original[nav.end():],encoding="utf-8")
    return {"status":"generated","date":day,"races":len(report["races"]),
            "timestamp_consistent_not_proven":report["summary"].get("clock_consistent_not_proven",0)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=True)
    p.add_argument("--site-dir",default="_family_site",type=Path)
    p.add_argument("--repo-root",default=".",type=Path)
    opts=p.parse_args()
    print(json.dumps(stage(opts.repo_root,opts.site_dir,opts.date),ensure_ascii=False))
if __name__=="__main__":main()
