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
  hr=rf.get((reg,)); recent=.5 if not hr else .35*rate(hr.get("last5_top3_rate"))+.30*rate(hr.get("last10_top3_rate"))+.25*rate(hr.get("d30_top3_rate"))+.10*clip((6-f(hr.get("last10_avg_finish"),3.5))/5)
  bs.append({"boat":lane,"base":rcscore(rc.get((reg,course)))*grades.get(str(pr.get("grade") or racer.get("grade","")).upper(),.4),"official":official,"series":series,"boatc":boatc,"exST":exST,"recent":recent,"motor":motor})
 races.append((a,bs))
forms=[("提案式 ((選手コース×級別×今節)×直近×展示ST×モーター)+公式+ボート",lambda b:(b["base"]*b["series"]*b["recent"]*b["exST"]*b["motor"])+b["official"]+b["boatc"]),("基準 選手コース×級別",lambda b:b["base"]),("×公式",lambda b:b["base"]*b["official"]),("×今節",lambda b:b["base"]*b["series"]),("×ボート",lambda b:b["base"]*b["boatc"]),("×展示ST",lambda b:b["base"]*b["exST"]),("×直近",lambda b:b["base"]*b["recent"]),("×モーター",lambda b:b["base"]*b["motor"]),("×公式×今節",lambda b:b["base"]*b["official"]*b["series"]),("×公式×展示ST",lambda b:b["base"]*b["official"]*b["exST"]),("×今節×展示ST",lambda b:b["base"]*b["series"]*b["exST"]),("×公式×今節×展示ST",lambda b:b["base"]*b["official"]*b["series"]*b["exST"]),("×公式×ボート",lambda b:b["base"]*b["official"]*b["boatc"]),("×公式×モーター",lambda b:b["base"]*b["official"]*b["motor"])]
out=[]
for name,fn in forms:
 n=t=e=o=0
 for a,bs in races:
  p=[x["boat"] for x in sorted(bs,key=lambda x:(-fn(x),x["boat"]))[:3]];n+=1;t+=set(p)==set(a);e+=p==a;o+=p[0]==a[0]
 out.append({"name":name,"races":n,"top3_matches":t,"top3_alignment_pct":round(100*t/n,2),"exact_matches":e,"exact_alignment_pct":round(100*e/n,2),"top1_matches":o,"top1_accuracy_pct":round(100*o/n,2)})
out.sort(key=lambda x:(-x["top3_alignment_pct"],-x["exact_alignment_pct"],-x["top1_accuracy_pct"]))
O.mkdir(parents=True,exist_ok=True);(O/"proposed_formula_test_20261002.json").write_text(json.dumps({"date":"20261002","rule":"ユーザー提案: 基本=選手×当該コース適性×級別×今節、補正=直近×展示ST×モーター、加算=公式+ボート。係数なし。","results":out},ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(out,ensure_ascii=False,indent=2))
