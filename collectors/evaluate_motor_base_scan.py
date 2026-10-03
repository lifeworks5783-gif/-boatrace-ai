from __future__ import annotations
import csv,json,itertools
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
DATES=["20260930","20261001","20261002"]
OUT=Path("evaluations/motor_base_scan")
def F(v):
 try:return float(v)
 except:return None
def I(v):
 try:return int(float(v))
 except:return None
def dt(v):return datetime.strptime(v,"%Y%m%d").date()
def nid(v):return "".join(c for c in (v or "") if c.isdigit())
def load():
 z=[]
 for p in Path("archive").glob("*/*/*/boat_results_*_all.csv"):
  with p.open(encoding="utf-8-sig",newline="") as h:z+=list(csv.DictReader(h))
 return z
def prog(d):
 for p in [Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/program_entries_{d}.csv"),Path(f"data/program_entries_{d}.csv")]:
  if p.exists():
   with p.open(encoding="utf-8-sig",newline="") as h:return {(nid(r["race_id"]),I(r["boat"])):r for r in csv.DictReader(h)}
 return {}
def stat(rs):
 fs=[I(r.get("finish")) for r in rs if I(r.get("finish")) in range(1,7)]
 if not fs:return {}
 return {"win":sum(x==1 for x in fs)/len(fs),"top2":sum(x<=2 for x in fs)/len(fs),"top3":sum(x<=3 for x in fs)/len(fs),"n":len(fs)}
def rank(bs,k):
 if any(b.get(k) is None for b in bs):return None
 o=sorted(bs,key=lambda b:(-b[k],b["boat"]))
 return {b["boat"]:1-j/5 for j,b in enumerate(o)}
def ev(races,w):
 A=defaultdict(int);D={d:defaultdict(int) for d in DATES}
 for d,rid,bs in races:
  qs={k:rank(bs,k) for k in w}
  if any(v is None for v in qs.values()):continue
  sc={b["boat"]:sum(w[k]*qs[k][b["boat"]] for k in w) for b in bs}
  p=sorted(bs,key=lambda b:(-sc[b["boat"]],b["boat"]));a=sorted(bs,key=lambda b:(b["finish"],b["boat"]))
  for x in (A,D[d]):
   x["n"]+=1;x["t1"]+=p[0]["boat"]==a[0]["boat"];x["t3"]+=set(y["boat"] for y in p[:3])==set(y["boat"] for y in a[:3]);x["ex"]+=[y["boat"] for y in p[:3]]==[y["boat"] for y in a[:3]]
 def fmt(x):
  n=x["n"];return {"races":n,"top1_pct":round(x["t1"]*100/n,2) if n else 0,"top3_pct":round(x["t3"]*100/n,2) if n else 0,"exact_pct":round(x["ex"]*100/n,2) if n else 0}
 return fmt(A),{d:fmt(x) for d,x in D.items()}
def main():
 rows=load();bd=defaultdict(list)
 for r in rows:
  if r.get("date") in DATES:bd[r["date"]].append(r)
 races=[]
 for d in DATES:
  td=dt(d);prior=[r for r in rows if r.get("date") and td-timedelta(days=90)<=dt(r["date"])<td];pg=prog(d);mg=defaultdict(list)
  for r in prior:
   m=I(r.get("motor_no"));v=str(r.get("venue_code","")).zfill(2)
   if m is not None:mg[(v,m)].append(r)
  rr=defaultdict(list)
  for r in bd[d]:
   bo=I(r.get("boat"));fi=I(r.get("finish"));v=str(r.get("venue_code","")).zfill(2);m=I(r.get("motor_no"))
   if bo not in range(1,7) or fi not in range(1,7):continue
   P=pg.get((nid(r.get("race_id")),bo),{});M=stat(mg[(v,m)]) if m is not None else {}
   rr[r["race_id"]].append({"boat":bo,"finish":fi,"official_top2":F(P.get("motor_top2_rate"))/100 if F(P.get("motor_top2_rate")) is not None else None,"d90_win":M.get("win"),"d90_top2":M.get("top2"),"d90_top3":M.get("top3")})
  for rid,bs in rr.items():
   if len(bs)==6:races.append((d,rid,bs))
 factors=["official_top2","d90_win","d90_top2","d90_top3"];models={}
 for k in factors:models[k+"100"]={k:1}
 # 2-factor 10% grid
 for a,b in itertools.combinations(factors,2):
  for x in range(1,10):models[f"{a}{x*10}_{b}{(10-x)*10}"]={a:x/10,b:(10-x)/10}
 # 3-factor 10% grid
 for comb in itertools.combinations(factors,3):
  for a in range(1,9):
   for b in range(1,10-a):
    c=10-a-b
    if c>=1:models[f"{comb[0]}{a*10}_{comb[1]}{b*10}_{comb[2]}{c*10}"]={comb[0]:a/10,comb[1]:b/10,comb[2]:c/10}
 # 4-factor 10% grid
 for a in range(1,8):
  for b in range(1,9-a):
   for c in range(1,10-a-b):
    e=10-a-b-c
    if e>=1:models[f"official{a*10}_win{b*10}_top2{c*10}_top3{e*10}"]={"official_top2":a/10,"d90_win":b/10,"d90_top2":c/10,"d90_top3":e/10}
 out=[];days=[]
 for name,w in models.items():
  x,ds=ev(races,w);out.append({"model":name,"weights":json.dumps(w),"factor_count":len(w),**x})
  for d,z in ds.items():days.append({"model":name,"date":d,**z})
 history_models=[x for x in out if "d90_" in x["weights"]]
 common_n=max(x["races"] for x in history_models)
 fair=[x for x in out if x["races"]==common_n]
 fair.sort(key=lambda x:(-x["top3_pct"],-x["top1_pct"],-x["exact_pct"]))
 OUT.mkdir(parents=True,exist_ok=True)
 for fn,data in [("all_models.csv",out),("fair_top3_ranked.csv",fair),("by_date.csv",days)]:
  with (OUT/fn).open("w",encoding="utf-8",newline="") as h:w=csv.DictWriter(h,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 (OUT/"summary.json").write_text(json.dumps({"rule":"motor-only base scan; official top2 and prior-90d motor win/top2/top3; rank-normalized; same maximum eligible race count; TOP3 primary; no target-day leakage","tested":len(out),"max_common_races":common_n,"top30":fair[:30]},ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({"tested":len(out),"max_common_races":maxn,"top20":fair[:20]},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
