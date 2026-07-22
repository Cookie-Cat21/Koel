"""W7: public channel open/close message builders (mocked storage)."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from koel.channel_posts import (
    CHANNEL_CTA,
    build_close_summary,
    build_open_pulse,
    channel_cta_line,
)
from koel.domain import disclaimer

_COLOMBO = ZoneInfo("Asia/Colombo")


@pytest.mark.asyncio
async def test_build_open_pulse_with_indexes() -> None:
    storage = AsyncMock()
    storage.latest_index_snapshots = AsyncMock(
        return_value=[
            {
                "code": "ASPI",
                "name": "All Share",
                "value": 12500.5,
                "change_pct": 0.42,
            },
            {
                "code": "SNP_SL20",
                "name": "S&P SL20",
                "value": 3800.0,
                "change_pct": -0.15,
            },
        ]
    )

    body = await build_open_pulse(storage)

    assert body is not None
    assert "koel open pulse" in body
    assert "CSE is open" in body
    assert "ASPI" in body
    assert "S&P SL20" in body
    assert "+0.42%" in body
    assert disclaimer() in body
    assert CHANNEL_CTA in body or "t.me/" in body
    assert "buy" not in body.lower()
    assert "sell" not in body.lower()


@pytest.mark.asyncio
async def test_build_open_pulse_none_without_indexes() -> None:
    storage = AsyncMock()
    storage.latest_index_snapshots = AsyncMock(return_value=[])

    assert await build_open_pulse(storage) is None


@pytest.mark.asyncio
async def test_build_close_summary_indexes_movers_disclosures() -> None:
    storage = AsyncMock()
    storage.latest_index_snapshots = AsyncMock(
        return_value=[
            {"code": "ASPI", "value": 12600.0, "change_pct": 1.1},
        ]
    )
    storage.list_market_movers = AsyncMock(
        return_value=[
            {"symbol": "JKH.N0000", "price": 101.5, "change_pct": 3.2},
            {"symbol": "COMB.N0000", "price": 140.0, "change_pct": -2.1},
        ]
    )
    storage.count_disclosures_published_since = AsyncMock(return_value=7)
    now = datetime(2026, 7, 20, 14, 45, tzinfo=_COLOMBO)

    body = await build_close_summary(storage, now=now)

    assert body is not None
    assert "koel close summary" in body
    assert date(2026, 7, 20).isoformat() in body
    assert "ASPI" in body
    assert "JKH.N0000" in body
    assert "COMB.N0000" in body
    assert "Disclosures filed today: 7" in body
    assert disclaimer() in body
    assert body.index("Indexes:") < body.index(disclaimer())
    assert CHANNEL_CTA in body or "https://t.me/" in channel_cta_line()


@pytest.mark.asyncio
async def test_build_close_summary_none_when_empty() -> None:
    storage = AsyncMock()
    storage.latest_index_snapshots = AsyncMock(return_value=[])
    storage.list_market_movers = AsyncMock(return_value=[])
    storage.count_disclosures_published_since = AsyncMock(
        side_effect=RuntimeError("db")
    )

    assert await build_close_summary(storage) is None


@pytest.mark.asyncio
async def test_build_open_pulse_fails_soft_on_storage_error() -> None:
    storage = AsyncMock()
    storage.latest_index_snapshots = AsyncMock(side_effect=RuntimeError("boom"))

    assert await build_open_pulse(storage) is None


def test_channel_cta_uses_bot_username(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "koel_cse_bot")
    assert channel_cta_line() == "Get alerts for your stocks → https://t.me/koel_cse_bot"
    monkeypatch.delenv("TELEGRAM_BOT_USERNAME", raising=False)
    assert channel_cta_line() == CHANNEL_CTA
