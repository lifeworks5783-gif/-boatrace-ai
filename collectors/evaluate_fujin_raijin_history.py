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
    resolve_analysis_live_path,
    signal_from_rows,
    to_int,
)


SYSTEM_NAME = "風神雷神シグナル"
BACKTEST_VERSION = "fujin_raijin_combo_backtest_v2_20261007"


def parse_args():
    p = argparse.ArgumentParser(
        description="現行の風神雷神シグナル判定を保存済み結果前予測へ適用し、組み合わせ別・累積で検証"
    )
    p.add_argument("--date", required=False, help="日次PDCA対象日 YYYYMMDD。省略時は最新評価可能日")
    return p.parse_args()


def pct(n, d):
    return round(n * 100.0 / d, 2) if d else None


def label(level, name):
    return f"{name}なし" if level == 0 else f"{name}Lv{level}"


def group_stats(rows, total_races):
    payouts = [int(x.get("payout") or 0) for x in rows]
    n = len(rows)
    p5 = sum(1 for p in payouts if p >= 5000)
    manshu = sum(1 for x in rows if x.get("manshu"))
    p30 = sum(1 for p in payouts if p >= 30000)
    p50 = sum(1 for p in payouts if p >= 50000)
    return {
        "races": n,
        "activation_rate_pct": pct(n, total_races),
        "payout_5000plus": p5,
        "payout_5000plus_rate_pct": pct(p5, n),
        "manshu": manshu,
        "manshu_rate_pct": pct(manshu, n),
        "avg_payout": round(sum(payouts) / n) if n else None,
        "median_payout": round(statistics.median(payouts)) if payouts else None,
        "payout_30000plus": p30,
        "payout_30000plus_rate_pct": pct(p30, n),
        "payout_50000plus": p50,
        "payout_50000plus_rate_pct": pct(p50, n),
    }


def summarize(details):
    total = len(details)

    presence = {
        "neither": group_stats(
            [x for x in details if x["fujin_level"] == 0 and x["raijin_level"] == 0],
            total,
        ),
        "fujin_only": group_stats(
            [x for x in details if x["fujin_level"] > 0 and x["raijin_level"] == 0],
            total,
        ),
        "raijin_only": group_stats(
            [x for x in details if x["fujin_level"] == 0 and x["raijin_level"] > 0],
            total,
        ),
        "both": group_stats(
            [x for x in details if x["fujin_level"] > 0 and x["raijin_level"] > 0],
            total,
        ),
        "any_signal": group_stats(
            [x for x in details if x["fujin_level"] > 0 or x["raijin_level"] > 0],
            total,
        ),
    }

    combinations = {}
    for f_level in range(4):
        for r_level in range(4):
            key = f"F{f_level}_R{r_level}"
            rows = [
                x for x in details
                if x["fujin_level"] == f_level and x["raijin_level"] == r_level
            ]
            combinations[key] = {
                "label": f"{label(f_level, '風神')} × {label(r_level, '雷神')}",
                "fujin_level": f_level,
                "raijin_level": r_level,
                **group_stats(rows, total),
            }

    fujin_levels = {
        str(level): group_stats(
            [x for x in details if x["fujin_level"] == level],
            total,
        )
        for level in range(4)
    }
    raijin_levels = {
        str(level): group_stats(
            [x for x in details if x["raijin_level"] == level],
            total,
        )
        for level in range(4)
    }

    payout_5000plus_total = sum(1 for x in details if int(x.get("payout") or 0) >= 5000)
    signal_rows = [x for x in details if x["fujin_level"] > 0 or x["raijin_level"] > 0]
    signal_5000plus = sum(1 for x in signal_rows if int(x.get("payout") or 0) >= 5000)
    no_signal_rows = [x for x in details if x["fujin_level"] == 0 and x["raijin_level"] == 0]
    no_signal_5000plus = sum(1 for x in no_signal_rows if int(x.get("payout") or 0) >= 5000)

    return {
        "all": group_stats(details, total),
        "payout_5000_signal_summary": {
            "payout_5000plus_total": payout_5000plus_total,
            "signal_active_races": len(signal_rows),
            "signal_5000plus": signal_5000plus,
            "signal_5000plus_rate_pct": pct(signal_5000plus, len(signal_rows)),
            "signal_capture_rate_of_all_5000plus_pct": pct(signal_5000plus, payout_5000plus_total),
            "no_signal_races": len(no_signal_rows),
            "no_signal_5000plus": no_signal_5000plus,
            "no_signal_5000plus_rate_pct": pct(no_signal_5000plus, len(no_signal_rows)),
        },
        "presence": presence,
        "fujin_levels": fujin_levels,
        "raijin_levels": raijin_levels,
        "combinations": combinations,
    }


