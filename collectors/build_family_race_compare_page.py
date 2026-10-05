#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BOAT RACE AI
家族共有サイト用・終了済みレース照合ページ生成

出力:
    _family_site/race_compare.html

表示:
    ・朝予測 TOP3
    ・最終直前予測 TOP3
    ・実際の1～3着
    ・TOP3整合率
    ・TOP3完全一致
    ・1着一致
    ・3連単結果
    ・3連単払戻
    ・締切前3連単オッズ

既存の朝予測・直前予測ロジックは変更しない。
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


JST = timezone(timedelta(hours=9))

PUBLIC_DATA_BASE = (
    "https://raw.githubusercontent.com/"
    "BoatraceCSV/boatracecsv.github.io/main/data"
)

VENUE_CODES = {
    "桐生": "01",
    "戸田": "02",
    "江戸川": "03",
    "平和島": "04",
    "多摩川": "05",
    "浜名湖": "06",
    "蒲郡": "07",
    "常滑": "08",
    "津": "09",
    "三国": "10",
    "びわこ": "11",
    "住之江": "12",
    "尼崎": "13",
    "鳴門": "14",
    "丸亀": "15",
    "児島": "16",
    "宮島": "17",
    "徳山": "18",
    "下関": "19",
    "若松": "20",
    "芦屋": "21",
    "福岡": "22",
    "唐津": "23",
    "からつ": "23",
    "大村": "24",
}

CODE_TO_VENUE = {
    code: name
    for name, code in VENUE_CODES.items()
    if name != "からつ"
}


# =========================================================
# 引数
# =========================================================

def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        required=True,
        help="YYYYMMDD",
    )

    parser.add_argument(
        "--predictions-root",
        default="predictions",
    )

    parser.add_argument(
        "--output-dir",
        default="_family_site",
    )

    return parser.parse_args()


# =========================================================
# 共通
# =========================================================

def fetch_text(url: str) -> str:

    req = Request(
        url,
        headers={
            "User-Agent":
                "boatrace-ai-family-view/1.0"
        },
    )

    try:

        with urlopen(
            req,
            timeout=30,
        ) as response:

            return response.read().decode(
                "utf-8-sig"
            )

    except (
        HTTPError,
        URLError,
        TimeoutError,
    ) as exc:

        print(
            f"WARN: 取得失敗: {url}"
        )

        print(
            f"WARN: {exc}"
        )

        return ""


def read_csv_text(text: str):

    if not text.strip():
        return []

    return list(
        csv.DictReader(
            io.StringIO(text)
        )
    )


def esc(value) -> str:

    if value is None:
        return ""

    return html.escape(
        str(value)
    )


