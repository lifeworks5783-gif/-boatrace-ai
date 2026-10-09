from __future__ import annotations

import argparse
import csv
import itertools
import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import requests
from bs4 import BeautifulSoup
from production_config import load_config

SIGNAL_RULES, SIGNAL_RULES_META = load_config("signal")
PURCHASE_RULES, PURCHASE_RULES_META = load_config("purchase")


JST = timezone(timedelta(hours=9))

FORMATION_MODEL = "formation_gap_flow_v2"

DOWN_SIGNAL_RULE_VERSION = "down_signal_v0_20261007"
UP_SIGNAL_RULE_VERSION = "raijin_signal_v1_20261008"
SIGNAL_SYSTEM_NAME = "風神雷神シグナル"
SIGNAL_AI_CONFIG_PATH = Path("config/signal_ai/signal_ai_corrections_v1_20261008.json")
SIGNAL_AI_MODEL_VERSION = "signal_ai_revalue_v1_20261008"


def parse_args():
    parser = argparse.ArgumentParser(
        description="スマホ確認用最新予想＋3連単フォーメーション生成"
    )
    parser.add_argument(
        "--date",
        required=True,
    )
    parser.add_argument(
        "--now",
        default=None,
    )
    return parser.parse_args()


def text(value):
    if value is None:
        return ""
    return str(value).strip()


def to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def to_float(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    return value


def parse_now(value):
    if not value:
        return datetime.now(JST)

    raw = value.strip().replace(
        "Z",
        "+00:00",
    )

    dt = datetime.fromisoformat(raw)

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=JST
        )

    return dt.astimezone(JST)


def load_json(
    path,
    required=False,
):
    path = Path(path)

    if not path.exists():
        if required:
            raise RuntimeError(
                f"ファイルがありません: {path}"
            )
        return None

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def prediction_map(payload):
    if not isinstance(
        payload,
        dict,
    ):
        return {}

    races = payload.get(
        "races"
    )

    if not isinstance(
        races,
        list,
    ):
        return {}

    result = {}

    for race in races:
        race_id = text(
            race.get(
                "race_id"
            )
        )

        if race_id:
            result[
                race_id
            ] = race

    return result


def numeric_score(row):
    value = to_float(
        row.get(
            "score"
        )
    )

    return value


def ranked_boats(race):
    boats = (
        race.get(
            "boats"
        )
        or []
    )

    rows = []

    for boat in boats:
        boat_no = to_int(
            boat.get(
                "boat"
            )
        )

        if boat_no is None:
            continue

        rows.append(
            boat
        )

    def sort_key(row):
        rank = to_int(
            row.get(
                "rank"
            )
        )

        score = numeric_score(
            row
        )

        boat_no = (
            to_int(
                row.get(
                    "boat"
                )
            )
            or 99
        )

        if rank is not None:
            return (
                0,
                rank,
                boat_no,
            )

        return (
            1,
            -(
                score
                if score is not None
                else -999.0
            ),
            boat_no,
        )

    rows.sort(
        key=sort_key
    )

    return rows



def build_up_signal(
    boats,
    prediction_quality=None,
):
    """Raijin display signal. Save/analyze only; never changes AI or formation."""
    quality = prediction_quality or {}
    if (
        quality.get("recovery_needed")
        or text(quality.get("status")) == "fallback"
    ):
        return {
            "available": False,
            "active": False,
            "level": 0,
            "rule_version": UP_SIGNAL_RULE_VERSION,
            "system_name": SIGNAL_SYSTEM_NAME,
            "signal_name": "雷神",
            "candidates": [],
            "max_rise": None,
            "ai_effect": False,
            "formation_effect": False,
            "suppressed_reason": "fallback_prediction",
        }

    if len(boats) != 6:
        return {
            "available": False,
            "active": False,
            "level": 0,
            "rule_version": UP_SIGNAL_RULE_VERSION,
            "system_name": SIGNAL_SYSTEM_NAME,
            "signal_name": "雷神",
            "candidates": [],
            "max_rise": None,
            "ai_effect": False,
            "formation_effect": False,
            "suppressed_reason": "incomplete_boats",
        }

    candidates = []
    for live_rank, row in enumerate(boats, start=1):
        live_score = to_float(row.get("score"))
        morning_score = to_float(row.get("morning_score_reference"))
        boat = boat_number(row)
        if (
            live_rank <= 3
            or boat is None
            or live_score is None
            or morning_score is None
        ):
            continue
        rise = live_score - morning_score
        if rise >= SIGNAL_RULES["raijin"]["rise_min"]:
            candidates.append({
                "boat": boat,
                "rank": live_rank,
                "rise": round(rise, 2),
                "score": round(live_score, 2),
            })

    max_rise = max(
        (item["rise"] for item in candidates),
        default=None,
    )
    has_score50 = any(
        item.get("score") is not None
        and item["score"] >= SIGNAL_RULES["raijin"]["level3_score_min"]
        for item in candidates
    )
    if max_rise is None:
        level = 0
    elif has_score50:
        # Lv3: 通常予測スコア50以上まで浮上した雷神対象艇がいる。
        level = 3
    elif max_rise >= SIGNAL_RULES["raijin"]["level2_rise_min"]:
        # Lv2: +10以上。Lv3条件に該当しない限り上限なし。
        level = 2
    else:
        level = 1

    return {
        "available": True,
        "active": level > 0,
        "level": level,
        "rule_version": UP_SIGNAL_RULE_VERSION,
        "system_name": SIGNAL_SYSTEM_NAME,
        "signal_name": "雷神",
        "thresholds": {
            "level1_rise_min": SIGNAL_RULES["raijin"]["rise_min"],
            "level1_rise_max_exclusive": SIGNAL_RULES["raijin"]["level2_rise_min"],
            "level2_rise_min": SIGNAL_RULES["raijin"]["level2_rise_min"],
            "level2_rise_max": None,
            "level3_candidate_score_min": SIGNAL_RULES["raijin"]["level3_score_min"],
            "level3_candidate_rise_min": SIGNAL_RULES["raijin"]["rise_min"],
            "outside_live_top3": True,
            "level3_priority": True,
        },
        "candidates": candidates,
        "max_rise": max_rise,
        "has_score50_candidate": has_score50,
        "ai_effect": False,
        "formation_effect": False,
        "status": "provisional_analysis_only",
    }


