"""Keep pre-deadline saved predictions immutable on later page refreshes.

An explicit verified official beforeinfo recovery is the only permitted overlay:
its reconstructed score/signal is labelled retrospective elsewhere, and its
historical normal picks are restored from the previous canonical record.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))


def _time(value):
    if not value:
        return None
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result if result.tzinfo else result.replace(tzinfo=JST)
    except (ValueError, TypeError):
        return None


def preserve_closed_prediction(previous: dict, proposed: dict, now: datetime) -> dict:
    """Retain original pre-deadline record except verified recovery or timely live evidence."""
    if not previous:
        return proposed
    deadline = _time(previous.get("deadline")) or _time(proposed.get("deadline"))
    original_time = _time(previous.get("generated_at"))
    if not deadline or not original_time or original_time > deadline or now < deadline:
        return proposed
    status = (proposed.get("prediction_quality") or {}).get("status")
    if status == "recovered_observation":
        # Once a verified retrospective event has been saved with complete
        # 24-ticket evaluation, keep it tied to its original model version.
        # Known missing/invalid recovery may be repaired explicitly.
        if previous.get("retrospective_signal_recovery"):
            from race_prediction_store import audit_race
            state = audit_race(previous)["signal_ai_status"]
            if state == "ready":
                return previous
        return proposed
    proposed_time = _time(proposed.get("generated_at"))
    current_quality = proposed.get("prediction_quality") or {}
    prior_quality = previous.get("prediction_quality") or {}
    # A previously published "直前・補完" is NOT genuine live evidence.
    # Do not freeze a morning-derived placeholder when verified real live
    # scores were calculated before the original deadline (e.g. race 08-04).
    # This restores the contemporaneous live record, not a later simulation.
    genuine_live = (
        proposed.get("prediction_type") == "直前"
        and proposed_time is not None
        and proposed_time <= deadline
        and current_quality.get("status") == "normal"
        and not current_quality.get("signal_blocked")
        and not current_quality.get("recovery_needed")
        and len(proposed.get("boats") or []) == 6
        and all(
            b.get("score") is not None and not b.get("score_fallback")
            for b in (proposed.get("boats") or [])
        )
    )
    if genuine_live and (
        previous.get("prediction_type") == "朝"
        or prior_quality.get("fallback_source") == "saved_morning_prediction"
        or prior_quality.get("signal_blocked") is True
    ):
        return proposed
    return previous
