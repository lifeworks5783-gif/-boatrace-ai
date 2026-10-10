"""Fail-closed finished-race signal audit across scores, saved AI, PDCA and HTML.

One research race has one normal-score-based Fujin/Raijin judgement. A true
verified F0R0 is not turned into a high-payout signal retrospectively.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from pathlib import Path

from build_latest_prediction_view import build_up_signal, build_down_signal
from race_prediction_store import audit_race


def race_code(value: object) -> str:
    value = str(value or "")
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits[:12] if len(digits) >= 12 else ""


def csv_rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise RuntimeError(f"Official/signal CSV missing: {path}")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def int_value(value: object) -> int:
    try:
        return int(float(str(value)))
    except (ValueError, TypeError):
        return 0


def saved_history(root: Path, date: str) -> dict[str, dict]:
    file = root / "evaluations" / "fujin_raijin" / "latest" / "backtest_details.csv"
    return {
        race_code(x.get("race_id")): x for x in csv_rows(file)
        if str(x.get("date")) == date and race_code(x.get("race_id"))
    }


def published_cards(path: Path, valid_venues: dict[str, str]) -> dict[str, dict]:
    if not path.is_file():
        raise RuntimeError(f"Race comparison was not rendered: {path}")
    raw = path.read_text(encoding="utf-8")
    by_venue_race = {(venue, int(race)): key for key, (venue, race)
                     in valid_venues.items()}
    output = {}
    for match in re.finditer(r'<article class="race-card">(.*?)</article>', raw, re.S):
        card = match.group(1)
        head = re.search(r'<div class="race-title">(.*?)</div>', card, re.S)
        if head is None:
            raise RuntimeError("Rendered race card has no venue/race title")
        title = html.unescape(re.sub(r'<[^>]+>', '', head.group(1)))
        title = re.sub(r'\s+', ' ', title).strip()
        match_name = re.match(r'(.+?)\s+(\d+)R', title)
        if match_name is None:
            raise RuntimeError(f"Unrecognizable race title: {title}")
        key = by_venue_race.get((match_name.group(1), int(match_name.group(2))))
        if not key:
            raise RuntimeError(f"Public card not grounded in saved official result: {title}")
        if key in output:
            raise RuntimeError(f"Duplicate public race card: {key}")
        title_html = head.group(1)
        raijin = re.search(r'<span class="signal-row raijin[^"]*"[^>]*>(.*?)</span>', title_html, re.S)
        fujin = re.search(r'<span class="signal-row fujin[^"]*"[^>]*>(.*?)</span>', title_html, re.S)
        output[key] = {
            "raijin_level": (raijin.group(1).count("⚡") if raijin else 0),
            "fujin_level": (fujin.group(1).count("💨") if fujin else 0),
            "badge_not_triggered": "5千円以上・未発動" in title_html,
            "badge_unobservable": "5千円以上・未判定" in title_html,
            "badge_caught": ("5千円以上捕捉" in title_html or "5千円以上・事後捕捉" in title_html),
            "explanation": "シグナル非発動の判定根拠" in card,
            "awaiting_official_live": "直前シグナル再照合待ち" in card,
        }
    return output


def audit(date: str, root: Path, rendered: Path | None) -> dict:
    if not re.fullmatch(r"\d{8}", date):
        raise ValueError("Expected YYYYMMDD date")
    folder = Path(date[:4]) / date[4:6] / date[6:8]
    canonical_path = root / "predictions" / folder / "live" / f"formation_predictions_final_{date}.json"
    if not canonical_path.is_file():
        raise RuntimeError(f"Canonical signal model absent: {canonical_path}")
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    by_id = {
        race_code(r.get("race_id")): r for r in canonical.get("races", [])
        if race_code(r.get("race_id"))
    }
    history = saved_history(root, date)
    official = csv_rows(root / "archive" / folder / f"results_{date}_all.csv")
    finished = {}
    for row in official:
        key = race_code(row.get("race_id"))
        if not key:
            continue
        if key in finished:
            raise RuntimeError(f"Duplicate official result: {key}")
        finished[key] = row

    valid_venues = {
        key: (row.get("venue_name") or "", int_value(row.get("race")))
        for key, row in finished.items()
    }
    # The public page may already show an external payout newly announced
    # AFTER the last official result import. Identify those races through the
    # official morning program; never call them fake or a false F0R0.
    program = root / "daily_inputs" / folder / "base" / f"program_races_{date}.csv"
    if program.is_file():
        for row in csv_rows(program):
            key = race_code(row.get("race_id"))
            if key and key not in valid_venues:
                valid_venues[key] = (
                    row.get("venue_name") or "", int_value(row.get("race"))
                )
    cards = published_cards(rendered, valid_venues) if rendered else None
    inconsistencies = []
    checked = []
    triggered = 0
    no_signal = 0
    high_payout_no_signal = 0

    for key, result in sorted(finished.items()):
        record = by_id.get(key)
        if not record:
            inconsistencies.append({"race_id": key, "error": "missing_canonical_prediction"})
            continue
        quality = record.get("prediction_quality") or {}
        boats = record.get("boats") or []
        if (record.get("prediction_type") != "直前"
                or quality.get("status") == "fallback"
                or quality.get("signal_blocked") is True
                or len(boats) not in (5, 6)):
            inconsistencies.append({"race_id": key, "error": "incomplete_live_scores_or_fallback"})
            continue

        saved_up = record.get("up_signal") or {}
        saved_down = record.get("down_signal") or {}
        expected_up = build_up_signal(boats, quality)
        expected_down = build_down_signal(boats, quality)
        raijin, fujin = int_value(saved_up.get("level")), int_value(saved_down.get("level"))
        check_up, check_down = int_value(expected_up.get("level")), int_value(expected_down.get("level"))
        independent = history.get(key)
        if not independent:
            inconsistencies.append({"race_id": key, "error": "missing_independent_pdca_row"})
            continue
        pdca_levels = [int_value(independent.get("raijin_level")), int_value(independent.get("fujin_level"))]
        if (raijin, fujin) != (check_up, check_down):
            inconsistencies.append({"race_id": key, "error": "saved_signal_not_equal_to_score_recompute",
                                    "saved": [raijin, fujin], "computed": [check_up, check_down]})
        if [raijin, fujin] != pdca_levels:
            inconsistencies.append({"race_id": key, "error": "saved_signal_not_equal_to_pdca",
                                    "saved": [raijin, fujin], "pdca": pdca_levels})
        if saved_up.get("available") is not True or saved_down.get("available") is not True:
            inconsistencies.append({"race_id": key, "error": "finished_race_signal_is_unobservable"})
        state = audit_race(record)
        if (raijin or fujin) and state.get("signal_ai_status") != "ready":
            inconsistencies.append({"race_id": key, "error": "active_signal_has_no_saved_24_picks",
                                    "status": state.get("signal_ai_status")})
        if cards is not None:
            card = cards.get(key)
            if not card:
                inconsistencies.append({"race_id": key, "error": "missing_public_race_card"})
            else:
                displayed = [card["raijin_level"], card["fujin_level"]]
                if displayed != [raijin, fujin]:
                    inconsistencies.append({"race_id": key, "error": "public_signal_icons_do_not_match",
                                            "saved": [raijin, fujin], "public": displayed})
                payout = int_value(result.get("trifecta_pay"))
                if payout >= 5000:
                    expected_miss = not bool(raijin or fujin)
                    if card["badge_not_triggered"] != expected_miss or card["badge_unobservable"]:
                        inconsistencies.append({"race_id": key, "error": "false_public_payout_signal_badge"})
                if not (raijin or fujin) and not card["explanation"]:
                    inconsistencies.append({"race_id": key, "error": "missing_visible_no_signal_explanation"})

        payout = int_value(result.get("trifecta_pay"))
        if raijin or fujin:
            triggered += 1
        else:
            no_signal += 1
            if payout >= 5000:
                high_payout_no_signal += 1
        checked.append({
            "race_id": key, "fujin_level": fujin, "raijin_level": raijin,
            "payout_yen": payout,
            "status": "validated_signal" if (raijin or fujin) else "validated_no_signal",
            "source": (quality.get("provenance") or "saved_live"),
        })

    external_payout_waiting = []
    external_payout_with_valid_scores = 0
    if cards is not None:
        for key in sorted(set(cards) - set(finished)):
            record = by_id.get(key)
            if not record:
                inconsistencies.append({"race_id": key, "error": "payout_only_without_canonical_race"})
                continue
            up, down = record.get("up_signal") or {}, record.get("down_signal") or {}
            ready = (record.get("prediction_type") == "直前"
                     and up.get("available") is True and down.get("available") is True)
            expected_levels = [int_value(up.get("level")), int_value(down.get("level"))]
            card = cards[key]
            if [card["raijin_level"], card["fujin_level"]] != expected_levels:
                inconsistencies.append({"race_id": key, "error": "new_external_payout_badge_not_canonical",
                                        "canonical": expected_levels,
                                        "displayed": [card["raijin_level"], card["fujin_level"]]})
            if not ready:
                external_payout_waiting.append(key)
                if not card["awaiting_official_live"]:
                    inconsistencies.append({"race_id": key, "error": "new_result_missing_recovery_pending_mark"})
                if card["badge_not_triggered"]:
                    inconsistencies.append({"race_id": key, "error": "new_result_falsely_labeled_signal_off"})
            else:
                external_payout_with_valid_scores += 1
                quality = record.get("prediction_quality") or {}
                scored_boats = record.get("boats") or []
                computed = [
                    int_value(build_up_signal(scored_boats, quality).get("level")),
                    int_value(build_down_signal(scored_boats, quality).get("level")),
                ]
                if computed != expected_levels:
                    inconsistencies.append({
                        "race_id": key, "error": "new_external_payout_signal_differs_from_six_boat_scores",
                        "saved": expected_levels, "computed": computed,
                    })
                if any(expected_levels) and audit_race(record).get("signal_ai_status") != "ready":
                    inconsistencies.append({"race_id": key, "error": "new_external_payout_missing_signal_24"})
                if not any(expected_levels) and not card["explanation"]:
                    inconsistencies.append({"race_id": key, "error": "new_external_payout_missing_validated_no_signal_reason"})
    return {
        "date": date, "audit": "Fujin_Raijin_score_PDCA_public_parity",
        "status": "PASS" if not inconsistencies else "FAIL",
        "finished_races": len(finished),
        "validated": len(checked),
        "signal_active": triggered,
        "validated_no_signal": no_signal,
        "validated_no_signal_payout_5000plus": high_payout_no_signal,
        "public_page_checked": bool(rendered),
        "published_external_payouts_awaiting_recovery": len(external_payout_waiting),
        "published_external_payouts_with_verified_scores": external_payout_with_valid_scores,
        "published_external_payout_ids": external_payout_waiting,
        "result_used_to_calculate_scores": False,
        "research_mode": "manual_research",
        "inconsistencies": inconsistencies,
        "per_race": checked,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--html", type=Path, default=None)
    p.add_argument("--output", type=Path, default=None)
    args = p.parse_args()
    result = audit(args.date, args.repo_root, args.html)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("SIGNAL_PARITY_AUDIT", json.dumps({
        k:v for k,v in result.items() if k not in ("per_race", "inconsistencies")
    }, ensure_ascii=False), flush=True)
    for item in result["inconsistencies"][:20]:
        print("SIGNAL_MISMATCH", item, flush=True)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
