from __future__ import annotations
import csv, io, itertools, json
from collections import defaultdict
from pathlib import Path
from urllib.request import Request, urlopen

DATES=["20260930","20261001","20261002","20261003","20261004","20261005"]
OUT=Path("evaluations/ai_score_freeform_v2")
ODDS_BASE="https://raw.githubusercontent.com/BoatraceCSV/boatracecsv.github.io/main/data/previews/od3"

FEATURES=["cw","c2","c3","grade","nat2","motor_win","motor_top3","boat2","boat3","etime","est"]
REVERSE={"etime","est"}
PROFILES={
 "first_course":{"cw":.42,"c2":.08,"grade":.14,"nat2":.10,"motor_win":.06,"motor_top3":.08,"etime":.06,"est":.06},
 "first_balanced":{"cw":.32,"c2":.10,"grade":.14,"nat2":.12,"motor_win":.07,"motor_top3":.09,"etime":.08,"est":.08},
 "first_live":{"cw":.28,"c2":.08,"grade":.12,"nat2":.10,"motor_top3":.10,"etime":.16,"est":.16},
 "second_place":{"c2":.30,"c3":.18,"cw":.10,"grade":.10,"nat2":.10,"motor_top3":.10,"boat3":.04,"etime":.04,"est":.04},
 "second_balanced":{"c2":.24,"c3":.22,"cw":.08,"grade":.10,"nat2":.10,"motor_top3":.12,"boat3":.05,"etime":.05,"est":.04},
 "second_machine":{"c2":.22,"c3":.20,"grade":.09,"nat2":.09,"motor_win":.08,"motor_top3":.16,"boat3":.06,"etime":.05,"est":.05},
 "third_survival":{"c3":.34,"c2":.18,"grade":.08,"nat2":.08,"motor_top3":.14,"boat3":.08,"etime":.05,"est":.05},
 "third_balanced":{"c3":.28,"c2":.20,"cw":.05,"grade":.09,"nat2":.09,"motor_top3":.13,"boat3":.07,"etime":.05,"est":.04},
 "third_machine":{"c3":.25,"c2":.17,"grade":.08,"nat2":.08,"motor_win":.08,"motor_top3":.17,"boat3":.08,"etime":.05,"est":.04},
}
CAND={"first":[k for k in PROFILES if k.startswith("first_")],
      "second":[k for k in PROFILES if k.startswith("second_")],
      "third":[k for k in PROFILES if k.startswith("third_")]}

def F(x):
 try:return float(str(x).replace(",","").strip())
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
   z["boat"]=I(r["boat"]); z["finish"]=I(r["finish"]); rr[r["race_id"]].append(z)
 return rr

def rank(bs,k):
 good=[b for b in bs if b.get(k) is not None]
 if len(good)<2:return {b["boat"]:.5 for b in bs}
 rev=k in REVERSE
 o=sorted(good,key=lambda b:((b[k] if rev else -b[k]),b["boat"]))
 m={b["boat"]:1-i/max(1,len(o)-1) for i,b in enumerate(o)}
 for b in bs:m.setdefault(b["boat"],.5)
 return m

def score_profile(bs,name):
 R={k:rank(bs,k) for k in FEATURES}; w=PROFILES[name]; out={}
 for b in bs:
  q=b["boat"]; s=sum(wt*R[k][q] for k,wt in w.items())
  flag=str(b.get("exhibition_st_flag") or "").upper()
  if flag.startswith("F"): s*=.94
  out[q]=max(.001,s)
 return out

def position_accuracy(data, dates, pos, profile):
 hit=n=0
 idx={"first":0,"second":1,"third":2}[pos]
 for d in dates:
  for bs in data[d].values():
   if len(bs)!=6:continue
   actual=[b["boat"] for b in sorted(bs,key=lambda x:(x["finish"],x["boat"]))]
   sc=score_profile(bs,profile); pred=max(sc,key=lambda q:(sc[q],-q))
   hit+=pred==actual[idx]; n+=1
 return hit/n if n else 0

def choose(data,train_dates,pos):
 return max(CAND[pos],key=lambda p:(position_accuracy(data,train_dates,pos,p),-CAND[pos].index(p)))

def normalize(m):
 s=sum(m.values()) or 1
 return {k:v/s for k,v in m.items()}

def combos(bs,p1,p2,p3):
 a=normalize(score_profile(bs,p1)); b=normalize(score_profile(bs,p2)); c=normalize(score_profile(bs,p3)); out=[]
 for x,y,z in itertools.permutations(sorted(a),3):
  # Sequential pseudo-probability: independent position evidence, then normalize across 120 orders.
  s=a[x]*b[y]*c[z]
  out.append({"combination":f"{x}-{y}-{z}","raw_score":s})
 total=sum(x["raw_score"] for x in out) or 1
 for x in out:x["probability"]=x["raw_score"]/total
 out.sort(key=lambda x:(-x["probability"],x["combination"]))
 return out

