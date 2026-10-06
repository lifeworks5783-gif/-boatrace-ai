#!/usr/bin/env python3
import csv,json,re,itertools
from pathlib import Path
D="20261005"
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
 with (base/"live"/f"live_predictions_final_{D}.csv").open(encoding="utf-8-sig",newline="") as f:
  for r in csv.DictReader(f):live.setdefault(rid(r.get("race_id")),[]).append(r)
 truth={};pay={}
 with Path(f"archive/2026/10/05/boat_results_{D}_all.csv").open(encoding="utf-8-sig",newline="") as f:
  z={}
  for r in csv.DictReader(f):
   if ii(r.get("finish")) in (1,2,3):z.setdefault(rid(r.get("race_id")),[]).append((ii(r["finish"]),ii(r["boat"])))
  for k,v in z.items():
   if len(v)>=3:truth[k]="-".join(str(b) for _,b in sorted(v)[:3])
 with Path(f"archive/2026/10/05/results_{D}_all.csv").open(encoding="utf-8-sig",newline="") as f:
  for r in csv.DictReader(f):
   for key in ("trifecta_pay","trifecta_payout","sanrentan_pay","3rentan_pay"):
    if r.get(key):
     pay[rid(r.get("race_id"))]=ii(str(r[key]).replace(",","")) or 0;break
 rows=[]
 for race in data.get("races",[]):
  k=rid(race.get("race_id"));all120=(race.get("ai_score_prediction") or {}).get("all_120_combinations") or []
  if k not in truth or not all120:continue
  lr=live.get(k,[]);ranked=sorted(lr,key=lambda x:ii(x.get("rank")) or 99);top3={ii(x.get("boat")) for x in ranked[:3]};sig={}
  for r in lr:
   s,m,b=ff(r.get("score")),ff(r.get("morning_score_reference")),ii(r.get("boat"))
   if None not in (s,m,b) and s-m>=10 and b not in top3:sig[b]={"rise":s-m,"rank":ii(r.get("rank")) or 99}
  rows.append((k,truth[k],pay.get(k,0),all120,sig))
 sigrows=[x for x in rows if x[4]]
 # Search general rules only. Position weights and rank-based attenuation; no result-specific race rules.
 pos1=[0,.10,.20,.30,.40,.50,.75,1.0]
 pos2=[.4,.6,.8,1.0,1.2,1.5]
 pos3=[.4,.6,.8,1.0,1.2,1.5]
 mult=[.25,.5,.75,1.0,1.25,1.5,2.0]
 rank5=[.5,.7,.85,1.0]
 rank6=[.35,.5,.7,1.0]
 cand=[]
 for w1,w2,w3,mul,r5,r6 in itertools.product(pos1,pos2,pos3,mult,rank5,rank6):
  sig_hits=ret=manshu=0; hitids=[]; lostids=[]; rescuedids=[]
  for k,a,p,all120,sigs in sigrows:
   base8=[x["combination"] for x in all120[:8]]; scored=[]
   for idx,x in enumerate(all120):
    parts=tuple(map(int,x["combination"].split("-")));bonus=0
    for pos,b in enumerate(parts):
     if b in sigs:
      att=1 if sigs[b]["rank"]<=4 else r5 if sigs[b]["rank"]==5 else r6
      bonus+=mul*sigs[b]["rise"]*(w1,w2,w3)[pos]*att
    scored.append((ff(x["score"])+bonus,idx,x["combination"]))
   scored.sort(key=lambda z:(-z[0],z[1]));ch=[x[2] for x in scored[:12]]
   h=a in ch;bh=a in base8
   if h:sig_hits+=1;ret+=p;manshu+=p>=10000;hitids.append(k)
   if bh and not h:lostids.append(k)
   if h and not bh:rescuedids.append(k)
  # primary: retain >=14 current signal hits; then maximize hits, minimize lost, maximize return
  if sig_hits>=14:cand.append({"w1":w1,"w2":w2,"w3":w3,"mult":mul,"rank5":r5,"rank6":r6,"signal_hits":sig_hits,"signal_hit_rate_pct":round(100*sig_hits/len(sigrows),2),"lost_baseline_signal_hits":len(lostids),"rescued_vs_base8":len(rescuedids),"return_signal_races":ret,"manshu":manshu,"hit_ids":hitids,"lost_ids":lostids})
 cand.sort(key=lambda x:(-x["signal_hits"],x["lost_baseline_signal_hits"],-x["return_signal_races"]))
 best=cand[:30]
 out={"production_changed":False,"date":D,"signal_races":len(sigrows),"search_space":len(pos1)*len(pos2)*len(pos3)*len(mult)*len(rank5)*len(rank6),"constraint":"general rules only; signal hits >=14; no race/result-specific forced insertion","best":best}
 Path("evaluations/2026/10/05/ai_signal_allocation_search_v2.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({**{k:v for k,v in out.items() if k!="best"},"best5":best[:5]},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
