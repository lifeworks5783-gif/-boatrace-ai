from __future__ import annotations
import csv,json,itertools
from collections import defaultdict
from pathlib import Path

DATES=["20260930","20261001","20261002","20261003","20261004","20261005"]
TARGET="20261005"
OUT=Path("evaluations/live_weights_from_pdca")
def F(x):
 try:return float(x)
 except:return None
def I(x):
 try:return int(float(x))
 except:return None
def load(d):
 p=Path(f"evaluations/pdca_datasets/{d}/comparison_dataset_{d}.csv")
 with p.open(encoding="utf-8-sig",newline="") as h: rows=list(csv.DictReader(h))
 rr=defaultdict(list)
 for r in rows:
  z={k:(r[k] if k=="exhibition_st_flag" else F(r[k])) for k in r if k!="race_id"}
  z["boat"]=I(r["boat"]);z["finish"]=I(r["finish"]);z["exhibition_course"]=I(r["exhibition_course"])
  rr[r["race_id"]].append(z)
 return rr
def rankmap(bs,key,reverse=False,neutral_missing=False):
 vals=[b.get(key) for b in bs]
 good=[v for v in vals if v is not None]
 if len(good)<2:return None
 o=sorted([b for b in bs if b.get(key) is not None],key=lambda b:((b[key] if reverse else -b[key]),b["boat"]))
 m={b["boat"]:1-j/max(1,len(o)-1) for j,b in enumerate(o)}
 if neutral_missing:
  for b in bs:m.setdefault(b["boat"],.5)
 elif len(m)!=len(bs):return None
 return m
def structural(bs,entry_blend):
 maps={}
 for k,rev in [("cw",0),("c2",0),("c3",0),("cst",1),("lw",0),("l2",0),("l3",0),("lst",1),("grade",0),("nat2",0),("motor_win",0),("motor_top3",0),("boat2",0),("boat3",0)]:
  maps[k]=rankmap(bs,k,bool(rev))
  if maps[k] is None:return None
 sc={}
 for b in bs:
  q=b["boat"]
  morning=.16*maps["cw"][q]+.08*maps["c2"][q]+.12*maps["c3"][q]+.04*maps["cst"][q]
  live=.16*maps["lw"][q]+.08*maps["l2"][q]+.12*maps["l3"][q]+.04*maps["lst"][q]
  course=(1-entry_blend)*morning+entry_blend*live
  sc[q]=course+.20*maps["grade"][q]+.15*maps["nat2"][q]+.08*maps["motor_win"][q]+.12*maps["motor_top3"][q]+.025*maps["boat2"][q]+.025*maps["boat3"][q]
 return sc
def order(bs,tw,sw,entry_blend,xf_mode,rf_pen):
 st=rankmap(bs,"est",True,True);tm=rankmap(bs,"etime",True,True);base=structural(bs,entry_blend)
 if st is None or tm is None or base is None:return None
 scores={}
 for b in bs:
  q=b["boat"];sv=st[q]
  if str(b.get("exhibition_st_flag","")).upper()=="F":
   sv={"neutral":.5,"mild":.35,"strong":0.0}[xf_mode]
  fcnt=b.get("racer_f90_count") or 0
  fmult=max(.55,1-rf_pen*min(fcnt,2))
  scores[q]=((1-tw-sw)*base[q]+tw*tm[q]+sw*sv)*fmult
 return [b["boat"] for b in sorted(bs,key=lambda b:(-scores[b["boat"]],b["boat"]))]