def build_down_signal(
    boats,
    prediction_quality=None,
):
    """Provisional decline signal. Display/save only; never changes AI or formation."""
    quality = prediction_quality or {}
    if (
        quality.get("recovery_needed")
        or text(quality.get("status")) == "fallback"
    ):
        return {
            "available": False,
            "active": False,
            "level": 0,
            "rule_version": DOWN_SIGNAL_RULE_VERSION,
            "reasons": [],
            "suppressed_reason": "fallback_prediction",
        }

    if len(boats) != 6:
        return {
            "available": False,
            "active": False,
            "level": 0,
            "rule_version": DOWN_SIGNAL_RULE_VERSION,
            "reasons": [],
            "suppressed_reason": "incomplete_boats",
        }

    live_scores = []
    deltas = []

    for row in boats:
        live_score = to_float(row.get("score"))
        morning_score = to_float(row.get("morning_score_reference"))
        if live_score is None or morning_score is None:
            return {
                "available": False,
                "active": False,
                "level": 0,
                "rule_version": DOWN_SIGNAL_RULE_VERSION,
                "reasons": [],
                "suppressed_reason": "missing_morning_reference",
            }
        live_scores.append(live_score)
        deltas.append(live_score - morning_score)

    rank1_delta = deltas[0]
    top3_delta_sum = sum(deltas[:3])
    gap12 = live_scores[0] - live_scores[1]

    criteria = [
        {
            "id": "rank1_drop_5",
            "label": "直前1位が朝比-5点以下",
            "met": rank1_delta <= SIGNAL_RULES["fujin"]["conditions"]["rank1_drop_5"],
        },
        {
            "id": "top3_total_drop_10",
            "label": "直前TOP3合計が朝比-10点以下",
            "met": top3_delta_sum <= SIGNAL_RULES["fujin"]["conditions"]["top3_total_drop_10"],
        },
        {
            "id": "rank1_drop_close_gap",
            "label": "直前1位が朝比-3点以下かつ1-2位差5点以内",
            "met": rank1_delta <= SIGNAL_RULES["fujin"]["conditions"]["rank1_drop_close_gap"]["max_drop"] and gap12 <= SIGNAL_RULES["fujin"]["conditions"]["rank1_drop_close_gap"]["max_gap"],
        },
    ]
    reasons = [
        item["id"]
        for item in criteria
        if item["met"]
    ]
    level = min(SIGNAL_RULES["fujin"]["level_cap"], len(reasons))

    return {
        "available": True,
        "active": level > 0,
        "level": level,
        "rule_version": DOWN_SIGNAL_RULE_VERSION,
        "reasons": reasons,
        "criteria": criteria,
        "metrics": {
            "rank1_delta": round(rank1_delta, 2),
            "top3_delta_sum": round(top3_delta_sum, 2),
            "gap_1_2": round(gap12, 2),
        },
        "ai_effect": False,
        "formation_effect": False,
        "status": "provisional_analysis_only",
    }

def load_signal_ai_config():
    if not SIGNAL_AI_CONFIG_PATH.is_file():
        raise RuntimeError(f"シグナルAI補正設定がありません: {SIGNAL_AI_CONFIG_PATH}")
    config = json.loads(SIGNAL_AI_CONFIG_PATH.read_text(encoding="utf-8"))
    config["_source"] = str(SIGNAL_AI_CONFIG_PATH)
    return config


def build_signal_ai_prediction(boats, up_signal, down_signal, config):
    """Revalue all boats for signal-only AI ranking without changing normal scores."""
    fujin_level = int((down_signal or {}).get("level") or 0)
    raijin_level = int((up_signal or {}).get("level") or 0)
    if fujin_level <= 0 and raijin_level <= 0:
        return None
    if len(boats) < 3:
        return None

    rule_key = f"F{fujin_level}R{raijin_level}"
    rule = (config.get("rules") or {}).get(rule_key)
    if not rule:
        raise RuntimeError(f"シグナルAI補正ルール未定義: {rule_key}")

    profiles = config.get("level_profiles") or {}
    attenuation = config.get("raijin_rank_attenuation") or {}
    base_rows = []
    base_score = {}
    delta = {}
    for rank, row in enumerate(boats, start=1):
        boat = boat_number(row)
        score = boat_score(row)
        morning = to_float(row.get("morning_score_reference"))
        if boat is None or score is None:
            continue
        base_score[boat] = float(score)
        delta[boat] = float(score) - morning if morning is not None else 0.0
        base_rows.append({"boat": boat, "rank": rank, "base_score": float(score)})

    if len(base_rows) < 3:
        return None

    adjusted = dict(base_score)
    adjustments = {boat: 0.0 for boat in adjusted}

    f_rule = rule.get("fujin")
    if fujin_level > 0 and f_rule:
        profile = profiles.get(f_rule.get("level_profile")) or {}
        level_mult = float(profile.get(str(fujin_level), 1.0))
        top3 = [x["boat"] for x in base_rows[:3]]
        target = f_rule.get("target")
        if target == "rank1":
            targets = top3[:1]
        elif target == "negative_top3":
            targets = [b for b in top3 if delta.get(b, 0.0) < 0.0]
        else:
            targets = top3
        for boat in targets:
            if f_rule.get("mode") == "drop_ratio":
                penalty = max(0.0, -delta.get(boat, 0.0)) * float(f_rule.get("strength") or 0.0) * level_mult
            else:
                penalty = float(f_rule.get("strength") or 0.0) * level_mult
            adjusted[boat] -= penalty
            adjustments[boat] -= penalty

    r_rule = rule.get("raijin")
    if raijin_level > 0 and r_rule:
        profile = profiles.get(r_rule.get("level_profile")) or {}
        level_mult = float(profile.get(str(raijin_level), 1.0))
        rank_att = attenuation.get(r_rule.get("rank_attenuation")) or {}
        for candidate in (up_signal or {}).get("candidates") or []:
            boat = to_int(candidate.get("boat"))
            rise = to_float(candidate.get("rise"))
            rank = to_int(candidate.get("rank"))
            if boat not in adjusted or rise is None or rank is None:
                continue
            bonus = rise * float(r_rule.get("multiplier") or 0.0) * level_mult * float(rank_att.get(str(rank), 1.0))
            adjusted[boat] += bonus
            adjustments[boat] += bonus

    adjusted_rows = []
    for item in base_rows:
        boat = item["boat"]
        adjusted_rows.append({
            "boat": boat,
            "normal_rank": item["rank"],
            "normal_score": round(base_score[boat], 3),
            "signal_adjustment": round(adjustments[boat], 3),
            "signal_ai_score": round(adjusted[boat], 3),
            "morning_to_current_delta": round(delta.get(boat, 0.0), 3),
        })
    adjusted_rows.sort(key=lambda x: (-x["signal_ai_score"], x["boat"]))
    for rank, item in enumerate(adjusted_rows, start=1):
        item["signal_ai_rank"] = rank

    combos = []
    boats_available = sorted(adjusted)
    for first, second, third in itertools.permutations(boats_available, 3):
        purchase_weights = PURCHASE_RULES["signal_ai"]["ranking_formula"]
        score = adjusted[first] * purchase_weights["first"] + adjusted[second] * purchase_weights["second"] + adjusted[third] * purchase_weights["third"]
        combos.append({
            "combination": f"{first}-{second}-{third}",
            "score": round(score, 3),
        })
    combos.sort(key=lambda x: (-x["score"], x["combination"]))

    required_points = int(PURCHASE_RULES["signal_ai"]["purchase_points"])
    if int(config.get("candidate_points") or 0) != required_points:
        raise RuntimeError("シグナルAIの補正設定と購入点数設定が一致しません")
    candidate_points = min(required_points, len(combos))
    return {
        "model_version": config.get("model_version") or SIGNAL_AI_MODEL_VERSION,
        "logic_effective_date": config.get("effective_date"),
        "logic_config_source": config.get("_source"),
        "signal_rules_config": SIGNAL_RULES_META,
        "purchase_rules_config": PURCHASE_RULES_META,
        "status": "active_signal_ai",
        "normal_prediction_unchanged": True,
        "signal_key": rule_key,
        "fujin_level": fujin_level,
        "raijin_level": raijin_level,
        "rule": rule,
        "points": candidate_points,
        "investment_100yen": candidate_points * 100,
        "boat_scores": sorted(adjusted_rows, key=lambda x: x["boat"]),
        "signal_ai_ranking": adjusted_rows,
        "combinations": combos[:candidate_points],
        "all_120_combinations": combos,
        "valid_combination_count": len(combos),
        "combination_method": config.get("combination_method"),
        "note": "通常予測は変更せず、風神雷神シグナル別補正で6艇を再評価した買い目専用AI。全シグナル組合せで上位24通りを候補保存。",
    }


