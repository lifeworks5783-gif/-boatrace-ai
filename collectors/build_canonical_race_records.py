#!/usr/bin/env python3
"""Single read-model for latest and completed race screens.

This is an adapter over the existing *pre-result* formation records. It never
reads results/payouts, changes old predictions, or treats 8 normal tickets as
24 signal tickets. Both screens must load the resulting canonical file.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from production_config import loaded_manifest

JST = timezone(timedelta(hours=9))


def _level(row, key):
    try:
        return max(0, int((row.get(key) or {}).get("level") or 0))
    except (ValueError, TypeError):
        return 0


def signal_key(row):
    f, r = _level(row, "down_signal"), _level(row, "up_signal")
    return f"F{f}R{r}" if f or r else None


def _tickets(signal):
    combos = signal.get("all_120_combinations") or signal.get("combinations") or []
    if not isinstance(combos, list):
        return []
    return [str(item.get("combination") or "") for item in combos[:24] if isinstance(item, dict)]


def _ticket_valid(signal, key):
    tickets = _tickets(signal)
    return (signal.get("signal_key") == key and len(tickets) == 24
            and len(set(tickets)) == 24 and all(len(x.split("-")) == 3 for x in tickets))


def canonicalize(races, *, target_date, config_manifest, signal_ai_config=None):
    if signal_ai_config is None:
        from build_latest_prediction_view import load_signal_ai_config
        signal_ai_config = load_signal_ai_config()
    final = []
    seen = set()
    for original in races:
        row = dict(original)
        rid = str(row.get("race_id") or "")
        if not rid.startswith(target_date + "-") or rid in seen:
            raise ValueError("invalid or duplicate race_id: " + rid)
        seen.add(rid)
        key = signal_key(row)
        signal = row.get("signal_ai_prediction") or {}
        flags = []
        stage = str(row.get("prediction_type") or "")
        quality = row.get("prediction_quality") or {}
        boats = row.get("boats") or []
        is_fallback = quality.get("recovery_needed") or quality.get("status") == "fallback"
        if key:
            if not _ticket_valid(signal, key):
                # Reconstruct from saved pre-result score inputs only.
                # Reconstructed predictions are explicitly distinguishable
                # from tickets actually persisted before the deadline.
                if len(boats) == 6 and not is_fallback:
                    from build_latest_prediction_view import build_signal_ai_prediction
                    result = build_signal_ai_prediction(
                        boats, row.get("up_signal"), row.get("down_signal"), signal_ai_config
                    ) or {}
                    if _ticket_valid(result, key):
                        signal = result
                        row["signal_ai_prediction"] = result
                        row["signal_ai_replay"] = {
                            "source": "saved_pre_result_scored_boats",
                            "replayed_at": datetime.now(JST).isoformat(),
                            "original_ticket_record": False,
                        }
                    else:
                        flags.append("signal_ticket_replay_failed")
                else:
                    flags.append("signal_ticket_input_unavailable")
            if not _ticket_valid(signal, key):
                flags.append("missing_24_signal_tickets")
        elif signal.get("signal_key"):
            flags.append("unexpected_signal_ticket_without_marker")
            row["signal_ai_prediction"] = None

        # Future and completed screens both read this exact decision. Neither
        # screen may independently calculate flags or change a 24-ticket signal
        # race to 8 normal AI tickets.
        row["canonical_signal_source"] = True
        row["canonical_signal_key"] = key
        row["canonical_strategy"] = (
            "signal_ai_24" if key and _ticket_valid(row.get("signal_ai_prediction") or {}, key)
            else ("signal_ai_unresolved" if key else "normal_ai")
        )
        row["canonical_model_manifest"] = config_manifest
        row["canonical_quality"] = {
            "stage": stage,
            "score_recovered": quality.get("status") == "recovered_observation",
            "historical_bet_preserved": bool(row.get("historical_bet_preserved")),
            "flags": flags,
        }
        final.append(row)
    return final


def build(date, root=Path("."), *, fail_on_unresolved=False):
    root = Path(root)
    source = root / "predictions" / date[:4] / date[4:6] / date[6:8] / "live" / f"formation_predictions_final_{date}.json"
    if not source.is_file():
        raise FileNotFoundError(source)
    raw = source.read_bytes()
    payload = json.loads(raw)
    if payload.get("target_date") != date:
        raise ValueError("formation target_date mismatch")
    originals = payload.get("races")
    if not isinstance(originals, list):
        raise ValueError("formation races must be a list")
    rows = canonicalize(originals, target_date=date, config_manifest=loaded_manifest(root))
    unresolved = [row["race_id"] for row in rows if row["canonical_strategy"] == "signal_ai_unresolved"]
    if fail_on_unresolved and unresolved:
        raise ValueError("unresolved signal AI records: " + ", ".join(unresolved[:10]))
    out = {
        "schema_version": "canonical_race_v1",
        "target_date": date,
        "generated_at": datetime.now(JST).isoformat(),
        "source_formation_sha256": hashlib.sha256(raw).hexdigest(),
        "race_count": len(rows),
        "signal_races": sum(bool(row["canonical_signal_key"]) for row in rows),
        "signal_24_ready": sum(row["canonical_strategy"] == "signal_ai_24" for row in rows),
        "signal_24_unresolved": len(unresolved),
        "unresolved_race_ids": unresolved,
        "races": rows,
    }
    destination = root / "predictions" / date[:4] / date[4:6] / date[6:8] / "canonical" / f"race_predictions_{date}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, destination)
    print("canonical:", len(rows), "races, signal:", out["signal_races"],
          "24-ready:", out["signal_24_ready"], "unresolved:", len(unresolved))
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--fail-on-unresolved", action="store_true")
    args = parser.parse_args()
    build(args.date, Path(args.root), fail_on_unresolved=args.fail_on_unresolved)