def evaluate_date(d):
    y, m, day = d[:4], d[4:6], d[6:8]
    production_live_path = Path("predictions") / y / m / day / "live" / f"live_predictions_final_{d}.csv"
    result_path = Path("archive") / y / m / day / f"results_{d}_all.csv"
    if not production_live_path.is_file() or not result_path.is_file():
        return [], {
            "date": d,
            "status": "missing_input",
            "live_exists": production_live_path.is_file(),
            "result_exists": result_path.is_file(),
        }

    live_path, _ = resolve_analysis_live_path(d, production_live_path)
    live_rows = read_csv(live_path)
    result_rows = read_csv(result_path)

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
    no_result = 0

    for race_id, rows in sorted(grouped.items()):
        result = results.get(race_id)
        if result is None:
            no_result += 1
            continue

        sig = signal_from_rows(rows)
        if sig is None:
            skipped.append(race_id)
            continue

        actual = parse_actual(result)
        if len(actual) != 3:
            continue

        ranked = sig["ranked"]
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
            "raijin_level": int(sig.get("raijin_level") or 0),
            "fujin_active": bool(sig.get("down_active")),
            "raijin_active": int(sig.get("raijin_level") or 0) > 0,
            "fujin_reasons": sig.get("reasons") or [],
            "rank1_delta": sig.get("rank1_delta"),
            "top3_delta_sum": sig.get("top3_delta_sum"),
            "gap_1_2": sig.get("gap_1_2"),
            "raijin_max_rise": sig.get("raijin_max_rise"),
            "payout": payout,
            "payout_5000plus": payout >= 5000,
            "manshu": payout >= 10000,
        })

    return details, {
        "date": d,
        "status": "ok",
        "saved_prediction_races": len(grouped),
        "evaluated_races": len(details),
        "skipped_incomplete_prediction_races": skipped,
        "saved_prediction_races_without_result": no_result,
    }


def discover_dates():
    dates = []
    for p in Path("predictions").glob("????/??/??/live/live_predictions_final_????????.csv"):
        stem = p.stem
        d = stem.rsplit("_", 1)[-1]
        if len(d) != 8 or not d.isdigit():
            continue
        y, m, day = d[:4], d[4:6], d[6:8]
        result_path = Path("archive") / y / m / day / f"results_{d}_all.csv"
        if result_path.is_file():
            dates.append(d)
    return sorted(set(dates))


