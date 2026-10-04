from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import build_morning_prediction as morning

JST = timezone(timedelta(hours=9))
MODEL_VERSION = "provisional_v1_20261004_live_80_6_14"


def parse_args():
    parser = argparse.ArgumentParser(
        description="TOP3整合率重視の統一スコアで直前予測を生成"
    )
    parser.add_argument("--date", required=True, help="対象日 YYYYMMDD")
    parser.add_argument("--input", default=None)
    parser.add_argument("--output-dir", default="data")
    parser.add_argument("--now", default=None, help="検証用現在時刻 ISO8601")
    parser.add_argument("--public-source-dir", default=None)
    return parser.parse_args()


def text(value):
    return "" if value is None else str(value).strip()


def to_float(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def to_int(value):
    n = to_float(value)
    return None if n is None else int(n)


def first_value(mapping, keys):
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        v = mapping.get(key)
        if v not in (None, ""):
            return v
    return None


def boat_beforeinfo(boat):
    info = boat.get("beforeinfo")
    return info if isinstance(info, dict) else {}


def get_exhibition_course(boat):
    info = boat_beforeinfo(boat)
    value = first_value(
        info,
        ("exhibition_course", "course", "tenji_course", "display_course"),
    )
    if value in (None, ""):
        value = first_value(boat, ("exhibition_course", "tenji_course"))
    course = to_int(value)
    return course if course in {1, 2, 3, 4, 5, 6} else None


def raw_exhibition_st_value(boat):
    info = boat_beforeinfo(boat)
    value = first_value(
        info,
        (
            "exhibition_st_raw",
            "exhibition_st",
            "tenji_st",
            "display_st",
            "st",
        ),
    )
    if value in (None, ""):
        value = first_value(
            boat,
            ("exhibition_st_raw", "exhibition_st", "tenji_st"),
        )
    return value


def parse_exhibition_st(value):
    raw = text(value).upper().replace(" ", "")
    if not raw or raw.startswith("L"):
        return None
    if raw.startswith("F"):
        raw = raw[1:]
        if raw.startswith("."):
            raw = "0" + raw
        try:
            return -abs(float(raw))
        except ValueError:
            return None
    if raw.startswith("."):
        raw = "0" + raw
    try:
        n = float(raw)
    except ValueError:
        return None
    return n if -0.30 <= n <= 1.00 else None


def get_exhibition_st(boat):
    return parse_exhibition_st(raw_exhibition_st_value(boat))


def get_exhibition_f(boat):
    raw = text(raw_exhibition_st_value(boat)).upper().replace(" ", "")
    if raw.startswith("F"):
        return True
    info = boat_beforeinfo(boat)
    flag = first_value(
        info,
        (
            "exhibition_st_flag",
            "tenji_st_flag",
            "display_st_flag",
            "exhibition_f",
            "is_f",
        ),
    )
    if isinstance(flag, bool):
        return flag
    return text(flag).upper() in {"F", "TRUE", "YES", "1"}


def get_exhibition_time(boat):
    info = boat_beforeinfo(boat)
    value = first_value(info, ("exhibition_time", "tenji_time", "display_time"))
    if value in (None, ""):
        value = first_value(boat, ("exhibition_time", "tenji_time"))
    n = to_float(value)
    return n if n is not None and 5.0 <= n <= 10.0 else None


def get_tilt(boat):
    info = boat_beforeinfo(boat)
    value = first_value(info, ("tilt", "tilt_angle"))
    if value in (None, ""):
        value = first_value(boat, ("tilt", "tilt_angle"))
    return to_float(value)


def parse_now(value):
    if not value:
        return datetime.now(JST)
    raw = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt.astimezone(JST)


def parse_deadline(target_date, race):
    value = first_value(
        race,
        ("deadline", "deadline_time", "close_time", "cutoff_time"),
    )
    if value in (None, ""):
        return None

    raw = text(value)
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)
        return dt.astimezone(JST)
    except ValueError:
        pass

    base = datetime.strptime(target_date, "%Y%m%d").date()
    for fmt in ("%H:%M:%S", "%H:%M", "%H%M"):
        try:
            t = datetime.strptime(raw, fmt).time()
            return datetime.combine(base, t, tzinfo=JST)
        except ValueError:
            pass
    return None


def validate_no_current_results(payload):
    return morning.validate_current_day_no_results(payload)


