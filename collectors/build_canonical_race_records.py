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


def hydrate_recovered_live(originals, *, date, root=Path("."), signal_ai_config=None):
    """Attach recovered *pre-result observations* without rewriting old bets.

    Recovery workflow intentionally leaves the original formation file alone.
    This read-model merges only verified recovered live scores and replays the
    associated F/R signals plus dedicated 24 tickets. Result/payout is NEVER
    read here; normal formation and normal AI purchase remain frozen.
    """
    if signal_ai_config is None:
        from build_latest_prediction_view import load_signal_ai_config
        signal_ai_config = load_signal_ai_config()
    source = (
        Path(root) / "predictions" / date[:4] / date[4:6] / date[6:8]
        / "live" / f"live_predictions_final_{date}.json"
    )
    if not source.is_file():
        return list(originals)

    from build_latest_prediction_view import (
        ranked_boats, build_up_signal, build_down_signal,
        build_signal_ai_prediction,
    )
    payload = json.loads(source.read_text(encoding="utf-8"))
    if str(payload.get("target_date")) != date:
        raise ValueError("restored live prediction date mismatch")

    candidates = {}
    for race in payload.get("races") or []:
        quality = race.get("prediction_quality") or {}
        if quality.get("status") != "recovered_observation":
            continue
        if quality.get("result_leakage") is not False:
            # Do not admit a recovery without an explicit leakage check.
            continue
        if quality.get("provenance") not in (
            "post_result_official_beforeinfo",
            "saved_pre_deadline_official_beforeinfo",
        ):
            continue
        boats = ranked_boats(race)
        if len(boats) != 6:
            continue
        if len({int(b.get("boat") or 0) for b in boats}) != 6:
            continue
        if not all(
            b.get("score") is not None and b.get("morning_score_reference") is not None
            for b in boats
        ):
            continue
        if any(set(b) & {"result", "finish", "payout", "actual_st"} for b in boats):
            continue
        candidates[str(race.get("race_id") or "")] = (race, boats)

    updated = []
    for original in originals:
        row = dict(original)
        rid = str(row.get("race_id") or "")
        if rid not in candidates:
            updated.append(row)
            continue
        old_quality = row.get("prediction_quality") or {}
        # A valid contemporaneous final live prediction must never be
        # replaced by a subsequently recovered/scored version.
        if row.get("prediction_type") == "直前" and not (
            old_quality.get("recovery_needed")
            or old_quality.get("status") in {"fallback", "recovered_observation"}
        ):
            updated.append(row)
            continue

        restored, boats = candidates[rid]
        up = build_up_signal(boats, restored.get("prediction_quality"))
        down = build_down_signal(boats, restored.get("prediction_quality"))
        if not (up.get("available") and down.get("available")):
            updated.append(row)
            continue
        row["boats"] = boats
        row["prediction_type"] = "直前"
        row["prediction_quality"] = restored["prediction_quality"]
        row["up_signal"] = up
        row["down_signal"] = down
        row["signal_ai_prediction"] = build_signal_ai_prediction(
            boats, up, down, signal_ai_config
        )
        row["score_model_version"] = (
            restored.get("score_model_version") or payload.get("model_version")
        )
        row["score_logic_config"] = (
            restored.get("logic_config") or payload.get("logic_config")
        )
        row["retrospective_signal_recovery"] = True
        row["signal_detected_at_original_deadline"] = False
        row["historical_bet_preserved"] = True
        row["signal_recovery_provenance"] = (
            restored["prediction_quality"]["provenance"]
        )
        print("公式直前予測復旧を共通レースへ統合（既存買い目は不変）:", rid)
        updated.append(row)
    return updated


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
                            "replay_model_version": result.get("model_version"),
                            "replay_logic_config": result.get("logic_config_source"),
                            "replay_status": "retrospective_reconstruction_not_original_bet",
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
        if not key and is_fallback and stage == "直前":
            flags.append("live_signal_pending_recovery")

        # Future and completed screens both read this exact decision. Neither
        # screen may independently calculate flags or change a 24-ticket signal
        # race to 8 normal AI tickets.
        row["canonical_signal_source"] = True
        row["canonical_signal_key"] = key
        row["canonical_strategy"] = (
            "signal_ai_24" if key and _ticket_valid(row.get("signal_ai_prediction") or {}, key)
            else ("signal_ai_unresolved" if key
                  else ("live_signal_pending_recovery"
                        if is_fallback and stage == "直前" else "normal_ai"))
        )
        # The currently loaded config is NOT evidence of which weights
        # produced an older score. Preserve original provenance separately.
        original_logic = row.get("score_logic_config")
        row["canonical_model_manifest"] = {
            "read_model_current_configs": config_manifest,
            "source_score_model_version": row.get("score_model_version"),
            "source_score_logic_config": original_logic,
            "source_score_config_identified": bool(
                isinstance(original_logic, dict) and original_logic.get("sha256")
            ),
        }
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
    # Restore pre-result official live observations without changing original
    # stored formation/normal AI; signal AI is an explicitly marked replay.
    hydrated = hydrate_recovered_live(originals, date=date, root=root)
    rows = canonicalize(hydrated, target_date=date, config_manifest=loaded_manifest(root))
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
