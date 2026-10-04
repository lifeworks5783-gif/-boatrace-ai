from __future__ import annotations
# Simulation of safer exhibition-ST handling on current 20260930-20261003 validation data.
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
 cache={}
 for d in DATES:
  td=DT(d);prior=[r for r in rows if r.get("date") and td-timedelta(days=90)<=DT(r["date"])<td];pg=load_program(d);lv=load_live(d)
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
  ready=[]
  for rid,bs in races.items():
   basekeys=["cw","c2","c3","cst","lw","l2","l3","lst","grade","nat2","mw","m3","b2","b3","etime","est"]
   maps={k:rank(bs,k,k in {"cst","lst","etime","est"}) for k in basekeys}
   if any(v is None for v in maps.values()) or any(x["own90st"] is None for x in bs): continue
   boats=sorted(maps["cw"]);r0={b:.4*maps["cw"][b]+.2*maps["c2"][b]+.3*maps["c3"][b]+.1*maps["cst"][b] for b in boats};re={b:.4*maps["lw"][b]+.2*maps["l2"][b]+.3*maps["l3"][b]+.1*maps["lst"][b] for b in boats};mo={b:.4*maps["mw"][b]+.6*maps["m3"][b] for b in boats};ba={b:.5*maps["b2"][b]+.5*maps["b3"][b] for b in boats}
   morning={b:.4*r0[b]+.2*maps["grade"][b]+.2*mo[b]+.05*ba[b]+.15*maps["nat2"][b] for b in boats};struct={b:.4*re[b]+.2*maps["grade"][b]+.2*mo[b]+.05*ba[b]+.15*maps["nat2"][b] for b in boats}
   raw={x["boat"]:x for x in bs};truth=set(x["boat"] for x in sorted(bs,key=lambda x:(x["finish"],x["boat"]))[:3]);mset=set(sorted(boats,key=lambda b:(-morning[b],b))[:3])
   ready.append((rid,boats,raw,maps,struct,truth,mset))
  cache[d]=ready

 def special_rank(boats,raw,mode):
  # higher rank score = better. For F: neutral gives middle .5; penalty gives 0; exclude gives neutral .5.
  normal=[b for b in boats if raw[b]["eflag"] not in {"F","L"}]
  order=sorted(normal,key=lambda b:(raw[b]["est"],b)); out={}
  if len(order)==1: out[order[0]]=1.0
  elif order:
   for j,b in enumerate(order): out[b]=1-j/(len(order)-1)
  for b in boats:
   if b not in out: out[b]=0.0 if mode=="penalty" else 0.5
  return out

 variants=[("current",14,0,"current"),("F_neutral",14,0,"neutral"),("F_penalty",14,0,"penalty"),("F_neutral_plus_personal4",10,4,"neutral"),("F_neutral_plus_personal6",8,6,"neutral"),("F_penalty_plus_personal4",10,4,"penalty")]
 results=[]
 for name,ws,wp,fmode in variants:
  tot=top1=exact=xo=ox=morning_exact=0;days=[]
  for d in DATES:
   dn=dh=0
   for rid,boats,raw,maps,struct,truth,mset in cache[d]:
    if name=="current": sr=maps["est"]
    else: sr=special_rank(boats,raw,fmode)
    deltas=[{"boat":b,"pdelta":raw[b]["est"]-raw[b]["own90st"]} for b in boats]
    pr=rank(deltas,"pdelta",True)
    sc={b:(1-(6+ws+wp)/100)*struct[b]+.06*maps["etime"][b]+ws/100*sr[b]+(wp/100*pr[b] if wp else 0) for b in boats}
    pred=sorted(boats,key=lambda b:(-sc[b],b));pset=set(pred[:3]); hit=pset==truth; mh=mset==truth
    tot+=1;dn+=1;dh+=hit;exact+=hit;morning_exact+=mh;top1+=pred[0]==next(x["boat"] for x in sorted(raw.values(),key=lambda x:(x["finish"],x["boat"])))
    xo+=(not mh and hit);ox+=(mh and not hit)
   days.append({"date":d,"n":dn,"exact_top3_pct":round(100*dh/dn,2) if dn else None})
  results.append({"variant":name,"st_pct":ws,"personal_delta_pct":wp,"f_mode":fmode,"n":tot,"top1_pct":round(100*top1/tot,2),"exact_top3_pct":round(100*exact/tot,2),"morning_exact_top3_pct":round(100*morning_exact/tot,2),"x_to_o":xo,"o_to_x":ox,"net":xo-ox,"by_date":days})
 out={"note":"F/L handling simulation. personal delta uses overall racer 90d avg ST. Production unchanged.","results":results}
 p=Path("evaluations/st_f_safety_sim_20260930_20261003");p.mkdir(parents=True,exist_ok=True);(p/"summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__": main2()
