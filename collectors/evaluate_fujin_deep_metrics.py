from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

from evaluate_down_signal import (
    RULE_VERSION,
    normalize_race_id,
    parse_actual,
    payout_value,
    read_csv,
    signal_from_rows,
    to_float,
    to_int,
)


VERSION = "fujin_deep_metrics_v1_20261008"
SYSTEM_NAME = "風神詳細PDCA"
CRITERIA_KEYS = (
    "rank1_drop_5",
    "top3_total_drop_10",
    "rank1_drop_close_gap",
)


def parse_args():
    p = argparse.ArgumentParser(
        description="風神を条件別・閾値別・新雷神との組み合わせ別に日次/累積評価"
    )
    p.add_argument("--date", required=True, help="YYYYMMDD")
    return p.parse_args()


def pct(n, d):
    return round(n * 100.0 / d, 2) if d else None


def saved_live_path(d):
    y, m, day = d[:4], d[4:6], d[6:8]
    merged = (
        Path("evaluations") / y / m / day / "recovery"
        / f"merged_live_predictions_{d}.csv"
    )
    if merged.is_file():
        return merged
    return (
        Path("predictions") / y / m / day / "live"
        / f"live_predictions_final_{d}.csv"
    )


def result_path(d):
    return (
        Path("archive") / d[:4] / d[4:6] / d[6:8]
        / f"results_{d}_all.csv"
    )


def discover_dates():
    found = set()
    for p in Path("predictions").glob(
        "????/??/??/live/live_predictions_final_????????.csv"
    ):
        d = p.stem.rsplit("_", 1)[-1]
        if len(d) == 8 and d.isdigit() and result_path(d).is_file():
            found.add(d)
    for p in Path("evaluations").glob(
        "????/??/??/recovery/merged_live_predictions_????????.csv"
    ):
        d = p.stem.rsplit("_", 1)[-1]
        if len(d) == 8 and d.isdigit() and result_path(d).is_file():
            found.add(d)
    return sorted(found)


def group_stats(rows, total=None):
    n = len(rows)
    total = n if total is None else total
    payouts = [int(x.get("payout") or 0) for x in rows]
    p5 = sum(1 for p in payouts if p >= 5000)
    manshu = sum(1 for p in payouts if p >= 10000)
    p30 = sum(1 for p in payouts if p >= 30000)
    p50 = sum(1 for p in payouts if p >= 50000)
    pred1_win = sum(1 for x in rows if x.get("pred1_win"))
    pred1_top3 = sum(1 for x in rows if x.get("pred1_top3"))
    winner_rank4 = sum(
        1 for x in rows
        if int(x.get("actual_winner_pred_rank") or 0) >= 4
    )
    return {
        "races": n,
        "share_pct": pct(n, total),
        "pred1_win": pred1_win,
        "pred1_win_rate_pct": pct(pred1_win, n),
        "pred1_top3": pred1_top3,
        "pred1_top3_rate_pct": pct(pred1_top3, n),
        "winner_pred_rank4plus": winner_rank4,
        "winner_pred_rank4plus_pct": pct(winner_rank4, n),
        "payout_5000plus": p5,
        "payout_5000plus_rate_pct": pct(p5, n),
        "manshu": manshu,
        "manshu_rate_pct": pct(manshu, n),
        "payout_30000plus": p30,
        "payout_30000plus_rate_pct": pct(p30, n),
        "payout_50000plus": p50,
        "payout_50000plus_rate_pct": pct(p50, n),
        "avg_payout": round(sum(payouts) / n) if n else None,
        "median_payout": round(statistics.median(payouts)) if payouts else None,
        "avg_rank1_delta": (
            round(sum(float(x["rank1_delta"]) for x in rows) / n, 2)
            if n else None
        ),
        "avg_gap_1_2": (
            round(sum(float(x["gap_1_2"]) for x in rows) / n, 2)
            if n else None
        ),
    }


def exact_reason_key(row):
    reasons = [k for k in CRITERIA_KEYS if k in (row.get("fujin_reasons") or [])]
    return "+".join(reasons) if reasons else "none"


