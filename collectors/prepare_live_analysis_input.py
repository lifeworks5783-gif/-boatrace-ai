#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def load_json(path: Path) -> Any:
    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


def save_json(
    path: Path,
    data: Any,
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def to_int(
    value: Any,
) -> Optional[int]:

    try:
        return int(
            float(value)
        )
    except Exception:
        return None


def to_float(
    value: Any,
) -> Optional[float]:

    if (
        value is None
        or isinstance(
            value,
            bool,
        )
    ):
        return None

    try:
        return float(
            str(value)
            .replace(",", "")
            .strip()
        )
    except Exception:
        return None


def venue_code(
    value: Any,
) -> str:

    try:
        return (
            f"{int(float(value)):02d}"
        )
    except Exception:
        return str(
            value or ""
        ).zfill(2)


def parse_race_id(
    value: Any,
) -> Tuple[
    str,
    str,
    Optional[int],
]:

    match = re.search(
        r"(\d{8})[-_](\d{2})[-_](\d{1,2})",
        str(value or ""),
    )

    if not match:
        return (
            "",
            "",
            None,
        )

    return (
        match.group(1),
        match.group(2),
        int(
            match.group(3)
        ),
    )


def boat_records(
    root: Any,
    default_date: str,
) -> List[
    Dict[str, Any]
]:

    rows: List[
        Dict[str, Any]
    ] = []

    def walk(
        node: Any,
        context: Dict[str, Any],
    ) -> None:

        if isinstance(
            node,
            dict,
        ):

            current = dict(
                context
            )

            if "race_id" in node:

                date_value, venue_value, race_value = (
                    parse_race_id(
                        node.get(
                            "race_id"
                        )
                    )
                )

                if date_value:
                    current[
                        "date"
                    ] = date_value

                if venue_value:
                    current[
                        "venue_code"
                    ] = venue_value

                if race_value is not None:
                    current[
                        "race"
                    ] = race_value

            for source, target in (
                (
                    "date",
                    "date",
                ),
                (
                    "target_date",
                    "date",
                ),
                (
                    "venue_code",
                    "venue_code",
                ),
                (
                    "jcd",
                    "venue_code",
                ),
                (
                    "race",
                    "race",
                ),
                (
                    "rno",
                    "race",
                ),
            ):

                value = node.get(
                    source
                )

                if not isinstance(
                    value,
                    (
                        dict,
                        list,
                    ),
                ):

                    if value is not None:
                        current[
                            target
                        ] = value

            boat = None

            for key in (
                "boat",
                "frame",
                "lane",
            ):

                candidate = to_int(
                    node.get(key)
                )

                if (
                    candidate is not None
                    and 1 <= candidate <= 6
                ):

                    boat = candidate
                    break

            race = to_int(
                current.get(
                    "race"
                )
            )

            if (
                boat is not None
                and race is not None
            ):

                rows.append(
                    {
                        "date":
                            str(
                                current.get(
                                    "date",
                                    default_date,
                                )
                            ),

                        "venue_code":
                            venue_code(
                                current.get(
                                    "venue_code"
                                )
                            ),

                        "race":
                            race,

                        "boat":
                            boat,

                        "raw":
                            node,
                    }
                )

            for value in node.values():

                if isinstance(
                    value,
                    (
                        dict,
                        list,
                    ),
                ):

                    walk(
                        value,
                        current,
                    )

        elif isinstance(
            node,
            list,
        ):

            for item in node:
                walk(
                    item,
                    context,
                )

    walk(
        root,
        {
            "date":
                default_date
        },
    )

    dedup = {}

    for row in rows:

        key = (
            row["date"],
            row["venue_code"],
            row["race"],
            row["boat"],
        )

        dedup[
            key
        ] = row

    return list(
        dedup.values()
    )


def find_total_score(
    node: Any,
) -> Optional[float]:

    if isinstance(
        node,
        dict,
    ):

        for key in (
            "total_score",
            "final_score",
            "prediction_score",
            "score",
        ):

            value = to_float(
                node.get(key)
            )

            if value is not None:
                return value

        for value in node.values():

            found = find_total_score(
                value
            )

            if found is not None:
                return found

    elif isinstance(
        node,
        list,
    ):

        for item in node:

            found = find_total_score(
                item
            )

            if found is not None:
                return found

    return None


def score_map(
    path: Path,
    date: str,
) -> Dict[
    Tuple[str, int, int],
    float,
]:

    output = {}

    for row in boat_records(
        load_json(path),
        date,
    ):

        score = find_total_score(
            row["raw"]
        )

        if score is None:
            continue

        key = (
            row["venue_code"],
            row["race"],
            row["boat"],
        )

        output[
            key
        ] = score

    return output


def get_previous_paths(
    date: str,
) -> Dict[str, Optional[Path]]:

    analysis_path = (
        Path("evaluations")
        / date[:4]
        / date[4:6]
        / date[6:8]
        / (
            "score_component_"
            f"analysis_{date}.json"
        )
    )

    output = {
        "morning_input":
            None,

        "morning_prediction":
            None,

        "live_prediction":
            None,
    }

    if not analysis_path.exists():
        return output

    data = load_json(
        analysis_path
    )

    stages = (
        data.get(
            "stage_analysis"
        )
        or {}
    )

    morning = (
        stages.get(
            "morning"
        )
        or {}
    )

    live = (
        stages.get(
            "live"
        )
        or {}
    )

    morning_meta = (
        morning.get(
            "meta"
        )
        or {}
    )

    live_meta = (
        live.get(
            "meta"
        )
        or {}
    )

    candidates = {
        "morning_input":
            morning_meta.get(
                "input_file"
            ),

        "morning_prediction":
            morning_meta.get(
                "prediction_file"
            ),

        "live_prediction":
            live_meta.get(
                "prediction_file"
            ),
    }

    for key, value in (
        candidates.items()
    ):

        if value:

            path = Path(
                value
            )

            if path.exists():
                output[
                    key
                ] = path

    return output


def discover_file(
    patterns: List[str],
) -> Optional[Path]:

    candidates = []

    for pattern in patterns:

        for path in Path(
            "."
        ).glob(
            pattern
        ):

            if path.is_file():
                candidates.append(
                    path
                )

    if not candidates:
        return None

    return sorted(
        candidates,
        key=lambda path:
            (
                "final"
                in path.name.lower(),

                "enriched"
                in path.name.lower(),

                str(path),
            ),
        reverse=True,
    )[0]


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        required=True,
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

    year = date[:4]
    month = date[4:6]
    day = date[6:8]

    paths = get_previous_paths(
        date
    )

    if paths[
        "morning_input"
    ] is None:

        paths[
            "morning_input"
        ] = discover_file(
            [
                (
                    f"data/"
                    f"prediction_input_"
                    f"enriched_morning_"
                    f"{date}.json"
                ),
                # 本番で長期保存される朝入力は daily_inputs/YYYY/MM/DD 直下。
                # 旧 morning/ サブフォルダだけを検索すると欠損と誤判定する。
                f"daily_inputs/{year}/{month}/{day}/prediction_input_enriched_morning_{date}.json",
                f"daily_inputs/{year}/{month}/{day}/prediction_input_morning_{date}.json",

                (
                    f"data/"
                    f"prediction_input_"
                    f"morning_"
                    f"{date}.json"
                ),

                (
                    f"daily_inputs/"
                    f"{year}/"
                    f"{month}/"
                    f"{day}/"
                    f"morning/"
                    f"**/*enriched*.json"
                ),
            ]
        )

    if paths[
        "morning_prediction"
    ] is None:

        paths[
            "morning_prediction"
        ] = discover_file(
            [
                (
                    f"predictions/"
                    f"{year}/"
                    f"{month}/"
                    f"{day}/"
                    f"morning/"
                    f"**/*final*.json"
                ),
                f"predictions/{year}/{month}/{day}/morning_predictions_{date}.json",
                f"daily_inputs/{year}/{month}/{day}/morning_predictions_{date}.json",

                (
                    f"predictions/"
                    f"{year}/"
                    f"{month}/"
                    f"{day}/"
                    f"morning/"
                    f"**/*prediction*.json"
                ),
            ]
        )

    if paths[
        "live_prediction"
    ] is None:

        paths[
            "live_prediction"
        ] = discover_file(
            [
                (
                    f"predictions/"
                    f"{year}/"
                    f"{month}/"
                    f"{day}/"
                    f"live/"
                    f"**/*final*.json"
                ),

                (
                    f"predictions/"
                    f"{year}/"
                    f"{month}/"
                    f"{day}/"
                    f"live/"
                    f"**/*prediction*.json"
                ),

                (
                    f"data/"
                    f"*live*prediction*"
                    f"{date}*.json"
                ),
            ]
        )

    for key in (
        "morning_input",
        "morning_prediction",
        "live_prediction",
    ):

        if paths[
            key
        ] is None:

            raise SystemExit(
                f"required file not found: {key}"
            )

        print(
            f"{key}: "
            f"{paths[key]}"
        )

    morning_records = (
        boat_records(
            load_json(
                paths[
                    "morning_input"
                ]
            ),
            date,
        )
    )

    morning_scores = score_map(
        paths[
            "morning_prediction"
        ],
        date,
    )

    live_scores = score_map(
        paths[
            "live_prediction"
        ],
        date,
    )

    output_entries = []

    delta_count = 0

    for row in morning_records:

        key = (
            row[
                "venue_code"
            ],
            row[
                "race"
            ],
            row[
                "boat"
            ],
        )

        raw = copy.deepcopy(
            row[
                "raw"
            ]
        )

        if not isinstance(
            raw,
            dict,
        ):
            continue

        raw[
            "date"
        ] = date

        raw[
            "venue_code"
        ] = row[
            "venue_code"
        ]

        raw[
            "race"
        ] = row[
            "race"
        ]

        raw[
            "boat"
        ] = row[
            "boat"
        ]

        morning_score = (
            morning_scores.get(
                key
            )
        )

        live_score = (
            live_scores.get(
                key
            )
        )

        analysis_beforeinfo = {}

        if (
            morning_score is not None
            and live_score is not None
        ):

            analysis_beforeinfo[
                "live_score_delta"
            ] = round(
                live_score
                - morning_score,
                6,
            )

            delta_count += 1

        raw[
            "beforeinfo_analysis"
        ] = (
            analysis_beforeinfo
        )

        output_entries.append(
            raw
        )

    output_path = Path(
        f"data/"
        f"prediction_input_"
        f"enriched_live_"
        f"{date}.json"
    )

    save_json(
        output_path,
        {
            "date":
                date,

            "stage":
                "live_analysis",

            "analysis_only":
                True,

            "source":
                (
                    "morning static pre-race "
                    "features + "
                    "morning-to-live score delta"
                ),

            "entries":
                output_entries,
        },
    )

    print("")
    print(
        "直前分析用入力生成: PASS"
    )

    print(
        "entries:",
        len(
            output_entries
        ),
    )

    print(
        "live_score_delta:",
        delta_count,
    )

    print(
        "output:",
        output_path,
    )

    if delta_count == 0:

        raise SystemExit(
            "live score delta was not generated"
        )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )