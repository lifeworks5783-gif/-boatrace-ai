from urllib.request import Request, urlopen
from urllib.parse import urlparse, parse_qs
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import csv
import re
import time


# =====================================
# 基本設定
# =====================================

JST = ZoneInfo("Asia/Tokyo")

TARGET_DATE = (
    datetime.now(JST).date()
    - timedelta(days=1)
)

DATE = TARGET_DATE.strftime("%Y%m%d")

REQUEST_INTERVAL = 1.5
RETRY_COUNT = 3


VENUE_NAMES = {
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


# =====================================
# HTML Parser
# =====================================

class LinkParser(HTMLParser):

    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):

        if tag != "a":
            return

        href = dict(attrs).get("href")

        if href:
            self.links.append(href)


class TableParser(HTMLParser):

    def __init__(self):
        super().__init__()

        self.rows = []
        self.current_row = []
        self.current_cell = ""

        self.in_row = False
        self.in_cell = False

    def handle_starttag(self, tag, attrs):

        if tag == "tr":

            self.in_row = True
            self.current_row = []

        elif (
            tag in ("td", "th")
            and self.in_row
        ):

            self.in_cell = True
            self.current_cell = ""

    def handle_data(self, data):

        if self.in_cell:
            self.current_cell += data

    def handle_endtag(self, tag):

        if (
            tag in ("td", "th")
            and self.in_cell
        ):

            text = " ".join(
                self.current_cell.split()
            )

            self.current_row.append(text)

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


class DetailParser(HTMLParser):

    def __init__(self):
        super().__init__()

        self.rows = []
        self.tokens = []

        self.current_row = []
        self.current_cell = ""

        self.in_row = False
        self.in_cell = False

    def handle_starttag(self, tag, attrs):

        if tag == "tr":

            self.in_row = True
            self.current_row = []

        elif (
            tag in ("td", "th")
            and self.in_row
        ):

            self.in_cell = True
            self.current_cell = ""

    def handle_data(self, data):

        text = " ".join(
            data.split()
        )

        if text:
            self.tokens.append(text)

        if self.in_cell:
            self.current_cell += data

    def handle_endtag(self, tag):

        if (
            tag in ("td", "th")
            and self.in_cell
        ):

            text = " ".join(
                self.current_cell.split()
            )

            self.current_row.append(text)

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


# =====================================
# 通信
# =====================================

def fetch_html(url):

    last_error = None

    for attempt in range(
        1,
        RETRY_COUNT + 1
    ):

        try:

            request = Request(
                url,
                headers={
                    "User-Agent":
                        "Mozilla/5.0"
                }
            )

            with urlopen(
                request,
                timeout=30
            ) as response:

                html = (
                    response
                    .read()
                    .decode(
                        "utf-8",
                        errors="replace"
                    )
                )

            return html

        except Exception as error:

            last_error = error

            print(
                f"通信失敗 "
                f"{attempt}/{RETRY_COUNT}:",
                error
            )

            time.sleep(
                attempt * 3
            )

    raise last_error


# =====================================
# 円 → 数値
# =====================================

def yen_to_int(text):

    return int(
        text
        .replace("¥", "")
        .replace("￥", "")
        .replace(",", "")
        .replace("円", "")
        .strip()
    )


# =====================================
# 開催場自動検出
# =====================================

def detect_venues():

    url = (
        "https://www.boatrace.jp/"
        "owpc/pc/race/index"
        f"?hd={DATE}"
    )

    html = fetch_html(url)

    parser = LinkParser()

    parser.feed(html)

    venue_codes = set()

    for href in parser.links:

        if "resultlist" not in href:
            continue

        parsed = urlparse(href)

        query = parse_qs(
            parsed.query
        )

        hd = query.get(
            "hd",
            [""]
        )[0]

        jcd = query.get(
            "jcd",
            [""]
        )[0]

        if (
            hd == DATE
            and jcd in VENUE_NAMES
        ):

            venue_codes.add(jcd)

    return sorted(
        venue_codes,
        key=int
    )


