#!/usr/bin/env python3
import csv,json
from pathlib import Path
DATES=["20260930","20261001","20261002"]
COMPS=["course","official","recent","venue","motor","boat","grade","series","exST"]
LABEL={"course":"コース","official":"公式能力","recent":"直近成績","venue":"当地","motor":"モーター","boat":"ボート","grade":"級別","series":"今節","exST":"展示ST"}
OUT=Path("evaluations/2026/component_3day")
def paths(d):
 y,m,dd=d[:4],d[4:6],d[6:8]
 if d=="20261002": p=Path("evaluations/2026/10/02/backfill_live/live_predictions_final_20261002.json")
 else:p=Path(f"data/rebuild_{d}/live_predictions_final_{d}.json")
 r=Path(f"archive/{y}/{m}/{dd}/boat_results_{d}_all.csv")
 return p,r
def val(b,c):
 x=(b.get("components") or {}).get(c) or {}
 try:return float(x["raw_score_0_1"]) if x.get("available") else None
 except:return None
allres={}
tot={c:{"eligible":0,"matches":0} for c in COMPS}
for d in DATES:
 pp,rp=paths(d); pred=json.loads(pp.read_text(encoding="utf-8"))
 actual={}
 with rp.open(encoding="utf-8-sig",newline="") as f:
  for r in csv.DictReader(f):
   try:actual.setdefault(r["race_id"],[]).append((int(float(r["finish"])),int(float(r["boat"]))))
   except:pass
 actual={k:[b for _,b in sorted(v)][:3] for k,v in actual.items() if len(v)==6}
 day={}
 for c in COMPS:
  e=h=0
  for race in pred["races"]:
   a=actual.get(race["race_id"].replace("-","_"))
   if not a:continue
   vs=[(int(b["boat"]),val(b,c)) for b in race["boats"]]
   if not all(v is not None for _,v in vs):continue
   p3=[b for b,v in sorted(vs,key=lambda z:(-z[1],z[0]))[:3]]
   e+=1; h+=set(p3)==set(a)
  day[c]={"label":LABEL[c],"eligible_races":e,"matches":h,"alignment_pct":round(h/e*100,2) if e else None}
  tot[c]["eligible"]+=e;tot[c]["matches"]+=h
 allres[d]=day
total={}
for c,s in tot.items():
 e=s["eligible"];h=s["matches"];total[c]={"label":LABEL[c],"eligible_races":e,"matches":h,"alignment_pct":round(h/e*100,2) if e else None}
summary={"definition":"各要素単体スコアTOP3と実着TOP3が順不同で3艇完全一致のみ○","dates":allres,"three_day_total":total,"note":"9/30・10/1は保存済み当日データを現行統一コンポーネント式で再構築。10/2はhistorical backfill。直前系は取得可能レースのみ。"}
OUT.mkdir(parents=True,exist_ok=True)
(OUT/"single_component_20260930_20261002.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
