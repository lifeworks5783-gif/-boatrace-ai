from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import lhafile


JST = timezone(timedelta(hours=9))
DATA_DIR = Path("data")

VENUES = {
    "01": "桐生",
    "02": "戸田",
    "03": "江戸川",
    "04": "平和島",
    "05": "多摩川",
    "06": "浜名湖",
    "07": "蒲郡",
    "08": "常滑",
    "09": "津",
    "10": "三国",
    "11": "びわこ",
    "12": "住之江",
    "13": "尼崎",
    "14": "鳴門",
    "15": "丸亀",
    "16": "児島",
    "17": "宮島",
    "18": "徳山",
    "19": "下関",
    "20": "若松",
    "21": "芦屋",
    "22": "福岡",
    "23": "唐津",
    "24": "大村",
}


STADIUM_BEGIN = re.compile(
    rb"^(\d{2})KBGN\s*$"
)

STADIUM_END = re.compile(
    rb"^(\d{2})KEND\s*$"
)

RACE_HEADER = re.compile(
    r"^\s*(\d{1,2})R(?:\s|$)"
)


VENUE_FIELDS = [
    "date",
    "venue_code",
    "venue_name",
]

RESULT_FIELDS = [
    "date",
    "venue_code",
    "venue_name",
    "race",
    "race_id",
    "trifecta",
    "trifecta_pay",
    "exacta",
    "exacta_pay",
]

BOAT_FIELDS = [
    "date",
    "venue_code",
    "venue_name",
    "race",
    "race_id",
    "boat",
    "course",
    "registration_no",
    "racer_name",
    "finish",
    "st",
    "race_time",
]


# 直近のparse_payloadで除外されたレース
LAST_EXCLUDED_RACES = []


def normalize(text):
    return unicodedata.normalize(
        "NFKC",
        text,
    ).replace(
        "　",
        " ",
    )


def decode(data):
    return data.decode(
        "cp932",
        errors="replace",
    )


def clean_name(text):
    return re.sub(
        r"[\s　]+",
        "",
        text,
    )


def build_url(target_date):
    dt = datetime.strptime(
        target_date,
        "%Y%m%d",
    )

    return (
        "https://www1.mbrace.or.jp/"
        f"od2/K/{dt:%Y%m}/"
        f"k{dt:%y%m%d}.lzh"
    )


def fetch(
    url,
    retries=3,
):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(compatible; "
            "boatrace-ai-data-collector/1.0)"
        )
    }

    last_error = None

    for attempt in range(
        1,
        retries + 1,
    ):
        try:
            request = urllib.request.Request(
                url,
                headers=headers,
            )

            with urllib.request.urlopen(
                request,
                timeout=60,
            ) as response:
                data = response.read()

            if not data:
                raise RuntimeError(
                    "競走成績ファイルが空です"
                )

            return data

        except urllib.error.HTTPError as exc:
            last_error = exc

            if exc.code == 404:
                raise RuntimeError(
                    "競走成績ファイルが"
                    f"見つかりません: {url}"
                ) from exc

        except Exception as exc:
            last_error = exc

        if attempt < retries:
            time.sleep(
                attempt * 2
            )

    raise RuntimeError(
        "競走成績ダウンロード失敗: "
        f"{last_error}"
    )


def extract_lzh(data):
    try:
        archive = lhafile.LhaFile(
            io.BytesIO(
                data
            )
        )

        names = archive.namelist()

        if not names:
            raise RuntimeError(
                "LZH内にファイルがありません"
            )

        parts = []

        for name in sorted(
            names
        ):
            payload = archive.read(
                name
            )

            if payload:
                parts.append(
                    payload
                )

        joined = b"".join(
            parts
        )

        if not joined:
            raise RuntimeError(
                "LZH解凍後データが空です"
            )

        return joined

    except Exception as exc:
        raise RuntimeError(
            f"LZH解凍失敗: {exc}"
        ) from exc


def is_result_row(line):
    if len(line) < 55:
        return False

    return (
        line[6:7] in b"123456"
        and len(
            line[8:12]
        ) == 4
        and line[8:12].isdigit()
    )


def parse_finish(line):
    value = normalize(
        decode(
            line[2:4]
        )
    ).strip().upper()

    if value.isdigit():
        number = int(value)

        if 1 <= number <= 6:
            return str(number)

    return value


def parse_boat(line):
    value = normalize(
        decode(
            line[6:7]
        )
    ).strip()

    if value.isdigit():
        return int(value)

    return None


def parse_course(line):
    value = normalize(
        decode(
            line[43:47]
        )
    ).strip()

    if value.isdigit():
        return int(value)

    return None


