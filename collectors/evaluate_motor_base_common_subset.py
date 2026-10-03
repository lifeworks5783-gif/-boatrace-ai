from __future__ import annotations
import csv,json,itertools
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
DATES=["20260930","20261001","20261002"];OUT=Path("evaluations/motor_base_common_subset")
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
 o=sorted(bs,key=lambda b:(-b[k],b["boat"]));return {b["boat"]:1-j/5 for j,b in enumerate(o)}
def score(races,w):
 n=t1=t3=ex=0;by=defaultdict(lambda:[0,0,0,0])
 for d,rid,bs in races:
  rr={k:rank(bs,k) for k in w};sc={b["boat"]:sum(w[k]*rr[k][b["boat"]] for k in w) for b in bs}
  p=sorted(bs,key=lambda b:(-sc[b["boat"]],b["boat"]));a=sorted(bs,key=lambda b:(b["finish"],b["boat"]))
  n+=1;t1+=p[0]["boat"]==a[0]["boat"];t3+=set(x["boat"] for x in p[:3])==set(x["boat"] for x in a[:3]);ex+=[x["boat"] for x in p[:3]]==[x["boat"] for x in a[:3]]
  z=by[d];z[0]+=1;z[1]+=p[0]["boat"]==a[0]["boat"];z[2]+=set(x["boat"] for x in p[:3])==set(x["boat"] for x in a[:3]);z[3]+=[x["boat"] for x in p[:3]]==[x["boat"] for x in a[:3]]
 def fmt(v):
  q=v[0];return {"races":q,"top1_pct":round(v[1]*100/q,2),"top3_pct":round(v[2]*100/q,2),"exact_pct":round(v[3]*100/q,2)}
 return fmt([n,t1,t3,ex]),{d:fmt(v) for d,v in by.items()}
def main():
 rows=load();bd=defaultdict(list)
 for r in rows:
  if r.get("date") in DATES:bd[r["date"]].append(r)
 allr=[];coverage={}
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
  full=[(d,rid,bs) for rid,bs in rr.items() if len(bs)==6];common=[x for x in full if all(all(b.get(k) is not None for k in ["official_top2","d90_win","d90_top2","d90_top3"]) for b in x[2])]
  coverage[d]={"completed_races":len(full),"common_complete_races":len(common)};allr+=common
 factors=["official_top2","d90_win","d90_top2","d90_top3"];models={}
 for k in factors:models[k+"100"]={k:1}
 for a,b in itertools.combinations(factors,2):
  for x in range(1,10):models[f"{a}{x*10}_{b}{(10-x)*10}"]={a:x/10,b:(10-x)/10}
 for comb in itertools.combinations(factors,3):
  for a in range(1,9):
   for b in range(1,10-a):
    c=10-a-b
    if c:models[f"{comb[0]}{a*10}_{comb[1]}{b*10}_{comb[2]}{c*10}"]={comb[0]:a/10,comb[1]:b/10,comb[2]:c/10}
 for a in range(1,8):
  for b in range(1,9-a):
   for c in range(1,10-a-b):
    e=10-a-b-c
    if e:models[f"official{a*10}_win{b*10}_top2{c*10}_top3{e*10}"]={"official_top2":a/10,"d90_win":b/10,"d90_top2":c/10,"d90_top3":e/10}
 out=[];days=[]
 for name,w in models.items():
  x,bdx=score(allr,w);out.append({"model":name,"weights":json.dumps(w),"factor_count":len(w),**x})
  for d,z in bdx.items():days.append({"model":name,"date":d,**z})
 out.sort(key=lambda x:(-x["top3_pct"],-x["top1_pct"],-x["exact_pct"]))
 OUT.mkdir(parents=True,exist_ok=True)
 for fn,data in [("ranked.csv",out),("by_date.csv",days)]:
  with (OUT/fn).open("w",encoding="utf-8",newline="") as h:w=csv.DictWriter(h,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 (OUT/"summary.json").write_text(json.dumps({"rule":"all four motor metrics complete for all six boats before model comparison; prior 90d only; TOP3 primary","coverage":coverage,"common_races":len(allr),"tested":len(out),"top30":out[:30]},ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({"coverage":coverage,"common_races":len(allr),"tested":len(out),"top20":out[:20]},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
