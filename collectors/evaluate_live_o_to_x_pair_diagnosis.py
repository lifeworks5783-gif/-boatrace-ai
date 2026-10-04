from __future__ import annotations
# Pair-level diagnosis of races where morning exact TOP3 was correct but live exact TOP3 became wrong.
exec(open("collectors/evaluate_live_logic_stage2_shortlist.py",encoding="utf-8").read().replace('if __name__=="__main__":main()',''))
import json
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

def main2():
 rows=[]
 for p in Path("archive").glob("*/*/*/boat_results_*_all.csv"): rows+=read(p)
 bd=defaultdict(list)
 for r in rows: bd[r.get("date")].append(r)
 cases=[]
 for d in DATES:
  td=DT(d); prior=[r for r in rows if r.get("date") and td-timedelta(days=90)<=DT(r["date"])<td]; pg=load_program(d); lv=load_live(d)
  rg=defaultdict(list);rc=defaultdict(list);mg=defaultdict(list);bg=defaultdict(list)
  for r in prior:
   reg=r.get("registration_no","");c=I(r.get("course"));v=str(r.get("venue_code","")).zfill(2);m=I(r.get("motor_no"));b=I(r.get("boat_no"))
   if reg: rg[reg].append(r)
   if reg and c: rc[(reg,c)].append(r)
   if m is not None: mg[(v,m)].append(r)
   if b is not None: bg[(v,b)].append(r)
  races=defaultdict(list)
  for r in bd[d]:
   bo=I(r.get("boat"));fi=I(r.get("finish"));rid=nid(r.get("race_id"))
   if bo not in range(1,7) or fi not in range(1,7): continue
   v=str(r.get("venue_code","")).zfill(2);reg=r.get("registration_no","");P=pg.get((rid,bo),{});Q=lv.get((rid,bo),{});entry=I(Q.get("exhibition_course")) or bo
   rs=stat(rg[reg]);cs=stat(rc[(reg,bo)]);ls=stat(rc[(reg,entry)]);ms=stat(mg[(v,I(r.get("motor_no")))]) if I(r.get("motor_no")) is not None else {};bt=stat(bg[(v,I(r.get("boat_no")))]) if I(r.get("boat_no")) is not None else {}
   races[rid].append({"boat":bo,"finish":fi,"entry":entry,"cw":cs.get("win"),"c2":cs.get("top2"),"c3":cs.get("top3"),"cst":cs.get("avg_st"),"own90st":rs.get("avg_st"),"lw":ls.get("win"),"l2":ls.get("top2"),"l3":ls.get("top3"),"lst":ls.get("avg_st"),"grade":GRADE.get(P.get("grade","")),"nat2":rs.get("top2"),"mw":ms.get("win"),"m3":ms.get("top3"),"b2":bt.get("top2"),"b3":bt.get("top3"),"etime":F(Q.get("exhibition_time")),"est":F(Q.get("exhibition_st_seconds")),"eflag":(Q.get("exhibition_st_flag") or "").strip()})
  for rid,bs in races.items():
   keys=["cw","c2","c3","cst","lw","l2","l3","lst","grade","nat2","mw","m3","b2","b3","etime","est"]
   maps={k:rank(bs,k,k in {"cst","lst","etime","est"}) for k in keys}
   if any(v is None for v in maps.values()): continue
   boats=sorted(maps["cw"]); r0={b:.4*maps["cw"][b]+.2*maps["c2"][b]+.3*maps["c3"][b]+.1*maps["cst"][b] for b in boats}; re={b:.4*maps["lw"][b]+.2*maps["l2"][b]+.3*maps["l3"][b]+.1*maps["lst"][b] for b in boats}; mo={b:.4*maps["mw"][b]+.6*maps["m3"][b] for b in boats}; ba={b:.5*maps["b2"][b]+.5*maps["b3"][b] for b in boats}
   morning={b:.4*r0[b]+.2*maps["grade"][b]+.2*mo[b]+.05*ba[b]+.15*maps["nat2"][b] for b in boats};struct={b:.4*re[b]+.2*maps["grade"][b]+.2*mo[b]+.05*ba[b]+.15*maps["nat2"][b] for b in boats};live={b:.80*struct[b]+.06*maps["etime"][b]+.14*maps["est"][b] for b in boats}
   act=sorted(bs,key=lambda x:(x["finish"],x["boat"]));truth=set(x["boat"] for x in act[:3]);mp=sorted(boats,key=lambda b:(-morning[b],b));lp=sorted(boats,key=lambda b:(-live[b],b))
   if set(mp[:3])!=truth or set(lp[:3])==truth: continue
   dropped=list(set(mp[:3])-set(lp[:3])); promoted=list(set(lp[:3])-set(mp[:3]))
   if len(dropped)!=1 or len(promoted)!=1: continue
   dr,pr=dropped[0],promoted[0]; raw={x["boat"]:x for x in bs}
   def val(b,k): return raw[b].get(k)
   cases.append({"date":d,"race_id":rid,"dropped_correct_boat":dr,"promoted_wrong_boat":pr,"dropped_finish":val(dr,"finish"),"promoted_finish":val(pr,"finish"),"morning_gap_promoted_minus_dropped":round(morning[pr]-morning[dr],4),"structural_delta_promoted_minus_dropped":round(struct[pr]-struct[dr],4),"live_delta_promoted_minus_dropped":round(live[pr]-live[dr],4),"etime_rank_advantage_promoted":round(maps["etime"][pr]-maps["etime"][dr],3),"est_rank_advantage_promoted":round(maps["est"][pr]-maps["est"][dr],3),"raw_etime_promoted":val(pr,"etime"),"raw_etime_dropped":val(dr,"etime"),"raw_est_promoted":val(pr,"est"),"raw_est_dropped":val(dr,"est"),"personal_delta_promoted":round(val(pr,"est")-val(pr,"own90st"),3) if val(pr,"est") is not None and val(pr,"own90st") is not None else None,"personal_delta_dropped":round(val(dr,"est")-val(dr,"own90st"),3) if val(dr,"est") is not None and val(dr,"own90st") is not None else None,"entry_changed_promoted":val(pr,"entry")!=pr,"entry_changed_dropped":val(dr,"entry")!=dr,"exhibition_flag_promoted":val(pr,"eflag"),"exhibition_flag_dropped":val(dr,"eflag")})
 def pct(n,d): return round(100*n/d,1) if d else None
 n=len(cases)
 summary={"n":n,"promoted_had_better_est_rank":sum(x["est_rank_advantage_promoted"]>0 for x in cases),"promoted_had_better_etime_rank":sum(x["etime_rank_advantage_promoted"]>0 for x in cases),"promoted_better_both":sum(x["est_rank_advantage_promoted"]>0 and x["etime_rank_advantage_promoted"]>0 for x in cases),"entry_change_in_pair":sum(x["entry_changed_promoted"] or x["entry_changed_dropped"] for x in cases),"exhibition_fl_in_pair":sum(bool(x["exhibition_flag_promoted"] or x["exhibition_flag_dropped"]) for x in cases)}
 summary["pct"]={k:pct(v,n) for k,v in summary.items() if k!="n"}
 out={"definition":"morning exact TOP3 correct -> live exact TOP3 wrong; one-for-one boundary swap","summary":summary,"cases":cases}
 p=Path("evaluations/live_o_to_x_pair_diagnosis_20260930_20261003");p.mkdir(parents=True,exist_ok=True);(p/"summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__": main2()