def parse_deadline(
    target_date,
    value,
):
    raw = text(value)

    if not raw:
        return None

    try:
        dt = datetime.fromisoformat(
            raw.replace(
                "Z",
                "+00:00",
            )
        )

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=JST
            )

        return dt.astimezone(
            JST
        )

    except ValueError:
        pass

    base_date = datetime.strptime(
        target_date,
        "%Y%m%d",
    ).date()

    for fmt in (
        "%H:%M:%S",
        "%H:%M",
        "%H%M",
    ):
        try:
            tm = datetime.strptime(
                raw,
                fmt,
            ).time()

            return datetime.combine(
                base_date,
                tm,
                tzinfo=JST,
            )

        except ValueError:
            pass

    return None


def normalize_external_race_id(value):
    digits = "".join(
        ch
        for ch in str(value or "")
        if ch.isdigit()
    )
    if len(digits) < 12:
        return ""
    return (
        f"{digits[:8]}-"
        f"{digits[8:10]}-"
        f"{digits[10:12]}"
    )


def parse_official_venue_deadlines(
    html,
    target_date,
    venue_code,
):
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    times = []

    label = soup.find(
        string=lambda value: (
            isinstance(value, str)
            and "締切予定時刻" in value
        )
    )

    if label is not None:
        row = label.find_parent(
            "tr"
        )
        if row is not None:
            times = re.findall(
                r"(?<!\d)(\d{1,2}:\d{2})(?!\d)",
                row.get_text(
                    " ",
                    strip=True,
                ),
            )

    if len(times) < 12:
        full_text = soup.get_text(
            " ",
            strip=True,
        )
        pos = full_text.find(
            "締切予定時刻"
        )

        if pos >= 0:
            segment = full_text[
                pos:pos + 500
            ]
            times = re.findall(
                r"(?<!\d)(\d{1,2}:\d{2})(?!\d)",
                segment,
            )[:12]

    if len(times) < 12:
        return {}

    return {
        (
            f"{target_date}-"
            f"{venue_code}-"
            f"{race_no:02d}"
        ): deadline
        for race_no, deadline
        in enumerate(
            times[:12],
            start=1,
        )
    }


def fetch_official_venue_deadlines(
    target_date,
    venue_code,
):
    url = (
        "https://www.boatrace.jp/owpc/pc/race/beforeinfo"
        f"?hd={target_date}"
        f"&jcd={venue_code}"
        "&rno=1"
    )

    try:
        response = requests.get(
            url,
            timeout=(5, 12),
            headers={
                "User-Agent":
                    "Mozilla/5.0 (compatible; boatrace-ai-deadline/1.0)"
            },
        )
        response.raise_for_status()

        return parse_official_venue_deadlines(
            response.text,
            target_date,
            venue_code,
        )

    except Exception as exc:
        print(
            f"WARN: 公式締切取得失敗 {venue_code}:",
            exc,
        )
        return {}


def load_odds_deadline_fallback(
    target_date,
):
    url = (
        "https://raw.githubusercontent.com/"
        "BoatraceCSV/boatracecsv.github.io/main/data/previews/od3/"
        f"{target_date[:4]}/{target_date[4:6]}/{target_date[6:8]}.csv"
    )

    try:
        req = Request(
            url,
            headers={
                "User-Agent":
                    "boatrace-ai-deadline-overlay/1.0"
            },
        )

        with urlopen(
            req,
            timeout=20,
        ) as response:
            body = response.read().decode(
                "utf-8-sig"
            )

        reader = csv.DictReader(
            body.splitlines()
        )

        latest = {}

        for row in reader:
            race_id = normalize_external_race_id(
                row.get(
                    "レースコード",
                    "",
                )
            )
            deadline = text(
                row.get(
                    "締切時刻"
                )
            )
            obtained_at = text(
                row.get(
                    "取得日時"
                )
            )

            if (
                not race_id
                or not deadline
            ):
                continue

            previous = latest.get(
                race_id
            )

            if (
                previous is None
                or obtained_at
                >= previous[0]
            ):
                latest[
                    race_id
                ] = (
                    obtained_at,
                    deadline,
                )

        return {
            race_id: value[1]
            for race_id, value
            in latest.items()
        }

    except Exception as exc:
        print(
            "WARN: オッズ締切フォールバック取得失敗:",
            exc,
        )
        return {}


def load_dynamic_deadlines(
    target_date,
    venue_codes,
):
    official = {}

    with ThreadPoolExecutor(
        max_workers=min(
            max(
                len(venue_codes),
                1,
            ),
            4,
        )
    ) as executor:
        futures = {
            executor.submit(
                fetch_official_venue_deadlines,
                target_date,
                venue_code,
            ): venue_code
            for venue_code
            in venue_codes
        }

        for future in as_completed(
            futures
        ):
            official.update(
                future.result()
            )

    odds = (
        load_odds_deadline_fallback(
            target_date
        )
    )

    for race_id, deadline in odds.items():
        official.setdefault(
            race_id,
            deadline,
        )

    return official


