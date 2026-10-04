#!/usr/bin/env python3
import csv, glob, json, os
from collections import defaultdict, deque
from datetime import datetime

OUT_DIR="evaluations/racer_recent_form"
os.makedirs(OUT_DIR, exist_ok=True)

files=sorted(glob.glob("archive/2026/*/*/boat_results_*_all.csv"))
history=defaultdict(lambda: deque(maxlen=10))
rows=[]
dates=set()

def fnum(x):
    try:return float(x)
    except:return None

for path in files:
    date=os.path.basename(path).split("_")[2]
    dates.add(date)
    with open(path, encoding="utf-8-sig", newline="") as f:
        data=list(csv.DictReader(f))
    # snapshot BEFORE each race, using only earlier races to avoid leakage
    by_race=defaultdict(list)
    for r in data: by_race[(r.get("venue_code",""), int(r.get("race") or 0))].append(r)
    for key in sorted(by_race, key=lambda x:(x[0],x[1])):
        race_rows=by_race[key]
        for r in race_rows:
            reg=(r.get("registration_no") or "").strip()
            if not reg: continue
            h=list(history[reg])
            last5=h[-5:]; last10=h[-10:]
            def stats(xs):
                fs=[x["finish"] for x in xs if x["finish"] is not None]
                sts=[x["st"] for x in xs if x["st"] is not None]
                return {
                    "n":len(fs),
                    "avg_finish":round(sum(fs)/len(fs),4) if fs else None,
                    "win_rate":round(sum(v==1 for v in fs)/len(fs),4) if fs else None,
                    "top3_rate":round(sum(v<=3 for v in fs)/len(fs),4) if fs else None,
                    "avg_st":round(sum(sts)/len(sts),4) if sts else None,
                }
            rows.append({
                "date":date,"race_id":r.get("race_id"),"venue_code":r.get("venue_code"),
                "race":r.get("race"),"boat":r.get("boat"),"registration_no":reg,
                "racer_name":r.get("racer_name"),"last5":stats(last5),"last10":stats(last10),
                "actual_finish":fnum(r.get("finish")),"actual_st":fnum(r.get("st"))
            })
        for r in race_rows:
            reg=(r.get("registration_no") or "").strip()
            if reg:
                history[reg].append({"finish":fnum(r.get("finish")),"st":fnum(r.get("st"))})

out=os.path.join(OUT_DIR,"racer_recent_form_backfill.json")
with open(out,"w",encoding="utf-8") as f:
    json.dump({"generated_at":datetime.now().isoformat(),"source_start":min(dates) if dates else None,
               "source_end":max(dates) if dates else None,"rows":rows},f,ensure_ascii=False,indent=2)
print(json.dumps({"files":len(files),"dates":len(dates),"rows":len(rows),"output":out},ensure_ascii=False))
