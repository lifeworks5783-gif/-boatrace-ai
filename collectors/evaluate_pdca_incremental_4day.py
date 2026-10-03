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
def main():
 rows=archive();bd=defaultdict(list)
 for r in rows:bd[r.get("date")].append(r)
 daily={}
 for d in DATES:
  td=DT(d);prior=[r for r in rows if r.get("date") and td-timedelta(days=90)<=DT(r["date"])<td];pg=program(d);lv=live_entries(d)
  rg=defaultdict(list);rc=defaultdict(list);mg=defaultdict(list);bg=defaultdict(list)
  for r in prior:
   reg=r.get("registration_no","");c=I(r.get("course"));v=str(r.get("venue_code","")).zfill(2);m=I(r.get("motor_no"));bn=I(r.get("boat_no"))
   if reg:rg[reg].append(r)
   if reg and c:rc[(reg,c)].append(r)
   if m is not None:mg[(v,m)].append(r)
   if bn is not None:bg[(v,bn)].append(r)
  rr=defaultdict(list)
  for r in bd[d]:
   bo=I(r.get("boat"));fi=I(r.get("finish"))
   if bo not in range(1,7) or fi not in range(1,7):continue
   rid=nid(r.get("race_id"));v=str(r.get("venue_code","")).zfill(2);reg=r.get("registration_no","");P=pg.get((rid,bo),{});L=lv.get((rid,bo),{})
   rs=stat(rg[reg]);cs=stat(rc[(reg,bo)]);ms=stat(mg[(v,I(r.get("motor_no")))]) if I(r.get("motor_no")) is not None else {};bs=stat(bg[(v,I(r.get("boat_no")))]) if I(r.get("boat_no")) is not None else {}
   rr[rid].append({"boat":bo,"finish":fi,"cw":cs.get("win"),"c2":cs.get("top2"),"c3":cs.get("top3"),"cst":cs.get("avg_st"),"grade":GRADE.get(P.get("grade","")),"nat2":rs.get("top2"),"motor_win":ms.get("win"),"motor_top3":ms.get("top3"),"boat2":bs.get("top2"),"boat3":bs.get("top3"),"etime":F(L.get("exhibition_time"))})
  daily[d]=rr
 def scores(bs,corr=None,w=0):
  maps={}
  for k,rev in [("cw",False),("c2",False),("c3",False),("cst",True)]:
   maps[k]=rankmap(bs,k,rev)
   if maps[k] is None:return None
  sc={b["boat"]:.4*maps["cw"][b["boat"]]+.2*maps["c2"][b["boat"]]+.3*maps["c3"][b["boat"]]+.1*maps["cst"][b["boat"]] for b in bs}
  if corr:
   q=rankmap(bs,corr,corr=="etime")
   if q is None:return None
   sc={b:sc[b]+w*q[b] for b in sc}
  return sc
 def hit(bs,sc):
  p=sorted(bs,key=lambda b:(-sc[b["boat"]],b["boat"]));a=sorted(bs,key=lambda b:(b["finish"],b["boat"]))
  return set(x["boat"] for x in p[:3])==set(x["boat"] for x in a[:3])
 specs=[("grade","級別"),("nat2","全国2連対率"),("etime","展示タイム"),("boat2","ボート90日2連対率"),("motor_win","モーター90日1着率"),("motor_top3","モーター90日3連対率"),("boat3","ボート90日3連対率")]
 out=[]
 for key,label in specs:
  for w in [.02,.05,.10,.15,.20,.30]:
   days={};tot={"n":0,"base":0,"new":0,"xx":0,"xo":0,"ox":0,"oo":0}
   for d in DATES:
    z={"n":0,"base":0,"new":0,"xx":0,"xo":0,"ox":0,"oo":0}
    for rid,bs in daily[d].items():
     bsc=scores(bs);nsc=scores(bs,key,w)
     if bsc is None or nsc is None:continue
     bh=hit(bs,bsc);nh=hit(bs,nsc);z["n"]+=1;z["base"]+=bh;z["new"]+=nh
     z["oo" if bh and nh else "ox" if bh else "xo" if nh else "xx"]+=1
    z["base_pct"]=round(100*z["base"]/z["n"],2) if z["n"] else None;z["new_pct"]=round(100*z["new"]/z["n"],2) if z["n"] else None;z["delta_pt"]=round(z["new_pct"]-z["base_pct"],2) if z["n"] else None
    days[d]=z
    for x in ["n","base","new","xx","xo","ox","oo"]:tot[x]+=z[x]
   vals=[x["new_pct"] for x in days.values() if x["new_pct"] is not None]
   out.append({"factor":label,"weight_pct":int(w*100),"by_date":days,"daily_avg_top3_pct":round(sum(vals)/len(vals),2) if vals else None,"spread_pt":round(max(vals)-min(vals),2) if vals else None,"total_x_to_o":tot["xo"],"total_o_to_x":tot["ox"],"net_flips":tot["xo"]-tot["ox"],"eligible_races":tot["n"]})
 OUT=Path("evaluations/pdca_incremental_20260930_20261003");OUT.mkdir(parents=True,exist_ok=True)
 (OUT/"summary.json").write_text(json.dumps({"dates":DATES,"baseline":"B1 racer course base = win40+top2 20+top3 30+avgST10","definition":"TOP3 unordered exact set","results":out},ensure_ascii=False,indent=2),encoding="utf-8")
 flat=[]
 for x in out:
  flat.append({"factor":x["factor"],"weight_pct":x["weight_pct"],"daily_avg_top3_pct":x["daily_avg_top3_pct"],"spread_pt":x["spread_pt"],"x_to_o":x["total_x_to_o"],"o_to_x":x["total_o_to_x"],"net_flips":x["net_flips"],"eligible_races":x["eligible_races"],**{d:x["by_date"][d]["new_pct"] for d in DATES}})
 with (OUT/"summary.csv").open("w",encoding="utf-8",newline="") as h:
  w=csv.DictWriter(h,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
 print(json.dumps(sorted(out,key=lambda x:(x["net_flips"],x["daily_avg_top3_pct"] or -1),reverse=True)[:20],ensure_ascii=False,indent=2))
if __name__=="__main__":main()