def actual(bs):return [b["boat"] for b in sorted(bs,key=lambda b:(b["finish"],b["boat"]))]
def hit3(p,a):return set(p[:3])==set(a[:3])
def metrics(data,cfg,baseline_orders=None):
 z={"n":0,"top1":0,"top3":0,"exact":0,"morning_hit":0,"oo":0,"ox":0,"xo":0,"xx":0,"current_rescued":0,"current_broken":0}
 for rid,bs in data.items():
  if len(bs)!=6:continue
  p=order(bs,*cfg);m=order(bs,0,0,0,"neutral",0)
  if p is None or m is None:continue
  a=actual(bs);ph=hit3(p,a);mh=hit3(m,a)
  z["n"]+=1;z["top1"]+=p[0]==a[0];z["top3"]+=ph;z["exact"]+=p[:3]==a[:3];z["morning_hit"]+=mh
  z["oo" if mh and ph else "ox" if mh else "xo" if ph else "xx"]+=1
  if baseline_orders and rid in baseline_orders:
   bh=hit3(baseline_orders[rid],a)
   z["current_rescued"]+=(not bh and ph);z["current_broken"]+=(bh and not ph)
 for k in ["top1","top3","exact","morning_hit"]:z[k+"_pct"]=round(100*z[k]/z["n"],2) if z["n"] else None
 z["net_vs_current"]=z["current_rescued"]-z["current_broken"]
 return z
def main():
 data={d:load(d) for d in DATES}
 current_cfg=(.06,.14,1.0,"neutral",0.0)
 current_orders={rid:order(bs,*current_cfg) for rid,bs in data[TARGET].items() if len(bs)==6}
 grid=[]
 for tw in [0,.04,.06,.08,.12]:
  for sw in [0,.06,.10,.14,.18,.20]:
   if tw+sw>.30:continue
   for eb in [0,.5,1.0]:
    for xf in ["neutral","mild","strong"]:
     for rf in [0,.06,.12]:
      cfg=(tw,sw,eb,xf,rf)
      t=metrics(data[TARGET],cfg,current_orders)
      if not t["n"]:continue
      vals=[]
      for d in DATES[:-1]:
       q=metrics(data[d],cfg)
       if q["n"]:vals.append(q["top3_pct"])
      avg=round(sum(vals)/len(vals),2) if vals else None
      spread=round(max(vals)-min(vals),2) if vals else None
      grid.append({"time_pct":int(tw*100),"st_pct":int(sw*100),"entry_blend":eb,"exhibition_f":xf,"racer_f_penalty":rf,"target":t,"prior5_avg_top3_pct":avg,"prior5_spread_pt":spread})
 grid.sort(key=lambda x:(-x["target"]["oo"],x["target"]["ox"],-x["target"]["top3"],-x["target"]["top1"],-(x["prior5_avg_top3_pct"] or 0),x["prior5_spread_pt"] or 999))
 # consolidate exact metric duplicates and keep meaningful Pareto-like representatives
 seen=set();cand=[]
 for x in grid:
  sig=(x["target"]["oo"],x["target"]["ox"],x["target"]["xo"],x["target"]["top3"],x["target"]["top1"],x["target"]["current_rescued"],x["target"]["current_broken"],x["prior5_avg_top3_pct"])
  if sig in seen:continue
  seen.add(sig);cand.append(x)
  if len(cand)>=40:break
 current=metrics(data[TARGET],current_cfg,current_orders)
 out={"definition":{"top3":"unordered exact top3 set","exact":"ordered 1-2-3","current":"structural80 + exhibition_time6 + exhibition_st14; exhibition F neutral; racer F no separate penalty"},"current_20261005":current,"tested_patterns":len(grid),"candidates":cand}
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/"summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
 with (OUT/"candidates.csv").open("w",encoding="utf-8",newline="") as h:
  cols=["time_pct","st_pct","entry_blend","exhibition_f","racer_f_penalty","target_oo","target_ox","target_xo","target_top3_pct","target_top1_pct","rescued","broken","net_vs_current","prior5_avg_top3_pct","prior5_spread_pt"]
  w=csv.DictWriter(h,fieldnames=cols);w.writeheader()
  for x in cand:
   t=x["target"];w.writerow({"time_pct":x["time_pct"],"st_pct":x["st_pct"],"entry_blend":x["entry_blend"],"exhibition_f":x["exhibition_f"],"racer_f_penalty":x["racer_f_penalty"],"target_oo":t["oo"],"target_ox":t["ox"],"target_xo":t["xo"],"target_top3_pct":t["top3_pct"],"target_top1_pct":t["top1_pct"],"rescued":t["current_rescued"],"broken":t["current_broken"],"net_vs_current":t["net_vs_current"],"prior5_avg_top3_pct":x["prior5_avg_top3_pct"],"prior5_spread_pt":x["prior5_spread_pt"]})
 print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
