"""Postgres persistence layer (snapshots, disclosures, users, rules, alert log)."""

from __future__ import annotations

import math
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import date, datetime
from time import perf_counter
from typing import Any, cast

from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from psycopg.types.json import Json
from psycopg_pool import AsyncConnectionPool

from koel.domain import (
    AlertEvent,
    AlertRule,
    AlertType,
    BigPrint,
    DailyBar,
    Disclosure,
    ForecastPoint,
    IndexSnapshot,
    MarketNotice,
    OrderBookSnapshot,
    PreviousPriceState,
    PriceSnapshot,
    SectorSnapshot,
    sanitize_disclosure_category,
)
from koel.logging_setup import get_logger

log = get_logger(__name__)


def _as_row(row: Any) -> dict[str, Any]:
    return cast(dict[str, Any], row)


def _as_rows(rows: Any) -> list[dict[str, Any]]:
    return [cast(dict[str, Any], r) for r in rows]


def _require_pg_int(value: Any, *, what: str) -> int:
    """Fail closed — bool soft-accepts via ``int(True)==1``; lists abort mid path."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{what} failed validation")
    return value


def _pg_count(value: Any) -> int | None:
    """Non-negative PG COUNT; None when poisoned (bool / non-int / negative)."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _clean_symbol(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    symbol = value.strip().upper()
    return symbol or None


# Transaction-scoped daily-cap serializer for claim_pending_briefs.
# Distinct from poller.POLL_LOCK_ID (4_201_337): same bigint would let a
# session poll hold block brief xact waiters on a second pool connection and
# deadlock under max_size=2 (poll waits for pool; brief waits for advisory).
BRIEF_CAP_LOCK_ID = 4_201_339


