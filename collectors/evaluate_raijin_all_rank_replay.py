"""Side-by-side research replay of archived rank-gated Raijin vs all-rank Raijin.

Never edits canonical predictions, observed purchase records, or production PDCA.
Result data is joined AFTER the two independently generated pre-result signals/tickets.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from build_latest_prediction_view import (
    build_up_signal, build_down_signal, build_signal_ai_prediction,
    load_signal_ai_config, signal_field_is_verified, SIGNAL_LOGIC,
)
from evaluate_signal_ai_performance import load_live, _signal_inputs
from evaluate_down_signal import verified_signal_quality_by_race, normalize_race_id


def parse_args():
    parser = argparse.ArgumentParser(description="Re-evaluate archived Raijin without live-rank gate")
    parser.add_argument("--from-date", default="20260930", help="YYYYMMDD")
    parser.add_argument("--to-date", default="20991231", help="YYYYMMDD")
    parser.add_argument("--output-dir", default="evaluations/raijin_all_rank_v2_replay")
    return parser.parse_args()


def official_results(date):
    source = Path("archive") / date[:4] / date[4:6] / date[6:8] / f"results_{date}_all.csv"
    if not source.is_file():
        return {}
    results = {}
    with source.open(encoding="utf-8-sig", newline="") as stream:
        for item in csv.DictReader(stream):
            key = normalize_race_id(item.get("race_id"))
            if not key:
                continue
            combo = str(item.get("trifecta") or "").replace("=", "-").strip()
            parts = combo.split("-")
            valid = (
                len(parts) == 3
                and all(p.isdigit() and int(p) in range(1, 7) for p in parts)
                and len(set(parts)) == 3
            )
            try:
                payout = int(float(item.get("trifecta_pay") or 0))
            except (TypeError, ValueError):
                payout = 0
            if key in results and (results[key]["actual"] != (combo if valid else None)
                                   or results[key]["payout"] != payout):
                raise ValueError(f"Conflicting official result: {key}")
            results[key] = {"actual": combo if valid else None, "payout": payout}
    # A separately verified, immutable official-result backfill may exist when
    # the historical K-file omitted a race. It is settlement evidence ONLY.
    # Do not edit prediction inputs or silently overwrite conflicting results.
    backfill = source.with_name(f"official_result_backfills_{date}.json")
    if backfill.is_file():
        document = json.loads(backfill.read_text(encoding="utf-8"))
        if document.get("date") != date or not isinstance(document.get("verified_results"), list):
            raise ValueError(f"Invalid official result backfill manifest: {backfill}")
        for row in document["verified_results"]:
            race = normalize_race_id(row.get("race_id"))
            combo = str(row.get("trifecta") or "").strip()
            parts = combo.split("-")
            url = str(row.get("source_url") or "")
            if (not race or not race.startswith(date) or
                row.get("source_type") != "boatrace_official" or
                not url.startswith("https://www.boatrace.jp/") or
                f"hd={date}" not in url or
                len(parts) != 3 or len(set(parts)) != 3 or
                any(p not in {"1", "2", "3", "4", "5", "6"} for p in parts)):
                raise ValueError(f"Unverified official result backfill: {race}")
            try:
                payout = int(row["trifecta_pay"])
            except (KeyError, ValueError, TypeError) as exc:
                raise ValueError(f"Invalid official backfill payout: {race}") from exc
            if payout <= 0:
                raise ValueError(f"Nonpositive official backfill payout: {race}")
            verified = {"actual": combo, "payout": payout}
            if race in results and results[race] != verified:
                raise ValueError(f"Official result/backfill conflict: {race}")
            results[race] = verified
    return results


def combinations(prediction):
    if not prediction:
        return set(), None
    top24 = {x["combination"] for x in prediction.get("combinations") or []}
    return top24, prediction.get("signal_key")


def summarize(rows, label):
    finished = [x for x in rows if x["actual"] is not None]
    candidates = [x for x in finished if x[f"{label}_active"]]
    hits = [x for x in candidates if x[f"{label}_hit24"]]
    investment = 2400 * len(candidates)
    payout = sum(x["payout"] for x in hits)
    higher = [x for x in finished if x["payout"] >= 5000]
    manshu = [x for x in finished if x["payout"] >= 10000]
    pct = lambda a, b: round(100 * a / b, 2) if b else None
    return {
        "finished_races_with_usable_data": len(finished),
        "signal_active_finished_races": len(candidates),
        "active_rate_pct": pct(len(candidates), len(finished)),
        "hit24_races": len(hits),
        "hit24_rate_pct": pct(len(hits), len(candidates)),
        "investment_yen": investment,
        "return_yen": payout,
        "profit_yen": payout - investment,
        "roi_pct": pct(payout, investment),
        "payout_5000plus_captured": sum(x[f"{label}_active"] for x in higher),
        "payout_5000plus_total": len(higher),
        "payout_5000plus_capture_pct": pct(sum(x[f"{label}_active"] for x in higher), len(higher)),
        "manshu_captured": sum(x[f"{label}_active"] for x in manshu),
        "manshu_total": len(manshu),
        "manshu_capture_pct": pct(sum(x[f"{label}_active"] for x in manshu), len(manshu)),
    }



def grouped_signal_pdca(rows, label="new"):
    """16 classification PDCA, one fixed 24-ticket virtual purchase per active race."""
    buckets = {}
    for f_level in range(4):
        for r_level in range(4):
            key = f"F{f_level}R{r_level}"
            matching = [r for r in rows
                        if r["fujin_level"] == f_level
                        and r[f"{label}_raijin_level"] == r_level]
            buckets[key] = {
                "signal_key": key,
                "fujin_level": f_level,
                "raijin_level": r_level,
                "valid_races": len(matching),
                **summarize(matching, label),
            }
    return buckets


def candidate_pdca(rows):
    """Raijin candidate finish position and score bands (truth used only in settlement)."""
    bands = {
        "under40": (0, 40), "40_49": (40, 50),
        "50_59": (50, 60), "60_plus": (60, float("inf")),
    }
    summary = {}
    for name, (lower, upper) in bands.items():
        candidates = [
            candidate for row in rows if row["actual"] is not None
            for candidate in row["new_raijin_candidates"]
            if lower <= candidate["score"] < upper
        ]
        counts = Counter(int(c["finish"]) for c in candidates if c["finish"] is not None)
        total = len(candidates)
        pct = lambda v: round(v * 100 / total, 2) if total else None
        summary[name] = {
            "candidate_count": total,
            "first_count": counts[1],
            "second_count": counts[2],
            "third_count": counts[3],
            "top3_count": counts[1] + counts[2] + counts[3],
            "first_rate_pct": pct(counts[1]),
            "second_rate_pct": pct(counts[2]),
            "third_rate_pct": pct(counts[3]),
            "top3_rate_pct": pct(counts[1] + counts[2] + counts[3]),
        }
    return summary


def write_details(path, details):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(details[0]) if details else [
        "date", "race_id", "fujin_level", "old_raijin_level",
        "new_raijin_level", "old_hit24", "new_hit24",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in details:
            writer.writerow({
                k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                for k, v in item.items()
            })



def main():
    args = parse_args()
    config = load_signal_ai_config()
    if SIGNAL_LOGIC["detection"]["raijin"]["outside_live_top3"] is not False:
        raise RuntimeError("v2 rank-independent configuration has not been selected")
    result_dir = Path(args.output_dir)
    days = sorted({
        file.stem.rsplit("_", 1)[-1]
        for file in Path("predictions").glob("20??/??/??/live/live_predictions_final_*.csv")
        if file.stem.rsplit("_", 1)[-1].isdigit()
    })
    days = [d for d in days if args.from_date <= d <= args.to_date]
    details = []
    skipped = []
    by_date = []
    for day in days:
        live = load_live(day)
        quality_map = verified_signal_quality_by_race(day)
        actual = official_results(day)
        daily = []
        for race_id, observation in sorted(live.items()):
            ranked = sorted(observation, key=lambda b: (int(float(b.get("rank") or 99)), int(float(b.get("boat") or 99))))
            boats = _signal_inputs(ranked)
            quality = quality_map.get(race_id) or {}
            if not signal_field_is_verified(boats, quality):
                skipped.append({"date": day, "race_id": race_id, "reason": "unverified_starters_or_fallback"})
                continue
            if any(row["score"] is None or row["morning_score_reference"] is None for row in boats):
                skipped.append({"date": day, "race_id": race_id, "reason": "missing_score"})
                continue
            # Two independent predictions before touching actual finish or payout.
            fujin = build_down_signal(boats, quality)
            old = build_up_signal(boats, quality, outside_live_top3=True)
            new = build_up_signal(boats, quality, outside_live_top3=False)
            if not (fujin.get("available") and old.get("available") and new.get("available")):
                skipped.append({"date": day, "race_id": race_id, "reason": "signal_not_observable"})
                continue
            fo = int(fujin["level"])
            ol = int(old["level"])
            nl = int(new["level"])
            old_ai = build_signal_ai_prediction(boats, old, fujin, config) if fo or ol else None
            new_ai = build_signal_ai_prediction(boats, new, fujin, config) if fo or nl else None
            old_tickets, old_key = combinations(old_ai)
            new_tickets, new_key = combinations(new_ai)
            if (fo or ol) and len(old_tickets) != 24:
                raise RuntimeError(f"Old signal did not produce 24 picks: {race_id}")
            if (fo or nl) and len(new_tickets) != 24:
                raise RuntimeError(f"New signal did not produce 24 picks: {race_id}")

            # Official results are *only* attached once all signal/ticket calculations finish.
            observed = actual.get(race_id) or {}
            outcome = observed.get("actual")
            payout = int(observed.get("payout") or 0)
            item = {
                "date": day, "race_id": race_id,
                "venue": ranked[0].get("venue_name"), "race": ranked[0].get("race"),
                "provenance": quality.get("provenance") or "saved_csv_unclassified",
                "fujin_level": fo, "old_raijin_level": ol, "new_raijin_level": nl,
                "changed": ol != nl,
                "old_active": bool(fo or ol), "new_active": bool(fo or nl),
                "old_signal_key": old_key, "new_signal_key": new_key,
                "new_raijin_candidates": [
                    {
                        "boat": b["boat"], "rank": b["rank"],
                        "rise": b["rise"], "score": b["score"],
                        "finish": (
                            (outcome.split("-").index(str(b["boat"])) + 1)
                            if outcome and str(b["boat"]) in outcome.split("-") else 4
                        ) if outcome else None,
                    }
                    for b in new["candidates"]
                ],
                "new_top3_rising_candidates": [
                    {"boat": b["boat"], "rank": b["rank"], "rise": b["rise"], "score": b["score"]}
                    for b in new["candidates"] if b["rank"] <= 3
                ],
                "actual": outcome, "payout": payout,
                "old_hit24": outcome in old_tickets if outcome else None,
                "new_hit24": outcome in new_tickets if outcome else None,
                "old_actual_rank": next((i for i, x in enumerate((old_ai or {}).get("all_120_combinations") or [], 1)
                                         if x["combination"] == outcome), None) if outcome else None,
                "new_actual_rank": next((i for i, x in enumerate((new_ai or {}).get("all_120_combinations") or [], 1)
                                         if x["combination"] == outcome), None) if outcome else None,
            }
            daily.append(item)
            details.append(item)
        by_date.append({
            "date": day, "valid_races": len(daily),
            "official_finished_valid": sum(x["actual"] is not None for x in daily),
            "changed_levels": sum(x["changed"] for x in daily),
            "old": summarize(daily, "old"), "new": summarize(daily, "new"),
            "new_by_signal": grouped_signal_pdca(daily, "new"),
            "new_candidate_score_bands": candidate_pdca(daily),
        })

    changes = [x for x in details if x["changed"]]
    summary = {
        "ruleset": SIGNAL_LOGIC["model_version"],
        "scope": {"from": args.from_date, "to": args.to_date, "dates_evaluated": days},
        "research_only": True,
        "retrospective_result_not_original_signal": True,
        "legacy_comparison": "Same Raijin Lv1/Lv2/Lv3 scoring thresholds; ONLY final-rank restriction differs",
        "never_mutate_historical_predictions": True,
        "result_as_input_to_signals": False,
        "valid_races": len(details),
        "excluded_races": len(skipped),
        "changed_raijin_levels": len(changes),
        "transition_counts": dict(sorted(Counter(f'{x["old_raijin_level"]}->{x["new_raijin_level"]}' for x in details).items())),
        "old": summarize(details, "old"),
        "new": summarize(details, "new"),
        "new_by_signal": grouped_signal_pdca(details, "new"),
        "new_candidate_score_bands": candidate_pdca(details),
        "rolling7": {
            "dates": days[-7:],
            "old": summarize([r for r in details if r["date"] in days[-7:]], "old"),
            "new": summarize([r for r in details if r["date"] in days[-7:]], "new"),
            "new_by_signal": grouped_signal_pdca([r for r in details if r["date"] in days[-7:]], "new"),
        },
        "last_completed_date": max((x["date"] for x in details if x["actual"]), default=None),
        "by_date": by_date,
        "known_case_202610112306": next((x for x in details if x["race_id"] == "202610112306"), None),
    }
    result_dir.mkdir(parents=True, exist_ok=True)
    (result_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (result_dir / "skipped.json").write_text(json.dumps(skipped, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_details(result_dir / "details.csv", details)
    # Dedicated corrected daily PDCA data is materialized independently of legacy
    # prediction and historical real-time purchase records.
    for row in by_date:
        date = row["date"]
        day_dir = result_dir / "daily" / date
        day_dir.mkdir(parents=True, exist_ok=True)
        (day_dir / "summary.json").write_text(
            json.dumps({
                "date": date, "ruleset": SIGNAL_LOGIC["model_version"],
                "research_only": True,
                "retrospective_result_not_original_signal": True,
                **row,
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        write_details(day_dir / "details.csv", [x for x in details if x["date"] == date])
    print("RAIJIN_RANKLESS_REPLAY", json.dumps({
        "dates": days, "valid": len(details), "skipped": len(skipped),
        "changed": len(changes), "old": summary["old"], "new": summary["new"],
        "karatsu_6R": summary["known_case_202610112306"],
    }, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