def threshold_grid(details):
    rows = []
    for drop in (2, 3, 4, 5, 6, 7):
        for gap in (2, 3, 4, 5, 6):
            subset = [
                x for x in details
                if float(x["rank1_delta"]) <= -float(drop)
                and float(x["gap_1_2"]) <= float(gap)
            ]
            rows.append({
                "rank1_drop_at_least": drop,
                "gap_1_2_max": gap,
                **group_stats(subset, len(details)),
            })
    return rows


def binned(details, key, bins):
    out = []
    for label, lo, hi in bins:
        subset = []
        for x in details:
            value = float(x[key])
            if lo is not None and value < lo:
                continue
            if hi is not None and value >= hi:
                continue
            subset.append(x)
        out.append({
            "label": label,
            "min_inclusive": lo,
            "max_exclusive": hi,
            **group_stats(subset, len(details)),
        })
    return out


def summarize(details):
    total = len(details)
    active = [x for x in details if int(x["fujin_level"]) > 0]

    by_level = {
        str(level): group_stats(
            [x for x in details if int(x["fujin_level"]) == level],
            total,
        )
        for level in range(4)
    }

    by_criterion = {
        key: group_stats(
            [x for x in details if key in (x.get("fujin_reasons") or [])],
            total,
        )
        for key in CRITERIA_KEYS
    }

    exact = {}
    for row in details:
        exact.setdefault(exact_reason_key(row), [])
        exact[exact_reason_key(row)].append(row)
    exact = {
        key: group_stats(rows, total)
        for key, rows in sorted(exact.items())
    }

    cross = {}
    for f_level in range(4):
        for r_level in range(4):
            rows = [
                x for x in details
                if int(x["fujin_level"]) == f_level
                and int(x["raijin_level"]) == r_level
            ]
            cross[f"F{f_level}_R{r_level}"] = group_stats(rows, total)

    pred1_score_bands = binned(
        active,
        "pred1_score",
        (
            ("<50", None, 50),
            ("50-60", 50, 60),
            ("60-70", 60, 70),
            ("70-80", 70, 80),
            ("80+", 80, None),
        ),
    )

    rank1_delta_bins = binned(
        details,
        "rank1_delta",
        (
            ("<-12", None, -12),
            ("-12 to -8", -12, -8),
            ("-8 to -5", -8, -5),
            ("-5 to -3", -5, -3),
            ("-3 to 0", -3, 0),
            ("0+", 0, None),
        ),
    )

    top3_delta_bins = binned(
        details,
        "top3_delta_sum",
        (
            ("<-20", None, -20),
            ("-20 to -15", -20, -15),
            ("-15 to -10", -15, -10),
            ("-10 to -5", -10, -5),
            ("-5 to 0", -5, 0),
            ("0+", 0, None),
        ),
    )

    research_zones = {
        "axis_danger_drop5_gap3": group_stats([
            x for x in details
            if float(x["rank1_delta"]) <= -5.0
            and float(x["gap_1_2"]) <= 3.0
        ], total),
        "axis_danger_drop4_gap3": group_stats([
            x for x in details
            if float(x["rank1_delta"]) <= -4.0
            and float(x["gap_1_2"]) <= 3.0
        ], total),
        "f2_r0_axis_hold_widen": group_stats([
            x for x in details
            if int(x["fujin_level"]) == 2
            and int(x["raijin_level"]) == 0
        ], total),
        "f2_r2_axis_weaken_high_payout": group_stats([
            x for x in details
            if int(x["fujin_level"]) == 2
            and int(x["raijin_level"]) == 2
        ], total),
        "fujin_with_raijin3": group_stats([
            x for x in details
            if int(x["fujin_level"]) > 0
            and int(x["raijin_level"]) == 3
        ], total),
    }

    return {
        "all": group_stats(details, total),
        "fujin_active": group_stats(active, total),
        "by_fujin_level": by_level,
        "by_fujin_criterion": by_criterion,
        "by_exact_criterion_combination": exact,
        "fujin_x_new_raijin": cross,
        "rank1_delta_bins": rank1_delta_bins,
        "top3_delta_bins": top3_delta_bins,
        "pred1_score_bands_when_fujin_active": pred1_score_bands,
        "close_gap_threshold_grid": threshold_grid(details),
        "research_zones": research_zones,
    }


