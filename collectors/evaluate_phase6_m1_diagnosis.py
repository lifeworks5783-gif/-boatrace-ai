from __future__ import annotations
import csv,json
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
DATES=["20260930","20261001","20261002"];OUT=Path("evaluations/phase6_m1_diagnosis");GRADE={"A1":1.0,"A2":.75,"B1":.45,"B2":.25}
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
def prog(d):
 p=Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/program_entries_{d}.csv")
 if not p.exists():p=Path(f"data/program_entries_{d}.csv")
 if not p.exists():return {}
 with p.open(encoding="utf-8-sig",newline="") as h:return {(nid(r["race_id"]),i(r["boat"])):r for r in csv.DictReader(h)}
def hs(rs):
 x=[i(r.get("finish")) for r in rs if i(r.get("finish")) in range(1,7)]
 return {} if not x else {"win":sum(a==1 for a in x)/len(x),"top3":sum(a<=3 for a in x)/len(x),"n":len(x)}
def rank(bs,k):
 if any(b.get(k) is None for b in bs):return None
 o=sorted(bs,key=lambda b:(-b[k],b["boat"]))
 return {b["boat"]:1-j/5 for j,b in enumerate(o)}
def main():
 rows=load();bd=defaultdict(list)
 for r in rows:
  if r.get("date") in DATES:bd[r["date"]].append(r)
 races={}
 for d in DATES:
  td=dt(d); prior=[r for r in rows if r.get("date") and td-timedelta(days=90)<=dt(r["date"])<td];p=prog(d)
  rg=defaultdict(list);rc=defaultdict(list)
  for r in prior:
   reg=r.get("registration_no","");co=i(r.get("course"))
   if reg:rg[reg].append(r)
   if reg and co:rc[(reg,co)].append(r)
  rr=defaultdict(list)
  for r in bd[d]:
   bo=i(r.get("boat"));fi=i(r.get("finish"))
   if bo not in range(1,7) or fi not in range(1,7):continue
   reg=r.get("registration_no","");A=hs(rg[reg]);C=hs(rc[(reg,bo)]);q=p.get((nid(r.get("race_id")),bo),{})
   rr[r["race_id"]].append({"boat":bo,"finish":fi,"rc_win":C.get("win"),"rc_n":C.get("n"),"grade":GRADE.get(q.get("grade","")),"grade_raw":q.get("grade",""),"national_top3":A.get("top3"),"national_n":A.get("n")})
  races.update(rr)
 cases=[];counts=defaultdict(int); driver=defaultdict(int)
 for rid,bs in races.items():
  if len(bs)!=6:continue
  R=rank(bs,"rc_win");G=rank(bs,"grade");N=rank(bs,"national_top3")
  if None in (R,G,N):continue
  base=sorted(bs,key=lambda b:(-R[b["boat"]],b["boat"]))
  scores={b["boat"]:R[b["boat"]]+.2*G[b["boat"]]+.1*N[b["boat"]] for b in bs}
  m1=sorted(bs,key=lambda b:(-scores[b["boat"]],b["boat"]));act=sorted(bs,key=lambda b:(b["finish"],b["boat"]))
  bf1=base[0]["boat"]==act[0]["boat"];mf1=m1[0]["boat"]==act[0]["boat"]
  bf3=set(x["boat"] for x in base[:3])==set(x["boat"] for x in act[:3]);mf3=set(x["boat"] for x in m1[:3])==set(x["boat"] for x in act[:3])
  t1=("○" if bf1 else "×")+"→"+("○" if mf1 else "×");t3=("○" if bf3 else "×")+"→"+("○" if mf3 else "×")
  counts["top1_"+t1]+=1;counts["top3_"+t3]+=1
  if t1 in ("×→○","○→×") or t3 in ("×→○","○→×"):
   moved=[b for b in bs if [x["boat"] for x in base].index(b["boat"]) != [x["boat"] for x in m1].index(b["boat"])]
   # determine which correction had stronger rank advantage for newly promoted top boat(s)
   promoted=sorted(moved,key=lambda b:([x["boat"] for x in m1].index(b["boat"])-[x["boat"] for x in base].index(b["boat"])))
   lead=promoted[0] if promoted else None
   why=""
   if lead:
    gv=.2*G[lead["boat"]];nv=.1*N[lead["boat"]]
    why="grade" if gv>nv else ("national_top3" if nv>gv else "mixed")
    driver[(t1,t3,why)]+=1
   cases.append({"date":bs[0].get("date","") or rid[:8],"race_id":rid,"actual":"-".join(str(x["boat"]) for x in act[:3]),"base_pred":"-".join(str(x["boat"]) for x in base[:3]),"m1_pred":"-".join(str(x["boat"]) for x in m1[:3]),"top1_transition":t1,"top3_transition":t3,"main_driver":why,
    "boats":json.dumps([{"boat":b["boat"],"finish":b["finish"],"base_rank":[x["boat"] for x in base].index(b["boat"])+1,"m1_rank":[x["boat"] for x in m1].index(b["boat"])+1,"course_win":round(b["rc_win"],4),"course_n":b["rc_n"],"grade":b["grade_raw"],"grade_rank":round(G[b["boat"]],2),"national_top3":round(b["national_top3"],4),"national_n":b["national_n"],"national_rank":round(N[b["boat"]],2),"m1_score":round(scores[b["boat"]],3)} for b in bs],ensure_ascii=False)})
 OUT.mkdir(parents=True,exist_ok=True)
 with (OUT/"phase6_m1_changed_cases.csv").open("w",encoding="utf-8",newline="") as h:
  w=csv.DictWriter(h,fieldnames=list(cases[0]));w.writeheader();w.writerows(cases)
 summary={"counts":dict(counts),"driver_counts":[{"top1_transition":k[0],"top3_transition":k[1],"driver":k[2],"cases":v} for k,v in driver.items()],"important_cases":len(cases),"interpretation_rule":"main_driverは昇格艇に対する補正寄与の大小による簡易分類。因果確定ではなく診断用。"}
 (OUT/"phase6_m1_diagnosis.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