class Storage:
    def __init__(self, database_url: str, *, min_size: int = 1, max_size: int = 4) -> None:
        if max_size < 2:
            raise ValueError(
                "Storage max_size must be >= 2: advisory lock holds one pool connection "
                "for the poll tick, so health checks and other queries need a free conn"
            )
        self._pool = AsyncConnectionPool(
            conninfo=database_url,
            min_size=min_size,
            max_size=max_size,
            open=False,
            kwargs={"row_factory": dict_row},
        )
        # Session advisory locks must stay on the same connection for the hold duration.
        self._lock_cm: Any | None = None
        self._lock_conn: Any | None = None
        self._lock_id: int | None = None
        self._last_health_checkout_wait_ms: float | None = None

    async def open(self) -> None:
        await self._pool.open()
        await self._pool.wait()

    async def close(self) -> None:
        if self._lock_conn is not None:
            await self.advisory_unlock()
        await self._pool.close()

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[Any]:
        async with self._pool.connection() as conn:
            yield conn

    async def upsert_stock(
        self,
        symbol: str,
        name: str | None = None,
        sector: str | None = None,
        *,
        cse_stock_id: int | None = None,
    ) -> None:
        # Fail closed — non-string symbol used to throw on .strip mid upsert.
        if not isinstance(symbol, str):
            return
        symbol = symbol.strip().upper()
        if not symbol:
            return
        # Fail closed — bool / non-positive must not poison cse_stock_id.
        stock_id: int | None
        if (
            isinstance(cse_stock_id, bool)
            or not isinstance(cse_stock_id, int)
            or cse_stock_id <= 0
        ):
            stock_id = None
        else:
            stock_id = cse_stock_id
        async with self._pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO stocks (symbol, name, sector, cse_stock_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (symbol) DO UPDATE SET
                    name = COALESCE(EXCLUDED.name, stocks.name),
                    sector = COALESCE(EXCLUDED.sector, stocks.sector),
                    cse_stock_id = COALESCE(
                        EXCLUDED.cse_stock_id, stocks.cse_stock_id
                    ),
                    updated_at = now()
                """,
                (symbol, name, sector, stock_id),
            )

    async def list_stock_names(self) -> list[tuple[str, str]]:
        """Return ``(symbol, name)`` for stocks with a non-empty company name.

        Used by optional bulk disclosure discovery to map
        ``approvedAnnouncement.company`` → watchlist symbol.
        """
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT symbol, name
                    FROM stocks
                    WHERE name IS NOT NULL AND btrim(name) <> ''
                    """
                )
            ).fetchall()
        out: list[tuple[str, str]] = []
        for row in _as_rows(rows):
            # Fail closed — non-string PG values used to soft-accept via str()
            # (int/None became "123"/"None" symbols in the bulk name map).
            raw_sym = row["symbol"]
            raw_name = row["name"]
            if not isinstance(raw_sym, str) or not isinstance(raw_name, str):
                continue
            symbol = raw_sym.strip().upper()
            name = raw_name.strip()
            if symbol and name:
                out.append((symbol, name))
        return out

    async def insert_snapshot(self, snap: PriceSnapshot) -> PriceSnapshot:
        stored = await self.persist_market_snapshots([snap])
        if not stored:
            raise ValueError(f"invalid snapshot symbol: {snap.symbol!r}")
        return stored[0]

    async def persist_market_snapshots(self, snaps: list[PriceSnapshot]) -> list[PriceSnapshot]:
        """Upsert stocks + insert price_snapshots for a full tradeSummary board.

        Used by the poller to keep a market-wide browse layer in Postgres while
        rule evaluation stays watchlist-scoped. Empty input is a no-op.

        Duplicate symbols in one board collapse to last-wins (one snapshot row
        per symbol) so rule eval cannot use an intra-tick sibling as
        ``previous``. Empty/whitespace symbols are skipped. Batches into two
        multi-row statements inside one transaction.
        """
        if not snaps:
            return []

        # Last-wins per normalized symbol; skip blanks (invalid CSE rows)
        # and non-finite prices (NaN/±Inf must not poison price_snapshots).
        by_symbol: dict[str, PriceSnapshot] = {}
        for snap in snaps:
            # Fail closed — non-string symbol used to throw on .strip and abort
            # the whole tradeSummary board persist.
            if not isinstance(snap.symbol, str):
                continue
            symbol = snap.symbol.strip().upper()
            if not symbol:
                continue
            if not math.isfinite(snap.price):
                continue
            by_symbol[symbol] = snap
        if not by_symbol:
            return []

        normalized: list[tuple[str, PriceSnapshot]] = list(by_symbol.items())
        # Column-wise arrays + UNNEST: static SQL only (no f-string / concat VALUES).
        stock_symbols = [symbol for symbol, _ in normalized]
        stock_names = [snap.name for _, snap in normalized]
        stock_sectors = [None] * len(normalized)
        stock_cse_ids: list[int | None] = []
        for _, snap in normalized:
            raw_id = snap.cse_stock_id
            if isinstance(raw_id, bool) or not isinstance(raw_id, int) or raw_id <= 0:
                stock_cse_ids.append(None)
            else:
                stock_cse_ids.append(raw_id)
        snap_symbols = list(stock_symbols)
        snap_prices = [snap.price for _, snap in normalized]
        snap_changes = [snap.change for _, snap in normalized]
        snap_change_pcts = [snap.change_pct for _, snap in normalized]
        snap_prev_closes = [snap.previous_close for _, snap in normalized]
        snap_volumes = [snap.volume for _, snap in normalized]
        snap_trade_counts = [snap.trade_count for _, snap in normalized]
        snap_turnovers = [snap.turnover for _, snap in normalized]
        snap_crossing = [snap.crossing_volume for _, snap in normalized]
        snap_highs = [snap.high for _, snap in normalized]
        snap_lows = [snap.low for _, snap in normalized]
        snap_opens = [snap.open for _, snap in normalized]
        snap_market_caps = [snap.market_cap for _, snap in normalized]
        snap_ts = [snap.ts for _, snap in normalized]

        async with self._pool.connection() as conn, conn.transaction():
            await conn.execute(
                """
                INSERT INTO stocks (symbol, name, sector, cse_stock_id)
                SELECT symbol, name, sector, cse_stock_id
                FROM UNNEST(
                    %s::text[], %s::text[], %s::text[], %s::int[]
                ) AS t(symbol, name, sector, cse_stock_id)
                ON CONFLICT (symbol) DO UPDATE SET
                    name = COALESCE(EXCLUDED.name, stocks.name),
                    sector = COALESCE(EXCLUDED.sector, stocks.sector),
                    cse_stock_id = COALESCE(
                        EXCLUDED.cse_stock_id, stocks.cse_stock_id
                    ),
                    updated_at = now()
                """,
                (stock_symbols, stock_names, stock_sectors, stock_cse_ids),
            )
            rows = await (
                await conn.execute(
                    """
                    INSERT INTO price_snapshots (
                        symbol, price, change, change_pct, previous_close,
                        volume, trade_count, turnover, crossing_volume,
                        high, low, open, market_cap, ts, source
                    )
                    SELECT
                        symbol, price, change, change_pct, previous_close,
                        volume, trade_count, turnover, crossing_volume,
                        high, low, open, market_cap, ts, 'poller'
                    FROM UNNEST(
                        %s::text[],
                        %s::double precision[],
                        %s::double precision[],
                        %s::double precision[],
                        %s::double precision[],
                        %s::double precision[],
                        %s::double precision[],
                        %s::double precision[],
                        %s::double precision[],
                        %s::double precision[],
                        %s::double precision[],
                        %s::double precision[],
                        %s::double precision[],
                        %s::timestamptz[]
                    ) AS t(
                        symbol, price, change, change_pct, previous_close,
                        volume, trade_count, turnover, crossing_volume,
                        high, low, open, market_cap, ts
                    )
                    ON CONFLICT (symbol, ts) DO UPDATE SET
                        price = EXCLUDED.price,
                        change = EXCLUDED.change,
                        change_pct = EXCLUDED.change_pct,
                        previous_close = EXCLUDED.previous_close,
                        volume = EXCLUDED.volume,
                        trade_count = EXCLUDED.trade_count,
                        turnover = EXCLUDED.turnover,
                        crossing_volume = EXCLUDED.crossing_volume,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        open = EXCLUDED.open,
                        market_cap = EXCLUDED.market_cap,
                        source = 'poller',
                        ingested_at = now()
                    RETURNING id
                    """,
                    (
                        snap_symbols,
                        snap_prices,
                        snap_changes,
                        snap_change_pcts,
                        snap_prev_closes,
                        snap_volumes,
                        snap_trade_counts,
                        snap_turnovers,
                        snap_crossing,
                        snap_highs,
                        snap_lows,
                        snap_opens,
                        snap_market_caps,
                        snap_ts,
                    ),
                )
            ).fetchall()

        assert len(rows) == len(normalized)
        out: list[PriceSnapshot] = []
        for (symbol, snap), row in zip(normalized, _as_rows(rows), strict=True):
            # Fail closed — bool ids soft-accept via int(True)==1; lists abort
            # mid market persist (parity ``_row_to_snapshot`` id guard).
            raw_id = row.get("id")
            if isinstance(raw_id, bool) or not isinstance(raw_id, int):
                log.warning(
                    "market_persist_row_poisoned_id",
                    symbol=symbol,
                    row_id=raw_id,
                )
                continue
            out.append(snap.model_copy(update={"id": raw_id, "symbol": symbol}))
        return out

    async def delete_old_non_watchlist_snapshots(
        self,
        days: int,
        *,
        limit: int = 5_000,
    ) -> int:
        """Delete ``price_snapshots`` older than ``days`` for non-watchlist symbols.

        Symbols present on any user's watchlist keep full history. ``days <= 0``
        is a no-op (returns 0). Used by optional ``SNAPSHOT_RETENTION_DAYS``.

        Deletes at most ``limit`` rows per call so a large backlog cannot pin
        the poll tick (remaining rows drain on subsequent ticks).
        """
        if days <= 0:
            return 0
        batch = max(1, int(limit))
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    WITH doomed AS (
                        SELECT ps.id
                        FROM price_snapshots ps
                        WHERE ps.ts < now() - (%s * interval '1 day')
                          AND NOT EXISTS (
                              SELECT 1
                              FROM watchlist_items w
                              WHERE w.symbol = ps.symbol
                          )
                        ORDER BY ps.ts ASC, ps.id ASC
                        LIMIT %s
                    ),
                    deleted AS (
                        DELETE FROM price_snapshots ps
                        USING doomed
                        WHERE ps.id = doomed.id
                        RETURNING 1
                    )
                    SELECT COUNT(*)::int AS n FROM deleted
                    """,
                    (days, batch),
                )
            ).fetchone()
        if row is None:
            return 0
        # Fail closed — bool soft-accepts via int(True)==1; None/"n" → 0.
        counted = _pg_count(_as_row(row).get("n"))
        return 0 if counted is None else counted

    async def persist_sectors(self, sectors: list[SectorSnapshot]) -> list[SectorSnapshot]:
        """Upsert CSE sector index rows (optional ``SECTORS_INGEST`` path).

        Last-wins per ``sector_id``. Blank symbols skipped. Empty input is a no-op.
        """
        if not sectors:
            return []

        by_id: dict[int, SectorSnapshot] = {}
        for sector in sectors:
            # Fail closed — non-string symbol used to throw on .strip and abort
            # the whole allSectors persist.
            if not isinstance(sector.symbol, str):
                continue
            symbol = sector.symbol.strip().upper()
            if not symbol:
                continue
            by_id[sector.sector_id] = sector.model_copy(update={"symbol": symbol})
        if not by_id:
            return []

        rows = list(by_id.values())
        # Column-wise arrays + UNNEST: static SQL only (no f-string / concat VALUES).
        async with self._pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO sectors (
                    sector_id, symbol, name, index_code, index_code_sp, index_name,
                    index_value, change, change_pct, trade_today, volume_today,
                    turnover_today, previous_close, ts, cse_row_id
                )
                SELECT
                    sector_id, symbol, name, index_code, index_code_sp, index_name,
                    index_value, change, change_pct, trade_today, volume_today,
                    turnover_today, previous_close, ts, cse_row_id
                FROM UNNEST(
                    %s::integer[],
                    %s::text[],
                    %s::text[],
                    %s::text[],
                    %s::text[],
                    %s::text[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::timestamptz[],
                    %s::integer[]
                ) AS t(
                    sector_id, symbol, name, index_code, index_code_sp, index_name,
                    index_value, change, change_pct, trade_today, volume_today,
                    turnover_today, previous_close, ts, cse_row_id
                )
                ON CONFLICT (sector_id) DO UPDATE SET
                    symbol = EXCLUDED.symbol,
                    name = EXCLUDED.name,
                    index_code = EXCLUDED.index_code,
                    index_code_sp = EXCLUDED.index_code_sp,
                    index_name = EXCLUDED.index_name,
                    index_value = EXCLUDED.index_value,
                    change = EXCLUDED.change,
                    change_pct = EXCLUDED.change_pct,
                    trade_today = EXCLUDED.trade_today,
                    volume_today = EXCLUDED.volume_today,
                    turnover_today = EXCLUDED.turnover_today,
                    previous_close = EXCLUDED.previous_close,
                    ts = EXCLUDED.ts,
                    cse_row_id = EXCLUDED.cse_row_id,
                    ingested_at = now()
                """,
                (
                    [s.sector_id for s in rows],
                    [s.symbol for s in rows],
                    [s.name for s in rows],
                    [s.index_code for s in rows],
                    [s.index_code_sp for s in rows],
                    [s.index_name for s in rows],
                    [s.index_value for s in rows],
                    [s.change for s in rows],
                    [s.change_pct for s in rows],
                    [s.trade_today for s in rows],
                    [s.volume_today for s in rows],
                    [s.turnover_today for s in rows],
                    [s.previous_close for s in rows],
                    [s.ts for s in rows],
                    [s.cse_row_id for s in rows],
                ),
            )
        return rows

    async def list_stocks_with_cse_ids(self) -> list[tuple[str, int]]:
        """Return ``(symbol, cse_stock_id)`` for path backfill targets.

        Prefer symbols with no ``daily_bars`` yet so a ``--limit`` pass fills
        gaps (thin names / late watchlist adds) instead of re-hitting A… first.
        """
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT s.symbol, s.cse_stock_id
                    FROM stocks s
                    WHERE s.cse_stock_id IS NOT NULL
                    ORDER BY
                      EXISTS (
                        SELECT 1 FROM daily_bars d WHERE d.symbol = s.symbol
                      ) ASC,
                      s.symbol ASC
                    """
                )
            ).fetchall()
        out: list[tuple[str, int]] = []
        for row in _as_rows(rows):
            raw_sym = row.get("symbol")
            raw_id = row.get("cse_stock_id")
            if not isinstance(raw_sym, str):
                continue
            symbol = raw_sym.strip().upper()
            if not symbol:
                continue
            if isinstance(raw_id, bool) or not isinstance(raw_id, int) or raw_id <= 0:
                continue
            out.append((symbol, raw_id))
        return out

    async def list_symbols_missing_cse_stock_id(
        self, *, limit: int = 40
    ) -> list[str]:
        """Listed CSE tickers that still need a chart ``stockId``.

        Prefers symbols that already have poller snapshots (someone cares)
        and skips synthetic rows like ``MARKET`` / bare indexes.
        """
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            return []
        cap = min(limit, 200)
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT s.symbol
                    FROM stocks s
                    WHERE s.cse_stock_id IS NULL
                      AND s.symbol ~ '^[A-Z0-9]+\\.[A-Z][0-9]{4}$'
                      AND NOT EXISTS (
                        SELECT 1 FROM daily_bars d WHERE d.symbol = s.symbol
                      )
                    ORDER BY
                      EXISTS (
                        SELECT 1 FROM price_snapshots p WHERE p.symbol = s.symbol
                      ) DESC,
                      s.symbol ASC
                    LIMIT %s
                    """,
                    (cap,),
                )
            ).fetchall()
        out: list[str] = []
        for row in _as_rows(rows):
            raw = row.get("symbol")
            if not isinstance(raw, str):
                continue
            symbol = raw.strip().upper()
            if symbol:
                out.append(symbol)
        return out

    async def persist_daily_bars(self, bars: list[DailyBar]) -> int:
        """Upsert CSE daily path bars (``UNIQUE (symbol, trade_date)``).

        Last-wins per ``(symbol, trade_date)``. Non-finite prices skipped.
        Returns number of rows written (insert or update). Empty → 0.
        """
        if not bars:
            return 0

        by_key: dict[tuple[str, object], DailyBar] = {}
        for bar in bars:
            if not isinstance(bar.symbol, str):
                continue
            symbol = bar.symbol.strip().upper()
            if not symbol:
                continue
            if not math.isfinite(bar.price):
                continue
            by_key[(symbol, bar.trade_date)] = bar.model_copy(update={"symbol": symbol})
        if not by_key:
            return 0

        rows = list(by_key.values())
        async with self._pool.connection() as conn:
            # Ensure parent stocks exist (path backfill may race empty board).
            await conn.execute(
                """
                INSERT INTO stocks (symbol)
                SELECT DISTINCT symbol
                FROM UNNEST(%s::text[]) AS t(symbol)
                ON CONFLICT (symbol) DO NOTHING
                """,
                ([b.symbol for b in rows],),
            )
            result = await conn.execute(
                """
                INSERT INTO daily_bars (
                    symbol, trade_date, price, high, low, open, volume,
                    source_period, bar_ts
                )
                SELECT
                    symbol, trade_date, price, high, low, open, volume,
                    source_period, bar_ts
                FROM UNNEST(
                    %s::text[],
                    %s::date[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::smallint[],
                    %s::timestamptz[]
                ) AS t(
                    symbol, trade_date, price, high, low, open, volume,
                    source_period, bar_ts
                )
                ON CONFLICT (symbol, trade_date) DO UPDATE SET
                    price = EXCLUDED.price,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    open = EXCLUDED.open,
                    volume = EXCLUDED.volume,
                    source_period = EXCLUDED.source_period,
                    bar_ts = EXCLUDED.bar_ts,
                    ingested_at = now()
                """,
                (
                    [b.symbol for b in rows],
                    [b.trade_date for b in rows],
                    [b.price for b in rows],
                    [b.high for b in rows],
                    [b.low for b in rows],
                    [b.open for b in rows],
                    [b.volume for b in rows],
                    [b.source_period for b in rows],
                    [b.bar_ts for b in rows],
                ),
            )
        # psycopg Status: "INSERT 0 N" / "UPDATE N" — prefer rowcount when present.
        rowcount = getattr(result, "rowcount", None)
        if isinstance(rowcount, int) and not isinstance(rowcount, bool) and rowcount >= 0:
            return rowcount
        return len(rows)

    async def persist_intraday_snapshots(self, snaps: list[PriceSnapshot]) -> int:
        """Insert CSE chart ticks as ``source='cse_intraday'``.

        Alert ``previous_snapshot`` ignores these rows so dense chart backfill
        cannot mute price-cross fires. Idempotent on ``UNIQUE (symbol, ts)``.
        """
        if not snaps:
            return 0

        by_key: dict[tuple[str, datetime], PriceSnapshot] = {}
        for snap in snaps:
            if not isinstance(snap.symbol, str):
                continue
            symbol = snap.symbol.strip().upper()
            if not symbol:
                continue
            if not math.isfinite(snap.price) or snap.price <= 0:
                continue
            if not isinstance(snap.ts, datetime):
                continue
            by_key[(symbol, snap.ts)] = snap.model_copy(update={"symbol": symbol})
        if not by_key:
            return 0

        rows = list(by_key.values())
        symbols = [s.symbol for s in rows]
        prices = [s.price for s in rows]
        changes = [s.change for s in rows]
        change_pcts = [s.change_pct for s in rows]
        volumes = [s.volume for s in rows]
        highs = [s.high for s in rows]
        lows = [s.low for s in rows]
        opens = [s.open for s in rows]
        tss = [s.ts for s in rows]

        async with self._pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO stocks (symbol)
                SELECT DISTINCT symbol
                FROM UNNEST(%s::text[]) AS t(symbol)
                ON CONFLICT (symbol) DO NOTHING
                """,
                (symbols,),
            )
            result = await conn.execute(
                """
                INSERT INTO price_snapshots (
                    symbol, price, change, change_pct, volume, high, low, open,
                    ts, source
                )
                SELECT
                    v.symbol, v.price, v.change, v.change_pct, v.volume,
                    v.high, v.low, v.open, v.ts, 'cse_intraday'
                FROM UNNEST(
                    %s::text[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::timestamptz[]
                ) AS v(
                    symbol, price, change, change_pct, volume, high, low, open, ts
                )
                ON CONFLICT (symbol, ts) DO NOTHING
                """,
                (
                    symbols,
                    prices,
                    changes,
                    change_pcts,
                    volumes,
                    highs,
                    lows,
                    opens,
                    tss,
                ),
            )
        rowcount = getattr(result, "rowcount", None)
        if isinstance(rowcount, int) and not isinstance(rowcount, bool) and rowcount >= 0:
            return rowcount
        return 0

    async def list_symbols_with_daily_bars(self) -> list[str]:
        """Symbols that have at least one ``daily_bars`` row (sorted)."""
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT DISTINCT symbol
                    FROM daily_bars
                    ORDER BY symbol ASC
                    """
                )
            ).fetchall()
        out: list[str] = []
        for row in _as_rows(rows):
            raw = row.get("symbol")
            if not isinstance(raw, str):
                continue
            symbol = raw.strip().upper()
            if symbol:
                out.append(symbol)
        return out

    async def persist_hybrid_daily_bars(self, rows: list[dict[str, Any]]) -> int:
        """Upsert spliced Yahoo+CSE bars into ``hybrid_daily_bars``.

        Last-wins per ``(symbol, trade_date)``. Returns rows written.
        """
        if not rows:
            return 0
        by_key: dict[tuple[str, date], dict[str, Any]] = {}
        for row in rows:
            sym = row.get("symbol")
            td = row.get("trade_date")
            price = row.get("price")
            source = row.get("source")
            bar_ts = row.get("bar_ts")
            if not isinstance(sym, str) or not sym.strip():
                continue
            if not isinstance(td, date):
                continue
            if not isinstance(price, int | float) or isinstance(price, bool):
                continue
            if not math.isfinite(float(price)):
                continue
            if source not in {"cse", "yahoo"}:
                continue
            if not isinstance(bar_ts, datetime):
                continue
            symbol = sym.strip().upper()
            by_key[(symbol, td)] = {
                **row,
                "symbol": symbol,
                "price": float(price),
            }
        if not by_key:
            return 0
        payload = list(by_key.values())
        async with self._pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO stocks (symbol)
                SELECT DISTINCT symbol
                FROM UNNEST(%s::text[]) AS t(symbol)
                ON CONFLICT (symbol) DO NOTHING
                """,
                ([r["symbol"] for r in payload],),
            )
            result = await conn.execute(
                """
                INSERT INTO hybrid_daily_bars (
                    symbol, trade_date, price, high, low, open, volume,
                    source, yahoo_ticker, bar_ts
                )
                SELECT
                    symbol, trade_date, price, high, low, open, volume,
                    source, yahoo_ticker, bar_ts
                FROM UNNEST(
                    %s::text[],
                    %s::date[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::text[],
                    %s::text[],
                    %s::timestamptz[]
                ) AS t(
                    symbol, trade_date, price, high, low, open, volume,
                    source, yahoo_ticker, bar_ts
                )
                ON CONFLICT (symbol, trade_date) DO UPDATE SET
                    price = EXCLUDED.price,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    open = EXCLUDED.open,
                    volume = EXCLUDED.volume,
                    source = EXCLUDED.source,
                    yahoo_ticker = EXCLUDED.yahoo_ticker,
                    bar_ts = EXCLUDED.bar_ts,
                    ingested_at = now()
                """,
                (
                    [r["symbol"] for r in payload],
                    [r["trade_date"] for r in payload],
                    [r["price"] for r in payload],
                    [r.get("high") for r in payload],
                    [r.get("low") for r in payload],
                    [r.get("open") for r in payload],
                    [r.get("volume") for r in payload],
                    [r["source"] for r in payload],
                    [r.get("yahoo_ticker") for r in payload],
                    [r["bar_ts"] for r in payload],
                ),
            )
        rowcount = getattr(result, "rowcount", None)
        if isinstance(rowcount, int) and not isinstance(rowcount, bool) and rowcount >= 0:
            return rowcount
        return len(payload)

    async def list_hybrid_daily_bars(self, symbol: str) -> list[DailyBar]:
        """Load hybrid panel as ``DailyBar`` (source_period: 5=cse, 0=yahoo)."""
        if not isinstance(symbol, str) or not symbol.strip():
            return []
        sym = symbol.strip().upper()
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT symbol, trade_date, price, high, low, open, volume,
                           source, bar_ts
                    FROM hybrid_daily_bars
                    WHERE symbol = %s
                    ORDER BY trade_date ASC
                    """,
                    (sym,),
                )
            ).fetchall()
        out: list[DailyBar] = []
        for row in _as_rows(rows):
            src = row.get("source")
            period = 5 if src == "cse" else 0
            try:
                out.append(
                    DailyBar(
                        symbol=str(row["symbol"]),
                        trade_date=row["trade_date"],
                        price=float(row["price"]),
                        high=row.get("high"),
                        low=row.get("low"),
                        open=row.get("open"),
                        volume=row.get("volume"),
                        source_period=period,
                        bar_ts=row["bar_ts"],
                    )
                )
            except Exception:
                continue
        return out

    async def list_symbols_with_hybrid_daily_bars(self) -> list[str]:
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT DISTINCT symbol
                    FROM hybrid_daily_bars
                    ORDER BY symbol ASC
                    """
                )
            ).fetchall()
        out: list[str] = []
        for row in _as_rows(rows):
            raw = row.get("symbol")
            if isinstance(raw, str) and raw.strip():
                out.append(raw.strip().upper())
        return out

    async def upsert_market_daily_summary(self, rows: list[dict[str, Any]]) -> int:
        """Upsert CSE dailyMarketSummery rows (keyed by trade_date)."""
        if not rows:
            return 0
        by_date: dict[date, dict[str, Any]] = {}
        for row in rows:
            d = row.get("trade_date")
            if not isinstance(d, date):
                continue
            by_date[d] = row
        if not by_date:
            return 0
        payload = list(by_date.values())
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.executemany(
                """
                    INSERT INTO market_daily_summary (
                        trade_date, market_turnover, market_trades,
                        equity_foreign_purchase, equity_foreign_sales,
                        foreign_net, volume_of_turnover, market_cap, asi, raw
                    ) VALUES (
                        %(trade_date)s, %(market_turnover)s, %(market_trades)s,
                        %(equity_foreign_purchase)s, %(equity_foreign_sales)s,
                        %(foreign_net)s, %(volume_of_turnover)s, %(market_cap)s,
                        %(asi)s, %(raw)s
                    )
                    ON CONFLICT (trade_date) DO UPDATE SET
                        market_turnover = EXCLUDED.market_turnover,
                        market_trades = EXCLUDED.market_trades,
                        equity_foreign_purchase = EXCLUDED.equity_foreign_purchase,
                        equity_foreign_sales = EXCLUDED.equity_foreign_sales,
                        foreign_net = EXCLUDED.foreign_net,
                        volume_of_turnover = EXCLUDED.volume_of_turnover,
                        market_cap = EXCLUDED.market_cap,
                        asi = EXCLUDED.asi,
                        raw = EXCLUDED.raw,
                        ingested_at = now()
                    """,
                [
                    {
                        **r,
                        "raw": Json(r.get("raw") or {}),
                    }
                    for r in payload
                ],
            )
        return len(payload)

    async def list_market_daily_summary(self) -> list[dict[str, Any]]:
        """All market_daily_summary rows ascending by trade_date."""
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT trade_date, market_turnover, market_trades,
                           equity_foreign_purchase, equity_foreign_sales,
                           foreign_net, volume_of_turnover, market_cap, asi
                    FROM market_daily_summary
                    ORDER BY trade_date ASC
                    """
                )
            ).fetchall()
        return [dict(r) for r in rows]

    def _bars_table_for_source(self, source: str) -> str:
        """Return daily bars table name for appetite source (SQL-safe whitelist)."""
        if source == "hybrid_research":
            return "hybrid_daily_bars"
        return "daily_bars"

    async def list_daily_bar_trade_dates(self, *, source: str = "cse") -> list[date]:
        """Distinct trade_dates present in the bars table for ``source``."""
        table = self._bars_table_for_source(source)
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    f"""
                    SELECT DISTINCT trade_date
                    FROM {table}
                    WHERE symbol <> 'ASPI'
                    ORDER BY trade_date ASC
                    """
                )
            ).fetchall()
        out: list[date] = []
        for row in _as_rows(rows):
            d = row.get("trade_date")
            if isinstance(d, date):
                out.append(d)
        return out

    async def list_daily_bar_changes_for_date(
        self, trade_date: date, *, source: str = "cse"
    ) -> list[dict[str, Any]]:
        """Per-symbol change_pct for ``trade_date`` (excludes ASPI).

        change_pct = (price / lag(price) - 1) * 100 using the prior bar.
        """
        if not isinstance(trade_date, date):
            return []
        table = self._bars_table_for_source(source)
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    f"""
                    WITH ordered AS (
                        SELECT
                            symbol,
                            trade_date,
                            price,
                            volume,
                            LAG(price) OVER (
                                PARTITION BY symbol ORDER BY trade_date
                            ) AS prev_price
                        FROM {table}
                        WHERE symbol <> 'ASPI'
                    )
                    SELECT
                        symbol,
                        trade_date,
                        price,
                        volume,
                        prev_price,
                        CASE
                            WHEN prev_price IS NOT NULL
                                 AND prev_price <> 0
                                 AND price IS NOT NULL
                            THEN (price / prev_price - 1.0) * 100.0
                            ELSE NULL
                        END AS change_pct
                    FROM ordered
                    WHERE trade_date = %s
                    ORDER BY symbol ASC
                    """,
                    (trade_date,),
                )
            ).fetchall()
        return [dict(r) for r in rows]

    async def list_all_daily_bar_changes(
        self, *, source: str = "cse"
    ) -> list[dict[str, Any]]:
        """All symbol/date change_pct rows (excludes ASPI) for appetite backfill."""
        table = self._bars_table_for_source(source)
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    f"""
                    WITH ordered AS (
                        SELECT
                            symbol,
                            trade_date,
                            price,
                            volume,
                            LAG(price) OVER (
                                PARTITION BY symbol ORDER BY trade_date
                            ) AS prev_price
                        FROM {table}
                        WHERE symbol <> 'ASPI'
                    )
                    SELECT
                        symbol,
                        trade_date,
                        price,
                        volume,
                        CASE
                            WHEN prev_price IS NOT NULL
                                 AND prev_price <> 0
                                 AND price IS NOT NULL
                            THEN (price / prev_price - 1.0) * 100.0
                            ELSE NULL
                        END AS change_pct
                    FROM ordered
                    WHERE prev_price IS NOT NULL
                    ORDER BY trade_date ASC, symbol ASC
                    """
                )
            ).fetchall()
        return [dict(r) for r in rows]

    async def aspi_change_pct_for_date(
        self, trade_date: date, *, source: str = "cse"
    ) -> float | None:
        """ASPI daily change_pct for ``trade_date`` from bars lag(price)."""
        if not isinstance(trade_date, date):
            return None
        table = self._bars_table_for_source(source)
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    f"""
                    WITH ordered AS (
                        SELECT
                            trade_date,
                            price,
                            LAG(price) OVER (ORDER BY trade_date) AS prev_price
                        FROM {table}
                        WHERE symbol = 'ASPI'
                    )
                    SELECT
                        CASE
                            WHEN prev_price IS NOT NULL AND prev_price <> 0
                            THEN (price / prev_price - 1.0) * 100.0
                            ELSE NULL
                        END AS change_pct
                    FROM ordered
                    WHERE trade_date = %s
                    """,
                    (trade_date,),
                )
            ).fetchone()
        if row is None:
            return None
        val = _as_row(row).get("change_pct")
        if isinstance(val, bool) or not isinstance(val, int | float):
            return None
        if not math.isfinite(float(val)):
            return None
        return float(val)

    async def list_aspi_change_pcts(
        self, *, source: str = "cse"
    ) -> dict[date, float]:
        """Map trade_date → ASPI change_pct for all dates with a prior bar."""
        table = self._bars_table_for_source(source)
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    f"""
                    WITH ordered AS (
                        SELECT
                            trade_date,
                            price,
                            LAG(price) OVER (ORDER BY trade_date) AS prev_price
                        FROM {table}
                        WHERE symbol = 'ASPI'
                    )
                    SELECT
                        trade_date,
                        (price / prev_price - 1.0) * 100.0 AS change_pct
                    FROM ordered
                    WHERE prev_price IS NOT NULL AND prev_price <> 0
                    ORDER BY trade_date ASC
                    """
                )
            ).fetchall()
        out: dict[date, float] = {}
        for row in _as_rows(rows):
            d = row.get("trade_date")
            val = row.get("change_pct")
            if not isinstance(d, date):
                continue
            if isinstance(val, bool) or not isinstance(val, int | float):
                continue
            if not math.isfinite(float(val)):
                continue
            out[d] = float(val)
        return out

    async def list_latest_price_snapshots(self) -> list[PriceSnapshot]:
        """Latest poller snapshot per symbol (for live appetite path)."""
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT DISTINCT ON (symbol) *
                    FROM price_snapshots
                    WHERE source = 'poller'
                      AND symbol <> 'MARKET'
                    ORDER BY symbol ASC, ts DESC, id DESC
                    """
                )
            ).fetchall()
        out: list[PriceSnapshot] = []
        for row in _as_rows(rows):
            try:
                snap = _row_to_snapshot(row)
            except Exception:
                continue
            if snap is None:
                continue
            out.append(snap)
        return out

    async def upsert_market_appetite_daily(self, row: Any) -> None:
        """Upsert one ``market_appetite_daily`` row (keyed by trade_date)."""
        trade_date = getattr(row, "trade_date", None)
        if not isinstance(trade_date, date):
            return
        score = getattr(row, "score", None)
        if isinstance(score, bool) or not isinstance(score, int | float):
            return
        if not math.isfinite(float(score)):
            return
        band = getattr(row, "band", None)
        if not isinstance(band, str) or not band.strip():
            return
        source = getattr(row, "source", "cse")
        if source not in ("cse", "hybrid_research"):
            source = "cse"
        components = getattr(row, "components", None)
        payload = components if isinstance(components, dict) else {}
        universe_n = getattr(row, "universe_n", 0)
        if isinstance(universe_n, bool) or not isinstance(universe_n, int) or universe_n < 0:
            universe_n = 0

        def _opt_int(value: Any) -> int | None:
            if isinstance(value, bool) or not isinstance(value, int):
                return None
            return value

        def _opt_float(value: Any) -> float | None:
            if value is None or isinstance(value, bool):
                return None
            if not isinstance(value, int | float) or not math.isfinite(value):
                return None
            return float(value)

        async with self._pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO market_appetite_daily (
                    trade_date, score, band, components, source,
                    universe_n, advancers, decliners, unchanged,
                    aspi_change_pct, computed_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, now()
                )
                ON CONFLICT (trade_date) DO UPDATE SET
                    score = EXCLUDED.score,
                    band = EXCLUDED.band,
                    components = EXCLUDED.components,
                    source = EXCLUDED.source,
                    universe_n = EXCLUDED.universe_n,
                    advancers = EXCLUDED.advancers,
                    decliners = EXCLUDED.decliners,
                    unchanged = EXCLUDED.unchanged,
                    aspi_change_pct = EXCLUDED.aspi_change_pct,
                    computed_at = now()
                """,
                (
                    trade_date,
                    float(score),
                    band.strip(),
                    Json(payload),
                    source,
                    universe_n,
                    _opt_int(getattr(row, "advancers", None)),
                    _opt_int(getattr(row, "decliners", None)),
                    _opt_int(getattr(row, "unchanged", None)),
                    _opt_float(getattr(row, "aspi_change_pct", None)),
                ),
            )

    async def list_market_appetite_daily(
        self, *, source: str | None = None, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """List appetite rows ascending by trade_date (optional source filter)."""
        clauses: list[str] = []
        params: list[Any] = []
        if source in ("cse", "hybrid_research"):
            clauses.append("source = %s")
            params.append(source)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        lim_sql = ""
        if (
            limit is not None
            and isinstance(limit, int)
            and not isinstance(limit, bool)
            and limit > 0
        ):
            lim_sql = "LIMIT %s"
            params.append(limit)
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    f"""
                    SELECT trade_date, score, band, components, source,
                           universe_n, advancers, decliners, unchanged,
                           aspi_change_pct, computed_at
                    FROM market_appetite_daily
                    {where}
                    ORDER BY trade_date ASC
                    {lim_sql}
                    """,
                    tuple(params),
                )
            ).fetchall()
        return [dict(r) for r in rows]

    async def upsert_macro_series(self, rows: list[dict[str, Any]]) -> int:
        """Upsert macro_series points. Returns rows attempted."""
        if not rows:
            return 0
        n = 0
        async with self._pool.connection() as conn:
            for row in rows:
                if not isinstance(row, dict):
                    continue
                source = row.get("source")
                series_id = row.get("series_id")
                ts = row.get("ts")
                value = row.get("value")
                if not isinstance(source, str) or not source.strip():
                    continue
                if not isinstance(series_id, str) or not series_id.strip():
                    continue
                if not isinstance(ts, datetime):
                    continue
                if isinstance(value, bool) or not isinstance(value, int | float):
                    continue
                if not math.isfinite(float(value)):
                    continue
                unit = row.get("unit")
                if unit is not None and not isinstance(unit, str):
                    unit = None
                as_of = row.get("as_of_date")
                if not isinstance(as_of, date):
                    as_of = None
                attribution = row.get("attribution")
                if not isinstance(attribution, str):
                    attribution = ""
                raw_hash = row.get("raw_hash")
                if raw_hash is not None and not isinstance(raw_hash, str):
                    raw_hash = None
                await conn.execute(
                    """
                    INSERT INTO macro_series (
                        source, series_id, ts, value, unit, as_of_date,
                        attribution, raw_hash
                    ) VALUES (
                        %(source)s, %(series_id)s, %(ts)s, %(value)s, %(unit)s,
                        %(as_of_date)s, %(attribution)s, %(raw_hash)s
                    )
                    ON CONFLICT (source, series_id, ts) DO UPDATE SET
                        value = EXCLUDED.value,
                        unit = EXCLUDED.unit,
                        as_of_date = EXCLUDED.as_of_date,
                        attribution = EXCLUDED.attribution,
                        raw_hash = EXCLUDED.raw_hash,
                        ingested_at = now()
                    """,
                    {
                        "source": source.strip(),
                        "series_id": series_id.strip(),
                        "ts": ts,
                        "value": float(value),
                        "unit": unit,
                        "as_of_date": as_of,
                        "attribution": attribution,
                        "raw_hash": raw_hash,
                    },
                )
                n += 1
        return n

    async def latest_macro_change_pct(self, series_id: str) -> float | None:
        """Day-over-day % change for the two newest ``macro_series`` points.

        Uses ``as_of_date`` when present else ``ts`` date. Returns None when
        fewer than two finite points exist.
        """
        if not isinstance(series_id, str) or not series_id.strip():
            return None
        sid = series_id.strip()
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT value, as_of_date, ts
                    FROM macro_series
                    WHERE series_id = %s
                    ORDER BY COALESCE(as_of_date, (ts AT TIME ZONE 'UTC')::date) DESC,
                             ts DESC
                    LIMIT 2
                    """,
                    (sid,),
                )
            ).fetchall()
        vals: list[float] = []
        for row in _as_rows(rows):
            raw = row.get("value")
            if isinstance(raw, bool) or not isinstance(raw, int | float):
                continue
            if not math.isfinite(float(raw)):
                continue
            vals.append(float(raw))
        if len(vals) < 2:
            return None
        newest, prior = vals[0], vals[1]
        if prior == 0:
            return None
        return ((newest / prior) - 1.0) * 100.0

    async def market_book_imbalance_pct(
        self, *, lookback_minutes: int = 24 * 60
    ) -> float | None:
        """Market-wide public book imbalance % from recent order_book_snapshots.

        Mirrors web ``queryTapePulse``: sum bids/asks across sample, then
        ``(bids - asks) / (bids + asks) * 100``. None when no usable rows.
        """
        mins = lookback_minutes
        if (
            not isinstance(mins, int)
            or isinstance(mins, bool)
            or mins < 30
        ):
            mins = 24 * 60
        mins = min(mins, 7 * 24 * 60)
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT total_bids, total_asks
                    FROM order_book_snapshots
                    WHERE ts >= now() - (%s::text || ' minutes')::interval
                    ORDER BY ts DESC
                    LIMIT 500
                    """,
                    (str(mins),),
                )
            ).fetchall()
        sum_bids = 0.0
        sum_asks = 0.0
        sample_n = 0
        for row in _as_rows(rows):
            bids = row.get("total_bids")
            asks = row.get("total_asks")
            if isinstance(bids, bool) or not isinstance(bids, int | float):
                continue
            if isinstance(asks, bool) or not isinstance(asks, int | float):
                continue
            if not math.isfinite(float(bids)) or not math.isfinite(float(asks)):
                continue
            if float(bids) <= 0 or float(asks) <= 0:
                continue
            sum_bids += float(bids)
            sum_asks += float(asks)
            sample_n += 1
        total = sum_bids + sum_asks
        if sample_n <= 0 or total <= 0:
            return None
        return ((sum_bids - sum_asks) / total) * 100.0

    async def market_regime_fired_keys(self) -> set[str]:
        """Event keys already claimed for MARKET regime day-bucket rules."""
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT al.event_key
                    FROM alert_log al
                    JOIN alert_rules ar ON ar.id = al.rule_id
                    WHERE ar.symbol = 'MARKET'
                      AND (
                        al.event_key LIKE 'appetite_band:%%'
                        OR al.event_key LIKE 'foreign_flow:%%'
                        OR al.event_key LIKE 'book_pressure:%%'
                        OR al.event_key LIKE 'usdlkr_move:%%'
                        OR al.event_key LIKE 'oil_move:%%'
                      )
                      AND al.event_key IS NOT NULL
                    """
                )
            ).fetchall()
        out: set[str] = set()
        for row in _as_rows(rows):
            key = row.get("event_key")
            if isinstance(key, str) and key.strip():
                out.add(key.strip())
        return out

    async def list_symbols_missing_sector(self) -> list[str]:
        """Symbols with daily bars (or any stock) missing a sector label."""
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT s.symbol
                    FROM stocks s
                    WHERE (s.sector IS NULL OR btrim(s.sector) = '')
                      AND EXISTS (
                          SELECT 1 FROM daily_bars d WHERE d.symbol = s.symbol
                      )
                    ORDER BY s.symbol ASC
                    """
                )
            ).fetchall()
        out: list[str] = []
        for row in _as_rows(rows):
            raw = row.get("symbol")
            if isinstance(raw, str) and raw.strip():
                out.append(raw.strip().upper())
        return out

    async def get_stock_sector(self, symbol: str) -> str | None:
        if not isinstance(symbol, str) or not symbol.strip():
            return None
        sym = symbol.strip().upper()
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    "SELECT sector FROM stocks WHERE symbol = %s",
                    (sym,),
                )
            ).fetchone()
        if row is None:
            return None
        raw = _as_row(row).get("sector")
        if not isinstance(raw, str) or not raw.strip():
            return None
        return raw.strip()

    async def list_symbols_in_sector(self, sector: str) -> list[str]:
        if not isinstance(sector, str) or not sector.strip():
            return []
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT symbol FROM stocks
                    WHERE sector IS NOT NULL AND btrim(sector) = %s
                    ORDER BY symbol ASC
                    """,
                    (sector.strip(),),
                )
            ).fetchall()
        out: list[str] = []
        for row in _as_rows(rows):
            raw = row.get("symbol")
            if isinstance(raw, str) and raw.strip():
                out.append(raw.strip().upper())
        return out

    async def get_latest_filing_yoy(self, symbol: str) -> dict[str, float | None]:
        """Latest exact/approx YoY deltas for extract_ok filings (fail soft)."""
        empty: dict[str, float | None] = {
            "eps_yoy_pct": None,
            "rev_yoy_pct": None,
            "profit_yoy_pct": None,
        }
        if not isinstance(symbol, str) or not symbol.strip():
            return empty
        sym = symbol.strip().upper()
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    SELECT
                        fc.eps_delta_pct,
                        fc.revenue_delta_pct,
                        fc.profit_delta_pct
                    FROM filing_metrics fm
                    JOIN filing_comparisons fc
                      ON fc.filing_metrics_id = fm.id
                    WHERE fm.symbol = %s
                      AND fm.extract_ok = TRUE
                      AND fc.match_quality IN ('exact_yoy', 'approx_yoy')
                    ORDER BY fm.fiscal_period_end DESC NULLS LAST, fm.id DESC
                    LIMIT 1
                    """,
                    (sym,),
                )
            ).fetchone()
        if row is None:
            return empty
        data = _as_row(row)

        def _pct(key: str) -> float | None:
            val = data.get(key)
            if isinstance(val, bool) or not isinstance(val, int | float):
                return None
            if not math.isfinite(float(val)):
                return None
            return float(val)

        return {
            "eps_yoy_pct": _pct("eps_delta_pct"),
            "rev_yoy_pct": _pct("revenue_delta_pct"),
            "profit_yoy_pct": _pct("profit_delta_pct"),
        }

    async def count_disclosure_categories_since(
        self, symbol: str, *, since: datetime
    ) -> dict[str, int]:
        """Category → count for disclosures since ``since`` (fail soft)."""
        if not isinstance(symbol, str) or not symbol.strip():
            return {}
        if not isinstance(since, datetime):
            return {}
        sym = symbol.strip().upper()
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT COALESCE(NULLIF(btrim(category), ''), 'uncategorized') AS cat,
                           COUNT(*)::int AS n
                    FROM disclosures
                    WHERE symbol = %s AND published_at >= %s
                    GROUP BY 1
                    """,
                    (sym, since),
                )
            ).fetchall()
        out: dict[str, int] = {}
        for row in _as_rows(rows):
            cat = row.get("cat")
            n = _pg_count(row.get("n"))
            if isinstance(cat, str) and cat.strip() and n is not None and n > 0:
                out[cat.strip()[:64]] = n
        return out

    async def latest_index_change_pct(self, code: str = "ASPI") -> float | None:
        """Latest persisted index change_pct (intraday board; not multi-week)."""
        if not isinstance(code, str) or not code.strip():
            return None
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    SELECT change_pct
                    FROM index_snapshots
                    WHERE code = %s AND change_pct IS NOT NULL
                    ORDER BY ts DESC
                    LIMIT 1
                    """,
                    (code.strip().upper(),),
                )
            ).fetchone()
        if row is None:
            return None
        val = _as_row(row).get("change_pct")
        if isinstance(val, bool) or not isinstance(val, int | float):
            return None
        if not math.isfinite(float(val)):
            return None
        # CSE stores percent points (e.g. 0.14) or fraction — normalize if huge.
        pct = float(val)
        # If already fraction-like tiny, keep; if looks like percent points keep as-is
        # for comparison against symbol ret * 100 below in score job.
        return pct

    async def count_notices_since(self, symbol: str, *, since: datetime) -> int:
        """Count buy-in / non-compliance / halt notices for ``symbol`` since."""
        by_type = await self.count_notices_by_type_since(symbol, since=since)
        return sum(by_type.values())

    async def count_notices_by_type_since(
        self, symbol: str, *, since: datetime
    ) -> dict[str, int]:
        """Per-type notice counts for ``symbol`` since ``since``."""
        if not isinstance(symbol, str) or not symbol.strip():
            return {}
        if not isinstance(since, datetime):
            return {}
        sym = symbol.strip().upper()
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT notice_type, COUNT(*)::int AS n
                    FROM market_notices
                    WHERE symbol = %s AND published_at >= %s
                    GROUP BY notice_type
                    """,
                    (sym, since),
                )
            ).fetchall()
        out: dict[str, int] = {}
        for row in _as_rows(rows):
            kind = row.get("notice_type")
            n = _pg_count(row.get("n"))
            if (
                isinstance(kind, str)
                and kind in {"buy_in", "non_compliance", "halt"}
                and n is not None
                and n > 0
            ):
                out[kind] = n
        return out

    async def get_paired_listing_symbol(self, symbol: str) -> str | None:
        """Return the other voting/share class ticker if present (``.N`` ↔ ``.X``)."""
        if not isinstance(symbol, str) or not symbol.strip():
            return None
        sym = symbol.strip().upper()
        if ".N" in sym:
            pair = sym.replace(".N", ".X", 1)
        elif ".X" in sym:
            pair = sym.replace(".X", ".N", 1)
        else:
            return None
        if pair == sym:
            return None
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    "SELECT 1 FROM stocks WHERE symbol = %s",
                    (pair,),
                )
            ).fetchone()
        return pair if row is not None else None

    async def count_disclosures_since(self, symbol: str, *, since: datetime) -> int:
        if not isinstance(symbol, str) or not symbol.strip():
            return 0
        if not isinstance(since, datetime):
            return 0
        sym = symbol.strip().upper()
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    SELECT COUNT(*)::int AS n
                    FROM disclosures
                    WHERE symbol = %s AND published_at >= %s
                    """,
                    (sym, since),
                )
            ).fetchone()
        if row is None:
            return 0
        counted = _pg_count(_as_row(row).get("n"))
        return 0 if counted is None else counted

    async def list_daily_bars(self, symbol: str) -> list[DailyBar]:
        """Return ascending daily bars for ``symbol``."""
        if not isinstance(symbol, str):
            return []
        symbol = symbol.strip().upper()
        if not symbol:
            return []
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT symbol, trade_date, price, high, low, open, volume,
                           source_period, bar_ts
                    FROM daily_bars
                    WHERE symbol = %s
                    ORDER BY trade_date ASC
                    """,
                    (symbol,),
                )
            ).fetchall()
        out: list[DailyBar] = []
        for row in _as_rows(rows):
            raw_sym = row.get("symbol")
            raw_price = row.get("price")
            raw_period = row.get("source_period")
            trade_date = row.get("trade_date")
            bar_ts = row.get("bar_ts")
            if not isinstance(raw_sym, str) or not raw_sym.strip():
                continue
            if isinstance(raw_price, bool) or not isinstance(raw_price, int | float):
                continue
            if not math.isfinite(float(raw_price)):
                continue
            if isinstance(raw_period, bool) or not isinstance(raw_period, int):
                continue
            if not isinstance(trade_date, date) or not isinstance(bar_ts, datetime):
                continue
            try:
                out.append(
                    DailyBar(
                        symbol=raw_sym.strip().upper(),
                        trade_date=trade_date,
                        price=float(raw_price),
                        high=row.get("high"),
                        low=row.get("low"),
                        open=row.get("open"),
                        volume=row.get("volume"),
                        source_period=raw_period,
                        bar_ts=bar_ts,
                    )
                )
            except (TypeError, ValueError):
                continue
        return out

    async def upsert_symbol_score(
        self,
        *,
        symbol: str,
        as_of: date,
        model_version: str,
        score: float,
        components: dict[str, Any],
        reasons: list[str],
        bar_count: int,
    ) -> None:
        if not isinstance(symbol, str) or not symbol.strip():
            return
        if not isinstance(model_version, str) or not model_version.strip():
            return
        if not isinstance(as_of, date):
            return
        if isinstance(score, bool) or not isinstance(score, int | float) or not math.isfinite(
            score
        ):
            return
        sym = symbol.strip().upper()
        version = model_version.strip()
        safe_reasons = [
            r.strip()
            for r in reasons
            if isinstance(r, str) and r.strip()
        ]
        count = bar_count if isinstance(bar_count, int) and not isinstance(bar_count, bool) else 0
        if count < 0:
            count = 0
        # Json wrapper — plain dict can fail depending on adapter settings.
        payload = components if isinstance(components, dict) else {}
        async with self._pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO symbol_scores (
                    symbol, as_of, model_version, score, components, reasons, bar_count
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol, as_of, model_version) DO UPDATE SET
                    score = EXCLUDED.score,
                    components = EXCLUDED.components,
                    reasons = EXCLUDED.reasons,
                    bar_count = EXCLUDED.bar_count,
                    computed_at = now()
                """,
                (
                    sym,
                    as_of,
                    version,
                    float(score),
                    Json(payload),
                    safe_reasons,
                    count,
                ),
            )

    async def replace_forecast_points(self, points: list[ForecastPoint]) -> int:
        """Replace one symbol/model/as_of forecast series (delete + insert)."""
        if not points:
            return 0
        symbol = points[0].symbol
        version = points[0].model_version
        as_of = points[0].as_of
        if not isinstance(symbol, str) or not symbol.strip():
            return 0
        if not isinstance(version, str) or not version.strip():
            return 0
        if not isinstance(as_of, date):
            return 0
        sym = symbol.strip().upper()
        clean: list[ForecastPoint] = []
        for p in points:
            if p.symbol.strip().upper() != sym:
                continue
            if p.model_version != version or p.as_of != as_of:
                continue
            if (
                isinstance(p.yhat, bool)
                or not isinstance(p.yhat, int | float)
                or not math.isfinite(p.yhat)
            ):
                continue
            clean.append(p)
        if not clean:
            return 0
        async with self._pool.connection() as conn, conn.transaction():
            await conn.execute(
                """
                DELETE FROM forecast_points
                WHERE symbol = %s AND model_version = %s AND as_of = %s
                """,
                (sym, version, as_of),
            )
            import json as _json

            await conn.execute(
                """
                INSERT INTO forecast_points (
                    symbol, model_version, horizon_i, as_of, ts, yhat,
                    confidence, confidence_band, gate, reasons
                )
                SELECT
                    symbol, model_version, horizon_i, as_of, ts, yhat,
                    confidence, confidence_band, gate, reasons::jsonb
                FROM UNNEST(
                    %s::text[],
                    %s::text[],
                    %s::smallint[],
                    %s::date[],
                    %s::timestamptz[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::text[],
                    %s::text[],
                    %s::text[]
                ) AS t(
                    symbol, model_version, horizon_i, as_of, ts, yhat,
                    confidence, confidence_band, gate, reasons
                )
                """,
                (
                    [p.symbol for p in clean],
                    [p.model_version for p in clean],
                    [p.horizon_i for p in clean],
                    [p.as_of for p in clean],
                    [p.ts for p in clean],
                    [float(p.yhat) for p in clean],
                    [
                        float(p.confidence)
                        if p.confidence is not None
                        and isinstance(p.confidence, int | float)
                        and not isinstance(p.confidence, bool)
                        and math.isfinite(float(p.confidence))
                        else None
                        for p in clean
                    ],
                    [p.confidence_band for p in clean],
                    [p.gate for p in clean],
                    [_json.dumps(list(p.reasons or [])) for p in clean],
                ),
            )
        return len(clean)

    async def persist_index_snapshots(
        self,
        indexes: list[IndexSnapshot],
    ) -> list[IndexSnapshot]:
        """Insert market index snapshots from ``aspiData`` / ``snpData``."""
        if not indexes:
            return []

        by_code: dict[str, IndexSnapshot] = {}
        for index in indexes:
            # Fail closed — non-string code used to throw on .strip and abort
            # both index persists.
            if not isinstance(index.code, str):
                continue
            code = index.code.strip().upper()
            if not code:
                continue
            if not math.isfinite(index.value):
                continue
            by_code[code] = index.model_copy(update={"code": code})
        if not by_code:
            return []

        rows = list(by_code.values())
        async with self._pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO index_snapshots (
                    code, name, value, change, change_pct, ts
                )
                SELECT code, name, value, change, change_pct, ts
                FROM UNNEST(
                    %s::text[],
                    %s::text[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::double precision[],
                    %s::timestamptz[]
                ) AS t(code, name, value, change, change_pct, ts)
                """,
                (
                    [s.code for s in rows],
                    [s.name for s in rows],
                    [s.value for s in rows],
                    [s.change for s in rows],
                    [s.change_pct for s in rows],
                    [s.ts for s in rows],
                ),
            )
        return rows

    async def latest_snapshot(self, symbol: str) -> PriceSnapshot | None:
        # Fail closed — non-string symbol used to throw on .strip mid lookup.
        if not isinstance(symbol, str):
            return None
        symbol = symbol.strip().upper()
        if not symbol:
            return None
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    SELECT * FROM price_snapshots
                    WHERE symbol = %s
                    ORDER BY ts DESC, id DESC
                    LIMIT 1
                    """,
                    (symbol,),
                )
            ).fetchone()
        if not row:
            return None
        return _row_to_snapshot(_as_row(row))

    async def previous_snapshot(self, symbol: str, *, before_id: int) -> PriceSnapshot | None:
        # Fail closed — non-string symbol used to throw on .strip mid lookup.
        if not isinstance(symbol, str):
            return None
        symbol = symbol.strip().upper()
        if not symbol:
            return None
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    SELECT * FROM price_snapshots
                    WHERE symbol = %s
                      AND id < %s
                      AND source = 'poller'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (symbol, before_id),
                )
            ).fetchone()
        if not row:
            return None
        return _row_to_snapshot(_as_row(row))

    async def get_previous_state(self, symbol: str, *, before_id: int) -> PreviousPriceState:
        # Fail closed — non-string symbol used to throw on .strip after
        # previous_snapshot already returned None (parity previous_snapshot).
        empty = PreviousPriceState(
            price=None,
            change_pct=None,
            move_fired_keys=set(),
            avg_volume=None,
            avg_crossing_volume=None,
            activity_fired_keys=set(),
        )
        if not isinstance(symbol, str):
            return empty
        symbol = symbol.strip().upper()
        if not symbol:
            return empty
        prev = await self.previous_snapshot(symbol, before_id=before_id)
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT al.event_key
                    FROM alert_log al
                    JOIN alert_rules ar ON ar.id = al.rule_id
                    WHERE ar.symbol = %s
                      AND (
                        al.event_key LIKE 'move:%%'
                        OR al.event_key LIKE 'volspike:%%'
                        OR al.event_key LIKE 'volup:%%'
                        OR al.event_key LIKE 'voldown:%%'
                        OR al.event_key LIKE 'xvol:%%'
                        OR al.event_key LIKE 'gap:%%'
                      )
                    """,
                    (symbol,),
                )
            ).fetchall()
            keys = {r["event_key"] for r in _as_rows(rows)}
            move_keys = {k for k in keys if k.startswith("move:")}
            activity_keys = keys - move_keys
            avg_row = await (
                await conn.execute(
                    """
                    SELECT
                        AVG(day_vol) AS avg_volume,
                        AVG(day_xvol) AS avg_crossing_volume
                    FROM (
                        SELECT
                            (ps.ts AT TIME ZONE 'Asia/Colombo')::date AS d,
                            MAX(ps.volume) AS day_vol,
                            MAX(ps.crossing_volume) AS day_xvol
                        FROM price_snapshots ps
                        WHERE ps.symbol = %s
                          AND ps.id < %s
                          AND ps.source = 'poller'
                          AND (ps.ts AT TIME ZONE 'Asia/Colombo')::date
                              < (now() AT TIME ZONE 'Asia/Colombo')::date
                        GROUP BY 1
                        ORDER BY 1 DESC
                        LIMIT 20
                    ) daily
                    """,
                    (symbol, before_id),
                )
            ).fetchone()
        avg_volume = None
        avg_crossing = None
        if avg_row is not None:
            ar = _as_row(avg_row)
            for key, dest in (
                ("avg_volume", "avg_volume"),
                ("avg_crossing_volume", "avg_crossing"),
            ):
                raw = ar.get(key)
                if isinstance(raw, bool):
                    continue
                try:
                    val = float(raw) if raw is not None else None
                except (TypeError, ValueError):
                    val = None
                if val is not None and math.isfinite(val):
                    if dest == "avg_volume":
                        avg_volume = val
                    else:
                        avg_crossing = val
        if prev is None:
            return PreviousPriceState(
                price=None,
                change_pct=None,
                move_fired_keys=move_keys,
                avg_volume=avg_volume,
                avg_crossing_volume=avg_crossing,
                activity_fired_keys=activity_keys,
            )
        return PreviousPriceState(
            price=prev.price,
            change_pct=prev.change_pct,
            move_fired_keys=move_keys,
            avg_volume=avg_volume,
            avg_crossing_volume=avg_crossing,
            activity_fired_keys=activity_keys,
        )

    async def upsert_big_print(self, print_: BigPrint) -> BigPrint:
        """Insert or return existing day-tape print; sets just_inserted."""
        if not isinstance(print_.symbol, str) or not print_.symbol.strip():
            raise ValueError("big print symbol required")
        symbol = print_.symbol.strip().upper()
        await self.upsert_stock(symbol)
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    INSERT INTO big_prints
                        (external_id, symbol, price, quantity, traded_at, seen_at)
                    VALUES (%s, %s, %s, %s, %s, COALESCE(%s, now()))
                    ON CONFLICT (external_id, symbol) DO UPDATE SET
                        price = COALESCE(EXCLUDED.price, big_prints.price),
                        quantity = EXCLUDED.quantity,
                        traded_at = COALESCE(EXCLUDED.traded_at, big_prints.traded_at)
                    RETURNING id, external_id, symbol, price, quantity, traded_at, seen_at,
                              (xmax = 0) AS just_inserted
                    """,
                    (
                        print_.external_id,
                        symbol,
                        print_.price,
                        print_.quantity,
                        print_.traded_at,
                        print_.seen_at,
                    ),
                )
            ).fetchone()
        assert row is not None
        r = _as_row(row)
        return BigPrint(
            id=r["id"],
            external_id=r["external_id"],
            symbol=r["symbol"],
            price=r.get("price"),
            quantity=r["quantity"],
            traded_at=r.get("traded_at"),
            seen_at=r.get("seen_at"),
            just_inserted=bool(r.get("just_inserted")),
        )

    async def upsert_market_notice(self, notice: MarketNotice) -> MarketNotice:
        """Insert or update a market notice; sets just_inserted on first insert."""
        if notice.notice_type not in {"buy_in", "non_compliance", "halt"}:
            raise ValueError("invalid notice_type")
        symbol = None
        if isinstance(notice.symbol, str) and notice.symbol.strip():
            symbol = notice.symbol.strip().upper()
            await self.upsert_stock(symbol)
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    INSERT INTO market_notices
                        (external_id, notice_type, symbol, title, body, url, published_at, seen_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, COALESCE(%s, now()))
                    ON CONFLICT (external_id, notice_type) DO UPDATE SET
                        symbol = COALESCE(EXCLUDED.symbol, market_notices.symbol),
                        title = EXCLUDED.title,
                        body = COALESCE(EXCLUDED.body, market_notices.body),
                        url = COALESCE(EXCLUDED.url, market_notices.url),
                        published_at = EXCLUDED.published_at
                    RETURNING id, external_id, notice_type, symbol, title, body, url,
                              published_at, seen_at,
                              (xmax = 0) AS just_inserted
                    """,
                    (
                        notice.external_id,
                        notice.notice_type,
                        symbol,
                        notice.title,
                        notice.body,
                        notice.url,
                        notice.published_at,
                        notice.seen_at,
                    ),
                )
            ).fetchone()
        assert row is not None
        r = _as_row(row)
        return MarketNotice(
            id=r["id"],
            external_id=r["external_id"],
            notice_type=r["notice_type"],
            symbol=r.get("symbol"),
            title=r["title"],
            body=r.get("body"),
            url=r.get("url"),
            published_at=r["published_at"],
            seen_at=r.get("seen_at"),
            just_inserted=bool(r.get("just_inserted")),
        )

    async def resolve_symbol_by_company_name(self, company: str | None) -> str | None:
        """Map a CSE company/name string to a unique stocks.symbol.

        Collapses whitespace (CSE stocks often have double spaces in ``name``;
        notice boards usually do not). Ambiguous matches return None.
        """
        if not isinstance(company, str) or not company.strip():
            return None
        # Skip market-ops labels that are not issuers.
        collapsed = " ".join(company.split()).upper()
        if not collapsed or collapsed in {
            "TRADING AND MARKET SURVEILLANCE",
            "COLOMBO STOCK EXCHANGE",
            "CSE",
        }:
            return None
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT symbol
                    FROM stocks
                    WHERE name IS NOT NULL
                      AND regexp_replace(upper(btrim(name)), '\\s+', ' ', 'g')
                          = %s
                    LIMIT 2
                    """,
                    (collapsed,),
                )
            ).fetchall()
        if len(rows) != 1:
            return None
        sym = _as_row(rows[0]).get("symbol")
        return sym.strip().upper() if isinstance(sym, str) and sym.strip() else None

    async def list_latest_scores(
        self, *, model_version: str
    ) -> dict[str, float]:
        """Latest score per symbol for ``model_version`` (for rank autocorr)."""
        if not isinstance(model_version, str) or not model_version.strip():
            return {}
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT DISTINCT ON (symbol)
                        symbol, score
                    FROM symbol_scores
                    WHERE model_version = %s
                    ORDER BY symbol ASC, as_of DESC, computed_at DESC
                    """,
                    (model_version.strip(),),
                )
            ).fetchall()
        out: dict[str, float] = {}
        for row in _as_rows(rows):
            sym = row.get("symbol")
            score = row.get("score")
            if not isinstance(sym, str) or not sym.strip():
                continue
            if isinstance(score, bool) or not isinstance(score, int | float):
                continue
            if not math.isfinite(float(score)):
                continue
            out[sym.strip().upper()] = float(score)
        return out

    async def enqueue_disclosure_brief(
        self,
        disclosure_id: int,
        *,
        status: str = "pending",
    ) -> bool:
        """Insert a disclosure_briefs ledger row; no-op if one already exists.

        Returns True when a row was inserted. Default status is ``pending``;
        callers that honour ``briefs_enabled()`` pass ``skipped`` when AI
        briefs are off so Phase 2 can still see the row.
        """
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    INSERT INTO disclosure_briefs (disclosure_id, status)
                    VALUES (%s, %s)
                    ON CONFLICT (disclosure_id) DO NOTHING
                    RETURNING disclosure_id
                    """,
                    (disclosure_id, status),
                )
            ).fetchone()
        return row is not None

    async def promote_recent_skipped_briefs(
        self,
        *,
        max_age_hours: int = 24,
        limit: int = 100,
    ) -> int:
        """Re-queue recent ``skipped`` briefs as ``pending`` when AI is enabled.

        Rows enqueued while ``AI_BRIEFS_ENABLED=0`` stay ``skipped`` forever
        unless promoted. Bounded by age + limit so flipping the flag on cannot
        dump the entire historical archive into the daily cap.
        """
        hours = max(0, int(max_age_hours))
        if hours <= 0:
            return 0
        batch = max(1, int(limit))
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    WITH picked AS (
                        SELECT disclosure_id
                        FROM disclosure_briefs
                        WHERE status = 'skipped'
                          AND created_at >= now() - (%s * interval '1 hour')
                        ORDER BY created_at ASC
                        LIMIT %s
                        FOR UPDATE SKIP LOCKED
                    )
                    UPDATE disclosure_briefs b
                    SET
                        status = 'pending',
                        updated_at = now(),
                        error = NULL
                    FROM picked
                    WHERE b.disclosure_id = picked.disclosure_id
                    RETURNING b.disclosure_id
                    """,
                    (hours, batch),
                )
            ).fetchall()
        return len(rows)

    async def list_ready_briefs_for_followup_sweep(
        self,
        *,
        limit: int = 20,
        max_age_days: int = 7,
    ) -> list[dict[str, Any]]:
        """Ready briefs eligible for late Telegram follow-up (idempotent claim).

        Covers the race where a brief became ready while the primary disclosure
        alert was still undelivered (deferred / unsent). ``claim_brief_followups``
        remains the durable gate — this only lists candidates that still have at
        least one delivered primary without a ``brief_followup:`` row (so a
        newest-N window cannot starve older ready briefs forever).
        """
        if limit <= 0:
            return []
        days = max(1, int(max_age_days))
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT
                        b.disclosure_id,
                        b.brief,
                        d.external_id,
                        d.symbol,
                        d.title,
                        d.url
                    FROM disclosure_briefs b
                    JOIN disclosures d ON d.id = b.disclosure_id
                    WHERE b.status = 'ready'
                      AND b.brief IS NOT NULL
                      AND btrim(b.brief) <> ''
                      AND b.updated_at >= now() - (%s * interval '1 day')
                      AND EXISTS (
                          SELECT 1
                          FROM alert_rules ar
                          JOIN alert_log al
                            ON al.rule_id = ar.id
                           AND al.event_key = 'disclosure:' || ar.id::text
                               || ':' || d.external_id
                          WHERE ar.active
                            AND ar.type = 'disclosure'
                            AND ar.symbol = d.symbol
                            AND (al.message_sent OR al.delivery_attempted_ok)
                            AND (
                                al.message_text IS NULL
                                OR position(
                                    chr(10) || chr(10) || b.brief
                                    || chr(10) || chr(10)
                                    IN al.message_text
                                ) = 0
                            )
                            AND NOT EXISTS (
                                SELECT 1
                                FROM alert_log fu
                                WHERE fu.rule_id = ar.id
                                  AND fu.event_key = 'brief_followup:'
                                      || ar.id::text || ':' || d.external_id
                            )
                      )
                    ORDER BY b.updated_at ASC
                    LIMIT %s
                    """,
                    (days, limit),
                )
            ).fetchall()
        return _as_rows(rows)

    async def claim_pending_briefs(
        self,
        *,
        limit: int = 5,
        max_briefs_per_day: int | None = None,
        stale_processing_minutes: int = 15,
        pdf_grace_seconds: int = 120,
        cdn_backoff_seconds: int = 300,
    ) -> list[dict[str, Any]]:
        """Lease pending (or stale processing) briefs as ``processing``.

        Takes a transaction-scoped advisory lock when ``max_briefs_per_day`` is
        set so concurrent drainers cannot race past the daily cap. Marks rows
        ``processing`` before returning so FOR UPDATE ending does not allow
        double-claim. Stale ``processing`` rows older than
        ``stale_processing_minutes`` are reclaimable after a crash.

        PDF grace: rows without a non-empty ``disclosures.pdf_url`` are skipped
        until ``updated_at`` is older than ``pdf_grace_seconds`` so legacy enrich
        can land before a title-only summarize burns the daily cap. Uses
        ``updated_at`` (not ``created_at``) so ``promote_recent_skipped_briefs``
        restarts the grace window. ``0`` claims immediately (title-only ok).

        CDN backoff: pending rows that already have an ``error`` (transient CDN
        miss requeue) and a non-empty ``pdf_url`` are skipped until
        ``updated_at`` ages past ``cdn_backoff_seconds`` so a flapping CDN
        cannot starve newer briefs or hammer the host every drain tick.
        ``0`` disables backoff (immediate reclaim).
        """
        if limit <= 0:
            return []
        # Fail closed — bool soft-accepts via int(True)==1 shorten grace/backoff.
        grace = (
            max(0, pdf_grace_seconds)
            if isinstance(pdf_grace_seconds, int)
            and not isinstance(pdf_grace_seconds, bool)
            else 0
        )
        cdn_backoff = (
            max(0, cdn_backoff_seconds)
            if isinstance(cdn_backoff_seconds, int)
            and not isinstance(cdn_backoff_seconds, bool)
            else 0
        )
        async with self._pool.connection() as conn, conn.transaction():
            if max_briefs_per_day is not None:
                # Fail closed — bool soft-accepts via int(True)==1 understate the
                # daily cap and skew remaining batch size.
                if (
                    isinstance(max_briefs_per_day, bool)
                    or not isinstance(max_briefs_per_day, int)
                    or max_briefs_per_day < 0
                ):
                    return []
                # Must stay distinct from poller.POLL_LOCK_ID (session try-lock).
                # Same-id would nest session hold + blocking xact wait on a pool
                # conn and can deadlock under max_size=2. See docs/factory/passes/
                # ADVISORY_LOCK_DEADLOCK.md (wave10 audit — not a live bug).
                await conn.execute(
                    "SELECT pg_advisory_xact_lock(%s)",
                    (BRIEF_CAP_LOCK_ID,),
                )
                used_row = await (
                    await conn.execute(
                        """
                        SELECT COUNT(*)::int AS n
                        FROM disclosure_briefs
                        WHERE updated_at >= date_trunc('day', now() AT TIME ZONE 'UTC')
                          AND (
                              status IN ('ready', 'failed')
                              OR (
                                  status = 'processing'
                                  AND updated_at
                                      >= now() - (%s * interval '1 minute')
                              )
                          )
                        """,
                        (stale_processing_minutes,),
                    )
                ).fetchone()
                # Fail closed — bool soft-accept via int(True)==1 understates
                # daily use and over-claims past AI_MAX_BRIEFS_PER_DAY.
                raw_n = _as_row(used_row).get("n") if used_row else 0
                used = _pg_count(raw_n)
                if used is None:
                    return []
                remaining = max(0, max_briefs_per_day - used)
                if remaining <= 0:
                    return []
                batch = min(limit, remaining)
            else:
                batch = limit

            rows = await (
                await conn.execute(
                    """
                    WITH picked AS (
                        SELECT b.disclosure_id
                        FROM disclosure_briefs b
                        JOIN disclosures d ON d.id = b.disclosure_id
                        WHERE (
                            b.status = 'pending'
                            OR (
                                b.status = 'processing'
                                AND b.updated_at
                                    < now() - (%s * interval '1 minute')
                            )
                        )
                        AND (
                            NULLIF(btrim(d.pdf_url), '') IS NOT NULL
                            OR b.updated_at
                                < now() - (%s * interval '1 second')
                        )
                        AND (
                            b.error IS NULL
                            OR NULLIF(btrim(d.pdf_url), '') IS NULL
                            OR b.updated_at
                                < now() - (%s * interval '1 second')
                        )
                        ORDER BY b.created_at ASC
                        LIMIT %s
                        FOR UPDATE OF b SKIP LOCKED
                    ),
                    claimed AS (
                        UPDATE disclosure_briefs b
                        SET
                            status = 'processing',
                            updated_at = now(),
                            error = NULL
                        FROM picked
                        WHERE b.disclosure_id = picked.disclosure_id
                        RETURNING b.disclosure_id
                    )
                    SELECT
                        c.disclosure_id,
                        d.external_id,
                        d.symbol,
                        d.title,
                        d.url,
                        d.pdf_url
                    FROM claimed c
                    JOIN disclosures d ON d.id = c.disclosure_id
                    """,
                    (stale_processing_minutes, grace, cdn_backoff, batch),
                )
            ).fetchall()
        return _as_rows(rows)

    async def claim_brief_followups(
        self,
        *,
        external_id: str,
        symbol: str,
        brief: str,
        message_text: str,
        lease_seconds: int = 120,
    ) -> list[dict[str, Any]]:
        """Claim Telegram follow-ups for a ready brief (idempotent, no double send).

        Only targets users who already have a *delivered* primary disclosure alert
        for this filing (``disclosure:{rule_id}:{external_id}`` with
        ``message_sent`` or ``delivery_attempted_ok``). Skips recipients whose
        primary message already embeds the brief as its own paragraph (blank-line
        delimited — avoids title/URL substring false skips). Inserts
        ``brief_followup:{rule_id}:{external_id}`` into ``alert_log`` with a
        delivery lease — concurrent callers and retries collide on
        UNIQUE(rule_id, event_key).
        """
        # Fail closed — non-string args used to throw on .strip mid brief follow-up claim.
        ext = external_id.strip() if isinstance(external_id, str) else ""
        sym = symbol.strip().upper() if isinstance(symbol, str) else ""
        brief_text = brief.strip() if isinstance(brief, str) else ""
        msg = message_text if isinstance(message_text, str) else ""
        if not ext or not sym or not brief_text or not msg.strip():
            return []
        # Fail closed — bool soft-accepts via int(True)==1 shorten reclaim races.
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int):
            lease_seconds = 120
        lease = max(1, int(lease_seconds))
        async with self._pool.connection() as conn, conn.transaction():
            rows = await (
                await conn.execute(
                    """
                    WITH primary_alerts AS (
                        SELECT
                            ar.id AS rule_id,
                            u.telegram_id
                        FROM alert_rules ar
                        JOIN users u ON u.id = ar.user_id
                        JOIN alert_log al
                          ON al.rule_id = ar.id
                         AND al.event_key = 'disclosure:' || ar.id::text || ':' || %s
                        WHERE ar.active
                          AND ar.type = 'disclosure'
                          AND ar.symbol = %s
                          AND (al.message_sent OR al.delivery_attempted_ok)
                          AND (
                              al.message_text IS NULL
                              OR position(
                                  chr(10) || chr(10) || %s || chr(10) || chr(10)
                                  IN al.message_text
                              ) = 0
                          )
                    ),
                    inserted AS (
                        INSERT INTO alert_log (
                            rule_id,
                            snapshot_id,
                            event_key,
                            message_sent,
                            message_text,
                            delivery_lease_until
                        )
                        SELECT
                            p.rule_id,
                            NULL,
                            'brief_followup:' || p.rule_id::text || ':' || %s,
                            FALSE,
                            %s,
                            now() + (%s * interval '1 second')
                        FROM primary_alerts p
                        ON CONFLICT (rule_id, event_key) DO NOTHING
                        RETURNING id, rule_id, message_text
                    )
                    SELECT
                        i.id,
                        i.rule_id,
                        i.message_text,
                        u.telegram_id
                    FROM inserted i
                    JOIN alert_rules ar ON ar.id = i.rule_id
                    JOIN users u ON u.id = ar.user_id
                    """,
                    (ext, sym, brief_text, ext, msg, lease),
                )
            ).fetchall()
        return _as_rows(rows)

    async def mark_brief_ready(
        self,
        disclosure_id: int,
        *,
        brief: str,
        model: str,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
    ) -> bool:
        """Mark a claimed (processing) brief row ready with generated text.

        Sanitizes/caps the brief body at write time so a hostile provider
        response cannot land an unbounded control-laden blob in Postgres
        (Telegram + dash egress also sanitize, but storage is the choke point).
        """
        from koel.domain import sanitize_brief_body

        cleaned = sanitize_brief_body(brief)
        if cleaned is None:
            # Fail closed: do not leave status=processing or persist garbage.
            raise ValueError("brief empty after sanitize")
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    UPDATE disclosure_briefs
                    SET
                        status = 'ready',
                        brief = %s,
                        model = %s,
                        tokens_in = %s,
                        tokens_out = %s,
                        error = NULL,
                        updated_at = now()
                    WHERE disclosure_id = %s
                      AND status IN (
                          'pending', 'processing', 'failed', 'skipped'
                      )
                    RETURNING disclosure_id
                    """,
                    (cleaned, model, tokens_in, tokens_out, disclosure_id),
                )
            ).fetchone()
        return row is not None

    async def mark_brief_failed(
        self,
        disclosure_id: int,
        *,
        error: str,
        model: str | None = None,
    ) -> bool:
        """Mark a claimed brief row failed (keeps prior brief null)."""
        err = (error or "unknown")[:2000]
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    UPDATE disclosure_briefs
                    SET
                        status = 'failed',
                        error = %s,
                        model = COALESCE(%s, model),
                        updated_at = now()
                    WHERE disclosure_id = %s
                      AND status IN ('pending', 'processing')
                    RETURNING disclosure_id
                    """,
                    (err, model, disclosure_id),
                )
            ).fetchone()
        return row is not None

    async def requeue_brief_pending(
        self,
        disclosure_id: int,
        *,
        error: str,
    ) -> bool:
        """Return a claimed brief to ``pending`` for a later retry.

        Used for transient CDN fetch misses so we do not burn the daily cap
        on a permanent ``failed`` row (``failed`` counts toward
        ``max_briefs_per_day``; ``pending`` does not).
        """
        err = (error or "unknown")[:2000]
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    UPDATE disclosure_briefs
                    SET
                        status = 'pending',
                        error = %s,
                        updated_at = now()
                    WHERE disclosure_id = %s
                      AND status IN ('pending', 'processing')
                    RETURNING disclosure_id
                    """,
                    (err, disclosure_id),
                )
            ).fetchone()
        return row is not None

    async def count_briefs_today(self, *, stale_processing_minutes: int = 15) -> int:
        """Count today's completed briefs plus non-stale in-flight processing."""
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    SELECT COUNT(*)::int AS n
                    FROM disclosure_briefs
                    WHERE updated_at >= date_trunc('day', now() AT TIME ZONE 'UTC')
                      AND (
                          status IN ('ready', 'failed')
                          OR (
                              status = 'processing'
                              AND updated_at
                                  >= now() - (%s * interval '1 minute')
                          )
                      )
                    """,
                    (stale_processing_minutes,),
                )
            ).fetchone()
        if row is None:
            return 0
        # Fail closed — bool soft-accept via int(True)==1 understates daily use.
        counted = _pg_count(_as_row(row).get("n"))
        if counted is None:
            raise ValueError("count_briefs_today n failed validation")
        return counted

    async def upsert_disclosure(self, disc: Disclosure) -> Disclosure:
        """Insert or update disclosure; always return it with a DB id.

        ON CONFLICT updates title so RETURNING id always yields a row — callers
        can re-evaluate rules after a crash between insert and claim without
        permanently skipping the disclosure. Existing ``pdf_url`` is preserved
        and returned so enrichment can skip already-resolved rows.

        On a true insert (``xmax = 0``), enqueues a ``disclosure_briefs`` row:
        ``pending`` when briefs are enabled, ``skipped`` otherwise. Updates
        never enqueue again (idempotent with ON CONFLICT DO NOTHING).
        """
        from koel.briefs import BriefStatus, briefs_enabled

        await self.upsert_stock(disc.symbol, disc.company_name)
        async with self._pool.connection() as conn, conn.transaction():
            row = await (
                await conn.execute(
                    """
                    INSERT INTO disclosures (
                        external_id, symbol, title, category, url, company_name,
                        published_at, seen_at, pdf_url
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (external_id, symbol) DO UPDATE SET
                        title = EXCLUDED.title
                    RETURNING
                        id,
                        title,
                        category,
                        url,
                        company_name,
                        published_at,
                        seen_at,
                        pdf_url,
                        (xmax = 0) AS inserted
                    """,
                    (
                        disc.external_id,
                        disc.symbol,
                        disc.title,
                        disc.category,
                        disc.url,
                        disc.company_name,
                        disc.published_at,
                        disc.seen_at,
                        disc.pdf_url,
                    ),
                )
            ).fetchone()
            assert row is not None
            data = _as_row(row)
            # Fail closed — bool ids soft-accept via int(True)==1; lists abort
            # mid disclosure upsert (parity market persist / row mappers).
            raw_id = data.get("id")
            if isinstance(raw_id, bool) or not isinstance(raw_id, int):
                raise ValueError("disclosure row id failed validation")
            disclosure_id = raw_id
            existing_pdf = data.get("pdf_url")
            stored_published_at = data.get("published_at")
            if not isinstance(stored_published_at, datetime):
                stored_published_at = disc.published_at
            stored_seen_at = data.get("seen_at")
            if not isinstance(stored_seen_at, datetime):
                stored_seen_at = disc.seen_at
            stored_title = data.get("title") if "title" in data else disc.title
            if not isinstance(stored_title, str):
                stored_title = disc.title
            stored_category = data.get("category") if "category" in data else disc.category
            if stored_category is not None and not isinstance(stored_category, str):
                stored_category = disc.category
            stored_url = data.get("url") if "url" in data else disc.url
            if not isinstance(stored_url, str):
                stored_url = disc.url
            stored_company_name = (
                data.get("company_name") if "company_name" in data else disc.company_name
            )
            if stored_company_name is not None and not isinstance(stored_company_name, str):
                stored_company_name = disc.company_name
            # Fail closed — bool("false")/1 used to soft-accept via bool() and
            # falsely mark re-upserts as just_inserted (duplicate alert fires).
            raw_ins = data.get("inserted")
            just_inserted = raw_ins is True
            if just_inserted:
                brief_status = BriefStatus.PENDING if briefs_enabled() else BriefStatus.SKIPPED
                await conn.execute(
                    """
                    INSERT INTO disclosure_briefs (disclosure_id, status)
                    VALUES (%s, %s)
                    ON CONFLICT (disclosure_id) DO NOTHING
                    """,
                    (disclosure_id, brief_status.value),
                )
        return disc.model_copy(
            update={
                "id": disclosure_id,
                "title": stored_title,
                "category": stored_category,
                "url": stored_url,
                "company_name": stored_company_name,
                "published_at": stored_published_at,
                "seen_at": stored_seen_at,
                "pdf_url": (
                    existing_pdf
                    if isinstance(existing_pdf, str) and existing_pdf
                    else disc.pdf_url
                ),
                "just_inserted": just_inserted,
            }
        )

    async def set_disclosure_pdf_url(self, disclosure_id: int, pdf_url: str) -> bool:
        """Fill ``disclosures.pdf_url`` when known; never overwrite a real URL.

        Blank / whitespace-only ``pdf_url`` values are treated as missing (same
        as claim PDF-grace) so enrich can still land. Only
        ``https://cdn.cse.lk/...`` URLs are persisted (SSRF guard). Returns True
        if a row was updated. Fail-soft callers treat False / errors as
        non-blocking for alerts.
        """
        from koel.adapters.cse import resolve_pdf_url

        normalized = resolve_pdf_url(pdf_url)
        if not normalized:
            return False
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    UPDATE disclosures
                    SET pdf_url = %s
                    WHERE id = %s
                      AND NULLIF(btrim(pdf_url), '') IS NULL
                    RETURNING id
                    """,
                    (normalized, disclosure_id),
                )
            ).fetchone()
        return row is not None

    async def upsert_dividend_event_from_disclosure(
        self,
        *,
        symbol: str,
        disclosure_id: int | None,
        title: str | None,
        category: str | None,
        brief: str | None = None,
        published_at: datetime | None = None,
    ) -> Any:
        """Parse dividend hints from disclosure text and upsert ``dividend_events``.

        Returns the stored ``DividendEvent`` or None when not a dividend filing /
        nothing useful to store. Fail-soft for poller.
        """
        from koel.dividends import (
            DividendEvent,
            hints_raw_hash,
            is_dividend_disclosure,
            merge_dividend_hints,
        )

        if not is_dividend_disclosure(category, title):
            return None
        hints = merge_dividend_hints(title, category, brief)
        # Need at least one of DPS / XD / pay / dates_tbd to persist.
        if (
            hints.dps is None
            and hints.d_xd is None
            and hints.d_pay is None
            and not hints.dates_tbd
        ):
            return None
        d_ann = hints.d_ann
        if d_ann is None and published_at is not None:
            try:
                from koel.dividends import colombo_today

                d_ann = colombo_today(published_at)
            except Exception:
                d_ann = None
        clean_title = (title or "").strip()[:500] or None
        raw_hash = hints_raw_hash(symbol, clean_title or "", hints)
        async with self._pool.connection() as conn:
            if disclosure_id is not None:
                row = await (
                    await conn.execute(
                        """
                        INSERT INTO dividend_events (
                            symbol, disclosure_id, d_ann, d_xd, d_pay, dps,
                            kind, fy, dates_tbd, title, source, raw_hash
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, 'cse_disclosure', %s
                        )
                        ON CONFLICT (disclosure_id) WHERE disclosure_id IS NOT NULL
                        DO UPDATE SET
                            d_ann = COALESCE(EXCLUDED.d_ann, dividend_events.d_ann),
                            d_xd = COALESCE(EXCLUDED.d_xd, dividend_events.d_xd),
                            d_pay = COALESCE(EXCLUDED.d_pay, dividend_events.d_pay),
                            dps = COALESCE(EXCLUDED.dps, dividend_events.dps),
                            kind = COALESCE(EXCLUDED.kind, dividend_events.kind),
                            fy = COALESCE(EXCLUDED.fy, dividend_events.fy),
                            dates_tbd = EXCLUDED.dates_tbd OR dividend_events.dates_tbd,
                            title = COALESCE(EXCLUDED.title, dividend_events.title),
                            raw_hash = EXCLUDED.raw_hash,
                            updated_at = now()
                        RETURNING id, symbol, disclosure_id, d_ann, d_xd, d_pay, dps,
                                  kind, fy, dates_tbd, title, source, raw_hash
                        """,
                        (
                            symbol,
                            disclosure_id,
                            d_ann,
                            hints.d_xd,
                            hints.d_pay,
                            hints.dps,
                            hints.kind,
                            hints.fy,
                            hints.dates_tbd,
                            clean_title,
                            raw_hash,
                        ),
                    )
                ).fetchone()
            else:
                if hints.d_xd is None:
                    return None
                row = await (
                    await conn.execute(
                        """
                        INSERT INTO dividend_events (
                            symbol, disclosure_id, d_ann, d_xd, d_pay, dps,
                            kind, fy, dates_tbd, title, source, raw_hash
                        ) VALUES (
                            %s, NULL, %s, %s, %s, %s,
                            %s, %s, %s, %s, 'cse_disclosure', %s
                        )
                        ON CONFLICT (symbol, d_xd, dps, source)
                            WHERE disclosure_id IS NULL AND d_xd IS NOT NULL
                        DO UPDATE SET
                            d_ann = COALESCE(EXCLUDED.d_ann, dividend_events.d_ann),
                            d_pay = COALESCE(EXCLUDED.d_pay, dividend_events.d_pay),
                            kind = COALESCE(EXCLUDED.kind, dividend_events.kind),
                            fy = COALESCE(EXCLUDED.fy, dividend_events.fy),
                            dates_tbd = EXCLUDED.dates_tbd OR dividend_events.dates_tbd,
                            title = COALESCE(EXCLUDED.title, dividend_events.title),
                            raw_hash = EXCLUDED.raw_hash,
                            updated_at = now()
                        RETURNING id, symbol, disclosure_id, d_ann, d_xd, d_pay, dps,
                                  kind, fy, dates_tbd, title, source, raw_hash
                        """,
                        (
                            symbol,
                            d_ann,
                            hints.d_xd,
                            hints.d_pay,
                            hints.dps,
                            hints.kind,
                            hints.fy,
                            hints.dates_tbd,
                            clean_title,
                            raw_hash,
                        ),
                    )
                ).fetchone()
        if row is None:
            return None
        data = _as_row(row)
        return DividendEvent(
            id=_require_pg_int(data.get("id"), what="dividend_events.id"),
            symbol=str(data.get("symbol") or symbol),
            disclosure_id=(
                _require_pg_int(data["disclosure_id"], what="disclosure_id")
                if data.get("disclosure_id") is not None
                else None
            ),
            d_ann=data.get("d_ann"),
            d_xd=data.get("d_xd"),
            d_pay=data.get("d_pay"),
            dps=data.get("dps"),
            kind=data.get("kind") if isinstance(data.get("kind"), str) else None,
            fy=data.get("fy") if isinstance(data.get("fy"), str) else None,
            dates_tbd=data.get("dates_tbd") is True,
            title=data.get("title") if isinstance(data.get("title"), str) else None,
            source=str(data.get("source") or "cse_disclosure"),
            raw_hash=data.get("raw_hash") if isinstance(data.get("raw_hash"), str) else None,
        )

    async def upsert_corporate_action_from_disclosure(
        self,
        *,
        symbol: str,
        disclosure_id: int | None,
        title: str | None,
        category: str | None,
        published_at: datetime | None = None,
    ) -> Any:
        """Parse split/consolidation hints and upsert ``corporate_actions``.

        Returns stored ``CorporateAction`` or None when not a split filing.
        """
        from koel.corporate_actions import (
            colombo_today,
            hints_raw_hash,
            is_split_disclosure,
            parse_split_hints,
            row_to_corporate_action,
        )

        if not is_split_disclosure(category, title):
            return None
        hints = parse_split_hints(title, category)
        if (
            hints.kind is None
            or hints.ratio_from is None
            or hints.ratio_to is None
        ):
            return None
        effective = hints.effective_date
        if effective is None and published_at is not None:
            try:
                effective = colombo_today(published_at)
            except Exception:
                effective = None
        if effective is None:
            effective = colombo_today()
        clean_title = (title or "").strip()[:500] or None
        raw_hash = hints_raw_hash(symbol, clean_title or "", hints)
        async with self._pool.connection() as conn:
            if disclosure_id is not None:
                row = await (
                    await conn.execute(
                        """
                        INSERT INTO corporate_actions (
                            symbol, disclosure_id, effective_date, kind,
                            ratio_from, ratio_to, title, source, raw_hash
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s, 'cse_disclosure', %s
                        )
                        ON CONFLICT (disclosure_id) WHERE disclosure_id IS NOT NULL
                        DO UPDATE SET
                            effective_date = EXCLUDED.effective_date,
                            kind = EXCLUDED.kind,
                            ratio_from = EXCLUDED.ratio_from,
                            ratio_to = EXCLUDED.ratio_to,
                            title = COALESCE(EXCLUDED.title, corporate_actions.title),
                            raw_hash = EXCLUDED.raw_hash,
                            updated_at = now()
                        RETURNING id, symbol, disclosure_id, effective_date, kind,
                                  ratio_from, ratio_to, title, source, raw_hash
                        """,
                        (
                            symbol,
                            disclosure_id,
                            effective,
                            hints.kind,
                            hints.ratio_from,
                            hints.ratio_to,
                            clean_title,
                            raw_hash,
                        ),
                    )
                ).fetchone()
            else:
                row = await (
                    await conn.execute(
                        """
                        INSERT INTO corporate_actions (
                            symbol, disclosure_id, effective_date, kind,
                            ratio_from, ratio_to, title, source, raw_hash
                        ) VALUES (
                            %s, NULL, %s, %s,
                            %s, %s, %s, 'cse_disclosure', %s
                        )
                        ON CONFLICT (symbol, effective_date, kind, ratio_from,
                                     ratio_to, source)
                            WHERE disclosure_id IS NULL
                        DO UPDATE SET
                            title = COALESCE(EXCLUDED.title, corporate_actions.title),
                            raw_hash = EXCLUDED.raw_hash,
                            updated_at = now()
                        RETURNING id, symbol, disclosure_id, effective_date, kind,
                                  ratio_from, ratio_to, title, source, raw_hash
                        """,
                        (
                            symbol,
                            effective,
                            hints.kind,
                            hints.ratio_from,
                            hints.ratio_to,
                            clean_title,
                            raw_hash,
                        ),
                    )
                ).fetchone()
        if row is None:
            return None
        return row_to_corporate_action(_as_row(row))

    async def upsert_corporate_action_from_price(
        self,
        *,
        symbol: str,
        prev_price: float | None,
        curr_price: float | None,
        as_of: datetime | date | None = None,
    ) -> Any:
        """Persist a price-ratio detected split/consolidation for chart adjust."""
        from koel.corporate_actions import (
            colombo_today,
            detect_share_split_ratio,
            row_to_corporate_action,
        )

        hit = detect_share_split_ratio(prev_price, curr_price)
        if hit is None:
            return None
        effective = colombo_today(as_of)
        title = (
            f"Detected {hit.ratio_from}:{hit.ratio_to} {hit.kind} "
            f"(session ratio ×{hit.observed_ratio:.3f})"
        )
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    INSERT INTO corporate_actions (
                        symbol, disclosure_id, effective_date, kind,
                        ratio_from, ratio_to, title, source, raw_hash
                    ) VALUES (
                        %s, NULL, %s, %s,
                        %s, %s, %s, 'price_ratio', %s
                    )
                    ON CONFLICT (symbol, effective_date, kind, ratio_from,
                                 ratio_to, source)
                        WHERE disclosure_id IS NULL
                    DO UPDATE SET
                        title = COALESCE(EXCLUDED.title, corporate_actions.title),
                        raw_hash = EXCLUDED.raw_hash,
                        updated_at = now()
                    RETURNING id, symbol, disclosure_id, effective_date, kind,
                              ratio_from, ratio_to, title, source, raw_hash
                    """,
                    (
                        symbol,
                        effective,
                        hit.kind,
                        hit.ratio_from,
                        hit.ratio_to,
                        title[:500],
                        f"price:{symbol}:{effective}:{hit.kind}:"
                        f"{hit.ratio_from}:{hit.ratio_to}",
                    ),
                )
            ).fetchone()
        if row is None:
            return None
        return row_to_corporate_action(_as_row(row))

    async def list_corporate_actions(
        self,
        *,
        symbol: str,
        limit: int = 50,
    ) -> list[Any]:
        """Corporate actions for a symbol, newest effective_date first."""
        from koel.corporate_actions import row_to_corporate_action

        lim = max(1, min(int(limit), 200))
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT id, symbol, disclosure_id, effective_date, kind,
                           ratio_from, ratio_to, title, source, raw_hash
                    FROM corporate_actions
                    WHERE symbol = %s
                    ORDER BY effective_date DESC, id DESC
                    LIMIT %s
                    """,
                    (symbol, lim),
                )
            ).fetchall()
        return [row_to_corporate_action(_as_row(r)) for r in rows]

    async def list_upcoming_dividend_events(
        self,
        *,
        symbols: Sequence[str] | None = None,
        horizon_days: int = 14,
        limit: int = 50,
    ) -> list[Any]:
        """Upcoming XD rows (Colombo today → today+horizon), newest XD first."""
        from koel.dividends import DividendEvent, colombo_today

        days = max(1, min(int(horizon_days), 90))
        lim = max(1, min(int(limit), 200))
        today = colombo_today()
        async with self._pool.connection() as conn:
            if symbols:
                syms = [s for s in symbols if isinstance(s, str) and s]
                if not syms:
                    return []
                rows = await (
                    await conn.execute(
                        """
                        SELECT id, symbol, disclosure_id, d_ann, d_xd, d_pay, dps,
                               kind, fy, dates_tbd, title, source, raw_hash
                        FROM dividend_events
                        WHERE d_xd IS NOT NULL
                          AND d_xd >= %s
                          AND d_xd <= (%s::date + %s::int)
                          AND symbol = ANY(%s)
                        ORDER BY d_xd ASC, symbol ASC
                        LIMIT %s
                        """,
                        (today, today, days, syms, lim),
                    )
                ).fetchall()
            else:
                rows = await (
                    await conn.execute(
                        """
                        SELECT id, symbol, disclosure_id, d_ann, d_xd, d_pay, dps,
                               kind, fy, dates_tbd, title, source, raw_hash
                        FROM dividend_events
                        WHERE d_xd IS NOT NULL
                          AND d_xd >= %s
                          AND d_xd <= (%s::date + %s::int)
                        ORDER BY d_xd ASC, symbol ASC
                        LIMIT %s
                        """,
                        (today, today, days, lim),
                    )
                ).fetchall()
        out: list[DividendEvent] = []
        for row in rows:
            data = _as_row(row)
            try:
                out.append(
                    DividendEvent(
                        id=_require_pg_int(data.get("id"), what="dividend_events.id"),
                        symbol=str(data.get("symbol")),
                        disclosure_id=(
                            _require_pg_int(data["disclosure_id"], what="disclosure_id")
                            if data.get("disclosure_id") is not None
                            else None
                        ),
                        d_ann=data.get("d_ann"),
                        d_xd=data.get("d_xd"),
                        d_pay=data.get("d_pay"),
                        dps=data.get("dps"),
                        kind=data.get("kind") if isinstance(data.get("kind"), str) else None,
                        fy=data.get("fy") if isinstance(data.get("fy"), str) else None,
                        dates_tbd=data.get("dates_tbd") is True,
                        title=data.get("title") if isinstance(data.get("title"), str) else None,
                        source=str(data.get("source") or "cse_disclosure"),
                        raw_hash=(
                            data.get("raw_hash")
                            if isinstance(data.get("raw_hash"), str)
                            else None
                        ),
                    )
                )
            except Exception:
                continue
        return out

    async def list_dividend_events_for_symbol(
        self,
        symbol: str,
        *,
        limit: int = 40,
    ) -> list[Any]:
        from koel.dividends import DividendEvent

        lim = max(1, min(int(limit), 100))
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT id, symbol, disclosure_id, d_ann, d_xd, d_pay, dps,
                           kind, fy, dates_tbd, title, source, raw_hash
                    FROM dividend_events
                    WHERE symbol = %s
                    ORDER BY COALESCE(d_xd, d_ann, DATE '1970-01-01') DESC, id DESC
                    LIMIT %s
                    """,
                    (symbol, lim),
                )
            ).fetchall()
        out: list[DividendEvent] = []
        for row in rows:
            data = _as_row(row)
            try:
                out.append(
                    DividendEvent(
                        id=_require_pg_int(data.get("id"), what="dividend_events.id"),
                        symbol=str(data.get("symbol")),
                        disclosure_id=(
                            _require_pg_int(data["disclosure_id"], what="disclosure_id")
                            if data.get("disclosure_id") is not None
                            else None
                        ),
                        d_ann=data.get("d_ann"),
                        d_xd=data.get("d_xd"),
                        d_pay=data.get("d_pay"),
                        dps=data.get("dps"),
                        kind=data.get("kind") if isinstance(data.get("kind"), str) else None,
                        fy=data.get("fy") if isinstance(data.get("fy"), str) else None,
                        dates_tbd=data.get("dates_tbd") is True,
                        title=data.get("title") if isinstance(data.get("title"), str) else None,
                        source=str(data.get("source") or "cse_disclosure"),
                        raw_hash=(
                            data.get("raw_hash")
                            if isinstance(data.get("raw_hash"), str)
                            else None
                        ),
                    )
                )
            except Exception:
                continue
        return out

    async def sync_dividend_events_from_recent_disclosures(
        self,
        *,
        limit: int = 200,
    ) -> int:
        """Backfill/refresh dividend_events from recent dividend-labelled disclosures."""
        lim = max(1, min(int(limit), 500))
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT d.id, d.symbol, d.title, d.category, d.published_at,
                           b.brief, b.status AS brief_status
                    FROM disclosures d
                    LEFT JOIN disclosure_briefs b ON b.disclosure_id = d.id
                    WHERE d.category ILIKE '%%dividend%%'
                       OR d.title ILIKE '%%dividend%%'
                       OR d.category ILIKE '%%cash div%%'
                       OR d.title ILIKE '%%cash div%%'
                    ORDER BY d.published_at DESC, d.id DESC
                    LIMIT %s
                    """,
                    (lim,),
                )
            ).fetchall()
        n = 0
        for row in rows:
            data = _as_row(row)
            brief = None
            if data.get("brief_status") == "ready" and isinstance(data.get("brief"), str):
                brief = data["brief"]
            try:
                stored = await self.upsert_dividend_event_from_disclosure(
                    symbol=str(data.get("symbol")),
                    disclosure_id=_require_pg_int(data.get("id"), what="disclosures.id"),
                    title=data.get("title") if isinstance(data.get("title"), str) else None,
                    category=(
                        data.get("category")
                        if isinstance(data.get("category"), str)
                        else None
                    ),
                    brief=brief,
                    published_at=data.get("published_at"),
                )
            except Exception:
                continue
            if stored is not None:
                n += 1
        return n

    async def get_disclosure_by_id(self, disclosure_id: int) -> Disclosure | None:
        """Load a disclosure row by id (metrics worker)."""
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    SELECT id, external_id, symbol, title, category, url, company_name,
                           published_at, seen_at, pdf_url
                    FROM disclosures
                    WHERE id = %s
                    """,
                    (disclosure_id,),
                )
            ).fetchone()
        if row is None:
            return None
        return self._disclosure_from_row(_as_row(row))

    def _disclosure_from_row(self, r: dict[str, Any]) -> Disclosure | None:
        try:
            return Disclosure(
                id=int(r["id"]),
                external_id=str(r["external_id"]),
                symbol=str(r["symbol"]),
                title=str(r["title"]),
                category=r.get("category"),
                url=str(r["url"]),
                company_name=r.get("company_name"),
                published_at=r["published_at"],
                seen_at=r["seen_at"],
                pdf_url=r.get("pdf_url"),
            )
        except Exception:
            return None

    async def list_disclosures_missing_pdf(
        self,
        *,
        limit: int = 20,
        watched_only: bool = True,
    ) -> list[Disclosure]:
        """Disclosures with no ``pdf_url`` — for scheduled enrich drains."""
        lim = max(1, min(int(limit), 500)) if not isinstance(limit, bool) else 20
        watched_sql = (
            """
            AND d.symbol IN (SELECT DISTINCT symbol FROM watchlist_items)
            """
            if watched_only
            else ""
        )
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    f"""
                    SELECT d.id, d.external_id, d.symbol, d.title, d.category, d.url,
                           d.company_name, d.published_at, d.seen_at, d.pdf_url
                    FROM disclosures d
                    WHERE d.pdf_url IS NULL
                    {watched_sql}
                    ORDER BY d.id ASC
                    LIMIT %s
                    """,
                    (lim,),
                )
            ).fetchall()
        out: list[Disclosure] = []
        for row in _as_rows(rows):
            disc = self._disclosure_from_row(row)
            if disc is not None:
                out.append(disc)
        return out

    async def list_disclosures_pending_metrics(
        self,
        *,
        limit: int = 20,
        watched_only: bool = True,
    ) -> list[Disclosure]:
        """Financial-candidate disclosures with ``pdf_url`` but no ``filing_metrics``."""
        lim = max(1, min(int(limit), 500)) if not isinstance(limit, bool) else 20
        watched_sql = (
            """
            AND d.symbol IN (SELECT DISTINCT symbol FROM watchlist_items)
            """
            if watched_only
            else ""
        )
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    f"""
                    SELECT d.id, d.external_id, d.symbol, d.title, d.category, d.url,
                           d.company_name, d.published_at, d.seen_at, d.pdf_url
                    FROM disclosures d
                    LEFT JOIN filing_metrics fm ON fm.disclosure_id = d.id
                    WHERE d.pdf_url IS NOT NULL
                      AND fm.id IS NULL
                    {watched_sql}
                    ORDER BY d.id ASC
                    LIMIT %s
                    """,
                    (lim,),
                )
            ).fetchall()
        out: list[Disclosure] = []
        for row in _as_rows(rows):
            disc = self._disclosure_from_row(row)
            if disc is not None:
                out.append(disc)
        return out

    async def upsert_filing_metrics(self, row: dict[str, Any]) -> dict[str, Any]:
        """Insert or update filing_metrics by disclosure_id."""
        import json as _json

        notes = row.get("extract_notes") or {}
        if not isinstance(notes, str):
            notes = _json.dumps(notes)
        async with self._pool.connection() as conn:
            saved = await (
                await conn.execute(
                    """
                    INSERT INTO filing_metrics (
                        disclosure_id, symbol, kind, fiscal_period_end, fiscal_quarter,
                        entity, scale, currency, revenue, profit, eps_basic, eps_diluted,
                        extract_ok, extract_notes, pdf_url
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s::jsonb, %s
                    )
                    ON CONFLICT (disclosure_id) DO UPDATE SET
                        kind = EXCLUDED.kind,
                        fiscal_period_end = EXCLUDED.fiscal_period_end,
                        fiscal_quarter = EXCLUDED.fiscal_quarter,
                        entity = EXCLUDED.entity,
                        scale = EXCLUDED.scale,
                        currency = EXCLUDED.currency,
                        revenue = EXCLUDED.revenue,
                        profit = EXCLUDED.profit,
                        eps_basic = EXCLUDED.eps_basic,
                        eps_diluted = EXCLUDED.eps_diluted,
                        extract_ok = EXCLUDED.extract_ok,
                        extract_notes = EXCLUDED.extract_notes,
                        pdf_url = EXCLUDED.pdf_url
                    RETURNING *
                    """,
                    (
                        row["disclosure_id"],
                        row["symbol"],
                        row.get("kind") or "unknown",
                        row.get("fiscal_period_end"),
                        row.get("fiscal_quarter"),
                        row.get("entity") or "unknown",
                        row.get("scale") or "unknown",
                        row.get("currency") or "LKR",
                        row.get("revenue"),
                        row.get("profit"),
                        row.get("eps_basic"),
                        row.get("eps_diluted"),
                        bool(row.get("extract_ok")),
                        notes,
                        row.get("pdf_url"),
                    ),
                )
            ).fetchone()
        assert saved is not None
        return dict(_as_row(saved))

    async def list_filing_metrics_for_symbol(
        self, symbol: str, *, kind: str | None = None
    ) -> list[dict[str, Any]]:
        async with self._pool.connection() as conn:
            if kind:
                rows = await (
                    await conn.execute(
                        """
                        SELECT * FROM filing_metrics
                        WHERE symbol = %s AND kind = %s
                        ORDER BY fiscal_period_end DESC NULLS LAST, id DESC
                        """,
                        (symbol, kind),
                    )
                ).fetchall()
            else:
                rows = await (
                    await conn.execute(
                        """
                        SELECT * FROM filing_metrics
                        WHERE symbol = %s
                        ORDER BY fiscal_period_end DESC NULLS LAST, id DESC
                        """,
                        (symbol,),
                    )
                ).fetchall()
        return [dict(_as_row(r)) for r in rows]

    async def upsert_filing_comparison(self, row: dict[str, Any]) -> dict[str, Any]:
        async with self._pool.connection() as conn:
            saved = await (
                await conn.execute(
                    """
                    INSERT INTO filing_comparisons (
                        filing_metrics_id, prior_filing_metrics_id, match_quality,
                        eps_delta, eps_delta_pct,
                        revenue_delta, revenue_delta_pct,
                        profit_delta, profit_delta_pct
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s
                    )
                    ON CONFLICT (filing_metrics_id) DO UPDATE SET
                        prior_filing_metrics_id = EXCLUDED.prior_filing_metrics_id,
                        match_quality = EXCLUDED.match_quality,
                        eps_delta = EXCLUDED.eps_delta,
                        eps_delta_pct = EXCLUDED.eps_delta_pct,
                        revenue_delta = EXCLUDED.revenue_delta,
                        revenue_delta_pct = EXCLUDED.revenue_delta_pct,
                        profit_delta = EXCLUDED.profit_delta,
                        profit_delta_pct = EXCLUDED.profit_delta_pct
                    RETURNING *
                    """,
                    (
                        row["filing_metrics_id"],
                        row.get("prior_filing_metrics_id"),
                        row["match_quality"],
                        row.get("eps_delta"),
                        row.get("eps_delta_pct"),
                        row.get("revenue_delta"),
                        row.get("revenue_delta_pct"),
                        row.get("profit_delta"),
                        row.get("profit_delta_pct"),
                    ),
                )
            ).fetchone()
        assert saved is not None
        return dict(_as_row(saved))

    async def get_filing_comparison_for_metrics(
        self, filing_metrics_id: int
    ) -> dict[str, Any] | None:
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    SELECT * FROM filing_comparisons
                    WHERE filing_metrics_id = %s
                    """,
                    (filing_metrics_id,),
                )
            ).fetchone()
        return dict(_as_row(row)) if row is not None else None

    async def list_stock_name_pairs(self) -> list[tuple[str, str | None]]:
        """All ``(symbol, name)`` rows for company-name resolution."""
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT symbol, name
                    FROM stocks
                    WHERE symbol IS NOT NULL
                    ORDER BY symbol ASC
                    """
                )
            ).fetchall()
        out: list[tuple[str, str | None]] = []
        for row in _as_rows(rows):
            sym = row.get("symbol")
            if not isinstance(sym, str) or not sym.strip():
                continue
            name = row.get("name")
            out.append(
                (
                    sym.strip().upper(),
                    name.strip() if isinstance(name, str) and name.strip() else None,
                )
            )
        return out

    async def list_top_symbols_by_market_cap(self, *, limit: int = 60) -> list[str]:
        """Voting-share symbols ordered by latest market cap (desc)."""
        lim = max(1, min(int(limit), 300)) if not isinstance(limit, bool) else 60
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT s.symbol
                    FROM stocks s
                    JOIN LATERAL (
                      SELECT market_cap
                      FROM price_snapshots p
                      WHERE p.symbol = s.symbol AND p.market_cap IS NOT NULL
                      ORDER BY p.ts DESC
                      LIMIT 1
                    ) ps ON TRUE
                    WHERE s.symbol LIKE '%%.N0000'
                      AND s.symbol <> 'MARKET'
                    ORDER BY ps.market_cap DESC NULLS LAST
                    LIMIT %s
                    """,
                    (lim,),
                )
            ).fetchall()
        out: list[str] = []
        for row in _as_rows(rows):
            sym = row.get("symbol")
            if isinstance(sym, str) and sym.strip():
                out.append(sym.strip().upper())
        return out

    async def list_voting_share_symbols(self, *, limit: int | None = None) -> list[str]:
        """All ``*.N0000`` symbols in ``stocks`` (alphabetical)."""
        lim_sql = ""
        params: list[Any] = []
        if (
            limit is not None
            and isinstance(limit, int)
            and not isinstance(limit, bool)
            and limit > 0
        ):
            lim_sql = "LIMIT %s"
            params.append(max(1, min(limit, 500)))
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    f"""
                    SELECT symbol
                    FROM stocks
                    WHERE symbol LIKE '%%.N0000'
                      AND symbol <> 'MARKET'
                    ORDER BY symbol ASC
                    {lim_sql}
                    """,
                    tuple(params),
                )
            ).fetchall()
        out: list[str] = []
        for row in _as_rows(rows):
            sym = row.get("symbol")
            if isinstance(sym, str) and sym.strip():
                out.append(sym.strip().upper())
        return out

    async def deactivate_person_roles_for_symbol(self, symbol: str) -> int:
        """Mark all active person roles for an issuer inactive (CSE replace)."""
        if not isinstance(symbol, str) or not symbol.strip():
            return 0
        sym = symbol.strip().upper()
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    UPDATE person_company_roles
                    SET active = FALSE, updated_at = now()
                    WHERE symbol = %s AND active
                    RETURNING id
                    """,
                    (sym,),
                )
            ).fetchall()
        return len(rows or [])

    async def deactivate_non_cse_person_roles_for_symbol(
        self, symbol: str, *, source: str = "cse_company_profile"
    ) -> int:
        """Deactivate PDF/other seats once official CSE rows exist for symbol."""
        if not isinstance(symbol, str) or not symbol.strip():
            return 0
        sym = symbol.strip().upper()
        src = source if isinstance(source, str) and source.strip() else "cse_company_profile"
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    UPDATE person_company_roles
                    SET active = FALSE, updated_at = now()
                    WHERE symbol = %s
                      AND active
                      AND COALESCE(extract_notes->>'source', '') <> %s
                    RETURNING id
                    """,
                    (sym, src),
                )
            ).fetchall()
        return len(rows or [])

    async def list_disclosures_pending_graph(
        self,
        *,
        limit: int = 20,
        watched_only: bool = True,
        symbols: Sequence[str] | None = None,
    ) -> list[Disclosure]:
        """Disclosures with ``pdf_url`` but no ``filing_graph_extracts`` row."""
        lim = max(1, min(int(limit), 500)) if not isinstance(limit, bool) else 20
        watched_sql = (
            """
            AND d.symbol IN (SELECT DISTINCT symbol FROM watchlist_items)
            """
            if watched_only and not symbols
            else ""
        )
        symbol_sql = ""
        params: list[Any] = []
        if symbols:
            cleaned = [
                s.strip().upper()
                for s in symbols
                if isinstance(s, str) and s.strip()
            ]
            if cleaned:
                symbol_sql = "AND d.symbol = ANY(%s)"
                params.append(cleaned)
        params.append(lim)
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    f"""
                    SELECT d.id, d.external_id, d.symbol, d.title, d.category, d.url,
                           d.company_name, d.published_at, d.seen_at, d.pdf_url
                    FROM disclosures d
                    LEFT JOIN filing_graph_extracts g ON g.disclosure_id = d.id
                    WHERE d.pdf_url IS NOT NULL
                      AND g.id IS NULL
                    {watched_sql}
                    {symbol_sql}
                    ORDER BY d.id ASC
                    LIMIT %s
                    """,
                    tuple(params),
                )
            ).fetchall()
        out: list[Disclosure] = []
        for row in _as_rows(rows):
            disc = self._disclosure_from_row(row)
            if disc is not None:
                out.append(disc)
        return out

    async def upsert_filing_graph_extract(self, row: dict[str, Any]) -> dict[str, Any]:
        import json as _json

        notes = row.get("extract_notes") or {}
        if not isinstance(notes, str):
            notes = _json.dumps(notes)
        async with self._pool.connection() as conn:
            saved = await (
                await conn.execute(
                    """
                    INSERT INTO filing_graph_extracts (
                        disclosure_id, symbol, kind, fiscal_period_end,
                        entity, scale, currency, equity, equity_label,
                        equity_ok, relations_ok, extract_ok, extract_notes, pdf_url
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s::jsonb, %s
                    )
                    ON CONFLICT (disclosure_id) DO UPDATE SET
                        kind = EXCLUDED.kind,
                        fiscal_period_end = EXCLUDED.fiscal_period_end,
                        entity = EXCLUDED.entity,
                        scale = EXCLUDED.scale,
                        currency = EXCLUDED.currency,
                        equity = EXCLUDED.equity,
                        equity_label = EXCLUDED.equity_label,
                        equity_ok = EXCLUDED.equity_ok,
                        relations_ok = EXCLUDED.relations_ok,
                        extract_ok = EXCLUDED.extract_ok,
                        extract_notes = EXCLUDED.extract_notes,
                        pdf_url = EXCLUDED.pdf_url,
                        updated_at = now()
                    RETURNING *
                    """,
                    (
                        row["disclosure_id"],
                        row["symbol"],
                        row.get("kind") or "unknown",
                        row.get("fiscal_period_end"),
                        row.get("entity") or "unknown",
                        row.get("scale") or "unknown",
                        row.get("currency") or "LKR",
                        row.get("equity"),
                        row.get("equity_label"),
                        bool(row.get("equity_ok")),
                        bool(row.get("relations_ok")),
                        bool(row.get("extract_ok")),
                        notes,
                        row.get("pdf_url"),
                    ),
                )
            ).fetchone()
        assert saved is not None
        return dict(_as_row(saved))

    async def upsert_company_graph_node(self, row: dict[str, Any]) -> dict[str, Any]:
        """Upsert listed nodes by symbol; unlisted by name_norm."""
        node_kind = row.get("node_kind") or "listed"
        update_equity = bool(row.get("update_equity"))
        async with self._pool.connection() as conn:
            if node_kind == "listed":
                symbol = row.get("symbol")
                if not isinstance(symbol, str) or not symbol.strip():
                    raise ValueError("listed node requires symbol")
                saved = await (
                    await conn.execute(
                        """
                        INSERT INTO company_graph_nodes (
                            symbol, display_name, name_norm, node_kind,
                            equity, equity_as_of, equity_scale, equity_currency,
                            equity_disclosure_id, equity_confidence
                        ) VALUES (
                            %s, %s, %s, 'listed',
                            %s, %s, %s, %s,
                            %s, %s
                        )
                        ON CONFLICT (symbol) DO UPDATE SET
                            display_name = EXCLUDED.display_name,
                            name_norm = EXCLUDED.name_norm,
                            equity = CASE
                                WHEN %s THEN EXCLUDED.equity
                                ELSE company_graph_nodes.equity
                            END,
                            equity_as_of = CASE
                                WHEN %s THEN EXCLUDED.equity_as_of
                                ELSE company_graph_nodes.equity_as_of
                            END,
                            equity_scale = CASE
                                WHEN %s THEN EXCLUDED.equity_scale
                                ELSE company_graph_nodes.equity_scale
                            END,
                            equity_currency = CASE
                                WHEN %s THEN EXCLUDED.equity_currency
                                ELSE company_graph_nodes.equity_currency
                            END,
                            equity_disclosure_id = CASE
                                WHEN %s THEN EXCLUDED.equity_disclosure_id
                                ELSE company_graph_nodes.equity_disclosure_id
                            END,
                            equity_confidence = CASE
                                WHEN %s THEN EXCLUDED.equity_confidence
                                ELSE company_graph_nodes.equity_confidence
                            END,
                            updated_at = now()
                        RETURNING *
                        """,
                        (
                            symbol.strip().upper(),
                            row.get("display_name") or symbol.strip().upper(),
                            row.get("name_norm")
                            or symbol.strip().upper(),
                            row.get("equity"),
                            row.get("equity_as_of"),
                            row.get("equity_scale") or "unknown",
                            row.get("equity_currency") or "LKR",
                            row.get("equity_disclosure_id"),
                            row.get("equity_confidence") or "none",
                            update_equity,
                            update_equity,
                            update_equity,
                            update_equity,
                            update_equity,
                            update_equity,
                        ),
                    )
                ).fetchone()
            else:
                name_norm = row.get("name_norm")
                if not isinstance(name_norm, str) or not name_norm.strip():
                    raise ValueError("unlisted node requires name_norm")
                saved = await (
                    await conn.execute(
                        """
                        INSERT INTO company_graph_nodes (
                            symbol, display_name, name_norm, node_kind,
                            equity, equity_as_of, equity_scale, equity_currency,
                            equity_disclosure_id, equity_confidence
                        ) VALUES (
                            NULL, %s, %s, 'unlisted',
                            NULL, NULL, 'unknown', 'LKR',
                            NULL, 'none'
                        )
                        ON CONFLICT (name_norm) DO UPDATE SET
                            display_name = EXCLUDED.display_name,
                            updated_at = now()
                        RETURNING *
                        """,
                        (
                            row.get("display_name") or name_norm.strip(),
                            name_norm.strip(),
                        ),
                    )
                ).fetchone()
        assert saved is not None
        return dict(_as_row(saved))

    async def upsert_company_graph_edge(self, row: dict[str, Any]) -> dict[str, Any]:
        import json as _json

        notes = row.get("extract_notes") or {}
        if not isinstance(notes, str):
            notes = _json.dumps(notes)
        async with self._pool.connection() as conn:
            saved = await (
                await conn.execute(
                    """
                    INSERT INTO company_graph_edges (
                        src_node_id, dst_node_id, relation,
                        ownership_pct, ownership_pct_confidence, confidence,
                        evidence_disclosure_id, evidence_page, evidence_snippet,
                        extract_notes, active
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s::jsonb, TRUE
                    )
                    ON CONFLICT (src_node_id, dst_node_id, relation) DO UPDATE SET
                        ownership_pct = COALESCE(
                            EXCLUDED.ownership_pct,
                            company_graph_edges.ownership_pct
                        ),
                        ownership_pct_confidence = CASE
                            WHEN EXCLUDED.ownership_pct IS NOT NULL
                            THEN EXCLUDED.ownership_pct_confidence
                            ELSE company_graph_edges.ownership_pct_confidence
                        END,
                        confidence = CASE
                            WHEN EXCLUDED.confidence = 'high' THEN 'high'
                            WHEN company_graph_edges.confidence = 'high' THEN 'high'
                            WHEN EXCLUDED.confidence = 'medium' THEN 'medium'
                            ELSE company_graph_edges.confidence
                        END,
                        evidence_disclosure_id = EXCLUDED.evidence_disclosure_id,
                        evidence_page = EXCLUDED.evidence_page,
                        evidence_snippet = EXCLUDED.evidence_snippet,
                        extract_notes = EXCLUDED.extract_notes,
                        active = TRUE,
                        updated_at = now()
                    RETURNING *
                    """,
                    (
                        row["src_node_id"],
                        row["dst_node_id"],
                        row["relation"],
                        row.get("ownership_pct"),
                        row.get("ownership_pct_confidence") or "none",
                        row.get("confidence") or "low",
                        row.get("evidence_disclosure_id"),
                        row.get("evidence_page"),
                        row.get("evidence_snippet"),
                        notes,
                    ),
                )
            ).fetchone()
        assert saved is not None
        return dict(_as_row(saved))

    async def get_company_graph_node_by_symbol(
        self, symbol: str
    ) -> dict[str, Any] | None:
        if not isinstance(symbol, str) or not symbol.strip():
            return None
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    SELECT * FROM company_graph_nodes
                    WHERE symbol = %s
                    """,
                    (symbol.strip().upper(),),
                )
            ).fetchone()
        return dict(_as_row(row)) if row is not None else None

    async def list_disclosures_pending_people(
        self,
        *,
        limit: int = 20,
        watched_only: bool = True,
        symbols: Sequence[str] | None = None,
    ) -> list[Disclosure]:
        lim = max(1, min(int(limit), 500)) if not isinstance(limit, bool) else 20
        watched_sql = (
            """
            AND d.symbol IN (SELECT DISTINCT symbol FROM watchlist_items)
            """
            if watched_only and not symbols
            else ""
        )
        symbol_sql = ""
        params: list[Any] = []
        if symbols:
            cleaned = [
                s.strip().upper()
                for s in symbols
                if isinstance(s, str) and s.strip()
            ]
            if cleaned:
                symbol_sql = "AND d.symbol = ANY(%s)"
                params.append(cleaned)
        params.append(lim)
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    f"""
                    SELECT d.id, d.external_id, d.symbol, d.title, d.category, d.url,
                           d.company_name, d.published_at, d.seen_at, d.pdf_url
                    FROM disclosures d
                    LEFT JOIN filing_people_extracts g ON g.disclosure_id = d.id
                    WHERE d.pdf_url IS NOT NULL
                      AND g.id IS NULL
                    {watched_sql}
                    {symbol_sql}
                    ORDER BY d.id ASC
                    LIMIT %s
                    """,
                    tuple(params),
                )
            ).fetchall()
        out: list[Disclosure] = []
        for row in _as_rows(rows):
            disc = self._disclosure_from_row(row)
            if disc is not None:
                out.append(disc)
        return out

    async def upsert_filing_people_extract(self, row: dict[str, Any]) -> dict[str, Any]:
        import json as _json

        notes = row.get("extract_notes") or {}
        if not isinstance(notes, str):
            notes = _json.dumps(notes)
        async with self._pool.connection() as conn:
            saved = await (
                await conn.execute(
                    """
                    INSERT INTO filing_people_extracts (
                        disclosure_id, symbol, people_ok, extract_ok,
                        extract_notes, pdf_url
                    ) VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (disclosure_id) DO UPDATE SET
                        people_ok = EXCLUDED.people_ok,
                        extract_ok = EXCLUDED.extract_ok,
                        extract_notes = EXCLUDED.extract_notes,
                        pdf_url = EXCLUDED.pdf_url,
                        updated_at = now()
                    RETURNING *
                    """,
                    (
                        row["disclosure_id"],
                        row["symbol"],
                        bool(row.get("people_ok")),
                        bool(row.get("extract_ok")),
                        notes,
                        row.get("pdf_url"),
                    ),
                )
            ).fetchone()
        assert saved is not None
        return dict(_as_row(saved))

    async def upsert_person(
        self, *, display_name: str, name_norm: str
    ) -> dict[str, Any]:
        if not isinstance(name_norm, str) or not name_norm.strip():
            raise ValueError("name_norm required")
        async with self._pool.connection() as conn:
            saved = await (
                await conn.execute(
                    """
                    INSERT INTO people (display_name, name_norm)
                    VALUES (%s, %s)
                    ON CONFLICT (name_norm) DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        updated_at = now()
                    RETURNING *
                    """,
                    (
                        (display_name or name_norm).strip()[:120],
                        name_norm.strip(),
                    ),
                )
            ).fetchone()
        assert saved is not None
        return dict(_as_row(saved))

    async def upsert_person_company_role(self, row: dict[str, Any]) -> dict[str, Any]:
        import json as _json

        notes = row.get("extract_notes") or {}
        if not isinstance(notes, str):
            notes = _json.dumps(notes)
        async with self._pool.connection() as conn:
            saved = await (
                await conn.execute(
                    """
                    INSERT INTO person_company_roles (
                        person_id, symbol, role, confidence,
                        evidence_disclosure_id, evidence_page, evidence_snippet,
                        extract_notes, active
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s::jsonb, TRUE
                    )
                    ON CONFLICT (person_id, symbol, role) DO UPDATE SET
                        confidence = CASE
                            WHEN EXCLUDED.confidence = 'high' THEN 'high'
                            WHEN person_company_roles.confidence = 'high' THEN 'high'
                            WHEN EXCLUDED.confidence = 'medium' THEN 'medium'
                            ELSE person_company_roles.confidence
                        END,
                        evidence_disclosure_id = EXCLUDED.evidence_disclosure_id,
                        evidence_page = EXCLUDED.evidence_page,
                        evidence_snippet = EXCLUDED.evidence_snippet,
                        extract_notes = EXCLUDED.extract_notes,
                        active = TRUE,
                        updated_at = now()
                    RETURNING *
                    """,
                    (
                        row["person_id"],
                        str(row["symbol"]).strip().upper(),
                        row["role"],
                        row.get("confidence") or "low",
                        row.get("evidence_disclosure_id"),
                        row.get("evidence_page"),
                        row.get("evidence_snippet"),
                        notes,
                    ),
                )
            ).fetchone()
        assert saved is not None
        return dict(_as_row(saved))

    async def get_ready_filing_brief(
        self,
        *,
        disclosure_id: int | None = None,
        external_id: str | None = None,
        symbol: str | None = None,
    ) -> str | None:
        """Return brief text when ``disclosure_briefs.status = ready``.

        Lookup prefers ``disclosure_id``; otherwise ``external_id`` + ``symbol``
        (unique on disclosures). Returns None when missing, not ready, blank,
        or on any DB error (fail-soft — alerts must not wait on briefs).
        """
        try:
            if disclosure_id is not None:
                async with self._pool.connection() as conn:
                    row = await (
                        await conn.execute(
                            """
                            SELECT brief
                            FROM disclosure_briefs
                            WHERE disclosure_id = %s
                              AND status = 'ready'
                              AND brief IS NOT NULL
                              AND btrim(brief) <> ''
                            """,
                            (disclosure_id,),
                        )
                    ).fetchone()
            else:
                # Fail closed — non-string args used to throw on .strip mid brief lookup.
                ext = external_id.strip() if isinstance(external_id, str) else ""
                sym = symbol.strip().upper() if isinstance(symbol, str) else ""
                if not ext or not sym:
                    return None
                async with self._pool.connection() as conn:
                    row = await (
                        await conn.execute(
                            """
                            SELECT b.brief
                            FROM disclosure_briefs b
                            JOIN disclosures d ON d.id = b.disclosure_id
                            WHERE d.external_id = %s
                              AND d.symbol = %s
                              AND b.status = 'ready'
                              AND b.brief IS NOT NULL
                              AND btrim(b.brief) <> ''
                            """,
                            (ext, sym),
                        )
                    ).fetchone()
            if row is None:
                return None
            data = _as_row(row)
            brief = data.get("brief")
            if not isinstance(brief, str):
                return None
            text = brief.strip()
            return text or None
        except Exception:
            return None

    async def get_latest_ready_brief(self, symbol: str) -> dict[str, Any] | None:
        """Latest ``ready`` filing brief for a symbol (read-only lookup).

        Ordered by disclosure ``published_at`` then ``id`` descending. Returns
        ``None`` when missing, blank, or on any DB error (fail-soft).
        """
        # Fail closed — non-string symbol used to throw on .strip mid /brief lookup.
        sym = symbol.strip().upper() if isinstance(symbol, str) else ""
        if not sym:
            return None
        try:
            async with self._pool.connection() as conn:
                row = await (
                    await conn.execute(
                        """
                        SELECT
                            b.brief,
                            d.symbol,
                            d.title,
                            d.url,
                            d.external_id,
                            b.disclosure_id
                        FROM disclosure_briefs b
                        JOIN disclosures d ON d.id = b.disclosure_id
                        WHERE d.symbol = %s
                          AND b.status = 'ready'
                          AND b.brief IS NOT NULL
                          AND btrim(b.brief) <> ''
                        ORDER BY d.published_at DESC NULLS LAST, d.id DESC
                        LIMIT 1
                        """,
                        (sym,),
                    )
                ).fetchone()
            if row is None:
                return None
            data = _as_row(row)
            brief = data.get("brief")
            if not isinstance(brief, str):
                return None
            text = brief.strip()
            if not text:
                return None
            # Fail closed — non-string PG fields used to soft-accept via str()
            # (ints/None became "123"/"None" in /brief lookup egress).
            raw_sym = data.get("symbol")
            sym_out = (
                raw_sym.strip().upper()
                if isinstance(raw_sym, str) and raw_sym.strip()
                else sym
            )
            raw_title = data.get("title")
            raw_url = data.get("url")
            raw_ext = data.get("external_id")
            return {
                "brief": text,
                "symbol": sym_out,
                "title": (
                    raw_title.strip()
                    if isinstance(raw_title, str) and raw_title.strip()
                    else None
                ),
                "url": (
                    raw_url.strip()
                    if isinstance(raw_url, str) and raw_url.strip()
                    else None
                ),
                "external_id": (
                    raw_ext.strip()
                    if isinstance(raw_ext, str) and raw_ext.strip()
                    else None
                ),
                "disclosure_id": data.get("disclosure_id"),
            }
        except Exception:
            return None

    async def insert_disclosure_if_new(self, disc: Disclosure) -> Disclosure | None:
        """Compat wrapper — prefer upsert_disclosure.

        Always returns the stored disclosure with id (never None). Claim
        uniqueness + created_at gating handle dedupe / historical backfill.
        """
        return await self.upsert_disclosure(disc)

    async def ensure_user(self, telegram_id: int) -> int:
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    INSERT INTO users (telegram_id)
                    VALUES (%s)
                    ON CONFLICT (telegram_id) DO UPDATE SET telegram_id = EXCLUDED.telegram_id
                    RETURNING id
                    """,
                    (telegram_id,),
                )
            ).fetchone()
        assert row is not None
        # Fail closed — bool ids soft-accept via int(True)==1 mid /start.
        return _require_pg_int(_as_row(row).get("id"), what="ensure_user RETURNING id")

    async def add_watch(self, user_id: int, symbol: str) -> None:
        # Fail closed — non-string symbol used to throw on .strip mid watch.
        if not isinstance(symbol, str):
            return
        symbol = symbol.strip().upper()
        if not symbol:
            return
        await self.upsert_stock(symbol)
        async with self._pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO watchlist_items (user_id, symbol)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (user_id, symbol),
            )

    async def remove_watch(self, user_id: int, symbol: str) -> bool:
        # Fail closed — non-string symbol used to throw on .strip mid remove.
        if not isinstance(symbol, str):
            return False
        symbol = symbol.strip().upper()
        if not symbol:
            return False
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    DELETE FROM watchlist_items
                    WHERE user_id = %s AND symbol = %s
                    RETURNING symbol
                    """,
                    (user_id, symbol),
                )
            ).fetchone()
        return row is not None

    async def unwatch_symbol(self, user_id: int, symbol: str) -> tuple[bool, int]:
        """Atomically remove watchlist row and deactivate rules for symbol.

        Returns ``(removed_from_watchlist, deactivated_rule_count)`` in one
        transaction so a crash cannot leave active orphans without a watch row.
        """
        # Fail closed — non-string symbol used to throw on .strip mid unwatch.
        if not isinstance(symbol, str):
            return False, 0
        symbol = symbol.strip().upper()
        if not symbol:
            return False, 0
        async with self._pool.connection() as conn, conn.transaction():
            row = await (
                await conn.execute(
                    """
                    DELETE FROM watchlist_items
                    WHERE user_id = %s AND symbol = %s
                    RETURNING symbol
                    """,
                    (user_id, symbol),
                )
            ).fetchone()
            deactivated = await (
                await conn.execute(
                    """
                    UPDATE alert_rules
                    SET active = FALSE
                    WHERE user_id = %s AND symbol = %s AND active
                    RETURNING id
                    """,
                    (user_id, symbol),
                )
            ).fetchall()
        return row is not None, len(_as_rows(deactivated))

    async def list_watchlist(self, user_id: int) -> list[str]:
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT symbol FROM watchlist_items
                    WHERE user_id = %s
                      AND btrim(symbol) <> ''
                    ORDER BY symbol
                    """,
                    (user_id,),
                )
            ).fetchall()
        out: list[str] = []
        for row in _as_rows(rows):
            symbol = _clean_symbol(row.get("symbol"))
            if symbol is not None:
                out.append(symbol)
        return out

    async def watched_symbols(self) -> list[str]:
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT DISTINCT symbol FROM watchlist_items
                    WHERE btrim(symbol) <> ''
                    ORDER BY symbol
                    """
                )
            ).fetchall()
        out: list[str] = []
        seen: set[str] = set()
        for row in _as_rows(rows):
            symbol = _clean_symbol(row.get("symbol"))
            if symbol is not None and symbol not in seen:
                seen.add(symbol)
                out.append(symbol)
        return out

    async def create_alert_rule(
        self,
        user_id: int,
        symbol: str,
        alert_type: AlertType,
        threshold: float | None,
        category: str | None = None,
    ) -> AlertRule:
        """Create or return an identical active rule (idempotent under concurrency).

        Avoids deactivate-then-insert TOCTOU where a parallel caller could
        deactivate the rule id we already returned to the user.
        ``category`` is for disclosure rules only (substring filter); ignored otherwise.
        """
        # Fail closed — non-string symbol used to throw on .strip mid create.
        if not isinstance(symbol, str):
            raise ValueError("symbol must be a non-empty string")
        symbol = symbol.strip().upper()
        if not symbol:
            raise ValueError("symbol must be a non-empty string")
        cat = (
            sanitize_disclosure_category(category)
            if alert_type == AlertType.DISCLOSURE
            else None
        )
        await self.upsert_stock(symbol)
        await self.add_watch(user_id, symbol)
        async with self._pool.connection() as conn:
            existing = await self._fetch_active_rule(
                conn, user_id, symbol, alert_type, threshold, cat
            )
            if existing is not None:
                return existing
            try:
                row = await (
                    await conn.execute(
                        """
                        INSERT INTO alert_rules
                            (user_id, symbol, type, threshold, category, active, armed)
                        VALUES (%s, %s, %s, %s, %s, TRUE, TRUE)
                        RETURNING id, user_id, symbol, type, threshold, category,
                                  active, armed, created_at
                        """,
                        (user_id, symbol, alert_type.value, threshold, cat),
                    )
                ).fetchone()
            except UniqueViolation:
                await conn.rollback()
                raced = await self._fetch_active_rule(
                    conn, user_id, symbol, alert_type, threshold, cat
                )
                if raced is not None:
                    return raced
                raise
            user = await (
                await conn.execute(
                    "SELECT telegram_id FROM users WHERE id = %s",
                    (user_id,),
                )
            ).fetchone()
        assert row is not None and user is not None
        r = _as_row(row)
        u = _as_row(user)
        # Reuse _row_to_rule — manual int()/fromisoformat(str()) used to
        # soft-accept bools (int(True)==1) or abort on poisoned created_at
        # after a successful INSERT.
        r["telegram_id"] = u["telegram_id"]
        rule = _row_to_rule(r)
        if rule is None:
            raise ValueError("inserted alert rule row failed validation")
        return rule

    async def get_user_quiet_hours_by_telegram(
        self, telegram_id: int
    ) -> tuple[int | None, int | None] | None:
        """Return (start_hour, end_hour) in Asia/Colombo local hours, or None.

        Missing user → None. Malformed hours fail closed to (None, None)
        meaning quiet hours off.
        """
        if not isinstance(telegram_id, int) or isinstance(telegram_id, bool):
            return None
        if telegram_id <= 0 or not (telegram_id.bit_length() <= 63):
            return None
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    SELECT quiet_hours_start, quiet_hours_end
                      FROM users
                     WHERE telegram_id = %s
                    """,
                    (telegram_id,),
                )
            ).fetchone()
        if row is None:
            return None
        r = _as_row(row)
        start = r.get("quiet_hours_start")
        end = r.get("quiet_hours_end")
        def _hour(v: object) -> int | None:
            if v is None:
                return None
            if isinstance(v, bool) or not isinstance(v, int):
                return None
            return v if 0 <= v <= 23 else None
        return _hour(start), _hour(end)

    async def list_digest_users(self) -> list[dict[str, Any]]:
        """Users with digest_enabled and a positive telegram_id."""
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT id, telegram_id, last_digest_on
                      FROM users
                     WHERE digest_enabled IS TRUE
                       AND telegram_id IS NOT NULL
                       AND telegram_id > 0
                     ORDER BY id ASC
                    """
                )
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in _as_rows(rows):
            uid = row.get("id")
            tid = row.get("telegram_id")
            if isinstance(uid, bool) or not isinstance(uid, int) or uid <= 0:
                continue
            if isinstance(tid, bool) or not isinstance(tid, int) or tid <= 0:
                continue
            out.append(
                {
                    "id": uid,
                    "telegram_id": tid,
                    "last_digest_on": row.get("last_digest_on"),
                }
            )
        return out

    async def claim_digest_send(self, user_id: int, on_date: date) -> bool:
        """Claim today's digest slot. True if newly claimed (not already sent)."""
        if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
            return False
        if not isinstance(on_date, date):
            return False
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    UPDATE users
                       SET last_digest_on = %s
                     WHERE id = %s
                       AND digest_enabled IS TRUE
                       AND (last_digest_on IS DISTINCT FROM %s)
                    RETURNING id
                    """,
                    (on_date, user_id, on_date),
                )
            ).fetchone()
        return row is not None

    async def list_recent_alert_fires(
        self,
        user_id: int,
        *,
        since: datetime,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Recent alert_log rows for a user (today's fires for digests)."""
        if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
            return []
        if not isinstance(since, datetime):
            return []
        if isinstance(limit, int) and not isinstance(limit, bool):
            lim = max(1, min(limit, 50))
        else:
            lim = 20
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT al.id,
                           al.fired_at,
                           al.message_text,
                           ar.symbol,
                           ar.type,
                           ar.threshold
                      FROM alert_log al
                      JOIN alert_rules ar ON ar.id = al.rule_id
                     WHERE ar.user_id = %s
                       AND al.fired_at >= %s
                       AND COALESCE(al.message_text, '') NOT LIKE '[dry-run]%%'
                     ORDER BY al.fired_at DESC
                     LIMIT %s
                    """,
                    (user_id, since, lim),
                )
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in _as_rows(rows):
            sym = row.get("symbol")
            typ = row.get("type")
            msg = row.get("message_text")
            # Prefer first line of stored message as trigger summary.
            trigger = typ if isinstance(typ, str) else "alert"
            if isinstance(msg, str) and msg.strip():
                first = msg.strip().splitlines()[0].strip()
                if first and not first.startswith("Not financial"):
                    trigger = first[:120]
            out.append(
                {
                    "id": row.get("id"),
                    "symbol": sym if isinstance(sym, str) else "?",
                    "type": typ if isinstance(typ, str) else None,
                    "trigger": trigger,
                    "fired_at": row.get("fired_at"),
                    "threshold": row.get("threshold"),
                }
            )
        return out

    async def list_watchlist_movers(
        self,
        user_id: int,
        *,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Watchlist symbols sorted by |change_pct| from latest poller snaps."""
        if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
            return []
        if isinstance(limit, int) and not isinstance(limit, bool):
            lim = max(1, min(limit, 20))
        else:
            lim = 5
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    WITH latest AS (
                        SELECT DISTINCT ON (ps.symbol)
                               ps.symbol, ps.price, ps.change_pct, ps.ts
                          FROM price_snapshots ps
                          JOIN watchlist_items w
                            ON w.symbol = ps.symbol
                         WHERE w.user_id = %s
                           AND ps.source = 'poller'
                           AND ps.symbol <> 'MARKET'
                         ORDER BY ps.symbol ASC, ps.ts DESC, ps.id DESC
                    )
                    SELECT symbol, price, change_pct, ts
                      FROM latest
                     WHERE change_pct IS NOT NULL
                     ORDER BY ABS(change_pct) DESC NULLS LAST, symbol ASC
                     LIMIT %s
                    """,
                    (user_id, lim),
                )
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in _as_rows(rows):
            sym = row.get("symbol")
            if not isinstance(sym, str) or not sym.strip():
                continue
            out.append(
                {
                    "symbol": sym.strip().upper(),
                    "price": row.get("price"),
                    "change_pct": row.get("change_pct"),
                    "ts": row.get("ts"),
                }
            )
        return out

    async def _fetch_active_rule(
        self,
        conn: Any,
        user_id: int,
        symbol: str,
        alert_type: AlertType,
        threshold: float | None,
        category: str | None = None,
    ) -> AlertRule | None:
        row = await (
            await conn.execute(
                """
                SELECT ar.*, u.telegram_id
                FROM alert_rules ar
                JOIN users u ON u.id = ar.user_id
                WHERE ar.user_id = %s AND ar.symbol = %s AND ar.type = %s
                  AND COALESCE(ar.threshold, -1) = COALESCE(%s, -1)
                  AND COALESCE(ar.category, '') = COALESCE(%s, '')
                  AND ar.active
                ORDER BY ar.id DESC
                LIMIT 1
                """,
                (user_id, symbol, alert_type.value, threshold, category),
            )
        ).fetchone()
        if row is None:
            return None
        return _row_to_rule(_as_row(row))

    async def list_alerts(self, user_id: int) -> list[AlertRule]:
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT ar.*, u.telegram_id
                    FROM alert_rules ar
                    JOIN users u ON u.id = ar.user_id
                    WHERE ar.user_id = %s AND ar.active
                    ORDER BY ar.created_at
                    """,
                    (user_id,),
                )
            ).fetchall()
        out: list[AlertRule] = []
        for r in rows:
            rule = _row_to_rule(_as_row(r))
            if rule is not None:
                out.append(rule)
        return out

    async def active_rules_for_symbols(self, symbols: Sequence[str]) -> list[AlertRule]:
        if not symbols:
            return []
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT ar.*, u.telegram_id
                    FROM alert_rules ar
                    JOIN users u ON u.id = ar.user_id
                    WHERE ar.active AND ar.symbol = ANY(%s)
                    """,
                    (list(symbols),),
                )
            ).fetchall()
        out: list[AlertRule] = []
        for r in rows:
            rule = _row_to_rule(_as_row(r))
            if rule is not None:
                out.append(rule)
        return out

    async def set_rule_armed(self, rule_id: int, armed: bool) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                "UPDATE alert_rules SET armed = %s WHERE id = %s",
                (armed, rule_id),
            )

    async def deactivate_alert(self, user_id: int, rule_id: int) -> bool:
        """Set active=FALSE for user's rule. Return True if a row was updated."""
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    UPDATE alert_rules
                    SET active = FALSE
                    WHERE id = %s AND user_id = %s AND active
                    RETURNING id
                    """,
                    (rule_id, user_id),
                )
            ).fetchone()
        return row is not None

    async def deactivate_rules_for_symbol(self, user_id: int, symbol: str) -> int:
        """Deactivate all active rules for user+symbol. Return count."""
        # Fail closed — non-string symbol used to throw on .strip mid deactivate.
        if not isinstance(symbol, str):
            return 0
        symbol = symbol.strip().upper()
        if not symbol:
            return 0
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    UPDATE alert_rules
                    SET active = FALSE
                    WHERE user_id = %s AND symbol = %s AND active
                    RETURNING id
                    """,
                    (user_id, symbol),
                )
            ).fetchall()
        return len(_as_rows(rows))

    async def try_advisory_lock(self, lock_id: int = 4_201_337) -> bool:
        """Acquire a session advisory lock and HOLD the pooled connection.

        Postgres session locks are connection-scoped. Returning the connection to
        the pool before unlock would leak the lock or unlock a different session.
        """
        if self._lock_conn is not None:
            return False
        cm = self._pool.connection()
        conn = await cm.__aenter__()
        try:
            row = await (
                await conn.execute("SELECT pg_try_advisory_lock(%s) AS locked", (lock_id,))
            ).fetchone()
            # Fail closed — bool(1)/"false" used to soft-accept a held lock
            # (parity upsert_disclosure inserted is True / health ok).
            locked = bool(row) and _as_row(row).get("locked") is True
        except Exception:
            await cm.__aexit__(None, None, None)
            self._lock_cm = None
            self._lock_conn = None
            self._lock_id = None
            raise
        if not locked:
            await cm.__aexit__(None, None, None)
            return False
        self._lock_cm = cm
        self._lock_conn = conn
        self._lock_id = lock_id
        return True

    async def advisory_unlock(self, lock_id: int | None = None) -> None:
        """Release the held session advisory lock and return the connection."""
        if self._lock_conn is None or self._lock_cm is None:
            return
        lid = lock_id if lock_id is not None else self._lock_id
        cm = self._lock_cm
        try:
            if lid is not None:
                await self._lock_conn.execute("SELECT pg_advisory_unlock(%s)", (lid,))
        finally:
            try:
                await cm.__aexit__(None, None, None)
            finally:
                self._lock_cm = None
                self._lock_conn = None
                self._lock_id = None

    async def claim_alert(
        self,
        event: AlertEvent,
        message_text: str,
        *,
        lease_seconds: int = 120,
    ) -> int | None:
        """Insert-first claim. Returns alert_log id if newly claimed, else None.

        Sets ``delivery_lease_until`` so concurrent ``claim_unsent_batch`` cannot
        pick up the row while ``_deliver_pending`` is still sending.
        ``lease_seconds`` is floored to ``>= 1`` so a zero/negative lease cannot
        race with unsent drain (lease-until == now() is immediately reclaimable).
        """
        # Fail closed — bool soft-accepts via int(True)==1 shorten reclaim races.
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int):
            lease_seconds = 120
        lease = max(1, int(lease_seconds))
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    INSERT INTO alert_log (
                        rule_id, snapshot_id, event_key, message_sent, message_text,
                        delivery_lease_until
                    )
                    VALUES (
                        %s, %s, %s, FALSE, %s,
                        now() + (%s * interval '1 second')
                    )
                    ON CONFLICT (rule_id, event_key) DO NOTHING
                    RETURNING id
                    """,
                    (
                        event.rule_id,
                        event.snapshot_id,
                        event.event_key,
                        message_text,
                        lease,
                    ),
                )
            ).fetchone()
        if row is None:
            return None
        # Fail closed — bool ids soft-accept via int(True)==1 mid claim deliver.
        return _require_pg_int(_as_row(row).get("id"), what="claim_alert RETURNING id")

    async def claim_and_disarm(
        self,
        event: AlertEvent,
        message_text: str,
        *,
        lease_seconds: int = 120,
    ) -> int | None:
        """Claim alert and disarm the rule in one transaction (E2-C03).

        Returns alert_log id if newly claimed (rule disarmed). On claim conflict
        (already claimed), skips disarm and returns None.

        Sets ``delivery_lease_until`` like ``claim_alert`` so unsent drain cannot
        double-claim during the in-flight Telegram send.
        ``lease_seconds`` is floored to ``>= 1`` (same as ``claim_alert``).
        """
        # Fail closed — bool soft-accepts via int(True)==1 shorten reclaim races.
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int):
            lease_seconds = 120
        lease = max(1, int(lease_seconds))
        async with self._pool.connection() as conn, conn.transaction():
            row = await (
                await conn.execute(
                    """
                    INSERT INTO alert_log (
                        rule_id, snapshot_id, event_key, message_sent, message_text,
                        delivery_lease_until
                    )
                    VALUES (
                        %s, %s, %s, FALSE, %s,
                        now() + (%s * interval '1 second')
                    )
                    ON CONFLICT (rule_id, event_key) DO NOTHING
                    RETURNING id
                    """,
                    (
                        event.rule_id,
                        event.snapshot_id,
                        event.event_key,
                        message_text,
                        lease,
                    ),
                )
            ).fetchone()
            if row is None:
                return None
            # Fail closed — bool ids soft-accept via int(True)==1 mid claim+disarm
            # (parity claim_alert / ensure_user RETURNING id). Validate before
            # disarm so a poisoned RETURNING id rolls the transaction back.
            raw_id = _require_pg_int(
                _as_row(row).get("id"), what="claim_and_disarm RETURNING id"
            )
            await conn.execute(
                "UPDATE alert_rules SET armed = %s WHERE id = %s",
                (False, event.rule_id),
            )
            return raw_id

    async def mark_delivery_attempted_ok(self, alert_log_id: int) -> None:
        """Record that Telegram accepted the send (before message_sent).

        Survives process restart when ``mark_alert_sent`` fails (E2-C04).
        Clears the delivery lease; ``delivery_attempted_ok`` keeps the row out of
        ``claim_unsent_batch``.
        """
        async with self._pool.connection() as conn:
            await conn.execute(
                """
                UPDATE alert_log
                SET delivery_attempted_ok = TRUE,
                    delivery_lease_until = NULL
                WHERE id = %s
                """,
                (alert_log_id,),
            )

    async def mark_alert_sent(self, alert_log_id: int) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                """
                UPDATE alert_log
                SET message_sent = TRUE,
                    delivery_attempted_ok = TRUE,
                    delivery_lease_until = NULL
                WHERE id = %s
                """,
                (alert_log_id,),
            )

    async def mark_alert_attempt(self, alert_log_id: int) -> int:
        """Increment attempt_count for a failed send. Returns the new count."""
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    UPDATE alert_log
                    SET attempt_count = attempt_count + 1,
                        delivery_lease_until = NULL
                    WHERE id = %s
                    RETURNING attempt_count
                    """,
                    (alert_log_id,),
                )
            ).fetchone()
        assert row is not None
        # Fail closed — bool soft-accepts via int(True)==1 undercount attempts
        # and delay dead-letter (parity format_dead_letter_notify attempts).
        return _require_pg_int(
            _as_row(row).get("attempt_count"),
            what="mark_alert_attempt RETURNING attempt_count",
        )

    async def mark_alert_deferred_attempt(self, alert_log_id: int) -> int:
        """Increment deferred_attempt_count for a RetryAfter defer. Returns the new count.

        Kept separate from ``attempt_count`` so a flood-waited alert is judged
        against ``MAX_DEFERRED_ATTEMPTS``, not the tighter ``MAX_SEND_ATTEMPTS``
        shared with ordinary send failures.
        """
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    UPDATE alert_log
                    SET deferred_attempt_count = deferred_attempt_count + 1,
                        delivery_lease_until = NULL
                    WHERE id = %s
                    RETURNING deferred_attempt_count
                    """,
                    (alert_log_id,),
                )
            ).fetchone()
        assert row is not None
        return _require_pg_int(
            _as_row(row).get("deferred_attempt_count"),
            what="mark_alert_deferred_attempt RETURNING deferred_attempt_count",
        )

    async def dead_letter(self, alert_log_id: int) -> None:
        """Mark an unsent alert as abandoned (skip further retries)."""
        async with self._pool.connection() as conn:
            await conn.execute(
                """
                UPDATE alert_log
                SET dead_lettered = TRUE,
                    delivery_lease_until = NULL
                WHERE id = %s
                """,
                (alert_log_id,),
            )

    async def unsent_alerts(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """List claimable unsent rows (excludes active delivery leases)."""
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT al.id, al.rule_id, al.message_text, al.attempt_count, u.telegram_id
                    FROM alert_log al
                    JOIN alert_rules ar ON ar.id = al.rule_id
                    JOIN users u ON u.id = ar.user_id
                    WHERE al.message_sent = FALSE
                      AND al.dead_lettered = FALSE
                      AND al.delivery_attempted_ok = FALSE
                      AND ar.active = TRUE
                      AND (
                          al.delivery_lease_until IS NULL
                          OR al.delivery_lease_until < now()
                      )
                    ORDER BY al.fired_at
                    LIMIT %s
                    """,
                    (limit,),
                )
            ).fetchall()
        return _as_rows(rows)

    async def claim_unsent_batch(
        self,
        *,
        limit: int = 50,
        lease_seconds: int = 120,
    ) -> list[dict[str, Any]]:
        """Claim unsent rows via FOR UPDATE SKIP LOCKED + delivery lease (E2-C05).

        Locks and leases rows in one short transaction, then returns so Telegram
        send can proceed outside any advisory lock. Concurrent claimers skip
        already-locked or still-leased rows.
        ``lease_seconds`` is floored to ``>= 1`` so zero/negative cannot make
        the lease immediately reclaimable (``<= now()``).
        """
        # Fail closed — bool soft-accepts via int(True)==1 shorten reclaim races.
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int):
            lease_seconds = 120
        lease = max(1, int(lease_seconds))
        async with self._pool.connection() as conn, conn.transaction():
            rows = await (
                await conn.execute(
                    """
                        WITH picked AS (
                            SELECT
                                al.id,
                                al.rule_id,
                                al.message_text,
                                al.attempt_count,
                                u.telegram_id
                            FROM alert_log al
                            JOIN alert_rules ar ON ar.id = al.rule_id
                            JOIN users u ON u.id = ar.user_id
                            WHERE al.message_sent = FALSE
                              AND al.dead_lettered = FALSE
                              AND al.delivery_attempted_ok = FALSE
                              AND ar.active = TRUE
                              AND (
                                  al.delivery_lease_until IS NULL
                                  OR al.delivery_lease_until < now()
                              )
                            ORDER BY al.fired_at
                            LIMIT %s
                            FOR UPDATE OF al SKIP LOCKED
                        ),
                        leased AS (
                            UPDATE alert_log al
                            SET delivery_lease_until =
                                now() + (%s * interval '1 second')
                            FROM picked
                            WHERE al.id = picked.id
                            RETURNING
                                al.id,
                                picked.rule_id,
                                picked.message_text,
                                picked.attempt_count,
                                picked.telegram_id
                        )
                        SELECT * FROM leased
                        """,
                    (limit, lease),
                )
            ).fetchall()
        return _as_rows(rows)

    async def health_check(self) -> bool:
        cm = self._pool.connection()
        started = perf_counter()
        try:
            conn = await cm.__aenter__()
        except Exception:
            self._last_health_checkout_wait_ms = (perf_counter() - started) * 1000
            raise
        self._last_health_checkout_wait_ms = (perf_counter() - started) * 1000
        exc_info: tuple[Any, BaseException, Any] | tuple[None, None, None] = (None, None, None)
        try:
            row = await (await conn.execute("SELECT 1 AS ok")).fetchone()
            # Fail closed — True == 1 soft-accepts a bool ok as healthy.
            raw_ok = _as_row(row).get("ok") if row else None
            return isinstance(raw_ok, int) and not isinstance(raw_ok, bool) and raw_ok == 1
        except BaseException as exc:
            exc_info = (type(exc), exc, exc.__traceback__)
            raise
        finally:
            await cm.__aexit__(*exc_info)

    async def count_pending_disclosure_briefs(self) -> int:
        """Count ``disclosure_briefs`` rows still ``pending`` (ops queue hint)."""
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    SELECT COUNT(*)::int AS n
                    FROM disclosure_briefs
                    WHERE status = 'pending'
                    """
                )
            ).fetchone()
        if row is None:
            return 0
        # Fail closed — bool soft-accept via int(True)==1 mid health hint.
        counted = _pg_count(_as_row(row).get("n"))
        if counted is None:
            raise ValueError("count_pending_disclosure_briefs n failed validation")
        return counted

    def pool_health_snapshot(self) -> dict[str, Any]:
        """Return real pool metrics observed by health checks.

        ``health_checkout_wait_ms`` is measured around the actual psycopg pool
        checkout used by ``health_check``. Other keys are copied from psycopg's
        own pool stats when available.
        """
        snapshot: dict[str, Any] = {
            "health_checkout_wait_ms": self._last_health_checkout_wait_ms,
        }
        get_stats = getattr(self._pool, "get_stats", None)
        if not callable(get_stats):
            return snapshot
        stats = get_stats()
        if not isinstance(stats, dict):
            return snapshot
        for key in ("pool_min", "pool_max", "pool_size", "pool_available", "requests_waiting"):
            value = stats.get(key)
            # Fail closed — bool soft-accepts via isinstance(True, int).
            if isinstance(value, bool) or not isinstance(value, int):
                continue
            snapshot[key] = value
        return snapshot



    async def persist_order_book(self, book: OrderBookSnapshot) -> OrderBookSnapshot:
        """Insert an order-book imbalance snapshot row."""
        if not isinstance(book.symbol, str) or not book.symbol.strip():
            raise ValueError("order book symbol required")
        symbol = book.symbol.strip().upper()
        await self.upsert_stock(symbol)
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    INSERT INTO order_book_snapshots
                        (symbol, total_bids, total_asks, best_bid, best_bid_qty, ts)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, symbol, total_bids, total_asks, best_bid, best_bid_qty, ts
                    """,
                    (
                        symbol,
                        book.total_bids,
                        book.total_asks,
                        book.best_bid,
                        book.best_bid_qty,
                        book.ts,
                    ),
                )
            ).fetchone()
        assert row is not None
        r = _as_row(row)
        return OrderBookSnapshot(
            id=r["id"],
            symbol=r["symbol"],
            total_bids=float(r["total_bids"]),
            total_asks=float(r["total_asks"]),
            best_bid=r.get("best_bid"),
            best_bid_qty=r.get("best_bid_qty"),
            ts=r["ts"],
        )

    async def order_book_fired_keys(self, symbol: str) -> set[str]:
        """Day-bucket event keys already claimed for book imbalance rules."""
        if not isinstance(symbol, str) or not symbol.strip():
            return set()
        symbol = symbol.strip().upper()
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT al.event_key
                    FROM alert_log al
                    JOIN alert_rules ar ON ar.id = al.rule_id
                    WHERE ar.symbol = %s
                      AND (
                        al.event_key LIKE 'bidheavy:%%'
                        OR al.event_key LIKE 'askheavy:%%'
                      )
                    """,
                    (symbol,),
                )
            ).fetchall()
        return {r["event_key"] for r in _as_rows(rows)}


def _row_to_snapshot(row: dict[str, Any]) -> PriceSnapshot | None:
    # Fail closed — non-string / blank symbol used to coerce via pydantic or
    # abort latest/previous snapshot reads mid poller.
    raw_sym = row.get("symbol")
    if not isinstance(raw_sym, str) or not raw_sym.strip():
        return None
    raw_price = row.get("price")
    # Fail closed — bool soft-accepts via float(True)==1.0.
    if isinstance(raw_price, bool):
        return None
    try:
        price = float(raw_price)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(price):
        return None
    ts = row.get("ts")
    if not isinstance(ts, datetime):
        # Fail closed — never str()-coerce non-string ts (objects used to
        # soft-accept via a hostile __str__ that looked like ISO).
        if not isinstance(ts, str):
            return None
        try:
            ts = datetime.fromisoformat(ts)
        except (TypeError, ValueError):
            return None
    # Fail closed — bool ids soft-accept via int(True)==1; lists/None throw
    # mid latest/previous snapshot reads (parity ``_row_to_rule``).
    raw_id = row.get("id")
    if isinstance(raw_id, bool) or not isinstance(raw_id, int):
        return None
    return PriceSnapshot(
        id=raw_id,
        symbol=raw_sym.strip().upper(),
        price=price,
        previous_close=row.get("previous_close"),
        change=row.get("change"),
        change_pct=row.get("change_pct"),
        volume=row.get("volume"),
        trade_count=row.get("trade_count"),
        turnover=row.get("turnover"),
        crossing_volume=row.get("crossing_volume"),
        high=row.get("high"),
        low=row.get("low"),
        open=row.get("open"),
        market_cap=row.get("market_cap"),
        ts=ts,
    )


def _row_to_rule(row: dict[str, Any]) -> AlertRule | None:
    created = row.get("created_at")
    if created is not None and not isinstance(created, datetime):
        # Fail closed — never str()-coerce non-string created_at.
        if not isinstance(created, str):
            created = None
        else:
            try:
                created = datetime.fromisoformat(created)
            except (TypeError, ValueError):
                created = None
    muted_until = row.get("muted_until")
    if muted_until is not None and not isinstance(muted_until, datetime):
        # Fail closed — never str()-coerce non-string muted_until values.
        if not isinstance(muted_until, str):
            muted_until = None
        else:
            try:
                muted_until = datetime.fromisoformat(muted_until)
            except (TypeError, ValueError):
                muted_until = None
    # Legacy / poisoned rows may still hold C0 controls or oversize categories —
    # sanitize on read so matching + Telegram egress share one egress bar.
    # Fail closed — never str()-coerce non-string PG values into category
    # (objects used to become "<...>" and bypass the isinstance guard).
    raw_cat = row.get("category")
    cat = sanitize_disclosure_category(
        raw_cat if isinstance(raw_cat, str) else None
    )
    # Fail closed — invalid / non-string type or symbol used to raise mid
    # list_alerts / active_rules_for_symbols and abort the tick.
    raw_type = row.get("type")
    if not isinstance(raw_type, str):
        return None
    try:
        alert_type = AlertType(raw_type)
    except ValueError:
        return None
    raw_sym = row.get("symbol")
    if not isinstance(raw_sym, str) or not raw_sym.strip():
        return None
    # Fail closed — bool ids soft-accept via int(True)==1; lists/None throw
    # mid list_alerts / active_rules_for_symbols and abort the tick.
    raw_id = row.get("id")
    raw_uid = row.get("user_id")
    raw_tg = row.get("telegram_id")
    if (
        isinstance(raw_id, bool)
        or not isinstance(raw_id, int)
        or isinstance(raw_uid, bool)
        or not isinstance(raw_uid, int)
        or isinstance(raw_tg, bool)
        or not isinstance(raw_tg, int)
    ):
        return None
    # Fail closed — bool() soft-accept of "false"/1 used to mislabel armed/active
    # (parity dash ``=== true``).
    raw_active = row.get("active")
    if not isinstance(raw_active, bool):
        return None
    raw_armed = row.get("armed", True)
    if not isinstance(raw_armed, bool):
        return None
    return AlertRule(
        id=raw_id,
        user_id=raw_uid,
        telegram_id=raw_tg,
        symbol=raw_sym.strip().upper(),
        type=alert_type,
        threshold=row.get("threshold"),
        category=cat,
        active=raw_active,
        armed=raw_armed,
        created_at=created,
        muted_until=muted_until,
    )
