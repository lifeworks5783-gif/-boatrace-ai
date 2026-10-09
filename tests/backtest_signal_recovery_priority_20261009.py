#!/usr/bin/env python3
"""Recovery-FIRST signal counterfactual over official saved beforeinfo-derived scores.

No historical result, payout or finish order is read. The code being tested
is unmodified. Observability gating is tested as a simulated policy in the
test only; there is NO production scoring, signal or bet mutation.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collectors"))
from recovery_live_overlay import load_verified_recovered_live
from build_latest_prediction_view import (
    build_up_signal, build_down_signal, build_signal_ai_prediction,
    load_signal_ai_config,
)
from race_prediction_store import audit_race

DATE = "20261009"
OUT = ROOT / "_audit_backtest"
OUT.mkdir(parents=True, exist_ok=True)


def decide_quality(boats, *, structural_fallback=False, assumed_scores=False):
    """PROPOSED gate only: trust source completeness, not any fallback warning."""
    if assumed_scores:
        return None
    if len(boats) != 6:
        return None
    for row in boats:
        if any(row.get(k) is None for k in (
            "morning_score_reference", "score",
            "exhibition_course", "exhibition_time", "exhibition_st",
        )):
            return None
    return {"status": "provisional_structural_fallback" if structural_fallback else "normal",
            "recovery_needed": structural_fallback,
            "fallback_source": "saved_morning_structural_component" if structural_fallback else None}


def main():
    official = load_verified_recovered_live(DATE)
    config = load_signal_ai_config()
    verdict = Counter()
    examples = []
    mismatches = []
    for rid, replay in official.items():
        boats = replay["boats"]
        if len(boats) != 6:
            verdict["official_verified_scratch"] += 1
            continue
        real_up = build_up_signal(boats, replay["prediction_quality"])
        real_down = build_down_signal(boats, replay["prediction_quality"])
        if real_up.get("available") is not True or real_down.get("available") is not True:
            raise AssertionError(f"Official complete scores must evaluate signals {rid}")

        is_signal = bool(real_up.get("active") or real_down.get("active"))
        verdict["official_six_boat_verified"] += 1
        verdict["official_true_trigger"] += int(is_signal)
        verdict["official_true_nontrigger"] += int(not is_signal)
        if is_signal:
            real_ai = build_signal_ai_prediction(boats, real_up, real_down, config)
            assert len(real_ai["combinations"]) == 24, (rid, "real ticket count")

        # Historical current behavior even when all six official exhibition fields
        # and calculated live scores exist, but ONLY structural 80% used morning.
        legacy_quality = {"status": "fallback", "recovery_needed": True,
                          "fallback_source": "saved_morning_structural_component"}
        old_up = build_up_signal(boats, legacy_quality)
        old_down = build_down_signal(boats, legacy_quality)
        if old_up.get("available") or old_down.get("available"):
            raise AssertionError(f"Expected suppression regression not reproduced {rid}")
        if is_signal:
            verdict["true_trigger_suppressed_by_warning_only"] += 1

        candidate_quality = decide_quality(boats, structural_fallback=True)
        if candidate_quality is None:
            raise AssertionError(f"Official complete row could not be admitted {rid}")
        new_up = build_up_signal(boats, candidate_quality)
        new_down = build_down_signal(boats, candidate_quality)
        if new_up["level"] != real_up["level"] or new_down["level"] != real_down["level"]:
            mismatches.append({"race_id": rid, "expected": (real_up["level"], real_down["level"]),
                               "actual": (new_up["level"], new_down["level"])})
        if is_signal:
            verdict["rescued_verified_signal"] += 1
            pred = build_signal_ai_prediction(boats, new_up, new_down, config)
            assert len(pred["combinations"]) == 24
            expected = f"F{real_down['level']}R{real_up['level']}"
            assert pred["signal_key"] == expected
            if len(examples) < 8:
                examples.append({"race_id": rid, "signal": expected,
                                 "raijin_boats": [r["boat"] for r in new_up.get("candidates", [])]})

    # CRITICAL counterexample: morning score disguised as live without official data
    # must NOT be converted into "non-trigger" by simply dropping quality gate.
    sample = next(row["boats"] for row in official.values() if len(row["boats"]) == 6)
    morning_disguised = [{
        **b, "score": b["morning_score_reference"],
        "exhibition_course": None, "exhibition_time": None, "exhibition_st": None,
    } for b in sample]
    bad_naive_up = build_up_signal(morning_disguised, {"status": "normal", "recovery_needed": False})
    bad_naive_down = build_down_signal(morning_disguised, {"status": "normal", "recovery_needed": False})
    assert bad_naive_up["available"] and bad_naive_down["available"]
    assert bad_naive_up["level"] == 0 and bad_naive_down["level"] == 0
    verdict["naive_missing_data_falsely_classified_as_nontrigger"] += 1
    assert decide_quality(morning_disguised, assumed_scores=True) is None
    verdict["proposed_no_data_guard_rejects_false_nontrigger"] += 1

    # One component missing must be recognized as provisional, not silently
    # full official observation. A reconstruction model is required; this
    # test proves no valid numerical estimate exists from the stored score alone.
    missing_st = [{**b} for b in sample]
    missing_st[0]["exhibition_st"] = None
    assert decide_quality(missing_st, structural_fallback=True) is None
    verdict["single_missing_exhibition_component_requires_estimation"] += 1

    report = {
        "date": DATE, "scope": "official pre-race replay and counterfactual signal gating",
        "source": "recovery_live_overlay.py official beforeinfo-derived live scores (no race result input)",
        "verdict": dict(verdict), "mismatches": mismatches,
        "example_recovered_signals": examples,
        "safety": "No score, signal or historical betting data modified. Full exhibition record = complete; missing exhibition requires separately validated numerical estimator."
    }
    (OUT / "signal_recovery_counterfactual_20261009.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RECOVERY_FIRST_BACKTEST", json.dumps(report, ensure_ascii=False), flush=True)
    assert not mismatches, mismatches
    assert verdict["official_six_boat_verified"] >= 30
    assert verdict["true_trigger_suppressed_by_warning_only"] >= 1
    assert verdict["true_trigger_suppressed_by_warning_only"] == verdict["rescued_verified_signal"]
    print("RECOVERY_FIRST_BACKTEST_PASS", dict(verdict), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
