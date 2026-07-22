"""Feed health state machine + gap annotation (W6)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from koel.feed_health import (
    FeedHealth,
    FeedState,
    annotate_move_trigger,
    gap_seconds,
)


def test_degrade_after_failures() -> None:
    fh = FeedHealth(degrade_after_failures=3)
    assert fh.record_fail() == FeedState.STALE
    assert fh.record_fail() == FeedState.STALE
    assert fh.record_fail() == FeedState.DEGRADED
    assert "delayed" in fh.degradation_message().lower()


def test_recovery_path() -> None:
    fh = FeedHealth(degrade_after_failures=2)
    fh.record_fail()
    fh.record_fail()
    assert fh.state == FeedState.DEGRADED
    assert fh.record_ok() == FeedState.RECOVERING
    assert fh.record_ok() == FeedState.LIVE
    assert "healthy" in fh.recovery_message().lower()


def test_notice_cooldown() -> None:
    now = datetime(2026, 7, 21, 10, 0, tzinfo=UTC)
    fh = FeedHealth(degrade_after_failures=1)
    fh.record_fail(now=now)
    assert fh.should_broadcast_notice(now=now) is True
    fh.mark_notice_sent(now=now)
    assert fh.should_broadcast_notice(now=now + timedelta(minutes=5)) is False
    assert fh.should_broadcast_notice(now=now + timedelta(minutes=31)) is True


def test_gap_annotation() -> None:
    trigger = "daily move up 5.00% (threshold 5.00%)"
    assert annotate_move_trigger(trigger, gap_sec=60) == trigger
    annotated = annotate_move_trigger(trigger, gap_sec=2400)
    assert "last reading" in annotated
    assert "40 min" in annotated


def test_gap_seconds() -> None:
    a = datetime(2026, 7, 21, 10, 0, tzinfo=UTC)
    b = datetime(2026, 7, 21, 10, 30, tzinfo=UTC)
    assert gap_seconds(a, b) == 1800.0
    assert gap_seconds(None, b) is None
