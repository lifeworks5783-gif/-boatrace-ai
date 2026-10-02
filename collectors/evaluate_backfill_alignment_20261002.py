#!/usr/bin/env python3
import csv, json
from pathlib import Path

DATE="20261002"
PRED=Path("evaluations/2026/10/02/backfill_live/live_predictions_final_20261002.json")
RESULT=Path("archive/2026/10/02/boat_results_20261002_all.csv")
OUT=Path("evaluations/2026/10/02/backfill_alignment")
COMPONENTS=["course","official","recent","venue","motor","boat","grade","avgST","series","exTime","exST","discipline"]

def top3_match(pred3, actual3):
    return set(pred3)==set(actual3)

def comp_value(boat, name):
    c=(boat.get("components") or {}).get(name)
    if not isinstance(c,dict) or not c.get("available"): return None
    try: return float(c["raw_score_0_1"])
    except (TypeError,ValueError,KeyError): return None

pred=json.loads(PRED.read_text(encoding="utf-8"))
actual={}
with RESULT.open(encoding="utf-8",newline="") as f:
    for r in csv.DictReader(f):
        try: finish=int(float(r["finish"])); boat=int(float(r["boat"]))
        except (TypeError,ValueError): continue
        actual.setdefault(r["race_id"],[]).append((finish,boat))
actual={rid:[b for _,b in sorted(v)] for rid,v in actual.items() if len(v)==6}

rows=[]
single={c:{"eligible":0,"matches":0} for c in COMPONENTS}
current_matches=0
for race in pred["races"]:
    rid=race["race_id"]; result_rid=rid.replace("-", "_"); act=actual.get(result_rid)
    if not act: continue
    act3=act[:3]
    boats=race["boats"]
    pred3=[int(x["boat"]) for x in sorted(boats,key=lambda x:(int(x.get("rank",99)),int(x["boat"])))[:3]]
    ok=top3_match(pred3,act3); current_matches+=ok
    row={"race_id":rid,"venue_name":race.get("venue_name",""),"race":race.get("race"),"actual_top3":"-".join(map(str,act3)),"current_top3":"-".join(map(str,pred3)),"current_match":int(ok)}
    for c in COMPONENTS:
        vals=[(int(b["boat"]),comp_value(b,c)) for b in boats]
        if all(v is not None for _,v in vals):
            p3=[b for b,v in sorted(vals,key=lambda z:(-z[1],z[0]))[:3]]
            hit=top3_match(p3,act3)
            single[c]["eligible"]+=1; single[c]["matches"]+=hit
            row[c+"_top3"]="-".join(map(str,p3)); row[c+"_match"]=int(hit)
        else:
            row[c+"_top3"]=""; row[c+"_match"]=""
    rows.append(row)

n=len(rows)
summary={
 "date":DATE,
 "definition":"整合率=予測スコア上位3艇と実着1〜3着の3艇が順不同で完全一致したレース割合。3艇完全一致のみ○、2艇以下は×。",
 "provenance":"historical_backfill_after_races; 本番リアルタイム成績とは分離",
 "overall":{"races":n,"matches":current_matches,"alignment_pct":round(current_matches/n*100,2) if n else None},
 "single_components":{}
}
for c,s in single.items():
    e=s["eligible"]
    summary["single_components"][c]={"eligible_races":e,"matches":s["matches"],"alignment_pct":round(s["matches"]/e*100,2) if e else None}
summary["single_component_ranking"]=sorted(
 [{"component":c,**v} for c,v in summary["single_components"].items() if v["eligible_races"]],
 key=lambda x:(-x["alignment_pct"],-x["eligible_races"],x["component"])
)
OUT.mkdir(parents=True,exist_ok=True)
(OUT/"alignment_summary_20261002.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
with (OUT/"alignment_races_20261002.csv").open("w",encoding="utf-8",newline="") as f:
    fields=list(rows[0].keys()); w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
print(json.dumps(summary,ensure_ascii=False,indent=2))
if n!=168: raise SystemExit(f"対象レース数が168ではありません: {n}")
