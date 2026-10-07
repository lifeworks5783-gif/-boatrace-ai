from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


JST = timezone(timedelta(hours=9))
BET_YEN_PER_COMBINATION = 100


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "朝予測・直前予測・フォーメーション・"
            "上位3艇BOXを実結果と比較"
        )
    )
    parser.add_argument("--date", required=True)
    parser.add_argument("--require-live", action="store_true")
    return parser.parse_args()


def text(value):
    return "" if value is None else str(value).strip()


def to_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def to_int(value):
    number = to_float(value)
    return None if number is None else int(number)


def finish_number(value):
    raw = text(value)
    if raw.isdigit():
        number = int(raw)
        if 1 <= number <= 6:
            return number
    return None


def canonical_race_id(value):
    return "".join(re.findall(r"\d", text(value)))


def mean(values):
    return None if not values else sum(values) / len(values)


def rate(numerator, denominator):
    return None if not denominator else numerator / denominator


def rounded(value, digits=5):
    return None if value is None else round(value, digits)


def load_json(path, required=True):
    path = Path(path)
    if not path.exists():
        if required:
            raise RuntimeError(f"ファイルがありません: {path}")
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_official_miss_boats(target_date):
    """締切前beforeinfoで欠場扱い(is_miss)だった艇だけを返す。"""
    y, m, day = target_date[:4], target_date[4:6], target_date[6:8]
    live_root = Path("daily_inputs") / y / m / day / "live"
    misses = defaultdict(set)
    if not live_root.exists():
        return misses

    for path in sorted(live_root.glob("**/beforeinfo_entries_*.csv")):
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    flag = str(row.get("is_miss") or "").strip().lower()
                    if flag not in {"true", "1", "yes"}:
                        continue
                    race_key = canonical_race_id(row.get("race_id"))
                    boat = to_int(row.get("boat"))
                    if race_key and boat is not None:
                        misses[race_key].add(boat)
        except Exception:
            continue
    return misses


def load_analysis_live_payload(target_date, production_payload):
    """AI分析用に安全確認済みの欠損復旧直前予測があれば使用する。"""
    y, m, day = target_date[:4], target_date[4:6], target_date[6:8]
    recovery_dir = Path("evaluations") / y / m / day / "recovery"
    merged_path = recovery_dir / f"merged_live_predictions_{target_date}.csv"
    manifest_path = recovery_dir / f"live_recovery_manifest_{target_date}.json"

    if not merged_path.is_file() or not manifest_path.is_file():
        return production_payload, "production_live_json", None

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return production_payload, "production_live_json", None

    safe_recovery = (
        manifest.get("status") == "complete"
        and manifest.get("treat_recovered_as_observation") is True
        and manifest.get("result_leakage") is False
        and not (manifest.get("still_missing") or [])
    )
    if not safe_recovery:
        return production_payload, "production_live_json", manifest

    grouped = defaultdict(list)
    with merged_path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            race_key = canonical_race_id(row.get("race_id"))
            if race_key:
                grouped[race_key].append(row)

    official_misses = load_official_miss_boats(target_date)

    expected = to_int(manifest.get("merged_analysis_races"))
    if expected is not None and len(grouped) != expected:
        return production_payload, "production_live_json", manifest

    races = []
    for race_key in sorted(grouped):
        boat_rows = grouped[race_key]
        boat_rows.sort(
            key=lambda row: (
                to_int(row.get("rank")) or 99,
                -(to_float(row.get("score")) or 0),
                to_int(row.get("boat")) or 99,
            )
        )
        present_boats = {
            to_int(row.get("boat"))
            for row in boat_rows
            if to_int(row.get("boat")) is not None
        }
        missing_boats = sorted(set(range(1, 7)) - present_boats)
        allowed_missing = official_misses.get(race_key, set())

        # 通常は6艇必須。5艇以下を認めるのは、締切前beforeinfoで
        # is_miss=True と記録された欠場艇だけ。
        if len(boat_rows) < 3 or any(boat not in allowed_missing for boat in missing_boats):
            return production_payload, "production_live_json", manifest
        if len(boat_rows) + len(missing_boats) != 6:
            return production_payload, "production_live_json", manifest

        first = boat_rows[0]
        races.append(
            {
                "race_id": first.get("race_id"),
                "venue_code": first.get("venue_code"),
                "venue_name": first.get("venue_name"),
                "race": to_int(first.get("race")),
                "deadline": first.get("deadline"),
                "prediction_type": "live",
                "official_miss_boats": missing_boats,
                "boats": boat_rows,
            }
        )

    payload = {
        "model_version": (
            production_payload.get("model_version")
            if isinstance(production_payload, dict)
            else None
        ),
        "races": races,
    }
    return payload, str(merged_path), manifest