def load_program_deadlines(
    target_date,
):
    path = (
        Path("daily_inputs")
        / target_date[:4]
        / target_date[4:6]
        / target_date[6:8]
        / f"program_races_{target_date}.csv"
    )

    result = {}

    if path.exists():
        with path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as f:

            reader = csv.DictReader(
                f
            )

            for row in reader:
                race_id = text(
                    row.get(
                        "race_id"
                    )
                )

                deadline = (
                    row.get(
                        "deadline"
                    )
                    or row.get(
                        "deadline_time"
                    )
                    or row.get(
                        "close_time"
                    )
                    or row.get(
                        "cutoff_time"
                    )
                )

                if (
                    race_id
                    and deadline
                ):
                    result[
                        race_id
                    ] = deadline

    dynamic = load_dynamic_deadlines(
        target_date,
        sorted(
            {
                race_id.split("-")[1]
                for race_id in result
                if len(race_id.split("-")) >= 3
            }
        ),
    )

    changed = {
        race_id: (
            result.get(race_id),
            deadline,
        )
        for race_id, deadline in dynamic.items()
        if result.get(race_id) != deadline
    }

    if changed:
        print(
            "当日締切変更を最新一覧へ反映:",
            changed,
        )

    result.update(
        dynamic
    )

    return result


def race_deadline_raw(
    race,
    program_deadlines,
):
    race_id = text(
        race.get(
            "race_id"
        )
    )

    # 当日進行遅延などで締切が変わるため、
    # 最新の動的締切を朝予測JSON内の固定時刻より優先する。
    revised = program_deadlines.get(
        race_id
    )

    if revised not in (
        None,
        "",
    ):
        return revised

    return (
        race.get(
            "deadline"
        )
        or race.get(
            "deadline_time"
        )
        or race.get(
            "close_time"
        )
        or race.get(
            "cutoff_time"
        )
    )


def boat_number(row):
    return to_int(
        row.get(
            "boat"
        )
    )


def boat_score(row):
    return numeric_score(
        row
    )


def score_for_calculation(row):
    score = boat_score(
        row
    )

    if score is None:
        return 0.0

    return score


def combo_strength(
    combo,
    score_by_boat,
):
    first, second, third = combo

    weights = PURCHASE_RULES["normal_formation"]["ranking_formula"]
    return (
        score_by_boat[first] * weights["first"]
        + score_by_boat[second] * weights["second"]
        + score_by_boat[third] * weights["third"]
    )


def valid_combinations(
    first_candidates,
    second_candidates,
    third_candidates,
):
    combinations = []

    for (
        first,
        second,
        third,
    ) in itertools.product(
        first_candidates,
        second_candidates,
        third_candidates,
    ):

        if len(
            {
                first,
                second,
                third,
            }
        ) != 3:
            continue

        combinations.append(
            (
                first,
                second,
                third,
            )
        )

    return list(
        dict.fromkeys(
            combinations
        )
    )


def build_formation(
    boats,
):
    # 成立レースの欠場艇は候補から除外し、残った3艇以上でAI評価する。
    # 6艇なら120通り、5艇なら60通り。欠場艇の値は捏造しない。
    if len(boats) < 3:
        return None

    order = [boat_number(row) for row in boats]
    scores = [boat_score(row) for row in boats]

    if any(boat is None for boat in order):
        return None

    if any(score is None for score in scores):
        return {
            "model_version": FORMATION_MODEL,
            "formation_type": "スコア不足",
            "gap_1_2": None,
            "gap_2_3": None,
            "gap_3_4": None,
            "first_candidates": [],
            "second_candidates": [],
            "third_candidates": [],
            "combinations": [],
            "points": 0,
            "investment_100yen": 0,
        }

    score_by_boat = {
        boat_number(row): score_for_calculation(row)
        for row in boats
    }

    gap12 = scores[0] - scores[1]
    gap23 = scores[1] - scores[2]
    gap34 = scores[2] - scores[3] if len(scores) >= 4 else None
    thresholds = PURCHASE_RULES["normal_formation"]["thresholds"]
    maxima = PURCHASE_RULES["normal_formation"]["max_points"]
    close = thresholds["close_gap_max_exclusive"]
    strong = thresholds["strong_gap_min"]
    semi = thresholds["semi_anchor_gap_min"]

    # 流しルール:
    # 1) 1・2位が接近し、3位以下と明確な差 -> 1・2着折返し＋3着流し
    # 2) 1位が強く、2位も3位以下と明確な差 -> 1着・2着固定＋3着流し
    # 3) 1位だけ強い -> 1着固定＋2・3着相手流し
    if gap12 < close and gap23 >= strong:
        formation_type = "1・2着折返し＋3着流し"
        top1, top2 = order[0], order[1]
        tail = order[2:]
        combinations = [
            (top1, top2, c) for c in tail
        ] + [
            (top2, top1, c) for c in tail
        ]
        first_candidates = [top1, top2]
        second_candidates = [top1, top2]
        third_candidates = tail

    elif gap12 >= strong and gap23 >= strong:
        formation_type = "1・2着固定＋3着流し"
        top1, top2 = order[0], order[1]
        tail = order[2:]
        combinations = [(top1, top2, c) for c in tail]
        first_candidates = [top1]
        second_candidates = [top2]
        third_candidates = tail

    elif gap12 >= strong:
        formation_type = "1着固定＋相手流し"
        top1 = order[0]
        tail = order[1:]
        combinations = [
            (top1, b, c)
            for b in tail
            for c in tail
            if b != c
        ]
        combinations.sort(
            key=lambda combo: (
                -combo_strength(combo, score_by_boat),
                combo,
            )
        )
        # 点数過多を避けつつ従来4点より広げる
        combinations = combinations[:maxima["single_anchor"]]
        first_candidates = [top1]
        second_candidates = tail
        third_candidates = tail

    elif gap12 >= semi:
        formation_type = "準軸"
        first_candidates = order[:2]
        second_candidates = order[:3]
        third_candidates = order[:4]
        combinations = valid_combinations(
            first_candidates,
            second_candidates,
            third_candidates,
        )
        combinations.sort(
            key=lambda combo: (
                -combo_strength(combo, score_by_boat),
                combo,
            )
        )
        combinations = combinations[:maxima["semi_anchor"]]

    else:
        formation_type = "混戦"
        first_candidates = order[:2]
        second_candidates = order[:4]
        third_candidates = order[:5]
        combinations = valid_combinations(
            first_candidates,
            second_candidates,
            third_candidates,
        )
        combinations.sort(
            key=lambda combo: (
                -combo_strength(combo, score_by_boat),
                combo,
            )
        )
        combinations = combinations[:maxima["chaos"]]

    return {
        "model_version": FORMATION_MODEL,
        "formation_type": formation_type,
        "gap_1_2": round(gap12, 2),
        "gap_2_3": round(gap23, 2),
        "gap_3_4": round(gap34, 2) if gap34 is not None else None,
        "first_candidates": first_candidates,
        "second_candidates": second_candidates,
        "third_candidates": third_candidates,
        "combinations": [
            f"{a}-{b}-{c}" for a, b, c in combinations
        ],
        "points": len(combinations),
        "investment_100yen": len(combinations) * 100,
    }



