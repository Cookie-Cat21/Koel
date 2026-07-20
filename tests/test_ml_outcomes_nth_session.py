"""Unit tests for forecast outcome calendar helpers."""

from __future__ import annotations

from datetime import date

from koel.ml.outcomes import _add_trading_days, _nth_session_after


def test_nth_session_after_on_calendar() -> None:
    cal = [date(2026, 7, 13), date(2026, 7, 14), date(2026, 7, 15), date(2026, 7, 16)]
    assert _nth_session_after(date(2026, 7, 14), 1, cal) == date(2026, 7, 15)
    assert _nth_session_after(date(2026, 7, 14), 2, cal) == date(2026, 7, 16)
    assert _nth_session_after(date(2026, 7, 16), 1, cal) is None


def test_nth_session_after_start_missing() -> None:
    cal = [date(2026, 7, 14), date(2026, 7, 15), date(2026, 7, 16)]
    # start before first session → count n from next
    assert _nth_session_after(date(2026, 7, 13), 1, cal) == date(2026, 7, 14)


def test_add_trading_days_matches_emit_calendar() -> None:
    cal = [date(2026, 7, 13), date(2026, 7, 14), date(2026, 7, 15)]
    assert _add_trading_days(date(2026, 7, 13), 1, cal) == date(2026, 7, 14)
    assert _add_trading_days(date(2026, 7, 15), 1, cal) is None
