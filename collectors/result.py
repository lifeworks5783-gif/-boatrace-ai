from urllib.request import Request, urlopen
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import csv
import re


VENUE_CODE = "02"

JST = ZoneInfo("Asia/Tokyo")

TARGET_DATE = (
    datetime.now(JST).date()
    - timedelta(days=1)
)

DATE = TARGET_DATE.strftime("%Y%m%d")


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

        elif tag in ("td", "th") and self.in_row:
            self.in_cell = True
            self.current_cell = ""

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.in_cell:
            text = " ".join(
                self.current_cell.split()
            )

            self.current_row.append(
                text
            )

            self.in_cell = False

        elif tag == "tr" and self.in_row:
            if self.current_row:
                self.rows.append(
                    self.current_row
                )

            self.in_row = False


def yen_to_int(text):
    return int(
        text
        .replace("¥", "")
        .replace("￥", "")
        .replace(",", "")
        .replace("円", "")
        .strip()
    )


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
# BOAT RACE公式結果一覧取得
# =========================

url = (
    "https://www.boatrace.jp/owpc/pc/race/"
    f"resultlist?hd={DATE}&jcd={VENUE_CODE}"
)

request = Request(
    url,
    headers={
        "User-Agent": "Mozilla/5.0"
    }
)

with urlopen(
    request,
    timeout=20
) as response:

    html = response.read().decode(
        "utf-8",
        errors="replace"
    )


parser = TableParser()
parser.feed(html)


# =========================
# 1R〜12R抽出
# =========================

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

        results.append({
            "date": DATE,
            "venue_code":
                VENUE_CODE,
            "race":
                race_no,
            "trifecta":
                row[1]
                .replace(" ", ""),
            "trifecta_pay":
                yen_to_int(
                    row[2]
                ),
            "exacta":
                row[3]
                .replace(" ", ""),
            "exacta_pay":
                yen_to_int(
                    row[4]
                ),
        })


# =========================
# 件数チェック
# =========================

if len(results) == 0:

    print(
        "対象日は戸田非開催、"
        "または結果未掲載です。"
    )

    print(
        "結果CSVは作成しません。"
    )

    raise SystemExit(0)


if len(results) != 12:

    raise RuntimeError(
        "取得レース数が異常です: "
        f"{len(results)}件"
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
    / (
        f"results_"
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
            "trifecta",
            "trifecta_pay",
            "exacta",
            "exacta_pay",
        ]
    )

    writer.writeheader()

    writer.writerows(
        results
    )


# =========================
# ログ
# =========================

print(
    "===================="
)

print(
    "レース結果取得成功"
)

print(
    "対象日:",
    DATE
)

print(
    "取得レース数:",
    len(results)
)

print(
    "CSV保存先:",
    output_file
)

print(
    "===================="
)