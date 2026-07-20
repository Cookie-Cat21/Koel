"""Flag-gated CSE intraday chart backfill → ``price_snapshots``.

Uses ``POST /companyChartDataByStock`` with ``period=1`` (session prints).
Fills sparse poller history so the dash 1D candlestick range can render.

Disabled unless ``PATH_BACKFILL_ENABLED=1`` (or CLI ``--force``) — same gate
as daily path backfill; both are polite CSE chart drains.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass

from koel.adapters.cse import CSEClient
from koel.config import Settings
from koel.logging_setup import get_logger
from koel.path_backfill import seed_cse_stock_ids_from_trade_summary
from koel.storage import Storage

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class IntradayBackfillResult:
    symbols_targeted: int
    symbols_ok: int
    symbols_skipped: int
    symbols_failed: int
    ticks_inserted: int


async def run_intraday_backfill(
    *,
    settings: Settings,
    storage: Storage,
    cse: CSEClient,
    limit: int | None = None,
    sleep_seconds: float | None = None,
    seed_ids: bool = True,
    force: bool = False,
) -> IntradayBackfillResult:
    """Backfill today's CSE intraday ticks for stocks with ``cse_stock_id``."""
    if not force and not settings.path_backfill_enabled:
        log.info("intraday_backfill_disabled")
        return IntradayBackfillResult(0, 0, 0, 0, 0)

    pause = (
        sleep_seconds
        if sleep_seconds is not None
        else settings.path_backfill_sleep_seconds
    )
    if not isinstance(pause, int | float) or isinstance(pause, bool) or pause < 0:
        pause = 0.35

    if seed_ids:
        await seed_cse_stock_ids_from_trade_summary(storage=storage, cse=cse)

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
    ticks_total = 0

    for idx, (symbol, stock_id) in enumerate(targets):
        try:
            snaps = await cse.fetch_company_intraday(stock_id, symbol=symbol)
            if not snaps:
                skipped += 1
                log.warning(
                    "intraday_backfill_empty",
                    symbol=symbol,
                    stock_id=stock_id,
                )
            else:
                n = await storage.persist_intraday_snapshots(snaps)
                ticks_total += n
                ok += 1
                log.info(
                    "intraday_backfill_symbol_ok",
                    symbol=symbol,
                    stock_id=stock_id,
                    fetched=len(snaps),
                    inserted=n,
                )
        except Exception as exc:
            failed += 1
            log.warning(
                "intraday_backfill_symbol_failed",
                symbol=symbol,
                stock_id=stock_id,
                error=str(exc),
            )
        if pause > 0 and idx + 1 < len(targets):
            await asyncio.sleep(float(pause))

    result = IntradayBackfillResult(
        symbols_targeted=len(targets),
        symbols_ok=ok,
        symbols_skipped=skipped,
        symbols_failed=failed,
        ticks_inserted=ticks_total,
    )
    log.info("intraday_backfill_done", **asdict(result))
    return result
