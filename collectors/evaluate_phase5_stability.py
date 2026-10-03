from __future__ import annotations
import csv,json
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
DATES=["20260930","20261001","20261002"]; OUT=Path("evaluations/phase5_stability")
GRADE={"A1":1.0,"A2":0.75,"B1":0.45,"B2":0.25}
MODELS={
"BASE":[],
"M1_grade20_nationalTop3_10":[("grade",.20),("national_top3",.10)],
"M2_grade20_motor20_nationalWin20":[("grade",.20),("motor",.20),("national_win",.20)],
"M3_grade20_nationalTop3_10_nationalWin10":[("grade",.20),("national_top3",.10),("national_win",.10)],
"M4_grade30_nationalWin10":[("grade",.30),("national_win",.10)],
}
def f(v):
 try:return float(v)
 except:return None
def i(v):
 try:return int(float(v))
 except:return None
def dt(v):return datetime.strptime(v,"%Y%m%d").date()
def nid(v):return "".join(c for c in (v or "") if c.isdigit())
def load():
 z=[]
 for p in Path("archive").glob("*/*/*/boat_results_*_all.csv"):
  with p.open(encoding="utf-8-sig",newline="") as h:z+=list(csv.DictReader(h))
 return z
def program(d):
 for p in [Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/program_entries_{d}.csv"),Path(f"data/program_entries_{d}.csv")]:
  if p.exists():
   with p.open(encoding="utf-8-sig",newline="") as h:return {(nid(r["race_id"]),i(r["boat"])):r for r in csv.DictReader(h)}
 return {}
def hs(rs):
 x=[i(r.get("finish")) for r in rs if i(r.get("finish")) in range(1,7)]
 return {} if not x else {"win":sum(a==1 for a in x)/len(x),"top3":sum(a<=3 for a in x)/len(x)}
def ranks(bs,k):
 if any(b.get(k) is None for b in bs):return None
 o=sorted(bs,key=lambda b:(-b[k],b["boat"]))
 return {b["boat"]:1-j/5 for j,b in enumerate(o)}
def pred(bs,mods):
 q0=ranks(bs,"rc_win")
 if q0 is None:return None
 qs=[]
 for k,w in mods:
  q=ranks(bs,k)
  if q is None:return None
  qs.append((q,w))
 sc={b["boat"]:q0[b["boat"]]+sum(w*q[b["boat"]] for q,w in qs) for b in bs}
 return sorted(bs,key=lambda b:(-sc[b["boat"]],b["boat"])),sc
def flags(p,actual):
 return {"top1":p[0]["boat"]==actual[0]["boat"],"top3":set(x["boat"] for x in p[:3])==set(x["boat"] for x in actual[:3]),"exact":[x["boat"] for x in p[:3]]==[x["boat"] for x in actual[:3]]}
def main():
 rows=load(); bd=defaultdict(list)
 for r in rows:
  if r.get("date") in DATES:bd[r["date"]].append(r)
 races=defaultdict(list)
 for d in DATES:
  td=dt(d);prior=[r for r in rows if r.get("date") and td-timedelta(days=90)<=dt(r["date"])<td];pg=program(d)
  rg=defaultdict(list);rc=defaultdict(list)
  for r in prior:
   reg=r.get("registration_no","");co=i(r.get("course"))
   if reg:rg[reg].append(r)
   if reg and co:rc[(reg,co)].append(r)
  for r in bd[d]:
   bo=i(r.get("boat"));fi=i(r.get("finish"))
   if bo not in range(1,7) or fi not in range(1,7):continue
   reg=r.get("registration_no","");p=pg.get((nid(r.get("race_id")),bo),{});A=hs(rg[reg]);C=hs(rc[(reg,bo)])
   races[r["race_id"]].append({"date":d,"boat":bo,"finish":fi,"rc_win":C.get("win"),"grade":GRADE.get(p.get("grade","")),"national_top3":A.get("top3"),"national_win":A.get("win"),"motor":f(p.get("motor_top2_rate"))/100 if f(p.get("motor_top2_rate")) is not None else None})
 detail=[]; agg={m:defaultdict(int) for m in MODELS}; day={m:{d:defaultdict(int) for d in DATES} for m in MODELS}
 for rid,bs in races.items():
  if len(bs)!=6:continue
  actual=sorted(bs,key=lambda b:(b["finish"],b["boat"]))
  bp=pred(bs,MODELS["BASE"])
  if bp is None:continue
  bf=flags(bp[0],actual)
  for name,mods in MODELS.items():
   z=pred(bs,mods)
   if z is None:continue
   pf=flags(z[0],actual); d=bs[0]["date"]
   agg[name]["races"]+=1;day[name][d]["races"]+=1
   for k in ["top1","top3","exact"]:
    agg[name][k]+=int(pf[k]);day[name][d][k]+=int(pf[k])
   if name!="BASE":
    rec={"date":d,"race_id":rid,"model":name,"actual":"-".join(str(x["boat"]) for x in actual[:3]),"base_pred":"-".join(str(x["boat"]) for x in bp[0][:3]),"model_pred":"-".join(str(x["boat"]) for x in z[0][:3])}
    for k in ["top1","top3"]:
     rec[k+"_transition"]=("○" if bf[k] else "×")+"→"+("○" if pf[k] else "×")
    if rec["top1_transition"]!="○→○" or rec["top3_transition"]!="○→○":detail.append(rec)
 summary=[]
 for name,a in agg.items():
  n=a["races"]; summary.append({"model":name,"races":n,"top1_pct":round(a["top1"]/n*100,2) if n else None,"top3_pct":round(a["top3"]/n*100,2) if n else None,"exact_pct":round(a["exact"]/n*100,2) if n else None})
 days=[]
 for name,ds in day.items():
  for d,a in ds.items():
   n=a["races"];days.append({"model":name,"date":d,"races":n,"top1_pct":round(a["top1"]/n*100,2) if n else None,"top3_pct":round(a["top3"]/n*100,2) if n else None,"exact_pct":round(a["exact"]/n*100,2) if n else None})
 trans=[]
 for name in MODELS:
  if name=="BASE":continue
  rr=[x for x in detail if x["model"]==name]
  for metric in ["top1","top3"]:
   c=defaultdict(int)
   for x in rr:c[x[metric+"_transition"]]+=1
   # unchanged correct rows excluded from detail; recover ○→○ from total/base intersections not needed for net diagnosis
   trans.append({"model":name,"metric":metric,"base_wrong_to_model_correct":c["×→○"],"base_correct_to_model_wrong":c["○→×"],"net_gain":c["×→○"]-c["○→×"]})
 OUT.mkdir(parents=True,exist_ok=True)
 def write(fn,rowsx):
  if not rowsx:return
  with (OUT/fn).open("w",encoding="utf-8",newline="") as h:w=csv.DictWriter(h,fieldnames=list(rowsx[0]));w.writeheader();w.writerows(rowsx)
 write("phase5_summary.csv",summary);write("phase5_by_date.csv",days);write("phase5_transitions.csv",trans);write("phase5_changed_races.csv",detail)
 (OUT/"phase5_summary.json").write_text(json.dumps({"models":MODELS,"summary":summary,"by_date":days,"transitions":trans,"rule":"同一データ構築。対象日前90日。BASEから×→○と○→×の差で改善の実体を確認。"},ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({"summary":summary,"by_date":days,"transitions":trans},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
