#!/usr/bin/env python3
"""Independent research hypotheses: score, signals and ordered trifecta tickets.
Never writes production predictions. Official results are joined after picks.
"""
from __future__ import annotations
import argparse
import csv
import itertools
import json
import math
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

CFG = Path("config/research/chatgpt_independent_strategy_v1.json")
OUT = Path("evaluations/chatgpt_independent_pdca")
CUTS = (6, 8, 12)

def read(path):
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def n(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None

def rid(v):
    digits = re.sub(r"\D", "", str(v or ""))
    return digits[:12] if len(digits) >= 12 else ""

def rate(a, b):
    return round(100*a/b, 2) if b else None

def propose(boats, morning, race_id, conf, *, baseline=False):
    pars = conf["score_formula"]
    w = 0 if baseline else pars["morning_weight"]
    tw = 0 if baseline else pars["exhibition_time_z_points"]
    valid = [n(x.get("exhibition_time")) for x in boats]
    valid = [t for t in valid if t is not None and 0<t<12]
    mean = sum(valid)/len(valid) if valid else None
    sd = max(.05, math.sqrt(sum((t-mean)**2 for t in valid)/len(valid))) if valid else None
    board = []
    for boat in boats:
        b = int(boat["boat"])
        M, L = morning[(race_id, b)], n(boat["score"])
        tm = n(boat.get("exhibition_time"))
        z = max(-2,min(2,(mean-tm)/sd)) if mean is not None and tm is not None and 0<tm<12 else 0
        board.append({"boat":b, "morning":M, "live":L, "exhibition_time":tm,
                      "exhibition_bonus":round(z*tw,3),
                      "score":w*M+(1-w)*L+z*tw,
                      "course":n(boat.get("exhibition_course")),
                      "exhibition_f":str(boat.get("exhibition_f")).lower() in ("true","1")})
    board.sort(key=lambda b:(-b["score"], b["boat"]))
    scale = conf["plackett_luce_temperature"]
    peak = max(b["score"] for b in board)
    weights = {b["boat"]:math.exp((b["score"]-peak)/scale) for b in board}
    total = sum(weights.values())
    tickets = []
    for a,b,c in itertools.permutations(weights,3):
        prob = (weights[a]/total * weights[b]/(total-weights[a])
                * weights[c]/(total-weights[a]-weights[b]))
        tickets.append((prob,f"{a}-{b}-{c}"))
    tickets.sort(key=lambda x:(-x[0],x[1]))
    if baseline:
        return board, "baseline", [t[1] for t in tickets]
    morning_first = max(board, key=lambda x:(x["morning"],-x["boat"]))["boat"]
    b0,b1 = board[:2]
    sr = conf["signal_rules"]
    if (b0["boat"]==morning_first and b0["score"]-b1["score"]>=sr["consensus_gap_min"]
        and b0["course"] is not None and 1<=b0["course"]<=3 and not b0["exhibition_f"]):
        signal = "consensus_axis"
    elif (b0["boat"]!=morning_first and b0["live"]-b0["morning"]>=sr["upset_live_lift_min"]):
        signal = "upset_watch"
    else:
        signal = "neutral_or_uncertain"
    return board, signal, [t[1] for t in tickets]

def day_rows(day, conf):
    path = Path(f"predictions/{day[:4]}/{day[4:6]}/{day[6:8]}")
    eval_dir = Path(f"evaluations/{day[:4]}/{day[4:6]}/{day[6:8]}")
    results = read(Path(f"archive/{day[:4]}/{day[4:6]}/{day[6:8]}/results_{day}_all.csv"))
    morning_csv = read(path/f"morning_predictions_{day}.csv")
    original = read(path/"live"/f"live_predictions_final_{day}.csv")
    merged = read(eval_dir/"recovery"/f"merged_live_predictions_{day}.csv")
    issues = Counter()
    if not (morning_csv and results and (original or merged)):
        return [],{"official":len(results),"included":0,"excluded":{"missing_source":len(results)}}
    morning = {}
    for r in morning_csv:
        b = int(n(r.get("boat")) or 0)
        morning[(rid(r.get("race_id")), b)] = n(r.get("score"))
    by_boat = {}
    for r in original + merged:
        b = int(n(r.get("boat")) or 0)
        if rid(r.get("race_id")) and 1<=b<=6:
            by_boat[(rid(r["race_id"]), b)] = r
    by_race = defaultdict(list)
    for (race_id,boat),row in by_boat.items():
        by_race[race_id].append(row)
    recovered = set()
    audit_path=eval_dir/"data_quality"/f"completeness_{day}.json"
    if audit_path.is_file():
        audit=json.loads(audit_path.read_text(encoding="utf-8"))
        recovered={rid(x.get("race_id")) for x in audit.get("recovered_after_result",[])}
    out = []
    for actual in results:
        race_id=rid(actual.get("race_id"))
        ordered=str(actual.get("trifecta") or "").replace("=","-")
        parts=ordered.split("-")
        payout=n(actual.get("trifecta_pay"))
        boats=by_race.get(race_id,[])
        if (not race_id or len(parts)!=3 or any(x not in tuple(str(j) for j in range(1,7)) for x in parts)
            or len(set(parts))!=3 or payout is None or payout<0):
            issues["invalid_official_outcome"]+=1;continue
        if (len(boats) not in (5,6) or len(set(int(x["boat"]) for x in boats))!=len(boats)
            or not set(parts).issubset({x["boat"] for x in boats})):
            issues["starter_identity_incomplete"]+=1;continue
        if any(n(x.get("score")) is None or morning.get((race_id,int(x["boat"]))) is None for x in boats):
            issues["missing_scores"]+=1;continue
        # Ticket creation has no access to actual finishes or payouts.
        ranked,signal,tickets=propose(boats,morning,race_id,conf)
        base,_,base_tickets=propose(boats,morning,race_id,conf,baseline=True)
        pred=[str(x["boat"]) for x in ranked[:3]]
        row={"date":day,"race_id":race_id,"provenance":"post_result_retry" if race_id in recovered else "saved_timing_unverified",
             "signal":signal,"observed_starters":len(boats),
             "score_evidence":[{k:x[k] for k in ("boat","morning","live","exhibition_time","exhibition_bonus","score")} for x in ranked],
             "proposed_top3":pred,"actual":ordered,"payout_yen":int(payout),
             "first_hit":int(pred[0]==parts[0]),"winner_top3":int(parts[0] in pred),
             "top3_set_hit":int(set(pred)==set(parts)),"exact_hit":int(pred==parts),
             "baseline_first_hit":int(str(base[0]["boat"])==parts[0]),
             "baseline_top3_set_hit":int({str(x["boat"]) for x in base[:3]}==set(parts))}
        for typ, ranked_tickets in (("proposed",tickets),("baseline",base_tickets)):
            for points in CUTS:
                key=f"{typ}{points}"
                chosen=ranked_tickets[:points]
                row[key+"_tickets"]=chosen
                row[key+"_hit"]=int(ordered in chosen)
                row[key+"_stake"]=points*100
                row[key+"_return"]=int(payout) if ordered in chosen else 0
        points=6 if signal=="consensus_axis" else 12 if signal=="upset_watch" else 8
        row["adaptive_points"]=points
        for k,v in (("tickets",row[f"proposed{points}_tickets"]),("hit",row[f"proposed{points}_hit"]),
                    ("stake",row[f"proposed{points}_stake"]),("return",row[f"proposed{points}_return"])):
            row["adaptive_"+k]=v
        out.append(row)
    return out, {"official":len(results),"included":len(out),"excluded":dict(issues),
                 "post_result_reconstructed":sum(x["provenance"]=="post_result_retry" for x in out),
                 "five_starter_races":sum(x["observed_starters"]==5 for x in out)}

def summarize(records):
    def bet(rows,key):
        total=len(rows)
        hits=sum(x[key+"_hit"] for x in rows)
        invest=sum(x[key+"_stake"] for x in rows)
        returns=sum(x[key+"_return"] for x in rows)
        payouts=sorted((x[key+"_return"] for x in rows if x[key+"_hit"]),reverse=True)
        return {"races":total,"hits":hits,"hit_pct":rate(hits,total),
                "invested":invest,"returned":returns,"profit":returns-invest,"roi_pct":rate(returns,invest),
                "biggest_win_yen":payouts[0] if payouts else 0,
                "roi_excluding_biggest_win_pct":rate(returns-(payouts[0] if payouts else 0),invest)}
    cnt=len(records)
    signal_names=("consensus_axis","upset_watch","neutral_or_uncertain")
    return {"races":cnt,"first_pct":rate(sum(x["first_hit"] for x in records),cnt),
            "winner_in_top3_pct":rate(sum(x["winner_top3"] for x in records),cnt),
            "top3_set_pct":rate(sum(x["top3_set_hit"] for x in records),cnt),
            "exact_pct":rate(sum(x["exact_hit"] for x in records),cnt),
            "baseline_first_pct":rate(sum(x["baseline_first_hit"] for x in records),cnt),
            "baseline_top3_set_pct":rate(sum(x["baseline_top3_set_hit"] for x in records),cnt),
            "proposed_tickets":{str(p):bet(records,f"proposed{p}") for p in CUTS},
            "baseline_tickets":{str(p):bet(records,f"baseline{p}") for p in CUTS},
            "adaptive":bet(records,"adaptive"),
            "signals":{s:{"count":sum(x["signal"]==s for x in records),
                         "fixed8":bet([x for x in records if x["signal"]==s],"proposed8"),
                         "adaptive":bet([x for x in records if x["signal"]==s],"adaptive")} for s in signal_names}}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--date",required=True)
    args=parser.parse_args()
    target=args.date
    cfg=json.loads(CFG.read_text(encoding="utf-8"))
    dates=[]
    for p in Path("archive").glob("20??/??/??/results_????????_all.csv"):
        found=re.fullmatch(r"results_(\d{8})_all",p.stem)
        if found and found.group(1)<=target:
            dates.append(found.group(1))
    dates=sorted(set(dates))
    all_rows=[];quality={};daily={}
    for d in dates:
        observed,q=day_rows(d,cfg)
        if observed:
            all_rows+=observed;quality[d]=q;daily[d]=summarize(observed)
    if target not in daily:
        raise SystemExit(f"No independently evaluable races on {target}")
    dt=date(int(target[:4]),int(target[4:6]),int(target[6:8]))
    last7={(dt-timedelta(days=x)).strftime("%Y%m%d") for x in range(7)}
    today=[x for x in all_rows if x["date"]==target]
    history=[x for x in all_rows if x["date"]<target]
    rolling=[x for x in all_rows if x["date"] in last7]
    data={"model_version":cfg["model_version"],"hypothesis_frozen_on":cfg["hypothesis_frozen_on"],
          "research_only":True,"historical_paper_bets_only":True,"never_modify_production":True,
          "prediction_inputs_have_no_official_outcomes":True,
          "pre_deadline_availability_not_verified":True,
          "not_a_calibrated_expected_value_model":True,
          "formula":cfg["score_formula"],"signal_rules":cfg["signal_rules"],
          "date":target,"quality":quality,"daily":daily,
          "latest_day":summarize(today),"training_prior_days":summarize(history),
          "rolling7":summarize(rolling),"cumulative":summarize(all_rows)}
    out=OUT/"daily"/target
    out.mkdir(parents=True,exist_ok=True)
    (out/"summary.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"latest.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    with (out/"race_evidence.jsonl").open("w",encoding="utf-8") as f:
        for row in today:
            f.write(json.dumps(row,ensure_ascii=False)+"\n")
    z=data["latest_day"]
    lines=[f"# ChatGPT独自ロジック・シグナル・買い目 PDCA {target}",
           "", "**研究用仮説。的中・購入は紙上再現であり、本番ロジック・実際の購入を変更しない。**",
           "", "## 独自スコアと確率付け",
           f"朝×{cfg['score_formula']['morning_weight']}＋直前×{1-cfg['score_formula']['morning_weight']}＋展示タイム相対z×{cfg['score_formula']['exhibition_time_z_points']}。zは±2以内。",
           "三連単候補はPlackett–Luce型で1着→2着→3着を重複なしで確率順に並べる。",
           "",f"公式{quality[target]['official']}R、評価{quality[target]['included']}R。除外内訳 {quality[target]['excluded']}。",
           f"1着 {z['first_pct']}%、勝者TOP3 {z['winner_in_top3_pct']}%、TOP3集合 {z['top3_set_pct']}%、完全一致 {z['exact_pct']}%。",
           "", "| 買い目・100円均等 | R数 | 的中 | ROI |","|---|---:|---:|---:|"]
    for p in CUTS:
        b=z["proposed_tickets"][str(p)]
        lines.append(f"| 独自上位{p}点 | {b['races']} | {b['hits']} | {b['roi_pct']}% |")
    for label,b in (("独自条件分岐6/8/12",z["adaptive"]),("既存直前スコアPL上位8点",z["baseline_tickets"]["8"])):
        lines.append(f"| {label} | {b['races']} | {b['hits']} | {b['roi_pct']}% |")
    lines+=["", "## 独自シグナルと条件分岐の根拠",
            "合意強軸：朝1位と独自1位一致、差8点以上、展示進入1～3、展示Fなし → 6点研究。",
            "穴浮上：独自1位が朝1位でなく、直前スコアが朝より5点以上上昇 → 12点研究。",
            "その他 → 8点研究。いずれも**採用済みの購入シグナルではない**。",
            "", "| 区分 | R数 | 8点的中 | 8点ROI | 条件分岐ROI |","|---|---:|---:|---:|---:|"]
    for s,b in z["signals"].items():
        lines.append(f"| {s} | {b['count']} | {b['fixed8']['hits']} | {b['fixed8']['roi_pct']}% | {b['adaptive']['roi_pct']}% |")
    improved=sorted((x for x in today if x["proposed8_hit"] and not x["baseline8_hit"]),
                    key=lambda x:(-x["payout_yen"],x["race_id"]))
    worsened=sorted((x for x in today if x["baseline8_hit"] and not x["proposed8_hit"]),
                    key=lambda x:(-x["payout_yen"],x["race_id"]))
    lines+=["", "## 同一レースでの改善・悪化（反証も省略しない）",
            f"独自8点のみ的中 {len(improved)}R、既存直前スコアPL8点のみ的中 {len(worsened)}R。"]
    for label,examples in (("独自案のみ的中",improved[:3]),("独自案のみ外れ",worsened[:3])):
        for x in examples:
            boat=x["score_evidence"][0]
            lines.append(f"- {label}：{x['race_id']} 実着{x['actual']}／公式払戻{x['payout_yen']}円。"
                         f"独自上位艇{boat['boat']}号艇：朝{boat['morning']:.2f}点、直前{boat['live']:.2f}点、"
                         f"展示タイム補正{boat['exhibition_bonus']:+.2f}点、独自総合{boat['score']:.2f}点。"
                         f"上位8点 {', '.join(x['proposed8_tickets'])}。")
    lines+=["",f"独自上位8点で最大の的中払戻1件を除いた場合のROI：{z['proposed_tickets']['8']['roi_excluding_biggest_win_pct']}%。",
            "※ 最大払戻を除外しても投資総額は同一とした感応度分析。", "",
            "## 公式保存結果と予測の出典",
            f"- https://github.com/lifeworks5783-gif/-boatrace-ai/blob/main/archive/{target[:4]}/{target[4:6]}/{target[6:8]}/results_{target}_all.csv",
            f"- https://github.com/lifeworks5783-gif/-boatrace-ai/blob/main/predictions/{target[:4]}/{target[4:6]}/{target[6:8]}/morning_predictions_{target}.csv",
            f"- https://github.com/lifeworks5783-gif/-boatrace-ai/blob/main/evaluations/{target[:4]}/{target[4:6]}/{target[6:8]}/recovery/merged_live_predictions_{target}.csv"]
    lines+=["", f"直近7日上位8点ROI：{data['rolling7']['proposed_tickets']['8']['roi_pct']}%。",
            f"保存期間全体上位8点ROI：{data['cumulative']['proposed_tickets']['8']['roi_pct']}%。",
            "前日以前・当日を分離。同日最適化なし。ただし検証者が当日結果を既に知っている場合、真の未知データ検証ではない。",
            "", "## 実レースごとの検証根拠",
            f"各艇の朝・直前・展示差による加点、シグナル、全買い目、実着、払戻、的中・外れを daily/{target}/race_evidence.jsonl に記録。",
            "", "## 判定・次の行動",
            "継続検証（本番不採用）。締切前オッズがないため期待値の正当化は未実施。",
            "独立した翌日以降の結果で最低7日、採点要素の単体効果、購入点数の副作用、高額配当依存、ROIと信頼区間を確認する。",
            "改善候補が出ても本番への反映はユーザーの明示的な判断後のみ。",""]
    (out/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    print("CHATGPT_INDEPENDENT_PDCA",target,"evaluated",len(today),
          "ROI8",z["proposed_tickets"]["8"]["roi_pct"])

if __name__ == "__main__":
    main()
