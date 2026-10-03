#!/usr/bin/env python3
import json
from pathlib import Path
from collectors import build_morning_prediction as morning
DATE="20261003"; base=Path("predictions/2026/10/03/live"); final_path=base/f"live_predictions_final_{DATE}.json"; snap_root=base/"snapshots"
def norm(v): return str(v or "").replace("-","")
def factor(b,ranks):
    st=b.get("exhibition_st")
    if b.get("exhibition_f") or (st is not None and float(st)<0): return .70
    return {1:1.10,2:1.06,3:1.03,4:1.00,5:.97,6:.94}.get(ranks.get(int(b["boat"])),1.0)
snaps={}
for d in sorted(snap_root.iterdir()):
    p=d/f"live_predictions_current_{DATE}.json"
    if p.exists():
        for r in json.loads(p.read_text(encoding="utf-8")).get("races",[]): snaps[norm(r.get("race_id"))]=r
data=json.loads(final_path.read_text(encoding="utf-8")); repaired=[]
for race in data.get("races",[]):
    if not any(float(b.get("score") or 0)==0 for b in race.get("boats",[])): continue
    rid=norm(race.get("race_id")); src=snaps.get(rid)
    if not src: continue
    boats=src.get("boats",[]); eligible=[b for b in boats if not b.get("exhibition_f") and b.get("exhibition_st") is not None and float(b["exhibition_st"])>=0]
    eligible.sort(key=lambda b:(float(b["exhibition_st"]),int(b["boat"]))); ranks={int(b["boat"]):i+1 for i,b in enumerate(eligible)}
    new=[]
    for b in boats:
        lane=int(b["boat"]); course=b.get("exhibition_course") or lane; rc=morning.racer_course_score(b.get("registration_no"),course); gs=morning.GRADE_PRIOR.get(str(b.get("grade") or "").strip().upper())
        score=round(rc*gs*factor(b,ranks)*100,2) if rc is not None and gs is not None else round(float(b.get("morning_score_reference") or b.get("score") or 0),2)
        nb=dict(b); nb["score"]=score; new.append(nb)
    new.sort(key=lambda x:(-x["score"],x["boat"]))
    for i,b in enumerate(new,1): b["rank"]=i
    race.update(src); race["boats"]=new; race["live_order"]=[b["boat"] for b in new]; race["top3_boats"]=[b["boat"] for b in new[:3]]; race["repair_note"]="zero-score repaired with current racer-course x grade x relative-ST formula"; repaired.append(rid)
final_path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8"); print("REPAIRED",len(repaired),repaired)
if len(repaired)!=19: raise SystemExit(f"expected 19 repairs, got {len(repaired)}")

# trigger repair workflow
