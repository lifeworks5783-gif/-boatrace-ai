#!/usr/bin/env python3
import csv,json,random
from pathlib import Path
DATE="20261002"
PRED=Path("evaluations/2026/10/02/backfill_live/live_predictions_final_20261002.json")
RESULT=Path("archive/2026/10/02/boat_results_20261002_all.csv")
OUT=Path("evaluations/2026/10/02/weight_search")
COMPS=["course","official","recent","venue","motor","boat","grade","series","exST"]
BASE={"course":32,"official":12,"recent":8,"venue":6,"motor":1,"boat":6,"grade":15,"series":17,"exST":3}
# 単体整合率を探索の中心値に使う。production weightsは変更しない。
SINGLE={"grade":18.45,"official":17.26,"course":14.29,"recent":13.69,"venue":12.50,"series":10.32,"exST":8.48,"motor":4.76,"boat":3.57}

pred=json.loads(PRED.read_text(encoding="utf-8"))
actual={}
with RESULT.open(encoding="utf-8-sig",newline="") as f:
  for r in csv.DictReader(f):
    try: fin=int(float(r["finish"])); b=int(float(r["boat"]))
    except: continue
    actual.setdefault(r["race_id"],[]).append((fin,b))
actual={k:[b for _,b in sorted(v)][:3] for k,v in actual.items() if len(v)==6}

races=[]
for r in pred["races"]:
  a=actual.get(r["race_id"].replace("-","_"))
  if not a: continue
  boats=[]
  for b in r["boats"]:
    vals={}
    for c in COMPS:
      x=(b.get("components") or {}).get(c) or {}
      vals[c]=float(x["raw_score_0_1"]) if x.get("available") and x.get("raw_score_0_1") is not None else None
    boats.append((int(b["boat"]),vals))
  races.append((r["race_id"],a,boats))
if len(races)!=168: raise SystemExit(f"168Rではありません: {len(races)}")

def evalw(w):
  hits=0
  for _,a,boats in races:
    scored=[]
    for bn,v in boats:
      den=sum(w[c] for c in COMPS if v[c] is not None and w[c]>0)
      s=sum(w[c]*v[c] for c in COMPS if v[c] is not None and w[c]>0)/den if den else 0
      scored.append((s,bn))
    p=[bn for _,bn in sorted(scored,key=lambda z:(-z[0],z[1]))[:3]]
    hits += set(p)==set(a)
  return hits,round(hits/len(races)*100,2)

cands={}
def add(w,label):
  w={c:int(w.get(c,0)) for c in COMPS}
  if sum(w.values())<=0:return
  key=tuple(w[c] for c in COMPS)
  if key not in cands:cands[key]=(w,label)

add(BASE,"current")
# 単体率比例を複数スケールで整数化
for total in (80,100,120,150):
  s=sum(SINGLE.values())
  add({c:round(total*SINGLE[c]/s) for c in COMPS},f"single_prop_{total}")
# 上位要素を段階強調
for grade in range(12,31,3):
 for official in range(10,26,3):
  for course in range(8,25,4):
   w=dict(BASE); w.update(grade=grade,official=official,course=course)
   add(w,"focused_grid")
# 再現可能なランダム探索。中心は単体率比例、弱い要素もゼロ固定にしない
rng=random.Random(20261002)
center={c:100*SINGLE[c]/sum(SINGLE.values()) for c in COMPS}
for i in range(25000):
  w={}
  for c in COMPS:
    lo=max(0,center[c]*0.25); hi=center[c]*2.5
    # courseは枠/進入効果を完全に消さない
    if c=="course": lo=max(lo,5)
    w[c]=round(rng.uniform(lo,hi))
  add(w,"single_guided_random")

results=[]
for w,label in cands.values():
  h,p=evalw(w)
  results.append({"alignment_pct":p,"matches":h,"races":168,"source":label,"weights":w})
results.sort(key=lambda x:(-x["matches"],sum(abs(x["weights"][c]-BASE[c]) for c in COMPS),tuple(x["weights"][c] for c in COMPS)))
top10=results[:10]
base=next(x for x in results if x["source"]=="current")
summary={"date":DATE,"definition":"予測スコアTOP3と実着TOP3が順不同で3艇完全一致のみ○","provenance":"historical_backfill_after_races; 本番リアルタイム成績とは分離","production_weights_changed":False,"candidate_count":len(results),"base":base,"top10":top10}
OUT.mkdir(parents=True,exist_ok=True)
(OUT/"weight_search_summary_20261002.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
with (OUT/"weight_search_top10_20261002.csv").open("w",encoding="utf-8",newline="") as f:
  fields=["rank","alignment_pct","matches","races","source"]+COMPS
  wr=csv.DictWriter(f,fieldnames=fields);wr.writeheader()
  for i,x in enumerate(top10,1): wr.writerow({"rank":i,"alignment_pct":x["alignment_pct"],"matches":x["matches"],"races":168,"source":x["source"],**x["weights"]})
print(json.dumps(summary,ensure_ascii=False,indent=2))
