#!/usr/bin/env python3
import csv,json,itertools
from pathlib import Path
DATE="20261002"
PRED=Path("evaluations/2026/10/02/backfill_live/live_predictions_final_20261002.json")
RESULT=Path("archive/2026/10/02/boat_results_20261002_all.csv")
OUT=Path("evaluations/2026/10/02/structure_search")
BASE=["course","official","recent","venue","motor","boat","grade","series"]
LIVE=["exST","exTime","live_course"]
FRAME={1:1.0,2:.72,3:.62,4:.58,5:.46,6:.38}
STRUCTS=[
("course+official",["course","official"]),
("course+official+grade",["course","official","grade"]),
("course+official+series",["course","official","series"]),
("course+official+recent",["course","official","recent"]),
("course+official+venue",["course","official","venue"]),
("course+grade",["course","grade"]),
("course+series",["course","series"]),
("official+grade",["official","grade"]),
("official+series",["official","series"]),
("official+recent",["official","recent"]),
("course+venue",["course","venue"]),
("course+official+grade+series",["course","official","grade","series"]),
("course+official+grade+recent",["course","official","grade","recent"]),
("course+official+venue+series",["course","official","venue","series"]),
("course+official+grade+venue",["course","official","grade","venue"]),
("course+official+motor",["course","official","motor"]),
("course+official+exST",["course","official","exST"]),
("course+official+exTime",["course","official","exTime"]),
("course+official+live_course+exST",["course","official","live_course","exST"]),
("core+live",["course","official","grade","recent","venue","series","live_course","exST","exTime"]),
]
pred=json.loads(PRED.read_text(encoding="utf-8"))
actual={}
with RESULT.open(encoding="utf-8-sig",newline="") as f:
 for r in csv.DictReader(f):
  try: actual.setdefault(r["race_id"],[]).append((int(float(r["finish"])),int(float(r["boat"]))))
  except: pass
actual={k:[b for _,b in sorted(v)][:3] for k,v in actual.items() if len(v)==6}
def num(x):
 try:return float(x)
 except:return None
def value(b,k):
 lane=int(b["boat"])
 if k=="course": return FRAME[lane]
 if k=="live_course":
  c=(b.get("components") or {}).get("course") or {};return num(c.get("raw_score_0_1")) if c.get("available") else None
 if k=="exTime": return num(b.get("exhibition_time"))
 c=(b.get("components") or {}).get(k) or {};return num(c.get("raw_score_0_1")) if c.get("available") else None
races=[]
for r in pred["races"]:
 a=actual.get(r["race_id"].replace("-","_"))
 if not a:continue
 races.append((a,r["boats"]))
assert len(races)==168
def weights(n):
 # integer compositions in 10% units; minimum 10%. For >4 factors use curated block profiles.
 if n<=4:
  for cuts in itertools.combinations(range(1,10),n-1):
   pts=(0,)+cuts+(10,)
   yield tuple((pts[i+1]-pts[i])*10 for i in range(n))
 else:
  yield tuple(round(100/n) for _ in range(n))
  if n==9:
   yield (25,25,10,5,5,10,5,10,5)
   yield (30,25,10,5,5,10,5,5,5)
def evaluate(keys,w):
 hits=eligible=0
 for a,boats in races:
  scored=[];ok=True
  for b in boats:
   vals=[value(b,k) for k in keys]
   if any(v is None for v in vals):ok=False;break
   # exhibition time lower is better: normalize within race later
   scored.append([int(b["boat"]),vals])
  if not ok:continue
  for j,k in enumerate(keys):
   if k=="exTime":
    order=sorted(range(6),key=lambda i:scored[i][1][j])
    norm={idx:1-(rank/5) for rank,idx in enumerate(order)}
    for i in range(6):scored[i][1][j]=norm[i]
  rank=sorted(((sum(v*x for v,x in zip(vals,w))/sum(w),bn) for bn,vals in scored),key=lambda z:(-z[0],z[1]))
  p=[b for _,b in rank[:3]];eligible+=1;hits+=set(p)==set(a)
 return eligible,hits,round(hits/eligible*100,2) if eligible else None
rows=[]
for name,keys in STRUCTS:
 for w in weights(len(keys)):
  e,h,p=evaluate(keys,w)
  rows.append({"structure":name,"components":keys,"weights_pct":dict(zip(keys,w)),"eligible_races":e,"matches":h,"alignment_pct":p})
rows.sort(key=lambda x:(-(x["alignment_pct"] or -1),-x["eligible_races"],x["structure"]))
top=rows[:20]
OUT.mkdir(parents=True,exist_ok=True)
summary={"date":DATE,"definition":"TOP3完全整合率。各候補構造について10%刻み係数（多要素core+liveは代表係数）を実計算。","production_weights_changed":False,"tested_candidates":len(rows),"top20":top}
(OUT/"structure_search_top20_20261002.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
with (OUT/"structure_search_top20_20261002.csv").open("w",encoding="utf-8",newline="") as f:
 wr=csv.DictWriter(f,fieldnames=["rank","structure","eligible_races","matches","alignment_pct","weights_pct"]);wr.writeheader()
 for i,x in enumerate(top,1):wr.writerow({"rank":i,"structure":x["structure"],"eligible_races":x["eligible_races"],"matches":x["matches"],"alignment_pct":x["alignment_pct"],"weights_pct":json.dumps(x["weights_pct"],ensure_ascii=False)})
print(json.dumps(summary,ensure_ascii=False,indent=2))
