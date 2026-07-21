"""Live CSE factor capture for shadow-model research (never sends alerts)."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from koel.adapters.cse import CSEClient
from koel.domain import DailyBar, OrderBookSnapshot, PriceSnapshot
from koel.storage import Storage

COLOMBO = ZoneInfo("Asia/Colombo")
ORDINARY_SUFFIXES = (".N0000", ".X0000")


@dataclass(frozen=True, slots=True)
class LiveCaptureResult:
    captured_at: str
    board_rows: int
    persisted_prices: int
    sector_rows: int
    index_rows: int
    order_book_rows: int
    daily_summary_rows: int
    daily_bars_written: int
    hybrid_bars_written: int
    partial_session: bool


def select_order_book_symbols(
    board: list[PriceSnapshot],
    *,
    limit: int,
) -> list[str]:
    """Stable top-turnover ordinary-share panel for public book capture."""
    if limit <= 0:
        return []
    eligible = [
        snapshot
        for snapshot in board
        if isinstance(snapshot.symbol, str)
        and snapshot.symbol.strip().upper().endswith(ORDINARY_SUFFIXES)
        and snapshot.price > 0
        and math.isfinite(snapshot.price)
    ]
    ordered = sorted(
        eligible,
        key=lambda snapshot: (
            float(snapshot.turnover or 0),
            float(snapshot.volume or 0),
            snapshot.symbol,
        ),
        reverse=True,
    )
    return [snapshot.symbol.strip().upper() for snapshot in ordered[:limit]]


def public_book_imbalance(book: OrderBookSnapshot) -> float | None:
    """Normalized displayed-book imbalance in [-1, 1]."""
    bids = float(book.total_bids)
    asks = float(book.total_asks)
    denominator = bids + asks
    if (
        not math.isfinite(bids)
        or not math.isfinite(asks)
        or bids < 0
        or asks < 0
        or denominator <= 0
    ):
        return None
    return (bids - asks) / denominator


def board_to_daily_bars(
    board: list[PriceSnapshot],
    *,
    trade_date: datetime | date,
) -> list[DailyBar]:
    """Convert the post-close ordinary-share board into CSE daily bars."""
    session_date = (
        trade_date.date() if isinstance(trade_date, datetime) else trade_date
    )
    return [
        DailyBar(
            symbol=snapshot.symbol.strip().upper(),
            trade_date=session_date,
            price=snapshot.price,
            high=snapshot.high,
            low=snapshot.low,
            open=snapshot.open,
            volume=snapshot.volume,
            source_period=5,
            bar_ts=snapshot.ts.astimezone(UTC),
        )
        for snapshot in board
        if snapshot.symbol.strip().upper().endswith(ORDINARY_SUFFIXES)
        and snapshot.price > 0
        and math.isfinite(snapshot.price)
    ]


async def capture_live_factors(
    *,
    storage: Storage,
    cse: CSEClient,
    book_limit: int = 25,
    include_sectors_indexes: bool = True,
    include_daily_summary: bool = False,
    partial_session: bool = True,
) -> LiveCaptureResult:
    """Capture one point-in-time live board/factor observation."""
    board = await cse.fetch_trade_summary()
    persisted = await storage.persist_market_snapshots(board)

    sectors = []
    indexes = []
    if include_sectors_indexes:
        sectors = await cse.fetch_all_sectors()
        await storage.persist_sectors(sectors)
        aspi, snp = await cse.fetch_aspi_data(), await cse.fetch_snp_data()
        indexes = [index for index in (aspi, snp) if index is not None]
        await storage.persist_index_snapshots(indexes)

    book_rows = 0
    for symbol in select_order_book_symbols(board, limit=book_limit):
        book = await cse.fetch_order_book(symbol)
        if book is None or public_book_imbalance(book) is None:
            continue
        await storage.persist_order_book(book)
        book_rows += 1

    summary_rows = 0
    if include_daily_summary:
        summary = await cse.fetch_daily_market_summary()
        summary_rows = await storage.upsert_market_daily_summary(summary)

    daily_bars_written = 0
    hybrid_bars_written = 0
    if not partial_session:
        trade_date = datetime.now(COLOMBO).date()
        bars = board_to_daily_bars(board, trade_date=trade_date)
        daily_bars_written = await storage.persist_daily_bars(bars)
        hybrid_bars_written = await storage.persist_hybrid_daily_bars(
            [
                {
                    "symbol": bar.symbol,
                    "trade_date": bar.trade_date,
                    "price": bar.price,
                    "high": bar.high,
                    "low": bar.low,
                    "open": bar.open,
                    "volume": bar.volume,
                    "source": "cse",
                    "yahoo_ticker": None,
                    "bar_ts": bar.bar_ts,
                }
                for bar in bars
            ]
        )

    return LiveCaptureResult(
        captured_at=datetime.now(COLOMBO).isoformat(),
        board_rows=len(board),
        persisted_prices=len(persisted),
        sector_rows=len(sectors),
        index_rows=len(indexes),
        order_book_rows=book_rows,
        daily_summary_rows=summary_rows,
        daily_bars_written=daily_bars_written,
        hybrid_bars_written=hybrid_bars_written,
        partial_session=partial_session,
    )


def _market_close(now: datetime) -> datetime:
    return datetime.combine(now.date(), time(14, 40), tzinfo=COLOMBO)


async def _run(args: argparse.Namespace) -> None:
    database_url = os.environ.get("ML_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("ML_DATABASE_URL (or DATABASE_URL) is required")
    storage = Storage(database_url)
    await storage.open()
    cycles = max(1, int(args.cycles))
    try:
        async with CSEClient(min_interval_seconds=0.25) as cse:
            cycle = 0
            while True:
                now = datetime.now(COLOMBO)
                close = _market_close(now)
                final_cycle = now >= close
                include_market = cycle % max(1, args.market_every_cycles) == 0
                include_books = cycle % max(1, args.book_every_cycles) == 0
                result = await capture_live_factors(
                    storage=storage,
                    cse=cse,
                    book_limit=args.book_limit if include_books else 0,
                    include_sectors_indexes=include_market,
                    include_daily_summary=final_cycle or args.include_daily_summary,
                    partial_session=not final_cycle,
                )
                print(json.dumps(asdict(result), sort_keys=True), flush=True)
                cycle += 1
                if (not args.until_close and cycle >= cycles) or (
                    args.until_close and final_cycle
                ):
                    break
                await asyncio.sleep(max(1.0, float(args.interval_seconds)))
    finally:
        await storage.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Capture live CSE shadow factors")
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--until-close", action="store_true")
    parser.add_argument("--book-limit", type=int, default=25)
    parser.add_argument("--book-every-cycles", type=int, default=10)
    parser.add_argument("--market-every-cycles", type=int, default=5)
    parser.add_argument("--include-daily-summary", action="store_true")
    args = parser.parse_args(argv)
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
