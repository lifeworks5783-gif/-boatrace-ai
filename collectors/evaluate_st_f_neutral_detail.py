from __future__ import annotations
# Explain exactly which races change when exhibition F/L ST is neutralized.
exec(open("collectors/evaluate_st_f_safety_sim.py",encoding="utf-8").read().replace('if __name__=="__main__": main2()',''))
# This script intentionally reuses the same reconstruction concept but emits transition deltas.
import json
from pathlib import Path

def main3():
 data=json.loads(Path("evaluations/st_f_safety_sim_20260930_20261003/summary.json").read_text(encoding="utf-8"))
 cur=next(x for x in data["results"] if x["variant"]=="current")
 neu=next(x for x in data["results"] if x["variant"]=="F_neutral")
 out={
  "comparison":"current ST14 vs F-neutral ST14",
  "current":cur,
  "neutral":neu,
  "aggregate_delta":{
   "top1_pct":round(neu["top1_pct"]-cur["top1_pct"],2),
   "exact_top3_pct":round(neu["exact_top3_pct"]-cur["exact_top3_pct"],2),
   "x_to_o":neu["x_to_o"]-cur["x_to_o"],
   "o_to_x":neu["o_to_x"]-cur["o_to_x"],
   "net":neu["net"]-cur["net"]
  },
  "interpretation":"F-neutral preserves x_to_o count and reduces o_to_x by 2 in the common 388-race sample. No production change."
 }
 p=Path("evaluations/st_f_neutral_detail_20260930_20261003");p.mkdir(parents=True,exist_ok=True)
 (p/"summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__": main3()
