#!/usr/bin/env python3
import csv,json,os
from collections import defaultdict
DATES=["20260930","20261001","20261002","20261003","20261004","20261005"]
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
def live_scores(rs):
 s=struct(rs,True); tr=rank({I(r["boat"]):F(r["etime"]) for r in rs if F(r["etime"]) is not None},True)
 # Current provisional V2 personal-ST-delta is not reproducible from daily dataset alone; for F diagnosis,
 # transitions use saved reusable baseline structural+time+legacy ST ranking consistently across all dates.
 sr=rank({I(r["boat"]):F(r["est"]) for r in rs if F(r["est"]) is not None and not (r["exhibition_st_flag"] or "").strip() and F(r["est"])>=0},True)
 return {I(r["boat"]):.80*s[I(r["boat"])]+.06*tr.get(I(r["boat"]),.5)+.14*sr.get(I(r["boat"]),.5) for r in rs}
agg={"F0":{"boats":0,"wins":0,"top3":0,"finish_sum":0},"F1":{"boats":0,"wins":0,"top3":0,"finish_sum":0},"F2+":{"boats":0,"wins":0,"top3":0,"finish_sum":0}}
days={}; trans=defaultdict(int); predF=defaultdict(lambda:{"races":0,"hits":0}); actualF=defaultdict(lambda:{"races":0,"hits":0})
for d in DATES:
 rows=list(csv.DictReader(open(f"evaluations/pdca_datasets/{d}/comparison_dataset_{d}.csv",encoding="utf-8-sig")))
 races=defaultdict(list)
 for r in rows:races[r["race_id"]].append(r)
 day={"races":0,"boats":{"F0":{"n":0,"wins":0,"top3":0},"F1":{"n":0,"wins":0,"top3":0},"F2+":{"n":0,"wins":0,"top3":0}},"oo":0,"ox":0,"xo":0,"xx":0,"ox_with_fholder":0,"ox_fholder_in_live_top3":0}
 for rid,rs in races.items():
  if len(rs)!=6:continue
  valid=[r for r in rs if I(r["finish"]) in (1,2,3)]
  if len(valid)!=3:continue
  day["races"]+=1; aset={I(r["boat"]) for r in valid}
  for r in rs:
   fin=I(r["finish"]);fc=I(r["racer_f90_count"]) or 0;g="F0" if fc==0 else ("F1" if fc==1 else "F2+")
   if fin is not None:
    agg[g]["boats"]+=1;agg[g]["wins"]+=fin==1;agg[g]["top3"]+=fin<=3;agg[g]["finish_sum"]+=fin
    day["boats"][g]["n"]+=1;day["boats"][g]["wins"]+=fin==1;day["boats"][g]["top3"]+=fin<=3
  ms=struct(rs,False); morning=sorted(ms,key=lambda b:(-ms[b],b)); mh=set(morning[:3])==aset
  ls=live_scores(rs); live=sorted(ls,key=lambda b:(-ls[b],b)); lh=set(live[:3])==aset
  key=("o" if mh else "x")+("o" if lh else "x");day[key]+=1;trans[key]+=1
  fboats={I(r["boat"]) for r in rs if (I(r["racer_f90_count"]) or 0)>=1}
  pcount=len(set(live[:3])&fboats); acount=len(aset&fboats)
  predF[pcount]["races"]+=1;predF[pcount]["hits"]+=lh
  actualF[acount]["races"]+=1;actualF[acount]["hits"]+=lh
  if key=="ox":
   if fboats:day["ox_with_fholder"]+=1
   if set(live[:3])&fboats:day["ox_fholder_in_live_top3"]+=1
 days[d]=day
summary={}
for g,x in agg.items():
 n=x["boats"];summary[g]={"boats":n,"win_pct":round(100*x["wins"]/n,2) if n else None,"top3_pct":round(100*x["top3"]/n,2) if n else None,"avg_finish":round(x["finish_sum"]/n,3) if n else None}
def conv(z):return {str(k):{"races":v["races"],"hit_pct":round(100*v["hits"]/v["races"],2) if v["races"] else None} for k,v in sorted(z.items())}
out={"definition":"Racer-owned F in prior 90d; separate from today's exhibition F. F2+ is sparse and reference only.","boat_performance":summary,"transitions":dict(trans),"predicted_top3_fholder_count":conv(predF),"actual_top3_fholder_count":conv(actualF),"dates":days}
os.makedirs("evaluations/racer_f_holdings",exist_ok=True);json.dump(out,open("evaluations/racer_f_holdings/summary.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print(json.dumps(out,ensure_ascii=False,indent=2))

# trigger