def parse_st(line):
    value = (
        normalize(
            decode(
                line[47:55]
            )
        )
        .strip()
        .upper()
        .replace(
            " ",
            "",
        )
    )

    if not value:
        return ""

    match = re.fullmatch(
        r"0\.(\d{2})",
        value,
    )

    if match:
        return (
            f".{match.group(1)}"
        )

    match = re.fullmatch(
        r"\.(\d{2})",
        value,
    )

    if match:
        return value

    match = re.fullmatch(
        r"F(?:0)?\.(\d{2})",
        value,
    )

    if match:
        return (
            f"F.{match.group(1)}"
        )

    match = re.fullmatch(
        r"L(?:0)?\.(\d{2})",
        value,
    )

    if match:
        return (
            f"L.{match.group(1)}"
        )

    if value in {
        "F",
        "L",
    }:
        return value

    return ""


def parse_race_time(line):
    if len(line) <= 55:
        return ""

    value = normalize(
        decode(
            line[55:66]
        )
    ).strip()

    compact = re.sub(
        r"\s+",
        "",
        value,
    )

    if not compact:
        return ""

    # 「. . .」などタイムなし表記は空欄に統一
    if not any(
        char.isdigit()
        for char in compact
    ):
        return ""

    return compact


def parse_result_row(line):
    return {
        "boat": parse_boat(
            line
        ),

        "course": parse_course(
            line
        ),

        "registration_no": normalize(
            decode(
                line[8:12]
            )
        ).strip(),

        "racer_name": clean_name(
            decode(
                line[13:29]
            )
        ),

        "finish": parse_finish(
            line
        ),

        "st": parse_st(
            line
        ),

        "race_time": parse_race_time(
            line
        ),
    }


def payout_from_line(
    text,
    label,
    arity,
):
    flat = normalize(
        text
    )

    combo_pattern = "-".join(
        [
            r"[1-6]"
        ]
        * arity
    )

    match = re.search(
        rf"{re.escape(label)}"
        rf"\s*"
        rf"({combo_pattern})"
        rf"\s*"
        rf"([\d,]+)",
        flat,
    )

    if not match:
        return "", ""

    return (
        match.group(1),

        match.group(2).replace(
            ",",
            "",
        ),
    )


def write_csv(
    path,
    rows,
    fields,
):
    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields,
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    field: row.get(
                        field,
                        "",
                    )
                    for field
                    in fields
                }
            )


def filter_complete_races(
    target_date,
    venues_seen,
    races,
    boats,
):
    global LAST_EXCLUDED_RACES

    boats_by_race = {}

    for row in boats:
        boats_by_race.setdefault(
            row[
                "race_id"
            ],
            [],
        ).append(
            row
        )

    valid_race_ids = set()
    excluded = []

    for key in sorted(
        races
    ):
        race = races[
            key
        ]

        race_id = race[
            "race_id"
        ]

        race_boats = (
            boats_by_race.get(
                race_id,
                [],
            )
        )

        boat_numbers = {
            row.get(
                "boat"
            )
            for row
            in race_boats
            if row.get(
                "boat"
            )
            is not None
        }

        complete = (
            len(
                race_boats
            ) == 6
            and boat_numbers
            == {
                1,
                2,
                3,
                4,
                5,
                6,
            }
        )

        if complete:
            valid_race_ids.add(
                race_id
            )

            continue

        if len(
            race_boats
        ) == 0:
            reason = (
                "艇別結果なし"
            )

        elif len(
            boat_numbers
        ) != len(
            race_boats
        ):
            reason = (
                "艇番重複"
            )

        else:
            reason = (
                "6艇未完了"
            )

        excluded.append(
            {
                "date": target_date,

                "venue_code": race[
                    "venue_code"
                ],

                "venue_name": race[
                    "venue_name"
                ],

                "race": race[
                    "race"
                ],

                "race_id": race_id,

                "boat_rows": len(
                    race_boats
                ),

                "boat_numbers": sorted(
                    boat_numbers
                ),

                "reason": reason,
            }
        )

    complete_races = [
        races[
            key
        ]
        for key
        in sorted(
            races
        )
        if races[
            key
        ][
            "race_id"
        ]
        in valid_race_ids
    ]

    complete_boats = [
        row
        for row
        in boats
        if row[
            "race_id"
        ]
        in valid_race_ids
    ]

    complete_boats.sort(
        key=lambda row: (
            row[
                "venue_code"
            ],

            int(
                row[
                    "race"
                ]
            ),

            int(
                row[
                    "boat"
                ]
            ),
        )
    )

    valid_venue_codes = {
        row[
            "venue_code"
        ]
        for row
        in complete_races
    }

    complete_venues = [
        {
            "date": target_date,

            "venue_code": code,

            "venue_name": (
                venues_seen.get(
                    code,
                    VENUES.get(
                        code,
                        "",
                    ),
                )
            ),
        }
        for code
        in sorted(
            valid_venue_codes
        )
    ]

    LAST_EXCLUDED_RACES = (
        excluded
    )

    return (
        complete_venues,
        complete_races,
        complete_boats,
    )


