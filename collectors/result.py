from urllib.request import Request, urlopen
from html.parser import HTMLParser
import re


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


url = (
    "https://www.boatrace.jp/owpc/pc/race/"
    "resultlist?hd=20260926&jcd=02"
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
        and any("¥" in cell for cell in row)
    ):
        results.append({
            "race": race,
            "trifecta": row[1],
            "trifecta_pay": row[2],
            "exacta": row[3],
            "exacta_pay": row[4],
        })


print("取得レース数:", len(results))

for result in results:
    print(
        result["race"],
        "3連単:", result["trifecta"],
        "払戻:", result["trifecta_pay"],
        "2連単:", result["exacta"],
        "払戻:", result["exacta_pay"],
    )