from __future__ import annotations
import csv,json,itertools
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
DATES=["20260930","20261001","20261002"];OUT=Path("evaluations/phase8_course_reliability")
GRADE={"A1":1.0,"A2":.75,"B1":.45,"B2":.25}
BASES={"B1":{"win":.4,"top2":.2,"top3":.3,"st":.1},"B2":{"win":.5,"top2":.5},"B3":{"win":.3,"top2":.2,"top3":.4,"st":.1}}
def F(v):
 try:return float(v)
 except:return None
def I(v):
 try:return int(float(v))
 except:return None
def dt(s):return datetime.strptime(s,"%Y%m%d").date()
def nid(v):return "".join(c for c in (v or "") if c.isdigit())
def load():
 z=[]
 for p in Path("archive").glob("*/*/*/boat_results_*_all.csv"):
  with p.open(encoding="utf-8-sig",newline="") as h:z+=list(csv.DictReader(h))
 return z
def program(d):
 for p in [Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/program_entries_{d}.csv"),Path(f"data/program_entries_{d}.csv")]:
  if p.exists():
   with p.open(encoding="utf-8-sig",newline="") as h:return {(nid(r["race_id"]),I(r["boat"])):r for r in csv.DictReader(h)}
 return {}
def stat(rs):
 fs=[I(r.get("finish")) for r in rs if I(r.get("finish")) in range(1,7)];sts=[]
 for r in rs:
  x=F(r.get("st"))
  if x is not None and x>=0:sts.append(x)
 if not fs:return None
 return {"win":sum(x==1 for x in fs)/len(fs),"top2":sum(x<=2 for x in fs)/len(fs),"top3":sum(x<=3 for x in fs)/len(fs),"st":sum(sts)/len(sts) if sts else None,"n":len(fs)}
def rank(bs,key,reverse=False):
 if any(b.get(key) is None for b in bs):return None
 o=sorted(bs,key=lambda b:((b[key] if reverse else -b[key]),b["boat"]))
 return {b["boat"]:1-j/5 for j,b in enumerate(o)}
def score_base(bs,w,prefix):
 ranks={}
 for k in w:
  ranks[k]=rank(bs,prefix+k,reverse=k=="st")
  if ranks[k] is None:return None
 return {b["boat"]:sum(w[k]*ranks[k][b["boat"]] for k in w) for b in bs}
def metrics(races,base,k,m1):
 agg=defaultdict(int);days={d:defaultdict(int) for d in DATES}
 for d,rid,bs in races:
  pref="raw_" if k==0 else f"k{k}_";sc=score_base(bs,BASES[base],pref)
  if sc is None:continue
  if m1:
   qg=rank(bs,"grade");qn=rank(bs,"nat_top3")
   if qg is None or qn is None:continue
   sc={b["boat"]:sc[b["boat"]]+.2*qg[b["boat"]]+.1*qn[b["boat"]] for b in bs}
  p=sorted(bs,key=lambda b:(-sc[b["boat"]],b["boat"]));a=sorted(bs,key=lambda b:(b["finish"],b["boat"]))
  for x in [agg,days[d]]:
   x["n"]+=1;x["top1"]+=p[0]["boat"]==a[0]["boat"];x["top3"]+=set(v["boat"] for v in p[:3])==set(v["boat"] for v in a[:3]);x["exact"]+=[v["boat"] for v in p[:3]]==[v["boat"] for v in a[:3]]
 def fmt(x):n=x["n"];return {"races":n,"top1_pct":round(x["top1"]*100/n,2),"top3_pct":round(x["top3"]*100/n,2),"exact_pct":round(x["exact"]*100/n,2)}
 return fmt(agg),{d:fmt(x) for d,x in days.items()}
def main():
 rows=load();target=defaultdict(list)
 for r in rows:
  if r.get("date") in DATES:target[r["date"]].append(r)
 races=[]
 for d in DATES:
  td=dt(d);prior=[r for r in rows if r.get("date") and td-timedelta(days=90)<=dt(r["date"])<td];pg=program(d);rg=defaultdict(list);rc=defaultdict(list)
  for r in prior:
   reg=r.get("registration_no","");co=I(r.get("course"))
   if reg:rg[reg].append(r)
   if reg and co:rc[(reg,co)].append(r)
  rr=defaultdict(list)
  for r in target[d]:
   bo=I(r.get("boat"));fi=I(r.get("finish"));reg=r.get("registration_no","")
   if bo not in range(1,7) or fi not in range(1,7):continue
   C=stat(rc[(reg,bo)]);N=stat(rg[reg]);p=pg.get((nid(r.get("race_id")),bo),{})
   if not C or not N:continue
   b={"boat":bo,"finish":fi,"grade":GRADE.get(p.get("grade","")),"nat_top3":N["top3"]}
   for x in ["win","top2","top3","st"]:b["raw_"+x]=C[x]
   for k in [3,5,10,15,20]:
    conf=C["n"]/(C["n"]+k)
    for x in ["win","top2","top3","st"]:
     b[f"k{k}_"+x]=None if C[x] is None or N[x] is None else conf*C[x]+(1-conf)*N[x]
   rr[r["race_id"]].append(b)
  for rid,bs in rr.items():
   if len(bs)==6:races.append((d,rid,bs))
 out=[];byday=[]
 for base in BASES:
  for k in [0,3,5,10,15,20]:
   for m1 in [False,True]:
    a,ds=metrics(races,base,k,m1);row={"base":base,"k":k,"m1":m1,**a};out.append(row)
    for d,x in ds.items():byday.append({"base":base,"k":k,"m1":m1,"date":d,**x})
 out.sort(key=lambda x:(-x["top1_pct"],-x["top3_pct"],-x["exact_pct"]))
 OUT.mkdir(parents=True,exist_ok=True)
 for fn,data in [("reliability_grid.csv",out),("by_date.csv",byday)]:
  with (OUT/fn).open("w",encoding="utf-8",newline="") as h:w=csv.DictWriter(h,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 (OUT/"summary.json").write_text(json.dumps({"method":"course stats shrunk toward same racer's national 90d stats: n/(n+k)*course + k/(n+k)*national. k=0,3,5,10,15,20. B1=40/20/30/10, B2=50/50, B3=30/20/40/10. M1 adds grade20 + national_top3 10 after base.","top20":out[:20]},ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({"races":len(races),"top20":out[:20]},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
