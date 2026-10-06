from __future__ import annotations
import csv,itertools,json,io
from urllib.request import Request,urlopen
from collections import defaultdict
from pathlib import Path

DATES=["20260930","20261001","20261002","20261003","20261004","20261005"]
OUT=Path("evaluations/ai_score_freeform_v43")
PUBLIC="https://raw.githubusercontent.com/BoatraceCSV/boatracecsv.github.io/main/data"
REV={"etime","est"}
FEATURES=["cw","c2","c3","grade","nat2","motor_win","motor_top3","boat2","boat3","etime","est"]

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
   z={k:F(r.get(k)) for k in FEATURES}; z["boat"]=I(r.get("boat")); z["finish"]=I(r.get("finish"))
   rr[canon(r["race_id"])].append(z)
 return rr

def canon(x):
 d="".join(ch for ch in str(x) if ch.isdigit())
 return d[:12] if len(d)>=12 else d
def fetch_csv(url):
 try:
  t=urlopen(Request(url,headers={"User-Agent":"boatrace-ai-v41/1.0"}),timeout=30).read().decode("utf-8-sig")
  return list(csv.DictReader(io.StringIO(t)))
 except Exception as e:
  print("WARN",url,e);return []
def market(d):
 y,m,dd=d[:4],d[4:6],d[6:8]; base=f"{y}/{m}/{dd}"
 odds={}; payouts={}
 for r in fetch_csv(f"{PUBLIC}/previews/od3/{base}.csv"):
  rid=canon(r.get("レースコード") or r.get("race_code"))
  if rid: odds[rid]={k.replace("3連単_","").replace("→","-"):F(v) for k,v in r.items() if k and k.startswith("3連単_")}
 for r in fetch_csv(f"{PUBLIC}/results/payouts/{base}.csv"):
  rid=canon(r.get("レースコード") or r.get("race_code"))
  if rid: payouts[rid]=F(r.get("3連単_払戻金"))
 return odds,payouts

def rank(bs,k):
 good=[b for b in bs if b.get(k) is not None]
 if len(good)<2:return {b["boat"]:.5 for b in bs}
 o=sorted(good,key=lambda b:((b[k] if k in REV else -b[k]),b["boat"]))
 m={b["boat"]:1-i/max(1,len(o)-1) for i,b in enumerate(o)}
 for b in bs:m.setdefault(b["boat"],.5)
 return m
def maps(bs):return {k:rank(bs,k) for k in FEATURES}
def win(R,q):
 return (R["cw"][q]**1.7)*(.70+.30*R["grade"][q])*(.75+.25*R["nat2"][q])*(.85+.15*(.4*R["motor_win"][q]+.6*R["motor_top3"][q]))*(.90+.10*R["etime"][q])*(.92+.08*R["est"][q])
def second(R,q):
 return .26*R["c2"][q]+.20*R["c3"][q]+.08*R["cw"][q]+.09*R["grade"][q]+.07*R["nat2"][q]+.13*R["motor_top3"][q]+.05*R["boat3"][q]+.06*R["etime"][q]+.06*R["est"][q]
def third(R,q):
 return .30*R["c3"][q]+.16*R["c2"][q]+.07*R["grade"][q]+.06*R["nat2"][q]+.15*R["motor_top3"][q]+.08*R["boat3"][q]+.09*R["etime"][q]+.09*R["est"][q]
def tickets(bs):
 R=maps(bs); W={q:win(R,q) for q in range(1,7)};S={q:second(R,q) for q in range(1,7)};T={q:third(R,q) for q in range(1,7)}
 rows=[]
 for a,b,c in itertools.permutations(range(1,7),3):
  base=(W[a]**1.30)*(max(.001,S[b])**1.00)*(max(.001,T[c])**.90)
  # Upset evidence deliberately differs from normal hit logic.
  # Reward non-obvious heads only when live/course/machine evidence jointly supports them.
  head_upset=(.34*R["etime"][a]+.24*R["est"][a]+.20*R["motor_top3"][a]+.12*R["cw"][a]+.10*R["grade"][a])
  tail_chaos=(.45*R["c3"][b]+.25*R["motor_top3"][b]+.30*R["c3"][c])
  upset=base*(.55+.45*head_upset)*(.65+.35*tail_chaos)
  rows.append({"combo":(a,b,c),"normal":base,"upset":upset})
 rows.sort(key=lambda x:(-x["normal"],x["combo"]))
 normal=rows[:8]; used={x["combo"] for x in normal}
 # Four longshot slots are selected from plausible non-core combinations.
 # True odds are intentionally not used here until pre-race odds ingestion is validated.
 pool=[x for x in rows[8:40] if x["combo"] not in used]
 pool.sort(key=lambda x:(-x["upset"],x["combo"]))
 upset=pool[:4]
 return normal,upset,rows[:12]
