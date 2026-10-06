from __future__ import annotations
import csv,json,math
from collections import defaultdict
from pathlib import Path
DATES=["20260930","20261001","20261002","20261003","20261004","20261005"]
OUT=Path("evaluations/rising_boat_top3_features_v1")
def F(x):
 try:return float(x)
 except:return None
def I(x):
 try:return int(float(x))
 except:return None
def load(d):
 p=Path(f"evaluations/pdca_datasets/{d}/comparison_dataset_{d}.csv");rr=defaultdict(list)
 if not p.exists():return rr
 with p.open(encoding="utf-8-sig",newline="") as h:
  for r in csv.DictReader(h):
   z={k:F(v) for k,v in r.items() if k!="race_id"};z["boat"]=I(r["boat"]);z["finish"]=I(r["finish"]);rr[r["race_id"]].append(z)
 return rr
def rank(bs,k,lower=False):
 good=[b for b in bs if b.get(k) is not None]
 if len(good)<2:return {b["boat"]:.5 for b in bs}
 o=sorted(good,key=lambda b:((b[k] if lower else -b[k]),b["boat"]))
 m={b["boat"]:1-i/max(1,len(o)-1) for i,b in enumerate(o)}
 for b in bs:m.setdefault(b["boat"],.5)
 return m
def scores(bs):
 R={k:rank(bs,k,lo) for k,lo in [("cw",0),("c2",0),("c3",0),("grade",0),("nat2",0),("motor_win",0),("motor_top3",0),("boat3",0),("etime",1),("est",1)]}
 M={};L={}
 for b in bs:
  q=b["boat"];base=(R["cw"][q]**1.55)*(0.72+.28*R["grade"][q])*(0.78+.22*R["nat2"][q]);base*=.86+.14*(.4*R["motor_win"][q]+.6*R["motor_top3"][q]);M[q]=base;L[q]=base*(.90+.10*R["etime"][q])*(.92+.08*R["est"][q])
 raw={q:math.log(max(L[q],1e-12)/max(M[q],1e-12)) for q in L};avg=sum(raw.values())/6;mom={q:raw[q]-avg for q in raw}
 scale=max(1e-9,max(abs(x) for x in mom.values()));sig={q:mom[q]/scale for q in mom}
 mr={q:i+1 for i,(q,_) in enumerate(sorted(M.items(),key=lambda x:(-x[1],x[0])))};lr={q:i+1 for i,(q,_) in enumerate(sorted(L.items(),key=lambda x:(-x[1],x[0])))}
 return R,M,L,sig,mr,lr
def avg(rows,k):
 x=[r[k] for r in rows if r.get(k) is not None];return round(sum(x)/len(x),4) if x else None
def summarize(rows):
 keys=["boat","morning_rank","live_rank","signal","cw_r","c3_r","grade_r","nat2_r","motor_top3_r","etime_r","est_r","cw","c3","grade","nat2","motor_top3","etime","est"]
 return {"n":len(rows),"top3_n":sum(r["top3"] for r in rows),"top3_rate_pct":round(100*sum(r["top3"] for r in rows)/len(rows),2) if rows else None,"win_rate_pct":round(100*sum(r["win"] for r in rows)/len(rows),2) if rows else None,"avg":{k:avg(rows,k) for k in keys}}
def main():
 rows=[]
 for d in DATES:
  for rid,bs in load(d).items():
   if len(bs)!=6:continue
   R,M,L,S,MR,LR=scores(bs)
   for b in bs:
    q=b["boat"]
    if S[q]<=0:continue
    rows.append({"date":d,"race_id":rid,"boat":q,"finish":b["finish"],"top3":int((b["finish"] or 99)<=3),"win":int(b["finish"]==1),"morning_rank":MR[q],"live_rank":LR[q],"signal":S[q],"cw_r":R["cw"][q],"c3_r":R["c3"][q],"grade_r":R["grade"][q],"nat2_r":R["nat2"][q],"motor_top3_r":R["motor_top3"][q],"etime_r":R["etime"][q],"est_r":R["est"][q],"cw":b.get("cw"),"c3":b.get("c3"),"grade":b.get("grade"),"nat2":b.get("nat2"),"motor_top3":b.get("motor_top3"),"etime":b.get("etime"),"est":b.get("est")})
 hit=[r for r in rows if r["top3"]];miss=[r for r in rows if not r["top3"]]
 # Signal tiers and live-rank cross table
 tiers=[("weak",0,.25),("medium",.25,.5),("strong",.5,.75),("very_strong",.75,1.01)]
 tierout={}
 for name,a,b in tiers:
  z=[r for r in rows if a<r["signal"]<=b];tierout[name]=summarize(z)
 cross={}
 for rk in [(1,3),(4,6)]:
  for name,a,b in tiers:
   z=[r for r in rows if rk[0]<=r["live_rank"]<=rk[1] and a<r["signal"]<=b]
   cross[f"live{rk[0]}-{rk[1]}_{name}"]=summarize(z)
 # Feature lift among rising boats: top/bottom half by race-relative rank.
 lifts={}
 for k in ["cw_r","c3_r","grade_r","nat2_r","motor_top3_r","etime_r","est_r"]:
  hi=[r for r in rows if r[k]>=.6];lo=[r for r in rows if r[k]<=.4]
  lifts[k]={"high":summarize(hi),"low":summarize(lo),"top3_lift_pp":round((summarize(hi)["top3_rate_pct"] or 0)-(summarize(lo)["top3_rate_pct"] or 0),2)}
 out={"production_changed":False,"dates":DATES,"definition":"rising = positive race-centered reconstructed morning-to-live momentum; v1 uses saved no-leakage factors because exact historical displayed scores are incomplete","all_rising":summarize(rows),"top3_rising":summarize(hit),"miss_rising":summarize(miss),"signal_tiers":tierout,"live_rank_x_signal":cross,"feature_lifts":lifts}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/"summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
 with (OUT/"boats.csv").open("w",encoding="utf-8-sig",newline="") as h:
  w=csv.DictWriter(h,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)
 print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