def rank_exhibition_st(boats):
    # 9/30+10/1探索時と同じ扱い:
    # F(負値)はランキング対象外、非F艇だけ「小さいSTほど高得点」。
    values = {}
    for boat in boats:
        lane = to_int(boat.get("boat"))
        st = get_exhibition_st(boat)
        is_f = get_exhibition_f(boat) or (st is not None and st < 0)
        if lane in {1,2,3,4,5,6} and st is not None and st >= 0 and not is_f:
            values[lane] = st
    return morning.rank_lower_is_better(values)


def component_exst(lane, boat, ranks):
    weight = morning.UNIFIED_WEIGHTS["exST"]
    st = get_exhibition_st(boat)
    is_f = get_exhibition_f(boat) or (st is not None and st < 0)
    raw = 0.0 if is_f else ranks.get(lane)
    if raw is None:
        return {
            "name": "exST",
            "available": False,
            "raw_score_0_1": None,
            "weight": weight,
            "weighted_points": 0.0,
            "source": f"展示ST={st}",
        }
    return {
        "name": "exST",
        "available": True,
        "raw_score_0_1": round(float(raw), 6),
        "weight": weight,
        "weighted_points": round(float(raw) * weight, 4),
        "source": (
            f"展示ST={st} F扱いで0点"
            if is_f
            else f"展示ST={st} レース内順位"
        ),
    }


def score_race(race, public_store):
    boats=race.get("boats")
    if not isinstance(boats,list) or len(boats)!=6: raise RuntimeError(f"6艇ではないレース: {race.get('race_id')}")
    overrides={to_int(x.get("boat")):(get_exhibition_course(x) or to_int(x.get("boat"))) for x in boats}
    morning_scores=morning.provisional_scores(race,public_store)
    structural=morning.provisional_scores(race,public_store,overrides)
    if len(structural)!=6: raise RuntimeError(f"暫定V1構造スコア欠損: {race.get('race_id')}")
    time_ranks=morning.rank_lower_is_better({to_int(x.get("boat")):get_exhibition_time(x) for x in boats if get_exhibition_time(x) is not None})
    st_ranks=morning.rank_lower_is_better({to_int(x.get("boat")):get_exhibition_st(x) for x in boats if get_exhibition_st(x) is not None and not get_exhibition_f(x) and get_exhibition_st(x)>=0})
    if len(time_ranks)!=6 or len(st_ranks)!=6: raise RuntimeError(f"展示タイム/ST不足: {race.get('race_id')}")
    scored=[]
    for boat in boats:
        lane=to_int(boat.get("boat")); live01=.80*(structural[lane]/100.0)+.06*time_ranks[lane]+.14*st_ranks[lane]; racer=boat.get("racer") or {}; motor=boat.get("motor") or {}; bm=boat.get("boat_machine") or {}
        scored.append({"boat":lane,"registration_no":racer.get("registration_no"),"racer_name":racer.get("name"),"grade":racer.get("grade"),"motor_no":motor.get("motor_no"),"boat_no":bm.get("boat_no"),"score":round(live01*100,2),"morning_score_reference":round(morning_scores.get(lane,0.0),2),"data_coverage_pct":100.0,"exhibition_course":overrides[lane],"exhibition_time":get_exhibition_time(boat),"exhibition_st":get_exhibition_st(boat),"exhibition_f":bool(get_exhibition_f(boat)),"tilt":get_tilt(boat),"components":{"structural":{"weight":80.0,"raw_score_0_1":round(structural[lane]/100.0,6),"available":True},"exTime":{"weight":6.0,"raw_score_0_1":round(time_ranks[lane],6),"available":True},"exST":{"weight":14.0,"raw_score_0_1":round(st_ranks[lane],6),"available":True}}})
    scored.sort(key=lambda x:(-x["score"],x["boat"]))
    for i,x in enumerate(scored,1):x["rank"]=i
    return scored

def race_context(race):
    keys = (
        "weather",
        "weather_code",
        "air_temperature",
        "temperature",
        "water_temperature",
        "wind_speed",
        "wind_direction",
        "wave_height",
    )
    result = {}
    for key in keys:
        v = race.get(key)
        if v not in (None, ""):
            result[key] = v

    nested = race.get("beforeinfo")
    if isinstance(nested, dict):
        for key in keys:
            v = nested.get(key)
            if v not in (None, "") and key not in result:
                result[key] = v
    return result


