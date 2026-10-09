from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import build_morning_prediction as morning
from production_config import load_config

LIVE_CONFIG, LIVE_CONFIG_META = load_config("live")
LIVE_WEIGHTS = LIVE_CONFIG["score_weights"]

JST = timezone(timedelta(hours=9))
MODEL_VERSION = "provisional_v5_20261007_live_saved_morning_fallback"


def parse_args():
    parser = argparse.ArgumentParser(
        description="TOP3整合率重視の統一スコアで直前予測を生成"
    )
    parser.add_argument("--date", required=True, help="対象日 YYYYMMDD")
    parser.add_argument("--input", default=None)
    parser.add_argument("--output-dir", default="data")
    parser.add_argument("--now", default=None, help="検証用現在時刻 ISO8601")
    parser.add_argument("--public-source-dir", default=None)
    parser.add_argument("--historical-backfill", action="store_true", help="保存済み公式beforeinfoから過去日の直前予測を再構成")
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


_RACER_ST90_CACHE = None

def racer_st90_map():
    global _RACER_ST90_CACHE
    if _RACER_ST90_CACHE is not None:
        return _RACER_ST90_CACHE
    out = {}
    path = Path(__file__).resolve().parents[1] / "features" / "racer_features.csv"
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                reg = text(row.get("registration_no"))
                avg = to_float(row.get("d90_avg_st"))
                samples = to_int(row.get("d90_st_samples")) or 0
                if reg:
                    out[reg] = (samples, avg)
    # 90日STが欠損/標本不足の選手は、保存済み長期コース履歴の実測STを補完候補にする。
    # 直前の展示進入コースごとに選べるよう、(選手,コース)も保持する。
    fallback_path = Path(__file__).resolve().parents[1] / "config" / "racer_course_history_fallback.csv"
    if fallback_path.exists():
        with fallback_path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                reg=text(row.get("registration_no")); course=text(row.get("course"))
                avg=to_float(row.get("avg_st")); samples=to_int(row.get("sample_count")) or 0
                if reg and course and avg is not None:
                    out[(reg,course)] = (samples,avg)
    _RACER_ST90_CACHE = out
    return out

def personal_st_delta_score(boat):
    # 暫定採用 2026-10-06:
    # 展示ST - 本人90日平均ST。±0.06秒で0〜1の最大補正。
    # 本人90日STが10走未満/欠損は中立0.5。展示Fは0.4。
    st = get_exhibition_st(boat)
    is_f = get_exhibition_f(boat) or (st is not None and st < 0)
    if is_f:
        return LIVE_CONFIG["st_exhibition_f_value"]
    racer = boat.get("racer") or {}
    reg = text(racer.get("registration_no"))
    st_map=racer_st90_map()
    samples, avg = st_map.get(reg, (0, None))
    # 90日STが使えない場合は、展示進入コースに対応する保存済み長期実績を参照する。
    # 長期履歴は標本10走未満でも「実データ」として使い、欠損時の中立0.5より優先する。
    if avg is None or samples < LIVE_CONFIG["st_min_races"]:
        course=text(get_exhibition_course(boat) or boat.get("boat"))
        fs, favg=st_map.get((reg,course),(0,None))
        if favg is not None:
            samples,avg=fs,favg
    if st is None or avg is None:
        return LIVE_CONFIG["st_neutral"]
    delta = st - avg
    return max(0.0, min(1.0, LIVE_CONFIG["st_neutral"] - delta / LIVE_CONFIG["st_delta_denominator_seconds"]))


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
    weight = LIVE_WEIGHTS["exhibition_st"] * 100.0
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


def is_miss_boat(boat):
    v = boat_beforeinfo(boat).get("is_miss", False)
    return v is True or text(v).lower() in {"true","1","yes"}


