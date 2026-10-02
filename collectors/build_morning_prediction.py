from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

JST = timezone(timedelta(hours=9))

MODEL_VERSION = "racer_course_grade_exst_v1_20261003"

# 9/30+10/1の主評価でTOP3整合率が最も高かった配点（No.4）
# 合計100。朝は展示STがまだ無いため、残り97点を利用可能分で再正規化。
UNIFIED_WEIGHTS = {
    "course": 32.0,
    "official": 12.0,
    "recent": 8.0,
    "venue": 6.0,
    "motor": 1.0,
    "boat": 6.0,
    "grade": 15.0,
    "avgST": 0.0,
    "series": 17.0,
    "exTime": 0.0,
    "exST": 3.0,
    "discipline": 0.0,
}

MORNING_KEYS = [
    "course",
    "official",
    "recent",
    "venue",
    "motor",
    "boat",
    "grade",
    "series",
]

FRAME_PRIOR = {1: 1.00, 2: 0.72, 3: 0.62, 4: 0.58, 5: 0.46, 6: 0.38}
GRADE_PRIOR = {"A1": 1.00, "A2": 0.75, "B1": 0.45, "B2": 0.25}

FORBIDDEN_CURRENT_RESULT_KEYS = {
    "finish",
    "result",
    "race_time",
    "actual_st",
    "actual_course",
}

PUBLIC_BASE = (
    "https://raw.githubusercontent.com/"
    "BoatraceCSV/boatracecsv.github.io/main/data"
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="TOP3整合率重視の統一スコアで朝予測を生成"
    )
    parser.add_argument("--date", required=True, help="対象日 YYYYMMDD")
    parser.add_argument(
        "--input",
        default=None,
        help="入力JSON。省略時は data/prediction_input_enriched_morning_YYYYMMDD.json",
    )
    parser.add_argument("--output-dir", default="data")
    parser.add_argument(
        "--public-source-dir",
        default=None,
        help="検証用。指定時は外部CSVをローカルから読む",
    )
    return parser.parse_args()


def text(value):
    return "" if value is None else str(value).strip()


def to_float(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def to_int(value):
    n = to_float(value)
    return None if n is None else int(n)


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, float(value)))


def canonical_race_code(value):
    return "".join(re.findall(r"\d", text(value)))


def rate100(value):
    n = to_float(value)
    return None if n is None else clamp(n / 100.0)


def winrate10(value):
    n = to_float(value)
    return None if n is None else clamp(n / 10.0)


def weighted_mean(items):
    num = 0.0
    den = 0.0
    for value, weight in items:
        if value is None or float(weight) <= 0:
            continue
        num += float(value) * float(weight)
        den += float(weight)
    return None if den <= 0 else num / den


def finish_sequence_score(raw):
    # "５　６３２　１５２３２２" 等から着順1〜6だけを抽出。
    s = text(raw).translate(str.maketrans("１２３４５６", "123456"))
    vals = [int(x) for x in re.findall(r"[1-6]", s)]
    if not vals:
        return None
    return sum((7.0 - v) / 6.0 for v in vals) / len(vals)


def recent_five_series_score(row, lane):
    if not isinstance(row, dict):
        return None
    ss = 0.0
    sw = 0.0
    for j in range(1, 6):
        v = finish_sequence_score(row.get(f"艇{lane}_前{j}節_着順列"))
        if v is None:
            continue
        w = 6 - j  # 直近ほど5,4,3,2,1
        ss += v * w
        sw += w
    return None if sw <= 0 else ss / sw


def current_series_score(card_row, lane):
    if not isinstance(card_row, dict):
        return None
    vals = []
    for day in range(1, 8):
        for run in range(1, 3):
            finish = to_int(card_row.get(f"艇{lane}_節D{day}走{run}_着順"))
            if finish is not None and 1 <= finish <= 6:
                vals.append((7.0 - finish) / 6.0)
    return None if not vals else sum(vals) / len(vals)


def rank_lower_is_better(values):
    valid = [(lane, v) for lane, v in values.items() if v is not None]
    if not valid:
        return {}
    valid.sort(key=lambda x: x[1])
    if len(valid) == 1:
        return {valid[0][0]: 0.5}
    return {
        lane: 1.0 - (idx / (len(valid) - 1))
        for idx, (lane, _) in enumerate(valid)
    }


