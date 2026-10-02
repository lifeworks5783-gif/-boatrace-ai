#!/usr/bin/env python3
import csv,json,math,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; F=ROOT/"features"
INP=ROOT/"evaluations/2026/10/02/backfill_live/prediction_input_enriched_live_20261002.json"
RES=ROOT/"archive/2026/10/02/boat_results_20261002_all.csv"; OUT=ROOT/"evaluations/2026/10/02/racer_course_7steps"
def loadcsv(p):
 with p.open(encoding="utf-8-sig",newline="") as h:return list(csv.DictReader(h))
def num(x,d=None):
 try:return float(x)
 except:return d
def key(x):
 try:return str(int(float(x)))
 except:return str(x or "").strip()
def rate(x,d=.5):
 x=num(x)
 return d if x is None else x/100 if x>1 else x
def clip(x):return max(0,min(1,x))
def invst(x):return clip(1-num(x,.20)/.35)
def finish(x):return clip((6-num(x,3.5))/5)
def trend(x,s=.5):return clip(.5+num(x,0)/s)
def series(raw):
 a=[int(x) for x in re.findall(r"[1-6]",str(raw or ""))]
 if not a:return .5
 w=list(range(1,len(a)+1));return sum(((7-v)/6)*q for v,q in zip(a,w))/sum(w)
def idx(rows,cols):return {tuple(key(r.get(c)) for c in cols):r for r in rows}
def scoped(r):
 if not r:return .5
 return .45*rate(r.get("d90_top3_rate"))+.25*rate(r.get("d90_win_rate"))+.15*rate(r.get("d90_top2_rate"))+.15*invst(r.get("d90_avg_st"))
def overall(r):
 if not r:return .5
 return .5*rate(r.get("d90_top3_rate"))+.25*rate(r.get("d30_top3_rate"))+.15*finish(r.get("last10_avg_finish"))+.10*trend(r.get("trend_top3_rate_30v90"))
def recent(r):
 if not r:return .5
 return .35*rate(r.get("last5_top3_rate"))+.30*rate(r.get("last10_top3_rate"))+.25*rate(r.get("d30_top3_rate"))+.10*finish(r.get("last10_avg_finish"))
rc=idx(loadcsv(F/"racer_course_features.csv"),["registration_no","course"]);rv=idx(loadcsv(F/"racer_venue_features.csv"),["registration_no","venue_code"]);rr=idx(loadcsv(F/"racer_features.csv"),["registration_no"])
data=json.loads(INP.read_text(encoding="utf-8")); actual={}
for r in loadcsv(RES):
 try:actual.setdefault(r["race_id"].replace("_","-"),[]).append((int(float(r["finish"])),int(float(r["boat"]))))
 except:pass
actual={k:[b for _,b in sorted(v)][:3] for k,v in actual.items() if len(v)==6}
grades={"A1":1.0,"A2":.75,"B1":.45,"B2":.25}
races=[]
for race in data.get("races",[]):
 rid=race.get("race_id","").replace("_","-"); act=actual.get(rid)
 if not act:continue
 boats=[]
 for b in race.get("boats",[]):
  racer=b.get("racer") or {}; reg=key(racer.get("registration_no")); lane=key(b.get("boat")); venue=key(race.get("venue_code"))
  before=b.get("beforeinfo") or {}; course=key(before.get("exhibition_course")) if before.get("exhibition_course") else lane
  cr=rc.get((reg,course)); vr=rv.get((reg,venue)); orow=rr.get((reg,))
  boats.append({"boat":int(lane),"rc":scoped(cr),"ability":overall(orow),"grade":grades.get(racer.get("grade"),.4),"recent":recent(orow),"venue":scoped(vr),"series":series(racer.get("series_results_raw") or b.get("series_results_raw"))})
 races.append((act,boats))
def run(name,fn):
 e=t=ex=o=0
 for a,bs in races:
  p=[b["boat"] for b in sorted(bs,key=lambda b:(-fn(b),b["boat"]))[:3]]
  e+=1;t+=set(p)==set(a);ex+=p==a;o+=p[0]==a[0]
 return {"name":name,"races":e,"top3_matches":t,"top3_alignment_pct":round(t/e*100,2),"exact_matches":ex,"exact_alignment_pct":round(ex/e*100,2),"top1_matches":o,"top1_accuracy_pct":round(o/e*100,2)}
tests=[
("1 選手×当該コース適性",lambda b:b["rc"]),
("2 選手×コース × 公式能力",lambda b:b["rc"]*b["ability"]),
("3 選手×コース × 級別",lambda b:b["rc"]*b["grade"]),
("4 選手×コース × 直近成績",lambda b:b["rc"]*b["recent"]),
("5 選手×コース × 当地適性",lambda b:b["rc"]*b["venue"]),
("6 選手×コース × 当地 × 公式能力",lambda b:b["rc"]*b["venue"]*b["ability"])]
results=[run(n,f) for n,f in tests]
OUT.mkdir(parents=True,exist_ok=True);(OUT/"racer_course_steps_1to6_20261002.json").write_text(json.dumps({"date":"20261002","note":"係数なし。選手本人の当該コース90日特徴を基準に掛け算。10/2事後検証。","results":results},ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(results,ensure_ascii=False,indent=2))