def load_saved_morning_race_map(target_date):
    """当日朝に確定保存した予測を、直前構造特徴量欠損時の実データfallbackとして読む。"""
    path = (
        Path("predictions")
        / target_date[:4]
        / target_date[4:6]
        / target_date[6:8]
        / f"morning_predictions_{target_date}.json"
    )
    if not path.is_file():
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
        if isinstance(race, dict) and text(race.get("race_id"))
    }


def _saved_morning_fallback(saved_race, active_lanes):
    """保存済み朝予測から、スコアと5基礎要素の実値だけを取り出す。"""
    if not isinstance(saved_race, dict):
        return None
    by_lane = {}
    for row in saved_race.get("boats") or []:
        lane = to_int(row.get("boat"))
        if lane in active_lanes:
            by_lane[lane] = row
    if set(by_lane) != set(active_lanes):
        return None

    scores = {}
    details = {}
    for lane in active_lanes:
        row = by_lane[lane]
        score = to_float(row.get("score"))
        comps = row.get("components") or {}
        values = {}
        for key in ("racer_course", "grade", "motor", "boat", "national_top2"):
            comp = comps.get(key) or {}
            value = to_float(comp.get("raw_score_0_1"))
            if value is None:
                return None
            values[key] = value
        if score is None:
            return None
        scores[lane] = score
        details[lane] = {
            "score": score,
            **values,
            "course": lane,
        }
    return scores, details