def get_last_excluded_races():
    return list(
        LAST_EXCLUDED_RACES
    )


def parse_payload(
    payload,
    target_date,
):
    venues_seen = {}
    races = {}
    boats = []

    current_venue = None
    current_race = None

    for raw in payload.splitlines():

        begin = (
            STADIUM_BEGIN.match(
                raw
            )
        )

        if begin:
            current_venue = (
                begin
                .group(1)
                .decode(
                    "ascii"
                )
            )

            venues_seen[
                current_venue
            ] = VENUES.get(
                current_venue,
                "",
            )

            current_race = None

            continue

        if STADIUM_END.match(
            raw
        ):
            current_venue = None
            current_race = None

            continue

        if current_venue is None:
            continue

        text = normalize(
            decode(
                raw
            )
        )

        header = (
            RACE_HEADER.match(
                text
            )
        )

        if header:
            current_race = int(
                header.group(1)
            )

            race_id = (
                f"{target_date}-"
                f"{current_venue}-"
                f"{current_race:02d}"
            )

            races[
                (
                    current_venue,
                    current_race,
                )
            ] = {
                "date": target_date,

                "venue_code": current_venue,

                "venue_name": VENUES.get(
                    current_venue,
                    "",
                ),

                "race": current_race,

                "race_id": race_id,

                "trifecta": "",

                "trifecta_pay": "",

                "exacta": "",

                "exacta_pay": "",
            }

            continue

        if current_race is None:
            continue

        race = races.get(
            (
                current_venue,
                current_race,
            )
        )

        if race is None:
            continue

        if is_result_row(
            raw
        ):
            parsed = (
                parse_result_row(
                    raw
                )
            )

            if parsed[
                "boat"
            ] is None:
                continue

            boats.append(
                {
                    "date": target_date,

                    "venue_code": current_venue,

                    "venue_name": VENUES.get(
                        current_venue,
                        "",
                    ),

                    "race": current_race,

                    "race_id": race[
                        "race_id"
                    ],

                    **parsed,
                }
            )

            continue

        (
            trifecta,
            trifecta_pay,
        ) = payout_from_line(
            text,
            "3連単",
            3,
        )

        if trifecta:
            race[
                "trifecta"
            ] = trifecta

            race[
                "trifecta_pay"
            ] = trifecta_pay

            continue

        (
            exacta,
            exacta_pay,
        ) = payout_from_line(
            text,
            "2連単",
            2,
        )

        if exacta:
            race[
                "exacta"
            ] = exacta

            race[
                "exacta_pay"
            ] = exacta_pay

    return filter_complete_races(
        target_date,
        venues_seen,
        races,
        boats,
    )


