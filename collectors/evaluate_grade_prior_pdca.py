#!/usr/bin/env python3
import csv,json,os
from collections import defaultdict
DATES=["20260930","20261001","20261002","20261003","20261004"]
PRIORS={
"current":{"A1":1.00,"A2":.75,"B1":.45,"B2":.25},
"compressed":{"A1":1.00,"A2":.80,"B1":.55,"B2":.35},
"mild":{"A1":1.00,"A2":.78,"B1":.50,"B2":.30},
"steeper":{"A1":1.00,"A2":.70,"B1":.40,"B2":.20},
}
def csvr(p):
 with open(p,encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def rank(vals):
 valid=sorted([(k,v) for k,v in vals.items() if v is not None],key=lambda x:(-x[1],x[0]))
 if not valid:return {}
 r={valid[0][0]:.5} if len(valid)==1 else {k:1-i/(len(valid)-1) for i,(k,v) in enumerate(valid)}
 for k,v in vals.items():
  if v is None:r[k]=.5
 return r
out={}
for name,prior in PRIORS.items():
 A=defaultdict(float); by={}
 for d in DATES:
  pp=f"predictions/{d[:4]}/{d[4:6]}/{d[6:8]}/morning_predictions_{d}.json"; rp=f"archive/{d[:4]}/{d[4:6]}/{d[6:8]}/boat_results_{d}_all.csv"
  if not os.path.exists(pp) or not os.path.exists(rp):continue
  P=json.load(open(pp,encoding="utf-8")); truth=defaultdict(dict)
  for x in csvr(rp):
   try:truth[x["race_id"].replace("_","-")][int(x["boat"])]=int(float(x["finish"]))
   except:pass
  D=defaultdict(float)
  for race in P.get("races",[]):
   tr=truth.get(race["race_id"]); bs=race.get("boats",[])
   if not tr or len(bs)!=6:continue
   gr=rank({int(b["boat"]):prior.get(str(b.get("grade","")).upper()) for b in bs})
   if len(gr)!=6:continue
   scores={}
   for b in bs:
    boat=int(b["boat"]); comps=b.get("components",{})
    def c(k):return float((comps.get(k) or {}).get("raw_score_0_1",0))
    scores[boat]=100*(.40*c("racer_course")+.20*gr[boat]+.20*c("motor")+.05*c("boat")+.15*c("national_top2"))
   po=sorted(scores,key=lambda z:(-scores[z],z)); ao=sorted(tr,key=lambda z:(tr[z],z)); wr=po.index(ao[0])+1
   for Z in (A,D):
    Z["n"]+=1;Z["t1"]+=wr==1;Z["w2"]+=wr<=2;Z["w3"]+=wr<=3;Z["e3"]+=set(po[:3])==set(ao[:3]);Z["ord"]+=po[:3]==ao[:3];Z["rs"]+=wr
  by[d]={"n":int(D["n"]),"top1":round(100*D["t1"]/D["n"],2) if D["n"] else None,"exact_top3":round(100*D["e3"]/D["n"],2) if D["n"] else None}
 out[name]={"prior":prior,"n":int(A["n"]),"top1_pct":round(100*A["t1"]/A["n"],2),"winner_top2_pct":round(100*A["w2"]/A["n"],2),"winner_top3_pct":round(100*A["w3"]/A["n"],2),"exact_top3_pct":round(100*A["e3"]/A["n"],2),"ordered_top3_pct":round(100*A["ord"]/A["n"],2),"avg_winner_rank":round(A["rs"]/A["n"],4),"by_date":by}
os.makedirs("evaluations/grade_prior_pdca",exist_ok=True)
json.dump(out,open("evaluations/grade_prior_pdca/summary.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print(json.dumps(out,ensure_ascii=False,indent=2))