def write_csv(path, rows):
    fields = [
        "target_date",
        "generated_at",
        "venue_code",
        "venue_name",
        "race",
        "race_id",
        "deadline",
        "rank",
        "boat",
        "registration_no",
        "racer_name",
        "grade",
        "motor_no",
        "boat_no",
        "score",
        "morning_score_reference",
        "data_coverage_pct",
        "exhibition_course",
        "exhibition_time",
        "exhibition_st",
        "exhibition_f",
        "tilt",
    ]
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_existing_final(target_date):
    path = (
        Path("predictions")
        / target_date[:4]
        / target_date[4:6]
        / target_date[6:8]
        / "live"
        / f"live_predictions_final_{target_date}.json"
    )
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    races = data.get("races")
    if not isinstance(races, list):
        return {}
    return {
        text(race.get("race_id")): race
        for race in races
        if text(race.get("race_id"))
    }


def main():
    args = parse_args()
    target_date = args.date

    try:
        datetime.strptime(target_date, "%Y%m%d")
    except ValueError:
        print("ERROR: --dateはYYYYMMDD形式です", file=sys.stderr)
        return 1

    now = parse_now(args.now)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    input_path = (
        Path(args.input)
        if args.input
        else output_dir / f"prediction_input_enriched_live_{target_date}.json"
    )
    current_json = output_dir / f"live_predictions_current_{target_date}.json"
    current_csv = output_dir / f"live_predictions_current_{target_date}.csv"
    validation_json = (
        output_dir / f"live_predictions_validation_current_{target_date}.json"
    )
    final_json = output_dir / f"live_predictions_final_{target_date}.json"
    final_csv = output_dir / f"live_predictions_final_{target_date}.csv"

    if not input_path.exists():
        print(f"ERROR: 入力ファイルがありません: {input_path}", file=sys.stderr)
        return 1

    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))

        if text(payload.get("target_date")) != target_date:
            raise RuntimeError("target_date不一致")
        if text(payload.get("prediction_stage")) != "live":
            raise RuntimeError("live用prediction_inputではありません")

        violations = validate_no_current_results(payload)
        if violations:
            raise RuntimeError(f"当日結果混入: {violations[:5]}")

        public_store = morning.PublicStore(
            target_date,
            local_dir=args.public_source_dir,
            include_stt=False,
        )

        races = payload.get("races")
        if not isinstance(races, list):
            raise RuntimeError("racesが不正です")

        predicted_races = []
        csv_rows = []
        skipped_after_deadline = []
        skipped_no_live_data = []

        for race in races:
            race_id = text(race.get("race_id"))
            boats = race.get("boats")
            if not isinstance(boats, list) or len(boats) != 6:
                continue

            deadline = parse_deadline(target_date, race)
            if deadline is not None and now >= deadline:
                skipped_after_deadline.append(race_id)
                continue

            course_count = sum(
                get_exhibition_course(boat) is not None for boat in boats
            )
            st_count = sum(
                get_exhibition_st(boat) is not None for boat in boats
            )

            # 今回の本番モデルはcourse32点＋展示ST3点。
            # 直前情報が概ね揃うまでは直前版を出さない。
            if course_count < 5 or st_count < 4:
                skipped_no_live_data.append(race_id)
                continue

            scored = score_race(race, public_store)

            pred = {
                "race_id": race_id,
                "date": race.get("date"),
                "venue_code": race.get("venue_code"),
                "venue_name": race.get("venue_name"),
                "race": race.get("race"),
                "race_name": race.get("race_name"),
                "deadline": race.get("deadline"),
                "generated_at": now.isoformat(),
                "live_data_counts": {
                    "exhibition_course": course_count,
                    "exhibition_st": st_count,
                },
                "weather_water": race_context(race),
                "live_order": [x["boat"] for x in scored],
                "top3_boats": [x["boat"] for x in scored[:3]],
                "strength": morning.prediction_strength(scored),
                "boats": scored,
            }
            predicted_races.append(pred)

            for row in scored:
                csv_rows.append(
                    {
                        "target_date": target_date,
                        "generated_at": now.isoformat(),
                        "venue_code": race.get("venue_code"),
                        "venue_name": race.get("venue_name"),
                        "race": race.get("race"),
                        "race_id": race_id,
                        "deadline": race.get("deadline"),
                        "rank": row["rank"],
                        "boat": row["boat"],
                        "registration_no": row["registration_no"],
                        "racer_name": row["racer_name"],
                        "grade": row["grade"],
                        "motor_no": row["motor_no"],
                        "boat_no": row["boat_no"],
                        "score": row["score"],
                        "morning_score_reference": row[
                            "morning_score_reference"
                        ],
                        "data_coverage_pct": row["data_coverage_pct"],
                        "exhibition_course": row["exhibition_course"],
                        "exhibition_time": row["exhibition_time"],
                        "exhibition_st": row["exhibition_st"],
                        "exhibition_f": row["exhibition_f"],
                        "tilt": row["tilt"],
                    }
                )

        status = "PASS" if predicted_races else "NO_DATA"
        validation = {
            "status": status,
            "model_version": MODEL_VERSION,
            "target_date": target_date,
            "generated_at": now.isoformat(),
            "weights": morning.UNIFIED_WEIGHTS,
            "input_race_count": len(races),
            "prediction_race_count": len(predicted_races),
            "prediction_boat_count": len(csv_rows),
            "skipped_after_deadline": skipped_after_deadline,
            "skipped_no_live_data": skipped_no_live_data,
            "current_day_result_leakage": 0,
            "errors": [],
        }
        validation_json.write_text(
            json.dumps(validation, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if not predicted_races:
            print("直前予測: 現在対象レースなし")
            return 0

        snapshot = {
            "schema_version": "1.0",
            "model_version": MODEL_VERSION,
            "target_date": target_date,
            "prediction_stage": "live",
            "generated_at": now.isoformat(),
            "weights": morning.UNIFIED_WEIGHTS,
            "live_policy": {
                "course": "32点を展示進入コースへ差し替え",
                "exhibition_st": "3点。Fは0点",
                "exhibition_time": "0点",
            },
            "race_count": len(predicted_races),
            "boat_count": len(csv_rows),
            "races": predicted_races,
        }
        current_json.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        write_csv(current_csv, csv_rows)

        # 過去締切レースは既存最終予測を保持し、
        # 今回まだ締切前のrace_idだけ新モデルで更新する。
        final_map = load_existing_final(target_date)
        for race in predicted_races:
            final_map[text(race.get("race_id"))] = race

        final_races = sorted(
            final_map.values(),
            key=lambda r: (
                text(r.get("venue_code")),
                to_int(r.get("race")) or 0,
            ),
        )

        final_rows = []
        for race in final_races:
            for row in race.get("boats", []):
                final_rows.append(
                    {
                        "target_date": target_date,
                        "generated_at": race.get("generated_at"),
                        "venue_code": race.get("venue_code"),
                        "venue_name": race.get("venue_name"),
                        "race": race.get("race"),
                        "race_id": race.get("race_id"),
                        "deadline": race.get("deadline"),
                        "rank": row.get("rank"),
                        "boat": row.get("boat"),
                        "registration_no": row.get("registration_no"),
                        "racer_name": row.get("racer_name"),
                        "grade": row.get("grade"),
                        "motor_no": row.get("motor_no"),
                        "boat_no": row.get("boat_no"),
                        "score": row.get("score"),
                        "morning_score_reference": row.get(
                            "morning_score_reference"
                        ),
                        "data_coverage_pct": row.get("data_coverage_pct"),
                        "exhibition_course": row.get("exhibition_course"),
                        "exhibition_time": row.get("exhibition_time"),
                        "exhibition_st": row.get("exhibition_st"),
                        "exhibition_f": row.get("exhibition_f"),
                        "tilt": row.get("tilt"),
                    }
                )

        final_payload = {
            "schema_version": "1.0",
            "model_version": MODEL_VERSION,
            "target_date": target_date,
            "prediction_stage": "live_final",
            "updated_at": now.isoformat(),
            "weights": morning.UNIFIED_WEIGHTS,
            "race_count": len(final_races),
            "boat_count": len(final_rows),
            "selection_rule": (
                "締切済みrace_idは既存最終予測を保持。"
                "締切前race_idだけunified_top3_v1で更新"
            ),
            "races": final_races,
        }
        final_json.write_text(
            json.dumps(final_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        write_csv(final_csv, final_rows)

        print("========================================")
        print("直前予測生成")
        print("モデル:", MODEL_VERSION)
        print("今回更新:", f"{len(predicted_races)}R")
        print("最終予測累積:", f"{len(final_races)}R")
        print("直前予測生成: PASS")
        print("========================================")
        return 0

    except Exception as exc:
        validation_json.write_text(
            json.dumps(
                {
                    "status": "FAIL",
                    "model_version": MODEL_VERSION,
                    "target_date": target_date,
                    "error": str(exc),
                    "generated_at": now.isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