def _csv_rows(s):
    return list(csv.DictReader(io.StringIO(s)))


def _download_text(url):
    req = Request(url, headers={"User-Agent": "boatrace-unified-top3/1.0"})
    with urlopen(req, timeout=30) as res:
        return res.read().decode("utf-8-sig")


def _load_source_file(target_date, rel, local_dir=None):
    yyyy, mm, dd = target_date[:4], target_date[4:6], target_date[6:8]
    date_slash = f"{yyyy}/{mm}/{dd}"
    name = Path(rel.format(date=date_slash)).name
    candidates = []
    if local_dir:
        base = Path(local_dir)
        candidates += [base / name, base / f"{target_date}_{name}"]
    # Production fallback: daily collection already stores public/base inputs locally.
    candidates += [
        Path("data") / name,
        Path("data") / f"{target_date}_{name}",
        Path("daily_inputs") / yyyy / mm / dd / "base" / name,
        Path("daily_inputs") / yyyy / mm / dd / "base" / f"{target_date}_{name}",
    ]
    for p in candidates:
        if p.exists():
            return p.read_text(encoding="utf-8-sig")
    if local_dir:
        raise FileNotFoundError(f"ローカル公開CSVがありません: {name}")
    url = f"{PUBLIC_BASE}/{rel.format(date=date_slash)}"
    return _download_text(url)

class PublicStore:
    def __init__(self, target_date, local_dir=None, include_stt=False):
        self.target_date = target_date
        self.card = self._map(
            _csv_rows(
                _load_source_file(
                    target_date,
                    "programs/race_cards/{date}.csv",
                    local_dir,
                )
            )
        )
        self.recent_national = self._map(
            _csv_rows(
                _load_source_file(
                    target_date,
                    "programs/recent_national/{date}.csv",
                    local_dir,
                )
            )
        )
        self.recent_local = self._map(
            _csv_rows(
                _load_source_file(
                    target_date,
                    "programs/recent_local/{date}.csv",
                    local_dir,
                )
            )
        )
        self.stt = {}
        if include_stt:
            try:
                self.stt = self._map(
                    _csv_rows(
                        _load_source_file(
                            target_date,
                            "previews/stt/{date}.csv",
                            local_dir,
                        )
                    )
                )
            except Exception:
                self.stt = {}

    @staticmethod
    def _map(rows):
        return {
            canonical_race_code(row.get("レースコード")): row
            for row in rows
            if canonical_race_code(row.get("レースコード"))
        }


def official_score(card, lane):
    nwr = winrate10(card.get(f"艇{lane}_全国勝率"))
    n2 = rate100(card.get(f"艇{lane}_全国2連対率"))
    n3 = rate100(card.get(f"艇{lane}_全国3連対率"))
    return weighted_mean([(nwr, 0.40), (n2, 0.35), (n3, 0.25)])


def venue_score(card, recent_local_row, lane):
    lwr = winrate10(card.get(f"艇{lane}_当地勝率"))
    l2 = rate100(card.get(f"艇{lane}_当地2連対率"))
    l3 = rate100(card.get(f"艇{lane}_当地3連対率"))
    official_local = weighted_mean([(lwr, 0.45), (l2, 0.30), (l3, 0.25)])
    hist_local = recent_five_series_score(recent_local_row, lane)
    return weighted_mean([(official_local, 0.60), (hist_local, 0.40)])


def equipment_score(card, lane, prefix):
    r2 = rate100(card.get(f"艇{lane}_{prefix}2連対率"))
    r3 = rate100(card.get(f"艇{lane}_{prefix}3連対率"))
    return weighted_mean([(r2, 0.55), (r3, 0.45)])


def grade_score(card, lane):
    return GRADE_PRIOR.get(text(card.get(f"艇{lane}_級別")).upper())


def feature_component(name, raw_value, source):
    weight = float(UNIFIED_WEIGHTS[name])
    if raw_value is None:
        return {
            "name": name,
            "available": False,
            "raw_score_0_1": None,
            "weight": weight,
            "weighted_points": 0.0,
            "source": source,
        }
    value = clamp(raw_value)
    return {
        "name": name,
        "available": True,
        "raw_score_0_1": round(value, 6),
        "weight": weight,
        "weighted_points": round(value * weight, 4),
        "source": source,
    }


