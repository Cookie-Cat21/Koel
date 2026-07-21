"""Poller feed state machine + degradation notices for unofficial cse.lk data.

States: LIVE → STALE → DEGRADED → RECOVERING → LIVE.
Drives Telegram/dash honesty when the upstream lags or fails.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

from koel.logging_setup import get_logger

log = get_logger(__name__)

SLT = ZoneInfo("Asia/Colombo")


class FeedState(StrEnum):
    LIVE = "live"
    STALE = "stale"
    DEGRADED = "degraded"
    RECOVERING = "recovering"


@dataclass
class FeedHealth:
    """In-memory feed health for one process (poller)."""

    state: FeedState = FeedState.LIVE
    last_ok_at: datetime | None = None
    last_fail_at: datetime | None = None
    consecutive_failures: int = 0
    notice_sent_at: datetime | None = None
    stale_after: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    degrade_after_failures: int = 3
    notice_cooldown: timedelta = field(default_factory=lambda: timedelta(minutes=30))

    def record_ok(self, *, now: datetime | None = None) -> FeedState:
        now = now or datetime.now(UTC)
        was = self.state
        self.last_ok_at = now
        self.consecutive_failures = 0
        if was in (FeedState.DEGRADED, FeedState.STALE, FeedState.RECOVERING):
            self.state = FeedState.RECOVERING
            # Next ok after recovering flips to LIVE
            if was == FeedState.RECOVERING:
                self.state = FeedState.LIVE
            else:
                # First success after outage → recovering; second call → live
                self.state = FeedState.RECOVERING
        else:
            self.state = FeedState.LIVE
        return self.state

    def record_fail(self, *, now: datetime | None = None) -> FeedState:
        now = now or datetime.now(UTC)
        self.last_fail_at = now
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.degrade_after_failures:
            self.state = FeedState.DEGRADED
        elif self.last_ok_at is not None and now - self.last_ok_at >= self.stale_after:
            self.state = FeedState.STALE
        elif self.state == FeedState.LIVE:
            self.state = FeedState.STALE
        return self.state

    def observe_age(self, *, now: datetime | None = None) -> FeedState:
        """Mark STALE when last success is older than ``stale_after`` (no new fail)."""
        now = now or datetime.now(UTC)
        if self.state == FeedState.DEGRADED:
            return self.state
        if self.last_ok_at is not None and now - self.last_ok_at >= self.stale_after:
            self.state = FeedState.STALE
        return self.state

    def should_broadcast_notice(self, *, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        if self.state not in (FeedState.STALE, FeedState.DEGRADED):
            return False
        if self.notice_sent_at is None:
            return True
        return now - self.notice_sent_at >= self.notice_cooldown

    def mark_notice_sent(self, *, now: datetime | None = None) -> None:
        self.notice_sent_at = now or datetime.now(UTC)

    def degradation_message(self) -> str:
        """User-facing Telegram body. Always NFA."""
        since = ""
        if self.last_ok_at is not None:
            local = self.last_ok_at.astimezone(SLT)
            since = f" since {local.strftime('%H:%M')} SLT"
        if self.state == FeedState.DEGRADED:
            headline = f"⚠️ cse.lk data delayed{since}; alerts may lag."
        else:
            headline = f"⚠️ Market data looks stale{since}; alerts may lag."
        next_hint = "We'll update when the feed recovers."
        return f"{headline} {next_hint}\nNot financial advice — informational only."

    def recovery_message(self) -> str:
        return (
            "✅ Market data feed looks healthy again. Alerts resume on schedule.\n"
            "Not financial advice — informational only."
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "last_ok_at": self.last_ok_at.isoformat() if self.last_ok_at else None,
            "last_fail_at": (
                self.last_fail_at.isoformat() if self.last_fail_at else None
            ),
            "consecutive_failures": self.consecutive_failures,
        }


def gap_seconds(prev_ts: datetime | None, curr_ts: datetime | None) -> float | None:
    """Seconds between two snapshots; None if either missing/unusable."""
    if prev_ts is None or curr_ts is None:
        return None
    try:
        if prev_ts.tzinfo is None:
            prev_ts = prev_ts.replace(tzinfo=UTC)
        if curr_ts.tzinfo is None:
            curr_ts = curr_ts.replace(tzinfo=UTC)
        delta = (curr_ts - prev_ts).total_seconds()
    except Exception:  # noqa: BLE001
        return None
    if delta < 0:
        return None
    return delta


def annotate_move_trigger(trigger: str, *, gap_sec: float | None, gap_warn_sec: float = 1800.0) -> str:
    """Append gap annotation when %-move spans a large poll gap (≥30m default)."""
    if gap_sec is None or gap_sec < gap_warn_sec:
        return trigger
    minutes = int(gap_sec // 60)
    if minutes < 1:
        return trigger
    note = f" (since our last reading {minutes} min ago)"
    if trigger.endswith(note):
        return trigger
    return trigger + note
