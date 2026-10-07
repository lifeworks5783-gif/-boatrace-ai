from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


RULE_VERSION = "down_signal_v0_20261007"


def parse_args():
    p = argparse.ArgumentParser(description="暫定下落シグナルの日次・累積評価")
    p.add_argument("--date", required=True, help="YYYYMMDD")
    return p.parse_args()


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def normalize_race_id(value):
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return digits[:12] if len(digits) >= 12 else ""


def read_csv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_actual(row):
    raw = str(
        row.get("trifecta")
        or row.get("3連単_組番")
        or ""
    ).strip().replace("=", "-")
    parts = []
    if raw:
        for x in raw.split("-"):
            try:
                parts.append(int(x))
            except ValueError:
                parts = []
                break
    if len(parts) == 3 and len(set(parts)) == 3:
        return parts

    fallback = []
    for key in ("1着_艇番", "2着_艇番", "3着_艇番"):
        v = to_int(row.get(key))
        if v is None:
            return []
        fallback.append(v)
    return fallback if len(set(fallback)) == 3 else []


def payout_value(row):
    for key in ("trifecta_pay", "3連単_払戻金", "payout"):
        v = to_int(row.get(key))
        if v is not None:
            return v
    return 0


def signal_from_rows(rows):
    ranked = sorted(rows, key=lambda x: to_int(x.get("rank")) or 99)
    if len(ranked) != 6:
        return None

    live_scores = []
    morning_scores = []
    deltas = []
    for row in ranked:
        live = to_float(row.get("score"))
        morning = to_float(row.get("morning_score_reference"))
        if live is None or morning is None:
            return None
        live_scores.append(live)
        morning_scores.append(morning)
        deltas.append(live - morning)

    rank1_delta = deltas[0]
    top3_delta_sum = sum(deltas[:3])
    gap12 = live_scores[0] - live_scores[1]

    criteria = {
        "rank1_drop_5": rank1_delta <= -5.0,
        "top3_total_drop_10": top3_delta_sum <= -10.0,
        "rank1_drop_close_gap": rank1_delta <= -3.0 and gap12 <= 5.0,
    }
    reasons = [key for key, met in criteria.items() if met]

    up10 = any(
        (idx + 1) > 3 and deltas[idx] >= 10.0
        for idx in range(6)
    )
    up75 = any(
        (idx + 1) > 3 and deltas[idx] >= 7.5
        for idx in range(6)
    )

    return {
        "ranked": ranked,
        "deltas": deltas,
        "rank1_delta": round(rank1_delta, 2),
        "top3_delta_sum": round(top3_delta_sum, 2),
        "gap_1_2": round(gap12, 2),
        "criteria": criteria,
        "reasons": reasons,
        "down_level": min(3, len(reasons)),
        "down_active": bool(reasons),
        "up_signal_10": up10,
        "up_candidate_75": up75,
    }


def rate(n, d):
    return round(n * 100.0 / d, 2) if d else None


def group_summary(rows):
    n = len(rows)
    manshu = sum(1 for x in rows if x.get("manshu"))
    pred1_win = sum(1 for x in rows if x.get("pred1_win"))
    pred1_top3 = sum(1 for x in rows if x.get("pred1_top3"))
    winner_rank4 = sum(
        1 for x in rows
        if (x.get("actual_winner_pred_rank") or 0) >= 4
    )
    winner_rank5 = sum(
        1 for x in rows
        if (x.get("actual_winner_pred_rank") or 0) >= 5
    )
    payout_sum = sum(int(x.get("payout") or 0) for x in rows)
    return {
        "races": n,
        "manshu": manshu,
        "manshu_rate_pct": rate(manshu, n),
        "pred1_win_rate_pct": rate(pred1_win, n),
        "pred1_top3_rate_pct": rate(pred1_top3, n),
        "winner_pred_rank4plus_pct": rate(winner_rank4, n),
        "winner_pred_rank5plus_pct": rate(winner_rank5, n),
        "avg_payout": round(payout_sum / n) if n else None,
    }


def summarize(details):
    by_level = {}
    for level in range(4):
        by_level[str(level)] = group_summary(
            [x for x in details if int(x.get("down_level") or 0) == level]
        )

    active = [x for x in details if x.get("down_active")]
    inactive = [x for x in details if not x.get("down_active")]

    criteria = {}
    for key in (
        "rank1_drop_5",
        "top3_total_drop_10",
        "rank1_drop_close_gap",
    ):
        rows = [
            x for x in details
            if key in (x.get("down_reasons") or [])
        ]
        criteria[key] = group_summary(rows)

    interaction_10 = {
        "neither": group_summary([
            x for x in details
            if not x.get("down_active") and not x.get("up_signal_10")
        ]),
        "down_only": group_summary([
            x for x in details
            if x.get("down_active") and not x.get("up_signal_10")
        ]),
        "up_only": group_summary([
            x for x in details
            if not x.get("down_active") and x.get("up_signal_10")
        ]),
        "both": group_summary([
            x for x in details
            if x.get("down_active") and x.get("up_signal_10")
        ]),
    }

    interaction_75 = {
        "neither": group_summary([
            x for x in details
            if not x.get("down_active") and not x.get("up_candidate_75")
        ]),
        "down_only": group_summary([
            x for x in details
            if x.get("down_active") and not x.get("up_candidate_75")
        ]),
        "up_only": group_summary([
            x for x in details
            if not x.get("down_active") and x.get("up_candidate_75")
        ]),
        "both": group_summary([
            x for x in details
            if x.get("down_active") and x.get("up_candidate_75")
        ]),
    }

    return {
        "all": group_summary(details),
        "down_active": group_summary(active),
        "down_inactive": group_summary(inactive),
        "by_level": by_level,
        "by_criterion": criteria,
        "interaction_with_up10": interaction_10,
        "interaction_with_up75": interaction_75,
    }


