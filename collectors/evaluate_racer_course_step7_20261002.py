#!/usr/bin/env python3
import csv,json,math,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];F=ROOT/"features";INP=ROOT/"evaluations/2026/10/02/backfill_live/prediction_input_enriched_live_20261002.json";RES=ROOT/"archive/2026/10/02/boat_results_20261002_all.csv";OUT=ROOT/"evaluations/2026/10/02/racer_course_7steps"
def csvs(p):
 with p.open(encoding="utf-8-sig",newline="") as h:return list(csv.DictReader(h))
def n(x,d=None):
 try:return float(x)
 except:return d
def k(x):
 try:return str(int(float(x)))
 except:return str(x or "").strip()
def rate(x,d=.5):
 x=n(x);return d if x is None else x/100 if x>1 else x
def clip(x):return max(0,min(1,x))
def invst(x):return clip(1-n(x,.20)/.35)
def finish(x):return clip((6-n(x,3.5))/5)
def trend(x,s=.5):return clip(.5+n(x,0)/s)
def series(x):
 a=[int(z) for z in re.findall(r"[1-6]",str(x or ""))]
 if not a:return .5
 w=range(1,len(a)+1);return sum(((7-v)/6)*q for v,q in zip(a,w))/sum(w)
def idx(rows,cols):return {tuple(k(r.get(c)) for c in cols):r for r in rows}
def scoped(r):
 if not r:return .5
 return .45*rate(r.get("d90_top3_rate"))+.25*rate(r.get("d90_win_rate"))+.15*rate(r.get("d90_top2_rate"))+.15*invst(r.get("d90_avg_st"))
def ability(r):
 if not r:return .5
 return .5*rate(r.get("d90_top3_rate"))+.25*rate(r.get("d30_top3_rate"))+.15*finish(r.get("last10_avg_finish"))+.10*trend(r.get("trend_top3_rate_30v90"))
def recent(r):
 if not r:return .5
 return .35*rate(r.get("last5_top3_rate"))+.30*rate(r.get("last10_top3_rate"))+.25*rate(r.get("d30_top3_rate"))+.10*finish(r.get("last10_avg_finish"))
rc=idx(csvs(F/"racer_course_features.csv"),["registration_no","course"]);rr=idx(csvs(F/"racer_features.csv"),["registration_no"])
data=json.loads(INP.read_text(encoding="utf-8"));actual={}
for r in csvs(RES):
 try:actual.setdefault(r["race_id"].replace("_","-"),[]).append((int(float(r["finish"])),int(float(r["boat"]))))
 except:pass
actual={x:[b for _,b in sorted(v)][:3] for x,v in actual.items() if len(v)==6};grades={"A1":1.0,"A2":.75,"B1":.45,"B2":.25}
races=[]
for race in data.get("races",[]):
 rid=race.get("race_id","").replace("_","-");a=actual.get(rid)
 if not a:continue
 bs=[]
 for b in race.get("boats",[]):
  racer=b.get("racer") or {};reg=k(racer.get("registration_no"));lane=k(b.get("boat"));course=k((b.get("beforeinfo") or {}).get("exhibition_course")) or lane
  cr=rc.get((reg,course));r=rr.get((reg,));com=b.get("components") or {}
  def raw(name):
   z=com.get(name) or {};return n(z.get("raw_score_0_1"),.5)
  bs.append({"boat":int(lane),"rc":scoped(cr),"grade":grades.get(racer.get("grade"),raw("grade")),"official":raw("official"),"recent":raw("recent"),"series":raw("series") if raw("series")!=.5 else series(racer.get("series_results_raw") or b.get("series_results_raw")),"boatc":raw("boat"),"motor":raw("motor"),"exST":raw("exST"),"live_course":raw("course")})
 races.append((a,bs))
# Step 7: replace old generic course term with racer-course compatibility; plus racer-course×grade block variants.
forms=[
("朝A 旧上位式のcourse→選手コース","grade*series*boatc + rc + official",lambda b:b["grade"]*b["series"]*b["boatc"]+b["rc"]+b["official"]),
("朝B 選手コース×級別ブロック","rc*grade + series + boatc + official",lambda b:b["rc"]*b["grade"]+b["series"]+b["boatc"]+b["official"]),
("朝C 選手コース×級別 + 公式","rc*grade + official",lambda b:b["rc"]*b["grade"]+b["official"]),
("朝D 選手コース×級別 + 今節","rc*grade + series",lambda b:b["rc"]*b["grade"]+b["series"]),
("直前A 旧上位式のcourse→選手コース","official*series*exST + rc + recent",lambda b:b["official"]*b["series"]*b["exST"]+b["rc"]+b["recent"]),
("直前B 選手コース×級別 + 展示ST + 公式","rc*grade + exST + official",lambda b:b["rc"]*b["grade"]+b["exST"]+b["official"]),
("直前C 選手コース×級別 + 展示ST + 今節","rc*grade + b['exST'] + series",lambda b:b["rc"]*b["grade"]+b["exST"]+b["series"]),
]
# fix display typo only; lambdas are authoritative
out=[]
for name,formula,fn in forms:
 e=t=ex=o=0
 for a,bs in races:
  p=[b["boat"] for b in sorted(bs,key=lambda b:(-fn(b),b["boat"]))[:3]]
  e+=1;t+=set(p)==set(a);ex+=p==a;o+=p[0]==a[0]
 out.append({"name":name,"formula":formula,"races":e,"top3_matches":t,"top3_alignment_pct":round(t/e*100,2),"exact_matches":ex,"exact_alignment_pct":round(ex/e*100,2),"top1_matches":o,"top1_accuracy_pct":round(o/e*100,2)})
out.sort(key=lambda x:(-x["top3_alignment_pct"],-x["exact_alignment_pct"],-x["top1_accuracy_pct"]))
OUT.mkdir(parents=True,exist_ok=True);(OUT/"racer_course_step7_20261002.json").write_text(json.dumps({"date":"20261002","rule":"係数なし。従来の一般コース項を選手本人×当該コース適性に置換し、選手コース×級別ブロックも比較。","results":out},ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(out,ensure_ascii=False,indent=2))