def evaluate_date(d):
    live_path = saved_live_path(d)
    results_path = result_path(d)
    if not live_path.is_file() or not results_path.is_file():
        return [], {
            "date": d,
            "status": "missing_input",
            "live_path": str(live_path),
            "result_path": str(results_path),
        }

    live_rows = read_csv(live_path)
    result_rows = read_csv(results_path)

    grouped = defaultdict(list)
    for row in live_rows:
        race_id = normalize_race_id(row.get("race_id"))
        if race_id:
            grouped[race_id].append(row)

    results = {}
    for row in result_rows:
        race_id = normalize_race_id(row.get("race_id") or row.get("レースコード"))
        if race_id:
            results[race_id] = row

    details = []
    skipped = []
    missing_result = 0

    for race_id, rows in sorted(grouped.items()):
        result = results.get(race_id)
        if result is None:
            missing_result += 1
            continue

        sig = signal_from_rows(rows)
        if sig is None:
            skipped.append(race_id)
            continue

        actual = parse_actual(result)
        if len(actual) != 3:
            continue

        ranked = sig["ranked"]
        pred1_boat = to_int(ranked[0].get("boat"))
        pred1_score = to_float(ranked[0].get("score"))
        rank_by_boat = {
            to_int(row.get("boat")): idx + 1
            for idx, row in enumerate(ranked)
            if to_int(row.get("boat")) is not None
        }
        payout = payout_value(result)

        details.append({
            "date": d,
            "race_id": race_id,
            "venue": str(
                ranked[0].get("venue_name")
                or result.get("venue_name")
                or ""
            ).strip(),
            "race": to_int(ranked[0].get("race") or result.get("race")),
            "fujin_level": int(sig.get("down_level") or 0),
            "fujin_active": bool(sig.get("down_active")),
            "fujin_reasons": list(sig.get("reasons") or []),
            "rank1_delta": float(sig.get("rank1_delta") or 0.0),
            "top3_delta_sum": float(sig.get("top3_delta_sum") or 0.0),
            "gap_1_2": float(sig.get("gap_1_2") or 0.0),
            "pred1_boat": pred1_boat,
            "pred1_score": pred1_score,
            "pred1_win": pred1_boat == actual[0],
            "pred1_top3": pred1_boat in actual,
            "actual_winner": actual[0],
            "actual_second": actual[1],
            "actual_third": actual[2],
            "actual_winner_pred_rank": rank_by_boat.get(actual[0]),
            "raijin_level": int(sig.get("raijin_level") or 0),
            "raijin_max_rise": sig.get("raijin_max_rise"),
            "raijin_has_score50": bool(sig.get("raijin_has_score50")),
            "raijin_candidates": list(sig.get("raijin_candidates") or []),
            "payout": payout,
            "payout_5000plus": payout >= 5000,
            "manshu": payout >= 10000,
            "payout_30000plus": payout >= 30000,
            "payout_50000plus": payout >= 50000,
        })

    return details, {
        "date": d,
        "status": "ok",
        "live_path": str(live_path),
        "saved_prediction_races": len(grouped),
        "evaluated_races": len(details),
        "skipped_incomplete_prediction_races": skipped,
        "saved_prediction_races_without_result": missing_result,
    }


def write_details_csv(path, rows):
    fields = [
        "date", "race_id", "venue", "race",
        "fujin_level", "fujin_active", "fujin_reasons",
        "rank1_delta", "top3_delta_sum", "gap_1_2",
        "pred1_boat", "pred1_score", "pred1_win", "pred1_top3",
        "actual_winner", "actual_second", "actual_third",
        "actual_winner_pred_rank",
        "raijin_level", "raijin_max_rise", "raijin_has_score50",
        "raijin_candidates",
        "payout", "payout_5000plus", "manshu",
        "payout_30000plus", "payout_50000plus",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            out = dict(row)
            out["fujin_reasons"] = "|".join(row.get("fujin_reasons") or [])
            out["raijin_candidates"] = json.dumps(
                row.get("raijin_candidates") or [],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            w.writerow({key: out.get(key) for key in fields})


def write_threshold_csv(path, rows):
    fields = [
        "rank1_drop_at_least", "gap_1_2_max",
        "races", "share_pct",
        "pred1_win_rate_pct", "pred1_top3_rate_pct",
        "winner_pred_rank4plus_pct",
        "payout_5000plus_rate_pct", "manshu_rate_pct",
        "payout_30000plus_rate_pct", "payout_50000plus_rate_pct",
        "avg_payout", "median_payout",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k) for k in fields})


