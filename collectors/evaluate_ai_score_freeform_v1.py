from __future__ import annotations
import csv,json
from collections import defaultdict
from pathlib import Path
DATES=["20260930","20261001","20261002","20261003","20261004","20261005"]
OUT=Path("evaluations/ai_score_freeform_v1")
def F(x):
 try:return float(x)
 except:return None
def I(x):
 try:return int(float(x))
 except:return None
def load(d):
 p=Path(f"evaluations/pdca_datasets/{d}/comparison_dataset_{d}.csv"); rr=defaultdict(list)
 if not p.exists():return rr
 with p.open(encoding="utf-8-sig",newline="") as h:
  for r in csv.DictReader(h):
   z={k:(r[k] if k=="exhibition_st_flag" else F(r[k])) for k in r if k!="race_id"}
   z["boat"]=I(r["boat"]);z["finish"]=I(r["finish"]);rr[r["race_id"]].append(z)
 return rr
def rank(bs,k,rev=False):
 good=[b for b in bs if b.get(k) is not None]
 if len(good)<2:return {b["boat"]:.5 for b in bs}
 o=sorted(good,key=lambda b:((b[k] if rev else -b[k]),b["boat"]));m={b["boat"]:1-i/max(1,len(o)-1) for i,b in enumerate(o)}
 for b in bs:m.setdefault(b["boat"],.5)
 return m
def predict(bs):
 maps={k:rank(bs,k,rev) for k,rev in [("cw",0),("c2",0),("c3",0),("cst",1),("grade",0),("nat2",0),("motor_win",0),("motor_top3",0),("boat2",0),("boat3",0),("etime",1),("lst",1)]}
 # Winner model: course win is the anchor; class/ability support it. ST is only a conditional confidence modifier.
 win={}
 place={}
 for b in bs:
  q=b["boat"]
  core=(maps["cw"][q]**1.7)*(0.70+0.30*maps["grade"][q])*(0.75+0.25*maps["nat2"][q])
  machine=(0.85+0.15*(.4*maps["motor_win"][q]+.6*maps["motor_top3"][q]))
  live=(0.90+0.10*maps["etime"][q])*(0.92+0.08*maps["lst"][q])
  win[q]=core*machine*live
  # Place model emphasizes survival/top3 rather than win rate.
  place[q]=(.42*maps["c3"][q]+.18*maps["c2"][q]+.12*maps["grade"][q]+.08*maps["nat2"][q]+.10*maps["motor_top3"][q]+.04*maps["boat3"][q]+.04*maps["etime"][q]+.02*maps["lst"][q])
 winner=max(win,key=lambda q:(win[q],-q))
 rest=sorted([q for q in win if q!=winner],key=lambda q:(-(.72*place[q]+.28*win[q]),q))
 return [winner]+rest[:2],win,place
def main():
 total={"n":0,"top1":0,"top3":0,"exact":0};by={}
 for d in DATES:
  z={"n":0,"top1":0,"top3":0,"exact":0}
  for rid,bs in load(d).items():
   if len(bs)!=6:continue
   p,_,_=predict(bs);a=[b["boat"] for b in sorted(bs,key=lambda x:(x["finish"],x["boat"]))]
   z["n"]+=1;z["top1"]+=p[0]==a[0];z["top3"]+=set(p)==set(a[:3]);z["exact"]+=p==a[:3]
  for k in ("top1","top3","exact"):z[k+"_pct"]=round(100*z[k]/z["n"],2) if z["n"] else None
  by[d]=z
  for k in total:total[k]+=z[k]
 for k in ("top1","top3","exact"):total[k+"_pct"]=round(100*total[k]/total["n"],2) if total["n"] else None
 out={"model":"freeform_v1_split_winner_place","production_changed":False,"concept":"winner and top3-survival are scored separately; no 100-point constraint","by_date":by,"pooled":total}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/"summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
