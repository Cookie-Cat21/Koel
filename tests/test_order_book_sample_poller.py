"""Unit tests for market order-book sample + tape accrual (Book Pressure)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from koel.config import Settings
from koel.domain import AlertRule, AlertType, OrderBookSnapshot
from koel.poller import Poller


def _settings(**kwargs: object) -> Settings:
    base: dict[str, object] = {
        "telegram_bot_token": "x",
        "database_url": "postgresql://x",
        "poll_jitter_seconds": 0,
        "order_book_sample_size": 3,
    }
    base.update(kwargs)
    return Settings(**base)  # type: ignore[arg-type]


def _book(symbol: str, bids: float = 100.0, asks: float = 80.0) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        symbol=symbol,
        total_bids=bids,
        total_asks=asks,
        ts=datetime.now(tz=UTC),
    )


@pytest.mark.asyncio
async def test_order_book_samples_without_bid_ask_rules() -> None:
    """Book Pressure accrual must not require armed bid_heavy/ask_heavy rules."""
    storage = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    storage.top_symbols_by_recent_volume = AsyncMock(
        return_value=["COMB.N0000", "SAMP.N0000", "DIAL.N0000", "LOLC.N0000"]
    )
    storage.persist_order_book = AsyncMock(side_effect=lambda b: b)
    storage.order_book_fired_keys = AsyncMock(return_value=set())

    cse = AsyncMock()
    cse.fetch_order_book = AsyncMock(side_effect=lambda sym: _book(sym))

    poller = Poller(_settings(), storage, cse, AsyncMock(return_value=True))
    fired, ok = await poller._poll_order_books()

    assert ok is True
    assert fired == []
    assert cse.fetch_order_book.await_count == 3
    assert storage.persist_order_book.await_count == 3
    # No rules → never look up fired keys / evaluate.
    storage.order_book_fired_keys.assert_not_awaited()


@pytest.mark.asyncio
async def test_order_book_priority_rules_always_included() -> None:
    storage = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["RULE.N0000", "JKH.N0000"])
    storage.active_rules_for_symbols = AsyncMock(
        return_value=[
            AlertRule(
                id=1,
                user_id=1,
                telegram_id=9001,
                symbol="RULE.N0000",
                type=AlertType.BID_HEAVY,
                threshold=1.5,
                active=True,
                created_at=datetime.now(tz=UTC),
            )
        ]
    )
    storage.top_symbols_by_recent_volume = AsyncMock(
        return_value=["A.N0000", "B.N0000", "C.N0000"]
    )
    storage.persist_order_book = AsyncMock(side_effect=lambda b: b)
    storage.order_book_fired_keys = AsyncMock(return_value=set())

    fetched: list[str] = []

    async def _fetch(sym: str) -> OrderBookSnapshot:
        fetched.append(sym)
        return _book(sym, bids=200.0, asks=50.0)

    cse = AsyncMock()
    cse.fetch_order_book = AsyncMock(side_effect=_fetch)

    poller = Poller(_settings(order_book_sample_size=2), storage, cse, AsyncMock())
    poller._claim_and_send = AsyncMock(return_value=True)  # type: ignore[method-assign]
    fired, ok = await poller._poll_order_books()

    assert ok is True
    assert "RULE.N0000" in fetched
    assert len(fetched) == 2
    storage.order_book_fired_keys.assert_awaited_once_with("RULE.N0000")
    assert len(fired) == 1
    assert fired[0].type == AlertType.BID_HEAVY


@pytest.mark.asyncio
async def test_order_book_sample_size_zero_still_polls_rules() -> None:
    storage = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["RULE.N0000"])
    storage.active_rules_for_symbols = AsyncMock(
        return_value=[
            AlertRule(
                id=2,
                user_id=1,
                telegram_id=9001,
                symbol="RULE.N0000",
                type=AlertType.ASK_HEAVY,
                threshold=1.2,
                active=True,
                created_at=datetime.now(tz=UTC),
            )
        ]
    )
    storage.top_symbols_by_recent_volume = AsyncMock(return_value=["X.N0000"])
    storage.persist_order_book = AsyncMock(side_effect=lambda b: b)
    storage.order_book_fired_keys = AsyncMock(return_value=set())
    cse = AsyncMock()
    cse.fetch_order_book = AsyncMock(return_value=_book("RULE.N0000", 10, 100))

    poller = Poller(_settings(order_book_sample_size=0), storage, cse, AsyncMock())
    poller._claim_and_send = AsyncMock(return_value=False)  # type: ignore[method-assign]
    fired, ok = await poller._poll_order_books()
    assert ok is True
    cse.fetch_order_book.assert_awaited_once_with("RULE.N0000")
    assert fired == []


@pytest.mark.asyncio
async def test_poll_tape_accrual_fail_soft() -> None:
    storage = AsyncMock()
    storage.upsert_market_daily_summary = AsyncMock(return_value=1)
    cse = AsyncMock()
    cse.fetch_daily_market_summary = AsyncMock(side_effect=RuntimeError("cse down"))

    poller = Poller(_settings(), storage, cse, AsyncMock())
    with patch("koel.appetite.compute_from_snapshots", new=AsyncMock(return_value=None)):
        # Should not raise when market summary fails.
        await poller._poll_tape_accrual()
    storage.upsert_market_daily_summary.assert_not_awaited()


@pytest.mark.asyncio
async def test_poll_tape_accrual_upserts_summary_and_appetite() -> None:
    storage = AsyncMock()
    storage.upsert_market_daily_summary = AsyncMock(return_value=2)
    cse = AsyncMock()
    cse.fetch_daily_market_summary = AsyncMock(return_value=[{"trade_date": "2026-07-23"}])

    appetite = MagicMock()
    appetite.trade_date = "2026-07-23"
    appetite.score = 55.0
    appetite.universe_n = 12

    poller = Poller(_settings(), storage, cse, AsyncMock())
    with patch(
        "koel.appetite.compute_from_snapshots",
        new=AsyncMock(return_value=appetite),
    ) as compute:
        await poller._poll_tape_accrual()
    storage.upsert_market_daily_summary.assert_awaited_once()
    compute.assert_awaited_once()
