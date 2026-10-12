"""Exactly one observed official race -> raw archive -> legacy parser -> score/signal dry-run.

Never persists reconstructed forecasts or claims predeadline observations.
Run from repo root, after installing requests and beautifulsoup4.
"""
from __future__ import annotations
import csv
import json
import re
import sys
import tempfile
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collectors"))
from raw_collector.archive import capture_one, load_raw, source_url
from raw_collector.drive_bundle import bundle_batch
from raw_collector.normalize import preview_local_bundle
from today_beforeinfo import parse_beforeinfo
from build_live_prediction import score_race
from build_latest_prediction_view import (
    build_up_signal, build_down_signal,
    build_signal_ai_prediction, load_signal_ai_config,
)

DATE, VENUE, NO, RACE_ID = "20261012", "22", 12, "20261012-22-12"

def official_racelist_ids(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    ids = []
    for tbody in soup.select("tbody"):
        link = tbody.select_one('a[href*="racersearch/profile?toban="]')
        if not link:
            continue
        m = re.search(r"toban=(\d{4})", link.get("href", ""))
        if m and m.group(1) not in ids:
            ids.append(m.group(1))
    return ids[:6]

def observed():
    stats = {
        "race_id": RACE_ID,
        "mode": "retrospective_readonly_diagnostic",
        "official_get_requests": 2,
        "raw_saved": False,
        "verified_6_registration_numbers": False,
        "parsed_six_exhibition_rows": False,
        "race_context_complete": False,
        "historical_features_available": False,
        "normal_score_six": False,
        "signals_computed": False,
        "signal_ai_if_active": False,
        "error": None,
    }
    with tempfile.TemporaryDirectory(prefix="boatrace-smoke-") as temp:
        pages = {}
        for kind in ("racelist", "beforeinfo"):
            url = source_url(DATE, kind, VENUE, NO)
            result = capture_one(url, Path(temp), retries=0)
            if result["status"] != "saved":
                raise RuntimeError("http_fetch_failed:" + kind + ":" + str(result.get("error")))
            raw = load_raw(Path(result["path"]))
            pages[kind] = raw.decode("utf-8", errors="replace")
        stats["raw_saved"] = True
        # Exercise the SAME normalization path as production without requiring Drive OAuth.
        # It remains local and ephemeral, and cannot be committed to public Git.
        bundle,_ = bundle_batch(Path(temp),Path(temp)/"private_bundle",DATE)
        preview = preview_local_bundle(bundle,root=ROOT)
        matches = [r for r in preview["races"] if r["race_id"]==RACE_ID]
        if len(matches)!=1 or matches[0]["parse_status"]!="ready_live_inputs":
            raise RuntimeError("raw_to_normalized_dry_run_failed")
        if matches[0]["source"].get("drive_raw_verified") or preview.get("source_archive")!="local_ephemeral_unarchived":
            raise RuntimeError("drive_status_misreported_in_dry_run")
        if len(matches[0]["boats"])!=6:
            raise RuntimeError("normalized_boat_count_not_six")
        stats["drive_free_normalize_six"] = True
        stats["raw_bundle_verified_locally_only"] = True

        program_path = ROOT / "daily_inputs" / "2026" / "10" / "12" / "base" / "program_entries_20261012.csv"
        if not program_path.is_file():
            raise RuntimeError("saved_official_program_missing")
        with program_path.open(encoding="utf-8-sig", newline="") as fh:
            program = sorted(
                [row for row in csv.DictReader(fh) if row["race_id"] == RACE_ID],
                key=lambda x: int(x["boat"]))
        if len(program) != 6 or len({r["registration_no"] for r in program}) != 6:
            raise RuntimeError("program_six_unique_entries_missing")
        ids = official_racelist_ids(pages["racelist"])
        expected = [x["registration_no"] for x in program]
        if ids != expected:
            raise RuntimeError("official_html_and_saved_program_entrant_mismatch:" + str(ids))
        stats["verified_6_registration_numbers"] = True

        base = dict(date=DATE, venue_code=VENUE, venue_name="福岡", race=NO, race_id=RACE_ID, deadline="16:40")
        parsed = parse_beforeinfo(pages["beforeinfo"], base, requested_at="retrospective_diagnostic")
        if parsed is None:
            raise RuntimeError("beforeinfo_parser_returned_empty")
        context, entries = parsed
        if len(entries) != 6:
            raise RuntimeError("beforeinfo_entries_not_six")
        for i, entry in enumerate(entries):
            if entry["registration_no"] != expected[i]:
                raise RuntimeError("beforeinfo_registration_mismatch")
            if entry["exhibition_time"] is None or entry["exhibition_course"] not in range(1, 7):
                raise RuntimeError("beforeinfo_exhibition_time_or_course_missing")
            if entry["exhibition_st_seconds"] is None or not entry["exhibition_st_raw"]:
                raise RuntimeError("beforeinfo_exhibition_st_missing")
        stats["parsed_six_exhibition_rows"] = True
        needed = ("air_temperature_c", "water_temperature_c", "wind_speed_mps", "wave_height_cm")
        if any(context.get(k) is None for k in needed):
            raise RuntimeError("beforeinfo_weather_missing")
        stats["race_context_complete"] = True
        stats["weather"] = {k:context[k] for k in needed}
        stats["exhibition_st"] = [e["exhibition_st_raw"] for e in entries]
        stats["exhibition_times"] = [e["exhibition_time"] for e in entries]

        boats = []
        for official, parsed_row in zip(program, entries):
            boats.append({
                "boat": int(official["boat"]),
                "racer": {
                    "registration_no": official["registration_no"],
                    "name": official["racer_name"],
                    "grade": official["grade"],
                },
                "motor": {
                    "motor_no": int(official["motor_no"]),
                    "official_top2_rate": official["motor_top2_rate"],
                },
                "boat_machine": {
                    "boat_no": int(official["boat_no"]),
                    "official_top2_rate": official["boat_top2_rate"],
                },
                "beforeinfo": parsed_row,
                "history": {},
            })
        race = {
            "race_id": RACE_ID, "venue_code": VENUE,
            "boats": boats, "beforeinfo": context, **context
        }
        try:
            scored = score_race(race, public_store=None)
        except Exception as ex:
            raise RuntimeError("normal_score_missing_inputs:" + str(ex)[:450]) from ex
        if len(scored) != 6 or any(x.get("score") is None or x.get("morning_score_reference") is None for x in scored):
            raise RuntimeError("normal_score_incomplete")
        stats["historical_features_available"] = True
        stats["normal_score_six"] = True
        stats["scores_by_boat"] = {str(b["boat"]): b["score"] for b in scored}
        quality = {"status":"retrospective_diagnostic","retrospective_simulation_only": True}
        up, down = build_up_signal(scored, quality), build_down_signal(scored, quality)
        if not up.get("available") or not down.get("available"):
            raise RuntimeError("signal_detector_unavailable")
        stats["signals_computed"] = True
        stats["raijin_level"] = up["level"]
        stats["fujin_level"] = down["level"]
        if up["level"] or down["level"]:
            signal_ai = build_signal_ai_prediction(scored, up, down, load_signal_ai_config())
            if not signal_ai:
                raise RuntimeError("active_signal_ai_missing")
            stats["signal_ai_if_active"] = True
            stats["signal_ai_ticket_count"] = len(signal_ai.get("combinations") or [])
            if stats["signal_ai_ticket_count"] != 24 or signal_ai.get("points") != 24:
                raise RuntimeError("signal_ai_24_tickets_not_generated")
            if len(signal_ai.get("all_120_combinations") or []) != 120:
                raise RuntimeError("signal_ai_120_combinations_missing")
        else:
            stats["signal_ai_if_active"] = "not_applicable"
    return stats

if __name__ == "__main__":
    try:
        result = observed()
    except Exception as exc:
        result = {"race_id": RACE_ID, "mode":"retrospective_readonly_diagnostic", "status":"FAILED",
                  "error": str(exc)}
        print("ONE_RACE_SMOKE=" + json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    result["status"]="PASS"
    print("ONE_RACE_SMOKE=" + json.dumps(result, ensure_ascii=False))
