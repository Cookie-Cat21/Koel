"""Flag-gated CSE daily path backfill → ``daily_bars``.

Uses ``POST /companyChartDataByStock`` (default ``period=5`` ≈ 1 year).
See ``docs/experiments/CSE_PATH_HISTORY_PROBE.md``.

Disabled unless ``PATH_BACKFILL_ENABLED=1`` (or CLI ``--force``).
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass

from chime.adapters.cse import (
    CHART_DAILY_PERIODS,
    CHART_PERIOD_1Y,
    CSEClient,
)
from chime.config import Settings
from chime.logging_setup import get_logger
from chime.storage import Storage

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PathBackfillResult:
    symbols_targeted: int
    symbols_ok: int
    symbols_skipped: int
    symbols_failed: int
    bars_upserted: int


async def seed_cse_stock_ids_from_trade_summary(
    *,
    storage: Storage,
    cse: CSEClient,
) -> int:
    """Persist board symbols + ``cse_stock_id`` from one ``tradeSummary`` call."""
    snaps = await cse.fetch_trade_summary()
    if not snaps:
        return 0
    stored = await storage.persist_market_snapshots(snaps)
    with_ids = sum(1 for s in snaps if s.cse_stock_id is not None)
    log.info(
        "path_backfill_seeded_ids",
        board_rows=len(snaps),
        persisted=len(stored),
        with_cse_stock_id=with_ids,
    )
    return with_ids


async def seed_cse_stock_ids_from_company_info(
    *,
    storage: Storage,
    cse: CSEClient,
    limit: int = 40,
    sleep_seconds: float = 0.35,
) -> int:
    """Fill ``cse_stock_id`` via ``companyInfoSummery`` for thin names.

    ``tradeSummary`` omits some listed issuers (e.g. TAP) even though
    ``companyInfoSummery`` still returns a chart ``id``. Without this seed,
    path backfill never reaches them and the dash falls back to fat tick
    blocks instead of daily candles.
    """
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or limit <= 0
    ):
        return 0
    pause = (
        sleep_seconds
        if isinstance(sleep_seconds, int | float)
        and not isinstance(sleep_seconds, bool)
        and sleep_seconds >= 0
        else 0.35
    )
    symbols = await storage.list_symbols_missing_cse_stock_id(limit=limit)
    seeded = 0
    for idx, symbol in enumerate(symbols):
        try:
            snap = await cse.fetch_company_info(symbol)
        except Exception as exc:
            log.warning(
                "path_backfill_company_info_failed",
                symbol=symbol,
                error=str(exc),
            )
            snap = None
        if snap is not None and snap.cse_stock_id is not None:
            await storage.upsert_stock(
                symbol,
                snap.name,
                cse_stock_id=snap.cse_stock_id,
            )
            seeded += 1
            log.info(
                "path_backfill_company_info_seeded",
                symbol=symbol,
                stock_id=snap.cse_stock_id,
            )
        if pause > 0 and idx + 1 < len(symbols):
            await asyncio.sleep(float(pause))
    return seeded


async def run_path_backfill(
    *,
    settings: Settings,
    storage: Storage,
    cse: CSEClient,
    period: int | None = None,
    limit: int | None = None,
    sleep_seconds: float | None = None,
    seed_ids: bool = True,
    force: bool = False,
) -> PathBackfillResult:
    """Backfill ``daily_bars`` for stocks that have ``cse_stock_id``.

    When ``force`` is False and ``PATH_BACKFILL_ENABLED`` is off, returns zeros
    without calling CSE (except the CLI may pass ``force=True`` for ops).
    """
    if not force and not settings.path_backfill_enabled:
        log.info("path_backfill_disabled")
        return PathBackfillResult(0, 0, 0, 0, 0)

    chart_period = period if period is not None else settings.path_backfill_period
    if (
        isinstance(chart_period, bool)
        or not isinstance(chart_period, int)
        or chart_period not in CHART_DAILY_PERIODS
    ):
        chart_period = CHART_PERIOD_1Y

    pause = (
        sleep_seconds
        if sleep_seconds is not None
        else settings.path_backfill_sleep_seconds
    )
    if not isinstance(pause, int | float) or isinstance(pause, bool) or pause < 0:
        pause = 0.35

    if seed_ids:
        await seed_cse_stock_ids_from_trade_summary(storage=storage, cse=cse)
        # Cap companyInfo probes so a limited ops pass still finishes quickly.
        info_limit = 40
        if (
            limit is not None
            and isinstance(limit, int)
            and not isinstance(limit, bool)
            and limit > 0
        ):
            info_limit = min(40, limit)
        await seed_cse_stock_ids_from_company_info(
            storage=storage,
            cse=cse,
            limit=info_limit,
            sleep_seconds=float(pause),
        )

    targets = await storage.list_stocks_with_cse_ids()
    if (
        limit is not None
        and isinstance(limit, int)
        and not isinstance(limit, bool)
        and limit > 0
    ):
        targets = targets[:limit]

    ok = 0
    skipped = 0
    failed = 0
    bars_total = 0

    for idx, (symbol, stock_id) in enumerate(targets):
        try:
            bars = await cse.fetch_company_chart(
                stock_id, symbol=symbol, period=chart_period
            )
            if not bars:
                skipped += 1
                log.warning(
                    "path_backfill_empty",
                    symbol=symbol,
                    stock_id=stock_id,
                    period=chart_period,
                )
            else:
                n = await storage.persist_daily_bars(bars)
                bars_total += n
                ok += 1
                log.info(
                    "path_backfill_symbol_ok",
                    symbol=symbol,
                    stock_id=stock_id,
                    bars=n,
                    period=chart_period,
                )
        except Exception as exc:
            failed += 1
            log.warning(
                "path_backfill_symbol_failed",
                symbol=symbol,
                stock_id=stock_id,
                error=str(exc),
            )
        if pause > 0 and idx + 1 < len(targets):
            await asyncio.sleep(float(pause))

    result = PathBackfillResult(
        symbols_targeted=len(targets),
        symbols_ok=ok,
        symbols_skipped=skipped,
        symbols_failed=failed,
        bars_upserted=bars_total,
    )
    log.info("path_backfill_done", **asdict(result))
    return result
