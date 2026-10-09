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
from race_prediction_store import canonical_path, audit_race


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
            "stage": str(row.get("stage") or row.get("prediction_stage") or row.get("source_stage") or "").strip(),
            "prediction_quality": row.get("prediction_quality") or {},
            "ai_score_prediction": row.get("ai_score_prediction") or {},
            "signal_ai_prediction": row.get("signal_ai_prediction") or {},
            "up_signal": row.get("up_signal"),
            "down_signal": row.get("down_signal"),
        }

    return output


def load_saved_score_rows(root, date, stage):
    """Use persisted scored CSV; do not recalculate or infer missing predictions."""
    folder = root / date[:4] / date[4:6] / date[6:8]
    file = (folder / f"morning_predictions_{date}.csv" if stage == "morning"
            else folder / "live" / f"live_predictions_final_{date}.csv")
    if not file.is_file():
        return {}
    grouped = {}
    with file.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            code = extract_race_code(row, date)
            if code and safe_float(row.get("score")) is not None:
                grouped.setdefault(code, []).append(row)
    output = {}
    for code, boats in grouped.items():
        boats.sort(key=lambda b: (safe_int(b.get("rank")) or 99, safe_int(b.get("boat")) or 99))
        top = [normalize_pick(b) for b in boats[:3]]
        if len(top) < 3 or any(p is None for p in top):
            continue
        for pick in top:
            source = next((b for b in boats if normalize_boat(b.get("boat")) == pick["boat"]), None)
            if source:
                pick["name"] = pick.get("name") or source.get("racer_name") or ""
        output[code] = {"race_code": code, "top3": top, "boats": boats,
                        "raw": {"boats": boats}, "stage": stage,
                        "prediction_quality": {}, "ai_score_prediction": {}}
    return output


def merge_saved_scores(existing, saved):
    """Preserve existing metadata/order; fill scores by boat number."""
    for code, item in saved.items():
        if code not in existing:
            existing[code] = item
            continue
        current = existing[code]
        scores = {normalize_boat(b.get("boat")): b for b in item["boats"]}
        for pick in current.get("top3", []):
            source = scores.get(normalize_boat(pick.get("boat")))
            if source:
                pick["score"] = safe_float(source.get("score"))
                pick["name"] = pick.get("name") or source.get("racer_name") or ""
        current["boats"] = item["boats"]
    return existing


