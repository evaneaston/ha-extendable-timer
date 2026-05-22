"""Pure-Python decision helpers for extendable_timer.

No Home Assistant imports — these run in unit tests without a HA core.
"""

import math
from datetime import datetime, timedelta
from enum import Enum


class StartupCase(Enum):
    """Result of classify_startup_state — drives async_setup_entry branching."""

    IDLE = "idle"
    FUTURE = "future"
    STALE_WITHIN_THRESHOLD = "stale_within_threshold"
    STALE_BEYOND_THRESHOLD = "stale_beyond_threshold"


def compute_extended_finish(
    *,
    now: datetime,
    current_finishes_at: datetime | None,
    extend_seconds: int,
) -> datetime:
    """Return the new finishes_at after pressing extend.

    Idle (no current finish) or persisted finish in the past — start fresh
    from now. Active (finish in future) — add to the existing finish.
    """
    if current_finishes_at is None or current_finishes_at < now:
        base = now
    else:
        base = current_finishes_at
    return base + timedelta(seconds=extend_seconds)


def classify_startup_state(
    *,
    now: datetime,
    persisted_finishes_at: datetime | None,
    stale_threshold_seconds: int,
) -> tuple[StartupCase, int]:
    """Classify what to do at async_setup_entry given persisted state.

    Returns (case, staleness_seconds). staleness_seconds is 0 for IDLE
    and FUTURE; for stale cases it's max(0, (now - persisted).total_seconds())
    rounded to int.

    stale_threshold_seconds == 0 means "never fire stale" — any past
    expiry is classified as STALE_BEYOND_THRESHOLD regardless of how
    recently it expired.
    """
    if persisted_finishes_at is None:
        return StartupCase.IDLE, 0
    if persisted_finishes_at > now:
        return StartupCase.FUTURE, 0
    staleness = int((now - persisted_finishes_at).total_seconds())
    if stale_threshold_seconds == 0:
        return StartupCase.STALE_BEYOND_THRESHOLD, staleness
    if staleness <= stale_threshold_seconds:
        return StartupCase.STALE_WITHIN_THRESHOLD, staleness
    return StartupCase.STALE_BEYOND_THRESHOLD, staleness


def compute_remaining_seconds(*, now: datetime, finishes_at: datetime | None) -> int:
    """Whole seconds until the timer expires, rounded UP for display.

    Countdown displays should show the largest integer that hasn't been
    reached yet — `int(14.9)` would read as "14" the instant after a 15s
    extend, which is wrong. Returns 0 when idle or already past finish.
    """
    if finishes_at is None:
        return 0
    delta = (finishes_at - now).total_seconds()
    if delta <= 0:
        return 0
    return math.ceil(delta)
