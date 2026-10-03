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
def rankmap(bs,key,reverse=False):
 if len(bs)!=6 or any(b.get(key) is None for b in bs):return None
 o=sorted(bs,key=lambda b:((b[key] if reverse else -b[key]),b["boat"]))
 return {b["boat"]:1-j/5 for j,b in enumerate(o)}
def hit(bs,sc):
 p=sorted(bs,key=lambda b:(-sc[b["boat"]],b["boat"]))
 a=sorted(bs,key=lambda b:(b["finish"],b["boat"]))
 return set(x["boat"] for x in p[:3])==set(x["boat"] for x in a[:3])
def main():
 rows=archive();bd=defaultdict(list)
 for r in rows:bd[r.get("date")].append(r)
 allres=[]
 for model,weights in [("avg_best",(40,20,20,5,15)),("stable",(40,20,10,10,20))]:
  for wt in [0,4,8]:
   for ws in [14,16,18,20]:
   vals=[];flipplus=flipminus=0
   for d in DATES:
    td=DT(d);prior=[r for r in rows if r.get("date") and td-timedelta(days=90)<=DT(r["date"])<td];pg=program(d);lv=live_entries(d)
    rc=defaultdict(list);rg=defaultdict(list);mg=defaultdict(list);bg=defaultdict(list)
    for r in prior:
     reg=r.get("registration_no","");c=I(r.get("course"));v=str(r.get("venue_code","")).zfill(2);mm=I(r.get("motor_no"));bn=I(r.get("boat_no"))
     if reg:rg[reg].append(r)
     if reg and c:rc[(reg,c)].append(r)
     if mm is not None:mg[(v,mm)].append(r)
     if bn is not None:bg[(v,bn)].append(r)
    rr=defaultdict(list)
    for r in bd[d]:
     bo=I(r.get("boat"));fi=I(r.get("finish"));rid=nid(r.get("race_id"))
     if bo not in range(1,7) or fi not in range(1,7):continue
     v=str(r.get("venue_code","")).zfill(2);reg=r.get("registration_no","");P=pg.get((rid,bo),{});Q=lv.get((rid,bo),{});entry=I(Q.get("exhibition_course")) or bo
     rs=stat(rg[reg]);cs=stat(rc[(reg,bo)]);ls=stat(rc[(reg,entry)]);ms=stat(mg[(v,I(r.get("motor_no")))]) if I(r.get("motor_no")) is not None else {};bs=stat(bg[(v,I(r.get("boat_no")))]) if I(r.get("boat_no")) is not None else {}
     rr[rid].append({"boat":bo,"finish":fi,"cw":cs.get("win"),"c2":cs.get("top2"),"c3":cs.get("top3"),"cst":cs.get("avg_st"),"lw":ls.get("win"),"l2":ls.get("top2"),"l3":ls.get("top3"),"lst":ls.get("avg_st"),"grade":GRADE.get(P.get("grade","")),"nat2":rs.get("top2"),"mw":ms.get("win"),"m3":ms.get("top3"),"b2":bs.get("top2"),"b3":bs.get("top3"),"etime":F(Q.get("exhibition_time")),"est":F(Q.get("exhibition_st_seconds"))})
    n=mh=lh=0
    for rid,bs in rr.items():
     def bk(keys):
      z=[]
      for k,w,rev in keys:
       q=rankmap(bs,k,rev)
       if q is None:return None
       z.append((q,w))
      return {b["boat"]:sum(q[b["boat"]]*w for q,w in z) for b in bs}
     r0=bk([("cw",.4,False),("c2",.2,False),("c3",.3,False),("cst",.1,True)]);re=bk([("lw",.4,False),("l2",.2,False),("l3",.3,False),("lst",.1,True)]);mo=bk([("mw",.4,False),("m3",.6,False)]);ba=bk([("b2",.5,False),("b3",.5,False)]);gr=rankmap(bs,"grade");nat=rankmap(bs,"nat2");et=rankmap(bs,"etime",True);es=rankmap(bs,"est",True)
     if any(x is None for x in [r0,re,mo,ba,gr,nat,et,es]):continue
     wr,wg,wm,wb,wn=weights
     morning={b:wr/100*r0[b]+wg/100*gr[b]+wm/100*mo[b]+wb/100*ba[b]+wn/100*nat[b] for b in r0};struct={b:wr/100*re[b]+wg/100*gr[b]+wm/100*mo[b]+wb/100*ba[b]+wn/100*nat[b] for b in re};rem=1-(wt+ws)/100
     live={b:rem*struct[b]+wt/100*et[b]+ws/100*es[b] for b in struct};a=hit(bs,morning);z=hit(bs,live);n+=1;mh+=a;lh+=z;flipplus+=(not a) and z;flipminus+=a and (not z)
    vals.append({"date":d,"n":n,"morning_pct":round(100*mh/n,2) if n else None,"live_pct":round(100*lh/n,2) if n else None})
   vv=[x["live_pct"] for x in vals if x["live_pct"] is not None];allres.append({"model":model,"weights":weights,"time_pct":wt,"st_pct":ws,"structural_pct":100-wt-ws,"by_date":vals,"daily_avg_top3_pct":round(sum(vv)/len(vv),2),"spread_pt":round(max(vv)-min(vv),2),"x_to_o":flipplus,"o_to_x":flipminus,"net_flips":flipplus-flipminus})
 allres.sort(key=lambda x:(-x["daily_avg_top3_pct"],x["spread_pt"],-x["net_flips"]))
 out=Path("evaluations/new_morning_live_scan_20260930_20261003");out.mkdir(parents=True,exist_ok=True);(out/"summary.json").write_text(json.dumps({"definition":"TOP3 unordered exact set","results":allres},ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(allres[:20],ensure_ascii=False,indent=2))
if __name__=="__main__":main()