def basic_validate(
    venues,
    races,
    boats,
):
    if not venues:
        raise RuntimeError(
            "開催場が0件です"
        )

    if not races:
        raise RuntimeError(
            "学習可能なレースが0件です"
        )

    if not boats:
        raise RuntimeError(
            "艇別結果が0件です"
        )

    race_ids = [
        row[
            "race_id"
        ]
        for row
        in races
    ]

    if len(
        race_ids
    ) != len(
        set(
            race_ids
        )
    ):
        raise RuntimeError(
            "race_id重複を検出しました"
        )

    boat_keys = [
        (
            row[
                "race_id"
            ],

            row[
                "boat"
            ],
        )
        for row
        in boats
    ]

    if len(
        boat_keys
    ) != len(
        set(
            boat_keys
        )
    ):
        raise RuntimeError(
            "race_id×boat重複を検出しました"
        )

    counts = {}
    boat_sets = {}

    for row in boats:

        race_id = row[
            "race_id"
        ]

        counts[
            race_id
        ] = (
            counts.get(
                race_id,
                0,
            )
            + 1
        )

        boat_sets.setdefault(
            race_id,
            set(),
        ).add(
            row[
                "boat"
            ]
        )

    bad = []

    for race_id in race_ids:

        count = counts.get(
            race_id,
            0,
        )

        boat_set = boat_sets.get(
            race_id,
            set(),
        )

        if (
            count != 6
            or boat_set
            != {
                1,
                2,
                3,
                4,
                5,
                6,
            }
        ):
            bad.append(
                (
                    race_id,
                    count,
                    sorted(
                        boat_set
                    ),
                )
            )

    if bad:
        raise RuntimeError(
            "6艇揃っていないレースが"
            f"{len(bad)}件残っています: "
            f"{bad[:5]}"
        )

    if set(
        race_ids
    ) != set(
        counts
    ):
        raise RuntimeError(
            "レース結果と艇別結果の"
            "race_id集合が一致しません"
        )

    if LAST_EXCLUDED_RACES:

        print("")
        print(
            "========================================"
        )

        print(
            "学習対象外レース"
        )

        print(
            "除外件数: "
            f"{len(LAST_EXCLUDED_RACES)}"
        )

        for item in (
            LAST_EXCLUDED_RACES[:20]
        ):
            print(
                f"- {item['race_id']} "
                f"{item['reason']} "
                f"({item['boat_rows']}艇)"
            )

        if len(
            LAST_EXCLUDED_RACES
        ) > 20:
            print(
                "...以降省略"
            )

        print(
            "========================================"
        )


def write_excluded_json(
    target_date,
):
    path = (
        DATA_DIR
        / (
            f"excluded_races_"
            f"{target_date}.json"
        )
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "target_date": target_date,

        "excluded_count": len(
            LAST_EXCLUDED_RACES
        ),

        "excluded_races": (
            LAST_EXCLUDED_RACES
        ),

        "rule": (
            "6艇分の艇別結果が揃わないレースは"
            "30日・90日集計と学習対象から除外。"
            "同日の正常レースは保存する。"
        ),

        "created_at": datetime.now(
            JST
        ).isoformat(),
    }

    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return path


def main():

    parser = argparse.ArgumentParser(
        description=(
            "BOAT RACE公式Kファイルから"
            "前日全場結果を高速収集"
        )
    )

    parser.add_argument(
        "--date",
        default=None,
        help=(
            "対象日 YYYYMMDD。"
            "省略時は日本時間の前日"
        ),
    )

    args = parser.parse_args()

    if args.date:
        target_date = (
            args.date
        )

    else:
        target_date = (
            datetime.now(
                JST
            )
            - timedelta(
                days=1
            )
        ).strftime(
            "%Y%m%d"
        )

    try:
        datetime.strptime(
            target_date,
            "%Y%m%d",
        )

    except ValueError:

        print(
            "ERROR: "
            "日付はYYYYMMDD形式で指定してください",
            file=sys.stderr,
        )

        return 1

    url = build_url(
        target_date
    )

    print(
        "========================================"
    )

    print(
        "前日全場結果・軽量収集"
    )

    print(
        f"対象日: {target_date}"
    )

    print(
        f"取得元: {url}"
    )

    print(
        "========================================"
    )

    try:
        archive_bytes = fetch(
            url
        )

        payload = extract_lzh(
            archive_bytes
        )

        (
            venues,
            races,
            boats,
        ) = parse_payload(
            payload,
            target_date,
        )

        basic_validate(
            venues,
            races,
            boats,
        )

        DATA_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        write_csv(
            DATA_DIR
            / (
                f"venues_"
                f"{target_date}.csv"
            ),
            venues,
            VENUE_FIELDS,
        )

        write_csv(
            DATA_DIR
            / (
                f"results_"
                f"{target_date}"
                f"_all.csv"
            ),
            races,
            RESULT_FIELDS,
        )

        write_csv(
            DATA_DIR
            / (
                f"boat_results_"
                f"{target_date}"
                f"_all.csv"
            ),
            boats,
            BOAT_FIELDS,
        )

        excluded_path = (
            write_excluded_json(
                target_date
            )
        )

        print("")
        print(
            "========================================"
        )

        print(
            "軽量収集結果"
        )

        print(
            f"開催場数: {len(venues)}"
        )

        print(
            "学習可能レース数: "
            f"{len(races)}"
        )

        print(
            f"艇数: {len(boats)}"
        )

        print(
            "除外レース数: "
            f"{len(LAST_EXCLUDED_RACES)}"
        )

        print(
            f"除外ログ: {excluded_path}"
        )

        print(
            "基本検証: PASS"
        )

        print(
            "========================================"
        )

        print(
            "軽量版収集 PASS"
        )

        return 0

    except Exception as exc:

        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    sys.exit(
        main()
    )