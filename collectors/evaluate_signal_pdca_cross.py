#!/usr/bin/env python3
"""Signal PDCA: 16 F/R combinations x four independent bet methods.

Uses SAVED pre-result predictions and separate archived race results only for
evaluation; never regenerates, changes, or selects the predictions using truth.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path("evaluations")
BACKTEST = ROOT / "fujin_raijin/latest/backtest_details.csv"
SIGNAL_AI = ROOT / "signal_ai/latest/details.csv"
OUT = ROOT / "signal_pdca_cross/latest"
METHODS = ("formation", "top3_box", "normal_ai", "signal_ai24")
BINS = (
    ("under_1000", 0, 1000), ("1000_1999", 1000, 2000),
    ("2000_2999", 2000, 3000), ("3000_3999", 3000, 4000),
    ("4000_4999", 4000, 5000), ("5000_9999", 5000, 10000),
    ("10000_29999", 10000, 30000),
    ("30000_49999", 30000, 50000), ("50000_plus", 50000, None),
)


def num(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def pct(a, b):
    return round(100.0 * a / b, 2) if b else None


def rid(v):
    digits = "".join(c for c in str(v or "") if c.isdigit())
    return digits[:12] if len(digits) >= 12 else ""


def rows(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def true(v):
    return str(v).lower() in {"1", "true", "yes"}


def datepath(d, method):
    names = {
        "formation": "formation_simulation",
        "top3_box": "top3_box_simulation",
        "normal_ai": "ai_score_simulation",
    }
    prefix = names[method]
    return ROOT / d[:4] / d[4:6] / d[6:8] / f"{prefix}_{d}.csv"


def method_result(entry, method):
    if entry is None:
        return None
    if method == "signal_ai24":
        if not entry.get("actual_combo_rank") or not entry.get("payout"):
            return None
        points = 24
        hit = num(entry.get("actual_combo_rank"), 999) <= points
        pay = num(entry.get("payout"))
        return dict(points=points, investment=2400, hit=hit,
                    returned=pay if hit else 0)
    points = num(entry.get("points"))
    cost = num(entry.get("investment"), points * 100)
    if not points or not cost:
        return None
    return dict(points=points, investment=cost, hit=true(entry.get("hit")),
                returned=num(entry.get("return")))


def summarize_method(items):
    valid = [r for r in items if r is not None]
    n = len(valid)
    if not n:
        return dict(races=0, hits=0, hit_rate_pct=None, points=0,
                    avg_points=None, investment=0, returned=0,
                    profit=0, roi_pct=None, missing=len(items))
    hits = sum(r["hit"] for r in valid)
    points = sum(r["points"] for r in valid)
    inv = sum(r["investment"] for r in valid)
    returned = sum(r["returned"] for r in valid)
    return dict(races=n, hits=hits, hit_rate_pct=pct(hits,n),
                points=points, avg_points=round(points/n,2),
                investment=inv, returned=returned,
                profit=returned-inv, roi_pct=pct(returned,inv),
                missing=len(items)-n)


def cross(rows_in):
    table = {}
    for f in range(4):
        for r in range(4):
            key = f"F{f}R{r}"
            group = [x for x in rows_in if x["key"] == key]
            table[key] = dict(
                races=len(group),
                high5000=sum(x["payout"] >= 5000 for x in group),
                manshu=sum(x["payout"] >= 10000 for x in group),
                methods={
                    method: ({"status": "not_applicable"} if key == "F0R0" and method == "signal_ai24"
                             else summarize_method([x["methods"].get(method) for x in group]))
                    for method in METHODS
                },
            )
    return table


def payout_group(rows_in):
    n = len(rows_in)
    p5 = sum(x["payout"] >= 5000 for x in rows_in)
    manshu = sum(x["payout"] >= 10000 for x in rows_in)
    return dict(races=n, under5000=n-p5, high5000=p5,
                high5000_rate_pct=pct(p5,n), manshu=manshu,
                manshu_rate_pct=pct(manshu,n),
                payout_bins={k:sum(x["payout"] >= low and
                          (high is None or x["payout"] < high) for x in rows_in)
                             for k,low,high in BINS})


def high_analysis(rows_in):
    yes = [x for x in rows_in if x["signal"]]
    no = [x for x in rows_in if not x["signal"]]
    all_high = sum(x["payout"] >= 5000 for x in rows_in)
    all_manshu = sum(x["payout"] >= 10000 for x in rows_in)
    high_yes = sum(x["payout"] >= 5000 for x in yes)
    manshu_yes = sum(x["payout"] >= 10000 for x in yes)
    return dict(
        total=payout_group(rows_in), signal_active=payout_group(yes),
        signal_inactive=payout_group(no),
        high5000_capture_pct=pct(high_yes,all_high),
        manshu_capture_pct=pct(manshu_yes,all_manshu),
        high5000_denominator=all_high,
        manshu_denominator=all_manshu,
    )


def main():
    raw = rows(BACKTEST)
    if not raw:
        raise RuntimeError(f"Required saved signal history absent: {BACKTEST}")
    ai_map = {(str(x.get("date")),rid(x.get("race_id"))):x for x in rows(SIGNAL_AI)}
    dates = sorted(set(str(x["date"]) for x in raw))
    by_method = {}
    for d in dates:
        by_method[d] = {}
        for method in METHODS[:3]:
            by_method[d][method] = {
                rid(x.get("race_id")):x for x in rows(datepath(d,method))
            }

    compiled = []
    for x in raw:
        d = str(x["date"])
        race = rid(x.get("race_id"))
        if not race:
            continue
        f,r = num(x.get("fujin_level")),num(x.get("raijin_level"))
        if f not in range(4) or r not in range(4):
            continue
        sample = dict(
            date=d, race_id=race, key=f"F{f}R{r}",
            fujin_level=f, raijin_level=r,
            signal=bool(f or r), payout=num(x.get("payout")),
            methods={},
        )
        for method in METHODS[:3]:
            sample["methods"][method] = method_result(
                by_method[d][method].get(race),method)
        sample["methods"]["signal_ai24"] = method_result(
            ai_map.get((d,race)),"signal_ai24") if (f or r) else None
        compiled.append(sample)

    per_date = {}
    for d in dates:
        day = [x for x in compiled if x["date"] == d]
        per_date[d] = dict(date=d, races=len(day),
                           high_analysis=high_analysis(day),
                           combination_methods=cross(day))

    anchor = datetime.strptime(dates[-1], "%Y%m%d").date()
    week_dates = {(anchor - timedelta(days=k)).strftime("%Y%m%d") for k in range(7)}
    last7 = [x for x in compiled if x["date"] in week_dates]
    output = dict(
        schema_version=1,
        definition="F0R0..F3R3 x saved formation / saved TOP3 BOX / saved normal AI / saved signal-only AI top24; 100 yen per combo",
        latest_date=dates[-1], available_dates=dates,
        total_races=len(compiled), model_note="method-specific missing entries not counted as losses; report missing per method",
        per_date=per_date,
        rolling7=dict(date_range=sorted(week_dates),
                      races=len(last7), high_analysis=high_analysis(last7),
                      combination_methods=cross(last7)),
        cumulative=dict(races=len(compiled),high_analysis=high_analysis(compiled),
                        combination_methods=cross(compiled)),
    )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(
        json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    with (OUT / "details.csv").open("w",encoding="utf-8",newline="") as f:
        cols = ["date","race_id","signal_key","payout","formation_hit",
                "top3_box_hit","normal_ai_hit","signal_ai24_hit"]
        w = csv.DictWriter(f,fieldnames=cols)
        w.writeheader()
        for row in compiled:
            w.writerow({
                "date":row["date"],"race_id":row["race_id"],"signal_key":row["key"],
                "payout":row["payout"],
                **{method+"_hit":(int(row["methods"][method]["hit"])
                   if row["methods"].get(method) is not None else "")
                   for method in METHODS}
            })
    print(json.dumps({"latest":dates[-1],"total":len(compiled),
                      "signal24":sum(x["methods"]["signal_ai24"] is not None
                                       for x in compiled)},ensure_ascii=False))


if __name__=="__main__":
    main()
