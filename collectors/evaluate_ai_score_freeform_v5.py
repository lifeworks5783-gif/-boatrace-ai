from __future__ import annotations
import csv,itertools,json,math
from collections import defaultdict
from pathlib import Path
DATES=["20260930","20261001","20261002","20261003","20261004","20261005"]
OUT=Path("evaluations/ai_score_freeform_v5")
REV={"etime","est"}; FEATURES=["cw","c2","c3","grade","nat2","motor_win","motor_top3","boat2","boat3","etime","est"]
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
   z={k:F(r.get(k)) for k in FEATURES};z["boat"]=I(r.get("boat"));z["finish"]=I(r.get("finish"));rr[r["race_id"]].append(z)
 return rr
def rank(bs,k):
 good=[b for b in bs if b.get(k) is not None]
 if len(good)<2:return {b["boat"]:.5 for b in bs}
 o=sorted(good,key=lambda b:((b[k] if k in REV else -b[k]),b["boat"]));m={b["boat"]:1-i/max(1,len(o)-1) for i,b in enumerate(o)}
 for b in bs:m.setdefault(b["boat"],.5)
 return m
def maps(bs):return {k:rank(bs,k) for k in FEATURES}
def winner(R,q):return (R["cw"][q]**1.7)*(.70+.30*R["grade"][q])*(.75+.25*R["nat2"][q])*(.85+.15*(.4*R["motor_win"][q]+.6*R["motor_top3"][q]))*(.90+.10*R["etime"][q])*(.92+.08*R["est"][q])
def s2(R,q):return .26*R["c2"][q]+.20*R["c3"][q]+.08*R["cw"][q]+.09*R["grade"][q]+.07*R["nat2"][q]+.13*R["motor_top3"][q]+.05*R["boat3"][q]+.06*R["etime"][q]+.06*R["est"][q]
def s3(R,q):return .30*R["c3"][q]+.16*R["c2"][q]+.07*R["grade"][q]+.06*R["nat2"][q]+.15*R["motor_top3"][q]+.08*R["boat3"][q]+.09*R["etime"][q]+.09*R["est"][q]
def race_type(R,W):
 order=sorted(range(1,7),key=lambda q:-W[q]);a,b=order[:2];gap=(W[a]-W[b])/max(W[a],1e-9)
 if a==1 and gap>=.18:return "inner_anchor"
 if a==1:return "inner_contested"
 if a in (2,3,4) and gap>=.12:return "center_attack"
 return "chaos"
def interaction(R,a,b,c,typ):
 # conditional-order compatibility: following positions depend on the projected winner and race shape
 pair=1.0
 if typ=="inner_anchor":
  pair*=1+.12*R["c2"][b]+.08*R["c3"][c]+.05*R["motor_top3"][b]
  if a==1:pair*=1.08
 elif typ=="inner_contested":
  pair*=1+.10*R["etime"][b]+.08*R["est"][b]+.10*R["c3"][c]
  if a in (1,2,3):pair*=1.04
 elif typ=="center_attack":
  pair*=1+.12*R["c2"][b]+.10*R["motor_top3"][b]+.12*R["c3"][c]+.06*R["boat3"][c]
  if a in (2,3,4):pair*=1.06
 else:
  pair*=1+.12*R["etime"][a]+.10*R["est"][a]+.12*R["motor_top3"][b]+.14*R["c3"][c]+.08*R["boat3"][c]
 # relational geometry, mild only: avoid hard-coded result fitting
 if abs(a-b)==1:pair*=1.025
 if b<c:pair*=1.015
 return pair
def score(bs):
 R=maps(bs);W={q:winner(R,q) for q in range(1,7)};S={q:s2(R,q) for q in range(1,7)};T={q:s3(R,q) for q in range(1,7)};typ=race_type(R,W);rows=[]
 for a,b,c in itertools.permutations(range(1,7),3):
  base=(W[a]**1.30)*max(.001,S[b])*(max(.001,T[c])**.90)
  rows.append((base*interaction(R,a,b,c,typ),(a,b,c)))
 rows.sort(key=lambda x:(-x[0],x[1]));return typ,rows
def main():
 data={d:load(d) for d in DATES};cuts=[1,4,6,8,10,12,16,20];daily={};tot={k:0 for k in cuts};types=defaultdict(lambda:{"n":0,**{f"top{k}":0 for k in cuts}});ranks=[]
 for d in DATES:
  z={k:0 for k in cuts};n=0;dr=[]
  for bs in data[d].values():
   if len(bs)!=6:continue
   actual=tuple(b["boat"] for b in sorted(bs,key=lambda x:(x["finish"],x["boat"])))[:3];typ,rows=score(bs);rank=next(i+1 for i,x in enumerate(rows) if x[1]==actual);n+=1;dr.append(rank);ranks.append(rank);types[typ]["n"]+=1
   for k in cuts:
    ok=rank<=k;z[k]+=ok;tot[k]+=ok;types[typ][f"top{k}"]+=ok
  daily[d]={"n":n,"mean_rank":round(sum(dr)/n,2),"median_rank":sorted(dr)[n//2],"coverage_pct":{str(k):round(100*z[k]/n,2) for k in cuts}}
 ty={}
 for name,q in types.items():
  ty[name]={"n":q["n"],"coverage_pct":{str(k):round(100*q[f"top{k}"]/q["n"],2) for k in cuts}}
 result={"model":"ai_score_freeform_v5_race_type_direct120","production_changed":False,"leakage_policy":"race type and 120-order scores use prediction-time features only; results used only for evaluation","race_types":["inner_anchor","inner_contested","center_attack","chaos"],"pooled_n":len(ranks),"mean_actual_rank":round(sum(ranks)/len(ranks),2),"median_actual_rank":sorted(ranks)[len(ranks)//2],"coverage_pct":{str(k):round(100*tot[k]/len(ranks),2) for k in cuts},"by_race_type":ty,"daily":daily}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
