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
 configs=[]
 for wr in range(32,39):
  for wg in range(18,23):
   for wm in range(22,29):
    for wb in range(3,8):
     for wn in range(13,18):
      if wr+wg+wm+wb+wn==100:configs.append((wr,wg,wm,wb,wn))
 out=[]
 for wr,wg,wm,wb,wn in configs:
  days={};xo=ox=0
  for d in DATES:
   n=h=0
   for rid,bs in daily[d].items():
    base=scores(bs);gr=rankmap(bs,"grade");mo1=rankmap(bs,"motor_win");mo3=rankmap(bs,"motor_top3");bo2=rankmap(bs,"boat2");bo3=rankmap(bs,"boat3");nat=rankmap(bs,"nat2")
    if any(x is None for x in [base,gr,mo1,mo3,bo2,bo3,nat]):continue
    motor={b:.4*mo1[b]+.6*mo3[b] for b in base};boat={b:.5*bo2[b]+.5*bo3[b] for b in base}
    current={b:.40*base[b]+.20*gr[b]+.20*motor[b]+.05*boat[b]+.15*nat[b] for b in base}
    sc={b:wr/100*base[b]+wg/100*gr[b]+wm/100*motor[b]+wb/100*boat[b]+wn/100*nat[b] for b in base};bh=hit(bs,current);nh=hit(bs,sc);n+=1;h+=nh;xo+=(not bh) and nh;ox+=bh and (not nh)
   days[d]={"n":n,"top3_pct":round(100*h/n,2) if n else None}
  vv=[x["top3_pct"] for x in days.values() if x["top3_pct"] is not None];out.append({"racer":wr,"grade":wg,"motor":wm,"boat":wb,"national_top2":wn,"by_date":days,"daily_avg_top3_pct":round(sum(vv)/len(vv),2),"spread_pt":round(max(vv)-min(vv),2),"x_to_o":xo,"o_to_x":ox,"net_flips":xo-ox})
 out.sort(key=lambda x:(-x["daily_avg_top3_pct"],x["spread_pt"],-x["net_flips"]))
 outdir=Path("evaluations/morning_weight_grid_20260930_20261003");outdir.mkdir(parents=True,exist_ok=True)
 (outdir/"summary.json").write_text(json.dumps({"definition":"TOP3 unordered exact set","baseline":"current 40/20/20/5/15; fine neighborhood around 35/20/25/5/15","results":out},ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(sorted(out,key=lambda x:(-x["net_flips"],-x["daily_avg_top3_pct"]))[:20],ensure_ascii=False,indent=2))
if __name__=="__main__":main()
