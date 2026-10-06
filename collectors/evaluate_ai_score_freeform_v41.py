from __future__ import annotations
import csv,itertools,json,io
from urllib.request import Request,urlopen
from collections import defaultdict
from pathlib import Path

DATES=["20260930","20261001","20261002","20261003","20261004","20261005"]
OUT=Path("evaluations/ai_score_freeform_v41")
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
def main():
 data={d:load(d) for d in DATES}; daily={}; race_rows=[]; totals={k:0 for k in ["races","bettable","normal_hits","upset_hits","combined_hits","normal_invest","normal_return","upset_invest","upset_return","combined_invest","combined_return"]}
 for d in DATES:
  odds,payouts=market(d); z={k:0 for k in totals}
  for rid,bs in data[d].items():
   if len(bs)!=6:continue
   actual=tuple(b["boat"] for b in sorted(bs,key=lambda x:(x["finish"],x["boat"])))[:3]; key="-".join(map(str,actual))
   n,u,_=tickets(bs); z["races"]+=1
   od=odds.get(rid,{})
   if rid not in payouts or not od:continue
   pay=payouts[rid] or 0; z["bettable"]+=1
   # normal 8 remains hit-rate book
   ns={x["combo"] for x in n}; nh=actual in ns
   # V4.1 upset book: candidates outside normal8, plausible by upset score, then capped market value
   used=ns; R=maps(bs); W={q:win(R,q) for q in range(1,7)};S={q:second(R,q) for q in range(1,7)};T={q:third(R,q) for q in range(1,7)}
   pool=[]
   for a,b,cmb in itertools.permutations(range(1,7),3):
    co=(a,b,cmb)
    if co in used:continue
    base=(W[a]**1.30)*(max(.001,S[b]))*(max(.001,T[cmb])**.90)
    evidence=(.34*R["etime"][a]+.24*R["est"][a]+.20*R["motor_top3"][a]+.12*R["cw"][a]+.10*R["grade"][a])*(.65+.35*(.45*R["c3"][b]+.25*R["motor_top3"][b]+.30*R["c3"][cmb]))
    o=od.get(f"{a}-{b}-{cmb}")
    if o is None:continue
    # capped odds contribution: seeks payout without allowing extreme odds to dominate
    value=base*evidence*(min(max(o,1.0),80.0)**.35)
    pool.append((value,base*evidence,o,co))
   pool.sort(key=lambda x:(-x[0],-x[1],x[3])); up={x[3] for x in pool[:4]}; uh=actual in up
   z["normal_hits"]+=nh;z["upset_hits"]+=uh;z["combined_hits"]+=(nh or uh)
   z["normal_invest"]+=800;z["normal_return"]+=pay if nh else 0
   z["upset_invest"]+=400;z["upset_return"]+=pay if uh else 0
   z["combined_invest"]+=1200;z["combined_return"]+=pay if (nh or uh) else 0
   race_rows.append({"date":d,"race_id":rid,"actual":key,"payout":pay,"normal_hit":int(nh),"upset_hit":int(uh),"normal8":" / ".join("-".join(map(str,x["combo"])) for x in n),"upset4":" / ".join("-".join(map(str,x[3])) for x in pool[:4])})
  for k in totals:totals[k]+=z[k]
  for book in ["normal","upset","combined"]:
   z[book+"_hit_pct"]=round(100*z[book+"_hits"]/z["bettable"],2) if z["bettable"] else None
   z[book+"_roi_pct"]=round(100*z[book+"_return"]/z[book+"_invest"],2) if z[book+"_invest"] else None
  daily[d]=z
 for book in ["normal","upset","combined"]:
  totals[book+"_hit_pct"]=round(100*totals[book+"_hits"]/totals["bettable"],2) if totals["bettable"] else None
  totals[book+"_roi_pct"]=round(100*totals[book+"_return"]/totals[book+"_invest"],2) if totals[book+"_invest"] else None
 # robustness: remove largest winning payout separately from each book
 for book in ["normal","upset","combined"]:
  wins=[r["payout"] for r in race_rows if r[book+"_hit"] if book!="combined"] if book!="combined" else [r["payout"] for r in race_rows if r["normal_hit"] or r["upset_hit"]]
  mx=max(wins) if wins else 0; totals[book+"_max_single_return"]=mx
  totals[book+"_roi_excluding_max_pct"]=round(100*(totals[book+"_return"]-mx)/totals[book+"_invest"],2) if totals[book+"_invest"] else None
 result={"model":"ai_score_freeform_v41_odds_value_upset","production_changed":False,"policy":"normal8 hit-rate book unchanged; upset4 uses independent upset evidence multiplied by capped pre-race odds value; payouts evaluation only","odds_cap":80,"odds_exponent":.35,"daily":daily,"pooled":totals}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
 with (OUT/"races.csv").open("w",encoding="utf-8-sig",newline="") as h:
  w=csv.DictWriter(h,fieldnames=race_rows[0].keys() if race_rows else ["date"]);w.writeheader();w.writerows(race_rows)
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
