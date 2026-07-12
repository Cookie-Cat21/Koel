"""Postgres persistence layer (snapshots, disclosures, users, rules, alert log)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import datetime
from time import perf_counter
from typing import Any, cast

from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from chime.domain import (
    AlertEvent,
    AlertRule,
    AlertType,
    Disclosure,
    PreviousPriceState,
    PriceSnapshot,
    SectorSnapshot,
)


def _as_row(row: Any) -> dict[str, Any]:
    return cast(dict[str, Any], row)


def _as_rows(rows: Any) -> list[dict[str, Any]]:
    return [cast(dict[str, Any], r) for r in rows]


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
        self, symbol: str, name: str | None = None, sector: str | None = None
    ) -> None:
        symbol = symbol.strip().upper()
        async with self._pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO stocks (symbol, name, sector)
                VALUES (%s, %s, %s)
                ON CONFLICT (symbol) DO UPDATE SET
                    name = COALESCE(EXCLUDED.name, stocks.name),
                    sector = COALESCE(EXCLUDED.sector, stocks.sector),
                    updated_at = now()
                """,
                (symbol, name, sector),
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
            symbol = str(row["symbol"]).strip().upper()
            name = str(row["name"]).strip()
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

        # Last-wins per normalized symbol; skip blanks (invalid CSE rows).
        by_symbol: dict[str, PriceSnapshot] = {}
        for snap in snaps:
            symbol = snap.symbol.strip().upper()
            if not symbol:
                continue
            by_symbol[symbol] = snap
        if not by_symbol:
            return []

        normalized: list[tuple[str, PriceSnapshot]] = list(by_symbol.items())
        # Column-wise arrays + UNNEST: static SQL only (no f-string / concat VALUES).
        stock_symbols = [symbol for symbol, _ in normalized]
        stock_names = [snap.name for _, snap in normalized]
        stock_sectors = [None] * len(normalized)
        snap_symbols = list(stock_symbols)
        snap_prices = [snap.price for _, snap in normalized]
        snap_changes = [snap.change for _, snap in normalized]
        snap_change_pcts = [snap.change_pct for _, snap in normalized]
        snap_prev_closes = [snap.previous_close for _, snap in normalized]
        snap_volumes = [snap.volume for _, snap in normalized]
        snap_trade_counts = [snap.trade_count for _, snap in normalized]
        snap_turnovers = [snap.turnover for _, snap in normalized]
        snap_highs = [snap.high for _, snap in normalized]
        snap_lows = [snap.low for _, snap in normalized]
        snap_opens = [snap.open for _, snap in normalized]
        snap_market_caps = [snap.market_cap for _, snap in normalized]
        snap_ts = [snap.ts for _, snap in normalized]

        async with self._pool.connection() as conn, conn.transaction():
            await conn.execute(
                """
                INSERT INTO stocks (symbol, name, sector)
                SELECT symbol, name, sector
                FROM UNNEST(%s::text[], %s::text[], %s::text[])
                    AS t(symbol, name, sector)
                ON CONFLICT (symbol) DO UPDATE SET
                    name = COALESCE(EXCLUDED.name, stocks.name),
                    sector = COALESCE(EXCLUDED.sector, stocks.sector),
                    updated_at = now()
                """,
                (stock_symbols, stock_names, stock_sectors),
            )
            rows = await (
                await conn.execute(
                    """
                    INSERT INTO price_snapshots (
                        symbol, price, change, change_pct, previous_close,
                        volume, trade_count, turnover, high, low, open,
                        market_cap, ts
                    )
                    SELECT
                        symbol, price, change, change_pct, previous_close,
                        volume, trade_count, turnover, high, low, open,
                        market_cap, ts
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
                        %s::timestamptz[]
                    ) AS t(
                        symbol, price, change, change_pct, previous_close,
                        volume, trade_count, turnover, high, low, open,
                        market_cap, ts
                    )
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
            out.append(snap.model_copy(update={"id": int(row["id"]), "symbol": symbol}))
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
        return int(_as_row(row).get("n") or 0)

    async def persist_sectors(self, sectors: list[SectorSnapshot]) -> list[SectorSnapshot]:
        """Upsert CSE sector index rows (optional ``SECTORS_INGEST`` path).

        Last-wins per ``sector_id``. Blank symbols skipped. Empty input is a no-op.
        """
        if not sectors:
            return []

        by_id: dict[int, SectorSnapshot] = {}
        for sector in sectors:
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

    async def latest_snapshot(self, symbol: str) -> PriceSnapshot | None:
        symbol = symbol.strip().upper()
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
        symbol = symbol.strip().upper()
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    SELECT * FROM price_snapshots
                    WHERE symbol = %s AND id < %s
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
        prev = await self.previous_snapshot(symbol, before_id=before_id)
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT al.event_key
                    FROM alert_log al
                    JOIN alert_rules ar ON ar.id = al.rule_id
                    WHERE ar.symbol = %s AND al.event_key LIKE 'move:%%'
                    """,
                    (symbol.strip().upper(),),
                )
            ).fetchall()
            move_keys = {r["event_key"] for r in _as_rows(rows)}
        if prev is None:
            return PreviousPriceState(price=None, change_pct=None, move_fired_keys=move_keys)
        return PreviousPriceState(
            price=prev.price,
            change_pct=prev.change_pct,
            move_fired_keys=move_keys,
        )

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
        """
        if limit <= 0:
            return []
        grace = max(0, int(pdf_grace_seconds))
        # Distinct from POLL_LOCK_ID; serializes brief claim + daily-cap check.
        brief_cap_lock_id = 4_201_339
        async with self._pool.connection() as conn, conn.transaction():
            if max_briefs_per_day is not None:
                await conn.execute(
                    "SELECT pg_advisory_xact_lock(%s)",
                    (brief_cap_lock_id,),
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
                used = int(_as_row(used_row).get("n") or 0) if used_row else 0
                remaining = max(0, int(max_briefs_per_day) - used)
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
                    (stale_processing_minutes, grace, batch),
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
        ext = (external_id or "").strip()
        sym = (symbol or "").strip().upper()
        brief_text = (brief or "").strip()
        msg = message_text or ""
        if not ext or not sym or not brief_text or not msg.strip():
            return []
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
                    (ext, sym, brief_text, ext, msg, lease_seconds),
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
        """Mark a claimed (processing) brief row ready with generated text."""
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
                      AND status IN ('pending', 'processing')
                    RETURNING disclosure_id
                    """,
                    (brief, model, tokens_in, tokens_out, disclosure_id),
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
        return int(_as_row(row).get("n") or 0)

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
        from chime.briefs import BriefStatus, briefs_enabled

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
                    RETURNING id, pdf_url, (xmax = 0) AS inserted
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
            disclosure_id = int(data["id"])
            existing_pdf = data.get("pdf_url")
            if data.get("inserted"):
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
                "pdf_url": existing_pdf if existing_pdf else disc.pdf_url,
                "just_inserted": bool(data.get("inserted")),
            }
        )

    async def set_disclosure_pdf_url(self, disclosure_id: int, pdf_url: str) -> bool:
        """Fill ``disclosures.pdf_url`` when known; never overwrite an existing URL.

        Only ``https://cdn.cse.lk/...`` URLs are persisted (SSRF guard). Returns
        True if a row was updated. Fail-soft callers treat False / errors as
        non-blocking for alerts.
        """
        from chime.adapters.cse import resolve_pdf_url

        normalized = resolve_pdf_url(pdf_url)
        if not normalized:
            return False
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    UPDATE disclosures
                    SET pdf_url = %s
                    WHERE id = %s AND pdf_url IS NULL
                    RETURNING id
                    """,
                    (normalized, disclosure_id),
                )
            ).fetchone()
        return row is not None

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
                ext = (external_id or "").strip()
                sym = (symbol or "").strip().upper()
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
        return int(_as_row(row)["id"])

    async def add_watch(self, user_id: int, symbol: str) -> None:
        symbol = symbol.strip().upper()
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
        symbol = symbol.strip().upper()
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
        symbol = symbol.strip().upper()
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
                    ORDER BY symbol
                    """,
                    (user_id,),
                )
            ).fetchall()
        return [r["symbol"] for r in _as_rows(rows)]

    async def watched_symbols(self) -> list[str]:
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute("SELECT DISTINCT symbol FROM watchlist_items ORDER BY symbol")
            ).fetchall()
        return [r["symbol"] for r in _as_rows(rows)]

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
        symbol = symbol.strip().upper()
        cat = category.strip() if category and category.strip() else None
        if alert_type != AlertType.DISCLOSURE:
            cat = None
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
        created = r.get("created_at")
        if created is not None and not isinstance(created, datetime):
            created = datetime.fromisoformat(str(created))
        return AlertRule(
            id=int(r["id"]),
            user_id=int(r["user_id"]),
            telegram_id=int(u["telegram_id"]),
            symbol=r["symbol"],
            type=AlertType(r["type"]),
            threshold=r["threshold"],
            category=r.get("category"),
            active=bool(r["active"]),
            armed=bool(r["armed"]),
            created_at=created,
        )

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
        return [_row_to_rule(_as_row(r)) for r in rows]

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
        return [_row_to_rule(_as_row(r)) for r in rows]

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
        symbol = symbol.strip().upper()
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
            locked = bool(row and _as_row(row)["locked"])
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
        """
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
                        lease_seconds,
                    ),
                )
            ).fetchone()
        if row is None:
            return None
        return int(_as_row(row)["id"])

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
        """
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
                        lease_seconds,
                    ),
                )
            ).fetchone()
            if row is None:
                return None
            await conn.execute(
                "UPDATE alert_rules SET armed = %s WHERE id = %s",
                (False, event.rule_id),
            )
            return int(_as_row(row)["id"])

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
        return int(_as_row(row)["attempt_count"])

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
        """
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
                    (limit, lease_seconds),
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
            return bool(row and _as_row(row)["ok"] == 1)
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
        return int(_as_row(row)["n"])

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
            if isinstance(value, int):
                snapshot[key] = value
        return snapshot


def _row_to_snapshot(row: dict[str, Any]) -> PriceSnapshot:
    return PriceSnapshot(
        id=int(row["id"]),
        symbol=row["symbol"],
        price=float(row["price"]),
        previous_close=row.get("previous_close"),
        change=row.get("change"),
        change_pct=row.get("change_pct"),
        volume=row.get("volume"),
        trade_count=row.get("trade_count"),
        turnover=row.get("turnover"),
        high=row.get("high"),
        low=row.get("low"),
        open=row.get("open"),
        market_cap=row.get("market_cap"),
        ts=row["ts"] if isinstance(row["ts"], datetime) else datetime.fromisoformat(str(row["ts"])),
    )


def _row_to_rule(row: dict[str, Any]) -> AlertRule:
    created = row.get("created_at")
    if created is not None and not isinstance(created, datetime):
        created = datetime.fromisoformat(str(created))
    cat = row.get("category")
    if cat is not None:
        cat = str(cat).strip() or None
    return AlertRule(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        telegram_id=int(row["telegram_id"]),
        symbol=row["symbol"],
        type=AlertType(row["type"]),
        threshold=row.get("threshold"),
        category=cat,
        active=bool(row["active"]),
        armed=bool(row.get("armed", True)),
        created_at=created,
    )
