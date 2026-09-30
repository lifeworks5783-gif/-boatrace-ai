#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.boatrace.jp/owpc/pc/race/resultlist"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/123.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en;q=0.8",
}

DASH_RE = r"[-‐-‒–—−]"

RACE_RE = re.compile(
    r"^(\d{1,2})R$"
)

TRIFECTA_RE = re.compile(
    rf"^([1-6]){DASH_RE}([1-6]){DASH_RE}([1-6])$"
)

EXACTA_RE = re.compile(
    rf"^([1-6]){DASH_RE}([1-6])$"
)

BOAT_NAME_RE = re.compile(
    r"^([1-6])\s+(.+)$"
)


def norm(text: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(text)
        .replace("\u3000", " ")
        .strip(),
    )


def compact(text: str) -> str:
    return re.sub(
        r"\s+",
        "",
        norm(text),
    )


def parse_money(
    text: str,
) -> Optional[int]:

    s = (
        compact(text)
        .replace("¥", "")
        .replace("￥", "")
        .replace("円", "")
        .replace(",", "")
    )

    if s.isdigit():
        return int(s)

    return None


def parse_combo(
    text: str,
    legs: int,
) -> Optional[str]:

    s = compact(text)

    if legs == 3:
        pattern = TRIFECTA_RE
    else:
        pattern = EXACTA_RE

    m = pattern.fullmatch(s)

    if not m:
        return None

    return "-".join(
        m.groups()
    )


def row_cells(
    tr,
) -> List[str]:

    return [
        norm(
            x.get_text(
                " ",
                strip=True,
            )
        )
        for x in tr.find_all(
            ["th", "td"]
        )
    ]


def extract_payouts(
    soup: BeautifulSoup,
) -> Dict[int, dict]:

    out: Dict[int, dict] = {}

    for tr in soup.find_all("tr"):

        cells = row_cells(tr)

        if not cells:
            continue

        m = RACE_RE.fullmatch(
            compact(cells[0])
        )

        if not m:
            continue

        race = int(
            m.group(1)
        )

        trifecta = None
        exacta = None

        trifecta_pay = None
        exacta_pay = None

        trifecta_idx = None
        exacta_idx = None

        for i, cell in enumerate(
            cells[1:],
            start=1,
        ):

            if trifecta is None:

                combo = parse_combo(
                    cell,
                    3,
                )

                if combo:

                    trifecta = combo
                    trifecta_idx = i

                    continue

            if exacta is None:

                combo = parse_combo(
                    cell,
                    2,
                )

                if combo:

                    exacta = combo
                    exacta_idx = i

        if not trifecta:
            continue

        if trifecta_idx is not None:

            for cell in cells[
                trifecta_idx + 1 :
            ]:

                value = parse_money(
                    cell
                )

                if value is not None:

                    trifecta_pay = value
                    break

                if parse_combo(
                    cell,
                    2,
                ):
                    break

        if exacta_idx is not None:

            for cell in cells[
                exacta_idx + 1 :
            ]:

                value = parse_money(
                    cell
                )

                if value is not None:

                    exacta_pay = value
                    break

        monies = []

        for cell in cells[1:]:

            value = parse_money(
                cell
            )

            if value is not None:
                monies.append(value)

        if (
            trifecta_pay is None
            and monies
        ):
            trifecta_pay = monies[0]

        if (
            exacta_pay is None
            and len(monies) >= 2
        ):
            exacta_pay = monies[1]

        out[race] = {
            "trifecta": trifecta,
            "trifecta_pay": trifecta_pay,
            "exacta": exacta or "",
            "exacta_pay": exacta_pay,
        }

    return out