# =====================================
# 結果一覧取得
# =====================================

def fetch_result_list(
    venue_code
):

    url = (
        "https://www.boatrace.jp/"
        "owpc/pc/race/"
        "resultlist"
        f"?hd={DATE}"
        f"&jcd={venue_code}"
    )

    html = fetch_html(url)

    parser = TableParser()

    parser.feed(html)

    results = []

    for row in parser.rows:

        if not row:
            continue

        race_text = (
            row[0]
            .replace(" ", "")
        )

        if (
            re.fullmatch(
                r"\d{1,2}R",
                race_text
            )
            and len(row) >= 5
            and any(
                "¥" in cell
                or "￥" in cell
                for cell in row
            )
        ):

            race_no = int(
                race_text.replace(
                    "R",
                    ""
                )
            )

            race_id = (
                f"{DATE}_"
                f"{venue_code}_"
                f"{race_no:02d}"
            )

            results.append({
                "date":
                    DATE,
                "venue_code":
                    venue_code,
                "venue_name":
                    VENUE_NAMES[
                        venue_code
                    ],
                "race":
                    race_no,
                "race_id":
                    race_id,
                "trifecta":
                    row[1]
                    .replace(
                        " ",
                        ""
                    ),
                "trifecta_pay":
                    yen_to_int(
                        row[2]
                    ),
                "exacta":
                    row[3]
                    .replace(
                        " ",
                        ""
                    ),
                "exacta_pay":
                    yen_to_int(
                        row[4]
                    ),
            })

    return results


# =====================================
# 1レース詳細取得
# =====================================

def fetch_race_detail(
    venue_code,
    race_no
):

    url = (
        "https://www.boatrace.jp/"
        "owpc/pc/race/"
        "raceresult"
        f"?hd={DATE}"
        f"&jcd={venue_code}"
        f"&rno={race_no}"
    )

    html = fetch_html(url)

    parser = DetailParser()

    parser.feed(html)

    return parser


# =====================================
# 選手・着順抽出
# =====================================