def candidate_pool(bs,od):
 R=maps(bs);W={q:win(R,q) for q in range(1,7)};S={q:second(R,q) for q in range(1,7)};T={q:third(R,q) for q in range(1,7)}
 rows=[]
 for a,b,c in itertools.permutations(range(1,7),3):
  base=(W[a]**1.30)*max(.001,S[b])*(max(.001,T[c])**.90)
  head=.34*R["etime"][a]+.24*R["est"][a]+.20*R["motor_top3"][a]+.12*R["cw"][a]+.10*R["grade"][a]
  chaos=.45*R["c3"][b]+.25*R["motor_top3"][b]+.30*R["c3"][c]
  evidence=base*(.55+.45*head)*(.65+.35*chaos)
  o=od.get(f"{a}-{b}-{c}")
  rows.append({"combo":(a,b,c),"base":base,"evidence":evidence,"odds":o or 0})
 return rows

STRATS={
 "pure_evidence":lambda x:x["evidence"],
 "light_value":lambda x:x["evidence"]*(min(max(x["odds"],1),50)**.10),
 "mid_value":lambda x:x["evidence"]*(min(max(x["odds"],1),50)**.20),
 "rank_then_value":None,
 "contrarian_head":lambda x:x["evidence"]*(1.12 if x["combo"][0] not in (1,2) else 1.0),
}
def select_upset(rows,normal,strat):
 pool=[x for x in rows if x["combo"] not in normal and x["odds"]>0]
 if strat=="rank_then_value":
  pool.sort(key=lambda x:(-x["evidence"],x["combo"])); pool=pool[:16]
  pool.sort(key=lambda x:(-(x["evidence"]*(min(x["odds"],60)**.15)),-x["evidence"],x["combo"]))
 else:pool.sort(key=lambda x:(-STRATS[strat](x),-x["evidence"],x["combo"]))
 return pool[:4]
def eval_strategy(records,strat):
 inv=ret=hit=0
 for rec in records:
  picks=select_upset(rec["rows"],rec["normal"],strat); ok=rec["actual"] in {x["combo"] for x in picks}
  inv+=400;hit+=ok;ret+=rec["pay"] if ok else 0
 return {"hit":hit,"invest":inv,"return":ret,"roi":ret/inv if inv else 0}
THRESHOLDS=[0.0,.80,.90,1.00,1.10,1.20,1.35,1.50]
def confidence(picks):
 if not picks:return 0
 # relative evidence of the fourth supplemental ticket vs best non-core candidate;
 # combines coverage quality and market value without result data.
 ev=[x["evidence"] for x in picks]
 odds=[min(max(x["odds"],1),60) for x in picks]
 return (sum(ev)/len(ev))*(sum(o**.10 for o in odds)/len(odds))
def simulate(records,strat,threshold):
 inv=ret=hit=bet=0
 for rec in records:
  picks=select_upset(rec["rows"],rec["normal"],strat); conf=confidence(picks)
  # normalize confidence by best evidence in that race to make threshold portable
  pool=[x for x in rec["rows"] if x["combo"] not in rec["normal"] and x["odds"]>0]
  anchor=max((x["evidence"] for x in pool),default=1e-9)
  rel=conf/max(anchor,1e-9)
  if rel<threshold:continue
  bet+=1;inv+=400;ok=rec["actual"] in {x["combo"] for x in picks};hit+=ok;ret+=rec["pay"] if ok else 0
 return {"bets":bet,"hits":hit,"invest":inv,"return":ret,"roi":ret/inv if inv else 0}
