from __future__ import annotations
import csv,json,itertools,math
from collections import defaultdict
from pathlib import Path

DATES=["20260930","20261001","20261002","20261003","20261004","20261005"]
OUT=Path("evaluations/ai_120_signal_roi_v1")

def F(x):
 try:return float(x)
 except:return None
def I(x):
 try:return int(float(x))
 except:return None

def load_day(d):
 p=Path(f"evaluations/pdca_datasets/{d}/comparison_dataset_{d}.csv")
 rr=defaultdict(list)
 if not p.exists(): return rr
 with p.open(encoding="utf-8-sig",newline="") as h:
  for r in csv.DictReader(h):
   z={k:F(v) for k,v in r.items() if k!="race_id"}
   z["boat"]=I(r["boat"]);z["finish"]=I(r["finish"])
   rr[r["race_id"]].append(z)
 return rr

def payouts(d):
 p=Path(f"archive/{d[:4]}/{d[4:6]}/{d[6:8]}/results_{d}_all.csv")
 out={}
 if not p.exists(): return out
 with p.open(encoding="utf-8-sig",newline="") as h:
  for r in csv.DictReader(h):
   rid=f'{d}{int(r["venue_code"]):02d}{int(r["race"]):02d}'
   out[rid]=(str(r.get("trifecta") or "").strip(),I(r.get("trifecta_pay")))
 return out

def rank(bs,k,lower=False):
 good=[b for b in bs if b.get(k) is not None]
 if len(good)<2:return {b["boat"]:.5 for b in bs}
 o=sorted(good,key=lambda b:((b[k] if lower else -b[k]),b["boat"]))
 m={b["boat"]:1-i/max(1,len(o)-1) for i,b in enumerate(o)}
 for b in bs:m.setdefault(b["boat"],.5)
 return m

def boat_scores(bs):
 R={k:rank(bs,k,lo) for k,lo in [
  ("cw",0),("c2",0),("c3",0),("grade",0),("nat2",0),("motor_win",0),
  ("motor_top3",0),("boat3",0),("etime",1),("est",1)]}
 morning={}; live={}; place={}
 for b in bs:
  q=b["boat"]
  # stable base: course is anchor, then class/ability/machine.
  base=(R["cw"][q]**1.55)*(0.72+.28*R["grade"][q])*(0.78+.22*R["nat2"][q])
  base*=.86+.14*(.4*R["motor_win"][q]+.6*R["motor_top3"][q])
  morning[q]=base
  # live evidence only; no result fields are used.
  live[q]=base*(.90+.10*R["etime"][q])*(.92+.08*R["est"][q])
  place[q]=.44*R["c3"][q]+.18*R["c2"][q]+.12*R["grade"][q]+.08*R["nat2"][q]+.10*R["motor_top3"][q]+.04*R["boat3"][q]+.03*R["etime"][q]+.01*R["est"][q]
 return morning,live,place

def combo_rank(bs,signal_weight):
 morning,live,place=boat_scores(bs)
 # Relative morning->live momentum within a race. Centering removes common scaling drift.
 raw={q:math.log(max(live[q],1e-12)/max(morning[q],1e-12)) for q in live}
 avg=sum(raw.values())/len(raw)
 mom={q:raw[q]-avg for q in raw}
 # standardize momentum to make the signal comparable across races.
 scale=max(1e-9,max(abs(x) for x in mom.values()))
 sig={q:mom[q]/scale for q in mom}
 scores=[]
 for a,b,c in itertools.permutations(sorted(live),3):
  # sequential 3-position base; first-place strength matters most.
  base=(live[a]**1.20)*(.65*place[b]+.35*live[b])*(.78*place[c]+.22*live[c])
  # hole signal is intentionally stronger in 2nd/3rd than 1st.
  boost=math.exp(signal_weight*(.25*sig[a]+.85*sig[b]+.70*sig[c]))
  scores.append(((a,b,c),base*boost))
 scores.sort(key=lambda x:(-x[1],x[0]))
 return scores,sig

def evaluate(data,pays,w):
 z={8:{"races":0,"hits":0,"invest":0,"return":0,"manshu_hits":0},10:{"races":0,"hits":0,"invest":0,"return":0,"manshu_hits":0}}
 ranks=[]
 for d in DATES:
  for rid,bs in data[d].items():
   if len(bs)!=6 or rid not in pays[d]:continue
   tri,pay=pays[d][rid]
   try: actual=tuple(map(int,tri.split("-")))
   except: continue
   ranked,_=combo_rank(bs,w)
   pos=next((i+1 for i,(x,_) in enumerate(ranked) if x==actual),None)
   if pos:ranks.append(pos)
   for n in (8,10):
    a=z[n];a["races"]+=1;a["invest"]+=100*n
    if pos and pos<=n:
     a["hits"]+=1;a["return"]+=pay or 0
     if (pay or 0)>=10000:a["manshu_hits"]+=1
 for n,a in z.items():
  a["hit_rate_pct"]=round(100*a["hits"]/a["races"],2) if a["races"] else None
  a["roi_pct"]=round(100*a["return"]/a["invest"],2) if a["invest"] else None
  a["avg_hit_pay"]=round(a["return"]/a["hits"]) if a["hits"] else None
 z["actual_rank"]={"n":len(ranks),"median":sorted(ranks)[len(ranks)//2] if ranks else None,"top8":sum(x<=8 for x in ranks),"top10":sum(x<=10 for x in ranks),"top12":sum(x<=12 for x in ranks),"top20":sum(x<=20 for x in ranks)}
 return z

def main():
 data={d:load_day(d) for d in DATES};pays={d:payouts(d) for d in DATES}
 weights=[0,.05,.10,.15,.20,.30,.40,.60]
 rows=[]
 for w in weights:
  rows.append({"signal_weight":w,**evaluate(data,pays,w)})
 best8=max(rows,key=lambda x:(x[8]["roi_pct"],x[8]["hit_rate_pct"]))
 best10=max(rows,key=lambda x:(x[10]["roi_pct"],x[10]["hit_rate_pct"]))
 out={"production_changed":False,"dates":DATES,"method":"120 trifecta ranking from stable base + morning-to-live relative momentum; signal emphasized for 2nd/3rd","note":"historical exact displayed scores are not complete for all dates, so v1 reconstructs morning/live evaluation from saved no-leakage factors","variants":rows,"best8":best8,"best10":best10}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/"summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({"best8":best8,"best10":best10},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
