"""Shared fixtures and builders for Koel unit tests."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from koel.domain import (
    AlertRule,
    AlertType,
    Disclosure,
    PreviousPriceState,
    PriceSnapshot,
)


@pytest.fixture
def now_utc() -> datetime:
    return datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC)


def make_rule(
    *,
    id: int = 1,
    user_id: int = 10,
    telegram_id: int = 1001,
    symbol: str = "JKH.N0000",
    type: AlertType = AlertType.PRICE_ABOVE,
    threshold: float | None = 100.0,
    category: str | None = None,
    ref_price: float | None = None,
    active: bool = True,
    armed: bool = True,
    created_at: datetime | None = None,
) -> AlertRule:
    return AlertRule(
        id=id,
        user_id=user_id,
        telegram_id=telegram_id,
        symbol=symbol,
        type=type,
        threshold=threshold,
        category=category,
        ref_price=ref_price,
        active=active,
        armed=armed,
        created_at=created_at,
    )


def make_snapshot(
    *,
    symbol: str = "JKH.N0000",
    price: float = 100.0,
    previous_close: float | None = 98.0,
    change: float | None = None,
    change_pct: float | None = None,
    volume: float | None = 1000.0,
    ts: datetime | None = None,
    id: int | None = 42,
) -> PriceSnapshot:
    return PriceSnapshot(
        symbol=symbol,
        price=price,
        previous_close=previous_close,
        change=change,
        change_pct=change_pct,
        volume=volume,
        ts=ts or datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
        id=id,
    )


def make_previous(
    *,
    price: float | None = 95.0,
    change_pct: float | None = None,
    move_fired_keys: set[str] | None = None,
    activity_fired_keys: set[str] | None = None,
    high_52w: float | None = None,
    low_52w: float | None = None,
    sma_by_period: dict[int, float] | None = None,
) -> PreviousPriceState:
    return PreviousPriceState(
        price=price,
        change_pct=change_pct,
        move_fired_keys=move_fired_keys or set(),
        activity_fired_keys=activity_fired_keys or set(),
        high_52w=high_52w,
        low_52w=low_52w,
        sma_by_period=sma_by_period or {},
    )


def make_disclosure(
    *,
    external_id: str = "ann-99",
    symbol: str = "JKH.N0000",
    title: str = "Quarterly Results",
    category: str | None = None,
    url: str = "https://www.cse.lk/announcements#99",
    published_at: datetime | None = None,
    seen_at: datetime | None = None,
) -> Disclosure:
    ts = datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC)
    return Disclosure(
        external_id=external_id,
        symbol=symbol,
        title=title,
        category=category,
        url=url,
        published_at=published_at or ts,
        seen_at=seen_at or ts,
    )


def claim_unsent_deque(rows: list[dict]) -> AsyncMock:
    """Mock claim_unsent_batch that depletes rows (limit=1 loop-safe)."""
    queue = list(rows)

    async def _claim(*, limit: int = 50, lease_seconds: int = 120) -> list[dict]:
        if not queue:
            return []
        batch = queue[:limit]
        del queue[:limit]
        return batch

    return AsyncMock(side_effect=_claim)
