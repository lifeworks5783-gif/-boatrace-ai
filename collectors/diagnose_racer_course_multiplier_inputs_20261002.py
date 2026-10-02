#!/usr/bin/env python3
import json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];P=ROOT/"evaluations/2026/10/02/backfill_live/prediction_input_enriched_live_20261002.json";O=ROOT/"evaluations/2026/10/02/racer_course_7steps"
d=json.loads(P.read_text(encoding="utf-8")); names=["official","series","boat","exST","recent","motor","grade","course"]; vals={x:[] for x in names}; examples=[]
for race in d.get("races",[]):
 for b in race.get("boats",[]):
  com=b.get("components") or {}; row={"race_id":race.get("race_id"),"boat":b.get("boat")}
  for x in names:
   z=com.get(x) or {};v=z.get("raw_score_0_1");row[x]=v
   if isinstance(v,(int,float)):vals[x].append(float(v))
  if len(examples)<12:examples.append(row)
summary={}
for x,a in vals.items():
 summary[x]={"count":len(a),"missing":sum(len(r.get("boats",[])) for r in d.get("races",[]))-len(a),"unique":len(set(a)),"min":min(a) if a else None,"max":max(a) if a else None,"mean":round(statistics.mean(a),6) if a else None}
out={"races":len(d.get("races",[])),"components":summary,"examples":examples,"diagnosis":"If count=0, multiplier evaluator fallback 0.5 makes that factor constant and cannot change ranking."}
O.mkdir(parents=True,exist_ok=True);(O/"multiplier_input_diagnosis_20261002.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(out,ensure_ascii=False,indent=2))
