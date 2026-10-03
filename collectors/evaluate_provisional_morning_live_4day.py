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
def rankmap(bs,key,reverse=False):
 if len(bs)!=6 or any(b.get(key) is None for b in bs):return None
 o=sorted(bs,key=lambda b:((b[key] if reverse else -b[key]),b["boat"]))
 return {b["boat"]:1-j/5 for j,b in enumerate(o)}
def rankmap(bs,key,reverse=False):
 if len(bs)!=6 or any(b.get(key) is None for b in bs):return None
 o=sorted(bs,key=lambda b:((b[key] if reverse else -b[key]),b["boat"]))
 return {b["boat"]:1-j/5 for j,b in enumerate(o)}
def main():
 rows=archive();bd=defaultdict(list)
 for r in rows:bd[r.get("date")].append(r)
 results=[]
 for d in DATES:
  td=DT(d);prior=[r for r in rows if r.get("date") and td-timedelta(days=90)<=DT(r["date"])<td];pg=program(d);lv=live_entries(d)
  rg=defaultdict(list);rc=defaultdict(list);mg=defaultdict(list);bg=defaultdict(list)
  for r in prior:
   reg=r.get("registration_no","");c=I(r.get("course"));v=str(r.get("venue_code","")).zfill(2);m=I(r.get("motor_no"));bn=I(r.get("boat_no"))
   if reg:rg[reg].append(r)
   if reg and c:rc[(reg,c)].append(r)
   if m is not None:mg[(v,m)].append(r)
   if bn is not None:bg[(v,bn)].append(r)
  races=defaultdict(list)
  for r in bd[d]:
   bo=I(r.get("boat"));fi=I(r.get("finish"));rid=nid(r.get("race_id"))
   if bo not in range(1,7) or fi not in range(1,7):continue
   v=str(r.get("venue_code","")).zfill(2);reg=r.get("registration_no","");P=pg.get((rid,bo),{});L=lv.get((rid,bo),{})
   expected=bo;entry=I(L.get("exhibition_course")) or I(L.get("course")) or expected
   cs=stat(rc[(reg,expected)]);ls=stat(rc[(reg,entry)]);ms=stat(mg[(v,I(r.get("motor_no")))]) if I(r.get("motor_no")) is not None else {};bs=stat(bg[(v,I(r.get("boat_no")))]) if I(r.get("boat_no")) is not None else {}
   races[rid].append({"boat":bo,"finish":fi,"cw":cs.get("win"),"c2":cs.get("top2"),"c3":cs.get("top3"),"cst":cs.get("avg_st"),"lw":ls.get("win"),"l2":ls.get("top2"),"l3":ls.get("top3"),"lst":ls.get("avg_st"),"grade":GRADE.get(P.get("grade","")),"mw":ms.get("win"),"m3":ms.get("top3"),"b2":bs.get("top2"),"b3":bs.get("top3"),"etime":F(L.get("exhibition_time")),"est":F(L.get("exhibition_st"))})
  z={"date":d,"morning_n":0,"morning_hit":0,"live_n":0,"live_hit":0}
  for rid,bs in races.items():
   def block(keys):
    maps={}
    for k,w,rev in keys:
     q=rankmap(bs,k,rev)
     if q is None:return None
     maps[k]=(q,w)
    return {b["boat"]:sum(w*q[b["boat"]] for q,w in maps.values()) for b in bs}
   # provisional weights follow single-factor strength: racer course 50, grade 20, motor 12, boat 18.
   racer=block([("cw",.4,False),("c2",.2,False),("c3",.3,False),("cst",.1,True)])
   motor=block([("mw",.4,False),("m3",.6,False)]);boat=block([("b2",.5,False),("b3",.5,False)]);gr=rankmap(bs,"grade")
   if all(x is not None for x in [racer,motor,boat,gr]):
    sc={b:.50*racer[b]+.20*gr[b]+.12*motor[b]+.18*boat[b] for b in racer}
    z["morning_n"]+=1;z["morning_hit"]+=int(hit(bs,sc))
   # live: replace racer expected-course base with exhibition-entry-course base; morning structural blocks + exhibition time/ST.
   lr=block([("lw",.4,False),("l2",.2,False),("l3",.3,False),("lst",.1,True)]);et=rankmap(bs,"etime",True);es=rankmap(bs,"est",True)
   if all(x is not None for x in [lr,motor,boat,gr,et,es]):
    sc={b:.46*lr[b]+.18*gr[b]+.11*motor[b]+.15*boat[b]+.06*et[b]+.04*es[b] for b in lr}
    z["live_n"]+=1;z["live_hit"]+=int(hit(bs,sc))
  z["morning_top3_pct"]=round(100*z["morning_hit"]/z["morning_n"],2) if z["morning_n"] else None
  z["live_top3_pct"]=round(100*z["live_hit"]/z["live_n"],2) if z["live_n"] else None
  results.append(z)
 out=Path("evaluations/provisional_morning_live_4day");out.mkdir(parents=True,exist_ok=True)
 mv=[x["morning_top3_pct"] for x in results if x["morning_top3_pct"] is not None];lvv=[x["live_top3_pct"] for x in results if x["live_top3_pct"] is not None]
 summary={"definition":"TOP3 unordered exact set","provisional":True,"morning_weights":{"racer_course_base":50,"grade":20,"motor_base":12,"boat_base":18},"live_weights":{"racer_exhibition_entry_course_base":46,"grade":18,"motor_base":11,"boat_base":15,"exhibition_time":6,"exhibition_st":4},"by_date":results,"morning_daily_avg_pct":round(sum(mv)/len(mv),2),"morning_spread_pt":round(max(mv)-min(mv),2),"live_daily_avg_pct":round(sum(lvv)/len(lvv),2),"live_spread_pt":round(max(lvv)-min(lvv),2)}
 (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
