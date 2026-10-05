from __future__ import annotations
import csv,json
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path

def read(p):
 with open(p,encoding="utf-8-sig",newline="") as h:return list(csv.DictReader(h))
def dt(s): return datetime.strptime(s,"%Y%m%d").date()
def main():
 files=sorted(Path("archive").glob("*/*/*/results_*_all.csv"))
 rows=[]
 for p in files:
  for r in read(p):
   tech=(r.get("technique") or "").strip()
   if tech: rows.append(r)
 racer=defaultdict(lambda:defaultdict(int)); venue=defaultdict(lambda:defaultdict(int))
 # Winner registration is resolved from the matching boat archive.
 boats={}
 for p in Path("archive").glob("*/*/*/boat_results_*_all.csv"):
  for b in read(p): boats[(b.get("race_id"),b.get("finish"))]=b
 for r in rows:
  tech=r.get("technique",""); v=str(r.get("venue_code","")).zfill(2); venue[v][tech]+=1
  w=boats.get((r.get("race_id"),"1"))
  if w and w.get("registration_no"): racer[w["registration_no"]][tech]+=1
 out={"races_with_technique":len(rows),"racer_winning_techniques":racer,"venue_winning_techniques":venue}
 Path("features").mkdir(exist_ok=True)
 Path("features/tactic_profiles.json").write_text(json.dumps(out,ensure_ascii=False,indent=2,default=dict),encoding="utf-8")
 print(json.dumps({"races_with_technique":len(rows),"racers":len(racer),"venues":len(venue)},ensure_ascii=False))
if __name__=="__main__": main()
