"""CORE-001: disarm after successful claim even when Telegram send fails."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from chime.config import Settings
from chime.domain import AlertType, PreviousPriceState, PriceSnapshot
from chime.poller import Poller
from tests.conftest import make_rule


@pytest.mark.asyncio
async def test_price_cross_disarms_when_send_fails() -> None:
    """Claim succeeds + send fails → rule still disarmed (crossing consumed)."""
    rule = make_rule(type=AlertType.PRICE_ABOVE, threshold=100.0, armed=True)
    snap = PriceSnapshot(
        symbol="JKH.N0000",
        price=105.0,
        previous_close=98.0,
        ts=datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
        id=42,
    )

    storage = AsyncMock()
    storage.claim_and_disarm = AsyncMock(return_value=501)
    storage.mark_alert_attempt = AsyncMock(return_value=1)
    storage.set_rule_armed = AsyncMock()
    storage.insert_snapshot = AsyncMock(side_effect=lambda s: s)
    storage.get_previous_state = AsyncMock(return_value=PreviousPriceState(price=95.0))

    send = AsyncMock(return_value=False)
    settings = Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )
    poller = Poller(settings, storage, AsyncMock(), send)

    fired = await poller._evaluate_price_snaps(
        [snap],
        rules_by_symbol={"JKH.N0000": [rule]},
    )

    assert len(fired) == 1
    storage.claim_and_disarm.assert_awaited_once()
    storage.set_rule_armed.assert_not_awaited()
    storage.mark_alert_attempt.assert_awaited_once_with(501)
    storage.mark_alert_sent.assert_not_awaited()
