from __future__ import annotations

import argparse
import csv
import io
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


VENUE_FIELDS = [
    "date",
    "venue_code",
    "venue_name",
]


def normalize(
    text: str,
) -> str:

    return (
        unicodedata.normalize(
            "NFKC",
            text,
        )
        .replace(
            "　",
            " ",
        )
    )


def decode(
    data: bytes,
) -> str:

    return data.decode(
        "cp932",
        errors="replace",
    )


def clean_name(
    text: str,
) -> str:

    return re.sub(
        r"[\s　]+",
        "",
        text,
    )


def build_url(
    target_date: str,
) -> str:

    dt = datetime.strptime(
        target_date,
        "%Y%m%d",
    )

    return (
        "https://www1.mbrace.or.jp/"
        "od2/K/"
        f"{dt:%Y%m}/"
        f"k{dt:%y%m%d}.lzh"
    )


def fetch(
    url: str,
    retries: int = 3,
) -> bytes:

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
            request = (
                urllib.request.Request(
                    url,
                    headers=headers,
                )
            )

            with urllib.request.urlopen(
                request,
                timeout=60,
            ) as response:

                data = (
                    response.read()
                )

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


def extract_lzh(
    data: bytes,
) -> bytes:

    try:
        archive = (
            lhafile.LhaFile(
                io.BytesIO(
                    data
                )
            )
        )

        names = (
            archive.namelist()
        )

        if not names:
            raise RuntimeError(
                "LZH内にファイルがありません"
            )

        parts = []

        for name in sorted(
            names
        ):
            payload = (
                archive.read(
                    name
                )
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


def is_result_row(
    line: bytes,
) -> bool:

    if len(line) < 55:
        return False

    lane = (
        line[6:7]
    )

    registration = (
        line[8:12]
    )

    return (
        lane
        in b"123456"
        and len(
            registration
        ) == 4
        and registration.isdigit()
    )


def parse_finish(
    line: bytes,
) -> str:

    return (
        normalize(
            decode(
                line[2:4]
            )
        )
        .strip()
    )


def parse_boat(
    line: bytes,
):

    value = (
        normalize(
            decode(
                line[6:7]
            )
        )
        .strip()
    )

    if value.isdigit():
        return int(
            value
        )

    return None


def parse_registration_no(
    line: bytes,
) -> str:

    return (
        normalize(
            decode(
                line[8:12]
            )
        )
        .strip()
    )


def parse_course(
    line: bytes,
):

    value = (
        normalize(
            decode(
                line[43:47]
            )
        )
        .strip()
    )

    if value.isdigit():
        return int(
            value
        )

    return None


def parse_st(
    line: bytes,
) -> str:

    return (
        normalize(
            decode(
                line[47:55]
            )
        )
        .strip()
    )


def parse_race_time(
    line: bytes,
) -> str:

    if len(line) <= 55:
        return ""

    return (
        normalize(
            decode(
                line[55:66]
            )
        )
        .strip()
    )


def parse_result_row(
    line: bytes,
) -> dict:

    return {
        "boat": (
            parse_boat(
                line
            )
        ),

        "course": (
            parse_course(
                line
            )
        ),

        "registration_no": (
            parse_registration_no(
                line
            )
        ),

        "racer_name": (
            clean_name(
                decode(
                    line[13:29]
                )
            )
        ),

        "finish": (
            parse_finish(
                line
            )
        ),

        "st": (
            parse_st(
                line
            )
        ),

        "race_time": (
            parse_race_time(
                line
            )
        ),
    }


def payout_from_line(
    text: str,
    label: str,
    arity: int,
):

    flat = (
        normalize(
            text
        )
    )

    if label not in flat:
        return "", ""

    combo_pattern = "-".join(
        [
            r"[1-6]"
        ]
        * arity
    )

    pattern = (
        rf"{re.escape(label)}"
        rf"\s*"
        rf"({combo_pattern})"
        rf"\s*"
        rf"([\d,]+)"
    )

    match = re.search(
        pattern,
        flat,
    )

    if not match:
        return "", ""

    combination = (
        match.group(1)
    )

    payout = (
        match.group(2)
        .replace(
            ",",
            "",
        )
    )

    return (
        combination,
        payout,
    )


def write_csv(
    path: Path,
    rows: list[dict],
    fields: list[str],
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as f:

        writer = (
            csv.DictWriter(
                f,
                fieldnames=fields,
            )
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


def parse_payload(
    payload: bytes,
    target_date: str,
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

        key = (
            current_venue,
            current_race,
        )

        race = (
            races.get(
                key
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

            boat = (
                parsed[
                    "boat"
                ]
            )

            if boat is None:
                continue

            boats.append(
                {
                    "date": (
                        target_date
                    ),

                    "venue_code": (
                        current_venue
                    ),

                    "venue_name": (
                        VENUES.get(
                            current_venue,
                            "",
                        )
                    ),

                    "race": (
                        current_race
                    ),

                    "race_id": (
                        race[
                            "race_id"
                        ]
                    ),

                    **parsed,
                }
            )

            continue

        trifecta, trifecta_pay = (
            payout_from_line(
                text,
                "3連単",
                3,
            )
        )

        if trifecta:
            race[
                "trifecta"
            ] = trifecta

            race[
                "trifecta_pay"
            ] = trifecta_pay

            continue

        exacta, exacta_pay = (
            payout_from_line(
                text,
                "2連単",
                2,
            )
        )

        if exacta:
            race[
                "exacta"
            ] = exacta

            race[
                "exacta_pay"
            ] = exacta_pay


    venue_rows = [
        {
            "date": (
                target_date
            ),

            "venue_code": (
                code
            ),

            "venue_name": (
                venues_seen[
                    code
                ]
            ),
        }
        for code
        in sorted(
            venues_seen
        )
    ]


    race_rows = [
        races[
            key
        ]
        for key
        in sorted(
            races
        )
    ]


    boats.sort(
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


    return (
        venue_rows,
        race_rows,
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
            "レースが0件です"
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

    for row in boats:
        race_id = (
            row[
                "race_id"
            ]
        )

        counts[
            race_id
        ] = (
            counts.get(
                race_id,
                0,
            )
            + 1
        )


    bad = {
        race_id: count
        for race_id, count
        in counts.items()
        if count != 6
    }


    if bad:
        sample = ", ".join(
            f"{race_id}:{count}"
            for race_id, count
            in list(
                bad.items()
            )[:5]
        )

        raise RuntimeError(
            "6艇揃っていないレースがあります: "
            f"{len(bad)}件 "
            f"({sample})"
        )


    missing = (
        set(
            race_ids
        )
        - set(
            counts
        )
    )


    if missing:
        raise RuntimeError(
            "艇別結果がないレースがあります: "
            f"{len(missing)}件"
        )


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


    args = (
        parser.parse_args()
    )


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
            "ERROR: 日付はYYYYMMDD形式で指定してください",
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
        archive_bytes = (
            fetch(
                url
            )
        )

        payload = (
            extract_lzh(
                archive_bytes
            )
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


        venues_path = (
            DATA_DIR
            / (
                f"venues_"
                f"{target_date}.csv"
            )
        )


        results_path = (
            DATA_DIR
            / (
                f"results_"
                f"{target_date}"
                f"_all.csv"
            )
        )


        boats_path = (
            DATA_DIR
            / (
                f"boat_results_"
                f"{target_date}"
                f"_all.csv"
            )
        )


        write_csv(
            venues_path,
            venues,
            VENUE_FIELDS,
        )


        write_csv(
            results_path,
            races,
            RESULT_FIELDS,
        )


        write_csv(
            boats_path,
            boats,
            BOAT_FIELDS,
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
            f"レース数: {len(races)}"
        )

        print(
            f"艇数: {len(boats)}"
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