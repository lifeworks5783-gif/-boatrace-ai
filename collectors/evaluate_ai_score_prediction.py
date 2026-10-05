#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,math,re
from collections import defaultdict
from pathlib import Path

BET=100

def text(v): return "" if v is None else str(v).strip()
def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception: return None
def cint(v):
    x=num(v); return None if x is None else int(x)
def rid(v): return "".join(re.findall(r"\d",text(v)))
def load(p):
    p=Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
def bucket(): return {"races":0,"hits":0,"points":0,"investment":0,"return":0,"top3_matches":0,"exact_matches":0}
def summary(b):
    return {**b,
      "hit_rate": round(b["hits"]/b["races"],5) if b["races"] else None,\n      "top3_alignment_rate": round(b["top3_matches"]/b["races"],5) if b["races"] else None,\n      "exact_alignment_rate": round(b["exact_matches"]/b["races"],5) if b["races"] else None,
      "average_points_per_race": round(b["points"]/b["races"],3) if b["races"] else None,
      "profit":b["return"]-b["investment"],
      "recovery_rate_pct":round(b["return"]/b["investment"]*100,2) if b["investment"] else None}
def add(b,hit,pts,ret):
    b["races"]+=1;b["hits"]+=hit;b["points"]+=pts;b["investment"]+=pts*BET;b["return"]+=ret

def actual(date):
    base=Path("archive")/date[:4]/date[4:6]/date[6:8]
    boats=base/f"boat_results_{date}_all.csv"; results=base/f"results_{date}_all.csv"
    by=defaultdict(list); pay={}
    with boats.open(encoding="utf-8-sig",newline="") as f:
        for r in csv.DictReader(f):
            k=rid(r.get("race_id")); finish=cint(r.get("finish")); boat=cint(r.get("boat"))
            if k and boat and finish in (1,2,3): by[k].append((finish,boat))
    if results.exists():
        with results.open(encoding="utf-8-sig",newline="") as f:
            for r in csv.DictReader(f):
                k=rid(r.get("race_id"))
                for key in ("trifecta_pay","trifecta_payout","sanrentan_pay","3rentan_pay"):
                    if r.get(key) not in (None,""):
                        pay[k]=cint(str(r.get(key)).replace(",","")) or 0; break
    out={}
    for k,rows in by.items():
        rows=sorted(rows)
        if len(rows)>=3 and [x[0] for x in rows[:3]]==[1,2,3]:
            out[k]={"trifecta":"-".join(str(x[1]) for x in rows[:3]),"pay":pay.get(k,0)}
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--date",required=True);a=ap.parse_args();d=a.date
    src=Path("predictions")/d[:4]/d[4:6]/d[6:8]/"live"/f"formation_predictions_final_{d}.json"
    payload=load(src); truth=actual(d)
    total=bucket(); by_points=defaultdict(bucket); by_stage=defaultdict(bucket); details=[]
    for race in payload.get("races") or []:
        t=truth.get(rid(race.get("race_id"))); ai=race.get("ai_score_prediction") or {}
        combos=ai.get("combinations") or []
        if not t or not combos: continue
        names=[text(x.get("combination")) if isinstance(x,dict) else text(x) for x in combos]
        pts=len(names); hit=int(t["trifecta"] in names); ret=t["pay"] if hit else 0
        stage=text(race.get("prediction_type")) or "不明"
        add(total,hit,pts,ret);add(by_points[str(pts)],hit,pts,ret);add(by_stage[stage],hit,pts,ret)
        all120=ai.get("all_120_combinations") or []
        actual_rank=next((i for i,x in enumerate(all120,1) if text(x.get("combination"))==t["trifecta"]),None)
        details.append({"race_id":race.get("race_id"),"venue_name":race.get("venue_name"),"race":race.get("race"),
          "prediction_type":stage,"points":pts,"actual_trifecta":t["trifecta"],"actual_combo_rank_120":actual_rank,
          "hit":hit,"top3_match":top3_match,"exact_match":exact_match,"investment":pts*BET,"trifecta_payout_100yen":t["pay"],"return":ret,"profit":ret-pts*BET,
          "combinations":" / ".join(names)})
    result={"model_version":"ai_finish_order_score_v0_20261005","strategy":"ai_score_prediction","100yen_per_combination":True,
      "overall":summary(total),"by_points":{k:summary(v) for k,v in sorted(by_points.items(),key=lambda x:int(x[0]))},
      "by_prediction_type":{k:summary(v) for k,v in by_stage.items()},"details":details}
    out=Path("evaluations")/d[:4]/d[4:6]/d[6:8];out.mkdir(parents=True,exist_ok=True)
    p=out/f"ai_score_simulation_{d}.json";p.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    cp=out/f"ai_score_simulation_{d}.csv"
    fields=list(details[0].keys()) if details else ["race_id","prediction_type","points","actual_trifecta","actual_combo_rank_120","hit","investment","return","profit"]
    with cp.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for row in details:w.writerow(row)
    print("AIスコア予測評価: PASS",len(details),"R");print(p)
if __name__=="__main__": main()