def fetch_odds(d):
 try:
  y,m,day=d[:4],d[4:6],d[6:8]; url=f"{ODDS_BASE}/{y}/{m}/{day}.csv"
  req=Request(url,headers={"User-Agent":"boatrace-ai-freeform-v2/1.0"})
  txt=urlopen(req,timeout=30).read().decode("utf-8-sig")
  rows=list(csv.DictReader(io.StringIO(txt))); out={}
  for r in rows:
   digits="".join(ch for ch in str(r.get("race_code") or r.get("レースコード") or "") if ch.isdigit())
   if len(digits)>=12: rid=digits[:8]+"_"+digits[8:10]+"_"+str(int(digits[10:12])).zfill(2)
   else: continue
   vals={}
   for k,v in r.items():
    if k and "3連単_" in k:
     vals[k.replace("3連単_","").replace("→","-")]=F(v)
   out[rid]=vals
  return out
 except Exception as e:
  print("WARN odds",d,e); return {}

def load_payouts(d):
 p=Path(f"archive/{d[:4]}/{d[4:6]}/{d[6:8]}/results_{d}_all.csv"); out={}
 if not p.exists():return out
 with p.open(encoding="utf-8-sig",newline="") as h:
  for r in csv.DictReader(h):
   rid=r.get("race_id") or r.get("レースID")
   tri=r.get("trifecta") or r.get("3連単") or r.get("result_3t")
   pay=F(r.get("trifecta_payout") or r.get("3連単払戻") or r.get("payout_3t"))
   if rid and tri:out[rid]=(str(tri).replace("→","-"),pay)
 return out

def select8(top12,odds):
 core=top12[:6]; used={x["combination"] for x in core}; value=[]
 for x in top12[6:]:
  o=odds.get(x["combination"])
  # Cap odds contribution so one extreme longshot cannot dominate selection.
  ev=x["probability"]*min(o,80.0) if o else 0
  value.append((ev,x))
 value.sort(key=lambda t:(-t[0],-t[1]["probability"],t[1]["combination"]))
 picks=core+[x for _,x in value[:2]]
 if len(picks)<8:picks += [x for x in top12 if x["combination"] not in {p["combination"] for p in picks}][:8-len(picks)]
 return picks[:8]

def main():
 data={d:load(d) for d in DATES}; rows=[]; daily={}; all_returns=[]
 for i,d in enumerate(DATES):
  if i==0: continue # no earlier day exists: strict walk-forward starts on day 2
  train=DATES[:i]; p1=choose(data,train,"first"); p2=choose(data,train,"second"); p3=choose(data,train,"third")
  odds=fetch_odds(d); payouts=load_payouts(d); z={"races":0,"top1":0,"second":0,"third":0,"top3":0,"exact":0,"bettable":0,"hits":0,"investment":0,"return":0,"profiles":{"first":p1,"second":p2,"third":p3}}
  for rid,bs in data[d].items():
   if len(bs)!=6:continue
   actual=[b["boat"] for b in sorted(bs,key=lambda x:(x["finish"],x["boat"]))]
   cs=combos(bs,p1,p2,p3); pred=[int(x) for x in cs[0]["combination"].split("-")]
   z["races"]+=1; z["top1"]+=pred[0]==actual[0]; z["second"]+=pred[1]==actual[1]; z["third"]+=pred[2]==actual[2]; z["top3"]+=set(pred)==set(actual[:3]); z["exact"]+=pred==actual[:3]
   od=odds.get(rid,{})
   if rid not in payouts or not od:continue
   actual_tri,pay=payouts[rid]; picks=select8(cs[:12],od); hit=actual_tri in {x["combination"] for x in picks}; ret=pay if hit and pay else 0
   z["bettable"]+=1;z["hits"]+=hit;z["investment"]+=800;z["return"]+=ret;all_returns.append(ret)
   rows.append({"date":d,"race_id":rid,"profiles":f"{p1}/{p2}/{p3}","actual":actual_tri,"hit":int(hit),"return":ret,"picks":" / ".join(x["combination"] for x in picks)})
  for k in ("top1","second","third","top3","exact"):z[k+"_pct"]=round(100*z[k]/z["races"],2) if z["races"] else None
  z["hit_pct"]=round(100*z["hits"]/z["bettable"],2) if z["bettable"] else None;z["roi_pct"]=round(100*z["return"]/z["investment"],2) if z["investment"] else None;daily[d]=z
 agg={k:sum(x[k] for x in daily.values()) for k in ["races","top1","second","third","top3","exact","bettable","hits","investment","return"]}
 for k in ("top1","second","third","top3","exact"):agg[k+"_pct"]=round(100*agg[k]/agg["races"],2) if agg["races"] else None
 agg["hit_pct"]=round(100*agg["hits"]/agg["bettable"],2) if agg["bettable"] else None;agg["roi_pct"]=round(100*agg["return"]/agg["investment"],2) if agg["investment"] else None
 maxret=max(all_returns) if all_returns else 0; agg["max_single_return"]=maxret
 agg["roi_excluding_max_return_pct"]=round(100*(agg["return"]-maxret)/agg["investment"],2) if agg["investment"] else None
 result={"model":"ai_score_freeform_v2_walk_forward_position_models","production_changed":False,"leakage_policy":"profiles for each test day are selected only from earlier dates; odds are pre-race; results are evaluation only","ticket_policy":"top12 by position joint score; core top6 + up to 2 value picks using probability*min(odds,80)","daily":daily,"pooled":agg}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
 with (OUT/"races.csv").open("w",encoding="utf-8-sig",newline="") as h:
  w=csv.DictWriter(h,fieldnames=["date","race_id","profiles","actual","hit","return","picks"]);w.writeheader();w.writerows(rows)
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
