from __future__ import annotations
import csv,json,itertools
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
DATES=["20260930","20261001","20261002"];OUT=Path("evaluations/phase7_course_base")
def I(v):
 try:return int(float(v))
 except:return None
def dt(s):return datetime.strptime(s,"%Y%m%d").date()
def load():
 z=[]
 for p in Path("archive").glob("*/*/*/boat_results_*_all.csv"):
  with p.open(encoding="utf-8-sig",newline="") as h:z+=list(csv.DictReader(h))
 return z
def stats(rs):
 fs=[I(r.get("finish")) for r in rs if I(r.get("finish")) in range(1,7)]
 sts=[]
 for r in rs:
  try: sts.append(float(r.get("st")))
  except: pass
 if not fs:return None
 return {"win":sum(x==1 for x in fs)/len(fs),"top2":sum(x<=2 for x in fs)/len(fs),"top3":sum(x<=3 for x in fs)/len(fs),"st":sum(sts)/len(sts) if sts else None,"n":len(fs)}
def rank(bs,k,rev=False):
 if any(b[k] is None for b in bs):return None
 o=sorted(bs,key=lambda b:((b[k] if rev else -b[k]),b["boat"]))
 return {b["boat"]:1-j/5 for j,b in enumerate(o)}
def pred(bs,w):
 qs={}
 for k in w:
  qs[k]=rank(bs,k,rev=(k=="st"))
  if qs[k] is None:return None
 sc={b["boat"]:sum(w[k]*qs[k][b["boat"]] for k in w) for b in bs}
 return sorted(bs,key=lambda b:(-sc[b["boat"]],b["boat"]))
def main():
 rows=load();byd=defaultdict(list)
 for r in rows:
  if r.get("date") in DATES:byd[r["date"]].append(r)
 races=[]
 for d in DATES:
  td=dt(d); prior=[r for r in rows if r.get("date") and td-timedelta(days=90)<=dt(r["date"])<td]
  rc=defaultdict(list)
  for r in prior:
   reg=r.get("registration_no","");c=I(r.get("course"))
   if reg and c:rc[(reg,c)].append(r)
  rr=defaultdict(list)
  for r in byd[d]:
   b=I(r.get("boat"));fin=I(r.get("finish"));reg=r.get("registration_no","")
   if b not in range(1,7) or fin not in range(1,7):continue
   st=stats(rc[(reg,b)])
   if st:rr[r["race_id"]].append({"date":d,"boat":b,"finish":fin,**st})
  for rid,bs in rr.items():
   if len(bs)==6:races.append((d,rid,bs))
 models={"win100":{"win":1},"top2_100":{"top2":1},"top3_100":{"top3":1},"st100":{"st":1}}
 vals=[.1,.2,.3,.4,.5,.6,.7,.8,.9]
 # all two-factor splits
 for a,b in itertools.combinations(["win","top2","top3","st"],2):
  for x in vals:
   models[f"{a}{int(x*100)}_{b}{int((1-x)*100)}"]={a:x,b:1-x}
 # three-factor coarse 20% grid
 for comb in itertools.combinations(["win","top2","top3","st"],3):
  for a in [.2,.4,.6]:
   for b in [.2,.4,.6]:
    c=1-a-b
    if c>=.2-1e-9:
     models["_".join([f"{comb[0]}{int(a*100)}",f"{comb[1]}{int(b*100)}",f"{comb[2]}{int(c*100)}"])]={comb[0]:a,comb[1]:b,comb[2]:c}
 # four factor 10% grid summing 100
 for a in range(1,8):
  for b in range(1,9-a):
   for c in range(1,10-a-b):
    d=10-a-b-c
    if d>=1:
     models[f"win{a*10}_top2{b*10}_top3{c*10}_st{d*10}"]={"win":a/10,"top2":b/10,"top3":c/10,"st":d/10}
 out=[];day=[]
 for name,w in models.items():
  A=defaultdict(int);D={d:defaultdict(int) for d in DATES}
  for d,rid,bs in races:
   p=pred(bs,w)
   if not p:continue
   act=sorted(bs,key=lambda x:(x["finish"],x["boat"]));A["n"]+=1;D[d]["n"]+=1
   checks={"top1":p[0]["boat"]==act[0]["boat"],"top3":set(x["boat"] for x in p[:3])==set(x["boat"] for x in act[:3]),"exact":[x["boat"] for x in p[:3]]==[x["boat"] for x in act[:3]]}
   for k,v in checks.items():A[k]+=v;D[d][k]+=v
  n=A["n"]
  out.append({"model":name,"weights":json.dumps(w,ensure_ascii=False),"races":n,"top1_pct":round(A["top1"]/n*100,2) if n else 0,"top3_pct":round(A["top3"]/n*100,2) if n else 0,"exact_pct":round(A["exact"]/n*100,2) if n else 0})
  for d,x in D.items():
   n=x["n"];day.append({"model":name,"date":d,"races":n,"top1_pct":round(x["top1"]/n*100,2) if n else 0,"top3_pct":round(x["top3"]/n*100,2) if n else 0,"exact_pct":round(x["exact"]/n*100,2) if n else 0})
 out.sort(key=lambda x:(-x["top1_pct"],-x["top3_pct"],-x["exact_pct"]))
 OUT.mkdir(parents=True,exist_ok=True)
 for fn,data in [("phase7_ranked.csv",out),("phase7_by_date.csv",day)]:
  with (OUT/fn).open("w",encoding="utf-8",newline="") as h:w=csv.DictWriter(h,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 (OUT/"phase7_summary.json").write_text(json.dumps({"method":"90日前方のみ。朝は枠番=想定コース。1着率/2連対率/3連対率/平均STをレース内順位正規化して組合せ。出走数nはまず信頼度診断用として保存し、直接加点しない。","models_tested":len(models),"top20":out[:20]},ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({"models":len(models),"top20":out[:20]},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
