from __future__ import annotations
import csv,json,itertools
from collections import defaultdict
from pathlib import Path
DATES=["20260930","20261001","20261002","20261003","20261004","20261005"];OUT=Path("evaluations/ai_score_buff_debuff_v1")
def F(x):
 try:return float(x)
 except:return None
def I(x):
 try:return int(float(x))
 except:return None
def load(d):
 p=Path(f"evaluations/pdca_datasets/{d}/comparison_dataset_{d}.csv");rr=defaultdict(list)
 if not p.exists():return rr
 with p.open(encoding="utf-8-sig",newline="") as h:
  for r in csv.DictReader(h):
   z={k:(r[k] if k=="exhibition_st_flag" else F(r[k])) for k in r if k!="race_id"};z["boat"]=I(r["boat"]);z["finish"]=I(r["finish"]);rr[r["race_id"]].append(z)
 return rr
def rank(bs,k,rev=False):
 good=[b for b in bs if b.get(k) is not None]
 if len(good)<2:return {b["boat"]:.5 for b in bs}
 o=sorted(good,key=lambda b:((b[k] if rev else -b[k]),b["boat"]));m={b["boat"]:1-i/max(1,len(o)-1) for i,b in enumerate(o)}
 for b in bs:m.setdefault(b["boat"],.5)
 return m
def score(bs,cfg):
 R={k:rank(bs,k,rev) for k,rev in [("cw",0),("c2",0),("c3",0),("cst",1),("grade",0),("nat2",0),("motor_win",0),("motor_top3",0),("boat3",0),("etime",1),("est",1)]}
 win={};place={}
 for b in bs:
  q=b["boat"];core=(R["cw"][q]**1.7)*(0.70+.30*R["grade"][q])*(.75+.25*R["nat2"][q]);machine=.85+.15*(.4*R["motor_win"][q]+.6*R["motor_top3"][q]);live=(.90+.10*R["etime"][q])*(.92+.08*R["est"][q]);s=core*machine*live
  # conditional buffs/debuffs; only alter confidence, never overwrite the base model.
  if R["cw"][q]>=.8 and R["grade"][q]>=.6:s*=1+cfg["anchor_buff"]
  if R["cw"][q]>=.6 and R["etime"][q]>=.8:s*=1+cfg["time_buff"]
  if R["cw"][q]>=.6 and R["est"][q]>=.8:s*=1+cfg["st_buff"]
  if R["motor_top3"][q]>=.8 and R["cw"][q]>=.6:s*=1+cfg["motor_buff"]
  if str(b.get("exhibition_st_flag") or "").upper().startswith("F"):s*=1-cfg["f_debuff"]
  if R["cw"][q]<=.2 and R["grade"][q]<=.4:s*=1-cfg["weak_debuff"]
  win[q]=s
  place[q]=.44*R["c3"][q]+.18*R["c2"][q]+.12*R["grade"][q]+.08*R["nat2"][q]+.10*R["motor_top3"][q]+.04*R["boat3"][q]+.03*R["etime"][q]+.01*R["est"][q]
 winner=max(win,key=lambda q:(win[q],-q));rest=sorted([q for q in win if q!=winner],key=lambda q:(-(.78*place[q]+.22*win[q]),q))
 return [winner]+rest[:2]
def evalcfg(data,cfg):
 z={"n":0,"top1":0,"top3":0,"exact":0}
 for d in DATES:
  for rid,bs in data[d].items():
   if len(bs)!=6:continue
   p=score(bs,cfg);a=[b["boat"] for b in sorted(bs,key=lambda x:(x["finish"],x["boat"]))]
   z["n"]+=1;z["top1"]+=p[0]==a[0];z["top3"]+=set(p)==set(a[:3]);z["exact"]+=p==a[:3]
 for k in ("top1","top3","exact"):z[k+"_pct"]=round(100*z[k]/z["n"],2)
 return z
def main():
 data={d:load(d) for d in DATES};out=[]
 vals=[0,.02,.04,.06,.08]
 # compact, interpretable grid: anchor and live buffs plus risk debuffs
 for a,t,s,m,f,w in itertools.product(vals,[0,.02,.04],[0,.02,.04],[0,.02,.04],[0,.04,.08],[0,.03,.06]):
  cfg={"anchor_buff":a,"time_buff":t,"st_buff":s,"motor_buff":m,"f_debuff":f,"weak_debuff":w};out.append({**cfg,**evalcfg(data,cfg)})
 out.sort(key=lambda x:(-x["top1_pct"],-x["top3_pct"],-x["exact_pct"]))
 result={"production_changed":False,"tested":len(out),"best_top1":out[:20],"best_balanced":sorted(out,key=lambda x:(-(x["top1_pct"]+.8*x["top3_pct"]+.4*x["exact_pct"])))[:20]}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps({"tested":len(out),"best_top1":out[0],"best_balanced":result["best_balanced"][0]},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