_RC_CACHE = None
def racer_course_score(registration_no, course_no):
    global _RC_CACHE
    if _RC_CACHE is None:
        _RC_CACHE = {}
        p = Path("features/racer_course_features.csv")
        if p.exists():
            with p.open(encoding="utf-8-sig", newline="") as h:
                for r in csv.DictReader(h):
                    try: k=(str(int(float(r.get("registration_no")))),str(int(float(r.get("course")))))
                    except (TypeError,ValueError): continue
                    def rr(name, default=.5):
                        try:
                            v=float(r.get(name)); return v/100.0 if v>1 else v
                        except (TypeError,ValueError): return default
                    def invst():
                        try: return max(0.0,min(1.0,1-float(r.get("d90_avg_st"))/.35))
                        except (TypeError,ValueError): return .5
                    _RC_CACHE[k]=.45*rr("d90_top3_rate")+.25*rr("d90_win_rate")+.15*rr("d90_top2_rate")+.15*invst()
    try: key=(str(int(float(registration_no))),str(int(float(course_no))))
    except (TypeError,ValueError): return None
    return _RC_CACHE.get(key)

def score_boat(race, boat, public_store, course_override=None):
    lane = to_int(boat.get("boat"))
    race_code = canonical_race_code(race.get("race_id"))
    card = public_store.card.get(race_code)
    rn = public_store.recent_national.get(race_code)
    rl = public_store.recent_local.get(race_code)

    if lane not in {1, 2, 3, 4, 5, 6}:
        raise RuntimeError(f"艇番異常: {race.get('race_id')} {boat.get('boat')}")
    if not card:
        raise RuntimeError(f"公開番組CSVにrace_idがありません: {race.get('race_id')}")

    # 登録番号が取れる場合は突合して、艇ズレを検知。
    project_reg = to_int((boat.get("racer") or {}).get("registration_no"))
    public_reg = to_int(card.get(f"艇{lane}_登録番号"))
    if (
        project_reg is not None
        and public_reg is not None
        and project_reg != public_reg
    ):
        raise RuntimeError(
            f"登録番号不一致: {race.get('race_id')} {lane}号艇 "
            f"project={project_reg} public={public_reg}"
        )

    course_no = to_int(course_override) if course_override is not None else lane
    if course_no not in {1, 2, 3, 4, 5, 6}:
        course_no = lane

    components = {
        "course": feature_component(
            "course",
            FRAME_PRIOR.get(course_no),
            (
                f"展示進入コース={course_no}"
                if course_override is not None
                else f"朝時点は枠番={lane}"
            ),
        ),
        "official": feature_component(
            "official",
            official_score(card, lane),
            "全国勝率40%＋全国2連率35%＋全国3連率25%",
        ),
        "recent": feature_component(
            "recent",
            recent_five_series_score(rn, lane),
            "全国直近5節の着順列（直近5,4,3,2,1重み）",
        ),
        "venue": feature_component(
            "venue",
            venue_score(card, rl, lane),
            "当地勝率/2連/3連＋当地直近5節",
        ),
        "motor": feature_component(
            "motor",
            equipment_score(card, lane, "モーター"),
            "モーター2連率55%＋3連率45%",
        ),
        "boat": feature_component(
            "boat",
            equipment_score(card, lane, "ボート"),
            "ボート2連率55%＋3連率45%",
        ),
        "grade": feature_component(
            "grade",
            grade_score(card, lane),
            "級別 A1=1.00/A2=.78/B1=.48/B2=.30",
        ),
        "series": feature_component(
            "series",
            current_series_score(card, lane),
            "今節の当該日より前までの着順",
        ),
    }

    available_weight = sum(
        c["weight"] for c in components.values() if c["available"] and c["weight"] > 0
    )
    weighted_points = sum(
        c["weighted_points"]
        for c in components.values()
        if c["available"] and c["weight"] > 0
    )
    # 10/2 retrospective test best racer-course structure for tomorrow's provisional production:
    # morning = racer-course suitability x grade; live adds exhibition-ST multiplicatively.
    rc = racer_course_score(public_reg or project_reg, course_no)
    gs = grade_score(card, lane)
    if rc is not None and gs is not None:
        score = rc * gs * 100.0
    else:
        score = 0.0 if available_weight <= 0 else weighted_points / available_weight * 100.0

    racer = boat.get("racer") or {}
    motor = boat.get("motor") or {}
    boat_machine = boat.get("boat_machine") or {}

    return {
        "boat": lane,
        "registration_no": racer.get("registration_no"),
        "racer_name": racer.get("name"),
        "grade": racer.get("grade"),
        "motor_no": motor.get("motor_no"),
        "boat_no": boat_machine.get("boat_no"),
        "score": round(score, 2),
        "base_score": round(score, 2),
        "trend_adjustment_points": 0.0,
        "f_l_penalty_points": 0.0,
        "data_coverage_pct": round(
            available_weight / sum(UNIFIED_WEIGHTS[k] for k in MORNING_KEYS) * 100.0,
            1,
        ),
        "components": components,
        "note": (
            "racer_course_grade_exst_v1。朝は選手×当該コース適性×級別、"
            "直前で展示STを乗算する暫定本番スコア"
        ),
    }


