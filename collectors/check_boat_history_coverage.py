import csv,json
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
DATES=["20260930","20261001","20261002"]
def I(v):
 try:return int(float(v))
 except:return None
def D(v):return datetime.strptime(v,"%Y%m%d").date()
def load():
 a=[]
 for p in Path("archive").glob("*/*/*/boat_results_*_all.csv"):
  with p.open(encoding="utf-8-sig",newline="") as h:a+=list(csv.DictReader(h))
 return a
rows=load();out={}
for day in DATES:
 td=D(day); prior=[r for r in rows if r.get("date") and td-timedelta(days=90)<=D(r["date"])<td]
 hist=defaultdict(int)
 for r in prior:
  q=I(r.get("boat_no"));v=str(r.get("venue_code","")).zfill(2)
  if q is not None:hist[(v,q)]+=1
 races=defaultdict(list)
 for r in rows:
  if r.get("date")!=day:continue
  b=I(r.get("boat"));f=I(r.get("finish"));m=I(r.get("boat_no"));v=str(r.get("venue_code","")).zfill(2)
  if b in range(1,7) and f in range(1,7):races[r["race_id"]].append(hist[(v,q)] if q is not None else 0)
 full=[x for x in races.values() if len(x)==6]
 out[day]={"completed":len(full),"all6_have_d90_history":sum(all(n>0 for n in x) for x in full),"at_least5":sum(sum(n>0 for n in x)>=5 for x in full),"at_least4":sum(sum(n>0 for n in x)>=4 for x in full),"boats_total":sum(len(x) for x in full),"boats_with_history":sum(sum(n>0 for n in x) for x in full)}
Path("evaluations/boat_history_coverage").mkdir(parents=True,exist_ok=True)
Path("evaluations/boat_history_coverage/summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
