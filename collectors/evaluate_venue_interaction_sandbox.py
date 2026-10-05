from __future__ import annotations
import csv,json
from collections import defaultdict
from pathlib import Path

DATES=["20260930","20261001","20261002","20261003","20261004","20261005"]
OUT=Path("evaluations/venue_interaction_sandbox")
def F(x):
 try:return float(x)
 except:return None
def I(x):
 try:return int(float(x))
 except:return None
def load(d):
 p=Path(f"evaluations/pdca_datasets/{d}/comparison_dataset_{d}.csv")
 if not p.exists(): return {}
 rr=defaultdict(list)
 with p.open(encoding="utf-8-sig",newline="") as h:
  for r in csv.DictReader(h):
   b={k:(r[k] if k=="exhibition_st_flag" else F(r[k])) for k in r if k!="race_id"}
   b["boat"]=I(r["boat"]); b["finish"]=I(r["finish"]); rr[r["race_id"]].append(b)
 return rr
def rank(bs,key,reverse=False,neutral=True):
 good=[b for b in bs if b.get(key) is not None]
 if len(good)<2:return None
 o=sorted(good,key=lambda b:((b[key] if reverse else -b[key]),b["boat"]))
 m={b["boat"]:1-i/max(1,len(o)-1) for i,b in enumerate(o)}
 if neutral:
  for b in bs:m.setdefault(b["boat"],.5)
 elif len(m)!=len(bs):return None
 return m
def base(bs):
 keys=[("cw",0,.16),("c2",0,.08),("c3",0,.12),("cst",1,.04),("grade",0,.20),("nat2",0,.15),("motor_win",0,.08),("motor_top3",0,.12),("boat2",0,.025),("boat3",0,.025)]
 maps={}
 for k,r,w in keys:
  maps[k]=rank(bs,k,bool(r))
  if maps[k] is None:return None
 sc={}
 for b in bs:
  q=b["boat"]; sc[q]=sum(w*maps[k][q] for k,r,w in keys)
 tm=rank(bs,"etime",True); st=rank(bs,"lst",True)
 if tm is None or st is None:return None
 return {q:.80*sc[q]+.06*tm[q]+.14*st[q] for q in sc}
def metric(data,mode,weight):
 z={"n":0,"top1":0,"top3":0,"exact":0}
 for rid,bs in data.items():
  if len(bs)!=6:continue
  sc=base(bs)
  rv=rank(bs,"venue_win"); vc=rank(bs,"venue_course_win")
  if sc is None or rv is None or vc is None:continue
  ns={}
  for b in bs:
   q=b["boat"]
   inter=rv[q]*vc[q] if mode=="product" else min(rv[q],vc[q]) if mode=="min" else max(0,rv[q]+vc[q]-1)
   ns[q]=sc[q]+weight*inter
  p=[b["boat"] for b in sorted(bs,key=lambda b:(-ns[b["boat"]],b["boat"]))]
  a=[b["boat"] for b in sorted(bs,key=lambda b:(b["finish"],b["boat"]))]
  z["n"]+=1; z["top1"]+=p[0]==a[0]; z["top3"]+=set(p[:3])==set(a[:3]); z["exact"]+=p[:3]==a[:3]
 for k in ("top1","top3","exact"):z[k+"_pct"]=round(100*z[k]/z["n"],2) if z["n"] else None
 return z
def main():
 data={d:load(d) for d in DATES}; out=[]
 for mode in ("product","min","threshold"):
  for w in (0,.005,.01,.02,.03,.05,.08):
   by={d:metric(data[d],mode,w) for d in DATES}
   n=sum(x["n"] for x in by.values()); hits=sum(round(x["top3_pct"]*x["n"]/100) for x in by.values() if x["n"] and x["top3_pct"] is not None)
   out.append({"mode":mode,"weight":w,"by_date":by,"races":n,"pooled_top3_pct":round(100*hits/n,2) if n else None})
 out.sort(key=lambda x:(-(x["pooled_top3_pct"] or 0),x["weight"]))
 OUT.mkdir(parents=True,exist_ok=True);(OUT/"summary.json").write_text(json.dumps({"note":"sandbox only; production untouched","results":out},ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(out[:10],ensure_ascii=False,indent=2))
if __name__=="__main__":main()
