from __future__ import annotations
import csv,json,itertools
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
DATES=["20260930","20261001","20261002"];OUT=Path("evaluations/motor_pair_scan")
GRADE={"A1":1.0,"A2":.75,"B1":.45,"B2":.25}
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
 fs=[I(r.get("finish")) for r in rs if I(r.get("finish")) in range(1,7)];sts=[F(r.get("st")) for r in rs if F(r.get("st")) is not None]
 if not fs:return {}
 return {"win":sum(x==1 for x in fs)/len(fs),"top2":sum(x<=2 for x in fs)/len(fs),"top3":sum(x<=3 for x in fs)/len(fs),"avg_finish":sum(fs)/len(fs),"avg_st":sum(sts)/len(sts) if sts else None}
def rank(bs,k,rev=False):
 if any(b.get(k) is None for b in bs):return None
 o=sorted(bs,key=lambda b:((b[k] if rev else -b[k]),b["boat"]))
 return {b["boat"]:1-j/5 for j,b in enumerate(o)}
def eval(races,motor,other,wm):
 n=t1=t3=ex=0
 for _,_,bs in races:
  rm=rank(bs,motor);ro=rank(bs,other,other in {"racer_avg_finish","racer_avg_st"})
  if rm is None or ro is None:continue
  sc={b["boat"]:wm*rm[b["boat"]]+(1-wm)*ro[b["boat"]] for b in bs}
  p=sorted(bs,key=lambda b:(-sc[b["boat"]],b["boat"]));a=sorted(bs,key=lambda b:(b["finish"],b["boat"]))
  n+=1;t1+=p[0]["boat"]==a[0]["boat"];t3+=set(x["boat"] for x in p[:3])==set(x["boat"] for x in a[:3]);ex+=[x["boat"] for x in p[:3]]==[x["boat"] for x in a[:3]]
 return n,t1,t3,ex
def main():
 rows=load();bd=defaultdict(list)
 for r in rows:
  if r.get("date") in DATES:bd[r["date"]].append(r)
 races=[]
 for d in DATES:
  td=dt(d);prior=[r for r in rows if r.get("date") and td-timedelta(days=90)<=dt(r["date"])<td];pg=prog(d)
  rg=defaultdict(list);rc=defaultdict(list);rv=defaultdict(list);mg=defaultdict(list)
  for r in prior:
   reg=r.get("registration_no","");v=str(r.get("venue_code","")).zfill(2);c=I(r.get("course"));m=I(r.get("motor_no"))
   if reg:rg[reg].append(r);rv[(reg,v)].append(r)
   if reg and c:rc[(reg,c)].append(r)
   if m is not None:mg[(v,m)].append(r)
  rr=defaultdict(list)
  for r in bd[d]:
   bo=I(r.get("boat"));fi=I(r.get("finish"));reg=r.get("registration_no","");v=str(r.get("venue_code","")).zfill(2)
   if bo not in range(1,7) or fi not in range(1,7):continue
   P=pg.get((nid(r.get("race_id")),bo),{});R=stat(rg[reg]);C=stat(rc[(reg,bo)]);V=stat(rv[(reg,v)]);M=stat(mg[(v,I(r.get("motor_no")))]) if I(r.get("motor_no")) is not None else {}
   b={"boat":bo,"finish":fi,"motor_official_top2":F(P.get("motor_top2_rate"))/100 if F(P.get("motor_top2_rate")) is not None else None,
      "motor_d90_win":M.get("win"),"motor_d90_top2":M.get("top2"),"motor_d90_top3":M.get("top3"),
      "grade":GRADE.get(P.get("grade","")),"frame":1-(bo-1)/5,
      "racer_win":R.get("win"),"racer_top2":R.get("top2"),"racer_top3":R.get("top3"),"racer_avg_finish":R.get("avg_finish"),"racer_avg_st":R.get("avg_st"),
      "course_win":C.get("win"),"course_top2":C.get("top2"),"course_top3":C.get("top3"),"venue_win":V.get("win"),"venue_top3":V.get("top3")}
   rr[r["race_id"]].append(b)
  for rid,bs in rr.items():
   if len(bs)==6:races.append((d,rid,bs))
 motors=["motor_official_top2","motor_d90_win","motor_d90_top2","motor_d90_top3"]
 others=["grade","frame","racer_win","racer_top2","racer_top3","racer_avg_finish","racer_avg_st","course_win","course_top2","course_top3","venue_win","venue_top3"]
 out=[]
 for m,o,wm in itertools.product(motors,others,[.2,.3,.4,.5,.6,.7,.8]):
  n,a,b,c=eval(races,m,o,wm)
  out.append({"motor_factor":m,"other_factor":o,"motor_weight":wm,"other_weight":round(1-wm,1),"races":n,"top1_pct":round(a/n*100,2) if n else 0,"top3_pct":round(b/n*100,2) if n else 0,"exact_pct":round(c/n*100,2) if n else 0})
 # fair ranking: maximize common/full sample first, then TOP3
 maxn=max(x["races"] for x in out);fair=[x for x in out if x["races"]==maxn];fair.sort(key=lambda x:(-x["top3_pct"],-x["top1_pct"],-x["exact_pct"]))
 OUT.mkdir(parents=True,exist_ok=True)
 with (OUT/"all_pairs.csv").open("w",encoding="utf-8",newline="") as h:w=csv.DictWriter(h,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
 with (OUT/"fair_top3_ranked.csv").open("w",encoding="utf-8",newline="") as h:w=csv.DictWriter(h,fieldnames=list(fair[0]));w.writeheader();w.writerows(fair)
 (OUT/"summary.json").write_text(json.dumps({"rule":"motor fixed as one of two factors; rank-normalized weighted pair; same maximum eligible race count only; ranked by TOP3 then top1 then exact; target-day results labels only","max_common_races":maxn,"tested":len(out),"top30":fair[:30]},ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({"max_common_races":maxn,"tested":len(out),"top20":fair[:20]},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
