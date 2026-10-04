from __future__ import annotations
import argparse,csv,json,re
from datetime import datetime
from pathlib import Path

def rows(p):
    if not p.exists(): return []
    with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def norm(v):
    m=re.fullmatch(r"(\d{8})[-_](\d{1,2})[-_](\d{1,2})",str(v or "").strip())
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else str(v or "").strip()
def nonempty(v): return str(v or "").strip()!=""

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--date",required=True);a=ap.parse_args();d=a.date
    y,m,day=d[:4],d[4:6],d[6:8]
    base=Path("daily_inputs")/y/m/day
    arc=Path("archive")/y/m/day
    out=Path("evaluations")/y/m/day/"data_quality";out.mkdir(parents=True,exist_ok=True)
    program=rows(base/"base"/f"program_races_{d}.csv")
    entries=rows(base/"base"/f"program_entries_{d}.csv")
    if not program: program=rows(Path("data")/f"program_races_{d}.csv")
    expected={norm(r.get("race_id")) for r in program if norm(r.get("race_id"))}
    result=rows(arc/f"results_{d}_all.csv")
    boats=rows(arc/f"boat_results_{d}_all.csv")
    actual={norm(r.get("race_id")) for r in result}
    bmap={}
    for r in boats:bmap.setdefault(norm(r.get("race_id")),[]).append(r)
    # Merge every saved live raw snapshot; latest non-empty value wins per race/boat.
    live={}
    for p in sorted((base/"live"/"raw").glob("*/beforeinfo_entries_*.csv")) if (base/"live"/"raw").exists() else []:
        for r in rows(p):
            key=(norm(r.get("race_id")),str(r.get("boat","")).strip())
            cur=live.setdefault(key,{})
            for k,v in r.items():
                if nonempty(v):cur[k]=v
    # Older snapshot/backfill layouts are also accepted.
    for p in sorted((base/"live").glob("**/beforeinfo_entries_*.csv")) if (base/"live").exists() else []:
        for r in rows(p):
            key=(norm(r.get("race_id")),str(r.get("boat","")).strip())
            cur=live.setdefault(key,{})
            for k,v in r.items():
                if nonempty(v):cur[k]=v
    issues=[];complete=0
    race_ids=sorted(expected|actual)
    for rid in race_ids:
        miss=[]
        if rid not in expected: miss.append("morning_program")
        if rid not in actual: miss.append("result")
        br=bmap.get(rid,[])
        if len(br)!=6: miss.append(f"boat_result:{len(br)}/6")
        for boat in map(str,range(1,7)):
            lr=live.get((rid,boat))
            if not lr:
                miss.append(f"boat{boat}:beforeinfo")
                continue
            for field in ("exhibition_course","exhibition_time","exhibition_st_raw"):
                if not nonempty(lr.get(field)):miss.append(f"boat{boat}:{field}")
        if miss:issues.append({"race_id":rid,"missing":sorted(set(miss))})
        else:complete+=1
    status="PASS" if not issues else "INCOMPLETE"
    report={"date":d,"status":status,"expected_races":len(expected),"result_races":len(actual),"audited_races":len(race_ids),"complete_races":complete,"incomplete_races":len(issues),"needs_recollection":bool(issues),"issues":issues,"rules":{"prediction_leakage":"results are audit-only and must never be used to reconstruct prediction inputs","required_live":["exhibition_course","exhibition_time","exhibition_st_raw"]}}
    (out/f"completeness_{d}.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    with (out/f"missing_{d}.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["race_id","missing"]);w.writeheader()
        for x in issues:w.writerow({"race_id":x["race_id"],"missing":";".join(x["missing"])})
    print(json.dumps({k:report[k] for k in ("date","status","audited_races","complete_races","incomplete_races","needs_recollection")},ensure_ascii=False))
    return 0
if __name__=="__main__":raise SystemExit(main())
