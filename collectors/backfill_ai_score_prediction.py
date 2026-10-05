#!/usr/bin/env python3
"""Backfill AI finish-order scores from saved prediction data only.
Results are never read here; they are used later by evaluate_ai_score_prediction.py.
"""
from __future__ import annotations
import argparse,itertools,json,math
from pathlib import Path

MODEL="ai_finish_order_score_v0_20261005"

def f(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None
def boatno(r):
    for k in ("boat","boat_no","艇番","frame"):
        x=f(r.get(k))
        if x and 1<=int(x)<=6:return int(x)
    return None
def score(r):
    for k in ("score","final_score","prediction_score"):
        x=f(r.get(k))
        if x is not None:return x
    return 0.0
def comp(r,key,default):
    x=f((((r.get("components") or {}).get(key) or {}).get("raw_score_0_1")))
    return default if x is None else max(0,min(1,x))

def ai(boats):
    if len(boats)!=6:return None
    out=[]
    for r in boats:
        b=boatno(r); overall=max(0,min(1,score(r)/100))
        structural=comp(r,"structural",overall); et=comp(r,"exTime",overall); st=comp(r,"exST",overall)
        if "structural" in (r.get("components") or {}):
            a=.48*structural+.10*et+.22*st+.20*overall
            s=.58*structural+.08*et+.14*st+.20*overall
            t=.66*structural+.07*et+.07*st+.20*overall
        else:
            course=comp(r,"racer_course",overall);grade=comp(r,"grade",overall);motor=comp(r,"motor",overall)
            machine=comp(r,"boat",overall);national=comp(r,"national_top2",overall)
            a=.35*course+.18*grade+.14*motor+.05*machine+.10*national+.18*overall
            s=.25*course+.20*grade+.17*motor+.06*machine+.14*national+.18*overall
            t=.18*course+.16*grade+.22*motor+.10*machine+.16*national+.18*overall
        out.append({"boat":b,"first_score":round(a*100,2),"second_score":round(s*100,2),"third_score":round(t*100,2)})
    if any(x["boat"] is None for x in out):return None
    m={x["boat"]:x for x in out}; combos=[]
    for a,b,c in itertools.permutations(sorted(m),3):
        joint=((max(m[a]["first_score"],.01)/100)*(max(m[b]["second_score"],.01)/100)*(max(m[c]["third_score"],.01)/100))**(1/3)
        combos.append({"combination":f"{a}-{b}-{c}","score":round(joint*100,3)})
    combos.sort(key=lambda x:(-x["score"],x["combination"]))
    return {"model_version":MODEL,"status":"historical_backfill","points":8,"investment_100yen":800,
      "position_scores":sorted(out,key=lambda x:x["boat"]),"combinations":combos[:8],"all_120_combinations":combos,
      "note":"過去保存予測のみで再計算。結果データは計算に未使用。表示上位12点、収支上位8点。"}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--date",required=True);a=ap.parse_args();d=a.date
    p=Path("predictions")/d[:4]/d[4:6]/d[6:8]/"live"/f"formation_predictions_final_{d}.json"
    data=json.loads(p.read_text(encoding="utf-8"));n=0
    for r in data.get("races") or []:
        if r.get("ai_score_prediction"):continue
        x=ai(r.get("boats") or [])
        if x:r["ai_score_prediction"]=x;n+=1
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print("AI historical backfill:",d,n,"R")
if __name__=="__main__":main()