def main():
 data={d:load(d) for d in DATES}; markets={d:market(d) for d in DATES}; prepared={}; daily={}; logs={}; rows=[]
 for d in DATES:
  odds,payouts=markets[d]; recs=[]
  for rid,bs in data[d].items():
   if len(bs)!=6 or rid not in payouts or rid not in odds:continue
   actual=tuple(b["boat"] for b in sorted(bs,key=lambda x:(x["finish"],x["boat"])))[:3]; n,_,_=tickets(bs); normal={x["combo"] for x in n}
   recs.append({"rid":rid,"actual":actual,"pay":payouts[rid] or 0,"normal":normal,"rows":candidate_pool(bs,odds[rid])})
  prepared[d]=recs
 totals={k:0 for k in ["races","normal_hits","upset_bets","upset_hits","combined_hits","normal_invest","normal_return","upset_invest","upset_return","combined_invest","combined_return"]}
 for i,d in enumerate(DATES):
  hist=[r for td in DATES[:i] for r in prepared[td]]
  if not hist: strat="pure_evidence";thr=0.0; grid={}
  else:
   grid={}
   for s in STRATS:
    for t in THRESHOLDS:
     q=simulate(hist,s,t); grid[f"{s}@{t}"]=q
   # require enough historical betting opportunities; optimize ROI with hit-count reliability penalty
   def obj(item):
    q=item[1]; reliability=min(q["bets"]/120,1.0)*min(q["hits"]/10,1.0)
    return (q["roi"]*reliability,q["hits"],q["bets"])
   key=max(grid.items(),key=obj)[0];strat,ts=key.split("@");thr=float(ts)
  logs[d]={"strategy":strat,"threshold":thr,"training":grid}
  z={k:0 for k in totals}
  for rec in prepared[d]:
   a=rec["actual"];pay=rec["pay"];nh=a in rec["normal"];z["races"]+=1;z["normal_hits"]+=nh;z["normal_invest"]+=800;z["normal_return"]+=pay if nh else 0
   picks=select_upset(rec["rows"],rec["normal"],strat);pool=[x for x in rec["rows"] if x["combo"] not in rec["normal"] and x["odds"]>0];anchor=max((x["evidence"] for x in pool),default=1e-9);rel=confidence(picks)/max(anchor,1e-9)
   buy=rel>=thr;uh=buy and a in {x["combo"] for x in picks}
   if buy:z["upset_bets"]+=1;z["upset_invest"]+=400;z["upset_hits"]+=uh;z["upset_return"]+=pay if uh else 0
   z["combined_hits"]+=(nh or uh);z["combined_invest"]+=800+(400 if buy else 0);z["combined_return"]+=pay if (nh or uh) else 0
   rows.append({"date":d,"race_id":rec["rid"],"strategy":strat,"threshold":thr,"relative_conf":round(rel,4),"buy_upset":int(buy),"actual":"-".join(map(str,a)),"payout":pay,"normal_hit":int(nh),"upset_hit":int(uh)})
  for k in totals:totals[k]+=z[k]
  z["normal_hit_pct"]=round(100*z["normal_hits"]/z["races"],2);z["normal_roi_pct"]=round(100*z["normal_return"]/z["normal_invest"],2)
  z["upset_buy_rate_pct"]=round(100*z["upset_bets"]/z["races"],2);z["upset_hit_per_bet_pct"]=round(100*z["upset_hits"]/z["upset_bets"],2) if z["upset_bets"] else None;z["upset_roi_pct"]=round(100*z["upset_return"]/z["upset_invest"],2) if z["upset_invest"] else None
  z["combined_hit_pct"]=round(100*z["combined_hits"]/z["races"],2);z["combined_roi_pct"]=round(100*z["combined_return"]/z["combined_invest"],2);daily[d]=z
 totals["normal_hit_pct"]=round(100*totals["normal_hits"]/totals["races"],2);totals["normal_roi_pct"]=round(100*totals["normal_return"]/totals["normal_invest"],2)
 totals["upset_buy_rate_pct"]=round(100*totals["upset_bets"]/totals["races"],2);totals["upset_hit_per_bet_pct"]=round(100*totals["upset_hits"]/totals["upset_bets"],2) if totals["upset_bets"] else None;totals["upset_roi_pct"]=round(100*totals["upset_return"]/totals["upset_invest"],2) if totals["upset_invest"] else None
 totals["combined_hit_pct"]=round(100*totals["combined_hits"]/totals["races"],2);totals["combined_roi_pct"]=round(100*totals["combined_return"]/totals["combined_invest"],2)
 result={"model":"ai_score_freeform_v43_dynamic_upset_budget","production_changed":False,"policy":"normal8 always; upset4 purchased only when walk-forward-selected strategy/confidence threshold qualifies","thresholds":THRESHOLDS,"selection_log":logs,"daily":daily,"pooled":totals}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
 with (OUT/"races.csv").open("w",encoding="utf-8-sig",newline="") as h:
  w=csv.DictWriter(h,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
