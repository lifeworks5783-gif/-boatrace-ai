#!/usr/bin/env python3
"""Research-only buy/skip PDCA with chronological, out-of-sample testing.

All decision inputs are limited to (Fujin level, Raijin level), which are
known before result settlement. The true trifecta rank and payout are
used only by the separate score/evaluate path, never the selection function.
Do NOT repurpose outcome-specific score_signal in race_diagnostics.csv for
race-level buy decisions; it describes the realized combination (leakage).
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from evaluate_signal_24_temporal_holdout import load_evidence

MODEL = "signal_buy_skip_holdout_v1_20261014"
STAKES_PER_RACE = 2400
MIN_TRAIN_PURCHASES = 120
MIN_TRAIN_COVERAGE = 0.40
MIN_ROI_UPLIFT_PTS = 10.0
MAX_HIT_RATE_LOSS_PTS = 10.0


def f_r(signal):
    if len(signal) != 4 or signal[0] != "F" or signal[2] != "R":
        raise ValueError("Unknown signal: " + signal)
    return int(signal[1]), int(signal[3])


# Predeclared mutually comparable hypotheses, not tuned against holdout.
POLICIES = {
    "all_signal": lambda f, r: f + r > 0,
    "fujin_any": lambda f, r: f >= 1,
    "raijin_any": lambda f, r: r >= 1,
    "strong_any": lambda f, r: f >= 2 or r >= 2,
    "sum_ge2": lambda f, r: f + r >= 2,
    "sum_ge3": lambda f, r: f + r >= 3,
    "sum_ge4": lambda f, r: f + r >= 4,
    "fujin_and_raijin": lambda f, r: f >= 1 and r >= 1,
    "fujin_only": lambda f, r: f >= 1 and r == 0,
    "raijin_only": lambda f, r: f == 0 and r >= 1,
    "exclude_F0R3": lambda f, r: f != 0 or r != 3,
    "exclude_R3": lambda f, r: r != 3,
    "exclude_F0R2": lambda f, r: f != 0 or r != 2,
    "exclude_F0R1": lambda f, r: f != 0 or r != 1,
}
assert len(POLICIES) == 14


def should_buy(signal, policy):
    """The PURE eligibility function; no actual rank, payout, or date input."""
    f, r = f_r(signal)
    if f + r == 0:
        return False
    return bool(POLICIES[policy](f, r))


def metrics(pool, policy):
    """Simulated top-24, ¥100 each; avoided stakes have no fictitious returns."""
    active = [x for x in pool if x["active"]]
    kept = [r for r in active if should_buy(r["signal"], policy)]
    skipped = [r for r in active if not should_buy(r["signal"], policy)]
    won = [r for r in kept if 1 <= r["rank"] <= 24]
    avoided_winners = [r for r in skipped if 1 <= r["rank"] <= 24]
    investment = len(kept) * STAKES_PER_RACE
    returned = sum(r["payout"] for r in won)
    return {
        "eligible_races": len(active),
        "purchased_races": len(kept), "skipped_races": len(skipped),
        "purchase_rate_pct": round(100 * len(kept) / len(active), 2) if active else None,
        "wins24": len(won),
        "hit_rate_pct": round(100 * len(won) / len(kept), 2) if kept else None,
        "purchased_payout_ge5000_races": sum(r["payout"] >= 5000 for r in kept),
        "purchased_payout_ge10000_races": sum(r["payout"] >= 10000 for r in kept),
        "high5_wins": sum(r["payout"] >= 5000 for r in won),
        "manshu_wins": sum(r["payout"] >= 10000 for r in won),
        "skipped_wins24": len(avoided_winners),
        "skipped_wins24_return_yen": sum(r["payout"] for r in avoided_winners),
        "skipped_payout_ge5000_races": sum(r["payout"] >= 5000 for r in skipped),
        "skipped_payout_ge10000_races": sum(r["payout"] >= 10000 for r in skipped),
        "avoided_stakes_yen": len(skipped) * STAKES_PER_RACE,
        "investment_yen": investment, "return_yen": returned,
        "profit_yen": returned - investment,
        "roi_pct": round(100 * returned / investment, 2) if investment else None,
    }


def choose_policy(training):
    """Training-only policy lock; never inspect validation/holdout outcomes."""
    if not training:
        raise ValueError("No signal-on training records")
    base = metrics(training, "all_signal")
    eligible = base["eligible_races"]
    min_buys = max(MIN_TRAIN_PURCHASES, math.ceil(eligible * MIN_TRAIN_COVERAGE))
    accepted = []
    for name in POLICIES:
        if name == "all_signal":
            continue
        m = metrics(training, name)
        if m["purchased_races"] < min_buys:
            continue
        if m["roi_pct"] < base["roi_pct"] + MIN_ROI_UPLIFT_PTS:
            continue
        if m["hit_rate_pct"] < base["hit_rate_pct"] - MAX_HIT_RATE_LOSS_PTS:
            continue
        accepted.append((m["roi_pct"], m["purchased_races"], name))
    if not accepted:
        return "all_signal", "no_training_rule_met_predeclared_gate"
    accepted.sort(key=lambda x: (-x[0], -x[1], x[2]))
    return accepted[0][2], "train_only_rule_met_predeclared_gate"


def run(evidence):
    days = sorted({r["date"] for r in evidence})
    if len(days) < 4:
        raise ValueError("Chronological evaluation needs at least four dates")
    mid = len(days) // 2
    train_days, holdout_days = days[:mid], days[mid:]
    assert train_days[-1] < holdout_days[0]
    train = [r for r in evidence if r["date"] in train_days and r["active"]]
    hold = [r for r in evidence if r["date"] in holdout_days and r["active"]]
    if not train or not hold:
        raise ValueError("Must have train and holdout signal records")
    locked, reason = choose_policy(train)
    table = {}
    for policy in POLICIES:
        table[policy] = {
            "train": metrics(train, policy),
            "holdout": metrics(hold, policy),
        }
    by_signal = {}
    for f in range(4):
        for r in range(4):
            key = f"F{f}R{r}"
            tr = [x for x in train if x["signal"] == key]
            ho = [x for x in hold if x["signal"] == key]
            by_signal[key] = {
                "train_races": len(tr),
                "holdout_races": len(ho),
                "proposed_decision": (
                    "not_applicable" if key == "F0R0"
                    else "buy" if should_buy(key, locked) else "skip"
                ),
                "train_baseline": metrics(tr, "all_signal"),
                "holdout_baseline": metrics(ho, "all_signal"),
                "holdout_candidate": metrics(ho, locked),
            }
    daily = {}
    for d in holdout_days:
        records = [x for x in hold if x["date"] == d]
        daily[d] = {"baseline": metrics(records, "all_signal"),
                    "candidate": metrics(records, locked)}
    best = table[locked]
    initial = table["all_signal"]
    assert initial["holdout"]["eligible_races"] == best["holdout"]["eligible_races"]
    assert best["holdout"]["purchased_races"] + best["holdout"]["skipped_races"] == len(hold)
    assert best["holdout"]["investment_yen"] + best["holdout"]["avoided_stakes_yen"] == len(hold) * STAKES_PER_RACE
    assert all(r["signal"] != "F0R0" for r in train + hold)
    return {
        "schema_version": 1,
        "model_version": MODEL,
        "status": "research_only_not_live_not_production",
        "configuration": {
            "ticket_plan": "existing_signal_top24_fixed_100yen_each",
            "fixed_stake_per_purchase_yen": STAKES_PER_RACE,
            "min_training_purchases": MIN_TRAIN_PURCHASES,
            "min_training_purchase_coverage": MIN_TRAIN_COVERAGE,
            "min_training_roi_uplift_points": MIN_ROI_UPLIFT_PTS,
            "max_training_hit_rate_loss_points": MAX_HIT_RATE_LOSS_PTS,
            "num_predeclared_rules": len(POLICIES),
            "decision_features": ["fujin_level", "raijin_level"],
            "not_used_due_to_label_leakage": [
                "score_live_of_realized_trifecta", "score_signal_of_realized_trifecta",
                "rank_signal_of_realized_trifecta", "payout", "actual_trifecta",
            ],
        },
        "source": "evaluations/signal_payout_rank_distribution/latest/race_evidence.csv",
        "training_dates": train_days, "holdout_dates": holdout_days,
        "locked_rule": locked, "locked_reason": reason,
        "comparison": {
            "train_baseline": initial["train"], "train_candidate": best["train"],
            "holdout_baseline": initial["holdout"], "holdout_candidate": best["holdout"],
        },
        "all_predeclared_rule_comparisons": table,
        "by_signal": by_signal,
        "holdout_by_date": daily,
        "data_audit": {
            "all_rows": len(evidence),
            "source_provenance": dict(Counter(r["provenance"] for r in evidence)),
            "holdout_provenance": dict(Counter(r["provenance"] for r in hold)),
            "missing_predeadline_proof": sum(r["provenance"] not in (
                "saved_pre_deadline_official_beforeinfo", "saved_live")
                for r in evidence),
            "f0r0_nonpurchases": sum(not r["active"] for r in evidence),
        },
        "interpretation": (
            "判断に使ったのは予測時点で知り得る風神・雷神強度だけ。"
            "前半のみで買い見送りを固定して後半で事後検証したが、"
            "予測保存時刻を証明できない事後復元データが含まれる。"
            "後半成績は実購入記録や将来の回収率保証ではない。"
            "ROIの分母は購入レースの24点×100円で、"
            "見送りレースは支出・払戻ともゼロ。"
            "見送りが取り逃した高配当も必ず表示する。"
            "14候補から選択したことによる過学習リスクがあるため、"
            "新規データの検証が済むまで本番には採用しない。"
            "当時の通常予測・本番シグナル・配分・購入ルールは不変。"
        ),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--evidence", default="evaluations/signal_payout_rank_distribution/latest/race_evidence.csv")
    p.add_argument("--output", default="evaluations/signal_buy_skip_holdout/latest/summary.json")
    args = p.parse_args()
    out = Path(args.output)
    report = run(load_evidence(Path(args.evidence)))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "locked_rule": report["locked_rule"],
        "dates": (report["training_dates"][-1], report["holdout_dates"][0]),
        "train_baseline_roi": report["comparison"]["train_baseline"]["roi_pct"],
        "train_candidate_roi": report["comparison"]["train_candidate"]["roi_pct"],
        "holdout_baseline_roi": report["comparison"]["holdout_baseline"]["roi_pct"],
        "holdout_candidate_roi": report["comparison"]["holdout_candidate"]["roi_pct"],
        "holdout_purchase_count": report["comparison"]["holdout_candidate"]["purchased_races"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
