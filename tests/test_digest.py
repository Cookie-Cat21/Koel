"""Unit tests for EOD digest (mocked storage/send; no live Telegram)."""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from koel.digest import (
    DIGEST_WINDOW_END,
    DIGEST_WINDOW_START,
    format_digest_message,
    in_digest_window,
    maybe_run_eod_digest,
    run_eod_digest,
)
from koel.domain import disclaimer
from koel.notify import SendResult

_COLOMBO = ZoneInfo("Asia/Colombo")


def test_in_digest_window_weekday_after_close() -> None:
    # Monday 2026-07-20 14:45 SLT
    now = datetime(2026, 7, 20, 14, 45, tzinfo=_COLOMBO)
    assert in_digest_window(now) is True
    assert DIGEST_WINDOW_START <= now.time() <= DIGEST_WINDOW_END


def test_in_digest_window_rejects_weekend_and_before_close() -> None:
    saturday = datetime(2026, 7, 18, 15, 0, tzinfo=_COLOMBO)
    morning = datetime(2026, 7, 20, 10, 0, tzinfo=_COLOMBO)
    late = datetime(2026, 7, 20, 17, 0, tzinfo=_COLOMBO)
    assert in_digest_window(saturday) is False
    assert in_digest_window(morning) is False
    assert in_digest_window(late) is False


def test_format_digest_message_includes_nfa_and_sections() -> None:
    body = format_digest_message(
        on_date=date(2026, 7, 20),
        fires=[
            {"symbol": "JKH.N0000", "trigger": "JKH.N0000 crossed above 100"},
        ],
        movers=[{"symbol": "JKH.N0000", "price": 101.5, "change_pct": 2.5}],
        xd_rows=[
            SimpleNamespace(
                symbol="COMB.N0000", d_xd=date(2026, 7, 24), dps=1.5
            )
        ],
    )
    assert "koel EOD digest" in body
    assert "JKH.N0000" in body
    assert "Upcoming XD" in body
    assert "COMB.N0000" in body
    assert disclaimer() in body
    assert body.index("Alerts today") < body.index(disclaimer())


@pytest.mark.asyncio
async def test_run_eod_digest_sends_and_skips_unclaimed() -> None:
    storage = AsyncMock()
    storage.list_digest_users = AsyncMock(
        return_value=[
            {"id": 1, "telegram_id": 9001},
            {"id": 2, "telegram_id": 9002},
        ]
    )
    # First user claimed, second already sent today.
    storage.claim_digest_send = AsyncMock(side_effect=[True, False])
    storage.list_recent_alert_fires = AsyncMock(return_value=[])
    storage.list_watchlist_movers = AsyncMock(return_value=[])
    storage.list_watchlist = AsyncMock(return_value=[])
    storage.list_upcoming_dividend_events = AsyncMock(return_value=[])

    send = AsyncMock(return_value=SendResult.OK)
    now = datetime(2026, 7, 20, 14, 40, tzinfo=_COLOMBO)
    result = await run_eod_digest(storage, send, now=now, force=False)

    assert result.outside_window is False
    assert result.candidates == 2
    assert result.sent == 1
    assert result.skipped == 1
    assert result.errors == 0
    send.assert_awaited_once()
    chat_id, text = send.await_args.args
    assert chat_id == 9001
    assert disclaimer() in text


@pytest.mark.asyncio
async def test_run_eod_digest_outside_window_without_force() -> None:
    storage = AsyncMock()
    send = AsyncMock()
    now = datetime(2026, 7, 20, 10, 0, tzinfo=_COLOMBO)
    result = await run_eod_digest(storage, send, now=now, force=False)
    assert result.outside_window is True
    assert result.sent == 0
    storage.list_digest_users.assert_not_awaited()
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_eod_digest_force_ignores_window() -> None:
    storage = AsyncMock()
    storage.list_digest_users = AsyncMock(
        return_value=[{"id": 1, "telegram_id": 42}]
    )
    storage.claim_digest_send = AsyncMock(return_value=True)
    storage.list_recent_alert_fires = AsyncMock(return_value=[])
    storage.list_watchlist_movers = AsyncMock(return_value=[])
    storage.list_watchlist = AsyncMock(return_value=["JKH.N0000"])
    storage.list_upcoming_dividend_events = AsyncMock(return_value=[])

    send = AsyncMock(return_value=SendResult.OK)
    now = datetime(2026, 7, 20, 10, 0, tzinfo=_COLOMBO)
    result = await run_eod_digest(storage, send, now=now, force=True)
    assert result.outside_window is False
    assert result.sent == 1
    send.assert_awaited_once()


@pytest.mark.asyncio
async def test_maybe_run_eod_digest_noop_outside_window() -> None:
    storage = AsyncMock()
    send = AsyncMock()
    now = datetime(2026, 7, 20, 9, 0, tzinfo=_COLOMBO)
    assert await maybe_run_eod_digest(storage, send, now=now) is None
    storage.list_digest_users.assert_not_awaited()