def write_details_csv(path, details):
    fields = [
        "date", "race_id", "venue", "race",
        "down_active", "down_level", "down_reasons",
        "rank1_delta", "top3_delta_sum", "gap_1_2",
        "up_signal_10", "up_candidate_75",
        "pred1_boat", "pred1_win", "pred1_top3",
        "actual_winner", "actual_winner_pred_rank",
        "payout", "manshu",
    ]
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in details:
            out = dict(row)
            out["down_reasons"] = "|".join(row.get("down_reasons") or [])
            w.writerow({key: out.get(key) for key in fields})


def main():
    args = parse_args()
    d = args.date
    y, m, day = d[:4], d[4:6], d[6:8]

    live_path = Path("predictions") / y / m / day / "live" / f"live_predictions_final_{d}.csv"
    result_path = Path("archive") / y / m / day / f"results_{d}_all.csv"
    if not live_path.is_file():
        raise RuntimeError(f"直前予測CSVがありません: {live_path}")
    if not result_path.is_file():
        raise RuntimeError(f"結果CSVがありません: {result_path}")

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
    for race_id, rows in sorted(grouped.items()):
        result = results.get(race_id)
        if result is None:
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
        rank_by_boat = {
            to_int(row.get("boat")): idx + 1
            for idx, row in enumerate(ranked)
            if to_int(row.get("boat")) is not None
        }
        payout = payout_value(result)
        venue = str(
            ranked[0].get("venue_name")
            or result.get("venue_name")
            or ""
        ).strip()
        race_no = to_int(
            ranked[0].get("race")
            or result.get("race")
        )

        details.append({
            "date": d,
            "race_id": race_id,
            "venue": venue,
            "race": race_no,
            "down_active": sig["down_active"],
            "down_level": sig["down_level"],
            "down_reasons": sig["reasons"],
            "rank1_delta": sig["rank1_delta"],
            "top3_delta_sum": sig["top3_delta_sum"],
            "gap_1_2": sig["gap_1_2"],
            "up_signal_10": sig["up_signal_10"],
            "up_candidate_75": sig["up_candidate_75"],
            "pred1_boat": pred1_boat,
            "pred1_win": pred1_boat == actual[0],
            "pred1_top3": pred1_boat in actual,
            "actual_winner": actual[0],
            "actual_winner_pred_rank": rank_by_boat.get(actual[0]),
            "payout": payout,
            "manshu": payout >= 10000,
        })

    out_dir = Path("evaluations") / y / m / day
    out_dir.mkdir(parents=True, exist_ok=True)
    daily_json = out_dir / f"down_signal_analysis_{d}.json"
    daily_csv = out_dir / f"down_signal_analysis_{d}.csv"

    payload = {
        "date": d,
        "rule_version": RULE_VERSION,
        "status": "provisional_analysis_only",
        "ai_effect": False,
        "formation_effect": False,
        "rules": {
            "one_mark_each": [
                "rank1_delta <= -5.0",
                "top3_delta_sum <= -10.0",
                "rank1_delta <= -3.0 and gap_1_2 <= 5.0",
            ],
            "max_level": 3,
        },
        "skipped_incomplete_races": skipped,
        "summary": summarize(details),
        "details": details,
    }
    daily_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_details_csv(daily_csv, details)

    cumulative = []
    for path in sorted(Path("evaluations").glob("????/??/??/down_signal_analysis_????????.json")):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for row in item.get("details") or []:
            key = (str(row.get("date")), str(row.get("race_id")))
            cumulative.append((key, row))

    dedup = {}
    for key, row in cumulative:
        dedup[key] = row
    cumulative_details = [
        dedup[key]
        for key in sorted(dedup)
    ]

    latest_dir = Path("evaluations") / "down_signal" / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    latest_payload = {
        "rule_version": RULE_VERSION,
        "status": "provisional_analysis_only",
        "dates": sorted({str(x.get("date")) for x in cumulative_details if x.get("date")}),
        "summary": summarize(cumulative_details),
        "details": cumulative_details,
    }
    (latest_dir / "summary.json").write_text(
        json.dumps(latest_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_details_csv(latest_dir / "details.csv", cumulative_details)

    print(json.dumps({
        "date": d,
        "evaluated_races": len(details),
        "down_signal_races": sum(1 for x in details if x["down_active"]),
        "manshu": sum(1 for x in details if x["manshu"]),
        "daily_json": str(daily_json),
        "latest_json": str(latest_dir / "summary.json"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
