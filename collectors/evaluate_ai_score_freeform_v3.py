from __future__ import annotations
import csv,itertools,json
from collections import defaultdict
from pathlib import Path

DATES=["20260930","20261001","20261002","20261003","20261004","20261005"]
OUT=Path("evaluations/ai_score_freeform_v3")
REV={"etime","est"}
FEATURES=["cw","c2","c3","grade","nat2","motor_win","motor_top3","boat2","boat3","etime","est"]
SECOND={
 "S1":{"c2":.30,"c3":.18,"cw":.08,"grade":.10,"nat2":.08,"motor_top3":.12,"boat3":.04,"etime":.05,"est":.05},
 "S2":{"c2":.24,"c3":.24,"cw":.06,"grade":.10,"nat2":.08,"motor_top3":.14,"boat3":.05,"etime":.05,"est":.04},
 "S3":{"c2":.22,"c3":.20,"cw":.06,"grade":.08,"nat2":.08,"motor_win":.08,"motor_top3":.16,"boat3":.05,"etime":.04,"est":.03},
 "S4":{"c2":.25,"c3":.18,"cw":.05,"grade":.08,"nat2":.07,"motor_top3":.12,"boat3":.05,"etime":.10,"est":.10},
}
THIRD={
 "T1":{"c3":.34,"c2":.16,"grade":.08,"nat2":.07,"motor_top3":.15,"boat3":.08,"etime":.06,"est":.06},
 "T2":{"c3":.28,"c2":.20,"cw":.04,"grade":.08,"nat2":.08,"motor_top3":.15,"boat3":.08,"etime":.05,"est":.04},
 "T3":{"c3":.25,"c2":.17,"grade":.07,"nat2":.07,"motor_win":.08,"motor_top3":.18,"boat3":.09,"etime":.05,"est":.04},
 "T4":{"c3":.28,"c2":.16,"grade":.07,"nat2":.06,"motor_top3":.13,"boat3":.07,"etime":.12,"est":.11},
}

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
   z={k:(r[k] if k=="exhibition_st_flag" else F(r[k])) for k in r if k!="race_id"}
   z["boat"]=I(r["boat"]);z["finish"]=I(r["finish"]);rr[r["race_id"]].append(z)
 return rr
def rank(bs,k):
 good=[b for b in bs if b.get(k) is not None]
 if len(good)<2:return {b["boat"]:.5 for b in bs}
 o=sorted(good,key=lambda b:((b[k] if k in REV else -b[k]),b["boat"]))
 m={b["boat"]:1-i/max(1,len(o)-1) for i,b in enumerate(o)}
 for b in bs:m.setdefault(b["boat"],.5)
 return m
def maps(bs):return {k:rank(bs,k) for k in FEATURES}
def winner(R,q):
 return (R["cw"][q]**1.7)*(.70+.30*R["grade"][q])*(.75+.25*R["nat2"][q])*(.85+.15*(.4*R["motor_win"][q]+.6*R["motor_top3"][q]))*(.90+.10*R["etime"][q])*(.92+.08*R["est"][q])
def linear(R,q,w):
 s=sum(v*R[k][q] for k,v in w.items())
 return max(.001,s)
def order_scores(bs,sname,tname):
 R=maps(bs); W={q:winner(R,q) for q in range(1,7)}
 S={q:linear(R,q,SECOND[sname]) for q in range(1,7)}
 T={q:linear(R,q,THIRD[tname]) for q in range(1,7)}
 out=[]
 for a,b,c in itertools.permutations(range(1,7),3):
  # Conditional order score: strong V1 winner anchor, then place/survival evidence.
  # Small coherence factors reward plausible 2nd/3rd survivors without replacing the winner anchor.
  raw=(W[a]**1.35)*(S[b]**1.00)*(T[c]**.90)
  raw*=1+.08*R["c3"][b]+.05*R["motor_top3"][b]
  raw*=1+.10*R["c3"][c]+.05*R["boat3"][c]
  out.append((raw,(a,b,c)))
 out.sort(key=lambda x:(-x[0],x[1]))
 return out
def eval_pair(data,dates,s,t):
 z={"n":0,"top1":0,"top3":0,"exact":0,"top8":0,"top12":0,"top8_when_first_right":0,"first_right_n":0}
 for d in dates:
  for bs in data[d].values():
   if len(bs)!=6:continue
   actual=tuple(b["boat"] for b in sorted(bs,key=lambda x:(x["finish"],x["boat"])))[:3]
   os=order_scores(bs,s,t);pred=os[0][1]; top8={x[1] for x in os[:8]};top12={x[1] for x in os[:12]}
   z["n"]+=1;z["top1"]+=pred[0]==actual[0];z["top3"]+=set(pred)==set(actual);z["exact"]+=pred==actual
   z["top8"]+=actual in top8;z["top12"]+=actual in top12
   if pred[0]==actual[0]:z["first_right_n"]+=1;z["top8_when_first_right"]+=actual in top8
 return z
def metric(z):
 # Optimize ticket usefulness, not in-sample exact ranking alone.
 return (z["top8_when_first_right"]/max(1,z["first_right_n"]))*1.8+(z["top12"]/max(1,z["n"]))*.8+(z["exact"]/max(1,z["n"]))*.3
def pct(z,k,den="n"):return round(100*z[k]/z[den],2) if z[den] else None
def main():
 data={d:load(d) for d in DATES};daily={};pooled={k:0 for k in ["n","top1","top3","exact","top8","top12","top8_when_first_right","first_right_n"]}
 for i,d in enumerate(DATES):
  if i==0:continue
  train=DATES[:i]; candidates=[]
  for s in SECOND:
   for t in THIRD:
    z=eval_pair(data,train,s,t);candidates.append((metric(z),s,t,z))
  candidates.sort(reverse=True);_,s,t,tr=candidates[0]
  te=eval_pair(data,[d],s,t)
  daily[d]={"second_model":s,"third_model":t,"train_score":round(metric(tr),4),**te,
   "top1_pct":pct(te,"top1"),"top3_pct":pct(te,"top3"),"exact_pct":pct(te,"exact"),
   "top8_hit_pct":pct(te,"top8"),"top12_coverage_pct":pct(te,"top12"),
   "top8_hit_when_first_right_pct":pct(te,"top8_when_first_right","first_right_n")}
  for k in pooled:pooled[k]+=te[k]
 for k in ["top1","top3","exact","top8","top12"]:pooled[k+"_pct"]=pct(pooled,k)
 pooled["top8_hit_when_first_right_pct"]=pct(pooled,"top8_when_first_right","first_right_n")
 result={"model":"ai_score_freeform_v3_conditional_order","production_changed":False,
  "design":"V1 winner anchor is preserved. 2nd/3rd are conditional order models. Model pair is selected only on earlier dates.",
  "selection_objective":"prioritize actual trifecta inclusion in top8 when the first-place prediction is correct, then top12 coverage, then exact top1 order",
  "daily":daily,"pooled":pooled}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