def extract_finish_orders(
    soup: BeautifulSoup,
) -> Dict[int, List[int]]:

    out: Dict[
        int,
        List[int],
    ] = {}

    current_race: Optional[
        int
    ] = None

    for tr in soup.find_all("tr"):

        cells = row_cells(tr)

        if not cells:
            continue

        first = compact(
            cells[0]
        )

        m = RACE_RE.fullmatch(
            first
        )

        if m:

            current_race = int(
                m.group(1)
            )

        boats: List[int] = []

        for cell in cells:

            mm = BOAT_NAME_RE.match(
                norm(cell)
            )

            if not mm:
                continue

            boat = int(
                mm.group(1)
            )

            if 1 <= boat <= 6:

                boats.append(
                    boat
                )

        if (
            current_race
            is not None
            and len(boats) >= 3
        ):

            dedup = []

            for boat in boats:

                if boat not in dedup:

                    dedup.append(
                        boat
                    )

            if len(dedup) >= 3:

                out[
                    current_race
                ] = dedup[:6]

    return out


def fetch_html(
    session: requests.Session,
    date: str,
    venue_code: int,
    retries: int = 3,
) -> str:

    params = {
        "hd": date,
        "jcd": f"{venue_code:02d}",
    }

    last_exc = None

    for attempt in range(
        1,
        retries + 1,
    ):

        try:

            response = session.get(
                BASE_URL,
                params=params,
                headers=HEADERS,
                timeout=(5, 20),
            )

            response.raise_for_status()

            response.encoding = (
                response.apparent_encoding
                or "utf-8"
            )

            text = response.text

            if (
                "結果一覧"
                not in text
                and
                "勝式・払戻金・結果"
                not in text
            ):

                raise RuntimeError(
                    "resultlist marker not found"
                )

            return text

        except Exception as exc:

            last_exc = exc

            if attempt < retries:

                time.sleep(
                    attempt * 1.5
                )

    raise RuntimeError(
        "fetch failed "
        f"jcd={venue_code:02d}: "
        f"{last_exc}"
    )