def write_details_csv(path, rows):
    fields = [
        "date", "race_id", "venue", "race",
        "fujin_level", "raijin_level",
        "fujin_active", "raijin_active",
        "fujin_reasons",
        "rank1_delta", "top3_delta_sum", "gap_1_2",
        "raijin_max_rise", "payout", "payout_5000plus", "manshu",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            out = dict(row)
            out["fujin_reasons"] = "|".join(row.get("fujin_reasons") or [])
            w.writerow({k: out.get(k) for k in fields})


def write_matrix_csv(path, summary):
    fields = [
        "key", "label", "fujin_level", "raijin_level",
        "races", "activation_rate_pct",
        "payout_5000plus", "payout_5000plus_rate_pct",
        "manshu", "manshu_rate_pct",
        "avg_payout", "median_payout",
        "payout_30000plus", "payout_30000plus_rate_pct",
        "payout_50000plus", "payout_50000plus_rate_pct",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for key, stats in summary["combinations"].items():
            w.writerow({
                "key": key,
                "label": stats["label"],
                "fujin_level": stats["fujin_level"],
                "raijin_level": stats["raijin_level"],
                "races": stats["races"],
                "activation_rate_pct": stats["activation_rate_pct"],
                "payout_5000plus": stats["payout_5000plus"],
                "payout_5000plus_rate_pct": stats["payout_5000plus_rate_pct"],
                "manshu": stats["manshu"],
                "manshu_rate_pct": stats["manshu_rate_pct"],
                "avg_payout": stats["avg_payout"],
                "median_payout": stats["median_payout"],
                "payout_30000plus": stats["payout_30000plus"],
                "payout_30000plus_rate_pct": stats["payout_30000plus_rate_pct"],
                "payout_50000plus": stats["payout_50000plus"],
                "payout_50000plus_rate_pct": stats["payout_50000plus_rate_pct"],
            })


def main():
    args = parse_args()
    dates = discover_dates()
    if not dates:
        raise RuntimeError("風神雷神バックテストに使える保存済み直前予測＋結果の組がありません")

    target_date = args.date or dates[-1]
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

    total_summary = summarize(all_details)

    latest_dir = Path("evaluations") / "fujin_raijin" / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "system_name": SYSTEM_NAME,
        "backtest_version": BACKTEST_VERSION,
        "signal_rule_version": RULE_VERSION,
        "status": "analysis_only",
        "prediction_effect": False,
        "formation_effect": False,
        "method": {
            "description": "保存済みの結果判明前の直前予測スコアへ、現行の風神雷神シグナル判定ルールを後適用するリーク防止バックテスト",
            "base_prediction_recalculated_with_latest_weights": False,
            "uses_saved_pre_result_prediction_scores": True,
            "result_used_only_for_settlement": True,
        },
        "rules": {
            "fujin": {
                "one_mark_each": [
                    "rank1_delta <= -5.0",
                    "top3_delta_sum <= -10.0",
                    "rank1_delta <= -3.0 and gap_1_2 <= 5.0",
                ],
                "level": "成立条件数をLv1-Lv3として扱う",
            },
            "raijin": {
                "level1": "直前TOP3外の最大上昇 >= 7.5 and < 10.0",
                "level2": "直前TOP3外の最大上昇 >= 10.0 and < 12.5",
                "level3": "直前TOP3外の最大上昇 >= 12.5",
            },
        },
        "analyzable_dates": dates,
        "date_count": len(per_date),
        "evaluated_races": len(all_details),
        "coverage": coverage,
        "total": total_summary,
        "per_date": per_date,
    }

    (latest_dir / "backtest_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_details_csv(latest_dir / "backtest_details.csv", all_details)
    write_matrix_csv(latest_dir / "combination_matrix.csv", total_summary)

    target_rows = [x for x in all_details if x["date"] == target_date]
    if target_rows:
        y, m, day = target_date[:4], target_date[4:6], target_date[6:8]
        daily_dir = Path("evaluations") / y / m / day
        daily_dir.mkdir(parents=True, exist_ok=True)
        daily_summary = summarize(target_rows)
        daily_payload = {
            "date": target_date,
            "system_name": SYSTEM_NAME,
            "backtest_version": BACKTEST_VERSION,
            "signal_rule_version": RULE_VERSION,
            "prediction_effect": False,
            "formation_effect": False,
            "summary": daily_summary,
        }
        (daily_dir / f"fujin_raijin_combo_{target_date}.json").write_text(
            json.dumps(daily_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        write_matrix_csv(
            daily_dir / f"fujin_raijin_combo_{target_date}.csv",
            daily_summary,
        )

    print(json.dumps({
        "system_name": SYSTEM_NAME,
        "target_date": target_date,
        "analyzable_dates": dates,
        "date_count": len(per_date),
        "evaluated_races": len(all_details),
        "neither": total_summary["presence"]["neither"],
        "both": total_summary["presence"]["both"],
        "summary_json": str(latest_dir / "backtest_summary.json"),
        "matrix_csv": str(latest_dir / "combination_matrix.csv"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
