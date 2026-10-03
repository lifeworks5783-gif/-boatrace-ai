from __future__ import annotations
import argparse,csv,json,subprocess,sys
from datetime import datetime,timedelta
from pathlib import Path
def nid(v): return "".join(c for c in (v or "") if c.isdigit())
def main():
 p=argparse.ArgumentParser();p.add_argument("--start",default="20260702");p.add_argument("--end",default="20261002");a=p.parse_args()
 s=datetime.strptime(a.start,"%Y%m%d");e=datetime.strptime(a.end,"%Y%m%d");report=[]
 d=s
 while d<=e:
  ds=d.strftime("%Y%m%d"); res=list(Path("archive").glob(f"*/*/*/boat_results_{ds}_all.csv"))
  if not res: d+=timedelta(days=1);continue
  pp=Path(f"data/program_entries_{ds}.csv")
  if not pp.exists():
   q=subprocess.run([sys.executable,"collectors/today_basic.py","--date",ds],capture_output=True,text=True)
   if q.returncode!=0:
    report.append({"date":ds,"status":"program_failed","error":q.stderr[-300:]});d+=timedelta(days=1);continue
  with pp.open(encoding="utf-8-sig",newline="") as h:
   pg={(nid(r.get("race_id")),int(r["boat"])):r for r in csv.DictReader(h) if r.get("boat")}
  for rp in res:
   with rp.open(encoding="utf-8-sig",newline="") as h: rows=list(csv.DictReader(h));fields=list(rows[0]) if rows else []
   for k in ["motor_no","motor_top2_rate","boat_no","boat_top2_rate"]:
    if k not in fields:fields.append(k)
   hit=0
   for r in rows:
    try:b=int(float(r.get("boat") or 0))
    except:b=0
    x=pg.get((nid(r.get("race_id")),b))
    if x:
     for k in ["motor_no","motor_top2_rate","boat_no","boat_top2_rate"]:r[k]=x.get(k,"")
     if x.get("motor_no"):hit+=1
   with rp.open("w",encoding="utf-8-sig",newline="") as h:w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows(rows)
   report.append({"date":ds,"file":str(rp),"rows":len(rows),"motor_joined":hit,"status":"ok"})
  d+=timedelta(days=1)
 Path("evaluations/motor_history_backfill").mkdir(parents=True,exist_ok=True)
 Path("evaluations/motor_history_backfill/report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({"files":len(report),"ok":sum(x.get("status")=="ok" for x in report),"motor_joined":sum(x.get("motor_joined",0) for x in report)},ensure_ascii=False))
if __name__=="__main__":main()
