from __future__ import annotations

import argparse
import csv
import itertools
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


JST = timezone(timedelta(hours=9))

FORMATION_MODEL = "formation_gap_flow_v2"


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

    if not path.exists():
        return result

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

    value = (
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

    if value not in (
        None,
        "",
    ):
        return value

    return program_deadlines.get(
        race_id
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

    return (
        score_by_boat[
            first
        ] * 0.50
        + score_by_boat[
            second
        ] * 0.30
        + score_by_boat[
            third
        ] * 0.20
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
    if len(boats) != 6:
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
    gap34 = scores[2] - scores[3]

    # 流しルール:
    # 1) 1・2位が接近し、3位以下と明確な差 -> 1・2着折返し＋3着流し
    # 2) 1位が強く、2位も3位以下と明確な差 -> 1着・2着固定＋3着流し
    # 3) 1位だけ強い -> 1着固定＋2・3着相手流し
    if gap12 < 5.0 and gap23 >= 10.0:
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

    elif gap12 >= 10.0 and gap23 >= 10.0:
        formation_type = "1・2着固定＋3着流し"
        top1, top2 = order[0], order[1]
        tail = order[2:]
        combinations = [(top1, top2, c) for c in tail]
        first_candidates = [top1]
        second_candidates = [top2]
        third_candidates = tail

    elif gap12 >= 10.0:
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
        combinations = combinations[:12]
        first_candidates = [top1]
        second_candidates = tail
        third_candidates = tail

    elif gap12 >= 5.0:
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
        combinations = combinations[:8]

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
        combinations = combinations[:12]

    return {
        "model_version": FORMATION_MODEL,
        "formation_type": formation_type,
        "gap_1_2": round(gap12, 2),
        "gap_2_3": round(gap23, 2),
        "gap_3_4": round(gap34, 2),
        "first_candidates": first_candidates,
        "second_candidates": second_candidates,
        "third_candidates": third_candidates,
        "combinations": [
            f"{a}-{b}-{c}" for a, b, c in combinations
        ],
        "points": len(combinations),
        "investment_100yen": len(combinations) * 100,
    }



AI_SCORE_MODEL = "ai_finish_order_score_v0_20261005"

def _component01(row, key, default=0.5):
    comps = row.get("components") or {}
    comp = comps.get(key) or {}
    value = to_float(comp.get("raw_score_0_1"))
    return default if value is None else max(0.0, min(1.0, value))

def build_ai_score_prediction(boats):
    """Experimental independent finish-position scorer; keeps existing formation untouched."""
    if len(boats) != 6:
        return None

    scored = []
    for row in boats:
        boat = boat_number(row)
        overall = max(0.0, min(1.0, score_for_calculation(row) / 100.0))

        # Morning components when present. Live rows expose structural/exTime/exST,
        # so overall already carries the production 80/6/14 live adjustment.
        course = _component01(row, "racer_course", overall)
        grade = _component01(row, "grade", overall)
        motor = _component01(row, "motor", overall)
        machine = _component01(row, "boat", overall)
        national = _component01(row, "national_top2", overall)
        structural = _component01(row, "structural", overall)
        ex_time = _component01(row, "exTime", overall)
        ex_st = _component01(row, "exST", overall)

        if "structural" in (row.get("components") or {}):
            # Live: 1着はST/展示を強め、2着は構造との均衡、3着は裾を広める。
            first = .48*structural + .10*ex_time + .22*ex_st + .20*overall
            second = .58*structural + .08*ex_time + .14*ex_st + .20*overall
            third = .66*structural + .07*ex_time + .07*ex_st + .20*overall
        else:
            # Morning: 1着はコース勝ち切り力、2着は級別/安定性、
            # 3着はモーター・ボート・全国成績をやや厚くする初期仮説。
            first = .35*course + .18*grade + .14*motor + .05*machine + .10*national + .18*overall
            second = .25*course + .20*grade + .17*motor + .06*machine + .14*national + .18*overall
            third = .18*course + .16*grade + .22*motor + .10*machine + .16*national + .18*overall

        scored.append({
            "boat": boat,
            "first_score": round(first*100, 2),
            "second_score": round(second*100, 2),
            "third_score": round(third*100, 2),
        })

    by_boat = {x["boat"]: x for x in scored}
    combos = []
    for first, second, third in itertools.permutations(sorted(by_boat), 3):
        a, b, d = by_boat[first], by_boat[second], by_boat[third]
        # Geometric-style joint score penalizes a weak leg more than a simple sum.
        joint = ((max(a["first_score"], .01)/100.0) *
                 (max(b["second_score"], .01)/100.0) *
                 (max(d["third_score"], .01)/100.0)) ** (1.0/3.0)
        combos.append({
            "combination": f"{first}-{second}-{third}",
            "score": round(joint*100, 3),
        })
    combos.sort(key=lambda x: (-x["score"], x["combination"]))

    # AIスコア予測は検証条件を固定するため、常に上位8点を採用する。
    # 1点100円・1レース800円で収支を継続比較する。
    points = 8

    selected = combos[:points]
    return {
        "model_version": AI_SCORE_MODEL,
        "status": "experimental",
        "points": points,
        "investment_100yen": points * 100,
        "position_scores": sorted(scored, key=lambda x: x["boat"]),
        "first_candidates": [x["boat"] for x in sorted(scored, key=lambda x: (-x["first_score"], x["boat"]))[:3]],
        "second_candidates": [x["boat"] for x in sorted(scored, key=lambda x: (-x["second_score"], x["boat"]))[:4]],
        "third_candidates": [x["boat"] for x in sorted(scored, key=lambda x: (-x["third_score"], x["boat"]))[:5]],
        "boundary_gaps": {},
        "combinations": selected,
        "all_120_combinations": combos,
        "note": "検証版。現行フォーメーション/BOXには影響せず、着順別スコアから120通りを独立採点し上位8点を採用。",
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
                boat = boats[
                    index
                ]

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

        if len(
            boats
        ) != 6:
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
                }
            )

        # 朝予測の買い目も別途固定保存する。
        # 直前予測へ切り替わった後も、朝時点のフォーメーションを失わない。
        morning_formation = None
        if race_id in morning:
            morning_boats = ranked_boats(morning[race_id])
            if len(morning_boats) == 6:
                morning_formation = build_formation(morning_boats)

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
            "ai_score_prediction": (
                build_ai_score_prediction(boats)
            ),
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