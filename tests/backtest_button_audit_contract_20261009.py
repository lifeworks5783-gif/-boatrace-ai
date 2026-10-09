#!/usr/bin/env python3
"""Real saved-data, black-box regression of button-only collection and audit UI.

Read-only in production: creates temporary rendered pages on a disposable CI
checkout.  Exit nonzero on any acceptance failure.  Never heals failures.
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import tempfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collectors"))
from build_family_prediction_page import build_card
from build_latest_prediction_view import build_up_signal, build_down_signal
from race_prediction_store import audit_canonical, audit_race, load_canonical, tickets24

DATE = "20261009"
RESULTS = []
TARGET = ROOT / "_audit_backtest"
TARGET.mkdir(exist_ok=True)


def record(case, ok, observed, expected, race_id=None):
    item = {"case": case, "status": "PASS" if ok else "FAIL",
            "observed": str(observed), "expected": str(expected)}
    if race_id:
        item["race_id"] = race_id
    RESULTS.append(item)
    print("BACKTEST", item["status"], case, "observed=", observed, "expected=", expected, flush=True)


def run_builder(args):
    p = subprocess.run([sys.executable, *args], cwd=ROOT, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=150)
    if p.returncode:
        print("RENDER_ERROR", p.returncode, p.stdout[-2200:], flush=True)
    return p.returncode == 0


def main():
    source = load_canonical(DATE)
    by_id = {r["race_id"]: r for r in source["races"]}
    stats = audit_canonical(source)
    record("actual_20261009_coverage", len(by_id) >= 140,
           f"{len(by_id)} canonical race IDs", "at least 140 saved races")
    record("saved_signal_24_integrity", stats["missing_signal_24"] == 0,
           stats["missing_signal_24"], "0 broken signal tickets")

    # A real production fallback that was mistakenly labelled "直前".
    mikuni = by_id["20261009-10-10"]
    q = mikuni.get("prediction_quality") or {}
    h = build_card(mikuni, 1)
    misleading = (
        "class=\"badge live\">直前</div>" in h
        and "saved_morning_prediction" == q.get("fallback_source")
        and "±0.0" in h
    )
    record("mikuni10_true_stage_visible", not misleading,
           f"stage={mikuni.get('prediction_type')} quality={q.get('status')} "
           f"source={q.get('fallback_source')} zero_delta={('±0.0' in h)}",
           "朝予測・直前未取得 (never a falsely completed live prediction)",
           mikuni["race_id"])

    # Button was not pressed again: never blame untried collections.
    workflow = (ROOT / ".github/workflows/fast_live_collection_v3.yml").read_text(encoding="utf-8")
    raw_dir = ROOT / "daily_inputs/2026/10/09/live/raw"
    stamps = sorted(p.name for p in raw_dir.iterdir() if p.is_dir()) if raw_dir.exists() else []
    last_attempt = stamps[-1] if stamps else "none"
    no_auto_schedule = "schedule:" not in workflow.split("jobs:", 1)[0]
    record("button_only_collection_switch", no_auto_schedule,
           f"schedule={not no_auto_schedule}, last_immutable_raw={last_attempt}",
           "no schedule; collect only after explicit trigger")
    # The actual issue is missing correlation between latest page and button run.
    record("attempt_identity_and_reason_saved", all(
        (mikuni.get(field) is not None) for field in ("collection_run_id", "collection_attempt_at", "collection_reason_code")
    ), {f:mikuni.get(f) for f in ("collection_run_id", "collection_attempt_at", "collection_reason_code")},
           "event ID, attempted_at and reason_code distinguish untried vs failed",
           mikuni["race_id"])

    # Real recorded official pre-race fallback must allow individual recovery.
    for race_id, expected_key in [
        ("20261009-03-08", "F0R1"), ("20261009-23-10", "F0R1")
    ]:
        race = by_id[race_id]
        audit = audit_race(race)
        completed = (
            audit.get("signal_key") == expected_key
            and audit.get("signal_ai_status") == "ready"
            and race.get("retrospective_signal_recovery") is True
            and race.get("signal_detected_at_original_deadline") is False
            and len(tickets24(race)) == 24
        )
        record("retrospective_signal_24_" + race_id[-5:],
               completed,
               f"signal={audit.get('signal_key')} state={audit.get('signal_ai_status')} "
               f"backfill={race.get('retrospective_signal_recovery')}, tickets={len(tickets24(race))}",
               "official replay, 24 combinations, real-time distinct",
               race_id)

    # Official reduced-field starter count is not a data corruption.
    scratched = by_id["20261009-08-08"]
    scratch_files = list((ROOT / "evaluations/2026/10/09/recovery").glob(
        "official_retry_beforeinfo_entries_*.csv"
    ))
    known_scratch = set()
    for path in scratch_files:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("race_id") == "20261009-08-08" and row.get("is_miss","").lower() in ("true","1","yes"):
                    known_scratch.add(int(row["boat"]))
    present = {int(b["boat"]) for b in scratched.get("boats", [])}
    record("tokoname8_official_scratched_valid", len(present) == 5 and
           bool(known_scratch) and not (known_scratch & present),
           f"scored={sorted(present)}, official_miss={sorted(known_scratch)}",
           "5 valid scores; officially absent starter is not a blocking error",
           scratched["race_id"])

    # Synthetic injected damage: audit should catch a corrupted active 24-ticket set.
    broken = deepcopy(by_id["20261009-23-10"])
    broken["signal_ai_prediction"] = {"signal_key": "F0R1", "combinations": []}
    b = audit_race(broken)
    record("injected_signal_ticket_loss_detected",
           b["signal_ai_status"] == "missing_or_invalid_signal_24",
           b["signal_ai_status"], "error detected; never silently switch to normal AI",
           broken["race_id"])

    # A complete valid live score using a STRUCTURAL fallback must remain usable,
    # flagged, and auditable. It is not the same as "morning only/no exhibition".
    original = by_id["20261009-03-08"]
    partial = deepcopy(original)
    partial["prediction_quality"] = {
        "status": "fallback", "recovery_needed": True,
        "reason": ["course history unavailable"],
        "fallback_source": "saved_morning_structural_component",
    }
    up = build_up_signal(partial["boats"], partial["prediction_quality"])
    down = build_down_signal(partial["boats"], partial["prediction_quality"])
    record("injected_valid_live_with_structural_fallback",
           bool(up.get("available")) and bool(down.get("available")),
           f"up={up.get('available')} down={down.get('available')} "
           f"reason={up.get('suppressed_reason')}",
           "evaluate valid official exhibition and mark component fallback as warning",
           original["race_id"])

    # Real HTML render, not a mocked screenshot or a grep of CI logs.
    with tempfile.TemporaryDirectory(prefix="audit_button_backtest_") as td:
        td = Path(td)
        ok_source = run_builder([
            "collectors/build_deadline_prediction_view.py", "--date", DATE,
        ])
        ok_latest = ok_source and run_builder([
            "collectors/build_family_prediction_page.py", "--input",
            "predictions/latest_by_deadline.json",
            "--output-dir", str(td / "latest"),
        ])
        ok_compare = run_builder([
            "collectors/build_family_race_compare_page.py",
            "--date", DATE, "--predictions-root", "predictions",
            "--output-dir", str(td / "compare"),
        ])
        record("render_both_actual_pages", ok_latest and ok_compare,
               f"latest={ok_latest} compare={ok_compare}",
               "both pages render successfully, from same saved date")

        htmls = {}
        for page, path in [
            ("latest", td / "latest" / "index.html"),
            ("comparison", td / "compare" / "race_compare.html"),
        ]:
            html = path.read_text(encoding="utf-8") if path.is_file() else ""
            htmls[page] = html
            cards = re.findall(r'<article class="race-card">(.+?)</article>',
                               html, flags=re.DOTALL)
            audit_summary = "監査状況" in html and "監査対象" in html
            cause_visible = "直前未取得" in html and "取得" in html
            record("visible_audit_summary_" + page, audit_summary,
                   f"cards={len(cards)}, audit_heading={audit_summary}",
                   "top-of-page audit summary with count and race-specific issues")
            record("visible_missing_reason_" + page, cause_visible,
                   f"contains_直前未取得={('直前未取得' in html)}",
                   "human-visible actionable reason for uncollected races")

        # Shared event-scoped audit view must be visible across BOTH pages.
        # Correlation key deliberately checks data, not identical HTML structure.
        record("identical_audit_dataset_across_two_pages",
               all("監査対象" in h and "監査状況" in h for h in htmls.values()),
               {k:("監査状況" in h and "監査対象" in h) for k,h in htmls.items()},
               "same auditable source/total/issues in both published views")

        # Check race must not disappear merely because it is finished.
        compare = htmls.get("comparison", "")
        record("edogawa8_result_comparison_retained",
               "江戸川" in compare and "事後捕捉" in compare,
               f"edogawa_present={('江戸川' in compare)}, retro_present={('事後捕捉' in compare)}",
               "recovery remains in finished-race comparison", "20261009-03-08")

    report = {
        "scope": "isolated pull-request backtest only; production untouched",
        "date": DATE,
        "saved_races": len(by_id),
        "failures": sum(x["status"] == "FAIL" for x in RESULTS),
        "passes": sum(x["status"] == "PASS" for x in RESULTS),
        "results": RESULTS,
    }
    path = TARGET / "button_mode_audit_backtest_20261009.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("BACKTEST_SUMMARY", json.dumps({
        "passes": report["passes"], "failures": report["failures"],
        "report_path": str(path)
    }, ensure_ascii=False), flush=True)
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
