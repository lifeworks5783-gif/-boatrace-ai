from urllib.request import Request, urlopen
from html.parser import HTMLParser
from pathlib import Path
import csv
import re


DATE = "20260926"
VENUE_CODE = "02"


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
            text = " ".join(self.current_cell.split())
            self.current_row.append(text)
            self.in_cell = False

        elif tag == "tr" and self.in_row:
            if self.current_row:
                self.rows.append(self.current_row)
            self.in_row = False


def yen_to_int(text):
    return int(
        text.replace("¥", "")
            .replace("￥", "")
            .replace(",", "")
            .replace("円", "")
            .strip()
    )


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

with urlopen(request, timeout=20) as response:
    html = response.read().decode("utf-8", errors="replace")

parser = TableParser()
parser.feed(html)

results = []

for row in parser.rows:
    if not row:
        continue

    race = row[0].replace(" ", "")

    if (
        re.fullmatch(r"\d{1,2}R", race)
        and len(row) >= 5
        and any("¥" in cell or "￥" in cell for cell in row)
    ):
        results.append({
            "date": DATE,
            "venue_code": VENUE_CODE,
            "race": race,
            "trifecta": row[1].replace(" ", ""),
            "trifecta_pay": yen_to_int(row[2]),
            "exacta": row[3].replace(" ", ""),
            "exacta_pay": yen_to_int(row[4]),
        })


output_dir = Path("data")
output_dir.mkdir(exist_ok=True)

output_file = output_dir / f"results_{DATE}_{VENUE_CODE}.csv"

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
    writer.writerows(results)


print("取得レース数:", len(results))
print("CSV保存先:", output_file)

for result in results:
    print(result)