def normalize_boat(value):

    try:
        return int(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def safe_float(value):

    try:

        if value is None:
            return None

        text = str(value).strip()

        if not text:
            return None

        return float(text)

    except (
        TypeError,
        ValueError,
    ):
        return None


def safe_int(value):

    try:

        if value is None:
            return None

        text = (
            str(value)
            .replace(",", "")
            .strip()
        )

        if not text:
            return None

        return int(
            float(text)
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def read_json(path: Path):

    try:

        if not path.is_file():
            return None

        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception as exc:

        print(
            f"WARN: JSON読込失敗: "
            f"{path}: {exc}"
        )

        return None


# =========================================================
# JSON構造からレース一覧を探す
# =========================================================

def find_race_list(data):

    if isinstance(
        data,
        list,
    ):

        return data

    if not isinstance(
        data,
        dict,
    ):

        return []

    candidate_keys = (
        "predictions",
        "races",
        "race_predictions",
        "items",
        "data",
    )

    for key in candidate_keys:

        value = data.get(key)

        if isinstance(
            value,
            list,
        ):

            return value

    for value in data.values():

        if (
            isinstance(
                value,
                list,
            )
            and value
            and isinstance(
                value[0],
                dict,
            )
        ):

            return value

    return []


# =========================================================
# レースコード
# =========================================================

def extract_race_code(
    row,
    target_date,
):

    for key in (
        "race_code",
        "レースコード",
        "race_id",
    ):

        value = row.get(key)

        if value:

            text = str(
                value
            ).strip()

            digits = "".join(
                x
                for x in text
                if x.isdigit()
            )

            if len(digits) >= 12:

                return digits[:12]

    venue_code = None

    for key in (
        "venue_code",
        "stadium_code",
        "place_code",
    ):

        value = row.get(key)

        if value is not None:

            text = str(
                value
            ).strip()

            if text.isdigit():

                venue_code = (
                    text.zfill(2)
                )

                break

    if not venue_code:

        venue_name = (
            row.get("venue")
            or row.get("venue_name")
            or row.get("stadium")
            or row.get("place")
            or ""
        )

        venue_code = (
            VENUE_CODES.get(
                str(
                    venue_name
                ).strip()
            )
        )

    race_no = None

    for key in (
        "race_no",
        "race_number",
        "race",
        "r",
    ):

        value = row.get(key)

        if value is None:
            continue

        try:

            race_no = int(
                value
            )

            break

        except (
            TypeError,
            ValueError,
        ):

            continue

    if (
        venue_code
        and race_no
    ):

        return (
            f"{target_date}"
            f"{venue_code}"
            f"{race_no:02d}"
        )

    return None


# =========================================================
# TOP3をJSONから取得
# =========================================================

def normalize_pick(
    item,
    fallback_rank=None,
):

    if isinstance(
        item,
        (int, float),
    ):

        boat = normalize_boat(
            item
        )

        if boat:

            return {
                "boat": boat,
                "name": "",
                "score": None,
            }

        return None

    if isinstance(
        item,
        str,
    ):

        boat = normalize_boat(
            item
        )

        if boat:

            return {
                "boat": boat,
                "name": "",
                "score": None,
            }

        return None

    if not isinstance(
        item,
        dict,
    ):

        return None

    boat = None

    for key in (
        "boat",
        "boat_no",
        "boat_number",
        "lane",
        "frame",
        "枠番",
        "艇番",
    ):

        if key in item:

            boat = normalize_boat(
                item.get(key)
            )

            if boat:
                break

    if not boat:

        return None

    name = ""

    for key in (
        "name",
        "racer_name",
        "player_name",
        "選手名",
    ):

        value = item.get(key)

        if value:

            name = str(
                value
            ).replace(
                "　",
                " ",
            ).strip()

            break

    score = None

    for key in (
        "score",
        "final_score",
        "total_score",
        "prediction_score",
    ):

        if key in item:

            score = safe_float(
                item.get(key)
            )

            if score is not None:
                break

    return {
        "boat": boat,
        "name": name,
        "score": score,
    }


def extract_top3(row):

    # 直接 top3 がある場合
    for key in (
        "top3",
        "top_3",
        "top3_boats",
    ):

        value = row.get(key)

        if isinstance(
            value,
            list,
        ):

            picks = []

            for index, item in enumerate(
                value
            ):

                pick = normalize_pick(
                    item,
                    index + 1,
                )

                if pick:
                    picks.append(
                        pick
                    )

            if len(picks) >= 3:

                return picks[:3]

    # order 系
    for key in (
        "morning_order",
        "live_order",
        "prediction_order",
        "order",
        "ranking",
    ):

        value = row.get(key)

        if isinstance(
            value,
            list,
        ):

            picks = []

            for index, item in enumerate(
                value
            ):

                pick = normalize_pick(
                    item,
                    index + 1,
                )

                if pick:
                    picks.append(
                        pick
                    )

            if len(picks) >= 3:

                return picks[:3]

    # boats / entries の中に順位がある場合
    for key in (
        "boats",
        "entries",
        "scores",
    ):

        value = row.get(key)

        if not isinstance(
            value,
            list,
        ):

            continue

        normalized = []

        for item in value:

            if not isinstance(
                item,
                dict,
            ):

                continue

            pick = normalize_pick(
                item
            )

            if not pick:
                continue

            rank = None

            for rank_key in (
                "rank",
                "prediction_rank",
                "score_rank",
            ):

                if rank_key in item:

                    try:

                        rank = int(
                            item.get(
                                rank_key
                            )
                        )

                    except Exception:
                        rank = None

                    break

            if rank is None:

                score = pick.get(
                    "score"
                )

                normalized.append(
                    (
                        None,
                        score,
                        pick,
                    )
                )

            else:

                normalized.append(
                    (
                        rank,
                        pick.get(
                            "score"
                        ),
                        pick,
                    )
                )

        if normalized:

            if all(
                x[0] is not None
                for x in normalized
            ):

                normalized.sort(
                    key=lambda x:
                        x[0]
                )

            else:

                normalized.sort(
                    key=lambda x:
                        (
                            x[1]
                            is None,
                            -(
                                x[1]
                                or 0
                            ),
                        )
                )

            picks = [
                x[2]
                for x in normalized
            ]

            if len(picks) >= 3:

                return picks[:3]

    return []


# =========================================================
# 予測ファイル読込
# =========================================================

def load_prediction_file(
    path,
    target_date,
):

    data = read_json(
        path
    )

    if data is None:
        return {}

    race_list = find_race_list(
        data
    )

    output = {}

    for row in race_list:

        if not isinstance(
            row,
            dict,
        ):
            continue

        race_code = extract_race_code(
            row,
            target_date,
        )

        if not race_code:
            continue

        top3 = extract_top3(
            row
        )

        if len(top3) < 3:
            continue

        output[
            race_code
        ] = {
            "race_code": race_code,
            "top3": top3,
            "boats": row.get("boats") or [],
            "raw": row,
            "ai_score_prediction": row.get("ai_score_prediction") or {},
        }

    return output


def locate_morning_file(
    root,
    target_date,
):

    yyyy = target_date[:4]
    mm = target_date[4:6]
    dd = target_date[6:8]

    candidates = [
        root
        / yyyy
        / mm
        / dd
        / "morning"
        / (
            "morning_predictions_"
            f"{target_date}.json"
        ),

        root
        / yyyy
        / mm
        / dd
        / "morning"
        / (
            "morning_predictions_final_"
            f"{target_date}.json"
        ),

        root
        / yyyy
        / mm
        / dd
        / "morning"
        / (
            "predictions_"
            f"{target_date}.json"
        ),
    ]

    for path in candidates:

        if path.is_file():
            return path

    # ファイル名が違う場合の探索
    search_root = (
        root
        / yyyy
        / mm
        / dd
    )

    if search_root.exists():

        files = sorted(
            search_root.rglob(
                "*.json"
            )
        )

        for path in files:

            name = (
                path.name.lower()
            )

            if (
                "morning"
                in name
                and "validation"
                not in name
            ):

                return path

    return None


def locate_live_file(
    root,
    target_date,
):

    yyyy = target_date[:4]
    mm = target_date[4:6]
    dd = target_date[6:8]

    candidates = [
        # レース照合では、買い目を含む最終フォーメーションを最優先する。
        root
        / yyyy
        / mm
        / dd
        / "live"
        / (
            "formation_predictions_final_"
            f"{target_date}.json"
        ),

        root
        / yyyy
        / mm
        / dd
        / "live"
        / (
            "live_predictions_final_"
            f"{target_date}.json"
        ),

        root
        / yyyy
        / mm
        / dd
        / "live"
        / (
            "live_predictions_"
            f"{target_date}.json"
        ),
    ]

    for path in candidates:

        if path.is_file():
            return path

    search_root = (
        root
        / yyyy
        / mm
        / dd
        / "live"
    )

    if search_root.exists():

        files = sorted(
            search_root.rglob(
                "*.json"
            )
        )

        preferred = []

        for path in files:

            name = (
                path.name.lower()
            )

            if (
                "validation"
                in name
            ):
                continue

            if (
                "final"
                in name
            ):
                preferred.append(
                    path
                )

        if preferred:

            return preferred[-1]

    return None


def load_predictions(
    predictions_root,
    target_date,
):

    root = Path(
        predictions_root
    )

    morning_file = locate_morning_file(
        root,
        target_date,
    )

    live_file = locate_live_file(
        root,
        target_date,
    )

    print(
        "朝予測ファイル:",
        morning_file
        if morning_file
        else "NOT FOUND",
    )

    print(
        "直前予測ファイル:",
        live_file
        if live_file
        else "NOT FOUND",
    )

    morning = {}

    live = {}

    if morning_file:

        morning = load_prediction_file(
            morning_file,
            target_date,
        )

    if live_file:

        live = load_prediction_file(
            live_file,
            target_date,
        )

    print(
        "朝予測読込:",
        len(morning),
        "R",
    )

    print(
        "直前予測読込:",
        len(live),
        "R",
    )

    return (
        morning,
        live,
    )


# =========================================================
# 公開結果CSV
# =========================================================

def latest_by_race(
    rows,
):

    output = {}

    for row in rows:

        race_code = str(
            row.get(
                "レースコード",
                "",
            )
        ).strip()

        if not race_code:
            continue

        previous = output.get(
            race_code
        )

        current_time = str(
            row.get(
                "取得日時",
                "",
            )
        )

        previous_time = (
            str(
                previous.get(
                    "取得日時",
                    "",
                )
            )
            if previous
            else ""
        )

        if (
            previous is None
            or current_time
            >= previous_time
        ):

            output[
                race_code
            ] = row

    return output


# =========================================================
# 評価
# =========================================================

def evaluate_top3(
    prediction,
    actual,
):

    if not prediction:
        return None

    picks = prediction.get(
        "top3",
        [],
    )

    if len(picks) < 3:
        return None

    predicted = [
        int(
            x["boat"]
        )
        for x in picks[:3]
    ]

    top3_match = (
        set(predicted)
        == set(actual)
    )

    exact_order = (
        predicted
        == list(actual)
    )

    return {
        "predicted":
            predicted,

        # TOP3整合: 予測上位3艇と実着上位3艇が
        # 順不同で3艇すべて一致したレースだけ1（100%）。
        # 1艇でも違えば0（0%）。
        "overlap_count":
            3 if top3_match else 0,

        "overlap_rate":
            100.0 if top3_match else 0.0,

        # 完全一致: 1着・2着・3着の順番まで一致。
        "exact":
            exact_order,

        "winner":
            predicted[0]
            == actual[0],
    }


# =========================================================
# オッズ時刻
# =========================================================

def odds_minutes_before(
    target_date,
    deadline,
    obtained_at,
):

    if (
        not deadline
        or not obtained_at
    ):
        return None

    try:

        deadline_text = (
            str(
                deadline
            )
            .strip()
            .replace(
                "締切",
                "",
            )
            .strip()
        )

        deadline_dt = datetime.strptime(
            target_date
            + deadline_text,
            "%Y%m%d%H:%M",
        ).replace(
            tzinfo=JST
        )

        obtained_text = str(
            obtained_at
        ).strip()

        obtained_dt = datetime.fromisoformat(
            obtained_text.replace(
                "Z",
                "+00:00",
            )
        )

        if (
            obtained_dt.tzinfo
            is None
        ):

            obtained_dt = (
                obtained_dt.replace(
                    tzinfo=JST
                )
            )

        obtained_dt = (
            obtained_dt.astimezone(
                JST
            )
        )

        minutes = (
            deadline_dt
            - obtained_dt
        ).total_seconds() / 60

        return round(
            minutes,
            1,
        )

    except Exception:
        return None


# =========================================================
# レースデータ統合
# =========================================================

def build_race_rows(
    target_date,
    morning_predictions,
    live_predictions,
):

    yyyy = target_date[:4]
    mm = target_date[4:6]
    dd = target_date[6:8]

    date_path = (
        f"{yyyy}/{mm}/{dd}"
    )

    result_url = (
        f"{PUBLIC_DATA_BASE}"
        "/results/realtime/"
        f"{date_path}.csv"
    )

    payout_url = (
        f"{PUBLIC_DATA_BASE}"
        "/results/payouts/"
        f"{date_path}.csv"
    )

    odds_url = (
        f"{PUBLIC_DATA_BASE}"
        "/previews/od3/"
        f"{date_path}.csv"
    )

    print(
        "結果CSV:",
        result_url,
    )

    print(
        "払戻CSV:",
        payout_url,
    )

    print(
        "オッズCSV:",
        odds_url,
    )

    results = latest_by_race(
        read_csv_text(
            fetch_text(
                result_url
            )
        )
    )

    payouts = latest_by_race(
        read_csv_text(
            fetch_text(
                payout_url
            )
        )
    )

    odds = latest_by_race(
        read_csv_text(
            fetch_text(
                odds_url
            )
        )
    )

    print(
        "結果取得:",
        len(results),
        "R",
    )

    print(
        "払戻取得:",
        len(payouts),
        "R",
    )

    print(
        "オッズ取得:",
        len(odds),
        "R",
    )

    race_rows = []

    for (
        race_code,
        result,
    ) in results.items():

        if not race_code.startswith(
            target_date
        ):
            continue

        actual = []

        actual_names = []

        valid = True

        for rank in range(
            1,
            4,
        ):

            boat = normalize_boat(
                result.get(
                    f"{rank}着_艇番"
                )
            )

            if boat is None:

                valid = False
                break

            actual.append(
                boat
            )

            name = str(
                result.get(
                    f"{rank}着_選手名",
                    "",
                )
            ).replace(
                "　",
                " ",
            ).strip()

            actual_names.append(
                name
            )

        if not valid:
            continue

        morning = (
            morning_predictions.get(
                race_code
            )
        )

        live = (
            live_predictions.get(
                race_code
            )
        )

        payout_row = (
            payouts.get(
                race_code,
                {},
            )
        )

        odds_row = (
            odds.get(
                race_code,
                {},
            )
        )

        trifecta = "-".join(
            str(x)
            for x in actual
        )

        payout_value = safe_int(
            payout_row.get(
                "3連単_払戻金"
            )
        )

        odds_value = safe_float(
            odds_row.get(
                f"3連単_{trifecta}"
            )
        )

        venue_code = (
            race_code[8:10]
        )

        venue = (
            CODE_TO_VENUE.get(
                venue_code,
                venue_code,
            )
        )

        try:

            race_no = int(
                race_code[-2:]
            )

        except ValueError:

            race_no = 0

        deadline = str(
            result.get(
                "締切時刻",
                "",
            )
        ).strip()

        odds_time = str(
            odds_row.get(
                "取得日時",
                "",
            )
        ).strip()

        race_rows.append(
            {
                "race_code":
                    race_code,

                "venue":
                    venue,

                "race":
                    race_no,

                "deadline":
                    deadline,

                "result_time":
                    str(
                        result.get(
                            "結果記録時刻",
                            "",
                        )
                    ).strip(),

                "technique":
                    str(
                        result.get(
                            "決まり手",
                            "",
                        )
                    ).strip(),

                "actual":
                    actual,

                "actual_names":
                    actual_names,

                "morning":
                    morning,

                "live":
                    live,

                "morning_eval":
                    evaluate_top3(
                        morning,
                        actual,
                    ),

                "live_eval":
                    evaluate_top3(
                        live,
                        actual,
                    ),

                "morning_formation_hit": formation_hit(live, trifecta, "morning_formation"),
                "live_formation_hit": formation_hit(live, trifecta, "formation"),

                "trifecta":
                    trifecta,

                "payout":
                    payout_value,

                "odds":
                    odds_value,

                "odds_time":
                    odds_time,

                "odds_minutes":
                    odds_minutes_before(
                        target_date,
                        deadline,
                        odds_time,
                    ),
            }
        )

    # 締切が遅いレースを上に
    race_rows.sort(
        key=lambda row: (
            row["deadline"],
            row["race_code"],
        ),
        reverse=True,
    )

    return race_rows


# =========================================================
# 集計
# =========================================================

def aggregate(
    race_rows,
    key,
):

    values = [
        row[key]
        for row in race_rows
        if row.get(key)
    ]

    if not values:

        return {
            "count": 0,
            "overlap": None,
            "exact": None,
            "winner": None,
        }

    count = len(
        values
    )

    overlap = (
        sum(
            item[
                "overlap_rate"
            ]
            for item in values
        )
        / count
    )

    exact = (
        sum(
            100
            if item["exact"]
            else 0
            for item in values
        )
        / count
    )

    winner = (
        sum(
            100
            if item["winner"]
            else 0
            for item in values
        )
        / count
    )

    return {
        "count": count,
        "overlap": overlap,
        "exact": exact,
        "winner": winner,
    }


def percent(
    value,
):

    if value is None:
        return "—"

    return (
        f"{value:.1f}%"
    )


# =========================================================
# HTML部品
# =========================================================

def prediction_html(
    prediction,
):

    if not prediction:

        return (
            '<span class="missing">'
            "予測なし"
            "</span>"
        )

    picks = prediction.get(
        "top3",
        [],
    )

    if len(picks) < 3:

        return (
            '<span class="missing">'
            "予測なし"
            "</span>"
        )

    output = []

    for pick in picks[:3]:

        boat = pick.get(
            "boat"
        )

        name = esc(
            pick.get(
                "name",
                "",
            )
        )

        score = pick.get(
            "score"
        )

        score_html = ""

        if score is not None:

            score_html = (
                f'<small>'
                f'{score:.1f}'
                f'</small>'
            )

        output.append(
            f'<span class="boat">'
            f'<b>{boat}</b>号艇 '
            f'{name}'
            f'{score_html}'
            f'</span>'
        )

    return (
        '<span class="arrow">'
        " → "
        "</span>"
    ).join(
        output
    )


def all_scores_html(prediction, label):
    if not prediction:
        return ""
    boats = prediction.get("boats") or (prediction.get("raw") or {}).get("boats") or []
    scored = []
    for boat in boats:
        b = normalize_boat(boat.get("boat"))
        score = safe_float(boat.get("score"))
        if b is not None and score is not None:
            scored.append((b, score))
    if not scored:
        return ""
    scored.sort(key=lambda x: (-x[1], x[0]))
    chips = " ".join(
        f'<span class="score-chip">{b}号艇 {score:.1f}</span>'
        for b, score in scored
    )
    return f'<details class="all-scores"><summary>{esc(label)}・6艇すべてのスコア</summary><div class="score-chips">{chips}</div></details>'


def formation_hit(prediction, trifecta, formation_key="formation"):
    if not prediction:
        return None
    formation = (prediction.get("raw") or {}).get(formation_key) or {}
    combos = [str(x) for x in (formation.get("combinations") or [])]
    if not combos:
        return None
    return trifecta in combos


def evaluation_html(
    evaluation,
):

    if not evaluation:

        return (
            '<span class="missing">'
            "未評価"
            "</span>"
        )

    exact = (
        "○"
        if evaluation[
            "exact"
        ]
        else "×"
    )

    winner = (
        "○"
        if evaluation[
            "winner"
        ]
        else "×"
    )

    return (
        f'<span class="tag">'
        f'TOP3整合 '
        f'{"○" if evaluation["overlap_rate"] == 100.0 else "×"}'
        f'</span>'

        f'<span class="tag">'
        f'完全一致 {exact}'
        f'</span>'

        f'<span class="tag">'
        f'1着一致 {winner}'
        f'</span>'
    )



def ai_score_result_html(prediction, trifecta, payout):
    if not prediction:
        return '<div class="simulation missing">AIスコア予測なし</div>'
    ai = prediction.get("ai_score_prediction") or (prediction.get("raw") or {}).get("ai_score_prediction") or {}
    all120 = ai.get("all_120_combinations") or []
    top12 = all120[:12]
    if not top12:
        top12 = ai.get("combinations") or []
    if not top12:
        return '<div class="simulation missing">AIスコア予測なし</div>'

    rows = []
    for i, item in enumerate(top12, 1):
        combo = str(item.get("combination") or "")
        score = safe_float(item.get("score"))
        bought = i <= 8
        classes = ["ai-result-pick"]
        if bought:
            classes.append("ai-bought")
        if combo == trifecta:
            classes.append("hit-pick")
        badge = "購入" if bought else "参考"
        score_text = f"{score:.3f}" if score is not None else "—"
        rows.append(
            f'<div class="{" ".join(classes)}">'
            f'<b>{i}位 {esc(combo)}</b>'
            f'<span>AI {score_text} ／ {badge}</span>'
            '</div>'
        )

    bought_combos = [str(x.get("combination") or "") for x in top12[:8]]
    hit = trifecta in bought_combos
    investment = len(bought_combos) * 100
    returned = payout if hit and payout is not None else 0
    profit = returned - investment
    status = '<span class="hit-status">的中</span>' if hit else '<span class="miss-status">不的中</span>'

    return f"""
    <details class="simulation-box ai-result-box">
      <summary class="ai-result-summary">
        <span class="simulation-title">AIスコア予測を見る</span>
        <span class="ai-result-summary-meta">上位12点 ／ {status}</span>
      </summary>
      <div class="ai-result-body">
        <div class="simulation-meta">表示12点 ／ 収支検証は上位8点・各100円 ／ 投資 {investment:,}円</div>
        <div class="ai-result-list">{''.join(rows)}</div>
        <div class="simulation-money">払戻 <b>{returned:,}円</b> ／ 収支 <b>{profit:+,}円</b></div>
      </div>
    </details>
    """


def simulation_html(prediction, trifecta, payout):
    """最終予測のフォーメーションと上位3艇BOXを100円/点で照合表示。"""
    if not prediction:
        return '<div class="simulation missing">予測データなし</div>'

    raw = prediction.get("raw") or {}
    formation = raw.get("formation") or {}
    combos = [str(x) for x in (formation.get("combinations") or [])]
    points = safe_int(formation.get("points")) or len(combos)
    investment = safe_int(formation.get("investment_100yen"))
    if investment is None:
        investment = points * 100

    hit = trifecta in combos
    payout_amount = payout if hit and payout is not None else 0
    profit = payout_amount - investment

    combo_html = []
    for combo in combos:
        cls = "combo-pick hit-pick" if combo == trifecta else "combo-pick"
        combo_html.append(f'<span class="{cls}">{esc(combo)}</span>')

    if combos:
        formation_detail = " / ".join(combo_html)
    else:
        formation_detail = '<span class="missing">買い目なし</span>'

    f_type = esc(formation.get("formation_type") or "不明")
    f_status = '<span class="hit-status">的中</span>' if hit else '<span class="miss-status">不的中</span>'

    picks = prediction.get("top3") or []
    box_boats = [int(x["boat"]) for x in picks[:3] if x.get("boat") is not None]
    box_combos = []
    if len(box_boats) == 3:
        a,b,c = box_boats
        box_combos = [
            f"{a}-{b}-{c}", f"{a}-{c}-{b}",
            f"{b}-{a}-{c}", f"{b}-{c}-{a}",
            f"{c}-{a}-{b}", f"{c}-{b}-{a}",
        ]
    box_hit = trifecta in box_combos
    box_investment = len(box_combos) * 100
    box_payout = payout if box_hit and payout is not None else 0
    box_profit = box_payout - box_investment

    box_combo_html = []
    for combo in box_combos:
        cls = "combo-pick hit-pick" if combo == trifecta else "combo-pick"
        box_combo_html.append(f'<span class="{cls}">{esc(combo)}</span>')
    box_detail = " / ".join(box_combo_html) if box_combo_html else '<span class="missing">BOXなし</span>'
    box_status = '<span class="hit-status">的中</span>' if box_hit else '<span class="miss-status">不的中</span>'

    return f"""
    <div class="simulation-grid">
      <div class="simulation-box">
        <div class="simulation-title">3連単フォーメーション</div>
        <div class="simulation-meta">{f_type} ／ {points}点 ／ 投資 {investment:,}円 ／ {f_status}</div>
        <div class="simulation-combos">{formation_detail}</div>
        <div class="simulation-money">払戻 <b>{payout_amount:,}円</b> ／ 収支 <b>{profit:+,}円</b></div>
      </div>
      <div class="simulation-box">
        <div class="simulation-title">AI上位3艇・3連単BOX</div>
        <div class="simulation-meta">{'-'.join(map(str,box_boats)) if box_boats else '—'} ／ {len(box_combos)}点 ／ 投資 {box_investment:,}円 ／ {box_status}</div>
        <div class="simulation-combos">{box_detail}</div>
        <div class="simulation-money">払戻 <b>{box_payout:,}円</b> ／ 収支 <b>{box_profit:+,}円</b></div>
      </div>
    </div>
    """


# =========================================================
# HTML生成
# =========================================================

def box_hit(prediction, trifecta):
    if not prediction:
        return None
    picks = [int(x["boat"]) for x in prediction.get("top3", [])[:3] if x.get("boat") is not None]
    if len(picks) != 3:
        return None
    a, b, c = picks
    combos = [
        f"{a}-{b}-{c}", f"{a}-{c}-{b}",
        f"{b}-{a}-{c}", f"{b}-{c}-{a}",
        f"{c}-{a}-{b}", f"{c}-{b}-{a}",
    ]
    return trifecta in combos


def ai_score_eval(prediction, actual):
    """AI着順別スコアのTOP3整合・完全一致と、上位8点買い目的中を評価。"""
    if not prediction or not actual or len(actual) < 3:
        return None
    ai = prediction.get("ai_score_prediction") or (prediction.get("raw") or {}).get("ai_score_prediction") or {}
    scores = ai.get("position_scores") or []
    if not scores:
        return None

    def best_boat(key, excluded=None):
        excluded = set(excluded or [])
        candidates = []
        for item in scores:
            boat = normalize_boat(item.get("boat"))
            score = safe_float(item.get(key))
            if boat is not None and score is not None and boat not in excluded:
                candidates.append((score, boat))
        if not candidates:
            return None
        candidates.sort(key=lambda x: (-x[0], x[1]))
        return candidates[0][1]

    first = best_boat("first_score")
    second = best_boat("second_score", [first])
    third = best_boat("third_score", [first, second])
    predicted = [first, second, third]
    if any(x is None for x in predicted):
        return None

    actual3 = [normalize_boat(x) for x in actual[:3]]
    top3_overlap = set(predicted) == set(actual3)
    exact = predicted == actual3

    all120 = ai.get("all_120_combinations") or ai.get("combinations") or []
    top8 = [str(x.get("combination") or "") for x in all120[:8]]
    trifecta = "-".join(str(x) for x in actual3)
    bought_hit = trifecta in top8
    return {"overlap": top3_overlap, "exact": exact, "bought_hit": bought_hit}


def ai_score_summary(rows):
    evals = []
    for row in rows:
        prediction = row.get("live") or row.get("morning")
        result = ai_score_eval(prediction, row.get("actual") or [])
        if result is not None:
            evals.append(result)
    count = len(evals)
    if not count:
        return {"count": 0, "overlap": None, "exact": None, "bought_hit": None}
    return {
        "count": count,
        "overlap": sum(1 for x in evals if x["overlap"]) / count * 100.0,
        "exact": sum(1 for x in evals if x["exact"]) / count * 100.0,
        "bought_hit": sum(1 for x in evals if x["bought_hit"]) / count * 100.0,
    }


def hit_summary_from_rows(rows, key):
    values = [row.get(key) for row in rows if row.get(key) is not None]
    if not values:
        return {"count": 0, "hits": 0, "rate": None}
    hits = sum(1 for value in values if value)
    return {"count": len(values), "hits": hits, "rate": hits / len(values) * 100.0}


def render_html(
    target_date,
    race_rows,
):

    morning_summary = aggregate(
        race_rows,
        "morning_eval",
    )

    live_summary = aggregate(
        race_rows,
        "live_eval",
    )

    def hit_summary(key):
        values = [row.get(key) for row in race_rows if row.get(key) is not None]
        if not values:
            return {"count": 0, "hits": 0, "rate": None}
        hits = sum(1 for value in values if value)
        return {"count": len(values), "hits": hits, "rate": hits / len(values) * 100.0}

    morning_hit_summary = hit_summary("morning_formation_hit")
    live_hit_summary = hit_summary("live_formation_hit")
    ai_summary = ai_score_summary(race_rows)

    # 結果・成績ページと同じ「最終予測」定義:
    # 直前予測が保存されているレースは直前、未保存は朝予測を採用する。
    final_rows = []
    for row in race_rows:
        final_prediction = row.get("live") or row.get("morning")
        final_rows.append({
            **row,
            "final_prediction": final_prediction,
            "final_formation_hit": formation_hit(final_prediction, row.get("trifecta"), "formation"),
            "final_box_hit": box_hit(final_prediction, row.get("trifecta")),
        })
    final_formation_summary = hit_summary_from_rows(final_rows, "final_formation_hit")
    final_box_summary = hit_summary_from_rows(final_rows, "final_box_hit")

    now = datetime.now(
        JST
    )

    generated = now.strftime(
        "%Y/%m/%d %H:%M"
    )

    display_date = (
        f"{target_date[:4]}/"
        f"{target_date[4:6]}/"
        f"{target_date[6:8]}"
    )

    cards = []

    for row in race_rows:

        actual_parts = []

        for (
            boat,
            name,
        ) in zip(
            row["actual"],
            row["actual_names"],
        ):

            actual_parts.append(
                f'<span class="boat">'
                f'<b>{boat}</b>号艇 '
                f'{esc(name)}'
                f'</span>'
            )

        actual_html = (
            '<span class="arrow">'
            " → "
            "</span>"
        ).join(
            actual_parts
        )

        payout_text = "—"

        if row["payout"] is not None:

            payout_text = (
                f'{row["payout"]:,}円'
            )

        odds_text = "—"

        if row["odds"] is not None:

            odds_text = (
                f'{row["odds"]:g}倍'
            )

        odds_note = ""

        if (
            row[
                "odds_minutes"
            ]
            is not None
        ):

            minutes = row[
                "odds_minutes"
            ]

            if minutes >= 0:

                odds_note = (
                    f"締切"
                    f"{minutes:g}分前"
                )

            else:

                odds_note = (
                    f"締切"
                    f"{abs(minutes):g}分後"
                )

        cards.append(
            f"""
<article class="race-card">

  <div class="race-head">

    <div>

      <div class="race-title">
        {esc(row["venue"])}
        {row["race"]}R
      </div>

      <div class="sub">
        締切
        {esc(row["deadline"])}
        ／
        結果
        {esc(row["result_time"])}
        ／
        {esc(row["technique"])}
      </div>

    </div>

    <div class="combo">
      {esc(row["trifecta"])}
    </div>

  </div>


  <div class="actual">

    <div class="label">
      実結果
    </div>

    <div>
      {actual_html}
    </div>

  </div>


  <div class="prediction-row">

    <div class="label">
      朝予測
    </div>

    <div>
      {prediction_html(row["morning"])}
      {all_scores_html(row["morning"], "朝予測")}
    </div>

    <div class="metrics">
      {evaluation_html(row["morning_eval"])}
    </div>

  </div>


  <div class="prediction-row">

    <div class="label">
      直前予測
    </div>

    <div>
      {prediction_html(row["live"])}
      {all_scores_html(row["live"], "直前予測")}
    </div>

    <div class="metrics">
      {evaluation_html(row["live_eval"])}
    </div>

  </div>


  <div class="label simulation-label">最終予測の買い目・100円/点シミュレーション</div>
  {simulation_html(row["live"] or row["morning"], row["trifecta"], row["payout"])}
  <div class="label simulation-label">AIスコア予測・保存済み上位12点</div>
  {ai_score_result_html(row["live"] or row["morning"], row["trifecta"], row["payout"])}

  <div class="money-grid">

    <div class="money-box">

      <span>
        3連単払戻
      </span>

      <strong>
        {payout_text}
      </strong>

    </div>


    <div class="money-box">

      <span>
        結果3連単の締切前オッズ
      </span>

      <strong>
        {odds_text}
      </strong>

      <small>
        {esc(odds_note)}
      </small>

    </div>

  </div>

</article>
"""
        )

    if cards:

        cards_html = "".join(
            cards
        )

    else:

        cards_html = """
<div class="empty">
  現在、結果確定済みレースはありません。
</div>
"""

    return f"""<!doctype html>
<html lang="ja">

<head>

<meta charset="utf-8">

<meta
  name="viewport"
  content="width=device-width,initial-scale=1"
>

<meta
  name="robots"
  content="noindex,nofollow"
>

<meta
  http-equiv="refresh"
  content="300"
>

<title>
レース照合
</title>


<style>

:root {{
  --bg:#f4f6f8;
  --card:#ffffff;
  --text:#111827;
  --muted:#667085;
  --line:#e5e7eb;
  --chip:#f3f4f6;
  --blue:#2563eb;
}}

* {{
  box-sizing:border-box;
}}

body {{
  margin:0;

  background:
    var(--bg);

  color:
    var(--text);

  font-family:
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    "Hiragino Sans",
    "Noto Sans JP",
    sans-serif;
}}

.wrap {{
  width:
    min(
      980px,
      100%
    );

  margin:auto;

  padding:
    16px
    12px
    50px;
}}

h1 {{
  margin:0;

  font-size:24px;
}}

.meta {{
  margin-top:5px;

  color:
    var(--muted);

  font-size:12px;
}}

.nav {{
  display:grid;

  grid-template-columns:
    repeat(
      4,
      minmax(
        0,
        1fr
      )
    );

  gap:6px;

  margin:
    14px
    0;

  padding:6px;

  border:
    1px solid
    var(--line);

  border-radius:14px;

  background:
    var(--card);
}}

.nav a {{
  display:flex;

  justify-content:center;
  align-items:center;

  min-height:44px;

  padding:
    7px
    3px;

  border-radius:10px;

  color:
    var(--text);

  text-align:center;
  text-decoration:none;

  font-size:12px;
  font-weight:800;
}}

.nav a.active {{
  background:
    var(--blue);

  color:white;
}}

.note {{
  margin:
    10px
    0
    14px;

  color:
    var(--muted);

  font-size:12px;

  line-height:1.6;
}}

.summary {{
  display:grid;

  grid-template-columns:
    repeat(
      3,
      minmax(
        0,
        1fr
      )
    );

  gap:8px;

  margin-bottom:14px;
}}

.summary-box {{
  padding:12px;

  background:
    var(--card);

  border:
    1px solid
    var(--line);

  border-radius:12px;
}}

.summary-box span {{
  display:block;

  color:
    var(--muted);

  font-size:11px;
}}

.summary-box strong {{
  display:block;

  margin-top:4px;

  font-size:19px;
}}

details.all-scores {{
  margin-top:8px;
}}
details.all-scores summary {{
  cursor:pointer;
  color:var(--muted);
  font-size:12px;
  font-weight:800;
}}
.score-chips {{
  display:flex;
  flex-wrap:wrap;
  gap:6px;
  margin-top:7px;
}}
.score-chip {{
  padding:5px 8px;
  border-radius:999px;
  background:var(--chip);
  font-size:12px;
  font-variant-numeric:tabular-nums;
}}

.race-card {{
  margin-bottom:12px;

  padding:14px;

  background:
    var(--card);

  border:
    1px solid
    var(--line);

  border-radius:14px;
}}

.race-head {{
  display:flex;

  justify-content:
    space-between;

  gap:10px;
}}

.race-title {{
  font-size:18px;

  font-weight:900;
}}

.sub {{
  margin-top:3px;

  color:
    var(--muted);

  font-size:11px;
}}

.combo {{
  white-space:nowrap;

  font-size:20px;

  font-weight:900;
}}

.actual {{
  margin-top:11px;

  padding:10px;

  background:
    var(--chip);

  border-radius:10px;

  line-height:1.6;
}}

.label {{
  margin-bottom:4px;

  color:
    var(--muted);

  font-size:11px;

  font-weight:800;
}}

.prediction-row {{
  display:grid;

  grid-template-columns:
    64px
    minmax(
      0,
      1fr
    );

  gap:
    5px
    10px;

  padding:
    10px
    0;

  border-bottom:
    1px solid
    var(--line);

  font-size:14px;

  line-height:1.6;
}}

.prediction-row .label {{
  margin:0;
}}

.metrics {{
  grid-column:2;

  display:flex;

  flex-wrap:wrap;

  gap:5px;
}}

.tag {{
  padding:
    3px
    7px;

  background:
    var(--chip);

  border-radius:
    999px;

  font-size:11px;

  font-weight:700;
}}

.boat small {{
  margin-left:4px;

  color:
    var(--muted);
}}

.arrow {{
  color:
    var(--muted);
}}

.missing {{
  color:
    var(--muted);

  font-size:12px;
}}

.simulation-label {{
  margin-top:12px;
}}
.simulation-grid {{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:8px;
  margin-top:6px;
}}
.simulation-box {{
  padding:10px;
  border:1px solid var(--line);
  border-radius:10px;
  background:var(--chip);
}}
.simulation-title {{
  font-size:13px;
  font-weight:900;
}}
.simulation-meta,
.simulation-money {{
  margin-top:5px;
  font-size:12px;
  line-height:1.5;
}}
.simulation-combos {{
  margin-top:7px;
  font-size:12px;
  line-height:1.8;
}}
.combo-pick {{
  display:inline-block;
  margin:1px 3px 1px 0;
}}
.hit-pick {{
  color:#dc2626;
  font-weight:900;
}}
.hit-status {{
  color:#dc2626;
  font-weight:900;
}}
.miss-status {{
  color:var(--muted);
}}
.ai-result-list {{
  display:grid;
  gap:6px;
  margin-top:10px;
}}
.ai-result-pick {{
  display:flex;
  justify-content:space-between;
  gap:10px;
  padding:8px 10px;
  border-radius:9px;
  background:var(--chip);
}}
.ai-result-pick.ai-bought {{
  border-left:4px solid var(--blue);
}}
.ai-result-pick span {{
  color:var(--muted);
  font-size:12px;
}}
.ai-result-box {{
  margin-bottom:12px;
}}
.ai-result-summary {{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:10px;
  cursor:pointer;
  list-style:none;
  user-select:none;
}}
.ai-result-summary::-webkit-details-marker {{
  display:none;
}}
.ai-result-summary::after {{
  content:"＋";
  flex:0 0 auto;
  font-size:18px;
  font-weight:900;
  color:var(--blue);
}}
.ai-result-box[open] .ai-result-summary::after {{
  content:"－";
}}
.ai-result-summary-meta {{
  margin-left:auto;
  color:var(--muted);
  font-size:11px;
  font-weight:800;
}}
.ai-result-body {{
  padding-top:6px;
}}

.money-grid {{
  display:grid;

  grid-template-columns:
    repeat(
      2,
      minmax(
        0,
        1fr
      )
    );

  gap:8px;

  margin-top:10px;
}}

.money-box {{
  padding:10px;

  background:
    var(--chip);

  border-radius:10px;
}}

.money-box span,
.money-box small {{
  display:block;

  color:
    var(--muted);

  font-size:11px;
}}

.money-box strong {{
  display:block;

  margin-top:3px;

  font-size:18px;
}}

.empty {{
  padding:30px;

  background:
    var(--card);

  border:
    1px solid
    var(--line);

  border-radius:14px;

  color:
    var(--muted);

  text-align:center;
}}


@media (
  max-width:600px
) {{

  .summary {{
    grid-template-columns:
      1fr;
  }}

  .simulation-grid {{
    grid-template-columns:1fr;
  }}

  .money-grid {{
    grid-template-columns:
      1fr;
  }}

  .nav a {{
    font-size:11px;
  }}
}}


@media (
  prefers-color-scheme:dark
) {{

  :root {{
    --bg:#0f1115;
    --card:#171a21;
    --text:#f3f4f6;
    --muted:#a8b0bd;
    --line:#2a3039;
    --chip:#222833;
    --blue:#3b82f6;
  }}

}}

</style>

</head>


<body>

<div class="wrap">

<h1>
レース照合
</h1>

<div class="meta">
  {display_date}
  ・確定
  {len(race_rows)}R
  ・更新
  {generated}
  JST
</div>


<nav class="nav">

  <a href="index.html">
    最新予想
  </a>

  <a href="results.html">
    結果・成績
  </a>

  <a href="analysis.html">
    AI分析
  </a>

  <a
    href="race_compare.html"
    class="active"
  >
    レース照合
  </a>

</nav>


<div class="note">

終了済みレースについて、
朝予測・最終直前予測と
実際の結果を照合します。

TOP3整合率は、
予測TOP3と実際のTOP3が
順不同で3艇すべて一致したレースを1、
1艇でも違うレースを0として集計します。

完全一致は、
予測した1着・2着・3着と
実際の1着・2着・3着が
着順まで一致した場合です。

</div>


<section class="summary">


<div class="summary-box">

  <span>
    確定レース
  </span>

  <strong>
    {len(race_rows)}R
  </strong>

</div>


<div class="summary-box">

  <span>
    朝 TOP3整合 / 完全一致 / 買い目的中
  </span>

  <strong>
    {percent(morning_summary["overlap"])}
    /
    {percent(morning_summary["exact"])}
    /
    {percent(morning_hit_summary["rate"])}
  </strong>

  <span>
    {morning_summary["count"]}R
  </span>

</div>


<div class="summary-box">

  <span>
    直前 TOP3整合 / 完全一致 / 買い目的中
  </span>

  <strong>
    {percent(live_summary["overlap"])}
    /
    {percent(live_summary["exact"])}
    /
    {percent(live_hit_summary["rate"])}
  </strong>

  <span>
    {live_summary["count"]}R
  </span>

</div>


<div class="summary-box">

  <span>
    AIスコア TOP3整合 / 完全一致 / 上位8点的中
  </span>

  <strong>
    {percent(ai_summary["overlap"])}
    /
    {percent(ai_summary["exact"])}
    /
    {percent(ai_summary["bought_hit"])}
  </strong>

  <span>
    {ai_summary["count"]}R
  </span>

</div>


</section>

{cards_html}


</div>

</body>

</html>
"""


# =========================================================
# MAIN
# =========================================================

def main():

    args = parse_args()

    target_date = str(
        args.date
    ).strip()

    if (
        len(target_date) != 8
        or not target_date.isdigit()
    ):

        raise SystemExit(
            "ERROR: "
            "--date は YYYYMMDD "
            "で指定してください"
        )

    output_dir = Path(
        args.output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "========================================"
    )

    print(
        "家族共有・レース照合ページ生成"
    )

    print(
        "========================================"
    )

    print(
        "対象日:",
        target_date,
    )

    # -----------------------------------------------------
    # 予測
    # -----------------------------------------------------

    (
        morning_predictions,
        live_predictions,
    ) = load_predictions(
        args.predictions_root,
        target_date,
    )

    # -----------------------------------------------------
    # 結果
    # -----------------------------------------------------

    race_rows = build_race_rows(
        target_date,
        morning_predictions,
        live_predictions,
    )

    print(
        "結果確定レース:",
        len(race_rows),
        "R",
    )

    # -----------------------------------------------------
    # HTML
    # -----------------------------------------------------

    page = render_html(
        target_date,
        race_rows,
    )

    output_path = (
        output_dir
        / "race_compare.html"
    )

    output_path.write_text(
        page,
        encoding="utf-8",
    )

    if not output_path.is_file():

        raise SystemExit(
            "ERROR: "
            "race_compare.html "
            "生成失敗"
        )

    if (
        output_path.stat().st_size
        <= 0
    ):

        raise SystemExit(
            "ERROR: "
            "race_compare.html "
            "が空です"
        )

    print(
        "出力:",
        output_path,
    )

    print(
        "race_compare.html: PASS"
    )

    print(
        "========================================"
    )


if __name__ == "__main__":
    main()