def extract_racers(parser):

    racers = {}

    rank_translate = str.maketrans(
        "１２３４５６",
        "123456"
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

            racer_text = " ".join(
                row[2].split()
            )

            match = re.match(
                r"^(\d{4})\s+(.+)$",
                racer_text
            )

            if not match:
                continue

            race_time = ""

            if len(row) >= 4:

                race_time = (
                    row[3]
                    .strip()
                )

            racers[boat] = {
                "finish":
                    finish,
                "registration_no":
                    match.group(1),
                "racer_name":
                    match.group(2),
                "race_time":
                    race_time,
            }

    return racers


# =====================================
# ST・進入コース抽出
# =====================================

def extract_start_info(parser):

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


    tokens = (
        parser.tokens[
            start_index + 1:
            end_index
        ]
    )

    course = 0
    i = 0

    while i < len(tokens):

        token = tokens[i]

        if token in [
            "1", "2", "3",
            "4", "5", "6"
        ]:

            boat = token

            course += 1

            st = None

            j = i + 1

            while j < len(tokens):

                candidate = (
                    tokens[j]
                )

                if candidate in [
                    "1", "2", "3",
                    "4", "5", "6"
                ]:

                    break

                match = re.search(
                    r"(?:F|L)?\.?\d{2}",
                    candidate
                )

                if match:

                    st = match.group(0)

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


# =====================================
# 開始
# =====================================

print(
    "日本時間:",
    datetime.now(JST)
)

print(
    "自動取得対象日:",
    DATE
)

print(
    "開催場を検出します"
)


venue_codes = detect_venues()


if not venue_codes:

    raise RuntimeError(
        "開催場を検出できませんでした"
    )


print(
    "開催場数:",
    len(venue_codes)
)

for venue_code in venue_codes:

    print(
        venue_code,
        VENUE_NAMES[
            venue_code
        ]
    )


# =====================================
# 全場収集
# =====================================

all_race_results = []

all_boat_results = []


for venue_index, venue_code in enumerate(
    venue_codes,
    start=1
):

    venue_name = (
        VENUE_NAMES[
            venue_code
        ]
    )

    print(
        "===================="
    )

    print(
        f"[{venue_index}/"
        f"{len(venue_codes)}]"
    )

    print(
        venue_code,
        venue_name,
        "取得開始"
    )


    race_results = (
        fetch_result_list(
            venue_code
        )
    )


    if not race_results:

        print(
            "結果を取得できないため"
            "スキップ"
        )

        continue


    all_race_results.extend(
        race_results
    )


    print(
        "結果取得レース数:",
        len(race_results)
    )


    for result in race_results:

        race_no = (
            result["race"]
        )

        race_id = (
            result["race_id"]
        )

        print(
            venue_name,
            f"{race_no}R",
            "詳細取得"
        )


        parser = (
            fetch_race_detail(
                venue_code,
                race_no
            )
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
                f"{venue_name}"
                f"{race_no}R "
                f"選手数異常: "
                f"{len(racers)}艇"
            )


        for boat in [
            "1", "2", "3",
            "4", "5", "6"
        ]:

            racer = (
                racers.get(
                    boat
                )
            )

            start = (
                start_info.get(
                    boat,
                    {}
                )
            )


            if racer is None:

                raise RuntimeError(
                    f"{venue_name}"
                    f"{race_no}R "
                    f"{boat}号艇なし"
                )


            all_boat_results.append({
                "date":
                    DATE,
                "venue_code":
                    venue_code,
                "venue_name":
                    venue_name,
                "race":
                    race_no,
                "race_id":
                    race_id,
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


        time.sleep(
            REQUEST_INTERVAL
        )


    print(
        venue_code,
        venue_name,
        "取得完了"
    )

    time.sleep(2)


# =====================================
# 品質チェック
# =====================================

race_ids = {
    row["race_id"]
    for row in all_race_results
}


for race_id in race_ids:

    rows = [
        row
        for row in all_boat_results
        if row["race_id"]
        == race_id
    ]

    if len(rows) != 6:

        raise RuntimeError(
            f"{race_id}: "
            f"{len(rows)}艇"
        )


# =====================================
# CSV保存
# =====================================

output_dir = Path("data")

output_dir.mkdir(
    exist_ok=True
)


venues_file = (
    output_dir
    / f"venues_{DATE}.csv"
)


race_file = (
    output_dir
    / (
        f"results_"
        f"{DATE}_all.csv"
    )
)


boat_file = (
    output_dir
    / (
        f"boat_results_"
        f"{DATE}_all.csv"
    )
)


with venues_file.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "date",
            "venue_code",
            "venue_name",
        ]
    )

    writer.writeheader()

    for code in venue_codes:

        writer.writerow({
            "date":
                DATE,
            "venue_code":
                code,
            "venue_name":
                VENUE_NAMES[code],
        })


with race_file.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
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
    )

    writer.writeheader()

    writer.writerows(
        all_race_results
    )


with boat_file.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
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
    )

    writer.writeheader()

    writer.writerows(
        all_boat_results
    )


# =====================================
# 最終ログ
# =====================================

print(
    "===================="
)

print(
    "前日全場収集 完了"
)

print(
    "対象日:",
    DATE
)

print(
    "開催場数:",
    len(venue_codes)
)

print(
    "取得レース数:",
    len(all_race_results)
)

print(
    "取得艇データ数:",
    len(all_boat_results)
)

print(
    "開催場CSV:",
    venues_file
)

print(
    "レース結果CSV:",
    race_file
)

print(
    "艇別結果CSV:",
    boat_file
)

print(
    "===================="
)