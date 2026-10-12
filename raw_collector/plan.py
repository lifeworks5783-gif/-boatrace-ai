"""Build bounded official URL collection plans; never parse exhibition values here.

Scheduling uses already saved, dated race program CSV only for race identity
and cutoff clock. It never marks a race fetched or generates predictions.
"""
from __future__ import annotations
import argparse
import csv
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from raw_collector.archive import source_url

JST = timezone(timedelta(hours=9))

def official_schedule_path(root: Path, day: str) -> Path:
    if not re.fullmatch(r"\d{8}", day):
        raise ValueError("invalid_schedule_date")
    return root / "daily_inputs" / day[:4] / day[4:6] / day[6:8] / "base" / f"program_races_{day}.csv"

def candidate_urls(root: Path, day: str, now: datetime, *, max_requests: int = 12,
                   venues: set[str] | None = None) -> list[dict]:
    if now.tzinfo is None:
        raise ValueError("timezone_aware_now_required")
    if not isinstance(max_requests, int) or not 1 <= max_requests <= 30:
        raise ValueError("invalid_request_limit")
    path = official_schedule_path(root, day)
    if not path.is_file():
        raise FileNotFoundError("official_program_schedule_missing")
    candidates = []
    seen = set()
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            race_id = str(row.get("race_id") or "")
            if not re.fullmatch(r"\d{8}-\d{2}-(?:0[1-9]|1[0-2])", race_id):
                continue
            rid_day, venue, race_text = race_id.split("-")
            if rid_day != day or (venues is not None and venue not in venues) or race_id in seen:
                continue
            seen.add(race_id)
            try:
                cutoff = datetime.strptime(day + " " + str(row["deadline"]), "%Y%m%d %H:%M").replace(tzinfo=JST)
                seconds = (cutoff-now.astimezone(JST)).total_seconds()
            except (KeyError, TypeError, ValueError):
                continue
            if seconds < 90:
                continue  # No predeadline claim from a late website response.
            if seconds <= 25*60:
                kind = "beforeinfo"
                priority = 0
            else:
                kind = "racelist"
                priority = 1
            candidates.append({
                "race_id": race_id,
                "source_kind": kind,
                "url": source_url(day, kind, venue, int(race_text)),
                "cutoff_iso": cutoff.isoformat(),
                "seconds_until_cutoff": int(seconds),
                "_priority": priority,
            })
    candidates.sort(key=lambda x:(x["_priority"],x["seconds_until_cutoff"],x["race_id"]))
    return [{k:v for k,v in row.items() if k!="_priority"}
            for row in candidates[:max_requests]]

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=True)
    p.add_argument("--now",default=datetime.now(JST).isoformat())
    p.add_argument("--max-requests",type=int,default=12)
    p.add_argument("--venue",action="append")
    p.add_argument("--repo-root",type=Path,default=Path("."))
    args=p.parse_args(argv)
    result=candidate_urls(args.repo_root,args.date,datetime.fromisoformat(args.now),
        max_requests=args.max_requests,
        venues={v.zfill(2) for v in args.venue} if args.venue else None)
    print(json.dumps({"planned":len(result),"targets":result},
                     ensure_ascii=False,indent=2))
if __name__=="__main__":
    main()
