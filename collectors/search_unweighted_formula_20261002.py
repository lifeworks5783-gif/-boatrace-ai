#!/usr/bin/env python3
import csv,json,itertools,math
from pathlib import Path
P=Path("evaluations/2026/10/02/backfill_live/live_predictions_final_20261002.json")
R=Path("archive/2026/10/02/boat_results_20261002_all.csv")
O=Path("evaluations/2026/10/02/unweighted_formula_search")
F={1:1.0,2:.72,3:.62,4:.58,5:.46,6:.38}
K=["course","official","grade","recent","venue","series","motor","boat","live_course","exST","exTime"]
pred=json.loads(P.read_text(encoding="utf-8")); actual={}
with R.open(encoding="utf-8-sig",newline="") as f:
 for r in csv.DictReader(f):
  try:actual.setdefault(r["race_id"],[]).append((int(float(r["finish"])),int(float(r["boat"]))))
  except:pass
actual={k:[b for _,b in sorted(v)][:3] for k,v in actual.items() if len(v)==6}
def num(x):
 try:return float(x)
 except:return None
def value(b,k):
 lane=int(b["boat"])
 if k=="course":return F[lane]
 if k=="live_course":
  c=(b.get("components") or {}).get("course") or {};return num(c.get("raw_score_0_1")) if c.get("available") else None
 if k=="exTime":return num(b.get("exhibition_time"))
 c=(b.get("components") or {}).get(k) or {};return num(c.get("raw_score_0_1")) if c.get("available") else None
races=[(actual.get(r["race_id"].replace("-","_")),r["boats"]) for r in pred["races"]]
races=[x for x in races if x[0]]
def evaluate(keys,mode,split=0):
 e=t=ex=one=0
 for a,boats in races:
  rows=[[int(b["boat"]),[value(b,k) for k in keys]] for b in boats]
  if any(v is None for _,vs in rows for v in vs):continue
  for j,k in enumerate(keys):
   if k=="exTime":
    order=sorted(range(6),key=lambda i:rows[i][1][j]); sc={ix:1-r/5 for r,ix in enumerate(order)}
    for i in range(6):rows[i][1][j]=sc[i]
  scores=[]
  for bn,vs in rows:
   s=math.prod(vs) if mode=="mul" else sum(vs) if mode=="add" else math.prod(vs[:split])+sum(vs[split:])
   scores.append((s,bn))
  p=[b for _,b in sorted(scores,key=lambda z:(-z[0],z[1]))[:3]]
  e+=1;t+=set(p)==set(a);ex+=p==a;one+=p[0]==a[0]
 pct=lambda x:round(x/e*100,2) if e else None
 return e,t,pct(t),ex,pct(ex),one,pct(one)
rows=[]
def addrow(keys,mode,split=0):
 e,t,tp,ex,exp,one,op=evaluate(keys,mode,split)
 formula=(" × ".join(keys) if mode=="mul" else " + ".join(keys) if mode=="add" else "("+" × ".join(keys[:split])+") + "+" + ".join(keys[split:]))
 rows.append({"formula":formula,"mode":mode,"eligible_races":e,"top3_matches":t,"top3_alignment_pct":tp,"exact_matches":ex,"exact_alignment_pct":exp,"top1_matches":one,"top1_accuracy_pct":op})
for n in range(2,6):
 for keys in itertools.combinations(K,n):
  addrow(keys,"mul");addrow(keys,"add")
for ncore in (2,3):
 for core in itertools.combinations(K,ncore):
  pool=[k for k in K if k not in core]
  for nr in (1,2):
   for rest in itertools.combinations(pool,nr):addrow(core+rest,"hybrid",ncore)
rows.sort(key=lambda x:(-(x["top3_alignment_pct"] or -1),-(x["exact_alignment_pct"] or -1),-(x["top1_accuracy_pct"] or -1),-x["eligible_races"],x["formula"]))
top=rows[:30];O.mkdir(parents=True,exist_ok=True)
summary={"date":"20261002","rule":"係数なし。積、単純和、相関コア積+独立要素和。","tested_candidates":len(rows),"production_weights_changed":False,"top30":top}
(O/"unweighted_formula_top30_20261002.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
