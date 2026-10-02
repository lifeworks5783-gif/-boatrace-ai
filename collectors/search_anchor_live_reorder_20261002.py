#!/usr/bin/env python3
import csv,json,math,itertools
from pathlib import Path
P=Path("evaluations/2026/10/02/backfill_live/live_predictions_final_20261002.json")
R=Path("archive/2026/10/02/boat_results_20261002_all.csv")
O=Path("evaluations/2026/10/02/anchor_live_reorder")
F={1:1.0,2:.72,3:.62,4:.58,5:.46,6:.38}
MORNING=[
("M1",("grade","series","boat"),("course","official")),
("M2",("grade","series"),("course","recent")),
("M3",("grade","venue","series"),("course","official")),
("M4",("grade","venue"),("course","recent")),
("M6",("motor","boat"),("course","official"))]
LIVE=[
("L1",("official","series","exST"),("course","recent")),
("L2",("official","boat","exST"),("course","recent")),
("L3",("official","venue","exST"),("course","recent")),
("L5",("official","motor","exST"),("course","recent")),
("L8",("motor","boat","live_course"),("course","official"))]
pred=json.loads(P.read_text(encoding="utf-8"));actual={}
with R.open(encoding="utf-8-sig",newline="") as f:
 for r in csv.DictReader(f):
  try:actual.setdefault(r["race_id"],[]).append((int(float(r["finish"])),int(float(r["boat"]))))
  except:pass
actual={k:[b for _,b in sorted(v)][:3] for k,v in actual.items() if len(v)==6}
def n(x):
 try:return float(x)
 except:return None
def v(b,k):
 lane=int(b["boat"])
 if k=="course":return F[lane]
 if k=="live_course":
  c=(b.get("components") or {}).get("course") or {};return n(c.get("raw_score_0_1")) if c.get("available") else None
 if k=="exTime":return n(b.get("exhibition_time"))
 c=(b.get("components") or {}).get(k) or {};return n(c.get("raw_score_0_1")) if c.get("available") else None
def score(boats,mul,add):
 keys=mul+add;rows=[]
 for b in boats:
  vals=[v(b,k) for k in keys]
  if any(x is None for x in vals):return None
  rows.append((int(b["boat"]),vals))
 out=[]
 for bn,vals in rows:out.append((math.prod(vals[:len(mul)])+sum(vals[len(mul):]),bn))
 return [bn for _,bn in sorted(out,key=lambda z:(-z[0],z[1]))]
races=[]
for r in pred["races"]:
 a=actual.get(r["race_id"].replace("-","_"))
 if a:races.append((a,r["boats"]))
rows=[]
for mn,mm,ma in MORNING:
 for ln,lm,la in LIVE:
  e=t3=ex=one=0
  for a,boats in races:
   mr=score(boats,mm,ma);lr=score(boats,lm,la)
   if not mr or not lr:continue
   anchor=mr[0]
   # 1着は朝1位で固定。2・3着は直前順位から朝1位を除いた上位2艇。
   rest=[x for x in lr if x!=anchor][:2]
   p=[anchor]+rest
   e+=1;t3+=set(p)==set(a);ex+=p==a;one+=anchor==a[0]
  pct=lambda x:round(x/e*100,2) if e else None
  rows.append({"morning":mn,"live":ln,"formula":f"{mn}の1位固定 + {ln}で2・3位","eligible_races":e,"top3_matches":t3,"top3_alignment_pct":pct(t3),"exact_matches":ex,"exact_alignment_pct":pct(ex),"top1_matches":one,"top1_accuracy_pct":pct(one)})
rows.sort(key=lambda x:(-(x["top3_alignment_pct"] or -1),-(x["exact_alignment_pct"] or -1),-(x["top1_accuracy_pct"] or -1)))
O.mkdir(parents=True,exist_ok=True)
(O/"anchor_live_reorder_20261002.json").write_text(json.dumps({"date":"20261002","rule":"朝式の1位を固定し、直前式で残りの上位2艇を選ぶ。係数なし。","results":rows},ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(rows,ensure_ascii=False,indent=2))
