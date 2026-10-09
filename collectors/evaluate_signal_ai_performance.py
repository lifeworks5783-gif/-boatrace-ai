#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

from evaluate_down_signal import verified_signal_quality_by_race
from build_latest_prediction_view import signal_field_is_verified

CONFIG = Path("config/signal_ai/signal_ai_corrections_v1_20261008.json")
BACKTEST = Path("evaluations/fujin_raijin/latest/backtest_details.csv")
OUT = Path("evaluations/signal_ai/latest")


def fnum(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def inum(v, default=None):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def norm_race_id(v):
    digits = "".join(ch for ch in str(v or "") if ch.isdigit())
    return digits[:12] if len(digits) >= 12 else digits


def load_csv(path):
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_live(date):
    y,m,d=date[:4],date[4:6],date[6:8]
    candidates = [
        Path("predictions")/y/m/d/"live"/f"live_predictions_final_{date}.csv",
        Path("evaluations")/y/m/d/"recovery"/f"merged_live_predictions_{date}.csv",
    ]
    rows_by_key = {}
    for path in candidates:
        for row in load_csv(path):
            rid=norm_race_id(row.get("race_id"))
            boat=inum(row.get("boat"))
            if rid and boat is not None:
                rows_by_key[(rid,boat)] = row
    grouped=defaultdict(list)
    for (rid,_),row in rows_by_key.items():
        grouped[rid].append(row)
    return grouped


def _signal_inputs(ranked):
    """Normalize history CSV to the identical six-boat interface as live."""
    return [
        {
            **r,
            "boat": inum(r.get("boat")),
            "rank": index,
            "score": fnum(r.get("score")),
            "morning_score_reference": fnum(r.get("morning_score_reference")),
        }
        for index, r in enumerate(ranked, 1)
    ]


def derive_raijin(ranked, quality=None):
    from build_latest_prediction_view import build_up_signal
    saved = build_up_signal(_signal_inputs(ranked), quality)
    return int(saved.get("level") or 0), saved.get("candidates") or []


def derive_fujin(ranked, quality=None):
    from build_latest_prediction_view import build_down_signal
    saved = build_down_signal(_signal_inputs(ranked), quality)
    return int(saved.get("level") or 0)


def apply_rule(ranked, flevel, rlevel, rcands, config):
    # Backtesting uses the SAME frozen scoring function as actual predictions.
    # Result order and payout are never passed into this function.
    from build_latest_prediction_view import build_signal_ai_prediction
    model = build_signal_ai_prediction(
        _signal_inputs(ranked),
        {"level": rlevel, "candidates": rcands},
        {"level": flevel},
        config,
    )
    if not model:
        return None
    adjusted = {
        item["boat"]: item["signal_ai_score"]
        for item in model["signal_ai_ranking"]
    }
    combos = [
        (item["score"], item["combination"])
        for item in model["all_120_combinations"]
    ]
    return model["signal_key"], model["rule"], adjusted, combos


def empty_bucket():
    return {
        "races":0,"hits24":0,"return24":0,
        "p5000_total":0,"p5000_hits24":0,
        "manshu_total":0,"manshu_hits24":0,
        "p30000_total":0,"p30000_hits24":0,
        "actual_ranks":[],
        "rank_cut_hits":{6:0,8:0,12:0,18:0,24:0},
    }


def finalize(b):
    n=b["races"]; inv=n*2400
    def pct(a,d): return round(a*100/d,2) if d else None
    ranks=b["actual_ranks"]
    return {
        "races":n,
        "hits24":b["hits24"],
        "hit_rate24_pct":pct(b["hits24"],n),
        "investment24":inv,
        "return24":b["return24"],
        "profit24":b["return24"]-inv,
        "roi24_pct":pct(b["return24"],inv),
        "payout_5000plus":{"races":b["p5000_total"],"hits24":b["p5000_hits24"],"hit_rate24_pct":pct(b["p5000_hits24"],b["p5000_total"])},
        "manshu":{"races":b["manshu_total"],"hits24":b["manshu_hits24"],"hit_rate24_pct":pct(b["manshu_hits24"],b["manshu_total"])},
        "payout_30000plus":{"races":b["p30000_total"],"hits24":b["p30000_hits24"],"hit_rate24_pct":pct(b["p30000_hits24"],b["p30000_total"])},
        "actual_combo_rank":{"mean":round(sum(ranks)/len(ranks),2) if ranks else None,"median":round(statistics.median(ranks),2) if ranks else None},
        "rank_cut_hit_rate_pct":{str(k):pct(v,n) for k,v in b["rank_cut_hits"].items()},
    }


def rule_text(rule):
    f=rule.get("fujin"); r=rule.get("raijin"); parts=[]
    if f:
        parts.append(f"風神:{f.get('target')}/{f.get('mode')}/{f.get('strength')}×{f.get('level_profile')}")
    if r:
        parts.append(f"雷神:+rise×{r.get('multiplier')}×{r.get('level_profile')}×{r.get('rank_attenuation')}")
    return " / ".join(parts) if parts else "補正なし"


def main():
    config=json.loads(CONFIG.read_text(encoding="utf-8"))
    source=load_csv(BACKTEST)
    by_date=defaultdict(list)
    for row in source:
        by_date[str(row.get("date") or "")].append(row)

    groups=defaultdict(empty_bucket)
    overall=empty_bucket()
    details=[]
    skipped=[]

    quality_maps = {}
    for date,truth_rows in sorted(by_date.items()):
        live=load_live(date)
        quality_maps[date]=verified_signal_quality_by_race(date)
        for truth in truth_rows:
            rid=norm_race_id(truth.get("race_id"))
            rows=live.get(rid) or []
            ranked=sorted(rows,key=lambda x:(inum(x.get("rank"),99),inum(x.get("boat"),99)))
            quality=quality_maps[date].get(rid) or {}
            if not signal_field_is_verified(_signal_inputs(ranked), quality):
                skipped.append({"date":date,"race_id":rid,"reason":f"unverified_live_starters_{len(rows)}"})
                continue
            flevel=derive_fujin(ranked,quality)
            rlevel,rcands=derive_raijin(ranked,quality)
            if flevel<=0 and rlevel<=0:
                continue
            applied=apply_rule(ranked,flevel,rlevel,rcands,config)
            if not applied:
                skipped.append({"date":date,"race_id":rid,"reason":f"rule_missing_F{flevel}R{rlevel}"})
                continue
            key,rule,adjusted,combos=applied
            actual=f"{inum(truth.get('actual_winner') or truth.get('winner') or '')}-{inum(truth.get('actual_second') or '')}-{inum(truth.get('actual_third') or '')}"
            # backtest_details has no actual order; use fujin_deep row when available below
            if "None" in actual:
                actual=""
            payout=inum(truth.get("payout"),0) or 0
            details.append({"date":date,"race_id":rid,"signal_key":key,"payout":payout,"rule_text":rule_text(rule),"actual_trifecta":actual})

    # Enrich actual order from fujin_deep, which is the canonical saved result alignment.
    deep=load_csv(Path("evaluations/fujin_deep/latest/details.csv"))
    truth_map={norm_race_id(x.get("race_id")):x for x in deep}
    # fujin_deepは日次更新が遅れる場合がある。分析用の実着・払戻だけ、
    # 日別保存済み公式結果から補完する（予測スコアやシグナル判定には渡さない）。
    # 当日結果の答え合わせから漏れることを防ぐ。
    for date in sorted(by_date):
        archive = Path("archive") / date[:4] / date[4:6] / date[6:8] / f"results_{date}_all.csv"
        for actual_row in load_csv(archive):
            rid = norm_race_id(actual_row.get("race_id"))
            combo = str(actual_row.get("trifecta") or "").strip()
            parts = combo.split("-")
            if not rid or len(parts)!=3:
                continue
            boats = [inum(x) for x in parts]
            if any(x is None or x < 1 or x > 6 for x in boats) or len(set(boats))!=3:
                continue
            truth_map.setdefault(rid, {
                "race_id":rid,
                "actual_winner":boats[0],
                "actual_second":boats[1],
                "actual_third":boats[2],
                "payout":inum(actual_row.get("trifecta_pay"),0),
                "truth_source":"archived_official_result",
            })
    groups=defaultdict(empty_bucket); overall=empty_bucket(); final_details=[]
    for d in details:
        tr=truth_map.get(d["race_id"])
        if not tr:
            skipped.append({"date":d["date"],"race_id":d["race_id"],"reason":"actual_order_missing"})
            continue
        actual=f"{inum(tr.get('actual_winner'))}-{inum(tr.get('actual_second'))}-{inum(tr.get('actual_third'))}"
        date=d["date"]; live=load_live(date); ranked=sorted(live.get(d["race_id"]) or [],key=lambda x:(inum(x.get("rank"),99),inum(x.get("boat"),99)))
        quality=quality_maps.get(date,{}).get(d["race_id"]) or {}
        if not signal_field_is_verified(_signal_inputs(ranked), quality):
            skipped.append({"date":date,"race_id":d["race_id"],"reason":"canonical_official_starter_verification_changed"})
            continue
        fl=derive_fujin(ranked,quality); rl,rc=derive_raijin(ranked,quality); applied=apply_rule(ranked,fl,rl,rc,config)
        if not applied: continue
        key,rule,adjusted,combos=applied
        rank=next((i for i,(_,c) in enumerate(combos,1) if c==actual),None)
        if rank is None: continue
        payout=inum(tr.get("payout"),0) or 0
        for bucket in (overall,groups[key]):
            bucket["races"]+=1; bucket["actual_ranks"].append(rank)
            for cut in bucket["rank_cut_hits"]:
                if rank<=cut: bucket["rank_cut_hits"][cut]+=1
            if rank<=24:
                bucket["hits24"]+=1; bucket["return24"]+=payout
            if payout>=5000:
                bucket["p5000_total"]+=1
                if rank<=24: bucket["p5000_hits24"]+=1
            if payout>=10000:
                bucket["manshu_total"]+=1
                if rank<=24: bucket["manshu_hits24"]+=1
            if payout>=30000:
                bucket["p30000_total"]+=1
                if rank<=24: bucket["p30000_hits24"]+=1
        final_details.append({
            "date":date,"race_id":d["race_id"],"signal_key":key,
            "fujin_level":fl,"raijin_level":rl,"payout":payout,
            "actual_trifecta":actual,"actual_combo_rank":rank,
            "hit6":rank<=6,"hit8":rank<=8,"hit12":rank<=12,"hit18":rank<=18,"hit24":rank<=24,
            "rule_text":rule_text(rule),
        })

    summary={
        "schema_version":1,
        "model_version":config.get("model_version"),
        "effective_date":config.get("effective_date"),
        "normal_prediction_unchanged":True,
        "candidate_points":24,
        "decision_policy":config.get("decision_policy") or {"status":"learning","purchase_decision_active":False},
        "source_dates":sorted(by_date),
        "source_date_count":len(by_date),
        "evaluated_signal_races":overall["races"],
        "overall_if_all_signals_bought24":finalize(overall),
        "by_signal":{
            key:{
                "signal_key":key,
                "current_rule":(config.get("rules") or {}).get(key),
                "rule_text":rule_text((config.get("rules") or {}).get(key) or {}),
                **finalize(bucket),
            }
            for key,bucket in sorted(groups.items())
        },
        "skipped":skipped,
        "note":"現行シグナルAI補正で全シグナルを24点評価。買い/見送り判定はまだ学習中で、ROIは全該当レースを24点購入した仮定。",
    }

    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    fields=["date","race_id","signal_key","fujin_level","raijin_level","payout","actual_trifecta","actual_combo_rank","hit6","hit8","hit12","hit18","hit24","rule_text"]
    with (OUT/"details.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(final_details)
    print(json.dumps({"model":summary["model_version"],"dates":summary["source_date_count"],"signal_races":summary["evaluated_signal_races"],"overall":summary["overall_if_all_signals_bought24"],"skipped":len(skipped)},ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
