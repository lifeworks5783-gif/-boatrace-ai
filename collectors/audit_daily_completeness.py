from __future__ import annotations
import argparse,csv,json,re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

def rows(p):
    if not p.exists(): return []
    with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def norm(v):
    m=re.fullmatch(r"(\d{8})[-_](\d{1,2})[-_](\d{1,2})",str(v or "").strip())
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else str(v or "").strip()
def nonempty(v): return str(v or "").strip()!=""

def _parse_official_beforeinfo(html):
    soup=BeautifulSoup(html,"html.parser")
    tbodies=[tb for tb in soup.select("tbody") if tb.select_one('a[href*="toban="]')]
    official=[]
    for idx,tb in enumerate(tbodies,1):
        cls=tb.get("class",[])
        official.append({"boat":idx,"is_miss":"is-miss" in cls})
    return official

def official_beforeinfo_check(d,rid):
    """異常時のみ公式を再確認。速報性を優先してSP版→PC版の順。全体処理は止めない。"""
    _,venue,race=rid.split("-")
    urls=[
        f"https://www.boatrace.jp/owsp/sp/race/beforeinfo?hd={d}&jcd={venue}&rno={int(race)}",
        f"https://www.boatrace.jp/owpc/pc/race/beforeinfo?hd={d}&jcd={venue}&rno={int(race)}",
    ]
    errors=[]
    for url in urls:
        try:
            res=requests.get(url,timeout=(2,4),headers={"User-Agent":"Mozilla/5.0 (compatible; boatrace-ai-quality-audit/1.1)"})
            res.raise_for_status()
            official=_parse_official_beforeinfo(res.text)
            if official:
                return {"checked":True,"source_url":url,"source_variant":"sp" if "/owsp/" in url else "pc","official_boats":official,"boat_count":len(official)}
            errors.append(f"{url}:no_rows")
        except Exception as exc:
            errors.append(f"{url}:{type(exc).__name__}")
    return {"checked":False,"errors":errors}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--date",required=True);a=ap.parse_args();d=a.date
    y,m,day=d[:4],d[4:6],d[6:8]
    base=Path("daily_inputs")/y/m/day
    arc=Path("archive")/y/m/day
    out=Path("evaluations")/y/m/day/"data_quality";out.mkdir(parents=True,exist_ok=True)
    program=rows(base/"base"/f"program_races_{d}.csv")
    entries=rows(base/"base"/f"program_entries_{d}.csv")
    if not program: program=rows(Path("data")/f"program_races_{d}.csv")
    if not entries: entries=rows(Path("data")/f"program_entries_{d}.csv")
    expected={norm(r.get("race_id")) for r in program if norm(r.get("race_id"))}
    schedule={norm(r.get("race_id")):str(r.get("deadline") or "").strip() for r in program}
    now_jst=datetime.now(timezone(timedelta(hours=9)))
    entry_count={}
    for r in entries:
        rid=norm(r.get("race_id"))
        if rid: entry_count[rid]=entry_count.get(rid,0)+1
    result=rows(arc/f"results_{d}_all.csv")
    boats=rows(arc/f"boat_results_{d}_all.csv")
    actual={norm(r.get("race_id")) for r in result}
    bmap={}
    for r in boats:bmap.setdefault(norm(r.get("race_id")),[]).append(r)
    # Merge saved live raw snapshots while preserving provenance.
    # Original pre-race snapshots are preferred. Post-result retries may fill
    # missing values, but must never be mislabeled as original observations.
    live={}; provenance={}
    def merge_live(path, source):
        for r in rows(path):
            key=(norm(r.get("race_id")),str(r.get("boat","")).strip())
            cur=live.setdefault(key,{})
            src=provenance.setdefault(key,{})
            for k,v in r.items():
                # change_parts は「部品交換なし」のとき空欄が正常。
                # 値の有無ではなく列が存在した事実を保持する。
                if k=="change_parts":
                    if source=="original_pre_race" or k not in cur:
                        cur[k]=v
                        src[k]=source
                    continue
                if not nonempty(v): continue
                if source=="original_pre_race" or not nonempty(cur.get(k)):
                    cur[k]=v; src[k]=source
    raw_paths=sorted((base/"live"/"raw").glob("*/beforeinfo_entries_*.csv")) if (base/"live"/"raw").exists() else []
    for p in raw_paths: merge_live(p,"original_pre_race")
    retry_paths=sorted((base/"live"/"retry_after_results").glob("**/beforeinfo_entries_*.csv")) if (base/"live"/"retry_after_results").exists() else []
    for p in retry_paths: merge_live(p,"post_result_retry")
    # Backfill is useful for completeness/audit, but it is never relabeled as genuine pre-race observation.
    backfill_paths=sorted((base/"live"/"backfill").glob("**/beforeinfo_entries_*.csv")) if (base/"live"/"backfill").exists() else []
    for p in backfill_paths: merge_live(p,"post_result_retry")
    # Older layouts: exclude retry_after_results because it was handled above.
    older=sorted((base/"live").glob("**/beforeinfo_entries_*.csv")) if (base/"live").exists() else []
    for p in older:
        if "retry_after_results" in p.parts or "backfill" in p.parts or p in raw_paths: continue
        merge_live(p,"original_pre_race")
    # Race-level beforeinfo (weather/water/wind/wave/flags) is audited separately.
    live_races={}; race_provenance={}
    def merge_races(path, source):
        for r in rows(path):
            key=norm(r.get("race_id"))
            if not key: continue
            cur=live_races.setdefault(key,{})
            src=race_provenance.setdefault(key,{})
            for k,v in r.items():
                if not nonempty(v): continue
                if source=="original_pre_race" or not nonempty(cur.get(k)):
                    cur[k]=v; src[k]=source
    for p in sorted((base/"live"/"raw").glob("*/beforeinfo_races_*.csv")) if (base/"live"/"raw").exists() else []: merge_races(p,"original_pre_race")
    for p in sorted((base/"live"/"retry_after_results").glob("**/beforeinfo_races_*.csv")) if (base/"live"/"retry_after_results").exists() else []: merge_races(p,"post_result_retry")
    for p in sorted((base/"live"/"backfill").glob("**/beforeinfo_races_*.csv")) if (base/"live"/"backfill").exists() else []: merge_races(p,"post_result_retry")
    issues=[];complete=0;recovered=[];official_checks=[];pending_results=[]
    race_ids=sorted(expected|actual)
    pending=[]
    for rid in race_ids:
        miss=[]
        if rid not in expected: miss.append("morning_program")
        if entry_count.get(rid,0)!=6: miss.append(f"morning_entries:{entry_count.get(rid,0)}/6")
        if rid not in actual: miss.append("result")
        br=bmap.get(rid,[])
        if len(br)!=6: miss.append(f"boat_result:{len(br)}/6")
        rr=live_races.get(rid)
        if not rr:
            miss.append("race:beforeinfo")
        else:
            for field in ("air_temperature_c","water_temperature_c","wind_speed_mps","wave_height_cm"):
                if not nonempty(rr.get(field)): miss.append(f"race:{field}")
        recovered_fields=[]
        if rr:
            for field in ("air_temperature_c","water_temperature_c","wind_speed_mps","wave_height_cm"):
                if nonempty(rr.get(field)) and race_provenance.get(rid,{}).get(field)=="post_result_retry":
                    recovered_fields.append(f"race:{field}")
        for boat in map(str,range(1,7)):
            lr=live.get((rid,boat))
            if not lr:
                miss.append(f"boat{boat}:beforeinfo")
                continue
            is_miss = str(lr.get("is_miss") or "").strip().lower() in {"true","1","yes"}
            # 欠場艇は公式beforeinfoでも展示値が空欄になるため欠損扱いしない。
            if not is_miss:
                for field in ("exhibition_course","exhibition_time","exhibition_st_raw"):
                    if not nonempty(lr.get(field)):miss.append(f"boat{boat}:{field}")
                    elif provenance.get((rid,boat),{}).get(field)=="post_result_retry":
                        recovered_fields.append(f"boat{boat}:{field}")
            # change_parts may legitimately be blank; only schema presence is required.
            if "change_parts" not in lr: miss.append(f"boat{boat}:change_parts_column")
        # A race whose result is not due yet is not an acquisition failure.
        # Use the morning program deadline, with a small post-race publication grace period.
        # Never infer a result or a prediction from the scheduled time.
        deadline=schedule.get(rid, "")
        if rid in expected and rid not in actual and re.fullmatch(r"\d{2}:\d{2}",deadline):
            due=datetime.strptime(f"{d} {deadline}","%Y%m%d %H:%M").replace(tzinfo=timezone(timedelta(hours=9)))
            due+=timedelta(minutes=12)
            if now_jst < due:
                pending_results.append({"race_id":rid,"deadline_jst":deadline,"review_after_jst":due.isoformat(),"status":"AWAITING_RESULT"})
                continue
        if recovered_fields: recovered.append({"race_id":rid,"fields":sorted(set(recovered_fields))})
        # まず手元データだけで候補を絞る。公式アクセスは候補だけを後段で並列実行する。
        if miss:
            pending.append((rid, sorted(set(miss))))
        else:
            complete+=1

    # △にする前に、異常候補は必ず公式を再参照する。
    # SP版を先に見て、取れない場合のみPC版へフォールバック。少数並列で全体停止を防ぐ。
    checks={}
    beforeinfo_pending=[(rid,miss) for rid,miss in pending if any(x.startswith(("boat1:", "boat2:", "boat3:", "boat4:", "boat5:", "boat6:", "race:")) for x in miss)]
    if beforeinfo_pending:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures={pool.submit(official_beforeinfo_check,d,rid):rid for rid,_ in beforeinfo_pending}
            for future in as_completed(futures):
                rid=futures[future]
                try: checks[rid]=future.result()
                except Exception as exc: checks[rid]={"checked":False,"errors":[f"worker:{type(exc).__name__}"]}
    for rid, miss0 in pending:
        miss=list(miss0)
        chk=checks.get(rid,{"checked":False,"errors":["not_checked"]})
        official_checks.append({"race_id":rid,**chk})
        if chk.get("checked"):
            official_miss={str(x["boat"]) for x in chk.get("official_boats",[]) if x.get("is_miss")}
            resolved=[]
            for item in miss:
                mboat=re.match(r"boat(\d+):",item)
                if mboat and mboat.group(1) in official_miss:
                    resolved.append(item)
            miss=[x for x in miss if x not in resolved]
        if miss:
            issues.append({"race_id":rid,"missing":sorted(set(miss)),"quality_mark":"△","quality_label":"要確認"})
        else:
            complete+=1
    status="INCOMPLETE" if issues else ("IN_PROGRESS" if pending_results else "PASS")
    pending_ids={x["race_id"] for x in pending_results}
    original_complete=0
    recovered_complete=0
    for rid in race_ids:
        if rid in pending_ids or any(x["race_id"]==rid for x in issues): continue
        used_retry=False
        for boat in map(str,range(1,7)):
            src=provenance.get((rid,boat),{})
            if any(src.get(f)=="post_result_retry" for f in ("exhibition_course","exhibition_time","exhibition_st_raw")):
                used_retry=True
        rsrc=race_provenance.get(rid,{})
        if any(rsrc.get(f)=="post_result_retry" for f in ("air_temperature_c","water_temperature_c","wind_speed_mps","wave_height_cm")):
            used_retry=True
        if used_retry: recovered_complete+=1
        else: original_complete+=1
    report={"date":d,"status":status,"expected_races":len(expected),"result_races":len(actual),"audited_races":len(race_ids),"complete_races":complete,"original_pre_race_complete_races":original_complete,"post_result_recovered_complete_races":recovered_complete,"incomplete_races":len(issues),"pending_races":len(pending_results),"pending_result_details":pending_results,"audit_asof_jst":now_jst.isoformat(),"needs_recollection":any(any(x.startswith(("race:", "boat1:", "boat2:", "boat3:", "boat4:", "boat5:", "boat6:")) for x in issue["missing"]) for issue in issues),"issues":issues,"recovered_after_result":recovered,"official_rechecks":official_checks,"rules":{"prediction_leakage":"results are audit-only and must never be used to reconstruct prediction inputs","required_live":["exhibition_course","exhibition_time","exhibition_st_raw","change_parts_column"],"exhibition_exception":"is_miss=true boats may legitimately have blank exhibition fields","required_race_environment":["air_temperature_c","water_temperature_c","wind_speed_mps","wave_height_cm"],"provenance":["original_pre_race","post_result_retry"]}}
    (out/f"completeness_{d}.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    with (out/f"missing_{d}.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["race_id","missing"]);w.writeheader()
        for x in issues:w.writerow({"race_id":x["race_id"],"missing":";".join(x["missing"])})
    print(json.dumps({k:report[k] for k in ("date","status","audited_races","complete_races","incomplete_races","needs_recollection")},ensure_ascii=False))
    return 0
if __name__=="__main__":raise SystemExit(main())
