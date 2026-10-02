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
            "race_code":
                race_code,

            "top3":
                top3,

            "raw":
                row,
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

    return