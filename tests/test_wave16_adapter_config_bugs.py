"""Wave16: medium+ behavioral bugs that 100% coverage still missed.

1. Overflow ``lastTradedTime`` / ``createdDate`` must not abort a whole board
   parse (``_ms_to_dt`` used to raise OSError/ValueError).
2. Non-finite CSE prices must not become ``price_snapshots`` rows.
3. Tiny-but-positive poll/timeout/circuit env knobs must fail closed (``1e-9``
   passes ``> 0`` but hammers cse.lk / poisons httpx).
4. HELP CATEGORY copy must match rule matching (category field, not title).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from structlog.testing import capture_logs

from koel.adapters.cse import (
    AnnouncementRow,
    CSEClient,
    SymbolInfo,
    TradeSummaryRow,
    _ms_to_dt,
    _try_ms_to_dt,
    announcement_to_disclosure,
    symbol_info_to_snapshot,
    trade_row_to_snapshot,
)
from koel.bot import BRIEF_NONE_YET, HELP_TEXT, format_brief_lookup_reply
from koel.config import Settings
from koel.domain import TELEGRAM_SAFE_MAX, disclaimer

_DSN = "postgresql://koel:koel@localhost:5432/koel"


def test_try_ms_to_dt_overflow_returns_none() -> None:
    assert _try_ms_to_dt(10**20) is None
    assert _try_ms_to_dt(2**63) is None


def test_ms_to_dt_overflow_fail_closed_to_epoch() -> None:
    """Disclosure gating: hostile ms must look stale, never raise."""
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    assert _ms_to_dt(10**20) == epoch
    assert _ms_to_dt(2**63) == epoch
    assert _ms_to_dt(None) == epoch


def test_trade_row_overflow_last_traded_uses_now_not_raise() -> None:
    now = datetime(2026, 7, 12, 10, 0, 0, tzinfo=UTC)
    row = TradeSummaryRow(
        symbol="JKH.N0000",
        price=100.0,
        lastTradedTime=10**20,
    )
    snap = trade_row_to_snapshot(row, now=now)
    assert snap is not None
    assert snap.ts == now
    assert snap.price == 100.0


@pytest.mark.parametrize("price", [float("nan"), float("inf"), float("-inf")])
def test_trade_row_rejects_nonfinite_price(price: float) -> None:
    row = TradeSummaryRow(symbol="JKH.N0000", price=price)
    assert trade_row_to_snapshot(row) is None


def test_trade_row_coerces_nonfinite_optional_floats_to_none() -> None:
    row = TradeSummaryRow(
        symbol="JKH.N0000",
        price=100.0,
        percentageChange=float("nan"),
        change=float("inf"),
        previousClose=float("-inf"),
    )
    snap = trade_row_to_snapshot(row)
    assert snap is not None
    assert snap.change_pct is None
    assert snap.change is None
    assert snap.previous_close is None


@pytest.mark.parametrize("price", [float("nan"), float("inf")])
def test_symbol_info_rejects_nonfinite_last_price(price: float) -> None:
    info = SymbolInfo(symbol="JKH.N0000", lastTradedPrice=price)
    assert symbol_info_to_snapshot(info) is None


@pytest.mark.asyncio
async def test_fetch_trade_summary_skips_bad_rows_keeps_good() -> None:
    """One overflow / NaN row must not abort the whole tradeSummary tick."""
    client = CSEClient(client=AsyncMock())
    client._request = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "reqTradeSummery": [
                {"symbol": "BAD.N0000", "price": float("nan")},
                {
                    "symbol": "JKH.N0000",
                    "price": 185.5,
                    "lastTradedTime": 10**20,
                },
                {"symbol": "COMB.N0000", "price": 100.0},
            ]
        }
    )

    with capture_logs() as logs:
        out = await client.fetch_trade_summary()

    symbols = {s.symbol for s in out}
    assert "JKH.N0000" in symbols
    assert "COMB.N0000" in symbols
    assert "BAD.N0000" not in symbols
    assert any(e.get("event") == "cse_trade_row_skipped" for e in logs)


def test_announcement_overflow_created_date_fail_closed() -> None:
    row = AnnouncementRow(
        id=1,
        announcementId=99,
        company="John Keells",
        announcementCategory="Financial",
        createdDate=10**20,
    )
    disc = announcement_to_disclosure(row, symbol="JKH.N0000")
    assert disc is not None
    assert disc.published_at == datetime(1970, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    "raw,poll_ok,timeout_ok,reset_ok",
    [
        ("1e-9", False, False, False),
        ("0.001", False, False, False),
        ("0.5", False, False, False),
        ("4.999", False, True, True),
    ],
)
def test_tiny_positive_poll_knobs_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
    poll_ok: bool,
    timeout_ok: bool,
    reset_ok: bool,
) -> None:
    """Wave16: ``> 0`` alone still allows cse.lk hammer / instant timeouts."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", _DSN)
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", raw)
    monkeypatch.setenv("HTTP_TIMEOUT_SECONDS", raw)
    monkeypatch.setenv("CIRCUIT_RESET_SECONDS", raw)
    settings = Settings.from_env(require_token=True)
    assert settings.poll_interval_seconds == (float(raw) if poll_ok else 5.0)
    assert settings.http_timeout_seconds == (float(raw) if timeout_ok else 15.0)
    assert settings.circuit_reset_seconds == (float(raw) if reset_ok else 60.0)


def test_poll_interval_at_floor_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", _DSN)
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", "5")
    monkeypatch.setenv("HTTP_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("CIRCUIT_RESET_SECONDS", "1")
    settings = Settings.from_env(require_token=True)
    assert settings.poll_interval_seconds == 5.0
    assert settings.http_timeout_seconds == 1.0
    assert settings.circuit_reset_seconds == 1.0


def test_help_category_matches_category_field_not_title() -> None:
    """Users filter on disclosure.category — HELP must not say title substring."""
    assert "CATEGORY = category substring" in HELP_TEXT
    assert "title substring" not in HELP_TEXT


def test_format_brief_lookup_strips_controls_and_clamps_hostile_symbol() -> None:
    """Wave16: hostile DB symbol must not inject C0 or blow Telegram's 4096."""
    hostile = "JKH\x00.N0000\n" + ("X" * 5000)
    msg = format_brief_lookup_reply(
        symbol=hostile,
        brief="B" * 4000,
        title="Filing",
        url="https://www.cse.lk/announcements#1",
    )
    assert "\x00" not in msg
    assert len(msg) < TELEGRAM_SAFE_MAX
    assert msg.endswith(disclaimer())
    assert "filing brief" in msg or BRIEF_NONE_YET in msg
    assert "BB" in msg or "filing brief" in msg


def test_format_brief_lookup_control_only_symbol_falls_back() -> None:
    msg = format_brief_lookup_reply(symbol="\x00\x01", brief="Ready brief body")
    assert msg.startswith("? filing brief")
    assert "Ready brief body" in msg
    assert "\x00" not in msg
    assert msg.endswith(disclaimer())
