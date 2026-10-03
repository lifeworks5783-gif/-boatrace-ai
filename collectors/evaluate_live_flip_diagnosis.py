from __future__ import annotations
exec(open("collectors/evaluate_live_logic_stage2_shortlist.py",encoding="utf-8").read().replace('if __name__=="__main__":main()',''))
# Dedicated flip diagnosis, rebuilt with same cached logic but stores race-level diagnostics.
import csv,json
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
def main2():
 rows=[]
 for p in Path("archive").glob("*/*/*/boat_results_*_all.csv"):rows+=read(p)
 bd=defaultdict(list)
 for r in rows:bd[r.get("date")].append(r)
 cases=[]
 for d in DATES:
  td=DT(d); prior=[r for r in rows if r.get("date") and td-timedelta(days=90)<=DT(r["date"])<td]; pg=load_program(d); lv=load_live(d)
  rg=defaultdict(list);rc=defaultdict(list);mg=defaultdict(list);bg=defaultdict(list)
  for r in prior:
   reg=r.get("registration_no","");c=I(r.get("course"));v=str(r.get("venue_code","")).zfill(2);m=I(r.get("motor_no"));b=I(r.get("boat_no"))
   if reg:rg[reg].append(r)
   if reg and c:rc[(reg,c)].append(r)
   if m is not None:mg[(v,m)].append(r)
   if b is not None:bg[(v,b)].append(r)
  races=defaultdict(list)
  for r in bd[d]:
   bo=I(r.get("boat"));fi=I(r.get("finish"));rid=nid(r.get("race_id"))
   if bo not in range(1,7) or fi not in range(1,7):continue
   v=str(r.get("venue_code","")).zfill(2);reg=r.get("registration_no","");P=pg.get((rid,bo),{});Q=lv.get((rid,bo),{});entry=I(Q.get("exhibition_course")) or bo
   rs=stat(rg[reg]);cs=stat(rc[(reg,bo)]);ls=stat(rc[(reg,entry)]);ms=stat(mg[(v,I(r.get("motor_no")))]) if I(r.get("motor_no")) is not None else {};bt=stat(bg[(v,I(r.get("boat_no")))]) if I(r.get("boat_no")) is not None else {}
   races[rid].append({"boat":bo,"finish":fi,"entry":entry,"cw":cs.get("win"),"c2":cs.get("top2"),"c3":cs.get("top3"),"cst":cs.get("avg_st"),"lw":ls.get("win"),"l2":ls.get("top2"),"l3":ls.get("top3"),"lst":ls.get("avg_st"),"grade":GRADE.get(P.get("grade","")),"nat2":rs.get("top2"),"mw":ms.get("win"),"m3":ms.get("top3"),"b2":bt.get("top2"),"b3":bt.get("top3"),"etime":F(Q.get("exhibition_time")),"est":F(Q.get("exhibition_st_seconds"))})
  for rid,bs in races.items():
   maps={k:rank(bs,k,k in {"cst","lst","etime","est"}) for k in ["cw","c2","c3","cst","lw","l2","l3","lst","grade","nat2","mw","m3","b2","b3","etime","est"]}
   if any(v is None for v in maps.values()):continue
   boats=sorted(maps["cw"]);r0={b:.4*maps["cw"][b]+.2*maps["c2"][b]+.3*maps["c3"][b]+.1*maps["cst"][b] for b in boats};re={b:.4*maps["lw"][b]+.2*maps["l2"][b]+.3*maps["l3"][b]+.1*maps["lst"][b] for b in boats};mo={b:.4*maps["mw"][b]+.6*maps["m3"][b] for b in boats};ba={b:.5*maps["b2"][b]+.5*maps["b3"][b] for b in boats}
   morning={b:.4*r0[b]+.2*maps["grade"][b]+.2*mo[b]+.05*ba[b]+.15*maps["nat2"][b] for b in boats};struct={b:.4*re[b]+.2*maps["grade"][b]+.2*mo[b]+.05*ba[b]+.15*maps["nat2"][b] for b in boats};live={b:.80*struct[b]+.06*maps["etime"][b]+.14*maps["est"][b] for b in boats}
   act=sorted(bs,key=lambda x:(x["finish"],x["boat"]));mp=sorted(boats,key=lambda b:(-morning[b],b));lp=sorted(boats,key=lambda b:(-live[b],b));truth=set(x["boat"] for x in act[:3]);mh=set(mp[:3])==truth;lh=set(lp[:3])==truth
   if mh==lh:continue
   rawst=[x["est"] for x in bs];rawt=[x["etime"] for x in bs];mscores=sorted(morning.values(),reverse=True);changed=sum(x["entry"]!=x["boat"] for x in bs)
   cases.append({"date":d,"race_id":rid,"transition":"x_to_o" if (not mh and lh) else "o_to_x","entry_changed_boats":changed,"st_spread":round(max(rawst)-min(rawst),3),"time_spread":round(max(rawt)-min(rawt),3),"morning_gap_1_2":round(mscores[0]-mscores[1],4),"morning_gap_3_4":round(mscores[2]-mscores[3],4)})
 def summarize(name,arr):
  def avg(k):return round(sum(x[k] for x in arr)/len(arr),4) if arr else None
  return {"group":name,"n":len(arr),"entry_change_races":sum(x["entry_changed_boats"]>0 for x in arr),"avg_st_spread":avg("st_spread"),"avg_time_spread":avg("time_spread"),"avg_morning_gap_1_2":avg("morning_gap_1_2"),"avg_morning_gap_3_4":avg("morning_gap_3_4"),"st_spread_ge_0_10":sum(x["st_spread"]>=.10 for x in arr),"morning_gap_3_4_lt_0_05":sum(x["morning_gap_3_4"]<.05 for x in arr)}
 xo=[x for x in cases if x["transition"]=="x_to_o"];ox=[x for x in cases if x["transition"]=="o_to_x"]
 out={"logic":{"morning":[40,20,20,5,15],"entry_course_replacement":True,"exhibition_time_pct":6,"exhibition_st_pct":14,"f_pct":0,"environment":False},"summary":[summarize("x_to_o",xo),summarize("o_to_x",ox)],"cases":cases}
 p=Path("evaluations/live_flip_diagnosis_20260930_20261003");p.mkdir(parents=True,exist_ok=True);(p/"summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(out["summary"],ensure_ascii=False,indent=2))
if __name__=="__main__":main2()
