from __future__ import annotations
import csv,json
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
DATES=["20260930","20261001","20261002","20261003"]
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
 for p in [Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/program_entries_{d}.csv"),Path(f"data/program_entries_{d}.csv")]:
  if p.exists():return {(nid(r.get("race_id")),I(r.get("boat"))):r for r in read(p)}
 return {}
def live_entries(d):
 ps=list(Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/live/backfill").glob(f"beforeinfo_entries_{d}.csv"))
 if not ps:ps=list(Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/live/snapshots").glob(f"*/beforeinfo_entries_{d}.csv"))
 best={}
 for p in ps:
  for r in read(p):
   k=(nid(r.get("race_id")),I(r.get("boat")))
   if k[0] and k[1] in range(1,7):best[k]=r
 return best
def live_races(d):
 ps=list(Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/live/raw").glob(f"*/beforeinfo_races_{d}.csv"))
 if not ps:ps=list(Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/live/snapshots").glob(f"*/beforeinfo_races_{d}.csv"))
 if not ps:ps=list(Path(f"daily_inputs/{d[:4]}/{d[4:6]}/{d[6:8]}/live/backfill").glob(f"beforeinfo_races_{d}.csv"))
 best={}
 for p in ps:
  for r in read(p):
   rid=nid(r.get("race_id"))
   if rid:best[rid]=r
 return best
def stat(rs):
 fs=[I(r.get("finish")) for r in rs if I(r.get("finish")) in range(1,7)];sts=[F(r.get("st")) for r in rs if F(r.get("st")) is not None]
 if not fs:return {}
 return {"win":sum(x==1 for x in fs)/len(fs),"top2":sum(x<=2 for x in fs)/len(fs),"top3":sum(x<=3 for x in fs)/len(fs),"avg_st":sum(sts)/len(sts) if sts else None}
def rankmap(bs,key,rev=False):
 if len(bs)!=6 or any(b.get(key) is None for b in bs):return None
 o=sorted(bs,key=lambda b:((b[key] if rev else -b[key]),b["boat"]));return {b["boat"]:1-j/5 for j,b in enumerate(o)}
def hit(bs,sc):
 p=sorted(bs,key=lambda b:(-sc[b["boat"]],b["boat"]));a=sorted(bs,key=lambda b:(b["finish"],b["boat"]));return set(x["boat"] for x in p[:3])==set(x["boat"] for x in a[:3])
def bucket(field,v):
 if v is None:return None
 if field=="wind_speed":return "0-2" if v<3 else "3-4" if v<5 else "5+"
 if field=="wave":return "0-2" if v<3 else "3-4" if v<5 else "5+"
 if field=="air":return "<20" if v<20 else "20-24" if v<25 else "25+"
 if field=="water":return "<22" if v<22 else "22-25" if v<26 else "26+"
 if field=="wind_dir":return str(int(v))
def main():
 rows=archive();bd=defaultdict(list)
 for r in rows:bd[r.get("date")].append(r)
 results=[]
 for field in ["wind_speed","wave","air","water","wind_dir"]:
  for w in [2,4,6,8,10]:
   days=[];xp=xm=0
   for d in DATES:
    td=DT(d);prior=[r for r in rows if r.get("date") and td-timedelta(days=90)<=DT(r["date"])<td];pg=program(d);le=live_entries(d);lr=live_races(d)
    rg=defaultdict(list);rc=defaultdict(list);mg=defaultdict(list);bg=defaultdict(list)
    for r in prior:
     reg=r.get("registration_no","");c=I(r.get("course"));v=str(r.get("venue_code","")).zfill(2);mm=I(r.get("motor_no"));bn=I(r.get("boat_no"))
     if reg:rg[reg].append(r)
     if reg and c:rc[(reg,c)].append(r)
     if mm is not None:mg[(v,mm)].append(r)
     if bn is not None:bg[(v,bn)].append(r)
    # Environment x course evidence from earlier target dates only; never current-date outcomes.
    envhist=defaultdict(list)
    for hd in DATES:
     if hd>=d:continue
     henv=live_races(hd)
     for rr in bd[hd]:
      rid=nid(rr.get("race_id"));c=I(rr.get("course")) or I(rr.get("boat"));e=henv.get(rid,{})
      raw={"wind_speed":F(e.get("wind_speed_mps")),"wave":F(e.get("wave_height_cm")),"air":F(e.get("air_temperature_c")),"water":F(e.get("water_temperature_c")),"wind_dir":F(e.get("wind_direction_code"))}[field];b=bucket(field,raw);fi=I(rr.get("finish"))
      if b and c and fi in range(1,7):envhist[(b,c)].append(fi)
    rr=defaultdict(list)
    for r in bd[d]:
     bo=I(r.get("boat"));fi=I(r.get("finish"));rid=nid(r.get("race_id"))
     if bo not in range(1,7) or fi not in range(1,7):continue
     v=str(r.get("venue_code","")).zfill(2);reg=r.get("registration_no","");P=pg.get((rid,bo),{});Q=le.get((rid,bo),{});E=lr.get(rid,{});entry=I(Q.get("exhibition_course")) or bo
     rs=stat(rg[reg]);ls=stat(rc[(reg,entry)]);ms=stat(mg[(v,I(r.get("motor_no")))]) if I(r.get("motor_no")) is not None else {};bt=stat(bg[(v,I(r.get("boat_no")))]) if I(r.get("boat_no")) is not None else {}
     raw={"wind_speed":F(E.get("wind_speed_mps")),"wave":F(E.get("wave_height_cm")),"air":F(E.get("air_temperature_c")),"water":F(E.get("water_temperature_c")),"wind_dir":F(E.get("wind_direction_code"))}[field];bk=bucket(field,raw);hs=envhist.get((bk,entry),[]);ev=sum(x<=3 for x in hs)/len(hs) if len(hs)>=6 else None
     rr[rid].append({"boat":bo,"finish":fi,"lw":ls.get("win"),"l2":ls.get("top2"),"l3":ls.get("top3"),"lst":ls.get("avg_st"),"grade":GRADE.get(P.get("grade","")),"nat2":rs.get("top2"),"mw":ms.get("win"),"m3":ms.get("top3"),"b2":bt.get("top2"),"b3":bt.get("top3"),"est":F(Q.get("exhibition_st_seconds")),"env":ev})
    n=bh=nh=0
    for rid,bs in rr.items():
     def bkmap(keys):
      z=[]
      for k,ww,rev in keys:
       q=rankmap(bs,k,rev)
       if q is None:return None
       z.append((q,ww))
      return {b["boat"]:sum(q[b["boat"]]*ww for q,ww in z) for b in bs}
     re=bkmap([("lw",.4,False),("l2",.2,False),("l3",.3,False),("lst",.1,True)]);mo=bkmap([("mw",.4,False),("m3",.6,False)]);ba=bkmap([("b2",.5,False),("b3",.5,False)]);gr=rankmap(bs,"grade");nat=rankmap(bs,"nat2");es=rankmap(bs,"est",True);en=rankmap(bs,"env")
     if any(x is None for x in [re,mo,ba,gr,nat,es,en]):continue
     struct={b:.4*re[b]+.2*gr[b]+.1*mo[b]+.1*ba[b]+.2*nat[b] for b in re};base={b:.84*struct[b]+.16*es[b] for b in struct};new={b:(1-w/100)*base[b]+w/100*en[b] for b in base};a=hit(bs,base);z=hit(bs,new);n+=1;bh+=a;nh+=z;xp+=(not a) and z;xm+=a and (not z)
    days.append({"date":d,"n":n,"base_pct":round(100*bh/n,2) if n else None,"new_pct":round(100*nh/n,2) if n else None})
   vv=[x["new_pct"] for x in days if x["new_pct"] is not None]
   results.append({"factor":field+"_x_course","weight_pct":w,"by_date":days,"daily_avg_top3_pct":round(sum(vv)/len(vv),2) if vv else None,"spread_pt":round(max(vv)-min(vv),2) if vv else None,"x_to_o":xp,"o_to_x":xm,"net_flips":xp-xm})
 results.sort(key=lambda x:(-(x["daily_avg_top3_pct"] or -1),x["spread_pt"] if x["spread_pt"] is not None else 999,-x["net_flips"]))
 out=Path("evaluations/environment_course_interactions_20260930_20261003");out.mkdir(parents=True,exist_ok=True);(out/"summary.json").write_text(json.dumps({"definition":"TOP3 unordered exact set","leakage_guard":"environment-course evidence uses only earlier dates among target period; target-date outcomes excluded","minimum_history_samples_per_bucket_course":6,"results":results},ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(results[:20],ensure_ascii=False,indent=2))
if __name__=="__main__":main()
