"""Unit tests for Yahoo↔CSE hybrid splice (no network / DB)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from koel.domain import DailyBar
from koel.hybrid_backfill import cse_symbol_to_yahoo, splice_bars


def _cse(sym: str, d: date, px: float) -> DailyBar:
    return DailyBar(
        symbol=sym,
        trade_date=d,
        price=px,
        high=px,
        low=px,
        open=px,
        volume=1000.0,
        source_period=5,
        bar_ts=datetime(d.year, d.month, d.day, 9, 0, tzinfo=UTC),
    )


def test_cse_to_yahoo_ticker() -> None:
    assert cse_symbol_to_yahoo("JKH.N0000") == "JKH-N0000.CM"
    assert cse_symbol_to_yahoo("comb.n0000") == "COMB-N0000.CM"
    assert cse_symbol_to_yahoo("ASPI") is None


def test_splice_prefers_cse_and_keeps_older_yahoo() -> None:
    cse = [
        _cse("JKH.N0000", date(2025, 7, 18), 100.0),
        _cse("JKH.N0000", date(2025, 7, 21), 101.0),
    ]
    yahoo = [
        (date(2020, 1, 2), 50.0, 51.0, 49.0, 50.0, 1e6),
        (date(2025, 7, 18), 999.0, None, None, None, None),  # overlap — drop
        (date(2026, 3, 1), 120.0, None, None, None, None),  # after stale cut — drop
    ]
    rows = splice_bars(
        symbol="JKH.N0000",
        cse_bars=cse,
        yahoo_rows=yahoo,
        yahoo_ticker="JKH-N0000.CM",
        stale_cutoff=date(2026, 2, 18),
    )
    by = {r["trade_date"]: r for r in rows}
    assert by[date(2020, 1, 2)]["source"] == "yahoo"
    assert by[date(2020, 1, 2)]["price"] == 50.0
    assert by[date(2025, 7, 18)]["source"] == "cse"
    assert by[date(2025, 7, 18)]["price"] == 100.0
    assert date(2026, 3, 1) not in by