def score_race(race, public_store, feature_manifest=None, saved_morning_race=None):
    all_boats=race.get("boats")
    missed=[x for x in all_boats if is_miss_boat(x)] if isinstance(all_boats,list) else []
    boats=[x for x in all_boats if not is_miss_boat(x)] if isinstance(all_boats,list) else all_boats
    if not isinstance(all_boats,list) or len(all_boats)!=6: raise RuntimeError(f"6艇ではないレース: {race.get('race_id')}")
    if len(boats)<3: raise RuntimeError(f"有効艇不足: {race.get('race_id')}")
    overrides={to_int(x.get("boat")):(get_exhibition_course(x) or to_int(x.get("boat"))) for x in boats}
    work_race=dict(race); work_race["boats"]=boats
    active_lanes={to_int(x.get("boat")) for x in boats}
    saved_bundle=_saved_morning_fallback(saved_morning_race, active_lanes)
    fresh_morning_details, fresh_morning_missing = morning.provisional_details(work_race, public_store)
    if saved_bundle is not None:
        morning_scores=dict(saved_bundle[0])
    elif not fresh_morning_missing and len(fresh_morning_details)==len(boats):
        morning_scores={lane:d["score"] for lane,d in fresh_morning_details.items()}
    else:
        raise RuntimeError(
            f"朝基礎スコア欠損: {race.get('race_id')} {fresh_morning_missing}"
        )

    structural_details, structural_missing = morning.provisional_details(
        work_race, public_store, overrides
    )
    structural_fallback = None
    if structural_missing or len(structural_details)!=len(boats):
        # 展示進入コース側の履歴が欠けても、欠損値を捏造せず、
        # 当日朝に確定保存済みの本番スコアを構造80%の実データfallbackにする。
        # 展示タイム6%・展示ST14%は取得済み直前値をそのまま使う。
        if saved_bundle is None:
            raise RuntimeError(
                f"直前構造スコア欠損: {race.get('race_id')} {structural_missing}"
            )
        structural, structural_details = saved_bundle
        structural_fallback = {
            "used": True,
            "source": "saved_morning_prediction",
            "reason": structural_missing,
        }
    else:
        structural={lane:d["score"] for lane,d in structural_details.items()}
    time_ranks=morning.rank_lower_is_better({to_int(x.get("boat")):get_exhibition_time(x) for x in boats if get_exhibition_time(x) is not None})
    st_delta_scores={to_int(x.get("boat")):personal_st_delta_score(x) for x in boats}
    # 展示ST14%は本人90日平均STとの差で評価。F=0.4、90日ST10走未満/欠損=0.5。
    for x in boats:
        lane=to_int(x.get("boat"))
        if lane not in time_ranks: time_ranks[lane]=0.5
        if lane not in st_delta_scores: st_delta_scores[lane]=0.5
    scored=[]
    for boat in boats:
        lane=to_int(boat.get("boat")); live01=LIVE_WEIGHTS["structural"]*(structural[lane]/100.0)+LIVE_WEIGHTS["exhibition_time"]*time_ranks[lane]+LIVE_WEIGHTS["exhibition_st"]*st_delta_scores[lane]; racer=boat.get("racer") or {}; motor=boat.get("motor") or {}; bm=boat.get("boat_machine") or {}
        if lane not in structural_details:
            raise RuntimeError(f"直前基礎要素欠損: {race.get('race_id')} {lane}号艇")
        sd = structural_details[lane]
        history=boat.get("history") or {}
        before=boat_beforeinfo(boat)
        scored.append({
            "boat":lane,"registration_no":racer.get("registration_no"),"racer_name":racer.get("name"),
            "grade":racer.get("grade"),"motor_no":motor.get("motor_no"),"boat_no":bm.get("boat_no"),
            "score":round(live01*100,2),"morning_score_reference":round(morning_scores.get(lane,0.0),2),
            "data_coverage_pct":100.0,"exhibition_course":overrides[lane],"exhibition_time":get_exhibition_time(boat),
            "exhibition_st":get_exhibition_st(boat),"exhibition_f":bool(get_exhibition_f(boat)),"tilt":get_tilt(boat),
            "change_parts":before.get("change_parts",""),
            "input_trace":{"history_feature_manifest":feature_manifest,"structural_course_fallback":structural_fallback,"racer_30d":history.get("racer_30d"),"racer_90d":history.get("racer_90d"),"motor_30d":history.get("motor_30d"),"motor_90d":history.get("motor_90d"),"boat_30d":history.get("boat_30d"),"boat_90d":history.get("boat_90d"),"racer_venue":history.get("racer_venue"),"racer_course":history.get("racer_course"),"beforeinfo":{"exhibition_course":get_exhibition_course(boat),"exhibition_time":get_exhibition_time(boat),"exhibition_st_raw":raw_exhibition_st_value(boat),"exhibition_st":get_exhibition_st(boat),"exhibition_f":bool(get_exhibition_f(boat)),"tilt":get_tilt(boat),"change_parts":before.get("change_parts","")},"weather_water":race_context(race),"official_f_count":racer.get("official_f_count"),"official_l_count":racer.get("official_l_count"),"official_avg_st":racer.get("official_avg_st"),"official_fl_available":racer.get("official_fl_available",False),"candidate_components":{"f_l_holdings":{"available":racer.get("official_fl_available",False),"f_count":racer.get("official_f_count"),"l_count":racer.get("official_l_count"),"active_in_score":False},"motor_30d":{"available":history.get("motor_30d_available",False),"features":history.get("motor_30d"),"active_in_score":False},"parts_exchange":{"available":before.get("change_parts") not in (None,""),"value":before.get("change_parts",""),"active_in_score":False},"weather_water":{"available":bool(race_context(race)),"value":race_context(race),"active_in_score":False}}},
            "components":{
                "racer_course":{"weight":40.0,"raw_score_0_1":round(sd["racer_course"],6),"available":True},
                "grade":{"weight":20.0,"raw_score_0_1":round(sd["grade"],6),"available":True},
                "motor":{"weight":20.0,"raw_score_0_1":round(sd["motor"],6),"available":True},
                "boat":{"weight":5.0,"raw_score_0_1":round(sd["boat"],6),"available":True},
                "national_top2":{"weight":15.0,"raw_score_0_1":round(sd["national_top2"],6),"available":True},
                "structural":{"weight":LIVE_WEIGHTS["structural"]*100.0,"raw_score_0_1":round(structural[lane]/100.0,6),"available":True},
                "exTime":{"weight":LIVE_WEIGHTS["exhibition_time"]*100.0,"raw_score_0_1":round(time_ranks[lane],6),"available":True},
                "exST":{"weight":LIVE_WEIGHTS["exhibition_st"]*100.0,"raw_score_0_1":round(st_delta_scores[lane],6),"available":True,
                        "method":"personal_d90_st_delta","delta_full_scale_seconds":LIVE_CONFIG["st_delta_denominator_seconds"]/2,"f_score":LIVE_CONFIG["st_exhibition_f_value"]}
            }
        })
    scored.sort(key=lambda x:(-x["score"],x["boat"]))
    for i,x in enumerate(scored,1):x["rank"]=i
    return scored

