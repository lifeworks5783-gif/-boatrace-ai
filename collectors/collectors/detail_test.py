from urllib.request import Request, urlopen
from html.parser import HTMLParser
import re


DATE = "20260926"
VENUE_CODE = "02"
RACE_NO = "1"


class DetailParser(HTMLParser):
    def __init__(self):
        super().__init__()

        self.rows = []
        self.current_row = []
        self.current_cell = ""
        self.in_row = False
        self.in_cell = False

        self.tokens = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.in_row = True
            self.current_row = []

        elif tag in ("td", "th") and self.in_row:
            self.in_cell = True
            self.current_cell = ""

    def handle_data(self, data):
        text = " ".join(data.split())

        if text:
            self.tokens.append(text)

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
    f"raceresult?hd={DATE}&jcd={VENUE_CODE}&rno={RACE_NO}"
)

request = Request(
    url,
    headers={
        "User-Agent": "Mozilla/5.0"
    }
)

with urlopen(request, timeout=20) as response:
    html = response.read().decode(
        "utf-8",
        errors="replace"
    )


parser = DetailParser()
parser.feed(html)


# -------------------------
# 着順・選手情報を取得
# -------------------------

rank_translate = str.maketrans(
    "１２３４５６",
    "123456"
)

racers = {}

for row in parser.rows:

    if len(row) < 3:
        continue

    finish = row[0].translate(rank_translate).strip()
    boat = row[1].strip()

    if (
        finish in ["1", "2", "3", "4", "5", "6"]
        and boat in ["1", "2", "3", "4", "5", "6"]
        and re.match(r"^\d{4}", row[2])
    ):

        racer_text = " ".join(row[2].split())

        match = re.match(
            r"^(\d{4})\s+(.+)$",
            racer_text
        )

        if not match:
            continue

        registration_no = match.group(1)
        racer_name = match.group(2)

        race_time = ""

        if len(row) >= 4:
            race_time = row[3].strip()

        racers[boat] = {
            "finish": finish,
            "boat": boat,
            "registration_no": registration_no,
            "racer_name": racer_name,
            "race_time": race_time,
        }


# -------------------------
# ST・進入コースを取得
# -------------------------

start_info = {}

try:
    start_index = parser.tokens.index(
        "スタート情報"
    )

    end_index = parser.tokens.index(
        "勝式",
        start_index
    )

    start_tokens = parser.tokens[
        start_index + 1:end_index
    ]

    course = 0
    i = 0

    while i < len(start_tokens):

        token = start_tokens[i]

        if token in [
            "1", "2", "3",
            "4", "5", "6"
        ]:

            boat = token
            st = None

            for j in range(
                i + 1,
                min(i + 5, len(start_tokens))
            ):

                candidate = start_tokens[j]

                if re.fullmatch(
                    r"(?:F|L)?\.?\d{2}",
                    candidate
                ):
                    st = candidate
                    break

            if st is not None:
                course += 1

                start_info[boat] = {
                    "course": course,
                    "st": st,
                }

        i += 1

except ValueError:
    print(
        "スタート情報を取得できませんでした"
    )


# -------------------------
# 6艇を結合して表示
# -------------------------

print(
    "取得艇数:",
    len(racers)
)

for boat in [
    "1", "2", "3",
    "4", "5", "6"
]:

    racer = racers.get(boat)
    start = start_info.get(
        boat,
        {}
    )

    if racer is None:
        continue

    result = {
        "date": DATE,
        "venue_code": VENUE_CODE,
        "race": RACE_NO,
        "boat": boat,
        "course": start.get(
            "course"
        ),
        "registration_no":
            racer["registration_no"],
        "racer_name":
            racer["racer_name"],
        "finish":
            racer["finish"],
        "st":
            start.get("st"),
        "race_time":
            racer["race_time"],
    }

    print(result)