AI_SCORE_CONFIG_DIR = Path("config/ai_score")

DEFAULT_AI_SCORE_CONFIG = {
    "schema_version": 1,
    "model_version": "ai_finish_order_score_v0_20261005",
    "effective_date": "20261005",
    "status": "experimental",
    "purchase_points": 8,
    "display_points": 12,
    "joint_method": "geometric_mean",
    "morning": {
        "first": {"racer_course": .35, "grade": .18, "motor": .14, "boat": .05, "national_top2": .10, "overall": .18},
        "second": {"racer_course": .25, "grade": .20, "motor": .17, "boat": .06, "national_top2": .14, "overall": .18},
        "third": {"racer_course": .18, "grade": .16, "motor": .22, "boat": .10, "national_top2": .16, "overall": .18},
    },
    "live": {
        "first": {"structural": .48, "exTime": .10, "exST": .22, "overall": .20},
        "second": {"structural": .58, "exTime": .08, "exST": .14, "overall": .20},
        "third": {"structural": .66, "exTime": .07, "exST": .07, "overall": .20},
    },
}


def load_ai_score_config(target_date):
    """Load the frozen daily AI-score logic. Never infer weights from race results."""
    path = AI_SCORE_CONFIG_DIR / f"{target_date}.json"
    if path.is_file():
        config = json.loads(path.read_text(encoding="utf-8"))
        source = str(path)
    else:
        config = json.loads(json.dumps(DEFAULT_AI_SCORE_CONFIG))
        config["effective_date"] = target_date
        config["model_version"] = f"ai_finish_order_score_fallback_{target_date}"
        source = "built_in_fallback"
    config["_source"] = source
    return config


def _component01(row, key, default=None):
    comps = row.get("components") or {}
    comp = comps.get(key) or {}
    value = to_float(comp.get("raw_score_0_1"))
    if value is None:
        if default is None:
            raise RuntimeError(
                f"AIスコア必須要素欠損: {boat_number(row)}号艇 {key}"
            )
        value = default
    return max(0.0, min(1.0, value))


def _weighted_position_score(values, weights):
    total = 0.0
    for key, weight in weights.items():
        total += float(weight) * values.get(key, 0.5)
    return total


def build_ai_score_prediction(boats, ai_config):
    """Independent finish-position scorer driven only by the frozen daily config."""
    if len(boats) < 3:
        return None

    scored = []
    for row in boats:
        boat = boat_number(row)
        overall = max(0.0, min(1.0, score_for_calculation(row) / 100.0))
        stage = "live" if "structural" in (row.get("components") or {}) else "morning"
        if stage == "live":
            values = {
                "structural": _component01(row, "structural"),
                "exTime": _component01(row, "exTime"),
                "exST": _component01(row, "exST"),
                "overall": overall,
            }
        else:
            values = {
                "racer_course": _component01(row, "racer_course"),
                "grade": _component01(row, "grade"),
                "motor": _component01(row, "motor"),
                "boat": _component01(row, "boat"),
                "national_top2": _component01(row, "national_top2"),
                "overall": overall,
            }
        weights = ai_config[stage]
        first = _weighted_position_score(values, weights["first"])
        second = _weighted_position_score(values, weights["second"])
        third = _weighted_position_score(values, weights["third"])
        scored.append({"boat": boat, "first_score": round(first*100,2), "second_score": round(second*100,2), "third_score": round(third*100,2)})

    by_boat = {x["boat"]: x for x in scored}
    if len(by_boat) != len(boats) or len(by_boat) < 3:
        raise RuntimeError("AIスコア計算対象の有効艇が不完全です")
    combos = []
    for first, second, third in itertools.permutations(sorted(by_boat), 3):
        a,b,d = by_boat[first],by_boat[second],by_boat[third]
        joint=((max(a["first_score"],.01)/100)*(max(b["second_score"],.01)/100)*(max(d["third_score"],.01)/100))**(1/3)
        combos.append({"combination":f"{first}-{second}-{third}","score":round(joint*100,3)})
    combos.sort(key=lambda x:(-x["score"],x["combination"]))
    expected_combos = len(by_boat) * (len(by_boat)-1) * (len(by_boat)-2)
    if len(combos) != expected_combos or len({x["combination"] for x in combos}) != expected_combos:
        raise RuntimeError(f"AIスコア3連単{expected_combos}通りの生成に失敗しました")

    # 風神雷神シグナルは表示・保存・分析専用。
    # 2026-10-07以降、シグナルによるAI再順位付け・購入点数変更は行わない。
    base_combos = [dict(x) for x in combos]
    points = int(ai_config.get("purchase_points", 8))
    signals = {}

    points = min(points, len(combos))
    selected=combos[:points]
    frozen={k:v for k,v in ai_config.items() if not k.startswith("_")}
    return {
        "model_version": ai_config["model_version"],
        "logic_effective_date": ai_config.get("effective_date"),
        "logic_config_source": ai_config.get("_source"),
        "logic_snapshot": frozen,
        "status": ai_config.get("status","experimental"),
        "signal_mode": False,
        "signal_boats": {},
        "signal_rule": {
            "enabled_in_ai": False,
            "reason": "風神雷神シグナルは表示・保存・分析専用",
        },
        "points": points,
        "investment_100yen": points*100,
        "position_scores": sorted(scored,key=lambda x:x["boat"]),
        "first_candidates":[x["boat"] for x in sorted(scored,key=lambda x:(-x["first_score"],x["boat"]))[:3]],
        "second_candidates":[x["boat"] for x in sorted(scored,key=lambda x:(-x["second_score"],x["boat"]))[:4]],
        "third_candidates":[x["boat"] for x in sorted(scored,key=lambda x:(-x["third_score"],x["boat"]))[:5]],
        "boundary_gaps": {},
        "combinations": selected,
        "base_120_combinations": base_combos,
        "all_120_combinations": combos,
        "valid_combination_count": expected_combos,
        "rerank_verified": (
            len(combos) == expected_combos
            and len({x["combination"] for x in combos}) == expected_combos
        ),
        "note":"AIスコア予測はシグナル非依存。風神雷神シグナルは表示・保存・分析だけに使用し、AI再順位付け・点数変更は行わない。",
    }

