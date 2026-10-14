#!/usr/bin/env python3
"""Research-only, time-separated evaluation of F0..3 x R0..3 ticket sets.

The input is a historical *rank evidence* CSV. The realized outcome rank is
joined to the past prediction score in another pipeline, not calculated here.
This experiment never sees the holdout dates when selecting a ticket policy.
It never modifies production score coefficients, signal rules, bet amounts,
prediction JSON, or live collectors.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

MODEL = "signal_24_temporal_holdout_v1_20261014"
SIGNALS = [f"F{f}R{r}" for f in range(4) for r in range(4)]
TIERS = (("強本線", 1, 6), ("本線", 7, 12), ("準本線", 13, 24),
         ("中穴", 25, 48), ("穴", 49, 72), ("大穴", 73, 120))
# Pre-registered fixed-position allocations: all exactly 24 selections.
POLICY_RANGES = {
    "top24": ((1, 24),),
    "head18_mid6": ((1, 18), (25, 30)),
    "head12_mid12": ((1, 12), (25, 36)),
    "head12_mid6_tail6": ((1, 12), (25, 30), (49, 54)),
    "head6_mid18": ((1, 6), (25, 42)),
    "head6_mid6_tail12": ((1, 6), (25, 30), (49, 60)),
    "spread_6x4": ((1, 6), (13, 18), (25, 30), (49, 54)),
    "wide_6x4": ((1, 6), (25, 30), (49, 54), (73, 78)),
}
POLICIES = {
    key: tuple(rank for first, last in segments for rank in range(first, last + 1))
    for key, segments in POLICY_RANGES.items()
}
assert len(POLICIES) == 8
assert all(len(v) == 24 and len(set(v)) == 24 for v in POLICIES.values())

MIN_TRAIN_RACES = 40
MIN_TRAIN_WINS = 8
MIN_UPLIFT_ROI_POINTS = 20
MAX_HIT_RATE_LOSS_POINTS = 5


def numeric(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def load_evidence(path):
    with path.open(encoding="utf-8-sig", newline="") as fh:
        raw = list(csv.DictReader(fh))
    if not raw:
        raise ValueError("Empty rank evidence; do not report zero samples as success")
    out, seen = [], set()
    for line in raw:
        key = (line.get("date"), line.get("race_id"))
        if key in seen:
            raise ValueError(f"Duplicate historical race: {key}")
        seen.add(key)
        active = numeric(line.get("active")) == 1
        signal = line.get("signal_key")
        payout = numeric(line.get("payout"), -1)
        rank = numeric(line.get("rank"))
        max_rank = numeric(line.get("max_rank"))
        if signal not in SIGNALS or active != (signal != "F0R0"):
            raise ValueError(f"Invalid F/R activation: {key}")
        if not (line.get("date") or "").isdigit() or len(line["date"]) != 8:
            raise ValueError(f"Invalid date: {key}")
        if payout <= 0 or max_rank < 24 or max_rank > 120:
            raise ValueError(f"Bad payout or combination range: {key}")
        if active and not (1 <= rank <= max_rank):
            raise ValueError(f"Missing result rank for active signal: {key}")
        if not active and rank != 0:
            raise ValueError(f"Inactive F0R0 was ranked: {key}")
        out.append(dict(date=line["date"], race_id=line["race_id"], signal=signal,
                        active=active, payout=payout, rank=rank, max_rank=max_rank,
                        provenance=line.get("provenance") or "unknown"))
    return sorted(out, key=lambda r: (r["date"], r["race_id"]))


def select_tickets(policy, max_rank):
    """Never use the realized rank: fill impossible ranks with lowest available."""
    plan = list(POLICIES[policy])
    selected = [r for r in plan if r <= max_rank]
    for r in range(1, max_rank + 1):
        if len(selected) >= min(24, max_rank):
            break
        if r not in selected:
            selected.append(r)
    return tuple(selected)


def evaluate(rows, policy):
    hits = high5 = manshu = payout_total = spend = 0
    for race in rows:
        tickets = select_tickets(policy, race["max_rank"])
        spend += 100 * len(tickets)
        if race["rank"] in tickets:
            hits += 1
            payout_total += race["payout"]
            high5 += race["payout"] >= 5000
            manshu += race["payout"] >= 10000
    n = len(rows)
    return {
        "races": n, "hits": hits, "high5_hits": high5, "manshu_hits": manshu,
        "stake_yen": spend, "return_yen": payout_total,
        "profit_yen": payout_total - spend,
        "hit_rate_pct": round(100 * hits / n, 2) if n else None,
        "roi_pct": round(100 * payout_total / spend, 2) if spend else None,
    }


def choose(train_rows):
    base = evaluate(train_rows, "top24")
    # A small n cannot justify a per-signal policy change. For zero n,
    # the default is clearly labelled "insufficient", not zero performance.
    if len(train_rows) < MIN_TRAIN_RACES:
        return "top24", "insufficient_training_races"
    qualified = []
    for name in POLICIES:
        if name == "top24":
            continue
        row = evaluate(train_rows, name)
        if (
            row["hits"] >= MIN_TRAIN_WINS
            and row["roi_pct"] >= base["roi_pct"] + MIN_UPLIFT_ROI_POINTS
            and row["hit_rate_pct"] >= base["hit_rate_pct"] - MAX_HIT_RATE_LOSS_POINTS
        ):
            qualified.append((row["roi_pct"], row["hit_rate_pct"], name))
    if not qualified:
        return "top24", "no_training_candidate_passed_gate"
    qualified.sort(key=lambda r: (-r[0], -r[1], r[2]))
    return qualified[0][2], "training_candidate_passed_gate"


def run(rows):
    dates = sorted({r["date"] for r in rows})
    if len(dates) < 4:
        raise ValueError("At least four distinct dates required for chronological holdout")
    half = len(dates) // 2
    train_dates, test_dates = dates[:half], dates[half:]
    assert max(train_dates) < min(test_dates)
    training = [r for r in rows if r["date"] in train_dates and r["active"]]
    holdout = [r for r in rows if r["date"] in test_dates and r["active"]]
    all_active = training + holdout
    if not training or not holdout:
        raise ValueError("No active training or holdout rows")
    details, decisions = {}, {}
    for signal in SIGNALS:
        tr = [r for r in training if r["signal"] == signal]
        te = [r for r in holdout if r["signal"] == signal]
        policy, reason = ("no_bet", "no_signal") if signal == "F0R0" else choose(tr)
        decisions[signal] = policy
        comparisons = {
            name: {"train": evaluate(tr, name), "holdout": evaluate(te, name)}
            for name in POLICIES
        } if signal != "F0R0" else {}
        details[signal] = {
            "training_races": len(tr), "holdout_races": len(te),
            "proposed_policy": policy, "selection_reason": reason,
            "train": {"baseline": evaluate(tr, "top24"),
                      "candidate": evaluate(tr, policy) if policy != "no_bet" else None},
            "holdout": {"baseline": evaluate(te, "top24"),
                        "candidate": evaluate(te, policy) if policy != "no_bet" else None},
            "all_fixed_policy_comparisons": comparisons,
        }
    def whole_period(pool):
        base = evaluate(pool, "top24")
        profit = stake = payout = hits = high5 = manshu = 0
        for r in pool:
            method = decisions[r["signal"]]
            result = evaluate([r], method)
            hits += result["hits"]; high5 += result["high5_hits"]; manshu += result["manshu_hits"]
            profit += result["profit_yen"]; stake += result["stake_yen"]; payout += result["return_yen"]
        return {
            "baseline": base,
            "candidate": {"races": len(pool), "hits": hits,
                          "high5_hits": high5, "manshu_hits": manshu,
                          "stake_yen": stake, "return_yen": payout, "profit_yen": profit,
                          "hit_rate_pct": round(100 * hits / len(pool), 2) if pool else None,
                          "roi_pct": round(100 * payout / stake, 2) if stake else None}
        }
    audit = {
        "unique_rows": len(rows),
        "all_dates": dates, "train_dates": train_dates, "holdout_dates": test_dates,
        "provenance_all": dict(Counter(r["provenance"] for r in rows)),
        "provenance_holdout": dict(Counter(r["provenance"] for r in holdout)),
        "normal_not_purchased": sum(not r["active"] for r in rows),
        "has_post_result_reconstruction": any(
            r["provenance"] in ("post_result_official_beforeinfo", "saved_after_deadline_official_beforeinfo")
            for r in rows),
    }
    return {
        "schema_version": 1, "model_version": MODEL,
        "status": "retrospective_rank_simulation_not_live_predeadline",
        "source": "evaluations/signal_payout_rank_distribution/latest/race_evidence.csv",
        "date_split": {"train_start": train_dates[0], "train_end": train_dates[-1],
                       "holdout_start": test_dates[0], "holdout_end": test_dates[-1],
                       "train_days": len(train_dates), "holdout_days": len(test_dates)},
        "policy_catalog": {
            name: {"ranks": list(ranks),
                   "tier_counts": {label: sum(lo <= r <= hi for r in ranks)
                                   for label, lo, hi in TIERS}}
            for name, ranks in POLICIES.items()
        },
        "gate": {"min_train_races": MIN_TRAIN_RACES,
                 "min_train_wins": MIN_TRAIN_WINS,
                 "min_roi_uplift_points": MIN_UPLIFT_ROI_POINTS,
                 "max_hit_rate_loss_points": MAX_HIT_RATE_LOSS_POINTS},
        "audit": audit,
        "overall": {"train": whole_period(training),
                    "holdout": whole_period(holdout),
                    "all_retrospective": whole_period(all_active)},
        "by_signal": details,
        "warning": (
            "分割はレース日付順だが、元データに事後復元/取得時刻の未立証データを含む。"
            "未来の実運用成績を示す前向き検証ではない。候補選択には前半データのみを使用し、"
            "後半7日は評価専用。ホールドアウトの成績を見て再選択しない。"
            "F0R0は専用AI非発動で購入対象外。購入ロジック・現行24点は変更しない。"
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default="evaluations/signal_payout_rank_distribution/latest/race_evidence.csv")
    parser.add_argument("--output", default="evaluations/signal_24_temporal_holdout/latest/summary.json")
    args = parser.parse_args()
    data = run(load_evidence(Path(args.evidence)))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "model": MODEL, "train": data["overall"]["train"]["baseline"],
        "holdout_baseline": data["overall"]["holdout"]["baseline"],
        "holdout_candidate": data["overall"]["holdout"]["candidate"],
        "selected_nonbaseline": {k: v["proposed_policy"] for k, v in data["by_signal"].items()
                                  if v["proposed_policy"] not in ("top24", "no_bet")},
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