def validate_current_day_no_results(payload):
    violations = []
    races = payload.get("races")
    if not isinstance(races, list):
        return ["racesがlistではありません"]

    for race in races:
        race_id = text(race.get("race_id"))
        boats = race.get("boats")
        if not isinstance(boats, list):
            violations.append(f"{race_id}: boats不正")
            continue
        for boat in boats:
            lane = boat.get("boat")
            for key in FORBIDDEN_CURRENT_RESULT_KEYS & set(boat.keys()):
                violations.append(
                    f"{race_id} {lane}号艇: 当日結果キー {key} を検出"
                )
    return violations


def prediction_strength(ranked):
    if len(ranked) < 2:
        return {"top1_top2_gap": None, "top1_top3_gap": None}
    top1 = ranked[0]["score"]
    top2 = ranked[1]["score"]
    top3 = ranked[2]["score"] if len(ranked) >= 3 else None
    return {
        "top1_top2_gap": round(top1 - top2, 2),
        "top1_top3_gap": round(top1 - top3, 2) if top3 is not None else None,
    }


def write_csv(path, rows):
    fields = [
        "target_date",
        "venue_code",
        "venue_name",
        "race",
        "race_id",
        "rank",
        "boat",
        "registration_no",
        "racer_name",
        "grade",
        "motor_no",
        "boat_no",
        "score",
        "base_score",
        "trend_adjustment_points",
        "f_l_penalty_points",
        "data_coverage_pct",
    ]
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    args = parse_args()
    target_date = args.date

    try:
        datetime.strptime(target_date, "%Y%m%d")
    except ValueError:
        print("ERROR: --dateはYYYYMMDD形式です", file=sys.stderr)
        return 1

    if abs(sum(UNIFIED_WEIGHTS.values()) - 100.0) > 1e-9:
        print("ERROR: UNIFIED_WEIGHTSの合計が100ではありません", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    input_path = (
        Path(args.input)
        if args.input
        else output_dir / f"prediction_input_enriched_morning_{target_date}.json"
    )
    output_json = output_dir / f"morning_predictions_{target_date}.json"
    output_csv = output_dir / f"morning_predictions_{target_date}.csv"
    validation_json = output_dir / f"morning_predictions_validation_{target_date}.json"

    if not input_path.exists():
        print(f"ERROR: 入力ファイルがありません: {input_path}", file=sys.stderr)
        return 1

    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))

        if text(payload.get("target_date")) != target_date:
            raise RuntimeError("入力JSONのtarget_dateが指定日と一致しません")
        if text(payload.get("prediction_stage")) != "morning":
            raise RuntimeError("朝予測以外のprediction_inputです")

        violations = validate_current_day_no_results(payload)
        if violations:
            raise RuntimeError(f"当日結果データ混入を検出: {violations[:5]}")

        public_store = PublicStore(
            target_date,
            local_dir=args.public_source_dir,
            include_stt=False,
        )

        races = payload.get("races")
        if not isinstance(races, list):
            raise RuntimeError("racesが不正です")

        prediction_races = []
        csv_rows = []
        all_scores = []
        all_coverages = []

        for race in races:
            boats = race.get("boats")
            if not isinstance(boats, list) or len(boats) != 6:
                raise RuntimeError(
                    f"6艇ではないレースがあります: {race.get('race_id')}"
                )

            scored = [
                score_boat(race, boat, public_store, course_override=None)
                for boat in boats
            ]
            scored.sort(key=lambda x: (-x["score"], x["boat"]))

            for rank, row in enumerate(scored, 1):
                row["rank"] = rank
                all_scores.append(row["score"])
                all_coverages.append(row["data_coverage_pct"])
                csv_rows.append(
                    {
                        "target_date": target_date,
                        "venue_code": race.get("venue_code"),
                        "venue_name": race.get("venue_name"),
                        "race": race.get("race"),
                        "race_id": race.get("race_id"),
                        "rank": rank,
                        "boat": row["boat"],
                        "registration_no": row["registration_no"],
                        "racer_name": row["racer_name"],
                        "grade": row["grade"],
                        "motor_no": row["motor_no"],
                        "boat_no": row["boat_no"],
                        "score": row["score"],
                        "base_score": row["base_score"],
                        "trend_adjustment_points": 0.0,
                        "f_l_penalty_points": 0.0,
                        "data_coverage_pct": row["data_coverage_pct"],
                    }
                )

            prediction_races.append(
                {
                    "race_id": race.get("race_id"),
                    "date": race.get("date"),
                    "venue_code": race.get("venue_code"),
                    "venue_name": race.get("venue_name"),
                    "race": race.get("race"),
                    "race_name": race.get("race_name"),
                    "deadline": race.get("deadline"),
                    "morning_order": [x["boat"] for x in scored],
                    "top3_boats": [x["boat"] for x in scored[:3]],
                    "strength": prediction_strength(scored),
                    "boats": scored,
                }
            )

        result = {
            "schema_version": "1.0",
            "model_version": MODEL_VERSION,
            "target_date": target_date,
            "prediction_stage": "morning",
            "generated_at": datetime.now(JST).isoformat(),
            "score_note": (
                "9/30+10/1累積でTOP3整合率が最も高かったNo.4配点。"
                "朝は展示ST未取得のため97点分を再正規化。"
                "trend/F-Lの別建て補正は停止。"
            ),
            "weights": UNIFIED_WEIGHTS,
            "morning_effective_weight_total": 97.0,
            "frame_prior": FRAME_PRIOR,
            "race_count": len(prediction_races),
            "boat_count": len(csv_rows),
            "races": prediction_races,
        }

        output_json.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        write_csv(output_csv, csv_rows)

        expected_races = len(races)
        expected_boats = expected_races * 6
        if len(prediction_races) != expected_races:
            raise RuntimeError(
                f"予測レース数不一致: {len(prediction_races)} != {expected_races}"
            )
        if len(csv_rows) != expected_boats:
            raise RuntimeError(
                f"予測艇数不一致: {len(csv_rows)} != {expected_boats}"
            )

        validation = {
            "status": "PASS",
            "model_version": MODEL_VERSION,
            "target_date": target_date,
            "prediction_stage": "morning",
            "race_count": len(prediction_races),
            "boat_count": len(csv_rows),
            "score_min": round(min(all_scores), 2),
            "score_max": round(max(all_scores), 2),
            "score_average": round(sum(all_scores) / len(all_scores), 2),
            "average_data_coverage_pct": round(
                sum(all_coverages) / len(all_coverages), 1
            ),
            "current_day_result_leakage": 0,
            "course_used": False,
            "exhibition_used": False,
            "weights": UNIFIED_WEIGHTS,
        }
        validation_json.write_text(
            json.dumps(validation, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print("========================================")
        print("朝予測スコア生成")
        print("モデル:", MODEL_VERSION)
        print("配点:", UNIFIED_WEIGHTS)
        print("レース数:", len(prediction_races))
        print("朝予測生成: PASS")
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
                    "generated_at": datetime.now(JST).isoformat(),
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