def score_label(value):
    score = to_float(
        value
    )

    if score is None:
        return "未算出"

    return f"{score:.1f}"


def racer_label(row):
    boat = boat_number(
        row
    )

    name = text(
        row.get(
            "racer_name"
        )
    )

    score = row.get(
        "score"
    )

    if boat is None:
        boat_text = "艇番不明"
    else:
        boat_text = (
            f"{boat}号艇"
        )

    label = boat_text

    if name:
        label += (
            f" {name}"
        )

    label += (
        f" ({score_label(score)})"
    )

    return label


def compact_scores(
    boats,
):
    parts = []

    for rank, row in enumerate(
        boats,
        start=1,
    ):

        parts.append(
            f"{rank}位 "
            f"{racer_label(row)}"
        )

    return " / ".join(
        parts
    )


def formation_candidate_text(
    candidates,
):
    if not candidates:
        return "なし"

    return "・".join(
        str(
            value
        )
        for value
        in candidates
    )


def write_formation_csv(
    path,
    rows,
):
    fields = [
        "target_date",
        "race_id",
        "venue_code",
        "venue_name",
        "race",
        "deadline",
        "prediction_type",
        "quality_status",
        "quality_mark",
        "recovery_needed",
        "formation_type",
        "gap_1_2",
        "first_candidates",
        "second_candidates",
        "third_candidates",
        "points",
        "investment_100yen",
        "combinations",
        "rank1_boat",
        "rank1_score",
        "rank2_boat",
        "rank2_score",
        "rank3_boat",
        "rank3_score",
        "rank4_boat",
        "rank4_score",
        "rank5_boat",
        "rank5_score",
        "rank6_boat",
        "rank6_score",
    ]

    with Path(
        path
    ).open(
        "w",
        encoding="utf-8",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields,
        )

        writer.writeheader()

        for item in rows:

            boats = item[
                "boats"
            ]

            formation = item[
                "formation"
            ]

            row = {
                "target_date": (
                    item[
                        "target_date"
                    ]
                ),
                "race_id": (
                    item[
                        "race_id"
                    ]
                ),
                "venue_code": (
                    item[
                        "venue_code"
                    ]
                ),
                "venue_name": (
                    item[
                        "venue_name"
                    ]
                ),
                "race": (
                    item[
                        "race"
                    ]
                ),
                "deadline": (
                    item[
                        "deadline"
                    ]
                ),
                "prediction_type": (
                    item[
                        "prediction_type"
                    ]
                ),
                "quality_status": ((item.get("prediction_quality") or {}).get("status") or "normal"),
                "quality_mark": ((item.get("prediction_quality") or {}).get("mark") or ""),
                "recovery_needed": bool((item.get("prediction_quality") or {}).get("recovery_needed")),
                "formation_type": (
                    formation[
                        "formation_type"
                    ]
                ),
                "gap_1_2": (
                    formation[
                        "gap_1_2"
                    ]
                ),
                "first_candidates": (
                    "-".join(
                        map(
                            str,
                            formation[
                                "first_candidates"
                            ],
                        )
                    )
                ),
                "second_candidates": (
                    "-".join(
                        map(
                            str,
                            formation[
                                "second_candidates"
                            ],
                        )
                    )
                ),
                "third_candidates": (
                    "-".join(
                        map(
                            str,
                            formation[
                                "third_candidates"
                            ],
                        )
                    )
                ),
                "points": (
                    formation[
                        "points"
                    ]
                ),
                "investment_100yen": (
                    formation[
                        "investment_100yen"
                    ]
                ),
                "combinations": (
                    " / ".join(
                        formation[
                            "combinations"
                        ]
                    )
                ),
            }

            for index in range(
                6
            ):
                boat = boats[index] if index < len(boats) else {}

                row[
                    f"rank{index + 1}_boat"
                ] = boat.get(
                    "boat"
                )

                row[
                    f"rank{index + 1}_score"
                ] = boat.get(
                    "score"
                )

            writer.writerow(
                row
            )


