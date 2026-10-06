from __future__ import annotations
import csv,re,json
from collections import Counter,defaultdict
from pathlib import Path
DATES=["20260930","20261001","20261002","20261003"]
def read(p):
 with open(p,encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def fhold(s):
 m=re.search(r"\bF([1-9])\b",s or "")
 return int(m.group(1)) if m else 0
def main():
 groups=Counter();examples=defaultdict(list)
 for d in DATES:
  paths=[Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/base/program_entries_fl_{d}.csv"),Path(f"data/program_entries_fl_{d}.csv"),Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/program_entries_{d}.csv"),Path(f"data/program_entries_{d}.csv")]
  p=next((x for x in paths if x.exists()),None)
  if not p:continue
  for r in read(p):
   official=str(r.get("official_f_count","")).strip()
   n=int(float(official)) if official else fhold(r.get("series_results_raw",""))
   source="official_f_count" if official else "legacy_series_results_raw"
   groups[f"{source}:F{min(n,2)}" if n else f"{source}:F0"]+=1
   if n and len(examples[f"F{min(n,2)}"])<5:examples[f"F{min(n,2)}"].append({"date":d,"race_id":r.get("race_id"),"boat":r.get("boat"),"registration_no":r.get("registration_no"),"series_results_raw":r.get("series_results_raw")})
 out={"definition":"Prefer official_f_count from program_entries_fl; legacy series_results_raw F1/F2 is fallback only","counts":groups,"examples":examples}
 q=Path("evaluations/f_hold_inventory_20260930_20261003");q.mkdir(parents=True,exist_ok=True);(q/"summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