def first_existing_value(row, keys):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def load_actual(target_date):
    base = Path("archive") / target_date[:4] / target_date[4:6] / target_date[6:8]
    boat_path = base / f"boat_results_{target_date}_all.csv"
    result_path = base / f"results_{target_date}_all.csv"

    if not boat_path.exists():
        raise RuntimeError(f"実結果がありません: {boat_path}")

    by_race = defaultdict(list)
    with boat_path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            race_key = canonical_race_id(row.get("race_id"))
            boat = to_int(row.get("boat"))
            if not race_key or boat is None:
                continue
            by_race[race_key].append(
                {
                    "boat": boat,
                    "finish": finish_number(row.get("finish")),
                    "course": to_int(row.get("course")),
                    "st": text(row.get("st")),
                }
            )

    payout_map = {}
    if result_path.exists():
        with result_path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                race_key = canonical_race_id(row.get("race_id"))
                payout_value = first_existing_value(
                    row,
                    (
                        "trifecta_pay",
                        "trifecta_payout",
                        "sanrentan_pay",
                        "3rentan_pay",
                    ),
                )
                payout_map[race_key] = to_int(payout_value)

    actual = {}
    for race_key, boats in by_race.items():
        top3 = []
        for finish in (1, 2, 3):
            winner_boat = next(
                (row["boat"] for row in boats if row["finish"] == finish),
                None,
            )
            if winner_boat is not None:
                top3.append(winner_boat)

        actual[race_key] = {
            "boats": boats,
            "winner": top3[0] if top3 else None,
            "top3": top3,
            "trifecta": "-".join(map(str, top3)) if len(top3) == 3 else None,
            "trifecta_pay": payout_map.get(race_key),
        }

    return actual


def prediction_map(payload):
    races = payload.get("races") if isinstance(payload, dict) else None
    if not isinstance(races, list):
        return {}
    return {
        canonical_race_id(race.get("race_id")): race
        for race in races
        if canonical_race_id(race.get("race_id"))
    }


def ordered_boats(race):
    boats = race.get("boats") or []
    rows = [row for row in boats if to_int(row.get("boat")) is not None]
    rows.sort(
        key=lambda row: (
            to_int(row.get("rank")) or 99,
            -(to_float(row.get("score")) or 0),
            to_int(row.get("boat")) or 99,
        )
    )
    return rows


def evaluate_stage(name, payload, actual):
    predictions = prediction_map(payload)
    rows = []
    top1_hits = 0
    top2_hits = 0
    top3_hits = 0
    winner_ranks = []

    for race_key, race in predictions.items():
        truth = actual.get(race_key)
        if not truth or truth.get("winner") is None:
            continue

        boats = ordered_boats(race)
        official_miss_boats = {
            to_int(x)
            for x in (race.get("official_miss_boats") or [])
            if to_int(x) is not None
        }
        expected_boats = 6 - len(official_miss_boats)
        if len(boats) < 3 or len(boats) != expected_boats:
            continue

        order = [to_int(row.get("boat")) for row in boats]
        winner = truth["winner"]
        if winner not in order:
            continue

        winner_rank = order.index(winner) + 1
        top1 = int(winner_rank == 1)
        top2 = int(winner_rank <= 2)
        top3 = int(winner_rank <= 3)

        top1_hits += top1
        top2_hits += top2
        top3_hits += top3
        winner_ranks.append(winner_rank)

        rows.append(
            {
                "stage": name,
                "race_id": text(race.get("race_id")),
                "venue_code": text(race.get("venue_code")),
                "venue_name": text(race.get("venue_name")),
                "race": to_int(race.get("race")),
                "pred_1": order[0],
                "pred_2": order[1],
                "pred_3": order[2],
                "actual_1": winner,
                "actual_2": truth["top3"][1] if len(truth["top3"]) >= 2 else None,
                "actual_3": truth["top3"][2] if len(truth["top3"]) >= 3 else None,
                "winner_prediction_rank": winner_rank,
                "top1_hit": top1,
                "winner_in_top2": top2,
                "winner_in_top3": top3,
            }
        )

    total = len(rows)
    summary = {
        "stage": name,
        "prediction_races_in_file": len(predictions),
        "evaluated_races": total,
        "top1_win_rate": rounded(rate(top1_hits, total)),
        "winner_in_top2_rate": rounded(rate(top2_hits, total)),
        "winner_in_top3_rate": rounded(rate(top3_hits, total)),
        "average_winner_prediction_rank": rounded(mean(winner_ranks)),
    }
    return summary, rows