def load_recovered_live_predictions(target_date):
    """既知の収集不具合を安全に復旧した直前予測を照合表示用に読む。"""
    yyyy, mm, dd = target_date[:4], target_date[4:6], target_date[6:8]
    recovery_dir = Path("evaluations") / yyyy / mm / dd / "recovery"
    merged_path = recovery_dir / f"merged_live_predictions_{target_date}.csv"
    manifest_path = recovery_dir / f"live_recovery_manifest_{target_date}.json"

    if not merged_path.is_file() or not manifest_path.is_file():
        return {}

    manifest = read_json(manifest_path) or {}
    safe_recovery = (
        manifest.get("status") in {"complete", "partial"}
        and manifest.get("treat_recovered_as_observation") is True
        and manifest.get("result_leakage") is False
    )
    if not safe_recovery:
        return {}

    grouped = {}
    try:
        with merged_path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                race_code = extract_race_code(row, target_date)
                if race_code:
                    grouped.setdefault(race_code, []).append(row)
    except Exception as exc:
        print(f"WARN: 復旧直前予測CSV読込失敗: {merged_path}: {exc}")
        return {}

    official_misses = {}
    live_root = Path("daily_inputs") / yyyy / mm / dd / "live"
    miss_sources = (
        sorted(live_root.glob("**/beforeinfo_entries_*.csv"))
        if live_root.exists() else []
    )
    # Completed-race replays retain verified official scratch evidence under
    # evaluations/recovery, not necessarily under the intraday live/raw folder.
    # Without this source a legitimate five-starter race is discarded entirely.
    retry_entries = recovery_dir / f"official_retry_beforeinfo_entries_{target_date}.csv"
    if retry_entries.is_file():
        miss_sources.append(retry_entries)
    for miss_path in miss_sources:
        try:
            with miss_path.open("r", encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    flag = str(row.get("is_miss") or "").strip().lower()
                    if flag not in {"true", "1", "yes"}:
                        continue
                    race_code = extract_race_code(row, target_date)
                    boat = safe_int(row.get("boat"))
                    if race_code and boat is not None:
                        official_misses.setdefault(race_code, set()).add(boat)
        except Exception as exc:
            print(f"WARN: saved official scratch evidence unreadable: {miss_path}: {exc}")

    expected = safe_int(manifest.get("merged_analysis_races"))
    if expected is not None and len(grouped) != expected:
        print(
            "WARN: 復旧直前予測のレース数不一致:",
            len(grouped),
            "!=",
            expected,
        )
        return {}

    output = {}
    for race_code, boats in grouped.items():
        boats.sort(
            key=lambda row: (
                safe_int(row.get("rank")) or 99,
                -(safe_float(row.get("score")) or 0),
                safe_int(row.get("boat")) or 99,
            )
        )
        present_boats = {
            safe_int(row.get("boat"))
            for row in boats
            if safe_int(row.get("boat")) is not None
        }
        missing_boats = sorted(set(range(1, 7)) - present_boats)
        allowed_missing = official_misses.get(race_code, set())
        if len(boats) < 3 or any(boat not in allowed_missing for boat in missing_boats):
            print("WARN: recovery row incomplete (excluded):", race_code)
            continue
        if len(boats) + len(missing_boats) != 6:
            print("WARN: recovery boat-count mismatch (excluded):", race_code)
            continue

        top3 = []
        for row in boats[:3]:
            pick = normalize_pick(row)
            if pick:
                top3.append(pick)
        if len(top3) != 3:
            return {}

        first = boats[0]
        quality = {
            "status": "recovered_observation",
            "recovery_needed": False,
            "provenance": manifest.get("provenance"),
        }
        raw = {
            "race_id": first.get("race_id"),
            "venue_code": first.get("venue_code"),
            "venue_name": first.get("venue_name"),
            "race": first.get("race"),
            "deadline": first.get("deadline"),
            "stage": "live_recovered_analysis",
            "prediction_quality": quality,
            "official_miss_boats": missing_boats,
            "boats": boats,
        }
        output[race_code] = {
            "race_code": race_code,
            "top3": top3,
            "boats": boats,
            "raw": raw,
            "stage": "live_recovered_analysis",
            "prediction_quality": quality,
            "official_miss_boats": missing_boats,
            "ai_score_prediction": {},
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

        if path.is_file() and path.stat().st_size > 0:
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
        # 直前予測の表示・評価は live_predictions_final を正本とする。
        # formation_predictions_final は直前欠損レースを朝予測で補完するため、
        # 「直前予測」欄の入力には使わない。
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

        if path.is_file() and path.stat().st_size > 0:
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
                and path.stat().st_size > 0
            ):
                preferred.append(
                    path
                )

        if preferred:

            return preferred[-1]

    return None


def locate_formation_file(root, target_date):
    path = canonical_path(target_date, root)
    return path if path.is_file() else None


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

    morning = merge_saved_scores(morning, load_saved_score_rows(root, target_date, "morning"))
    live = merge_saved_scores(live, load_saved_score_rows(root, target_date, "live"))

    recovered_live = load_recovered_live_predictions(
        target_date
    )
    if recovered_live:
        for code, recovered in recovered_live.items():
            live.setdefault(code, recovered)
        print(
            "復旧済み直前予測を照合表示に採用:",
            len(live),
            "R",
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

    formation_file = locate_formation_file(root, target_date)
    formations = load_prediction_file(formation_file, target_date) if formation_file else {}
    print("通常買い目読込:", len(formations), "R")

    return (
        morning,
        live,
        formations,
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


def load_archive_result_fallback(target_date):
    """外部公開CSVが遅延・欠損した場合だけ、検証済み公式保存結果で補完する。"""
    yyyy, mm, dd = target_date[:4], target_date[4:6], target_date[6:8]
    base = Path("archive") / yyyy / mm / dd
    result_path = base / f"results_{target_date}_all.csv"
    boat_path = base / f"boat_results_{target_date}_all.csv"
    validation_path = base / f"fast_results_validation_{target_date}.json"

    validation = read_json(validation_path) or {}
    # PARTIAL is expected during the race day; every archived completed
    # trifecta is independently parsed before it is added to the page.
    archive_valid = validation.get("status") in {"PASS", "PARTIAL"}

    results_by_race = {}
    if archive_valid and result_path.is_file():
        with result_path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                race_code = extract_race_code(row, target_date)
                actual = parse_trifecta_result(row.get("trifecta"))
                if not race_code or len(actual) != 3:
                    continue
                results_by_race[race_code] = {
                    "actual": actual,
                    "payout": safe_int(row.get("trifecta_pay")),
                    "technique": str(row.get("technique") or "").strip(),
                    "actual_names": ["", "", ""],
                }

    if archive_valid and boat_path.is_file() and results_by_race:
        names_by_race = {}
        with boat_path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                race_code = extract_race_code(row, target_date)
                finish = safe_int(row.get("finish"))
                if race_code not in results_by_race or finish not in (1, 2, 3):
                    continue
                names_by_race.setdefault(race_code, {})[finish] = str(
                    row.get("racer_name") or ""
                ).replace("　", " ").strip()

        for race_code, item in results_by_race.items():
            names = names_by_race.get(race_code, {})
            item["actual_names"] = [names.get(rank, "") for rank in (1, 2, 3)]

    # Missing official trifectas can be restored from separately audited
    # primary-source records. Never invent a third finisher for a race
    # where the official 3連単 was not established.
    verified_path = base / f"official_result_backfills_{target_date}.json"
    verified = read_json(verified_path) if verified_path.is_file() else {}
    for item in (verified or {}).get("verified_results", []):
        if not isinstance(item, dict) or item.get("source_type") != "boatrace_official":
            continue
        if not str(item.get("source_url") or "").startswith(
            "https://www.boatrace.jp/owpc/pc/race/raceresult?"
        ):
            continue
        race_code = extract_race_code(item, target_date)
        actual = parse_trifecta_result(item.get("trifecta"))
        payout = safe_int(item.get("trifecta_pay"))
        if not race_code or not race_code.startswith(target_date):
            continue
        if len(actual) != 3 or payout is None or payout <= 0:
            continue
        if race_code not in results_by_race:
            results_by_race[race_code] = {
                "actual": actual,
                "payout": payout,
                "technique": str(item.get("technique") or "").strip(),
                "actual_names": ["", "", ""],
                "result_source": "audited_official_result",
            }
            print("監査済み公式結果から3連単を補完:", race_code, item["source_url"])
    return results_by_race


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


def fujin_raijin_marker(raijin, fujin):
    raijin = raijin or {}
    fujin = fujin or {}
    raijin_level = safe_int(raijin.get("level")) or 0
    fujin_level = safe_int(fujin.get("level")) or 0

    if raijin_level <= 0 and fujin_level <= 0:
        return ""

    max_rise = safe_float(raijin.get("max_rise"))
    candidate_text = " / ".join(
        f"{safe_int(x.get('boat')) or '?'}号艇 +{safe_float(x.get('rise')) or 0:.1f}"
        for x in (raijin.get("candidates") or [])
    )
    raijin_title = (
        f"雷神シグナル {raijin_level}/3"
        + (f"｜最大上昇 +{max_rise:.1f}" if max_rise is not None else "")
        + (f"｜{candidate_text}" if candidate_text else "")
        + "｜表示・分析のみ（予測計算には未反映）"
    )

    metrics = fujin.get("metrics") or {}
    rank1_delta = safe_float(metrics.get("rank1_delta"))
    top3_delta_sum = safe_float(metrics.get("top3_delta_sum"))
    gap12 = safe_float(metrics.get("gap_1_2"))
    fujin_parts = [f"風神シグナル {fujin_level}/3"]
    if rank1_delta is not None:
        fujin_parts.append(f"1位朝比 {rank1_delta:.1f}")
    if top3_delta_sum is not None:
        fujin_parts.append(f"TOP3合計 {top3_delta_sum:.1f}")
    if gap12 is not None:
        fujin_parts.append(f"1-2位差 {gap12:.1f}")
    fujin_parts.append("表示・分析のみ（予測計算には未反映）")
    fujin_title = "｜".join(fujin_parts)

    top = (
        '<span class="signal-row raijin" title="'
        + esc(raijin_title)
        + '">'
        + ("⚡" * min(3, raijin_level))
        + "</span>"
        if raijin_level > 0
        else '<span class="signal-row raijin empty-signal">&nbsp;</span>'
    )
    bottom = (
        '<span class="signal-row fujin" title="'
        + esc(fujin_title)
        + '">'
        + ("💨" * min(3, fujin_level))
        + "</span>"
        if fujin_level > 0
        else '<span class="signal-row fujin empty-signal">&nbsp;</span>'
    )
    return (
        '<span class="fujin-raijin-stack" title="風神雷神シグナル">'
        + top
        + bottom
        + "</span>"
    )

def signal_payout_badge(payout, raijin, fujin, canonical_signal=None):
    """Distinguish true non-trigger, unobservable inputs, and retrospective catch."""
    payout_value = safe_int(payout)
    if payout_value is None or payout_value < 5000:
        return ""

    raijin = raijin or {}
    fujin = fujin or {}
    canonical_signal = canonical_signal or {}
    raijin_level = safe_int(raijin.get("level")) or 0
    fujin_level = safe_int(fujin.get("level")) or 0

    if raijin_level > 0 or fujin_level > 0:
        # A historical replay is valid for backtest catch statistics but
        # must not pretend a ticket or realtime alert existed at the deadline.
        if canonical_signal.get("recovered_after_result") is True:
            return (
                '<span class="signal-payout-hit" '
                'title="保存済み公式展示から事後にシグナルを再現（締切時のリアルタイム検知・実購入ではない）">'
                '5千円以上・事後捕捉'
                '</span>'
            )
        return (
            '<span class="signal-payout-hit" '
            'title="風神または雷神が発動し、3連単払戻が5,000円以上">'
            '5千円以上捕捉'
            '</span>'
        )

    # The old badge incorrectly treated an UNKNOWN signal as a false signal.
    # Not captured and not observable are different denominators in PDCA.
    if (
        raijin.get("available") is not True
        or fujin.get("available") is not True
        or canonical_signal.get("signal_ai_status")
        in ("prediction_missing", "signal_not_yet_observable")
    ):
        return (
            '<span class="signal-payout-miss" '
            'title="風神・雷神の判定入力が未保存または復元待ちで判定不可">'
            '5千円以上・未判定'
            '</span>'
        )
    return (
        '<span class="signal-payout-miss" '
        'title="有効な直前入力で検証済みだが風神・雷神は未発動">'
        '5千円以上・未発動'
        '</span>'
    )

def parse_trifecta_result(value):
    text = str(value or "").strip()
    if not text:
        return []
    parts = [normalize_boat(x) for x in text.replace("=", "-").split("-")]
    if len(parts) != 3 or any(x is None or x not in range(1, 7) for x in parts):
        return []
    if len(set(parts)) != 3:
        return []
    return parts


def prediction_name_map(*predictions):
    names = {}
    for prediction in predictions:
        if not prediction:
            continue
        boats = prediction.get("boats") or (prediction.get("raw") or {}).get("boats") or []
        for row in boats:
            boat = normalize_boat(row.get("boat"))
            if boat is None:
                continue
            name = str(
                row.get("name")
                or row.get("racer_name")
                or row.get("player_name")
                or ""
            ).replace("　", " ").strip()
            if name:
                names.setdefault(boat, name)
    return names


# =========================================================
# レースデータ統合
# =========================================================

def classify_live_for_pdca(prediction):
    """Return (verified_live, display): neutral is visible but not a real sample."""
    if not prediction:
        return None, None
    quality = prediction.get("prediction_quality") or (prediction.get("raw") or {}).get("prediction_quality") or {}
    boats = prediction.get("boats") or (prediction.get("raw") or {}).get("boats") or []
    pending = quality.get("signal_blocked") is True or any(
        str(boat.get("score_fallback") or "").strip().lower() in {"true", "yes", "1"}
        for boat in boats if isinstance(boat, dict)
    )
    return (None, prediction) if pending else (prediction, prediction)


def neutral_display_from_canonical(formation_prediction):
    """Display (but DO NOT score as official LIVE) a saved morning-neutral record.

    This is a view-only representation; all real-time signal/ROI evaluation
    continues to require verified official exhibition.
    """
    if not formation_prediction:
        return None
    raw = formation_prediction.get("raw") or {}
    quality = raw.get("prediction_quality") or {}
    neutral_only = quality.get("signal_blocked") is True or (
        quality.get("status") == "fallback"
        and quality.get("fallback_source") == "saved_morning_prediction"
        and not any(b.get("exhibition_time") is not None and
                    b.get("exhibition_st") is not None
                    for b in (raw.get("boats") or []))
    )
    if not neutral_only:
        return None
    flagged = []
    for boat in raw.get("boats") or []:
        item = dict(boat)
        item["score_fallback"] = True
        if not item.get("score_fallback_reasons"):
            item["score_fallback_reasons"] = [
                "exhibition_course", "exhibition_time", "exhibition_st"
            ]
        flagged.append(item)
    view = dict(formation_prediction)
    view["boats"] = flagged
    view["raw"] = dict(raw, boats=flagged)
    view["prediction_quality"] = dict(
        quality, status="fallback", recovery_needed=True, signal_blocked=True
    )
    view["stage"] = "neutral_morning_fallback"
    return view


def build_race_rows(
    target_date,
    morning_predictions,
    live_predictions,
    formation_predictions=None,
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

    ai_details = load_ai_details(target_date)
    archive_fallback = load_archive_result_fallback(target_date)
    race_rows = []

    # 詳細結果CSVは払戻CSVより数分遅れる場合がある。
    # 払戻で3連単が確定していれば、その時点で終了済みレースとして扱う。
    completed_codes = set(
        code
        for code in results
        if str(code).startswith(target_date)
    )
    completed_codes.update(
        code
        for code, row in payouts.items()
        if str(code).startswith(target_date)
        and len(parse_trifecta_result(row.get("3連単_組番"))) == 3
    )
    # 外部公開CSVが1Rだけ遅れても、公式保存結果の検証がPASSなら表示から落とさない。
    completed_codes.update(
        code
        for code in archive_fallback
        if str(code).startswith(target_date)
    )

    for race_code in sorted(completed_codes):
        result = results.get(race_code, {})
        payout_row = payouts.get(race_code, {})
        archive_result = archive_fallback.get(race_code, {})
        archive_fallback_used = False

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
        formation_prediction = (formation_predictions or {}).get(race_code)

        actual = []
        actual_names = []
        detailed_result_ready = True

        for rank in range(1, 4):
            boat = normalize_boat(
                result.get(f"{rank}着_艇番")
            )
            if boat is None:
                detailed_result_ready = False
                break

            actual.append(boat)
            actual_names.append(
                str(
                    result.get(
                        f"{rank}着_選手名",
                        "",
                    )
                ).replace("　", " ").strip()
            )

        if not detailed_result_ready:
            actual = parse_trifecta_result(
                payout_row.get("3連単_組番")
            )
            if len(actual) != 3:
                actual = list(archive_result.get("actual") or [])
                archive_fallback_used = len(actual) == 3
            if len(actual) != 3:
                continue

            archived_names = archive_result.get("actual_names") or []
            if archive_fallback_used and len(archived_names) == 3:
                actual_names = archived_names
            else:
                names = prediction_name_map(
                    live,
                    morning,
                    formation_prediction,
                )
                actual_names = [
                    names.get(boat, "")
                    for boat in actual
                ]

        if live:
            live_stage = str(live.get("stage") or (live.get("raw") or {}).get("stage") or (live.get("raw") or {}).get("prediction_stage") or "").strip().lower()
            if live_stage in {"morning", "\u671d"}:
                live = None

        # Partial live scores stay visible, but are not eligible for
        # official-LIVE accuracy or betting evaluation until fully verified.
        live, live_display = classify_live_for_pdca(live)
        if live_display is None:
            live_display = neutral_display_from_canonical(formation_prediction)

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
        if payout_value is None:
            payout_value = safe_int(
                archive_result.get("payout")
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
            result.get("締切時刻")
            or payout_row.get("締切時刻")
            or (live or {}).get("raw", {}).get("deadline")
            or (morning or {}).get("raw", {}).get("deadline")
            or ""
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
                    (
                        str(
                            result.get(
                                "結果記録時刻",
                                "",
                            )
                        ).strip()
                        if detailed_result_ready
                        else (
                            "公式保存"
                            if archive_fallback_used
                            else "速報"
                        )
                    ),

                "technique":
                    (
                        str(
                            result.get(
                                "決まり手",
                                "",
                            )
                        ).strip()
                        if detailed_result_ready
                        else (
                            str(archive_result.get("technique") or "").strip()
                            if archive_fallback_used
                            else "詳細反映待ち"
                        )
                    ),

                "result_source":
                    (
                        "detailed"
                        if detailed_result_ready
                        else (
                            "archive"
                            if archive_fallback_used
                            else "payout"
                        )
                    ),

                "actual":
                    actual,

                "actual_names":
                    actual_names,

                "morning":
                    morning,

                "live":
                    live,

                "live_display":
                    live_display,

                "formation_prediction":
                    formation_prediction,

                "ai_evaluation":
                    ai_details.get(race_code) or ai_details.get("".join(ch for ch in race_code if ch.isdigit())[:12]),

                # The SAME saved record governs both pre- and post-race screens.
                # Do not recompute a different signal after the race.
                "up_signal": (
                    (formation_prediction.get("raw") or {}).get("up_signal") or {}
                    if formation_prediction is not None else {}
                ),
                "down_signal": (
                    (formation_prediction.get("raw") or {}).get("down_signal") or {}
                    if formation_prediction is not None else {}
                ),

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

                "morning_formation_hit": formation_hit(formation_prediction, trifecta, "morning_formation") if formation_hit(formation_prediction, trifecta, "morning_formation") is not None else formation_hit(live, trifecta, "morning_formation"),
                # 最終formationは、直前予測があるレースでは必ず直前予測から生成される。
                # live_predictions_final 自体にはformationを持たないため、保存済みformation側を参照する。
                "live_formation_hit": formation_hit(formation_prediction, trifecta, "formation") if live else None,

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
        # 復旧したスコアと、当時保存できていない直前買い目を混同しない。
        # 朝の代替買い目を「直前購入的中」として数えない。
        if live and (live.get("prediction_quality") or {}).get("status") == "recovered_observation":
            race_rows[-1]["live_formation_hit"] = None

    built_codes = {
        row["race_code"]
        for row in race_rows
    }
    missing_codes = sorted(
        completed_codes - built_codes
    )
    if missing_codes:
        # 当日途中は公開結果CSVの更新タイミング差で、一部レースだけ
        # 着順/払戻の片側が先に到着することがある。取得済みレースまで
        # ページ全体を止めず、欠損分は次回5分更新で自動補完する。
        print(
            "WARN: レース照合一時欠損（次回更新で再取得）: "
            + ", ".join(missing_codes)
        )

    print(
        "レース照合整合性: "
        + ("PARTIAL" if missing_codes else "PASS")
        + " / "
        + f"確定元 {len(completed_codes)}R / 表示 {len(built_codes)}R"
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

def score_map(prediction):
    if not prediction:
        return {}
    boats = prediction.get("boats") or (prediction.get("raw") or {}).get("boats") or []
    out = {}
    for boat in boats:
        b = normalize_boat(boat.get("boat"))
        score = safe_float(boat.get("score"))
        if b is not None and score is not None:
            out[b] = score
    return out


def morning_reference_map(morning_prediction, live_prediction=None):
    out = {}
    if live_prediction:
        boats = live_prediction.get("boats") or (live_prediction.get("raw") or {}).get("boats") or []
        for row in boats:
            b = normalize_boat(row.get("boat"))
            ref = safe_float(row.get("morning_score_reference"))
            if b is not None and ref is not None:
                out[b] = ref
    for b, score in score_map(morning_prediction).items():
        out.setdefault(b, score)
    return out


def score_delta_html(boat, score, morning_scores):
    if not morning_scores or boat not in morning_scores:
        return ""
    delta = score - morning_scores[boat]
    if abs(delta) < 0.05:
        return '<span class="score-delta flat">→ ±0.0</span>'
    if delta > 0:
        return f'<span class="score-delta up">▲ +{delta:.1f}</span>'
    return f'<span class="score-delta down">▼ {delta:.1f}</span>'


def is_neutral_boat(boat):
    return str(boat.get("score_fallback") or "").strip().lower() in {"1", "true", "yes"}


def neutral_boat_marker(boat):
    if not is_neutral_boat(boat):
        return ""
    reasons = boat.get("score_fallback_reasons") or []
    if isinstance(reasons, str):
        reasons = [reason for reason in reasons.split(",") if reason]
    label = "朝のスコアを中立補完（±0.0）。公式直前データ復旧待ち"
    if reasons:
        label += "：" + " / ".join(str(x) for x in reasons)
    return f'<span class="quality-warning" title="{esc(label)}"> ▲</span>'


def prediction_quality_warning(prediction):
    if not prediction:
        return ""
    quality = prediction.get("prediction_quality") or (prediction.get("raw") or {}).get("prediction_quality") or {}
    if quality.get("recovery_needed") or quality.get("status") == "fallback":
        reasons = quality.get("reason") or []
        label = "補完した直前予測・復旧対象：" + " / ".join(str(x) for x in reasons)
        return f'<span class="quality-warning" title="{esc(label)}">▲</span>'
    return ""

def prediction_html(prediction, morning_scores=None):
    if not prediction:
        return '<span class="missing">予測なし</span>'
    picks = prediction.get("top3", [])
    if len(picks) < 3:
        return '<span class="missing">予測なし</span>'
    output = []
    fallback_boats = {
        normalize_boat(item.get("boat")): item
        for item in (prediction.get("boats") or (prediction.get("raw") or {}).get("boats") or [])
        if isinstance(item, dict)
    }
    for pick in picks[:3]:
        boat = normalize_boat(pick.get("boat"))
        name = esc(pick.get("name", ""))
        score = safe_float(pick.get("score"))
        score_html = ""
        if score is not None:
            score_html = f'<small>{score:.1f}</small>{score_delta_html(boat, score, morning_scores)}'
        output.append(f'<span class="boat"><b>{boat}</b>号艇 {name}{neutral_boat_marker(fallback_boats.get(boat) or {})}{score_html}</span>')
    return '<span class="arrow"> → </span>'.join(output)


def all_scores_html(prediction, label, morning_scores=None):
    if not prediction:
        return ""
    boats = prediction.get("boats") or (prediction.get("raw") or {}).get("boats") or []
    scored = []
    for boat in boats:
        b = normalize_boat(boat.get("boat"))
        score = safe_float(boat.get("score"))
        name = str(
            boat.get("racer_name")
            or boat.get("name")
            or boat.get("player_name")
            or ""
        ).replace("　", " ").strip()
        if b is not None and score is not None:
            scored.append((b, score, name, boat))
    if not scored:
        return ""
    scored.sort(key=lambda x: (-x[1], x[0]))
    chips = " ".join(
        f'<span class="score-chip">{b}号艇'
        f'{(" " + esc(name)) if name else ""} '
        f'{score:.1f}{neutral_boat_marker(source)}{score_delta_html(b, score, morning_scores)}</span>'
        for b, score, name, source in scored
    )
    score_title = "6艇すべてのスコア" if len(scored) == 6 else f"取得済み{len(scored)}艇のスコア"
    return f'<details class="all-scores"><summary>{esc(label)}・{score_title}</summary><div class="score-chips">{chips}</div></details>'

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



def signal_actual_combo_rank(signal_prediction, actual_trifecta):
    """Observed finish rank in the FROZEN full signal-AI ordering.

    Strictly require the complete saved 3-permutation ranking; do not mislabel
    an available top-24 ticket list as '120 total'. No re-scoring after result.
    Returns (rank, total) or (None, None) when unknown/unverifiable.
    """
    ai = signal_prediction or {}
    rows = ai.get("all_120_combinations") or []
    expected = safe_int(ai.get("valid_combination_count"))
    if expected not in (24, 60, 120) or len(rows) != expected:
        return None, None
    names = [str(x.get("combination") or "") for x in rows if isinstance(x, dict)]
    if len(names) != expected or len(set(names)) != expected:
        return None, None
    combo = str(actual_trifecta or "").strip()
    if not combo:
        return None, None
    try:
        return names.index(combo) + 1, expected
    except ValueError:
        return None, None


def ai_score_result_html(prediction, trifecta, payout, canonical_signal=None):
    """Use saved signal-only top 24 when active; do not modify normal AI."""
    prediction = prediction or {}
    raw = prediction.get("raw") or {}
    canonical_signal = canonical_signal or {}
    key = canonical_signal.get("signal_key")
    is_signal = bool(key)
    signal = canonical_signal.get("signal_ai_prediction") or {}
    if is_signal and signal.get("signal_key") != key:
        return '<div class="simulation missing">シグナル発動・専用AI24点の保存データを修復中（通常AI8点には切替不可）</div>'
    ai = signal if is_signal else (
        prediction.get("ai_score_prediction") or raw.get("ai_score_prediction") or {}
    )
    label = "風神雷神専用AI予想" if is_signal else "通常AIスコア予測"
    all120 = ai.get("all_120_combinations") or ai.get("combinations") or []
    purchase_points = 24 if is_signal else (safe_int(ai.get("points")) or 8)
    display_points = 24 if is_signal else 12
    visible = all120[:display_points]
    if not visible:
        return '<div class="simulation missing">専用AI24点未保存（要修復）</div>' if is_signal else '<div class="simulation missing">AI予想の保存済み買い目なし</div>'

    bought_combos = [
        str(item.get("combination") or "") for item in all120[:purchase_points]
    ]
    # Incomplete saved combinations are not counted as a full 24-point ticket.
    if is_signal and len(bought_combos) != 24:
        return '<div class="simulation missing">シグナルAIの購入24点が未保存のため集計対象外</div>'
    rows = []
    for i, item in enumerate(visible, 1):
        combo = str(item.get("combination") or "")
        score = safe_float(item.get("score"))
        bought = i <= purchase_points
        classes = ["ai-result-pick"]
        if bought:
            classes.append("ai-bought")
        if combo == trifecta:
            classes.append("hit-pick")
        badge = "購入" if bought else "参考"
        score_text = f"{score:.1f}" if score is not None else "—"
        rows.append(
            f'<div class="{" ".join(classes)}">'
            f'<b>{i}位 {esc(combo)}</b>'
            f'<span>AI評価 {score_text}点 ／ {badge}</span>'
            '</div>'
        )

    hit = trifecta in bought_combos
    investment = purchase_points * 100 if is_signal else safe_int(ai.get("investment_100yen"))
    if investment is None:
        investment = len(bought_combos) * 100
    returned = payout if hit and payout is not None else 0
    profit = returned - investment
    status = '<span class="hit-status">的中</span>' if hit else '<span class="miss-status">不的中</span>'
    if is_signal:
        actual_rank, total_ranked = signal_actual_combo_rank(signal, trifecta)
        rank_label = (f"実着{actual_rank}位／{total_ranked}通り"
                      if actual_rank is not None else "実着順位未取得")
        if hit:
            closed_result = (f'<span class="signal-rank-hit" title="風神雷神AI購入上位24点に実着が含まれました">'
                             f'✓ 的中・{esc(rank_label)}</span>')
        else:
            closed_result = (f'<span class="signal-rank-miss" title="購入24点の外でも実着のAI評価順位を確認できます">'
                             f'不的中・{esc(rank_label)}</span>')
    else:
        closed_result = status


    return f"""
    <details class="simulation-box ai-result-box">
      <summary class="ai-result-summary">
        <span class="simulation-title">{label}を見る</span>
        <span class="ai-result-summary-meta">
          購入{purchase_points}点 ／ {closed_result} ／ 投資 <b>{investment:,}円</b> ／ 払戻 <b>{returned:,}円</b> ／ 収支 <b>{profit:+,}円</b>
        </span>
      </summary>
      <div class="ai-result-body">
        <div class="simulation-meta">表示{len(visible)}点 ／ 購入上位{purchase_points}点・各100円</div>
        <div class="ai-result-list">{''.join(rows)}</div>
      </div>
    </details>
    """


def ai_eval_detail_html(detail):
    if not detail:
        return '<div class="simulation missing">AIスコア予測なし</div>'
    combos = [x.strip() for x in str(detail.get("combinations") or "").split("/") if x.strip()]
    points = safe_int(detail.get("points")) or len(combos)
    hit = bool(safe_int(detail.get("hit")) or 0)
    actual = esc(detail.get("actual_trifecta") or "—")
    combo_html = " / ".join(esc(x) for x in combos) if combos else "—"
    status = "的中" if hit else "不的中"
    return (
        '<details class="simulation-box ai-result-box">'
        '<summary><span class="simulation-title">AIスコア予測を見る</span></summary>'
        f'<div class="simulation-meta">AI独自スコア ／ 保存済み上位{points}点 ／ {status} ／ 実結果 {actual}</div>'
        f'<div class="simulation-combos">{combo_html}</div>'
        '</details>'
    )


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
    """AI着順別スコアのTOP3整合・完全一致と、保存済み購入点数で買い目的中を評価。"""
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
    points = safe_int(ai.get("points")) or 8
    bought = [str(x.get("combination") or "") for x in all120[:points]]
    trifecta = "-".join(str(x) for x in actual3)
    bought_hit = trifecta in bought
    return {"overlap": top3_overlap, "exact": exact, "bought_hit": bought_hit}




def load_formation_evaluation(target_date):
    p = Path(f"evaluations/{target_date[:4]}/{target_date[4:6]}/{target_date[6:8]}/formation_simulation_{target_date}.json")
    data = read_json(p) if p.is_file() else None
    overall = (data or {}).get("overall") or {}
    rate = safe_float(overall.get("hit_rate"))
    return (rate * 100.0) if rate is not None else None


def load_ai_details(target_date):
    p = Path(f"evaluations/{target_date[:4]}/{target_date[4:6]}/{target_date[6:8]}/ai_score_simulation_{target_date}.json")
    data = read_json(p) if p.is_file() else None
    out = {}
    for item in (data or {}).get("details") or []:
        rid = str(item.get("race_id") or "").strip()
        if rid:
            out[rid] = item
            digits = "".join(ch for ch in rid if ch.isdigit())
            if len(digits) >= 12:
                out[digits[:12]] = item
    return out


def load_ai_evaluation(target_date):
    p = Path(f"evaluations/{target_date[:4]}/{target_date[4:6]}/{target_date[6:8]}/ai_score_simulation_{target_date}.json")
    data = read_json(p) if p.is_file() else None
    overall = (data or {}).get("overall") or {}
    n = safe_int(overall.get("races")) or 0
    if not n:
        return None
    return {"count": n, "overlap": safe_float(overall.get("top3_alignment_rate")) * 100.0 if safe_float(overall.get("top3_alignment_rate")) is not None else None, "exact": safe_float(overall.get("exact_alignment_rate")) * 100.0 if safe_float(overall.get("exact_alignment_rate")) is not None else None, "bought_hit": safe_float(overall.get("hit_rate")) * 100.0 if safe_float(overall.get("hit_rate")) is not None else None}


def final_ai_prediction(row):
    """終了済みレースのAI予測は、結果を使わず事前生成済みformation保存値を最優先で使う。"""
    formation = row.get("formation_prediction")
    if formation and (
        formation.get("ai_score_prediction")
        or (formation.get("raw") or {}).get("ai_score_prediction")
    ):
        return formation
    live = row.get("live")
    if live and (
        live.get("ai_score_prediction")
        or (live.get("raw") or {}).get("ai_score_prediction")
    ):
        return live
    morning = row.get("morning")
    if morning and (
        morning.get("ai_score_prediction")
        or (morning.get("raw") or {}).get("ai_score_prediction")
    ):
        return morning
    return formation or live or morning


def ai_score_summary(rows):
    evals = []
    for row in rows:
        prediction = final_ai_prediction(row)
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

    # Canonical formation record is also the only signal/ticket source here.
    for record in race_rows:
        original = (record.get("formation_prediction") or {}).get("raw") or {}
        checked = audit_race(original) if original else {
            "signal_key": None, "signal_ai_status": "prediction_missing"
        }
        record["_canonical_signal"] = {
            **checked, "signal_ai_prediction": original.get("signal_ai_prediction") or {}
        }

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
    # 直前買い目的中率は、直前予測が実際に存在したレースだけを対象に
    # その時点で保存された最終formationを照合する。
    # 日次formation評価は「直前が無ければ朝」を含む最終予測全体なので、
    # ここへ流用すると直前欄の分母がずれるため使用しない。
    # 日次AI評価ファイルを正本にする。予測JSONへの埋め込み有無で0Rにならないようにする。
    ai_summary = load_ai_evaluation(target_date) or ai_score_summary(race_rows)

    # 結果・成績ページと同じ「最終予測」定義:
    # 直前予測が保存されているレースは直前、未保存は朝予測を採用する。
    final_rows = []
    for row in race_rows:
        final_prediction = row.get("live") or row.get("morning")
        final_rows.append({
            **row,
            "final_prediction": final_prediction,
            "final_eval": evaluate_top3(final_prediction, row.get("actual") or []),
            # 最終買い目は build_latest_prediction_view.py が
            # 「直前があれば直前、無ければ朝」で保存した formation を正本にする。
            "final_formation_hit": formation_hit(
                row.get("formation_prediction") or final_prediction,
                row.get("trifecta"),
                "formation",
            ),
            "final_box_hit": box_hit(final_prediction, row.get("trifecta")),
        })
    final_summary = aggregate(final_rows, "final_eval")
    final_formation_summary = hit_summary_from_rows(final_rows, "final_formation_hit")
    final_box_summary = hit_summary_from_rows(final_rows, "final_box_hit")

    # Evaluate precisely the SAME signal/24 tickets as the visible race card.
    # Never silently skip a flagged race when dedicated tickets are missing.
    signal24_rows = []
    signal24_missing = 0
    signal24_actual_ranks = []
    signal24_unranked = 0
    for record in race_rows:
        signal_info = record["_canonical_signal"]
        if not signal_info["signal_key"]:
            continue
        signal_pred = signal_info["signal_ai_prediction"]
        ranked_combinations = (
            signal_pred.get("all_120_combinations")
            or signal_pred.get("combinations")
            or []
        )
        bought_24 = [
            str(item.get("combination") or "")
            for item in ranked_combinations[:24]
        ]
        actual_combo = record.get("trifecta")
        actual_pay = record.get("payout")
        if len(bought_24) != 24 or not actual_combo or actual_pay is None:
            signal24_missing += 1
            continue
        hit_24 = actual_combo in bought_24
        actual_rank, _rank_total = signal_actual_combo_rank(signal_pred, actual_combo)
        if actual_rank is not None:
            signal24_actual_ranks.append(actual_rank)
        else:
            signal24_unranked += 1
        signal24_rows.append({
            "hit": hit_24,
            "investment": 2400,
            "returned": actual_pay if hit_24 else 0,
        })
    signal24_races = len(signal24_rows)
    signal24_hits = sum(int(x["hit"]) for x in signal24_rows)
    signal24_invest = 2400 * signal24_races
    signal24_paid = sum(x["returned"] for x in signal24_rows)
    signal24_profit = signal24_paid - signal24_invest
    signal24_roi = 100.0 * signal24_paid / signal24_invest if signal24_invest else None
    signal24_mean_actual_rank = (
        sum(signal24_actual_ranks) / len(signal24_actual_ranks)
        if signal24_actual_ranks else None
    )


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
        {row["race"]}R{fujin_raijin_marker(row.get("up_signal"), row.get("down_signal"))} {signal_payout_badge(row.get("payout"), row.get("up_signal"), row.get("down_signal"), row.get("_canonical_signal"))} {prediction_quality_warning(row.get("live_display"))}{" <span class=\"result-flash\">払戻速報</span>" if row.get("result_source") == "payout" else ""}
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
      {("直前予測" if row["live"] else (("直前補完（朝スコア）" if (row.get("live_display") or {}).get("stage") == "neutral_morning_fallback" else "直前予測（一部朝スコア補完）") if row.get("live_display") else "直前予測なし"))} {prediction_quality_warning(row.get("live_display"))}
    </div>

    <div>
      {prediction_html(row.get("live_display"), morning_reference_map(row["morning"], row.get("live_display")))}
      {all_scores_html(row.get("live_display"), ("直前予測" if row["live"] else "直前補完（朝スコア）"), morning_reference_map(row["morning"], row.get("live_display")))}
    </div>

    <div class="metrics">
      {evaluation_html(row["live_eval"])}
    </div>

  </div>


  <div class="label simulation-label">最終予測の買い目・100円/点シミュレーション</div>
  {simulation_html(row["formation_prediction"] or row["live"] or row["morning"], row["trifecta"], row["payout"])}
  <div class="label simulation-label">シグナル発動：専用AI24点／非発動：通常AIスコア予測</div>\n  <div class="simulation-meta">シグナル発動時は専用AI上位24点を各100円で照合し、投資・払戻・収支を計算</div>
  {ai_score_result_html(final_ai_prediction(row), row["trifecta"], row["payout"], row["_canonical_signal"]) if row["_canonical_signal"]["signal_key"] or (final_ai_prediction(row) and (final_ai_prediction(row).get("ai_score_prediction") or (final_ai_prediction(row).get("raw") or {}).get("ai_score_prediction"))) else ai_eval_detail_html(row.get("ai_evaluation"))}

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
  --bg:#cddce8;
  --card:#f4f8fb;
  --text:#111827;
  --muted:#667085;
  --line:#c4d4e0;
  --chip:#dfeaf1;
  --blue:#174f7a;
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
.score-delta {{ margin-left:5px; font-weight:900; white-space:nowrap; }}
@media (max-width:600px) {{
  .score-chips {{
    display:grid;
    grid-template-columns:minmax(0,1fr) minmax(0,1fr);
    gap:6px;
  }}
  .score-chip {{
    min-width:0;
    width:100%;
    min-height:54px;
    display:block;
    box-sizing:border-box;
    padding:9px 10px;
    line-height:1.35;
    border-radius:24px;
    font-size:clamp(10.5px,3vw,12px);
    overflow-wrap:anywhere;
  }}
  .score-chip .score-delta {{
    display:inline-block;
    margin-left:4px;
    white-space:nowrap;
  }}
}}
.score-delta.up {{ color:#a33f58; }}
.score-delta.down {{ color:#2f6690; }}
.score-delta.flat {{ color:var(--muted); }}
\n.score-chip {{
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
  display:flex;
  align-items:center;
  gap:2px;
  flex-wrap:wrap;
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

.quality-warning {{
  display:inline-block;
  margin-left:4px;
  color:#9a5b00;
  font-size:11px;
  font-weight:900;
  white-space:nowrap;
}}

.fujin-raijin-stack {{
  display:inline-grid;
  grid-template-rows:auto auto;
  align-items:center;
  justify-items:start;
  gap:0;
  margin-left:5px;
  vertical-align:middle;
  line-height:1;
}}
.signal-row {{
  display:block;
  min-height:13px;
  font-size:12px;
  font-weight:900;
  letter-spacing:-1px;
  white-space:nowrap;
}}
.signal-row.raijin {{
  color:#9a6500;
}}
.signal-row.fujin {{
  color:#176b7a;
}}
.signal-row.empty-signal {{
  visibility:hidden;
}}

.signal-payout-hit {{
  display:inline-block;
  margin-left:5px;
  padding:2px 6px;
  border-radius:999px;
  background:#ecfdf3;
  color:#067647;
  font-size:11px;
  font-weight:900;
  white-space:nowrap;
}}
.signal-payout-miss {{
  display:inline-block;
  margin-left:5px;
  padding:2px 6px;
  border-radius:999px;
  background:#fffaeb;
  color:#b54708;
  font-size:11px;
  font-weight:900;
  white-space:nowrap;
}}

.result-flash {{
  display:inline-block;
  margin-left:4px;
  color:#174f7a;
  font-size:11px;
  font-weight:900;
  white-space:nowrap;
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
.signal-rank-hit {{
  color:#067647;
  background:#ecfdf3;
  border:1px solid #a6f4c5;
  border-radius:6px;
  padding:2px 6px;
  font-weight:900;
}}
.signal-rank-miss {{
  color:var(--text);
  font-weight:750;
}}
.signal-rank-daily {{
  margin:6px 0;
  font-size:13px;
  line-height:1.6;
}}
.signal-rank-daily b {{
  color:var(--blue);
  font-size:18px;
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

  .score-chips {{
    display:grid;
    grid-template-columns:minmax(0,1fr) minmax(0,1fr);
    grid-template-rows:repeat(3,auto);
    grid-auto-flow:column;
    align-items:start;
  }}

  .score-chip {{
    width:100%;
    max-width:100%;
    min-width:0;
    min-height:52px;
    box-sizing:border-box;
    display:flex;
    align-items:center;
    flex-wrap:wrap;
    align-content:center;
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
    --text:#dfeaf1;
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
    最終予測（直前優先） TOP3整合 / 完全一致 / 買い目的中
  </span>

  <strong>
    {percent(final_summary["overlap"])}
    /
    {percent(final_summary["exact"])}
    /
    {percent(final_formation_summary["rate"])}
  </strong>

  <span>
    {final_summary["count"]}R
  </span>

</div>


<div class="summary-box">

  <span>
    AI着順別3艇一致 / AI着順完全一致 / AI買い目的中
  </span>

  <strong>
    {percent(ai_summary["overlap"])}
    /
    {percent(ai_summary["exact"])}
    /
    {percent(ai_summary["bought_hit"])}
  </strong>

  <span>
    {ai_summary["count"]}R（通常AIのみ）
  </span>

</div>

<div class="summary-box">
  <span>風神雷神専用AI24点の購入成績（通常AIとは別会計）</span>
  <strong>
    {signal24_hits}/{signal24_races}R的中 ／ 回収率 {percent(signal24_roi)}
  </strong>
  <div class="signal-rank-daily">
    当日実着の平均AI順位：
    <b>{f"{signal24_mean_actual_rank:.1f}位" if signal24_mean_actual_rank is not None else "—"}</b>
    （{len(signal24_actual_ranks)}R、6艇は120通り・5艇は60通り）
  </div>
  <span>
    購入{signal24_races * 24:,}点 ／ 投資{signal24_invest:,}円 ／
    払戻{signal24_paid:,}円 ／ 損益{signal24_profit:+,}円
    {f" ／ 未評価{signal24_missing}R" if signal24_missing else ""}
    {f" ／ 実着順位未取得{signal24_unranked}R" if signal24_unranked else ""}
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
        formation_predictions,
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
        formation_predictions,
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
# shared-theme-race-compare-refresh-v2

# shared-theme-race-compare-refresh-v3

# race-compare-score-delta-publish-v1

# race-compare-score-delta-publish-v2

# race-compare-mobile-score-column-order-v1
