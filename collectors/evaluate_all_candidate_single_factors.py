from __future__ import annotations
import csv,json,glob
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
DATES=["20260930","20261001","20261002","20261003"]
OUT=Path("evaluations/all_candidate_single_factors")
GRADE={"A1":1.0,"A2":.75,"B1":.45,"B2":.25}
def F(v):
 try:return float(v)
 except:return None
def I(v):
 try:return int(float(v))
 except:return None
def DT(v):return datetime.strptime(v,"%Y%m%d").date()
def nid(v):return "".join(c for c in (v or "") if c.isdigit())
def read(p):
 with open(p,encoding="utf-8-sig",newline="") as h:return list(csv.DictReader(h))
def archive():
 z=[]
 for p in Path("archive").glob("*/*/*/boat_results_*_all.csv"):z+=read(p)
 return z
def program(d):
 ps=[Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/program_entries_{d}.csv"),Path(f"data/program_entries_{d}.csv")]
 for p in ps:
  if p.exists():return {(nid(r.get("race_id")),I(r.get("boat"))):r for r in read(p)}
 return {}
def live_entries(d):
 ps=list(Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/live/backfill").glob(f"beforeinfo_entries_{d}.csv"))
 if not ps: ps=list(Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/live/snapshots").glob(f"*/beforeinfo_entries_{d}.csv"))
 best={}
 for p in ps:
  for r in read(p):
   k=(nid(r.get("race_id")),I(r.get("boat")))
   if k[0] and k[1] in range(1,7):best[k]=r
 return best
def stat(rs):
 fs=[I(r.get("finish")) for r in rs if I(r.get("finish")) in range(1,7)]
 sts=[F(r.get("st")) for r in rs if F(r.get("st")) is not None]
 if not fs:return {}
 return {"win":sum(x==1 for x in fs)/len(fs),"top2":sum(x<=2 for x in fs)/len(fs),"top3":sum(x<=3 for x in fs)/len(fs),"avg_finish":sum(fs)/len(fs),"avg_st":sum(sts)/len(sts) if sts else None}
def evaluate(races,key,reverse=False):
 n=t1=t3=ex=0
 for bs in races.values():
  if len(bs)!=6 or any(b.get(key) is None for b in bs):continue
  a=sorted(bs,key=lambda b:(b["finish"],b["boat"]))
  p=sorted(bs,key=lambda b:((b[key] if reverse else -b[key]),b["boat"]))
  n+=1;t1+=p[0]["boat"]==a[0]["boat"];t3+=set(x["boat"] for x in p[:3])==set(x["boat"] for x in a[:3]);ex+=[x["boat"] for x in p[:3]]==[x["boat"] for x in a[:3]]
 return {"races":n,"top1_pct":round(100*t1/n,2) if n else None,"top3_pct":round(100*t3/n,2) if n else None,"exact_pct":round(100*ex/n,2) if n else None}
def main():
 rows=archive();bd=defaultdict(list)
 for r in rows:bd[r.get("date")].append(r)
 combined=defaultdict(list)
 daily={}
 for d in DATES:
  td=DT(d);prior=[r for r in rows if r.get("date") and td-timedelta(days=90)<=DT(r["date"])<td];prior30=[r for r in rows if r.get("date") and td-timedelta(days=30)<=DT(r["date"])<td];pg=program(d);lv=live_entries(d)
  rg=defaultdict(list);rc=defaultdict(list);rv=defaultdict(list);vc=defaultdict(list);mg=defaultdict(list);mg30=defaultdict(list);bg=defaultdict(list)
  for r in prior:
   reg=r.get("registration_no","");c=I(r.get("course"));v=str(r.get("venue_code","")).zfill(2);m=I(r.get("motor_no"));bn=I(r.get("boat_no"))
   if reg:rg[reg].append(r)
   if reg and c:rc[(reg,c)].append(r)
   if reg:rv[(reg,v)].append(r)
   if c:vc[(v,c)].append(r)
   if m is not None:mg[(v,m)].append(r)
   if bn is not None:bg[(v,bn)].append(r)
  for r in prior30:
   v=str(r.get("venue_code","")).zfill(2);m=I(r.get("motor_no"))
   if m is not None:mg30[(v,m)].append(r)
  rr=defaultdict(list)
  for r in bd[d]:
   bo=I(r.get("boat"));fi=I(r.get("finish"))
   if bo not in range(1,7) or fi not in range(1,7):continue
   rid=nid(r.get("race_id"));v=str(r.get("venue_code","")).zfill(2);reg=r.get("registration_no","");P=pg.get((rid,bo),{});L=lv.get((rid,bo),{})
   rs=stat(rg[reg]);cs=stat(rc[(reg,bo)]);vs=stat(rv[(reg,v)]);vcs=stat(vc[(v,bo)]);ms=stat(mg[(v,I(r.get("motor_no")))]) if I(r.get("motor_no")) is not None else {};ms30=stat(mg30[(v,I(r.get("motor_no")))]) if I(r.get("motor_no")) is not None else {};bs=stat(bg[(v,I(r.get("boat_no")))]) if I(r.get("boat_no")) is not None else {}
   st=F(L.get("exhibition_st_seconds"));stflag=(L.get("exhibition_st_flag") or "").strip()
   b={"boat":bo,"finish":fi,"course_win":cs.get("win"),"course_top2":cs.get("top2"),"course_top3":cs.get("top3"),"course_avg_st":cs.get("avg_st"),"grade":GRADE.get(P.get("grade","")),"national_win":rs.get("win"),"national_top2":rs.get("top2"),"national_top3":rs.get("top3"),"national_avg_st":rs.get("avg_st"),"venue_win":vs.get("win"),"venue_top3":vs.get("top3"),"venue_course_win":vcs.get("win"),"venue_course_top2":vcs.get("top2"),"venue_course_top3":vcs.get("top3"),"motor_d30_win":ms30.get("win"),"motor_d30_top2":ms30.get("top2"),"motor_d30_top3":ms30.get("top3"),"motor_d90_win":ms.get("win"),"motor_d90_top2":ms.get("top2"),"motor_d90_top3":ms.get("top3"),"motor_official_top2":F(P.get("motor_top2_rate"))/100 if F(P.get("motor_top2_rate")) is not None else None,"boat_d90_win":bs.get("win"),"boat_d90_top2":bs.get("top2"),"boat_d90_top3":bs.get("top3"),"boat_official_top2":F(P.get("boat_top2_rate"))/100 if F(P.get("boat_top2_rate")) is not None else None,"exhibition_time":F(L.get("exhibition_time")),"exhibition_st":st,"exhibition_st_f_penalized":(1.0 if stflag=="F" else st) if st is not None else None,"f_flag":1.0 if stflag=="F" else 0.0 if L else None,"tilt":F(L.get("tilt")),"parts_changed":1.0 if (L.get("change_parts") or "").strip() else 0.0 if L else None}
   rr[rid].append(b);combined[rid].append(b)
  daily[d]=rr
 factors=[("course_win",False),("course_top2",False),("course_top3",False),("course_avg_st",True),("grade",False),("national_win",False),("national_top2",False),("national_top3",False),("national_avg_st",True),("venue_win",False),("venue_top3",False),("venue_course_win",False),("venue_course_top2",False),("venue_course_top3",False),("motor_d30_win",False),("motor_d30_top2",False),("motor_d30_top3",False),("motor_d90_win",False),("motor_d90_top2",False),("motor_d90_top3",False),("motor_official_top2",False),("boat_d90_win",False),("boat_d90_top2",False),("boat_d90_top3",False),("boat_official_top2",False),("exhibition_time",True),("exhibition_st",True),("exhibition_st_f_penalized",True),("f_flag",True),("tilt",False),("parts_changed",False)]
 out=[]
 for key,rev in factors:
  overall=evaluate(combined,key,rev)
  by_date={d:evaluate(daily.get(d,{}),key,rev) for d in DATES}
  vals=[v["top3_pct"] for v in by_date.values() if v["top3_pct"] is not None]
  avg=round(sum(vals)/len(vals),2) if vals else None
  spread=round(max(vals)-min(vals),2) if vals else None
  out.append({"factor":key,"direction":"lower_better" if rev else "higher_better","by_date":by_date,"daily_top3_avg_pct":avg,"top3_spread_pt":spread,"pooled":overall})
 OUT.mkdir(parents=True,exist_ok=True)
 with (OUT/"summary.csv").open("w",encoding="utf-8",newline="") as h:
  w=csv.DictWriter(h,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
 (OUT/"summary.json").write_text(json.dumps({"dates":DATES,"definition":"TOP3 = unordered predicted top3 set exactly equals actual top3 set","notes":["race-constant weather/water fields cannot rank six boats as standalone factors; require interaction models","exhibition entry course is a base-course replacement, not a scalar standalone score","parts_changed and tilt may have many ties; results are descriptive only"],"results":out},ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