def main():
    args = parse_args()

    target_date = (
        args.date
    )

    now = parse_now(
        args.now
    )

    ai_score_config = load_ai_score_config(target_date)
    signal_ai_config = load_signal_ai_config()
    print("AIスコア日別ロジック:", ai_score_config.get("model_version"), ai_score_config.get("_source"))
    print("シグナルAI補正:", signal_ai_config.get("model_version"), signal_ai_config.get("_source"))

    datetime.strptime(
        target_date,
        "%Y%m%d",
    )

    base = (
        Path(
            "predictions"
        )
        / target_date[:4]
        / target_date[4:6]
        / target_date[6:8]
    )

    morning_payload = (
        load_json(
            base
            / (
                f"morning_predictions_"
                f"{target_date}.json"
            ),
            required=True,
        )
    )

    live_payload = (
        load_json(
            base
            / "live"
            / (
                f"live_predictions_final_"
                f"{target_date}.json"
            ),
            required=False,
        )
    )

    morning = prediction_map(
        morning_payload
    )

    live = prediction_map(
        live_payload
    )

    program_deadlines = (
        load_program_deadlines(
            target_date
        )
    )

    race_ids = sorted(
        set(
            morning
        )
        | set(
            live
        )
    )

    all_rows = []
    upcoming_rows = []

    for race_id in race_ids:

        if race_id in live:

            race = live[
                race_id
            ]

            prediction_type = (
                "直前"
            )

        else:

            race = morning[
                race_id
            ]

            prediction_type = (
                "朝"
            )

        boats = ranked_boats(
            race
        )

        # 成立レースは欠場艇を除いた有効3艇以上なら生成対象にする。
        if len(
            boats
        ) < 3:
            continue

        formation = build_formation(
            boats
        )

        if formation is None:
            continue

        deadline_raw = (
            race_deadline_raw(
                race,
                program_deadlines,
            )
        )

        deadline_dt = (
            parse_deadline(
                target_date,
                deadline_raw,
            )
        )

        prediction_quality = (
            race.get("prediction_quality")
            or {
                "status": "normal",
                "mark": "",
                "label": "正常",
                "recovery_needed": False,
                "reason": [],
                "fallback_source": None,
            }
        )

        # 直前データが締切までに確定しなかった場合も「予測なし」にしない。
        # 締切10分前以降は、保存済み朝予測を直前補完として継続使用し、
        # 必ず品質マークを残す。後から正規の締切前直前予測が保存されたら
        # live側が優先され、この補完表示は自動的に解消する。
        if race_id not in live and race_id in morning and deadline_dt is not None:
            minutes_to_deadline = (deadline_dt - now).total_seconds() / 60.0
            if minutes_to_deadline <= 10.0:
                prediction_type = "直前"
                prediction_quality = {
                    "status": "fallback",
                    "mark": "⚠",
                    "label": "補完あり",
                    "recovery_needed": True,
                    "reason": ["締切前の直前情報が未確定または未保存"],
                    "fallback_source": "saved_morning_prediction",
                    "recorded_at": now.isoformat(),
                }

        cleaned_boats = []

        for index, boat in enumerate(
            boats,
            start=1,
        ):

            cleaned_boats.append(
                {
                    "rank": (
                        index
                    ),
                    "boat": (
                        boat_number(
                            boat
                        )
                    ),
                    "racer_name": (
                        text(
                            boat.get(
                                "racer_name"
                            )
                        )
                    ),
                    "score": (
                        boat_score(
                            boat
                        )
                    ),
                    "morning_score_reference": boat.get("morning_score_reference"),
                    "grade": boat.get("grade"),
                    "registration_no": boat.get("registration_no"),
                    "motor_no": boat.get("motor_no"),
                    "boat_no": boat.get("boat_no"),
                    "exhibition_course": boat.get("exhibition_course"),
                    "exhibition_time": boat.get("exhibition_time"),
                    "exhibition_st": boat.get("exhibition_st"),
                    "exhibition_f": boat.get("exhibition_f"),
                    "components": boat.get("components") or {},
                    "input_trace": boat.get("input_trace") or {},
                }
            )

        # 最新画面で直前予測生成後も朝予測の順位・スコアを参照できるよう、
        # 朝時点の6艇スナップショットを別保存する。
        morning_boats_snapshot = []
        morning_ai_score_prediction = None
        if race_id in morning:
            morning_ranked = ranked_boats(morning[race_id])
            if len(morning_ranked) == 6:
                for morning_index, morning_boat in enumerate(morning_ranked, start=1):
                    morning_boats_snapshot.append({
                        "rank": morning_index,
                        "boat": boat_number(morning_boat),
                        "racer_name": text(morning_boat.get("racer_name")),
                        "score": boat_score(morning_boat),
                        "grade": morning_boat.get("grade"),
                        "registration_no": morning_boat.get("registration_no"),
                        "motor_no": morning_boat.get("motor_no"),
                        "boat_no": morning_boat.get("boat_no"),
                        "components": morning_boat.get("components") or {},
                    })
                morning_ai_score_prediction = build_ai_score_prediction(
                    morning_ranked,
                    ai_score_config,
                )

        # 朝予測の買い目も別途固定保存する。
        # 直前予測へ切り替わった後も、朝時点のフォーメーションを失わない。
        morning_formation = None
        if race_id in morning:
            morning_boats = ranked_boats(morning[race_id])
            if len(morning_boats) == 6:
                morning_formation = build_formation(morning_boats)

        ai_score_prediction = build_ai_score_prediction(
            boats,
            ai_score_config,
        )

        # 風神雷神は通常予測・通常formation・既存AIスコアを変更しない。
        # シグナル専用の別レイヤーで6艇を再評価し、上位24通りを保存する。
        up_signal = build_up_signal(
            boats,
            prediction_quality,
        )
        down_signal = build_down_signal(
            boats,
            prediction_quality,
        )
        signal_ai_prediction = build_signal_ai_prediction(
            boats,
            up_signal,
            down_signal,
            signal_ai_config,
        )

        row = {
            "target_date": (
                target_date
            ),
            "race_id": (
                race_id
            ),
            "venue_code": (
                text(
                    race.get(
                        "venue_code"
                    )
                )
            ),
            "venue_name": (
                text(
                    race.get(
                        "venue_name"
                    )
                )
            ),
            "race": (
                to_int(
                    race.get(
                        "race"
                    )
                )
            ),
            "deadline": (
                deadline_dt.isoformat()
                if deadline_dt
                else text(
                    deadline_raw
                )
            ),
            "prediction_type": (
                prediction_type
            ),
            # Source model is the one that actually created these saved
            # scores, not the version currently active at page-render time.
            "score_model_version": (
                race.get("score_model_version")
                or (live_payload if race_id in live else morning_payload).get("model_version")
            ),
            "score_logic_config": (
                race.get("logic_config")
                or (live_payload if race_id in live else morning_payload).get("logic_config")
            ),
            "prediction_quality": (
                prediction_quality
            ),
            "generated_at": (
                text(
                    race.get(
                        "generated_at"
                    )
                )
                or now.isoformat()
            ),
            "boats": (
                cleaned_boats
            ),
            "formation": (
                formation
            ),
            "morning_formation": (
                morning_formation
            ),
            "morning_boats": (
                morning_boats_snapshot
            ),
            "morning_ai_score_prediction": (
                morning_ai_score_prediction
            ),
            "ai_score_prediction": (
                ai_score_prediction
            ),
            "signal_ai_prediction": (
                signal_ai_prediction
            ),
            "up_signal": (
                up_signal
            ),
            "down_signal": (
                down_signal
            ),
            "signal_system_name": SIGNAL_SYSTEM_NAME,
        }

        all_rows.append(
            row
        )

        if (
            deadline_dt is None
            or deadline_dt > now
        ):
            upcoming_rows.append(
                (
                    deadline_dt,
                    row,
                )
            )

    live_dir = (
        base
        / "live"
    )

    live_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    formation_json = (
        live_dir
        / (
            "formation_predictions_final_"
            f"{target_date}.json"
        )
    )

    formation_csv = (
        live_dir
        / (
            "formation_predictions_final_"
            f"{target_date}.csv"
        )
    )

    # 復旧後に予測スコアを再生成しても、当時保存した買い目・シグナルAIの
    # 結果を後出しで書き換えない。結果判明後の実行は当時の購入記録ではない。
    original_formation = load_json(formation_json, required=False) if formation_json.is_file() else {}
    previous_by_id = {
        text(item.get("race_id")): item
        for item in (original_formation.get("races") or [])
        if isinstance(item, dict) and text(item.get("race_id"))
    }
    for row in all_rows:
        source = live.get(text(row.get("race_id"))) or {}
        source_quality = source.get("prediction_quality") or {}
        if (
            source_quality.get("status") == "recovered_observation"
            and source_quality.get("provenance") in ("post_result_official_beforeinfo", "saved_pre_deadline_official_beforeinfo")
        ):
            prior = previous_by_id.get(text(row.get("race_id")))
            if prior:
                # 通常予測と実際の買い目は当時保存した値を維持する。
                # 一方、風神雷神は復旧スコアから通常ルールを再判定する。
                # 旧fallbackから作られた「未発動」を保持してしまうと
                # 公式データで判定可能になったあとも未発動の誤表示が続く。
                for key in ("formation", "morning_formation", "ai_score_prediction",
                            "morning_ai_score_prediction"):
                    if key in prior:
                        row[key] = prior[key]
                assert (row.get("up_signal") or {}).get("available") is True, (
                    "復旧シグナルの通常再判定に失敗", row.get("race_id"), row.get("up_signal")
                )
                assert (row.get("down_signal") or {}).get("available") is True, (
                    "復旧シグナルの通常再判定に失敗", row.get("race_id"), row.get("down_signal")
                )
                row["retrospective_score_recovery"] = True
                row["retrospective_signal_recovery"] = True
                row["signal_recovery_provenance"] = "official_beforeinfo_post_result_replay"
                row["signal_detected_at_original_deadline"] = False
                row["historical_bet_preserved"] = True
                print("公式展示から通常シグナルを再判定・当時の買い目保存:",
                      row.get("race_id"),
                      "雷神", (row.get("up_signal") or {}).get("level"),
                      "風神", (row.get("down_signal") or {}).get("level"))

    formation_json.write_text(
        json.dumps(
            {
                "schema_version": (
                    "1.0"
                ),
                "model_version": (
                    FORMATION_MODEL
                ),
                "target_date": (
                    target_date
                ),
                "generated_at": (
                    now.isoformat()
                ),
                "race_count": (
                    len(
                        all_rows
                    )
                ),
                "simulation_rule": (
                    "3連単各組み合わせ100円固定"
                ),
                "races": (
                    all_rows
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    write_formation_csv(
        formation_csv,
        all_rows,
    )

    # The completed and upcoming screens share one pre-result read model.
    # Build it atomically immediately after the persisted formation output.
    from build_canonical_race_records import build as build_canonical_races
    build_canonical_races(target_date)

    upcoming_rows.sort(
        key=lambda item: (
            item[0]
            or datetime.max.replace(
                tzinfo=JST
            ),
            item[1][
                "venue_code"
            ],
            item[1][
                "race"
            ]
            or 99,
        )
    )

    latest_rows = [
        item[
            1
        ]
        for item
        in upcoming_rows
    ]

    latest_md = (
        Path(
            "predictions"
        )
        / "latest.md"
    )

    latest_json = (
        Path(
            "predictions"
        )
        / "latest.json"
    )

    lines = []

    lines.append(
        "# ボートレースAI 最新予想"
    )

    lines.append("")

    lines.append(
        f"**最終更新："
        f"{now.strftime('%Y/%m/%d %H:%M')} JST**"
    )

    lines.append("")

    lines.append(
        f"締切前："
        f"**{len(latest_rows)}レース**"
    )

    lines.append("")

    lines.append(
        "> スコアは勝率ではありません。"
        "現在のAIモデル内での比較用スコアです。"
    )

    lines.append("")

    lines.append(
        "> フォーメーションは"
        "100円/点で検証するシミュレーションです。"
    )

    lines.append("")

    for row in latest_rows:

        deadline_label = (
            "不明"
        )

        if row[
            "deadline"
        ]:
            try:
                deadline_label = (
                    datetime.fromisoformat(
                        row[
                            "deadline"
                        ]
                    )
                    .astimezone(
                        JST
                    )
                    .strftime(
                        "%H:%M"
                    )
                )

            except ValueError:
                deadline_label = (
                    row[
                        "deadline"
                    ]
                )

        venue = (
            row[
                "venue_name"
            ]
            or row[
                "venue_code"
            ]
            or "会場不明"
        )

        formation = (
            row[
                "formation"
            ]
        )

        boats = (
            row[
                "boats"
            ]
        )

        lines.append(
            f"## {venue} "
            f"{row['race']}R"
        )

        lines.append("")

        lines.append(
            f"締切 **{deadline_label}** ｜ "
            f"予測 **{row['prediction_type']}** ｜ "
            f"タイプ **{formation['formation_type']}**"
        )

        lines.append("")

        lines.append(
            f"**◎ {racer_label(boats[0])}**"
        )

        lines.append("")

        lines.append(
            f"○ {racer_label(boats[1])}"
        )

        lines.append("")

        lines.append(
            f"▲ {racer_label(boats[2])}"
        )

        lines.append("")

        lines.append(
            "**全6艇スコア（予測順位順）**"
        )

        lines.append("")

        lines.append(
            compact_scores(
                boats
            )
        )

        lines.append("")

        if formation[
            "points"
        ] > 0:

            lines.append(
                "**3連単フォーメーション候補**"
            )

            lines.append("")

            lines.append(
                "1着："
                + formation_candidate_text(
                    formation[
                        "first_candidates"
                    ]
                )
            )

            lines.append("")

            lines.append(
                "2着："
                + formation_candidate_text(
                    formation[
                        "second_candidates"
                    ]
                )
            )

            lines.append("")

            lines.append(
                "3着："
                + formation_candidate_text(
                    formation[
                        "third_candidates"
                    ]
                )
            )

            lines.append("")

            lines.append(
                f"**シミュレーション買い目 "
                f"{formation['points']}点 "
                f"＝ "
                f"{formation['investment_100yen']}円**"
            )

            lines.append("")

            lines.append(
                " / ".join(
                    formation[
                        "combinations"
                    ]
                )
            )

        else:

            lines.append(
                "**フォーメーション："
                "スコア不足のため今回は生成なし**"
            )

        lines.append("")

        lines.append(
            "---"
        )

        lines.append("")

    latest_md.write_text(
        "\n".join(
            lines
        ),
        encoding="utf-8",
    )

    latest_json.write_text(
        json.dumps(
            {
                "target_date": (
                    target_date
                ),
                "generated_at": (
                    now.isoformat()
                ),
                "formation_model": (
                    FORMATION_MODEL
                ),
                "upcoming_race_count": (
                    len(
                        latest_rows
                    )
                ),
                "races": (
                    latest_rows
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "========================================"
    )

    print(
        "最新予想＋フォーメーション生成"
    )

    print(
        "========================================"
    )

    print(
        "全予測レース:",
        len(
            all_rows
        ),
    )

    print(
        "締切前表示:",
        len(
            latest_rows
        ),
    )

    print(
        "全6艇スコア表示: PASS"
    )

    print(
        "フォーメーション生成: PASS"
    )

    print(
        "predictions/latest.md: PASS"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )