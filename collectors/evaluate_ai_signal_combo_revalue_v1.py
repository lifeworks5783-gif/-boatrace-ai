#!/usr/bin/env python3
from __future__ import annotations
import csv,json,re,math
from pathlib import Path
D="20261005";BET=100
MULT=[0.05,0.10,0.15,0.20,0.30,0.40,0.50,0.75,1.00]
def rid(v):return "".join(re.findall(r"\d",str(v or "")))
def ff(v):
 try:return float(v)
 except:return None
def ii(v):
 try:return int(float(v))
 except:return None
def main():
 base=Path("predictions/2026/10/05")
 data=json.loads((base/"live"/f"formation_predictions_final_{D}.json").read_text(encoding="utf-8"))
 live={}
 with (base/"live"/f"live_predictions_final_{D}.csv").open(encoding="utf-8-sig",newline="") as fh:
  for r in csv.DictReader(fh):live.setdefault(rid(r.get("race_id")),[]).append(r)
 truth={};pay={}
 with Path(f"archive/2026/10/05/boat_results_{D}_all.csv").open(encoding="utf-8-sig",newline="") as fh:
  top={}
  for r in csv.DictReader(fh):
   k=rid(r.get("race_id"));fin=ii(r.get("finish"));b=ii(r.get("boat"))
   if fin in (1,2,3):top.setdefault(k,[]).append((fin,b))
 for k,v in top.items():
  v=sorted(v)
  if len(v)>=3:truth[k]="-".join(str(x[1]) for x in v[:3])
 with Path(f"archive/2026/10/05/results_{D}_all.csv").open(encoding="utf-8-sig",newline="") as fh:
  for r in csv.DictReader(fh):
   k=rid(r.get("race_id"))
   for key in ("trifecta_pay","trifecta_payout","sanrentan_pay","3rentan_pay"):
    if r.get(key) not in (None,""):pay[k]=ii(str(r[key]).replace(",","")) or 0;break
 rows=[]
 for race in data.get("races") or []:
  k=rid(race.get("race_id"));ai=race.get("ai_score_prediction") or {};a=truth.get(k)
  all120=ai.get("all_120_combinations") or []
  if not a or not all120:continue
  lr=live.get(k,[]);ranked=sorted(lr,key=lambda x:ii(x.get("rank")) or 99);top3={ii(x.get("boat")) for x in ranked[:3]}
  signals={}
  for r in lr:
   s,m,b=ff(r.get("score")),ff(r.get("morning_score_reference")),ii(r.get("boat"))
   if None not in (s,m,b) and s-m>=10 and b not in top3:signals[b]=s-m
  rows.append((k,a,pay.get(k,0),all120,signals))
 def calc(mult):
  hit=ret=pts=resc=lost=trig=manshu=0;details=[]
  for k,a,p,all120,sigs in rows:
   base=[x["combination"] for x in all120[:8]];chosen=base
   if sigs:
    trig+=1;sc=[]
    for idx,x in enumerate(all120):
     parts=tuple(map(int,x["combination"].split("-")));bonus=0.0
     # Rebuild combination AI evaluation only: continuous bonus from actual rise amount.
     # 2nd signal slightly stronger than 3rd; 1st is not promoted in V2.
     if parts[1] in sigs:bonus += mult*sigs[parts[1]]
     if parts[2] in sigs:bonus += mult*0.80*sigs[parts[2]]
     sc.append((ff(x["score"])+bonus,idx,x["combination"]))
    sc.sort(key=lambda z:(-z[0],z[1]));chosen=[z[2] for z in sc[:12]]
   bh=a in base;h=a in chosen;hit+=h;resc+=int(bool(sigs) and h and not bh);lost+=int(bool(sigs) and bh and not h)
   q=len(chosen);pts+=q*BET
   if h:ret+=p;manshu+=int(p>=10000)
   if sigs:details.append({"race_id":k,"signals":sigs,"base8_hit":bh,"new12_hit":h,"actual":a,"pay":p,"chosen":chosen})
  return {"multiplier":mult,"races":len(rows),"signal_races":trig,"hits":hit,"hit_rate_pct":round(100*hit/len(rows),2),"investment":pts,"return":ret,"roi_pct":round(100*ret/pts,2),"rescued":resc,"lost":lost,"manshu":manshu,"details":details}
 basehits=sum(a in [x["combination"] for x in all120[:8]] for _,a,_,all120,_ in rows)
 baseinv=len(rows)*800
 baseret=sum(p for _,a,p,all120,_ in rows if a in [x["combination"] for x in all120[:8]])
 tests=[calc(m) for m in MULT]
 out={"production_changed":False,"date":D,"method":"recalculate combination AI evaluation only on signal races; original combo score + multiplier*rise for signal boat in 2nd, 0.8*multiplier*rise in 3rd; top12; boat scores unchanged","baseline8":{"races":len(rows),"hits":basehits,"hit_rate_pct":round(100*basehits/len(rows),2),"investment":baseinv,"return":baseret,"roi_pct":round(100*baseret/baseinv,2)},"tests":tests}
 p=Path("evaluations/2026/10/05/ai_signal_combo_revalue_v1.json");p.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({"baseline8":out["baseline8"],"tests":[{k:v for k,v in x.items() if k!="details"} for x in tests]},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
