#!/usr/bin/env python3
from __future__ import annotations
import csv,json,re
from pathlib import Path
D="20261005"; BET=100
def rid(v):return "".join(re.findall(r"\d",str(v or "")))
def f(v):
 try:return float(v)
 except:return None
def i(v):
 try:return int(float(v))
 except:return None
def main():
 base=Path("predictions/2026/10/05"); jp=base/"live"/f"formation_predictions_final_{D}.json"
 data=json.loads(jp.read_text(encoding="utf-8"))
 live={}
 with (base/"live"/f"live_predictions_final_{D}.csv").open(encoding="utf-8-sig",newline="") as fh:
  for r in csv.DictReader(fh):live.setdefault(rid(r["race_id"]),[]).append(r)
 truth={};pay={}
 with Path(f"archive/2026/10/05/results_{D}_all.csv").open(encoding="utf-8-sig",newline="") as fh:
  for r in csv.DictReader(fh):
   k=rid(f'{D}{int(r["venue_code"]):02d}{int(r["race"]):02d}')
   truth[k]=str(r.get("trifecta") or "").strip();pay[k]=i(r.get("trifecta_pay")) or 0
 out=[];basehit=sighit=lost=rescued=trig=inv=ret=0
 for race in data.get("races") or []:
  k=rid(race.get("race_id")); ai=race.get("ai_score_prediction") or {}; all120=ai.get("all_120_combinations") or []
  if k not in truth or not all120:continue
  orig=[x["combination"] for x in all120[:8]]; rows=live.get(k,[])
  holes=[]
  top3=[i(x["boat"]) for x in sorted(rows,key=lambda x:i(x["rank"]) or 99)[:3]]
  for r in rows:
   s,m=f(r.get("score")),f(r.get("morning_score_reference"));b=i(r.get("boat"))
   if s is not None and m is not None and s-m>=10 and b not in top3:holes.append((b,s-m))
  sig=sorted(holes,key=lambda x:-x[1])
  if sig:
   trig+=1; hs={x[0] for x in sig}
   # Signal mode: keep AI 120 score order inside each class, but prioritize combos
   # where a signal boat is 2nd/3rd. Fill remaining slots by original AI rank.
   pri=[];rest=[]
   for x in all120:
    parts=tuple(map(int,x["combination"].split("-")))
    (pri if (parts[1] in hs or parts[2] in hs) else rest).append(x["combination"])
   chosen=(pri+rest)[:12]
  else:chosen=orig
  a=truth[k];bh=a in orig;sh=a in chosen;basehit+=bh;sighit+=sh
  if sig and sh and not bh:rescued+=1
  if sig and bh and not sh:lost+=1
  pts=len(chosen);inv+=pts*BET
  if sh:ret+=pay[k]
  out.append({"race_id":race.get("race_id"),"signal":sig,"base8_hit":bh,"signal_mode_hit":sh,"points":pts,"actual":a,"pay":pay[k],"chosen":chosen})
 n=len(out);base_inv=n*8*BET
 result={"production_changed":False,"date":D,"rule":"no signal: existing AI top8. signal: if TOP3-outside boat rises >=10 from saved morning reference, prioritize AI-120 combinations containing signal boat in 2nd/3rd, keep original AI score order within class, take 12 total.","races":n,"signal_races":trig,"base8":{"hits":basehit,"hit_rate_pct":round(basehit/n*100,2),"investment":base_inv},"signal12":{"hits":sighit,"hit_rate_pct":round(sighit/n*100,2),"investment":inv,"return":ret,"roi_pct":round(ret/inv*100,2)},"rescued":rescued,"lost":lost,"details":out}
 p=Path("evaluations/2026/10/05/ai_signal12_20261005.json");p.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps({k:v for k,v in result.items() if k!="details"},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
