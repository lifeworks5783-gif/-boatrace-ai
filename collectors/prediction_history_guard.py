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
        # Caller must preserve original normal tickets and tag retrospective data.
        return proposed
    proposed_time = _time(proposed.get("generated_at"))
    if (
        previous.get("prediction_type") == "朝"
        and proposed.get("prediction_type") == "直前"
        and proposed_time
        and proposed_time <= deadline
    ):
        # Originally captured live prediction can be restored without fabrication.
        return proposed
    return previous
