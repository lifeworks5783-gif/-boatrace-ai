#!/usr/bin/env python3
# User-proposed structure: ((racer-course * grade * series) * recent * exST * motor) + official + boat.
import csv,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];F=ROOT/"features";P=ROOT/"evaluations/2026/10/02/backfill_live/prediction_input_enriched_live_20261002.json";PROG=ROOT/"daily_inputs/2026/10/02/base/program_entries_20261002.csv";LIVE=ROOT/"daily_inputs/2026/10/02/live/backfill/beforeinfo_entries_20261002.csv";R=ROOT/"archive/2026/10/02/boat_results_20261002_all.csv";O=ROOT/"evaluations/2026/10/02/racer_course_7steps"
def rows(p):
 with p.open(encoding="utf-8-sig",newline="") as h:return list(csv.DictReader(h))
def f(x,d=None):
 try:return float(x)
 except:return d
def key(x):
 try:return str(int(float(x)))
 except:return str(x or "").strip()
def rate(x,d=.5):
 x=f(x);return d if x is None else x/100 if x>1 else x
def clip(x):return max(0,min(1,x))
def invst(x):return clip(1-f(x,.20)/.35)
def idx(rs,cs):return {tuple(key(r.get(c)) for c in cs):r for r in rs}
def rcscore(r):
 if not r:return .5
 return .45*rate(r.get("d90_top3_rate"))+.25*rate(r.get("d90_win_rate"))+.15*rate(r.get("d90_top2_rate"))+.15*invst(r.get("d90_avg_st"))
rc=idx(rows(F/"racer_course_features.csv"),["registration_no","course"]);rf=idx(rows(F/"racer_features.csv"),["registration_no"]);prog=idx(rows(PROG),["race_id","boat"]);live=idx(rows(LIVE),["race_id","boat"]);pred=json.loads(P.read_text(encoding="utf-8"))
actual={}
for r in rows(R):
 try:actual.setdefault(r["race_id"].replace("_","-"),[]).append((int(float(r["finish"])),int(float(r["boat"]))))
 except:pass
actual={k:[b for _,b in sorted(v)][:3] for k,v in actual.items() if len(v)==6}
grades={"A1":1.0,"A2":.75,"B1":.45,"B2":.25}; races=[]
for race in pred.get("races",[]):
 rid=str(race.get("race_id","")).replace("_","-");a=actual.get(rid)
 if not a:continue
 bs=[]
 for b in race.get("boats",[]):
  lane=int(float(b["boat"])); racer=b.get("racer") or {}; pr=prog.get((key(rid),key(lane))) or {}; lr=live.get((key(rid),key(lane))) or {}; reg=key(pr.get("registration_no") or racer.get("registration_no")); course=key(lr.get("exhibition_course")) if lr.get("exhibition_course") else str(lane)
  nw=f(pr.get("national_win_rate")); n2=f(pr.get("national_top2_rate")); official=.5 if nw is None or n2 is None else (nw/10*.5333333333+n2/100*.4666666667)
  sr=[int(x) for x in re.findall(r"[1-6]",str(pr.get("series_results_raw") or ""))]; series=.5 if not sr else sum(((7-v)/6)*w for v,w in zip(sr,range(1,len(sr)+1)))/sum(range(1,len(sr)+1))
  boatc=(f(pr.get("boat_top2_rate")) or 0)/100; motor=(f(pr.get("motor_top2_rate")) or 0)/100; st=f(lr.get("exhibition_st_seconds")); exST=.5 if st is None else clip(1-st/.35)
  hr=rf.get((reg,)); recent=.5 if not hr else .35*rate(hr.get("last5_top3_rate"))+.30*rate(hr.get("last10_top3_rate"))+.25*rate(hr.get("d30_top3_rate"))+.10*clip((6-f(hr.get("last10_avg_finish"),3.5))/5); avgst=f(hr.get("d90_avg_st")) if hr else None; stdiff=None if st is None or avgst is None else st-avgst; isf=str(lr.get("exhibition_st_flag") or "").upper().startswith("F")
  bs.append({"boat":lane,"base":rcscore(rc.get((reg,course)))*grades.get(str(pr.get("grade") or racer.get("grade","")).upper(),.4),"official":official,"series":series,"boatc":boatc,"exST":exST,"recent":recent,"motor":motor,"stdiff":stdiff,"isf":isf})
 races.append((a,bs))
def stcorr(b,strength):
 if b["isf"]: return 1.0-strength
 d=b["stdiff"]
 if d is None:return 1.0
 # difference is exhibition ST - racer 90d average ST; negative = faster than usual
 z=max(-1,min(1,-d/.10))
 return 1.0+z*strength
def corr(x,strength): return 1.0+(x-.5)*2*strength
def formula(b,s):
 base=b["base"]*b["series"]
 corrected=base*corr(b["recent"],s)*stcorr(b,s)*corr(b["motor"],s)
 return corrected+b["official"]+b["boatc"]
forms=[("相対ST補正±5%",lambda b:formula(b,.05)),("相対ST補正±10%",lambda b:formula(b,.10)),("相対ST補正±15%",lambda b:formula(b,.15)),("相対ST補正±20%",lambda b:formula(b,.20)),("相対ST補正±25%",lambda b:formula(b,.25)),("相対ST補正±30%",lambda b:formula(b,.30))]