def load_program(
    date: str,
    data_dir: Path,
) -> Tuple[
    pd.DataFrame,
    pd.DataFrame,
]:

    races_path = (
        data_dir
        / f"program_races_{date}.csv"
    )

    entries_path = (
        data_dir
        / f"program_entries_{date}.csv"
    )

    if (
        not races_path.exists()
        or
        not entries_path.exists()
    ):

        raise FileNotFoundError(
            "program files missing: "
            f"{races_path.name} / "
            f"{entries_path.name}"
        )

    races = pd.read_csv(
        races_path,
        dtype={
            "date": str,
        },
    )

    entries = pd.read_csv(
        entries_path,
        dtype={
            "date": str,
        },
    )

    return (
        races,
        entries,
    )


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        required=True,
        help="YYYYMMDD",
    )

    parser.add_argument(
        "--data-dir",
        default="data",
    )

    parser.add_argument(
        "--archive-root",
        default="archive",
    )

    args = parser.parse_args()

    date = args.date

    if not re.fullmatch(
        r"\d{8}",
        date,
    ):

        raise SystemExit(
            "--date must be YYYYMMDD"
        )

    data_dir = Path(
        args.data_dir
    )

    data_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    races, entries = load_program(
        date,
        data_dir,
    )

    venue_df = (
        races[
            [
                "venue_code",
                "venue_name",
            ]
        ]
        .drop_duplicates()
        .sort_values(
            "venue_code"
        )
        .reset_index(
            drop=True
        )
    )

    expected_races = len(
        races
    )

    entry_map = {}

    for row in entries.to_dict(
        "records"
    ):

        key = (
            int(
                row[
                    "venue_code"
                ]
            ),
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

        entry_map[
            key
        ] = row

    results_rows = []
    boat_rows = []
    venue_status = []

    session = requests.Session()

    started = time.monotonic()

    venues = venue_df.to_dict(
        "records"
    )

    for i, venue in enumerate(
        venues,
        start=1,
    ):

        code = int(
            venue[
                "venue_code"
            ]
        )

        name = str(
            venue[
                "venue_name"
            ]
        )

        print(
            f"[{i}/{len(venues)}] "
            f"{name}({code:02d}) "
            "結果一覧取得",
            flush=True,
        )

        html = fetch_html(
            session,
            date,
            code,
        )

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        payouts = extract_payouts(
            soup
        )

        finishes = (
            extract_finish_orders(
                soup
            )
        )

        venue_races = sorted(
            int(x)
            for x
            in races.loc[
                races[
                    "venue_code"
                ].astype(int)
                == code,
                "race",
            ].tolist()
        )

        got = 0
        finish_got = 0

        for race_no in venue_races:

            payout = payouts.get(
                race_no
            )

            if not payout:
                continue

            got += 1

            race_id = (
                f"{date}_"
                f"{code:02d}_"
                f"{race_no:02d}"
            )

            results_rows.append(
                {
                    "date": date,
                    "venue_code": code,
                    "venue_name": name,
                    "race": race_no,
                    "race_id": race_id,
                    "trifecta":
                        payout[
                            "trifecta"
                        ],
                    "trifecta_pay":
                        payout[
                            "trifecta_pay"
                        ],
                    "exacta":
                        payout[
                            "exacta"
                        ],
                    "exacta_pay":
                        payout[
                            "exacta_pay"
                        ],
                }
            )

            order = finishes.get(
                race_no,
                [],
            )

            if len(order) >= 3:

                finish_got += 1

            finish_by_boat = {
                boat: position
                for (
                    position,
                    boat,
                )
                in enumerate(
                    order,
                    start=1,
                )
            }

            if (
                len(
                    finish_by_boat
                )
                < 3
                and
                payout[
                    "trifecta"
                ]
            ):

                top3 = [
                    int(x)
                    for x
                    in payout[
                        "trifecta"
                    ].split("-")
                ]

                for (
                    position,
                    boat,
                ) in enumerate(
                    top3,
                    start=1,
                ):

                    finish_by_boat[
                        boat
                    ] = position

            for boat in range(
                1,
                7,
            ):

                entry = (
                    entry_map.get(
                        (
                            code,
                            race_no,
                            boat,
                        ),
                        {},
                    )
                )

                boat_rows.append(
                    {
                        "date": date,
                        "venue_code":
                            code,
                        "venue_name":
                            name,
                        "race":
                            race_no,
                        "race_id":
                            race_id,
                        "boat":
                            boat,

                        # 高速評価用なので
                        # 進入・ST・タイムは
                        # ここでは取得しない
                        "course": "",

                        "registration_no":
                            entry.get(
                                "registration_no",
                                "",
                            ),

                        "racer_name":
                            entry.get(
                                "racer_name",
                                "",
                            ),

                        "finish":
                            finish_by_boat.get(
                                boat,
                                "",
                            ),

                        "st": "",
                        "race_time": "",
                    }
                )

        venue_status.append(
            {
                "venue_code":
                    code,
                "venue_name":
                    name,
                "expected":
                    len(
                        venue_races
                    ),
                "payout_races":
                    got,
                "finish_order_races":
                    finish_got,
            }
        )

        print(
            "    払戻 "
            f"{got}/"
            f"{len(venue_races)}R "
            "/ 着順 "
            f"{finish_got}/"
            f"{len(venue_races)}R",
            flush=True,
        )

    results_rows.sort(
        key=lambda x: (
            x[
                "venue_code"
            ],
            x[
                "race"
            ],
        )
    )

    boat_rows.sort(
        key=lambda x: (
            x[
                "venue_code"
            ],
            x[
                "race"
            ],
            x[
                "boat"
            ],
        )
    )

    results_path = (
        data_dir
        / f"results_{date}_all.csv"
    )

    boats_path = (
        data_dir
        / f"boat_results_{date}_all.csv"
    )

    venues_path = (
        data_dir
        / f"venues_{date}.csv"
    )

    validation_path = (
        data_dir
        / (
            "fast_results_validation_"
            f"{date}.json"
        )
    )

    pd.DataFrame(
        results_rows,
        columns=[
            "date",
            "venue_code",
            "venue_name",
            "race",
            "race_id",
            "trifecta",
            "trifecta_pay",
            "exacta",
            "exacta_pay",
        ],
    ).to_csv(
        results_path,
        index=False,
        encoding="utf-8-sig",
    )

    pd.DataFrame(
        boat_rows,
        columns=[
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
        ],
    ).to_csv(
        boats_path,
        index=False,
        encoding="utf-8-sig",
    )

    venue_output = []

    for venue in venues:

        venue_output.append(
            {
                "date":
                    date,
                "venue_code":
                    int(
                        venue[
                            "venue_code"
                        ]
                    ),
                "venue_name":
                    venue[
                        "venue_name"
                    ],
            }
        )

    pd.DataFrame(
        venue_output,
        columns=[
            "date",
            "venue_code",
            "venue_name",
        ],
    ).to_csv(
        venues_path,
        index=False,
        encoding="utf-8-sig",
    )

    actual_races = len(
        results_rows
    )

    top3_complete = 0

    if boat_rows:

        boat_df = pd.DataFrame(
            boat_rows
        )

        boat_df[
            "finish_num"
        ] = pd.to_numeric(
            boat_df[
                "finish"
            ],
            errors="coerce",
        )

        top3_complete = int(
            boat_df[
                boat_df[
                    "finish_num"
                ].isin(
                    [
                        1,
                        2,
                        3,
                    ]
                )
            ]
            .groupby(
                [
                    "venue_code",
                    "race",
                ]
            )
            .size()
            .eq(3)
            .sum()
        )

    missing = []

    have_keys = {
        (
            int(
                row[
                    "venue_code"
                ]
            ),
            int(
                row[
                    "race"
                ]
            ),
        )
        for row
        in results_rows
    }

    for row in races.to_dict(
        "records"
    ):

        key = (
            int(
                row[
                    "venue_code"
                ]
            ),
            int(
                row[
                    "race"
                ]
            ),
        )

        if key not in have_keys:

            missing.append(
                f"{key[0]:02d}-"
                f"{key[1]:02d}"
            )

    elapsed = round(
        time.monotonic()
        - started,
        2,
    )

    if (
        actual_races
        == expected_races
        and
        top3_complete
        == expected_races
    ):

        status = "PASS"

    else:

        status = "PARTIAL"

    validation = {
        "status":
            status,

        "date":
            date,

        "expected_races":
            expected_races,

        "result_races":
            actual_races,

        "top3_complete_races":
            top3_complete,

        "venues":
            venue_status,

        "missing_races":
            missing,

        "elapsed_seconds":
            elapsed,

        "source":
            (
                "BOAT RACE official "
                "resultlist "
                "(one page per venue)"
            ),

        "note":
            (
                "course/st/race_time "
                "are intentionally "
                "blank in fast "
                "evaluation data"
            ),

        "generated_at":
            datetime.now()
            .astimezone()
            .isoformat(),
    }

    validation_path.write_text(
        json.dumps(
            validation,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    yyyy = date[:4]
    mm = date[4:6]
    dd = date[6:8]

    archive_dir = (
        Path(
            args.archive_root
        )
        / yyyy
        / mm
        / dd
    )

    archive_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for src in [
        results_path,
        boats_path,
        venues_path,
        validation_path,
    ]:

        shutil.copy2(
            src,
            archive_dir
            / src.name,
        )

    print(
        json.dumps(
            validation,
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )

    if status != "PASS":

        print(
            "高速評価データが"
            "全レース分"
            "そろっていません。"
            "評価を止めます。",
            file=sys.stderr,
        )

        return 2

    print(
        "高速結果取得 PASS: "
        f"{actual_races}R / "
        f"{elapsed:.2f}秒",
        flush=True,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )