from __future__ import annotations
import csv,itertools,json
from collections import defaultdict
from pathlib import Path

DATES=["20260930","20261001","20261002","20261003","20261004","20261005"]
OUT=Path("evaluations/ai_score_freeform_v4")
REV={"etime","est"}
FEATURES=["cw","c2","c3","grade","nat2","motor_win","motor_top3","boat2","boat3","etime","est"]

def F(x):
 try:return float(x)
 except:return None
def I(x):
 try:return int(float(x))
 except:return None
def load(d):
 p=Path(f"evaluations/pdca_datasets/{d}/comparison_dataset_{d}.csv"); rr=defaultdict(list)
 if not p.exists():return rr
 with p.open(encoding="utf-8-sig",newline="") as h:
  for r in csv.DictReader(h):
   z={k:F(r.get(k)) for k in FEATURES}; z["boat"]=I(r.get("boat")); z["finish"]=I(r.get("finish"))
   rr[r["race_id"]].append(z)
 return rr
def rank(bs,k):
 good=[b for b in bs if b.get(k) is not None]
 if len(good)<2:return {b["boat"]:.5 for b in bs}
 o=sorted(good,key=lambda b:((b[k] if k in REV else -b[k]),b["boat"]))
 m={b["boat"]:1-i/max(1,len(o)-1) for i,b in enumerate(o)}
 for b in bs:m.setdefault(b["boat"],.5)
 return m
def maps(bs):return {k:rank(bs,k) for k in FEATURES}
def win(R,q):
 return (R["cw"][q]**1.7)*(.70+.30*R["grade"][q])*(.75+.25*R["nat2"][q])*(.85+.15*(.4*R["motor_win"][q]+.6*R["motor_top3"][q]))*(.90+.10*R["etime"][q])*(.92+.08*R["est"][q])
def second(R,q):
 return .26*R["c2"][q]+.20*R["c3"][q]+.08*R["cw"][q]+.09*R["grade"][q]+.07*R["nat2"][q]+.13*R["motor_top3"][q]+.05*R["boat3"][q]+.06*R["etime"][q]+.06*R["est"][q]
def third(R,q):
 return .30*R["c3"][q]+.16*R["c2"][q]+.07*R["grade"][q]+.06*R["nat2"][q]+.15*R["motor_top3"][q]+.08*R["boat3"][q]+.09*R["etime"][q]+.09*R["est"][q]
def tickets(bs):
 R=maps(bs); W={q:win(R,q) for q in range(1,7)};S={q:second(R,q) for q in range(1,7)};T={q:third(R,q) for q in range(1,7)}
 rows=[]
 for a,b,c in itertools.permutations(range(1,7),3):
  base=(W[a]**1.30)*(max(.001,S[b])**1.00)*(max(.001,T[c])**.90)
  # Upset evidence deliberately differs from normal hit logic.
  # Reward non-obvious heads only when live/course/machine evidence jointly supports them.
  head_upset=(.34*R["etime"][a]+.24*R["est"][a]+.20*R["motor_top3"][a]+.12*R["cw"][a]+.10*R["grade"][a])
  tail_chaos=(.45*R["c3"][b]+.25*R["motor_top3"][b]+.30*R["c3"][c])
  upset=base*(.55+.45*head_upset)*(.65+.35*tail_chaos)
  rows.append({"combo":(a,b,c),"normal":base,"upset":upset})
 rows.sort(key=lambda x:(-x["normal"],x["combo"]))
 normal=rows[:8]; used={x["combo"] for x in normal}
 # Four longshot slots are selected from plausible non-core combinations.
 # True odds are intentionally not used here until pre-race odds ingestion is validated.
 pool=[x for x in rows[8:40] if x["combo"] not in used]
 pool.sort(key=lambda x:(-x["upset"],x["combo"]))
 upset=pool[:4]
 return normal,upset,rows[:12]
def main():
 data={d:load(d) for d in DATES}
 daily={}; total={k:0 for k in ["races","normal8_hits","upset4_hits","combined12_hits","top12_score_hits"]}
 for d in DATES:
  z={k:0 for k in total}
  for bs in data[d].values():
   if len(bs)!=6:continue
   actual=tuple(b["boat"] for b in sorted(bs,key=lambda x:(x["finish"],x["boat"])))[:3]
   n,u,t=tickets(bs); z["races"]+=1
   z["normal8_hits"]+=actual in {x["combo"] for x in n}
   z["upset4_hits"]+=actual in {x["combo"] for x in u}
   z["combined12_hits"]+=actual in ({x["combo"] for x in n}|{x["combo"] for x in u})
   z["top12_score_hits"]+=actual in {x["combo"] for x in t}
  for k in total:total[k]+=z[k]
  for k in ["normal8_hits","upset4_hits","combined12_hits","top12_score_hits"]:z[k+"_pct"]=round(100*z[k]/z["races"],2) if z["races"] else None
  daily[d]=z
 for k in ["normal8_hits","upset4_hits","combined12_hits","top12_score_hits"]:total[k+"_pct"]=round(100*total[k]/total["races"],2) if total["races"] else None
 result={"model":"ai_score_freeform_v4_120_direct_dual_book","production_changed":False,
  "concept":"score all 120 trifecta orders directly; normal 8 and upset 4 use different objectives",
  "normal8_role":"hit-rate core; highest direct joint-order scores",
  "upset4_role":"high-payout research sleeve; separate upset-evidence score among plausible non-core candidates",
  "budget":{"normal8_yen":800,"upset4_yen":400,"combined_yen":1200},
  "reporting":"normal8, upset4, combined12 are evaluated separately",
  "odds_status":"not yet used in V4 ranking until pre-race odds ingestion/key matching is validated; next stage adds capped odds/value without result leakage",
  "daily":daily,"pooled":total}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
