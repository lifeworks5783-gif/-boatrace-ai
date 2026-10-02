#!/usr/bin/env python3
import csv, json
from pathlib import Path

DATE="20261002"
PRED=Path("evaluations/2026/10/02/backfill_live/live_predictions_final_20261002.json")
RESULT=Path("archive/2026/10/02/boat_results_20261002_all.csv")
FORMATION=Path("evaluations/2026/10/02/formation_simulation_20261002.json")
OUT=Path("evaluations/2026/10/02/backfill_alignment")
BASE=["course","official","recent","venue","motor","boat","grade","series"]
LIVE=["live_course","exST","exTime"]
PAIRS={
 "course_x_venue":("course","venue"),
 "course_x_official":("course","official"),
 "grade_x_official":("grade","official"),
 "official_x_recent":("official","recent"),
}
FRAME_PRIOR={1:1.00,2:.72,3:.62,4:.58,5:.46,6:.38}

def match(a,b): return set(a)==set(b)
def fnum(v):
    try:return float(v)
    except:return None
def comp(boat,name):
    c=(boat.get("components") or {}).get(name)
    if not isinstance(c,dict) or not c.get("available"): return None
    return fnum(c.get("raw_score_0_1"))
def rank_top3(vals,lower=False):
    if len(vals)!=6 or any(v is None for _,v in vals): return None
    return [b for b,v in sorted(vals,key=(lambda z:(z[1],z[0])) if lower else (lambda z:(-z[1],z[0])))[:3]]
def metric():
    return {"eligible_races":0,"matches":0,"alignment_pct":None,"investment":0,"return":0,"profit":0,"recovery_rate_pct":None}
def add(m,hit,payout):
    m["eligible_races"]+=1;m["matches"]+=int(hit);m["investment"]+=600
    if hit:m["return"]+=int(payout or 0)
def finish(m):
    e=m["eligible_races"];inv=m["investment"]
    m["alignment_pct"]=round(m["matches"]/e*100,2) if e else None
    m["profit"]=m["return"]-inv
    m["recovery_rate_pct"]=round(m["return"]/inv*100,2) if inv else None
    return m

pred=json.loads(PRED.read_text(encoding="utf-8"))
form=json.loads(FORMATION.read_text(encoding="utf-8"))
payout={x["race_id"]:x.get("trifecta_payout_100yen",0) for x in form.get("details",[])}
actual={}
with RESULT.open(encoding="utf-8",newline="") as f:
    for r in csv.DictReader(f):
        try:fi=int(float(r["finish"]));b=int(float(r["boat"]))
        except:continue
        actual.setdefault(r["race_id"],[]).append((fi,b))
actual={k:[b for _,b in sorted(v)] for k,v in actual.items() if len(v)==6}

morning={k:metric() for k in BASE}
live={k:metric() for k in LIVE}
pairs={k:metric() for k in PAIRS}
rows=[];overall=0
for race in pred["races"]:
    rid=race["race_id"]; act=actual.get(rid.replace("-","_"))
    if not act:continue
    act3=act[:3];boats=race["boats"];pay=payout.get(rid,0)
    pred3=[int(x["boat"]) for x in sorted(boats,key=lambda x:(int(x.get("rank",99)),int(x["boat"])))[:3]]
    overall+=int(match(pred3,act3))
    row={"race_id":rid,"actual_top3":"-".join(map(str,act3))}
    # 朝基本要素。courseだけ枠番prior、その他は直前でも値が変わらない基本成分。
    for name in BASE:
        vals=[]
        for b in boats:
            lane=int(b["boat"])
            v=FRAME_PRIOR[lane] if name=="course" else comp(b,name)
            vals.append((lane,v))
        p3=rank_top3(vals)
        if p3:
            hit=match(p3,act3);add(morning[name],hit,pay)
            row["morning_"+name+"_top3"]="-".join(map(str,p3));row["morning_"+name+"_match"]=int(hit)
    # 直前単体
    for name in LIVE:
        vals=[]
        for b in boats:
            lane=int(b["boat"])
            if name=="live_course":v=comp(b,"course");lower=False
            elif name=="exST":v=comp(b,"exST");lower=False
            else:v=fnum(b.get("exhibition_time"));lower=True
            vals.append((lane,v))
        p3=rank_top3(vals,lower=lower)
        if p3:
            hit=match(p3,act3);add(live[name],hit,pay)
            row["live_"+name+"_top3"]="-".join(map(str,p3));row["live_"+name+"_match"]=int(hit)
    # 50:50掛け合わせ（朝基本成分）
    for key,(a,bn) in PAIRS.items():
        vals=[]
        for b in boats:
            lane=int(b["boat"])
            va=FRAME_PRIOR[lane] if a=="course" else comp(b,a)
            vb=FRAME_PRIOR[lane] if bn=="course" else comp(b,bn)
            vals.append((lane,None if va is None or vb is None else (va+vb)/2))
        p3=rank_top3(vals)
        if p3:
            hit=match(p3,act3);add(pairs[key],hit,pay)
            row[key+"_top3"]="-".join(map(str,p3));row[key+"_match"]=int(hit)
    rows.append(row)

summary={
 "date":DATE,
 "definition":"TOP3完全整合率=単体要素で順位付けした上位3艇と実着1〜3着の3艇が順不同で完全一致した割合。",
 "period_note":"固定定義の蓄積開始日が20261002のため、現時点では本日・直近7日・累計は同じ20261002の値。",
 "provenance":"20261002 historical backfill evaluation; production weights unchanged",
 "overall":{"races":len(rows),"matches":overall,"alignment_pct":round(overall/len(rows)*100,2)},
 "morning_single_components":{k:finish(v) for k,v in morning.items()},
 "live_single_components":{k:finish(v) for k,v in live.items()},
 "pair_components":{k:finish(v) for k,v in pairs.items()},
 "simulation_rule":"各単体/掛け合わせのTOP3を3連単6点BOX、100円/点（600円/R）で検証。完全整合なら実際の3連単払戻を100円分計上。",
}
# backward compatibility
summary["single_components"]={**summary["morning_single_components"],
 "exST":summary["live_single_components"]["exST"],
 "exTime":summary["live_single_components"]["exTime"]}
summary["single_component_ranking"]=sorted(
 [{"component":k,**v} for k,v in summary["single_components"].items() if v["eligible_races"]],
 key=lambda x:(-(x["alignment_pct"] or 0),-x["eligible_races"],x["component"]))
OUT.mkdir(parents=True,exist_ok=True)
(OUT/"alignment_summary_20261002.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
with (OUT/"alignment_races_20261002.csv").open("w",encoding="utf-8",newline="") as f:
    fields=sorted({k for r in rows for k in r});w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
print(json.dumps(summary,ensure_ascii=False,indent=2))
if len(rows)!=168:raise SystemExit(f"対象レース数が168ではありません: {len(rows)}")
