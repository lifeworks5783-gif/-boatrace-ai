from __future__ import annotations
import csv,json,math,itertools
from collections import defaultdict
from pathlib import Path
DATES=["20261003","20261004","20261005"];OUT=Path("evaluations/signal_prediction_method_v1")
def F(x):
 try:return float(x)
 except:return None
def I(x):
 try:return int(float(x))
 except:return None
def normid(x):return "".join(c for c in str(x) if c.isdigit())
def load_pdca(d):
 p=Path(f"evaluations/pdca_datasets/{d}/comparison_dataset_{d}.csv");rr=defaultdict(list)
 with p.open(encoding="utf-8-sig",newline="") as h:
  for r in csv.DictReader(h):
   z={k:F(v) for k,v in r.items() if k!="race_id"};z["boat"]=I(r["boat"]);z["finish"]=I(r["finish"]);rr[normid(r["race_id"])].append(z)
 return rr
def rank(bs,k,lower=False):
 good=[b for b in bs if b.get(k) is not None]
 if len(good)<2:return {b["boat"]:.5 for b in bs}
 o=sorted(good,key=lambda b:((b[k] if lower else -b[k]),b["boat"]));m={b["boat"]:1-i/max(1,len(o)-1) for i,b in enumerate(o)}\n for b in bs:m.setdefault(b["boat"],.5)\n return m
def signal(bs):
 R={k:rank(bs,k,lo) for k,lo in [("cw",0),("c3",0),("grade",0),("nat2",0),("motor_top3",0),("etime",1),("est",1)]}
 # live evidence momentum proxy, deliberately not added to boat score.
 raw={b["boat"]:(.55*R["etime"][b["boat"]]+.45*R["est"][b["boat"]]) for b in bs}
 avg=sum(raw.values())/6
 return {q:raw[q]-avg for q in raw},R
def results(d):
 p=Path(f"archive/{d[:4]}/{d[4:6]}/{d[6:8]}/results_{d}_all.csv");o={}
 with p.open(encoding="utf-8-sig",newline="") as h:
  for r in csv.DictReader(h):o[normid(f'{d}{int(r["venue_code"]):02d}{int(r["race"]):02d}')]=(tuple(map(int,r["trifecta"].split("-"))),I(r["trifecta_pay"]))
 return o
def forms(d):
 p=Path(f"predictions/{d[:4]}/{d[4:6]}/{d[6:8]}/live/formation_predictions_final_{d}.csv");o={}
 with p.open(encoding="utf-8-sig",newline="") as h:
  for r in csv.DictReader(h):o[normid(r["race_id"])]=r
 return o
def parse_combos(s):
 out=[]
 for x in str(s or "").split("/"):
  try:out.append(tuple(map(int,x.strip().split("-"))))
  except:pass
 return out
def scoremap(r):
 return {I(r[f"rank{i}_boat"]):F(r[f"rank{i}_score"]) for i in range(1,7)}
def ordermap(r):
 return [I(r[f"rank{i}_boat"]) for i in range(1,7)]
def metrics():
 return {"races":0,"hits":0,"points":0,"invest":0,"return":0,"manshu":0}
def add(m,combos,actual,pay):
 m["races"]+=1;m["points"]+=len(combos);m["invest"]+=100*len(combos)
 if actual in combos:m["hits"]+=1;m["return"]+=pay or 0;m["manshu"]+=int((pay or 0)>=10000)
def finish(m):
 m["hit_rate_pct"]=round(100*m["hits"]/m["races"],2) if m["races"] else None;m["roi_pct"]=round(100*m["return"]/m["invest"],2) if m["invest"] else None;return m
def choose_hole(order,S,R,minsig,support):
 cand=[]
 for q in order[3:]:
  sup=sum([R["c3"][q]>=.4,R["grade"][q]>=.4,R["nat2"][q]>=.4,R["etime"][q]>=.6,R["est"][q]>=.6])
  if S[q]>=minsig and sup>=support:cand.append((S[q]+.10*sup,q))
 return max(cand)[1] if cand else None
def run(cfg):
 mb,msb,mf,msf=metrics(),metrics(),metrics(),metrics()
 changed_box=changed_form=0
 for d in DATES:
  pd=load_pdca(d);rr=results(d);ff=forms(d)
  for rid,r in ff.items():
   if rid not in pd or rid not in rr or len(pd[rid])!=6:continue
   actual,pay=rr[rid];order=ordermap(r);sm=scoremap(r);S,R=signal(pd[rid]);hole=choose_hole(order,S,R,cfg["minsig"],cfg["support"])
   # BOX vs BOX: exactly 6 points both.
   base3=order[:3];sig3=list(base3)
   if hole is not None:
    sig3=[order[0],order[1],hole];changed_box+=int(set(sig3)!=set(base3))
   b0=list(itertools.permutations(base3,3));b1=list(itertools.permutations(sig3,3));add(mb,b0,actual,pay);add(msb,b1,actual,pay)
   # Formation vs formation: preserve exact point count. Signal only changes combo selection, never scores.
   base=parse_combos(r["combinations"]);n=len(base)
   add(mf,base,actual,pay)
   if hole is None:
    sigf=base
   else:
    # 120 combos ranked by unchanged production score; qualifying hole gets prediction-selection priority in 2nd/3rd only.
    allc=list(itertools.permutations(order,3))
    def key(c):
     strength=.50*sm[c[0]]+.30*sm[c[1]]+.20*sm[c[2]]
     hole_bonus=cfg["bonus"]*((1 if c[1]==hole else 0)*.30+(1 if c[2]==hole else 0)*.20)
     return -(strength+hole_bonus),c
    allc.sort(key=key);sigf=allc[:n];changed_form+=int(set(sigf)!=set(base))
   add(msf,sigf,actual,pay)
 return {"config":cfg,"box_base":finish(mb),"box_signal":finish(msb),"formation_base":finish(mf),"formation_signal":finish(msf),"changed_box_races":changed_box,"changed_formation_races":changed_form}
def main():
 variants=[]
 for minsig in [.05,.10,.15,.20,.25]:
  for support in [2,3,4]:
   for bonus in [2,4,6,8,10]:
    variants.append(run({"minsig":minsig,"support":support,"bonus":bonus}))
 def gain(x,k):return x[k]["roi_pct"]-x[k.replace("signal","base")]["roi_pct"]
 best_box=max(variants,key=lambda x:(gain(x,"box_signal"),x["box_signal"]["hit_rate_pct"]))
 best_form=max(variants,key=lambda x:(gain(x,"formation_signal"),x["formation_signal"]["hit_rate_pct"]))
 out={"production_changed":False,"dates":DATES,"method":"same production scores; only prediction selection changes. BOX remains 6 points. Formation preserves each race's original point count.","tested":len(variants),"best_box":best_box,"best_formation":best_form}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/"summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
