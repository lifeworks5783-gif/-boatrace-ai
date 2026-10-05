#!/usr/bin/env python3
import csv,json,os
from collections import defaultdict
DATES=["20260930","20261001","20261002","20261003","20261004","20261005"]
PENS=[0,.0025,.005,.0075,.01,.015,.02,.03]
def F(x):
 try:return float(x)
 except:return None
def I(x):
 try:return int(float(x))
 except:return None
def rank(vals,low=False):
 a=sorted(vals.items(),key=lambda z:((z[1] if low else -z[1]),z[0]));n=len(a)
 return {k:(1-i/(n-1) if n>1 else .5) for i,(k,v) in enumerate(a)}
def struct(rs,live):
 specs=[("lw" if live else "cw",.16,False),("l2" if live else "c2",.08,False),("l3" if live else "c3",.12,False),("lst" if live else "cst",.04,True),("grade",.20,False),("nat2",.15,False),("motor_win",.08,False),("motor_top3",.12,False),("boat2",.025,False),("boat3",.025,False)]
 maps={k:rank({I(r["boat"]):F(r[k]) for r in rs if F(r[k]) is not None},low) for k,w,low in specs}
 return {I(r["boat"]):sum(w*maps[k].get(I(r["boat"]),.5) for k,w,low in specs) for r in rs}
out={}
for pen in PENS:
 total={"n":0,"t3":0,"t1":0,"exact":0};daily={}
 for d in DATES:
  rows=list(csv.DictReader(open(f"evaluations/pdca_datasets/{d}/comparison_dataset_{d}.csv",encoding="utf-8-sig")));races=defaultdict(list)
  for r in rows:races[r["race_id"]].append(r)
  n=t3=t1=exact=0
  for rid,rs in races.items():
   if len(rs)!=6:continue
   act=sorted([r for r in rs if I(r["finish"]) in (1,2,3)],key=lambda r:I(r["finish"]))
   if len(act)!=3:continue
   aset={I(r["boat"]) for r in act};s=struct(rs,True);tr=rank({I(r["boat"]):F(r["etime"]) for r in rs if F(r["etime"]) is not None},True);sr=rank({I(r["boat"]):F(r["est"]) for r in rs if F(r["est"]) is not None and not (r["exhibition_st_flag"] or "").strip() and F(r["est"])>=0},True)
   sc={}
   for r in rs:
    b=I(r["boat"]);fc=I(r["racer_f90_count"]) or 0
    sc[b]=.80*s[b]+.06*tr.get(b,.5)+.14*sr.get(b,.5)-pen*min(fc,1)
   pred=sorted(sc,key=lambda b:(-sc[b],b));n+=1;t3+=set(pred[:3])==aset;t1+=pred[0]==I(act[0]["boat"]);exact+=pred[:3]==[I(x["boat"]) for x in act]
  daily[d]={"n":n,"top3_pct":round(100*t3/n,2),"top1_pct":round(100*t1/n,2),"exact_pct":round(100*exact/n,2)}
  total["n"]+=n;total["t3"]+=t3;total["t1"]+=t1;total["exact"]+=exact
 out[str(pen)]={"top3_pct":round(100*total["t3"]/total["n"],2),"top1_pct":round(100*total["t1"]/total["n"],2),"exact_pct":round(100*total["exact"]/total["n"],2),"daily":daily}
os.makedirs("evaluations/racer_f_penalties",exist_ok=True);json.dump({"definition":"Sensitivity only: subtract fixed score points from F1+ racer; exhibition F separate. Uses reusable baseline for cross-date comparison.","results":out},open("evaluations/racer_f_penalties/summary.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print(json.dumps(out,ensure_ascii=False,indent=2))

# trigger