def compare_stages(morning_rows, live_rows):
    morning = {canonical_race_id(row["race_id"]): row for row in morning_rows}
    live = {canonical_race_id(row["race_id"]): row for row in live_rows}
    keys = sorted(set(morning) & set(live))

    improved = 0
    worsened = 0
    same = 0

    for key in keys:
        before = morning[key]["winner_prediction_rank"]
        after = live[key]["winner_prediction_rank"]
        if after < before:
            improved += 1
        elif after > before:
            worsened += 1
        else:
            same += 1

    return {
        "compared_races": len(keys),
        "winner_rank_improved": improved,
        "winner_rank_worsened": worsened,
        "winner_rank_same": same,
        "improved_rate": rounded(rate(improved, len(keys))),
    }


def empty_bucket():
    return {
        "races": 0,
        "hits": 0,
        "points": 0,
        "investment": 0,
        "return": 0,
    }


def summarize_bucket(bucket):
    investment = bucket["investment"]
    returned = bucket["return"]
    return {
        **bucket,
        "hit_rate": rounded(rate(bucket["hits"], bucket["races"])),
        "average_points_per_race": rounded(rate(bucket["points"], bucket["races"])),
        "profit": returned - investment,
        "recovery_rate_pct": rounded(
            (returned / investment * 100) if investment else None,
            2,
        ),
    }


def add_to_bucket(bucket, hit, points, investment, returned):
    bucket["races"] += 1
    bucket["hits"] += hit
    bucket["points"] += points
    bucket["investment"] += investment
    bucket["return"] += returned


def evaluate_formations(payload, actual):
    races = payload.get("races") or []
    details = []
    totals = empty_bucket()
    by_type = defaultdict(empty_bucket)
    by_prediction = defaultdict(empty_bucket)

    for race in races:
        race_key = canonical_race_id(race.get("race_id"))
        truth = actual.get(race_key)
        if not truth or not truth.get("trifecta"):
            continue

        formation = race.get("formation") or {}
        combinations = formation.get("combinations") or []
        if not combinations:
            continue

        points = len(combinations)
        investment = points * BET_YEN_PER_COMBINATION
        winning_combo = truth["trifecta"]
        hit = int(winning_combo in combinations)
        payout = truth.get("trifecta_pay") or 0
        returned = payout if hit else 0
        profit = returned - investment
        formation_type = text(formation.get("formation_type")) or "不明"
        prediction_type = text(race.get("prediction_type")) or "不明"

        details.append(
            {
                "race_id": text(race.get("race_id")),
                "venue_code": text(race.get("venue_code")),
                "venue_name": text(race.get("venue_name")),
                "race": to_int(race.get("race")),
                "prediction_type": prediction_type,
                "formation_type": formation_type,
                "points": points,
                "investment": investment,
                "actual_trifecta": winning_combo,
                "trifecta_payout_100yen": payout,
                "hit": hit,
                "return": returned,
                "profit": profit,
                "combinations": " / ".join(combinations),
            }
        )

        for bucket in (
            totals,
            by_type[formation_type],
            by_prediction[prediction_type],
        ):
            add_to_bucket(bucket, hit, points, investment, returned)

    return {
        "model_version": text(payload.get("model_version")),
        "strategy": "formation",
        "100yen_per_combination": True,
        "overall": summarize_bucket(totals),
        "by_formation_type": {
            key: summarize_bucket(value) for key, value in by_type.items()
        },
        "by_prediction_type": {
            key: summarize_bucket(value) for key, value in by_prediction.items()
        },
        "details": details,
    }


