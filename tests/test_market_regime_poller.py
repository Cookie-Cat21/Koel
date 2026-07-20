"""Unit tests for Poller._poll_market_regime (mocked storage)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from koel.domain import MARKET_SYMBOL, AlertEvent, AlertRule, AlertType
from koel.poller import Poller


def _rule(alert_type: AlertType, threshold: float, rule_id: int) -> AlertRule:
    return AlertRule(
        id=rule_id,
        user_id=1,
        telegram_id=9001,
        symbol=MARKET_SYMBOL,
        type=alert_type,
        threshold=threshold,
        active=True,
        created_at=datetime.now(tz=UTC),
    )


def _poller(storage: Any) -> Poller:
    settings = MagicMock()
    cse = MagicMock()
    send = AsyncMock(return_value=True)
    p = Poller(settings=settings, storage=storage, cse=cse, send=send)
    p._queue_sends = True
    p._pending_sends = []
    return p


@pytest.mark.asyncio
async def test_poll_market_regime_claims_appetite() -> None:
    storage = MagicMock()
    storage.active_rules_for_symbols = AsyncMock(
        return_value=[_rule(AlertType.APPETITE_BAND, 60, 101)]
    )
    storage.list_market_appetite_daily = AsyncMock(
        return_value=[{"score": 72.0, "trade_date": "2026-07-16"}]
    )
    storage.list_market_daily_summary = AsyncMock(return_value=[])
    storage.market_book_imbalance_pct = AsyncMock(return_value=None)
    storage.latest_macro_change_pct = AsyncMock(return_value=None)
    storage.market_regime_fired_keys = AsyncMock(return_value=set())
    storage.claim_alert = AsyncMock(return_value=555)

    p = _poller(storage)
    # Bypass full claim path internals — stub _claim_and_send.
    claimed: list[AlertEvent] = []

    async def _claim(event: AlertEvent, *, disarm: bool = False) -> bool:
        claimed.append(event)
        return True

    p._claim_and_send = _claim  # type: ignore[method-assign]

    fired, ok = await p._poll_market_regime()
    assert ok is True
    assert len(fired) == 1
    assert fired[0].type == AlertType.APPETITE_BAND
    assert len(claimed) == 1


@pytest.mark.asyncio
async def test_poll_market_regime_noop_without_rules() -> None:
    storage = MagicMock()
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    p = _poller(storage)
    fired, ok = await p._poll_market_regime()
    assert fired == []
    assert ok is True
    storage.list_market_appetite_daily.assert_not_called()


@pytest.mark.asyncio
async def test_poll_market_regime_rules_load_failure() -> None:
    storage = MagicMock()
    storage.active_rules_for_symbols = AsyncMock(side_effect=RuntimeError("db down"))
    p = _poller(storage)
    fired, ok = await p._poll_market_regime()
    assert fired == []
    assert ok is False


@pytest.mark.asyncio
async def test_poll_market_regime_full_inputs_fires_oil() -> None:
    rule = _rule(AlertType.OIL_MOVE, 1.0, 303)
    storage = MagicMock()
    storage.active_rules_for_symbols = AsyncMock(return_value=[rule])
    storage.list_market_appetite_daily = AsyncMock(return_value=[])
    storage.list_market_daily_summary = AsyncMock(return_value=[])
    storage.market_book_imbalance_pct = AsyncMock(return_value=None)
    storage.latest_macro_change_pct = AsyncMock(
        side_effect=lambda sid: 3.5 if sid == "BRENT_SPOT" else None
    )
    storage.market_regime_fired_keys = AsyncMock(return_value=set())
    p = _poller(storage)
    claimed: list[AlertEvent] = []

    async def _claim(event: AlertEvent, *, disarm: bool = False) -> bool:
        claimed.append(event)
        return True

    p._claim_and_send = _claim  # type: ignore[method-assign]
    fired, ok = await p._poll_market_regime()
    assert ok is True
    assert len(fired) == 1
    assert fired[0].type == AlertType.OIL_MOVE
    assert len(claimed) == 1


@pytest.mark.asyncio
async def test_poll_market_regime_respects_fired_keys() -> None:
    rule = _rule(AlertType.FOREIGN_FLOW, 1_000_000, 202)
    day_key_prefix = f"foreign_flow:{rule.id}:"
    storage = MagicMock()
    storage.active_rules_for_symbols = AsyncMock(return_value=[rule])
    storage.list_market_appetite_daily = AsyncMock(return_value=[])
    storage.list_market_daily_summary = AsyncMock(
        return_value=[{"foreign_net": -5_000_000.0}]
    )
    storage.market_book_imbalance_pct = AsyncMock(return_value=None)
    storage.latest_macro_change_pct = AsyncMock(return_value=None)
    # Pre-seed a matching day key so evaluate skips.
    from zoneinfo import ZoneInfo

    day = datetime.now(tz=ZoneInfo("Asia/Colombo")).date().isoformat()
    storage.market_regime_fired_keys = AsyncMock(
        return_value={f"{day_key_prefix}{day}"}
    )

    p = _poller(storage)
    p._claim_and_send = AsyncMock(return_value=True)  # type: ignore[method-assign]
    fired, ok = await p._poll_market_regime()
    assert ok is True
    assert fired == []
    p._claim_and_send.assert_not_called()
