#!/usr/bin/env python3
"""Research-only 120-rank high-payout distribution, all saved V2 history + rolling 7 calendar days.

Inputs must already contain pre-result prediction rankings; official results join is historical.
Never mutates production prediction logic or tickets. Do not use reconstructed past
results as a claim of live, pre-deadline performance.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

SIGNALS = [f"F{f}R{r}" for f in range(4) for r in range(4)]
TIERS = [("強本線", 1, 6), ("本線", 7, 12), ("準本線", 13, 24),
         ("中穴", 25, 48), ("穴", 49, 72), ("大穴", 73, 120)]
MODEL = "fujin_raijin_pipeline_v2_20261011"


def parse(path):
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def race_id(value):
    return "".join(c for c in str(value or "") if c.isdigit())[:12]


def is_actual(value):
    numbers = str(value or "").split("-")
    return (len(numbers) == 3 and len(set(numbers)) == 3
            and all(x.isdigit() and 1 <= int(x) <= 6 for x in numbers))


def as_int(value):
    try:
        return int(float(value or 0))
    except (ValueError, TypeError):
        return 0


def pct(a, b):
    return round(100 * a / b, 3) if b else None


def row_from_replay(x, valid_combinations):
    f, r = as_int(x["fujin_level"]), as_int(x["new_raijin_level"])
    return {
        "date": x["date"], "race_id": race_id(x["race_id"]),
        "venue": x.get("venue", ""), "signal_key": f"F{f}R{r}",
        "active": x.get("new_active") == "True", "actual": x.get("actual"),
        "payout": as_int(x.get("payout")), "rank": as_int(x.get("new_actual_rank")),
        "max_rank": valid_combinations, "provenance": x.get("provenance", "unknown"),
    }


def row_from_audited(x):
    f, r = as_int(x["fujin_level"]), as_int(x["raijin_new_level"])
    rid = race_id(x["race_id"])
    return {
        "date": "20261013", "race_id": rid, "venue": x.get("venue", ""),
        "signal_key": f"F{f}R{r}", "active": as_int(x.get("new_active")) == 1,
        "actual": x.get("actual"), "payout": as_int(x.get("payout")),
        "rank": as_int(x.get("new_24_rank")),
        "max_rank": 60 if rid == "202610131408" else 120,
        "provenance": x.get("source", "audited"),
    }


def eligible(row):
    return is_actual(row["actual"]) and row["payout"] > 0


def collect(replay, supplement, diagnostic):
    known = {}
    for x in parse(diagnostic):
        known[(x["date"], race_id(x["race_id"]))] = as_int(x.get("combination_count"))
    races = {}
    excluded = []
    conflicts = []
    for x in parse(replay):
        key = (x["date"], race_id(x["race_id"]))
        r = row_from_replay(x, known.get(key) or 120)
        if not eligible(r):
            excluded.append({"date": key[0], "race_id": key[1], "reason": "unsettled_result"})
            continue
        if key in races and (r["actual"], r["payout"], r["signal_key"], r["rank"]) != (
            races[key]["actual"], races[key]["payout"], races[key]["signal_key"], races[key]["rank"]):
            raise ValueError(f"duplicate conflicting V2 replay: {key}")
        races[key] = r

    # Until the regular V2 replay includes the audited Oct-13 recovery, merge its
    # independently audited day. On conflicting replay use the dedicated day audit.
    for x in parse(supplement):
        r = row_from_audited(x)
        if not eligible(r):
            continue
        key = (r["date"], r["race_id"])
        if key in races and (r["actual"], r["payout"], r["signal_key"], r["rank"]) != (
            races[key]["actual"], races[key]["payout"], races[key]["signal_key"], races[key]["rank"]):
            conflicts.append({"date": key[0], "race_id": key[1],
                              "resolution": "audited_recovery_preferred"})
        races[key] = r

    rows = sorted(races.values(), key=lambda x: (x["date"], x["race_id"]))
    for r in rows:
        if r["signal_key"] not in SIGNALS or r["active"] != (r["signal_key"] != "F0R0"):
            raise ValueError(f"invalid signal state: {r['race_id']}")
        if r["active"] and not (1 <= r["rank"] <= r["max_rank"] <= 120):
            raise ValueError(f"invalid valid-combination count/rank: {r['race_id']}")
        if not r["active"] and r["rank"] != 0:
            raise ValueError(f"non-signaled scored as active: {r['race_id']}")
    return rows, excluded, conflicts


def statistics(rows):
    by_signal = {}
    for signal in SIGNALS:
        group = [r for r in rows if r["signal_key"] == signal]
        high5 = sum(r["payout"] >= 5000 for r in group)
        high10 = sum(r["payout"] >= 10000 for r in group)
        h = {"all": [0] * 120, "high5": [0] * 120, "manshu": [0] * 120}
        active = [r for r in group if r["active"]]
        for r in active:
            ix = r["rank"] - 1
            h["all"][ix] += 1
            if r["payout"] >= 5000:
                h["high5"][ix] += 1
            if r["payout"] >= 10000:
                h["manshu"][ix] += 1
        tiers = []
        for name, start, end in TIERS:
            total = sum(h["all"][start-1:end])
            n5 = sum(h["high5"][start-1:end])
            n10 = sum(h["manshu"][start-1:end])
            width = end - start + 1
            tiers.append(dict(name=name, start=start, end=end, width=width,
                              hits=total, high5_hits=n5, manshu_hits=n10,
                              p_any=pct(total, len(group)),
                              p_high5=pct(n5, len(group)),
                              p_manshu=pct(n10, len(group)),
                              p_high5_conditional=pct(n5, high5),
                              p_manshu_conditional=pct(n10, high10),
                              per_rank_high5=pct(n5, len(group)*width),
                              per_rank_manshu=pct(n10, len(group)*width)))
        by_signal[signal] = dict(
            races=len(group), active=len(active), payout_ge5000=high5,
            payout_ge10000=high10, p_ge5000=pct(high5, len(group)),
            p_ge10000=pct(high10, len(group)), ranks=h, tiers=tiers)
    active = [r for r in rows if r["active"]]
    return dict(races=len(rows), signal_active=len(active),
                payout_ge5000=sum(r["payout"] >= 5000 for r in rows),
                payout_ge10000=sum(r["payout"] >= 10000 for r in rows),
                signal_high5_captured=sum(r["payout"] >= 5000 for r in active),
                signal_manshu_captured=sum(r["payout"] >= 10000 for r in active),
                by_signal=by_signal)


def write_rows(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", default="evaluations/raijin_all_rank_v2_replay/details.csv")
    ap.add_argument("--audited-day", default="evaluations/2026/10/13/PDCA_08_V1_V2_RACE_LEVEL_20261013.csv")
    ap.add_argument("--diagnostic", default="evaluations/signal_rank_research/v1/race_diagnostics.csv")
    ap.add_argument("--output-dir", default="evaluations/signal_payout_rank_distribution/latest")
    opt = ap.parse_args()
    races, excluded, conflicts = collect(Path(opt.replay), Path(opt.audited_day),
                                         Path(opt.diagnostic))
    if not races:
        raise SystemExit("No auditable historical signal rankings")
    dates = sorted(set(x["date"] for x in races))
    latest = datetime.strptime(dates[-1], "%Y%m%d")
    first_in_seven = (latest - timedelta(days=6)).strftime("%Y%m%d")
    latest7 = [r for r in races if r["date"] >= first_in_seven]
    periods = {"last7": dict(dates=sorted(set(x["date"] for x in latest7)),
                             **statistics(latest7)),
               "all": dict(dates=dates, **statistics(races))}
    for kind, v in periods.items():
        if sum(s["races"] for s in v["by_signal"].values()) != v["races"]:
            raise RuntimeError(f"signal denominator mismatch in {kind}")
        if sum(sum(s["ranks"]["high5"]) for s in v["by_signal"].values()) != v["signal_high5_captured"]:
            raise RuntimeError(f"high payout rank coverage mismatch in {kind}")
        if sum(sum(s["ranks"]["manshu"]) for s in v["by_signal"].values()) != v["signal_manshu_captured"]:
            raise RuntimeError(f"manshu rank coverage mismatch in {kind}")
    root = Path(opt.output_dir)
    root.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": 1, "model_version": MODEL, "status": "retrospective_research_only",
        "source_coverage": {
            "from": dates[0], "to": dates[-1], "available_dates": dates,
            "available_date_count": len(dates), "excluded_unusable": excluded,
            "conflicts": conflicts, "source_counts": dict(Counter(r["provenance"] for r in races)),
        },
        "tiers": [{"name": n, "start": a, "end": b} for n, a, b in TIERS],
        "periods": periods,
        "warning": "累計は研究再生可能な保存済み履歴のみ。事後復元が含まれ、将来の個別レースの確率や実購入成績ではない。",
    }
    (root / "summary.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    records = []
    for r in races:
        records.append({**r, "rank": r["rank"] or "", "active": int(r["active"])})
    write_rows(root / "race_evidence.csv", records,
               ["date","race_id","venue","signal_key","active","actual","payout",
                "rank","max_rank","provenance"])
    rank_rows = []
    for period, s in periods.items():
        for key, group in s["by_signal"].items():
            for ix in range(120):
                rank_rows.append({
                    "period":period, "signal":key, "races":group["races"],
                    "rank":ix+1, "rank_applicable":int(key!="F0R0"),
                    "actual_hits":group["ranks"]["all"][ix] if key!="F0R0" else "",
                    "high5_hits":group["ranks"]["high5"][ix] if key!="F0R0" else "",
                    "manshu_hits":group["ranks"]["manshu"][ix] if key!="F0R0" else "",
                })
    write_rows(root / "rank_distribution.csv", rank_rows,
               ["period","signal","races","rank","rank_applicable",
                "actual_hits","high5_hits","manshu_hits"])
    print(json.dumps({"pass":True,"available_date_range":[dates[0],dates[-1]],
                      "all_races":periods["all"]["races"],
                      "all_signaled":periods["all"]["signal_active"],
                      "last7_races":periods["last7"]["races"],
                      "last7_signaled":periods["last7"]["signal_active"],
                      "excluded":len(excluded),"conflicts":len(conflicts)},ensure_ascii=False))


if __name__ == "__main__":
    main()