def normalize_prediction_type(value):
    raw = text(value).lower()
    if raw in {"live", "直前", "live_final"} or "live" in raw or "直前" in raw:
        return "live"
    if raw in {"morning", "朝"} or "morning" in raw or "朝" in raw:
        return "morning"
    return ""


def choose_box_source(race_key, formation_race, morning_map, live_map):
    requested = normalize_prediction_type(formation_race.get("prediction_type"))

    if requested == "live" and race_key in live_map:
        return "live", live_map[race_key]
    if requested == "morning" and race_key in morning_map:
        return "morning", morning_map[race_key]

    # フォーメーション側に明確な種別が無い場合は、
    # 締切前に取得済みの直前予測を優先し、無ければ朝予測を使う。
    if race_key in live_map:
        return "live", live_map[race_key]
    if race_key in morning_map:
        return "morning", morning_map[race_key]

    return "", None


def box_combinations(top3):
    return [
        "-".join(map(str, combo))
        for combo in itertools.permutations(top3, 3)
    ]


def evaluate_top3_box(formation_payload, morning_payload, live_payload, actual):
    formation_races = formation_payload.get("races") or []
    morning_map = prediction_map(morning_payload)
    live_map = prediction_map(live_payload or {})

    details = []
    totals = empty_bucket()
    by_prediction = defaultdict(empty_bucket)

    for formation_race in formation_races:
        race_key = canonical_race_id(formation_race.get("race_id"))
        truth = actual.get(race_key)
        if not truth or not truth.get("trifecta"):
            continue

        prediction_type, source_race = choose_box_source(
            race_key,
            formation_race,
            morning_map,
            live_map,
        )
        if source_race is None:
            continue

        ranked = ordered_boats(source_race)
        if len(ranked) < 3:
            continue

        top3 = [to_int(row.get("boat")) for row in ranked[:3]]
        if len(top3) != 3 or any(boat is None for boat in top3):
            continue

        combinations = box_combinations(top3)
        points = 6
        investment = points * BET_YEN_PER_COMBINATION
        winning_combo = truth["trifecta"]
        hit = int(winning_combo in combinations)
        payout = truth.get("trifecta_pay") or 0
        returned = payout if hit else 0
        profit = returned - investment

        details.append(
            {
                "race_id": text(source_race.get("race_id")) or text(formation_race.get("race_id")),
                "venue_code": text(source_race.get("venue_code")) or text(formation_race.get("venue_code")),
                "venue_name": text(source_race.get("venue_name")) or text(formation_race.get("venue_name")),
                "race": to_int(source_race.get("race")) or to_int(formation_race.get("race")),
                "prediction_type": prediction_type or "不明",
                "selected_1": top3[0],
                "selected_2": top3[1],
                "selected_3": top3[2],
                "points": points,
                "investment": investment,
                "actual_trifecta": winning_combo,
                "trifecta_payout_100yen": payout,
                "hit": hit,
                "return": returned,
                "profit": profit,
                "combinations": " / ".join(combinations),
            }
        )

        prediction_bucket = prediction_type or "不明"
        for bucket in (totals, by_prediction[prediction_bucket]):
            add_to_bucket(bucket, hit, points, investment, returned)

    return {
        "strategy": "top3_trifecta_box",
        "selection_rule": (
            "フォーメーションと同じレースを対象に、"
            "そのレースで採用した予測段階（直前優先、無ければ朝）の"
            "AI順位上位3艇を3連単6点BOXで各100円購入"
        ),
        "points_per_race": 6,
        "yen_per_combination": BET_YEN_PER_COMBINATION,
        "overall": summarize_bucket(totals),
        "by_prediction_type": {
            key: summarize_bucket(value) for key, value in by_prediction.items()
        },
        "details": details,
    }


