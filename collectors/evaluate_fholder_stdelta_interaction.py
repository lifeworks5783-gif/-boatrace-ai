#!/usr/bin/env python3
import csv,json,os
from collections import defaultdict
DATES=["20260930","20261001","20261002","20261003","20261004","20261005"]
TH=[0,.005,.01,.015,.02,.03,.04,.05]
PEN=[.0025,.005,.0075,.01,.015,.02]
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
def delta_score(est,av):
 if est is None or av is None:return .5
 return max(0,min(1,.5-(est-av)/.12))
prepared=[]
for d in DATES:
 rows=list(csv.DictReader(open(f"evaluations/pdca_datasets/{d}/comparison_dataset_{d}.csv",encoding="utf-8-sig")));races=defaultdict(list)
 for r in rows:races[r["race_id"]].append(r)
 for rid,rs in races.items():
  if len(rs)!=6:continue
  act=sorted([r for r in rs if I(r["finish"]) in (1,2,3)],key=lambda r:I(r["finish"]))
  if len(act)!=3:continue
  aset={I(r["boat"]) for r in act};s=struct(rs,True);tr=rank({I(r["boat"]):F(r["etime"]) for r in rs if F(r["etime"]) is not None},True)
  boats=[]
  for r in rs:
   b=I(r["boat"]);est=F(r["est"]);av=F(r["lst"]);fc=I(r["racer_f90_count"]) or 0;isef=bool((r["exhibition_st_flag"] or "").strip()) or (est is not None and est<0)
   ds=.4 if isef else delta_score(est,av)
   diff=None if est is None or av is None or isef else est-av
   boats.append((b,.80*s[b]+.06*tr.get(b,.5)+.14*ds,fc,diff))
  prepared.append((d,aset,I(act[0]["boat"]),[I(x["boat"]) for x in act],boats))
def evalone(th,pen):
 n=t3=t1=exact=triggered=0;days=defaultdict(lambda:[0,0,0])
 for d,aset,winner,aorder,boats in prepared:
  sc={}
  for b,base,fc,diff in boats:
   hit=fc>=1 and diff is not None and diff>=th
   sc[b]=base-(pen if hit else 0);triggered+=hit
  pred=sorted(sc,key=lambda b:(-sc[b],b));n+=1;t3+=set(pred[:3])==aset;t1+=pred[0]==winner;exact+=pred[:3]==aorder
  days[d][0]+=1;days[d][1]+=set(pred[:3])==aset;days[d][2]+=pred[0]==winner
 return {"threshold":th,"penalty":pen,"n":n,"triggered_boats":triggered,"top3_pct":round(100*t3/n,2),"top1_pct":round(100*t1/n,2),"exact_pct":round(100*exact/n,2),"daily":{d:{"top3_pct":round(100*v[1]/v[0],2),"top1_pct":round(100*v[2]/v[0],2)} for d,v in days.items()}}
base=evalone(999,0)
res=[evalone(t,p) for t in TH for p in PEN]
res.sort(key=lambda x:(-x["top3_pct"],-x["top1_pct"],-x["exact_pct"]))
# descriptive interaction groups, no penalty
groups=defaultdict(lambda:{"n":0,"wins":0,"top3":0})
for d,aset,winner,aorder,boats in prepared:
 for b,base,fc,diff in boats:
  if fc<1:g="F0"
  elif diff is None:g="F1_diff_missing"
  elif diff<=-.02:g="F1_faster_0.02+"
  elif diff>=.02:g="F1_slower_0.02+"
  else:g="F1_near_avg"
  groups[g]["n"]+=1;groups[g]["wins"]+=b==winner;groups[g]["top3"]+=b in aset
desc={g:{**v,"win_pct":round(100*v["wins"]/v["n"],2),"top3_pct":round(100*v["top3"]/v["n"],2)} for g,v in groups.items()}
out={"definition":"Current provisional V2 baseline reconstructed as 80 structural + 6 exTime + 14 personal ST delta (using daily course avg ST proxy available in PDCA dataset); extra penalty only when racer F90>=1 and exhibition ST is slower than own average by threshold.","baseline":base,"interaction_groups":desc,"candidates":res}
os.makedirs("evaluations/fholder_stdelta_interaction",exist_ok=True);json.dump(out,open("evaluations/fholder_stdelta_interaction/summary.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print(json.dumps({"baseline":base,"groups":desc,"top15":res[:15]},ensure_ascii=False,indent=2))

# trigger
