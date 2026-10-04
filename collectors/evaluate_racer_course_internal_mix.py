#!/usr/bin/env python3
# Compare racer-course internal mix while keeping top-level racer_course weight at 40%.
import csv,json,glob
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
DATES=["20260930","20261001","20261002","20261003"]
MIXES={"current_40_20_30_10":(.40,.20,.30,.10),"candidate_30_30_30_10":(.30,.30,.30,.10)}
def F(v):
 try:return float(v)
 except:return None
def I(v):
 try:return int(float(v))
 except:return None
def DT(v):return datetime.strptime(v,"%Y%m%d").date()
def read(p):
 with open(p,encoding="utf-8-sig",newline="") as h:return list(csv.DictReader(h))
def rank(vals,lower=False):
 valid=[(k,v) for k,v in vals.items() if v is not None]
 if not valid:return {}
 valid.sort(key=lambda x:((x[1] if lower else -x[1]),x[0]))
 r={valid[0][0]:.5} if len(valid)==1 else {k:1-i/(len(valid)-1) for i,(k,v) in enumerate(valid)}
 for k,v in vals.items():
  if v is None:r[k]=.5
 return r
rows=[]
for p in Path("archive").glob("*/*/*/boat_results_*_all.csv"):rows+=read(p)
out={}
for mixname,mix in MIXES.items():
 A=defaultdict(float);daily={}
 for d in DATES:
  prior=[r for r in rows if r.get("date") and DT(d)-timedelta(days=90)<=DT(r["date"])<DT(d)]
  rg=defaultdict(list);rc=defaultdict(list)
  for r in prior:
   reg=r.get("registration_no","");co=I(r.get("course"))
   if reg:rg[reg].append(r)
   if reg and co:rc[(reg,co)].append(r)
  def stat(z):
   fs=[I(x.get("finish")) for x in z if I(x.get("finish")) in range(1,7)]
   sts=[F(x.get("st")) for x in z if F(x.get("st")) is not None]
   return {"win":sum(x==1 for x in fs)/len(fs) if fs else None,"t2":sum(x<=2 for x in fs)/len(fs) if fs else None,"t3":sum(x<=3 for x in fs)/len(fs) if fs else None,"st":sum(sts)/len(sts) if sts else None}
  races=defaultdict(list)
  for r in [x for x in rows if x.get("date")==d]:
   bo=I(r.get("boat"));fi=I(r.get("finish"));reg=r.get("registration_no","")
   if bo in range(1,7) and fi in range(1,7):
    s=stat(rc[(reg,bo)]); races[r.get("race_id")].append({"boat":bo,"finish":fi,**s})
  D=defaultdict(float)
  for bs in races.values():
   if len(bs)!=6:continue
   maps=[rank({b["boat"]:b[k] for b in bs},k=="st") for k in ("win","t2","t3","st")]
   if any(len(x)!=6 for x in maps):continue
   rcscore={b["boat"]:sum(w*m[b["boat"]] for w,m in zip(mix,maps)) for b in bs}
   # isolate internal racer-course factor: evaluate its ordering directly
   po=sorted(rcscore,key=lambda x:(-rcscore[x],x)); ao=[b["boat"] for b in sorted(bs,key=lambda x:(x["finish"],x["boat"]))];wr=po.index(ao[0])+1
   for Z in (A,D):
    Z["n"]+=1;Z["t1"]+=wr==1;Z["w2"]+=wr<=2;Z["w3"]+=wr<=3;Z["e3"]+=set(po[:3])==set(ao[:3]);Z["ord"]+=po[:3]==ao[:3];Z["rs"]+=wr
  daily[d]={"n":int(D["n"]),"top1_pct":round(100*D["t1"]/D["n"],2),"exact_top3_pct":round(100*D["e3"]/D["n"],2)}
 out[mixname]={"n":int(A["n"]),"top1_pct":round(100*A["t1"]/A["n"],2),"winner_top2_pct":round(100*A["w2"]/A["n"],2),"winner_top3_pct":round(100*A["w3"]/A["n"],2),"exact_top3_pct":round(100*A["e3"]/A["n"],2),"ordered_top3_pct":round(100*A["ord"]/A["n"],2),"avg_winner_rank":round(A["rs"]/A["n"],4),"daily":daily}
Path("evaluations/racer_course_internal_mix").mkdir(parents=True,exist_ok=True)
Path("evaluations/racer_course_internal_mix/summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