def write_csv(path, rows):
    if not rows:
        return
    fields = list(rows[0].keys())
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    args = parse_args()
    target_date = args.date

    try:
        datetime.strptime(target_date, "%Y%m%d")

        base = Path("predictions") / target_date[:4] / target_date[4:6] / target_date[6:8]

        morning_payload = load_json(
            base / f"morning_predictions_{target_date}.json"
        )

        production_live_payload = load_json(
            base / "live" / f"live_predictions_final_{target_date}.json",
            required=args.require_live,
        )
        live_payload, analysis_live_source, recovery_manifest = (
            load_analysis_live_payload(target_date, production_live_payload)
        )

        formation_payload = load_json(
            base / "live" / f"formation_predictions_final_{target_date}.json"
        )

        actual = load_actual(target_date)

        morning_summary, morning_rows = evaluate_stage(
            "morning", morning_payload, actual
        )

        if live_payload:
            live_summary, live_rows = evaluate_stage(
                "live", live_payload, actual
            )
        else:
            live_summary = {
                "stage": "live",
                "prediction_races_in_file": 0,
                "evaluated_races": 0,
            }
            live_rows = []

        comparison = compare_stages(morning_rows, live_rows)
        formation_result = evaluate_formations(formation_payload, actual)
        box_result = evaluate_top3_box(
            formation_payload,
            morning_payload,
            live_payload,
            actual,
        )

        output_dir = (
            Path("evaluations")
            / target_date[:4]
            / target_date[4:6]
            / target_date[6:8]
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        write_csv(
            output_dir / f"prediction_evaluation_{target_date}.csv",
            morning_rows + live_rows,
        )
        write_csv(
            output_dir / f"formation_simulation_{target_date}.csv",
            formation_result["details"],
        )
        write_csv(
            output_dir / f"top3_box_simulation_{target_date}.csv",
            box_result["details"],
        )

        evaluation = {
            "status": "PASS",
            "target_date": target_date,
            "generated_at": datetime.now(JST).isoformat(),
            "actual_races_available": len(actual),
            "analysis_live_source": analysis_live_source,
            "recovery_manifest": recovery_manifest,
            "morning": morning_summary,
            "live": live_summary,
            "morning_vs_live": comparison,
            "formation_simulation": {
                "model_version": formation_result["model_version"],
                "overall": formation_result["overall"],
                "by_formation_type": formation_result["by_formation_type"],
                "by_prediction_type": formation_result["by_prediction_type"],
            },
            "top3_box_simulation": {
                "strategy": box_result["strategy"],
                "selection_rule": box_result["selection_rule"],
                "points_per_race": box_result["points_per_race"],
                "overall": box_result["overall"],
                "by_prediction_type": box_result["by_prediction_type"],
            },
            "note": (
                "フォーメーション戦略と上位3艇BOX戦略は完全に別会計。"
                "両方を同時購入した収支ではない。各買い目100円固定。"
            ),
        }

        (output_dir / f"prediction_evaluation_{target_date}.json").write_text(
            json.dumps(evaluation, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / f"formation_simulation_{target_date}.json").write_text(
            json.dumps(formation_result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / f"top3_box_simulation_{target_date}.json").write_text(
            json.dumps(box_result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print("========================================")
        print("予測＋2戦略 最終評価")
        print("========================================")
        print("朝予測評価:", morning_summary["evaluated_races"], "R")
        print("直前予測評価:", live_summary["evaluated_races"], "R")

        formation_overall = formation_result["overall"]
        print("")
        print("[フォーメーション]")
        print("対象:", formation_overall["races"], "R")
        print("的中:", formation_overall["hits"], "R")
        print("投資:", formation_overall["investment"], "円")
        print("払戻:", formation_overall["return"], "円")
        print("損益:", formation_overall["profit"], "円")
        print("回収率:", formation_overall["recovery_rate_pct"], "%")

        box_overall = box_result["overall"]
        print("")
        print("[AI上位3艇・3連単BOX]")
        print("対象:", box_overall["races"], "R")
        print("的中:", box_overall["hits"], "R")
        print("投資:", box_overall["investment"], "円")
        print("払戻:", box_overall["return"], "円")
        print("損益:", box_overall["profit"], "円")
        print("回収率:", box_overall["recovery_rate_pct"], "%")
        print("")
        print("2戦略評価生成: PASS")
        return 0

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
