#!/usr/bin/env python3
"""Research-only 6/8/12/18/24 ticket comparison using the SAME frozen V2 ranking.

Uses retrospective replay output. These are hypothetical purchases, not
pre-deadline orders or proof of real-time availability. Never modifies models.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

SRC = Path("evaluations/raijin_all_rank_v2_replay/details.csv")
REPLAY = Path("evaluations/raijin_all_rank_v2_replay/summary.json")
OUT = Path("evaluations/raijin_v2_points_pdca/latest")
CUTOFFS = (6, 8, 12, 18, 24)
KEYS = tuple(f"F{f}R{r}" for f in range(4) for r in range(4))


def pct(top, bottom):
    return round(100 * top / bottom, 2) if bottom else None


def summarize(rows):
    result = {}
    for p in CUTOFFS:
        n = len(rows)
        hit_rows = [r for r in rows if r["rank"] <= p]
        investment = n * p * 100
        ret = sum(r["payout"] for r in hit_rows)
        result[str(p)] = {
            "races": n,
            "points_per_race": p,
            "hits": len(hit_rows),
            "hit_rate_pct": pct(len(hit_rows), n),
            "investment_yen": investment,
            "return_yen": ret,
            "profit_yen": ret - investment,
            "roi_pct": pct(ret, investment),
            "manshu_hits": sum(r["payout"] >= 10000 for r in hit_rows),
            "payout_5000plus_hits": sum(r["payout"] >= 5000 for r in hit_rows),
        }
    return result


def group(rows):
    return {key: summarize([r for r in rows if r["key"] == key]) for key in KEYS}


def main():
    if not SRC.is_file() or not REPLAY.is_file():
        raise SystemExit("V2 retrospective replay source missing")
    reference = json.loads(REPLAY.read_text(encoding="utf-8"))
    if reference.get("research_only") is not True:
        raise SystemExit("V2 replay lacks research-only provenance")
    records = []
    seen = set()
    with SRC.open(encoding="utf-8-sig", newline="") as h:
        for source in csv.DictReader(h):
            if not source.get("actual"):
                continue
            date = source["date"]
            race_id = "".join(ch for ch in source["race_id"] if ch.isdigit())[:12]
            unique = (date, race_id)
            if unique in seen:
                raise SystemExit(f"duplicate V2 replay race: {unique}")
            seen.add(unique)
            f = int(source["fujin_level"])
            r = int(source["new_raijin_level"])
            if not (0 <= f <= 3 and 0 <= r <= 3):
                raise SystemExit(f"unrecognized signal strength: {unique}")
            if f == 0 and r == 0:
                continue
            raw_rank = source.get("new_actual_rank")
            if not raw_rank:
                raise SystemExit(f"active signal missing V2 120-order rank: {unique}")
            rank = int(raw_rank)
            if not 1 <= rank <= 120:
                raise SystemExit(f"invalid V2 rank: {unique}: {rank}")
            payout = int(source["payout"] or 0)
            if payout < 0:
                raise SystemExit(f"negative payout: {unique}")
            records.append({
                "date": date,
                "race_id": race_id,
                "key": f"F{f}R{r}",
                "rank": rank,
                "payout": payout,
                "provenance": source.get("provenance", ""),
            })

    dates = sorted({r["date"] for r in records})
    if not dates:
        raise SystemExit("no finished active signals")
    per_date = {}
    for day in dates:
        daily = [r for r in records if r["date"] == day]
        per_date[day] = {
            "active_races": len(daily),
            "points": summarize(daily),
            "by_signal_16": group(daily),
            "provenance_counts": dict(sorted(
                (p, sum(r["provenance"] == p for r in daily))
                for p in {r["provenance"] for r in daily}
            )),
        }

    anchor = datetime.strptime(dates[-1], "%Y%m%d").date()
    last7 = {(anchor - timedelta(days=i)).strftime("%Y%m%d") for i in range(7)}
    recent = [r for r in records if r["date"] in last7]
    current = summarize(records)
    expected = reference.get("new") or {}
    if (expected.get("signal_active_finished_races") != len(records)
        or expected.get("hit24_races") != current["24"]["hits"]
        or expected.get("investment_yen") != current["24"]["investment_yen"]
        or expected.get("return_yen") != current["24"]["return_yen"]):
        raise SystemExit("24-point totals conflict with canonical V2 retrospective replay")
    output = {
        "schema_version": 1,
        "model_version": reference.get("ruleset"),
        "research_only": True,
        "retrospective_paper_bets_not_historical_real_purchases": True,
        "uses_same_frozen_120_combination_order": True,
        "stake_per_ticket_yen": 100,
        "source_replay": str(SRC),
        "source_dates": dates,
        "latest_date": dates[-1],
        "per_date": per_date,
        "rolling7": {
            "dates": sorted(last7),
            "active_races": len(recent),
            "points": summarize(recent),
            "by_signal_16": group(recent),
        },
        "cumulative": {
            "active_races": len(records),
            "points": current,
            "by_signal_16": group(records),
        },
        "validation": {
            "matches_replay_24_point_races": True,
            "matches_replay_24_point_hits": True,
            "matches_replay_24_point_costs": True,
            "matches_replay_24_point_return": True,
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("RAIJIN_V2_POINTS_PDCA_READY", dates[-1], len(records), "6/8/12/18/24")


if __name__ == "__main__":
    main()
