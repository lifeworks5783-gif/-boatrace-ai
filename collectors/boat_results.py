from urllib.request import Request, urlopen
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import csv
import re
import time


VENUE_CODE = "02"

JST = ZoneInfo("Asia/Tokyo")

TARGET_DATE = (
    datetime.now(JST).date()
    - timedelta(days=1)
)

DATE = TARGET_DATE.strftime("%Y%m%d")

RACE_NUMBERS = range(1, 13)


class DetailParser(HTMLParser):
    def __init__(self):
        super().__init__()

        self.rows = []
        self.current_row = []
        self.current_cell = ""
        self.in_row = False
        self.in_cell = False
        self.tokens = []

    def handle_starttag(
        self,
        tag,
        attrs
    ):

        if tag == "tr":
            self.in_row = True
            self.current_row = []

        elif (
            tag in ("td", "th")
            and self.in_row
        ):
            self.in_cell = True
            self.current_cell = ""

    def handle_data(
        self,
        data
    ):

        text = " ".join(
            data.split()
        )

        if text:
            self.tokens.append(
                text
            )

        if self.in_cell:
            self.current_cell += data

    def handle_endtag(
        self,
        tag
    ):

        if (
            tag in ("td", "th")
            and self.in_cell
        ):

            text = " ".join(
                self.current_cell.split()
            )

            self.current_row.append(
                text
            )

            self.in_cell = False

        elif (
            tag == "tr"
            and self.in_row
        ):

            if self.current_row:
                self.rows.append(
                    self.current_row
                )

            self.in_row = False


def fetch_race(
    race_no
):

    url = (
        "https://www.boatrace.jp/owpc/pc/race/"
        f"raceresult?hd={DATE}"
        f"&jcd={VENUE_CODE}"
        f"&rno={race_no}"
    )

    request = Request(
        url,
        headers={
            "User-Agent":
                "Mozilla/5.0"
        }
    )

    with urlopen(
        request,
        timeout=20
    ) as response:

        html = (
            response
            .read()
            .decode(
                "utf-8",
                errors="replace"
            )
        )

    parser = DetailParser()

    parser.feed(
        html
    )

    return parser


def extract_racers(
    parser
):

    racers = {}

    rank_translate = (
        str.maketrans(
            "１２３４５６",
            "123456"
        )
    )

    for row in parser.rows:

        if len(row) < 3:
            continue

        finish = (
            row[0]
            .translate(
                rank_translate
            )
            .strip()
        )

        boat = (
            row[1]
            .strip()
        )

        if (
            boat in [
                "1", "2", "3",
                "4", "5", "6"
            ]
            and re.match(
                r"^\d{4}",
                row[2]
            )
        ):

            racer_text = (
                " ".join(
                    row[2].split()
                )
            )

            match = re.match(
                r"^(\d{4})\s+(.+)$",
                racer_text
            )

            if not match:
                continue

            registration_no = (
                match.group(1)
            )

            racer_name = (
                match.group(2)
            )

            race_time = ""

            if len(row) >= 4:
                race_time = (
                    row[3]
                    .strip()
                )

            racers[boat] = {
                "finish":
                    finish,
                "boat":
                    boat,
                "registration_no":
                    registration_no,
                "racer_name":
                    racer_name,
                "race_time":
                    race_time,
            }

    return racers


def extract_start_info(
    parser
):

    start_info = {}

    try:

        start_index = (
            parser.tokens.index(
                "スタート情報"
            )
        )

        end_index = (
            parser.tokens.index(
                "勝式",
                start_index
            )
        )

    except ValueError:

        return start_info


    start_tokens = (
        parser.tokens[
            start_index + 1:
            end_index
        ]
    )

    course = 0
    i = 0

    while i < len(
        start_tokens
    ):

        token = (
            start_tokens[i]
        )

        if token in [
            "1", "2", "3",
            "4", "5", "6"
        ]:

            boat = token

            course += 1

            st = None

            j = i + 1

            while j < len(
                start_tokens
            ):

                candidate = (
                    start_tokens[j]
                )

                if candidate in [
                    "1", "2", "3",
                    "4", "5", "6"
                ]:
                    break

                st_match = re.search(
                    r"(?:F|L)?\.?\d{2}",
                    candidate
                )

                if st_match:

                    st = (
                        st_match
                        .group(0)
                    )

                    break

                j += 1

            start_info[boat] = {
                "course":
                    course,
                "st":
                    st,
            }

        i += 1

    return start_info