def race_context(race):
    keys = (
        "weather",
        "weather_code",
        "air_temperature",
        "air_temperature_c",
        "temperature",
        "water_temperature",
        "water_temperature_c",
        "wind_speed",
        "wind_speed_mps",
        "wind_direction",
        "wind_direction_code",
        "wave_height",
        "wave_height_cm",
        "stabilizer",
        "fixed_course",
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

        public_store = None

        races = payload.get("races")
        if not isinstance(races, list):
            raise RuntimeError("racesが不正です")

        predicted_races = []
        csv_rows = []
        skipped_after_deadline = []
        skipped_no_live_data = []
        skipped_score_error = []
        structural_fallback_races = []
        saved_morning_races = load_saved_morning_race_map(target_date)

        for race in races:
            race_id = text(race.get("race_id"))
            boats = race.get("boats")
            # 欠場・出走取消等で6艇未満になるレースを処理停止させない。
            # 取得できた艇で処理を継続し、完全性/原因確認は監査側で別管理する。
            if not isinstance(boats, list) or len(boats) < 3:
                skipped_no_live_data.append(race_id)
                continue

            deadline = parse_deadline(target_date, race)
            requested_at = None
            requested_raw = text(race.get("beforeinfo_requested_at"))
            if requested_raw:
                try:
                    requested_at = parse_now(requested_raw)
                except (ValueError, TypeError):
                    requested_at = None

            collected_at = None
            collected_raw = text(race.get("beforeinfo_collected_at"))
            if collected_raw:
                try:
                    collected_at = parse_now(collected_raw)
                except (ValueError, TypeError):
                    collected_at = None

            # 直前情報の有効性は原則として締切前取得。
            # ただしHTTP取得を締切前に開始し、通信完了だけがごく短時間
            # 締切後になったケースは、結果ページではなくbeforeinfo取得なので
            # 通信遅延として許容する。これによりネットワーク待ち数秒で捨てない。
            request_grace_used = False
            if deadline is not None and not args.historical_backfill:
                if collected_at is not None and collected_at >= deadline:
                    request_grace_used = bool(
                        requested_at is not None
                        and requested_at < deadline
                        and (collected_at - deadline).total_seconds() <= 30
                    )
                    if not request_grace_used:
                        skipped_after_deadline.append(race_id)
                        continue
                if collected_at is None and now >= deadline:
                    skipped_after_deadline.append(race_id)
                    continue

            active_boats = [boat for boat in boats if not is_miss_boat(boat)]
            miss_count = len(boats) - len(active_boats)
            course_count = sum(
                get_exhibition_course(boat) is not None for boat in active_boats
            )
            st_count = sum(
                get_exhibition_st(boat) is not None for boat in active_boats
            )
            time_count = sum(
                get_exhibition_time(boat) is not None for boat in active_boats
            )

            # 暫定Ver.1: 展示進入・展示タイム・展示STが6艇分揃ってから更新。
            required_count = len(active_boats)
            if required_count < 3 or course_count < required_count or time_count < required_count or st_count < required_count:
                skipped_no_live_data.append(race_id)
                continue

            try:
                scored = score_race(
                    race,
                    public_store,
                    payload.get("history_feature_manifest"),
                    saved_morning_races.get(race_id),
                )
            except RuntimeError as exc:
                # 1レースの履歴欠損で、同時刻に取得済みの他レースまで失わない。
                skipped_score_error.append({
                    "race_id": race_id,
                    "error": str(exc),
                })
                print(f"WARN: {race_id} は直前計算を個別スキップ: {exc}")
                continue

            fallback_info = None
            for item in scored:
                trace = item.get("input_trace") or {}
                if trace.get("structural_course_fallback"):
                    fallback_info = trace["structural_course_fallback"]
                    break
            if fallback_info:
                structural_fallback_races.append({
                    "race_id": race_id,
                    **fallback_info,
                })

            prediction_quality = {
                "status": "fallback" if fallback_info else "normal",
                "mark": "⚠" if fallback_info else "",
                "label": "補完あり" if fallback_info else "正常",
                "recovery_needed": bool(fallback_info),
                "reason": (fallback_info or {}).get("reason") if fallback_info else [],
                "fallback_source": (fallback_info or {}).get("source") if fallback_info else None,
                "request_started_before_deadline": bool(
                    requested_at is not None and deadline is not None and requested_at < deadline
                ),
                "request_grace_used": request_grace_used,
                "recorded_at": now.isoformat(),
            }

            pred = {
                "race_id": race_id,
                "date": race.get("date"),
                "venue_code": race.get("venue_code"),
                "venue_name": race.get("venue_name"),
                "race": race.get("race"),
                "race_name": race.get("race_name"),
                "deadline": race.get("deadline"),
                "generated_at": now.isoformat(),
                "score_model_version": MODEL_VERSION,
                "logic_config": LIVE_CONFIG_META,
                "prediction_quality": prediction_quality,
                "live_data_counts": {
                    "exhibition_course": course_count,
                    "exhibition_time": time_count,
                    "exhibition_st": st_count,
                    "miss": miss_count,
                    "active_boats": required_count,
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
            "weights": {"structural": LIVE_WEIGHTS["structural"]*100.0, "exhibition_time": LIVE_WEIGHTS["exhibition_time"]*100.0, "exhibition_st": LIVE_WEIGHTS["exhibition_st"]*100.0, "F": "included_in_exST", "environment": 0.0},
            "input_race_count": len(races),
            "prediction_race_count": len(predicted_races),
            "prediction_boat_count": len(csv_rows),
            "skipped_after_deadline": skipped_after_deadline,
            "skipped_no_live_data": skipped_no_live_data,
            "skipped_score_error": skipped_score_error,
            "structural_fallback_races": structural_fallback_races,
            "current_day_result_leakage": 0,
            "errors": skipped_score_error,
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
            "weights": {"structural": LIVE_WEIGHTS["structural"]*100.0, "exhibition_time": LIVE_WEIGHTS["exhibition_time"]*100.0, "exhibition_st": LIVE_WEIGHTS["exhibition_st"]*100.0, "F": 0.0, "environment": 0.0},
            "live_policy": {
                "course": "32点を展示進入コースへ差し替え",
                "exhibition_st": "本人90日平均STとの差を14%評価。±0.06秒で最大補正、展示F=0.4、90日ST10走未満/欠損=0.5",
                "exhibition_time": "6%。レース内展示タイム順位で評価",
                "missing_course_history": "直前コース履歴欠損時のみ、当日朝の保存済み本番スコアを構造80%へ使用。欠損値の0点・架空補完はしない",
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
            "weights": {"structural": LIVE_WEIGHTS["structural"]*100.0, "exhibition_time": LIVE_WEIGHTS["exhibition_time"]*100.0, "exhibition_st": LIVE_WEIGHTS["exhibition_st"]*100.0, "F": 0.0, "environment": 0.0},
            "race_count": len(final_races),
            "boat_count": len(final_rows),
            "selection_rule": (
                "締切済みrace_idは既存最終予測を保持。"
                "締切前race_idだけprovisional_v1_80_6_14で更新"
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
