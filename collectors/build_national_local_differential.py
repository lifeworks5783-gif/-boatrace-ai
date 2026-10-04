#!/usr/bin/env python3
"""Persist national-vs-local racer performance differentials for PDCA diagnosis.
Collection only: does NOT change production prediction weights.
"""
import csv,json
from pathlib import Path
def f(v):
 try:return float(v)
 except:return None
def find_program(d):
 ps=[Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/program_entries_{d}.csv"),Path(f"data/program_entries_{d}.csv")]
 return next((p for p in ps if p.exists()),None)
def main():
 dates=sorted({p.stem.split("_")[-1] for p in Path("data").glob("program_entries_*.csv")})
 outdir=Path("evaluations/national_local_differential");outdir.mkdir(parents=True,exist_ok=True)
 summary={}
 for d in dates:
  p=find_program(d)
  if not p:continue
  with p.open(encoding="utf-8-sig",newline="") as h: rows=list(csv.DictReader(h))
  out=[]
  for r in rows:
   nw,nt,lw,lt=map(f,[r.get("national_win_rate"),r.get("national_top2_rate"),r.get("local_win_rate"),r.get("local_top2_rate")])
   out.append({"date":d,"venue_code":r.get("venue_code"),"race_id":r.get("race_id"),"boat":r.get("boat"),"registration_no":r.get("registration_no"),"racer_name":r.get("racer_name"),"national_win_rate":nw,"national_top2_rate":nt,"local_win_rate":lw,"local_top2_rate":lt,"local_minus_national_win":None if nw is None or lw is None else round(lw-nw,4),"local_minus_national_top2":None if nt is None or lt is None else round(lt-nt,4)})
  q=outdir/f"national_local_diff_{d}.csv"
  with q.open("w",encoding="utf-8",newline="") as h:
   w=csv.DictWriter(h,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
  summary[d]={"rows":len(out),"complete_top2_diff":sum(x["local_minus_national_top2"] is not None for x in out),"source":str(p)}
 (outdir/"summary.json").write_text(json.dumps({"purpose":"PDCA diagnostic accumulation only; production national_top2 weight remains 15%.","definition":{"local_minus_national_win":"local_win_rate - national_win_rate","local_minus_national_top2":"local_top2_rate - national_top2_rate"},"dates":summary},ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(summary,ensure_ascii=False))
if __name__=="__main__":main()

# workflow trigger marker: 20261005