# =========================
# 対象日表示
# =========================

print(
    "日本時間:",
    datetime.now(JST)
)

print(
    "自動取得対象日:",
    DATE
)

print(
    "対象会場コード:",
    VENUE_CODE
)


# =========================
# 1Rを先に確認
# =========================

first_parser = fetch_race(1)

first_racers = extract_racers(
    first_parser
)

if len(first_racers) == 0:

    print(
        "対象日は戸田非開催、"
        "または結果未掲載です。"
    )

    print(
        "詳細CSVは作成しません。"
    )

    raise SystemExit(0)


if len(first_racers) != 6:

    raise RuntimeError(
        "1Rの選手数が異常です: "
        f"{len(first_racers)}艇"
    )


# =========================
# 1R〜12R取得
# =========================

all_results = []

for race_no in RACE_NUMBERS:

    print(
        f"{race_no}R 取得開始"
    )

    if race_no == 1:

        parser = first_parser

        racers = first_racers

    else:

        parser = fetch_race(
            race_no
        )

        racers = (
            extract_racers(
                parser
            )
        )

    start_info = (
        extract_start_info(
            parser
        )
    )

    if len(racers) != 6:

        raise RuntimeError(
            f"{race_no}Rの選手数が"
            f"異常です: "
            f"{len(racers)}艇"
        )

    for boat in [
        "1", "2", "3",
        "4", "5", "6"
    ]:

        racer = racers.get(
            boat
        )

        start = (
            start_info.get(
                boat,
                {}
            )
        )

        if racer is None:
            continue

        all_results.append({
            "date":
                DATE,
            "venue_code":
                VENUE_CODE,
            "race":
                race_no,
            "boat":
                int(boat),
            "course":
                start.get(
                    "course"
                ),
            "registration_no":
                racer[
                    "registration_no"
                ],
            "racer_name":
                racer[
                    "racer_name"
                ],
            "finish":
                racer[
                    "finish"
                ],
            "st":
                start.get(
                    "st"
                ),
            "race_time":
                racer[
                    "race_time"
                ],
        })

    print(
        f"{race_no}R 取得完了"
    )

    if race_no != 12:
        time.sleep(1)


# =========================
# 件数チェック
# =========================

if len(all_results) != 72:

    raise RuntimeError(
        "取得艇数が異常です: "
        f"{len(all_results)}艇"
    )


# =========================
# データ品質チェック
# =========================

for race_no in RACE_NUMBERS:

    race_rows = [
        row
        for row in all_results
        if row["race"]
        == race_no
    ]

    if len(race_rows) != 6:

        raise RuntimeError(
            f"{race_no}Rが"
            f"{len(race_rows)}艇です"
        )

    boats = sorted(
        row["boat"]
        for row in race_rows
    )

    if boats != [
        1, 2, 3, 4, 5, 6
    ]:

        raise RuntimeError(
            f"{race_no}Rの艇番に"
            "異常があります"
        )


# =========================
# CSV保存
# =========================

output_dir = Path(
    "data"
)

output_dir.mkdir(
    exist_ok=True
)

output_file = (
    output_dir
    / (
        f"boat_results_"
        f"{DATE}_"
        f"{VENUE_CODE}.csv"
    )
)

with output_file.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "date",
            "venue_code",
            "race",
            "boat",
            "course",
            "registration_no",
            "racer_name",
            "finish",
            "st",
            "race_time",
        ]
    )

    writer.writeheader()

    writer.writerows(
        all_results
    )


# =========================
# 最終ログ
# =========================

print(
    "===================="
)

print(
    "全レース取得成功"
)

print(
    "対象日:",
    DATE
)

print(
    "取得レース数: 12"
)

print(
    "取得艇数:",
    len(all_results)
)

print(
    "CSV保存先:",
    output_file
)

print(
    "===================="
)