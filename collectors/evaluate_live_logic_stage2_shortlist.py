from __future__ import annotations
import csv,json
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
DATES=["20260930","20261001","20261002","20261003"]; GRADE={"A1":1.0,"A2":.75,"B1":.45,"B2":.25}
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
def stat(rs):
 fs=[I(r.get("finish")) for r in rs if I(r.get("finish")) in range(1,7)]; sts=[F(r.get("st")) for r in rs if F(r.get("st")) is not None]
 if not fs:return {}
 return {"win":sum(x==1 for x in fs)/len(fs),"top2":sum(x<=2 for x in fs)/len(fs),"top3":sum(x<=3 for x in fs)/len(fs),"avg_st":sum(sts)/len(sts) if sts else None}
def rank(bs,key,rev=False):
 if len(bs)!=6 or any(b.get(key) is None for b in bs):return None
 o=sorted(bs,key=lambda b:((b[key] if rev else -b[key]),b["boat"]));return {b["boat"]:1-j/5 for j,b in enumerate(o)}
def load_program(d):
 for p in [Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/program_entries_{d}.csv"),Path(f"data/program_entries_{d}.csv")]:
  if p.exists():return {(nid(r.get("race_id")),I(r.get("boat"))):r for r in read(p)}
 return {}
def load_live(d):
 ps=list(Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/live/backfill").glob(f"beforeinfo_entries_{d}.csv")) or list(Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/live/snapshots").glob(f"*/beforeinfo_entries_{d}.csv"))
 z={}
 for p in ps:
  for r in read(p):z[(nid(r.get("race_id")),I(r.get("boat")))]=r
 return z
def main():
 rows=[]
 for p in Path("archive").glob("*/*/*/boat_results_*_all.csv"):rows+=read(p)
 bd=defaultdict(list)
 for r in rows:bd[r.get("date")].append(r)
 cache={}
 for d in DATES:
  td=DT(d);prior=[r for r in rows if r.get("date") and td-timedelta(days=90)<=DT(r["date"])<td];pg=load_program(d);lv=load_live(d)
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
   rs=stat(rg[reg]);cs=stat(rc[(reg,bo)]);ls=stat(rc[(reg,entry)]);ms=stat(mg[(v,I(r.get("motor_no")))]) if I(r.get("motor_no")) is not None else {};bs=stat(bg[(v,I(r.get("boat_no")))]) if I(r.get("boat_no")) is not None else {}
   races[rid].append({"boat":bo,"finish":fi,"cw":cs.get("win"),"c2":cs.get("top2"),"c3":cs.get("top3"),"cst":cs.get("avg_st"),"lw":ls.get("win"),"l2":ls.get("top2"),"l3":ls.get("top3"),"lst":ls.get("avg_st"),"grade":GRADE.get(P.get("grade","")),"nat2":rs.get("top2"),"mw":ms.get("win"),"m3":ms.get("top3"),"b2":bs.get("top2"),"b3":bs.get("top3"),"etime":F(Q.get("exhibition_time")),"est":F(Q.get("exhibition_st_seconds")),"fpen":1.0 if (Q.get("exhibition_st_flag") or "").strip()=="F" else 0.0})
  ready=[]
  for bs in races.values():
   maps={k:rank(bs,k,k in {"cst","lst","etime","est","fpen"}) for k in ["cw","c2","c3","cst","lw","l2","l3","lst","grade","nat2","mw","m3","b2","b3","etime","est","fpen"]}
   if any(v is None for v in maps.values()):continue
   boats=sorted(maps["cw"]);r0={b:.4*maps["cw"][b]+.2*maps["c2"][b]+.3*maps["c3"][b]+.1*maps["cst"][b] for b in boats};re={b:.4*maps["lw"][b]+.2*maps["l2"][b]+.3*maps["l3"][b]+.1*maps["lst"][b] for b in boats};mo={b:.4*maps["mw"][b]+.6*maps["m3"][b] for b in boats};ba={b:.5*maps["b2"][b]+.5*maps["b3"][b] for b in boats}
   morning={b:.4*r0[b]+.2*maps["grade"][b]+.2*mo[b]+.05*ba[b]+.15*maps["nat2"][b] for b in boats};struct={b:.4*re[b]+.2*maps["grade"][b]+.2*mo[b]+.05*ba[b]+.15*maps["nat2"][b] for b in boats};act=sorted(bs,key=lambda x:(x["finish"],x["boat"]));mp=sorted(boats,key=lambda b:(-morning[b],b));mh=set(mp[:3])==set(x["boat"] for x in act[:3])
   ready.append((boats,act,struct,maps["etime"],maps["est"],maps["fpen"],mh))
  cache[d]=ready
 results=[]
 for wt in [0,2,4,6]:
  for ws in [14,15,16,17,18]:
   for wf in [0,1,2]:
    if wt+ws+wf>28:continue
    days=[];xp=xm=t1=ex=tot=0
    for d in DATES:
     n=lh=mhc=0
     for boats,act,st,et,es,fp,mh in cache[d]:
      rem=1-(wt+ws+wf)/100;sc={b:rem*st[b]+wt/100*et[b]+ws/100*es[b]+wf/100*fp[b] for b in boats};p=sorted(boats,key=lambda b:(-sc[b],b));z=set(p[:3])==set(x["boat"] for x in act[:3]);n+=1;tot+=1;mhc+=mh;lh+=z;t1+=p[0]==act[0]["boat"];ex+=p[:3]==[x["boat"] for x in act[:3]];xp+=(not mh) and z;xm+=mh and (not z)
     days.append({"date":d,"n":n,"morning_pct":round(100*mhc/n,2),"live_pct":round(100*lh/n,2)})
    vv=[x["live_pct"] for x in days];results.append({"time_pct":wt,"st_pct":ws,"f_pct":wf,"structural_pct":100-wt-ws-wf,"by_date":days,"daily_avg_top3_pct":round(sum(vv)/4,2),"spread_pt":round(max(vv)-min(vv),2),"x_to_o":xp,"o_to_x":xm,"net_flips":xp-xm,"pooled_top1_pct":round(100*t1/tot,2),"pooled_exact_pct":round(100*ex/tot,2)})
 results.sort(key=lambda x:(-x["daily_avg_top3_pct"],x["spread_pt"],-x["net_flips"]))
 out=Path("evaluations/live_logic_stage2_shortlist_20260930_20261003");out.mkdir(parents=True,exist_ok=True);(out/"summary.json").write_text(json.dumps({"definition":"TOP3 unordered exact set","optimization":"cached date features; same formulas and data","results":results},ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(results[:20],ensure_ascii=False,indent=2))
if __name__=="__main__":main()
