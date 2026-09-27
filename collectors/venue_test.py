from urllib.request import Request, urlopen
from html.parser import HTMLParser
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import csv


JST = ZoneInfo("Asia/Tokyo")

TARGET_DATE = (
    datetime.now(JST).date()
    - timedelta(days=1)
)

DATE = TARGET_DATE.strftime("%Y%m%d")


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


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()

        self.links = []

    def handle_starttag(self, tag, attrs):

        if tag != "a":
            return

        attrs_dict = dict(attrs)

        href = attrs_dict.get("href")

        if href:
            self.links.append(href)


# =========================
# 対象日表示
# =========================

print(
    "日本時間:",
    datetime.now(JST)
)

print(
    "開催場検出対象日:",
    DATE
)


# =========================
# BOAT RACE公式
# 当日レース一覧取得
# =========================

url = (
    "https://www.boatrace.jp/"
    "owpc/pc/race/index"
    f"?hd={DATE}"
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


# =========================
# 結果一覧リンクから
# 開催場コードを抽出
# =========================

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


venue_codes = sorted(
    venue_codes,
    key=int
)


# =========================
# 異常チェック
# =========================

if len(venue_codes) == 0:

    raise RuntimeError(
        "開催場を1件も検出"
        "できませんでした"
    )


if len(venue_codes) > 24:

    raise RuntimeError(
        "開催場数が異常です: "
        f"{len(venue_codes)}"
    )


# =========================
# CSV保存
# =========================

output_dir = Path("data")

output_dir.mkdir(
    exist_ok=True
)

output_file = (
    output_dir
    / f"venues_{DATE}.csv"
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
            "venue_name",
        ]
    )

    writer.writeheader()

    for code in venue_codes:

        writer.writerow({
            "date": DATE,
            "venue_code": code,
            "venue_name":
                VENUE_NAMES[code],
        })


# =========================
# ログ
# =========================

print(
    "===================="
)

print(
    "開催場検出成功"
)

print(
    "対象日:",
    DATE
)

print(
    "開催場数:",
    len(venue_codes)
)

for code in venue_codes:

    print(
        code,
        VENUE_NAMES[code]
    )

print(
    "CSV保存先:",
    output_file
)

print(
    "===================="
)