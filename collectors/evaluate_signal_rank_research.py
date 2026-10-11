#!/usr/bin/env python3
"""Research-only, reproducible 120-combination rank-attribution PDCA.

Prediction -> all candidate rankings -> frozen top-24 tickets -> attach results.
Historical original signals/purchases, normal AI, and adopted signal weights
are NEVER written or modified by this program.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter
from pathlib import Path

from build_latest_prediction_view import (
    SIGNAL_LOGIC, build_down_signal, build_signal_ai_prediction, build_up_signal,
    load_signal_ai_config, signal_field_is_verified,
)
from evaluate_raijin_all_rank_replay import official_results
from evaluate_signal_ai_performance import _signal_inputs, load_live
from evaluate_down_signal import verified_signal_quality_by_race

CONFIG_PATH = Path("config/research/signal_rank_diagnostic_v1_20261011.json")
REPLAY = Path("evaluations/raijin_all_rank_v2_replay/details.csv")
FIELDS = (
    "date", "race_id", "venue", "race", "provenance", "signal_key",
    "fujin_level", "raijin_level", "actual", "payout", "split",
    "combination_count", "rank_morning", "rank_live", "rank_signal",
    "score_morning", "score_live", "score_signal",
    "change_exhibition", "change_signal", "change_total",
    "rank_uplift_exhibition", "rank_uplift_signal", "rank_uplift_total",
    "source_vs_signal", "method_ranks", "baseline_hit24",
)
COMBO_FIELDS = (
    "date", "race_id", "signal_key", "provenance", "combination",
    "score_morning", "score_live", "score_signal",
    "change_exhibition", "change_signal", "change_total",
    "rank_morning", "rank_live", "rank_signal",
    "rank_uplift_exhibition", "rank_uplift_signal", "rank_uplift_total",
    "is_actual", "baseline_top24",
)
BINS = ((1,6), (7,12), (13,18), (19,24), (25,36),
        (37,48), (49,60), (61,80), (81,120))


def load_csv(path):
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def pct(numerator, denominator):
    return round(100.0 * numerator / denominator, 2) if denominator else None


def split_date(date, config):
    split = config["split"]
    if date <= split["train_end"]:
        return "train_exploratory"
    if date <= split["validation_end"]:
        return "validation_exploratory"
    if date <= split["historical_check_end"]:
        return "historical_check_not_unseen"
    return "prospective_after_freeze"


def score_rows(boats, score_by_boat, weights):
    """Exactly the ordinary 0.50/0.30/0.20 combo score, pre-result."""
    from itertools import permutations
    scores = []
    for a, b, c in permutations(sorted(score_by_boat), 3):
        s = (score_by_boat[a] * weights["first"]
             + score_by_boat[b] * weights["second"]
             + score_by_boat[c] * weights["third"])
        scores.append({"combination": f"{a}-{b}-{c}", "score": round(s, 3)})
    return sorted(scores, key=lambda x: (-x["score"], x["combination"]))


def prepare_matrix(boats, up_signal, down_signal, signal_config, research_config):
    """PURE prediction branch: not supplied race result or payout."""
    if not (up_signal["level"] or down_signal["level"]):
        return None
    adjusted = build_signal_ai_prediction(boats, up_signal, down_signal, signal_config)
    if adjusted is None:
        raise RuntimeError("Signal active but 24-ticket model missing")
    weights = research_config["score_weighting"]
    morning = score_rows(
        boats, {int(b["boat"]): float(b["morning_score_reference"]) for b in boats},
        weights
    )
    live = score_rows(
        boats, {int(b["boat"]): float(b["score"]) for b in boats}, weights
    )
    signal = adjusted["all_120_combinations"]
    expected = len(boats) * (len(boats)-1) * (len(boats)-2)
    for name, source in (("morning",morning), ("live",live), ("signal",signal)):
        if len(source) != expected or len({x["combination"] for x in source}) != expected:
            raise RuntimeError(f"120/60 distinct combinations violation: {name}")
    by_morning = {x["combination"]: x for x in morning}
    by_live = {x["combination"]: x for x in live}
    by_signal = {x["combination"]: x for x in signal}
    if set(by_morning) != set(by_live) or set(by_live) != set(by_signal):
        raise RuntimeError("Three evaluation stages have different boats/combos")
    mr = {x["combination"]: i for i,x in enumerate(morning,1)}
    lr = {x["combination"]: i for i,x in enumerate(live,1)}
    sr = {x["combination"]: i for i,x in enumerate(signal,1)}
    matrix = []
    for combo in sorted(by_signal):
        a = by_morning[combo]["score"]
        b = by_live[combo]["score"]
        c = by_signal[combo]["score"]
        matrix.append({
            "combination": combo, "score_morning": a, "score_live": b,
            "score_signal": c,
            "change_exhibition": round(b-a,3),
            "change_signal": round(c-b,3),
            "change_total": round(c-a,3),
            "rank_morning": mr[combo], "rank_live": lr[combo],
            "rank_signal": sr[combo],
            "rank_uplift_exhibition": mr[combo]-lr[combo],
            "rank_uplift_signal": lr[combo]-sr[combo],
            "rank_uplift_total": mr[combo]-sr[combo],
        })
    methods = {}
    for name, method in research_config["methods"].items():
        kind = method["kind"]
        base = method.get("base")
        field = "change_total" if base == "morning" else "change_signal"
        if kind == "signal":
            sorted_matrix = sorted(matrix, key=lambda x: (x["rank_signal"], x["combination"]))
        elif kind == "delta":
            sorted_matrix = sorted(matrix, key=lambda x: (-x[field], x["combination"]))
        elif kind == "absolute":
            sorted_matrix = sorted(matrix, key=lambda x: (-abs(x[field]), x["combination"]))
        elif kind == "blend":
            weight = float(method["weight"])
            sorted_matrix = sorted(matrix, key=lambda x: (
                -(x["score_signal"] + weight*x[field]), x["combination"]
            ))
        elif kind == "shortlist":
            pool = int(method["pool"])
            if pool < int(research_config["purchase_points"]):
                raise RuntimeError("Shortlist cannot be smaller than the ticket count")
            sorted_matrix = sorted(matrix, key=lambda x: (
                int(x["rank_signal"] > pool),
                -x[field] if x["rank_signal"] <= pool else x["rank_signal"],
                -x["score_signal"], x["combination"],
            ))
        else:
            raise RuntimeError("Unknown research method: " + kind)
        methods[name] = {x["combination"]: i for i,x in enumerate(sorted_matrix,1)}
    production_top = {x["combination"] for x in adjusted["combinations"]}
    baseline_top = {x for x,r in methods["signal_score"].items()
                    if r <= research_config["purchase_points"]}
    if production_top != baseline_top or len(production_top) != 24:
        raise RuntimeError("Production signal 24 picks differ from research baseline")
    return matrix, methods


def settle_matrix(matrix, methods, actual, payout, race, split):
    """Only this function may use official outcomes."""
    matches = [x for x in matrix if x["combination"] == actual]
    if not matches:
        raise RuntimeError("Official outcome is outside the evaluated starters")
    x = matches[0]
    ranks = {name: ordered[actual] for name, ordered in methods.items()}
    summary = {
        **{k:race[k] for k in ("date","race_id","venue","race","provenance","signal_key",
                              "fujin_level","raijin_level")},
        "actual": actual, "payout": payout, "split": split,
        "combination_count": len(matrix),
        **{k:x[k] for k in (
            "rank_morning","rank_live","rank_signal",
            "score_morning","score_live","score_signal",
            "change_exhibition","change_signal","change_total",
            "rank_uplift_exhibition","rank_uplift_signal","rank_uplift_total"
        )},
        "source_vs_signal": (
            "signal_rescued_top24" if x["rank_live"] > 24 and x["rank_signal"] <= 24
            else "signal_lost_top24" if x["rank_live"] <= 24 and x["rank_signal"] > 24
            else "both_inside24" if x["rank_live"] <= 24 else "both_outside24"
        ),
        "method_ranks": ranks,
        "baseline_hit24": ranks["signal_score"] <= 24,
    }
    return summary


def statistics_for(rows, method):
    method_name = method
    n = len(rows)
    ranks = [r["method_ranks"][method_name] for r in rows]
    wins = [r for r in rows if r["method_ranks"][method_name] <= 24]
    rescued = sum(1 for r in rows if r["method_ranks"][method_name] <= 24
                  and not r["baseline_hit24"])
    lost = sum(1 for r in rows if r["method_ranks"][method_name] > 24
               and r["baseline_hit24"])
    returned = sum(r["payout"] for r in wins)
    invest = n * 2400
    high = [r for r in rows if r["payout"] >= 10000]
    return {
        "races": n, "hits24": len(wins), "hit24_pct": pct(len(wins),n),
        "investment_yen": invest, "returned_yen": returned,
        "profit_yen": returned-invest, "roi_pct": pct(returned,invest),
        "actual_rank_mean": round(statistics.mean(ranks),2) if ranks else None,
        "actual_rank_median": statistics.median(ranks) if ranks else None,
        "rescued_vs_baseline": rescued, "lost_vs_baseline": lost,
        "high_10000_races": len(high),
        "high_10000_hits24": sum(r["method_ranks"][method_name] <= 24 for r in high),
        "high_10000_hit_pct": pct(sum(r["method_ranks"][method_name] <= 24 for r in high),len(high)),
    }


def breakdown(rows, methods):
    return {k: statistics_for(rows,k) for k in methods}


def diagnostics(rows):
    def avg(field):
        return round(statistics.mean(r[field] for r in rows),2) if rows else None
    by_rank = {}
    for lo, hi in BINS:
        by_rank[f"{lo}-{hi}"] = sum(lo <= r["rank_signal"] <= hi for r in rows)
    states = Counter(r["source_vs_signal"] for r in rows)
    return {
        "actual_rank_distribution": by_rank,
        "avg_realized_morning_rank": avg("rank_morning"),
        "avg_realized_live_rank": avg("rank_live"),
        "avg_realized_signal_rank": avg("rank_signal"),
        "avg_rank_uplift_exhibition": avg("rank_uplift_exhibition"),
        "avg_rank_uplift_signal": avg("rank_uplift_signal"),
        "avg_score_change_exhibition": avg("change_exhibition"),
        "avg_score_change_signal": avg("change_signal"),
        "actual_top24_lost_due_to_signal": states["signal_lost_top24"],
        "actual_top24_rescued_by_signal": states["signal_rescued_top24"],
        "signal_lost_but_actual_was_high10000": sum(
            r["source_vs_signal"] == "signal_lost_top24" and r["payout"] >= 10000
            for r in rows
        ),
        "signal_rescued_and_actual_was_high10000": sum(
            r["source_vs_signal"] == "signal_rescued_top24" and r["payout"] >= 10000
            for r in rows
        ),
    }


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({
                k:(json.dumps(r[k],ensure_ascii=False,sort_keys=True)
                   if isinstance(r.get(k),(dict,list)) else r.get(k))
                for k in fields
            })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-date", default="20260930")
    parser.add_argument("--to-date", default="20991231")
    parser.add_argument("--output-dir", default="evaluations/signal_rank_research/v1")
    parser.add_argument("--no-combination-details", action="store_true")
    parser.add_argument("--strict-replay", action="store_true", default=True)
    args = parser.parse_args()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config["raijin_model_version"] != SIGNAL_LOGIC["model_version"]:
        raise RuntimeError("Fujin Raijin logic config differs from rank research schema")
    if not (config["research_only"] and config["no_production_prediction_changes"]):
        raise RuntimeError("Production mutation is disallowed")
    if config["purchase_points"] != 24:
        raise RuntimeError("Ranking research must use frozen 24 ticket comparison")
    weights = SIGNAL_LOGIC["scoring"]["combination_position_weights"]
    if config["score_weighting"] != weights:
        raise RuntimeError("AI combo weights drift from the production baseline")
    production_config = load_signal_ai_config()
    replay_index = {(r["date"],r["race_id"]):r for r in load_csv(REPLAY)}
    if args.strict_replay and not replay_index:
        raise RuntimeError("Full all-rank replay is required for baseline parity")
    days = sorted({
        path.stem.rsplit("_",1)[-1]
        for path in Path("predictions").glob(
            "20??/??/??/live/live_predictions_final_*.csv")
    })
    days = [d for d in days if args.from_date <= d <= args.to_date]
    if not days:
        raise RuntimeError("No archived live observation dates")

    out = Path(args.output_dir)
    race_rows = []
    skipped = []
    all_methods = tuple(config["methods"])
    for day in days:
        live = load_live(day)
        quality = verified_signal_quality_by_race(day)
        actuals = official_results(day)
        daily = []
        combo_details = []
        for rid, observed in sorted(live.items()):
            ranked = sorted(observed, key=lambda x:(
                int(float(x.get("rank") or 99)), int(float(x.get("boat") or 99))))
            boats = _signal_inputs(ranked)
            info = quality.get(rid) or {}
            if not signal_field_is_verified(boats,info):
                skipped.append({"date":day,"race_id":rid,"reason":"unverified_starters"})
                continue
            if any(b["score"] is None or b["morning_score_reference"] is None
                   for b in boats):
                skipped.append({"date":day,"race_id":rid,"reason":"missing_morning_or_live_score"})
                continue
            down = build_down_signal(boats,info)
            up = build_up_signal(boats,info,outside_live_top3=False)
            if not down["available"] or not up["available"]:
                skipped.append({"date":day,"race_id":rid,"reason":"signal_not_observable"})
                continue
            key = f'F{int(down["level"])}R{int(up["level"])}'
            replay = replay_index.get((day,rid))
            if args.strict_replay:
                if replay is None:
                    raise RuntimeError(f"No comparable replay for {day} {rid}")
                if (int(replay["fujin_level"]) != int(down["level"]) or
                    int(replay["new_raijin_level"]) != int(up["level"])):
                    raise RuntimeError(f"Different corrected signal level {day} {rid}")
                if (replay["new_active"] == "True") != (key != "F0R0"):
                    raise RuntimeError(f"Different corrected signal trigger {day} {rid}")
            if key == "F0R0":
                continue
            matrix_methods = prepare_matrix(boats,up,down,production_config,config)
            if matrix_methods is None:
                raise RuntimeError(f"Signal active with missing prediction {rid}")
            matrix, methods = matrix_methods
            truth = actuals.get(rid) or {}
            actual = truth.get("actual")
            if not actual:
                skipped.append({"date":day,"race_id":rid,"reason":"result_pending"})
                continue
            provenance = info.get("provenance") or "saved_csv_unclassified"
            race = {
                "date":day, "race_id":rid,
                "venue": ranked[0].get("venue_name"),
                "race": ranked[0].get("race"),
                "provenance":provenance, "signal_key":key,
                "fujin_level":int(down["level"]),
                "raijin_level":int(up["level"])
            }
            result = settle_matrix(matrix,methods,actual,int(truth["payout"]),race,
                                   split_date(day,config))
            if args.strict_replay:
                try:
                    expected_rank = int(replay["new_actual_rank"])
                except (ValueError,TypeError):
                    raise RuntimeError(f"Missing saved 120-rank {day} {rid}")
                expected_hit = replay["new_hit24"] == "True"
                if (result["rank_signal"] != expected_rank or
                    result["baseline_hit24"] != expected_hit):
                    raise RuntimeError(
                        f"V2 production baseline parity failed {day} {rid}: "
                        f"{result['rank_signal']} != {expected_rank}"
                    )
            daily.append(result)
            race_rows.append(result)
            if not args.no_combination_details:
                for combo in matrix:
                    combo_details.append({
                        **{k:race[k] for k in ("date","race_id","signal_key","provenance")},
                        **combo, "is_actual":combo["combination"] == actual,
                        "baseline_top24":combo["rank_signal"] <= 24,
                    })
        day_dir = out / "daily" / day
        day_dir.mkdir(parents=True, exist_ok=True)
        day_summary = {
            "date":day, "research_model":config["model_version"],
            "signal_logic_model":SIGNAL_LOGIC["model_version"],
            "finished_signal_races":len(daily),
            "by_method":breakdown(daily, all_methods),
            "diagnostic":diagnostics(daily),
            "high_dividend_by_method":breakdown(
                [r for r in daily if r["payout"] >= 10000],all_methods),
        }
        (day_dir / "summary.json").write_text(
            json.dumps(day_summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
        )
        if not args.no_combination_details:
            write_csv(day_dir / "all_combinations.csv",combo_details,COMBO_FIELDS)

    if args.strict_replay:
        expected = [
            r for (date,_),r in replay_index.items()
            if args.from_date <= date <= args.to_date
            and r["new_active"] == "True" and r["actual"]
        ]
        if len(expected) != len(race_rows):
            raise RuntimeError(f"Research/replay race denominator drift: "
                               f"{len(race_rows)} != {len(expected)}")

    dates = sorted({r["date"] for r in race_rows})
    grouped = {
        "by_date":{
            d:{"races":sum(r["date"] == d for r in race_rows),
               "by_method":breakdown([r for r in race_rows if r["date"]==d], all_methods)}
            for d in dates
        },
        "by_split":{
            s:{"races":sum(r["split"]==s for r in race_rows),
               "by_method":breakdown([r for r in race_rows if r["split"]==s],all_methods),
               "diagnostic":diagnostics([r for r in race_rows if r["split"]==s])}
            for s in ("train_exploratory","validation_exploratory",
                      "historical_check_not_unseen","prospective_after_freeze")
        },
        "by_payout":{
            band:{"races":sum(test(r) for r in race_rows),
                  "by_method":breakdown([r for r in race_rows if test(r)],all_methods),
                  "diagnostic":diagnostics([r for r in race_rows if test(r)])}
            for band,test in {
                "under5000":lambda r:r["payout"]<5000,
                "5000_9999":lambda r:5000<=r["payout"]<10000,
                "10000_plus":lambda r:r["payout"]>=10000,
            }.items()
        },
        "by_signal":{
            f"F{f}R{r}":{
                "races":sum(x["signal_key"]==f"F{f}R{r}" for x in race_rows),
                "by_method":breakdown([x for x in race_rows if x["signal_key"]==f"F{f}R{r}"],all_methods),
                "diagnostic":diagnostics([x for x in race_rows if x["signal_key"]==f"F{f}R{r}"]),
            } for f in range(4) for r in range(4)
        },
    }
    summary = {
        "model_version":config["model_version"],
        "baseline_model_version":SIGNAL_LOGIC["model_version"],
        "status":"RESEARCH_ONLY",
        "no_production_prediction_changes":True,
        "result_as_scoring_input":False,
        "baseline_full_replay_verified":bool(args.strict_replay),
        "real_bets_preserved":True,
        "sample_dates":days,
        "finished_signal_races":len(race_rows),
        "excluded_or_pending_rows":skipped,
        "methods":{k:v["description"] for k,v in config["methods"].items()},
        "overall":{"by_method":breakdown(race_rows,all_methods),
                   "diagnostic":diagnostics(race_rows)},
        "rolling7":{
            "dates":days[-7:],
            "by_method":breakdown([r for r in race_rows if r["date"] in days[-7:]],all_methods)
        },
        "comparisons":grouped,
        "unseen_holdout_warning":config["holdout_notice"],
        "scientific_limitation":"Observed data and candidate definitions predate this freeze; historic 'validation' is not a truly untouched forward test.",
    }
    out.mkdir(parents=True,exist_ok=True)
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    write_csv(out/"race_diagnostics.csv",race_rows,FIELDS)
    (out/"skipped.json").write_text(json.dumps(skipped,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SIGNAL_RANK_DIAGNOSTIC",json.dumps({
        "days":len(days), "finished_signal_races":len(race_rows),
        "baseline":summary["overall"]["by_method"]["signal_score"],
        "diagnostic":summary["overall"]["diagnostic"],
        "not_mutating_bets":True,
    },ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