def main():
    args = parse_args()
    target_date = args.date
    dates = discover_dates()
    if not dates:
        raise RuntimeError("風神詳細分析に使える保存済み直前予測＋結果がありません")

    all_details = []
    coverage = []
    per_date = {}

    for d in dates:
        rows, meta = evaluate_date(d)
        coverage.append(meta)
        if meta["status"] != "ok":
            continue
        all_details.extend(rows)
        per_date[d] = summarize(rows)

    cumulative_summary = summarize(all_details)

    latest_dir = Path("evaluations") / "fujin_deep" / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "system_name": SYSTEM_NAME,
        "version": VERSION,
        "signal_rule_version": RULE_VERSION,
        "status": "analysis_only",
        "prediction_effect": False,
        "formation_effect": False,
        "method": {
            "uses_saved_pre_result_prediction_scores": True,
            "result_used_only_for_settlement": True,
            "recollection": False,
            "raijin_definition": "new score-qualified Lv3 adopted 2026-10-08",
            "purpose": "風神Lv・条件・閾値・新雷神との交差を日々固定観測する",
        },
        "tracked_items": [
            "風神Lv0-Lv3",
            "3条件の単独/複合",
            "予測1位の朝比低下量",
            "直前1位-2位スコア差",
            "TOP3合計朝比",
            "予測1位の直前スコア帯",
            "予測1位の1着率/3着以内率/実着",
            "5000円以上/万舟/3万円以上/5万円以上",
            "新雷神Lv0-Lv3との組み合わせ",
            "軸危険候補 -5&gap3 / -4&gap3",
            "F2R0 / F2R2 / 風神+新雷神Lv3",
        ],
        "dates": dates,
        "date_count": len(per_date),
        "evaluated_races": len(all_details),
        "coverage": coverage,
        "summary": cumulative_summary,
        "per_date": per_date,
    }

    (latest_dir / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_details_csv(latest_dir / "details.csv", all_details)
    write_threshold_csv(
        latest_dir / "close_gap_threshold_grid.csv",
        cumulative_summary["close_gap_threshold_grid"],
    )

    target_rows = [x for x in all_details if x["date"] == target_date]
    if target_rows:
        y, m, day = target_date[:4], target_date[4:6], target_date[6:8]
        daily_dir = Path("evaluations") / y / m / day
        daily_summary = summarize(target_rows)
        daily_payload = {
            "date": target_date,
            "system_name": SYSTEM_NAME,
            "version": VERSION,
            "signal_rule_version": RULE_VERSION,
            "status": "analysis_only",
            "prediction_effect": False,
            "formation_effect": False,
            "summary": daily_summary,
            "details": target_rows,
        }
        (daily_dir / f"fujin_deep_analysis_{target_date}.json").write_text(
            json.dumps(daily_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        write_details_csv(
            daily_dir / f"fujin_deep_analysis_{target_date}.csv",
            target_rows,
        )
        write_threshold_csv(
            daily_dir / f"fujin_close_gap_grid_{target_date}.csv",
            daily_summary["close_gap_threshold_grid"],
        )

    print(json.dumps({
        "system_name": SYSTEM_NAME,
        "target_date": target_date,
        "signal_rule_version": RULE_VERSION,
        "date_count": len(per_date),
        "evaluated_races": len(all_details),
        "target_races": len(target_rows),
        "latest_summary": str(latest_dir / "summary.json"),
        "latest_details": str(latest_dir / "details.csv"),
        "prediction_changed": False,
        "formation_changed": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
