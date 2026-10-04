from __future__ import annotations
exec(open("collectors/evaluate_live_logic_stage2_shortlist.py",encoding="utf-8").read().replace('if __name__=="__main__":main()',''))
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
import json

def hit1(bs,sc):
 p=sorted(bs,key=lambda b:(-sc[b["boat"]],b["boat"]));a=sorted(bs,key=lambda b:(b["finish"],b["boat"]))
 return p[0]["boat"]==a[0]["boat"]

def hit3(bs,sc):
 p=sorted(bs,key=lambda b:(-sc[b["boat"]],b["boat"]));a=sorted(bs,key=lambda b:(b["finish"],b["boat"]))
 return set(x["boat"] for x in p[:3])==set(x["boat"] for x in a[:3])

def main_delta():
 rows=[]
 for p in Path("archive").glob("*/*/*/boat_results_*_all.csv"): rows+=read(p)
 bd=defaultdict(list)
 for r in rows: bd[r.get("date")].append(r)
 cache={}
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
   est=F(Q.get("exhibition_st_seconds")); base_st=cs.get("avg_st")
   delta=(est-base_st) if est is not None and base_st is not None else None
   races[rid].append({"boat":bo,"finish":fi,"cw":cs.get("win"),"c2":cs.get("top2"),"c3":cs.get("top3"),"cst":base_st,"lw":ls.get("win"),"l2":ls.get("top2"),"l3":ls.get("top3"),"lst":ls.get("avg_st"),"grade":GRADE.get(P.get("grade","")),"nat2":rs.get("top2"),"mw":ms.get("win"),"m3":ms.get("top3"),"b2":bt.get("top2"),"b3":bt.get("top3"),"etime":F(Q.get("exhibition_time")),"est":est,"delta":delta})
  ready=[]
  for bs in races.values():
   keys=["cw","c2","c3","cst","lw","l2","l3","lst","grade","nat2","mw","m3","b2","b3","etime","est","delta"]
   maps={k:rank(bs,k,k in {"cst","lst","etime","est","delta"}) for k in keys}
   if any(v is None for v in maps.values()): continue
   boats=sorted(maps["cw"]);r0={b:.4*maps["cw"][b]+.2*maps["c2"][b]+.3*maps["c3"][b]+.1*maps["cst"][b] for b in boats};re={b:.4*maps["lw"][b]+.2*maps["l2"][b]+.3*maps["l3"][b]+.1*maps["lst"][b] for b in boats};mo={b:.4*maps["mw"][b]+.6*maps["m3"][b] for b in boats};ba={b:.5*maps["b2"][b]+.5*maps["b3"][b] for b in boats}
   morning={b:.4*r0[b]+.2*maps["grade"][b]+.2*mo[b]+.05*ba[b]+.15*maps["nat2"][b] for b in boats};struct={b:.4*re[b]+.2*maps["grade"][b]+.2*mo[b]+.05*ba[b]+.15*maps["nat2"][b] for b in boats}
   ready.append((bs,boats,morning,struct,maps["etime"],maps["est"],maps["delta"]))
  cache[d]=ready
 out=[]
 for mode in ["raw_est","personal_delta"]:
  for ws in range(6,19):
   xp1=xm1=xp3=xm3=h1=h3=n=0; days=[]
   for d in DATES:
    dn=dh1=dh3=0
    for bs,boats,morning,struct,et,es,de in cache[d]:
     st=es if mode=="raw_est" else de; rem=1-(6+ws)/100
     sc={b:rem*struct[b]+.06*et[b]+ws/100*st[b] for b in boats}
     m1=hit1(bs,morning);m3=hit3(bs,morning);z1=hit1(bs,sc);z3=hit3(bs,sc)
     n+=1;dn+=1;h1+=z1;h3+=z3;dh1+=z1;dh3+=z3;xp1+=(not m1 and z1);xm1+=(m1 and not z1);xp3+=(not m3 and z3);xm3+=(m3 and not z3)
    days.append({"date":d,"n":dn,"top1_pct":round(100*dh1/dn,2) if dn else None,"top3_pct":round(100*dh3/dn,2) if dn else None})
   out.append({"mode":mode,"time_pct":6,"st_pct":ws,"structural_pct":94-ws,"n":n,"top1_pct":round(100*h1/n,2),"top3_pct":round(100*h3/n,2),"top1_x_to_o":xp1,"top1_o_to_x":xm1,"top1_net":xp1-xm1,"top3_x_to_o":xp3,"top3_o_to_x":xm3,"top3_net":xp3-xm3,"by_date":days})
 out.sort(key=lambda x:(-x["top1_net"],-x["top3_net"],-x["top1_pct"],-x["top3_pct"]))
 p=Path("evaluations/st_personal_delta_20260930_20261003");p.mkdir(parents=True,exist_ok=True)
 (p/"summary.json").write_text(json.dumps({"definition":"personal_delta = exhibition_st - own 90d course average ST; lower is better","results":out},ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(out[:20],ensure_ascii=False,indent=2))
if __name__=="__main__": main_delta()
