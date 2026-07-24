"""Live CSE shadow factor capture helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime

from koel.domain import OrderBookSnapshot, PriceSnapshot
from koel.ml.live_capture import (
    board_to_daily_bars,
    public_book_imbalance,
    select_order_book_symbols,
)


def _price(
    symbol: str,
    *,
    turnover: float,
    volume: float,
) -> PriceSnapshot:
    return PriceSnapshot(
        symbol=symbol,
        price=10.0,
        turnover=turnover,
        volume=volume,
        ts=datetime(2026, 7, 21, tzinfo=UTC),
    )


def test_order_book_panel_excludes_non_company_instruments() -> None:
    board = [
        _price("RIGHT.R0001", turnover=10_000, volume=10_000),
        _price("VOTING.N0000", turnover=5_000, volume=100),
        _price("NONVOTE.X0000", turnover=4_000, volume=1_000),
        _price("WARRANT.W0001", turnover=20_000, volume=20_000),
    ]
    assert select_order_book_symbols(board, limit=2) == [
        "VOTING.N0000",
        "NONVOTE.X0000",
    ]


def test_public_book_imbalance() -> None:
    book = OrderBookSnapshot(
        symbol="A.N0000",
        total_bids=300.0,
        total_asks=100.0,
        ts=datetime(2026, 7, 21, tzinfo=UTC),
    )
    assert public_book_imbalance(book) == 0.5
    empty = book.model_copy(update={"total_bids": 0.0, "total_asks": 0.0})
    assert public_book_imbalance(empty) is None


def test_post_close_bar_conversion_keeps_only_company_shares() -> None:
    board = [
        _price("A.N0000", turnover=100.0, volume=10.0),
        _price("B.X0000", turnover=90.0, volume=9.0),
        _price("RIGHT.R0001", turnover=1000.0, volume=100.0),
    ]
    bars = board_to_daily_bars(board, trade_date=date(2026, 7, 21))
    assert [bar.symbol for bar in bars] == ["A.N0000", "B.X0000"]
    assert all(bar.trade_date == date(2026, 7, 21) for bar in bars)
