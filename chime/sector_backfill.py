"""Flag-gated sector label backfill from ``POST /companyProfile``.

Writes ``stocks.sector`` from ``reqComSumInfo[].sector`` (e.g. Banks,
Capital Goods). Polite sleep between symbols. CLI: ``sector-backfill``.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass

from chime.adapters.cse import CSEClient
from chime.config import Settings
from chime.logging_setup import get_logger
from chime.storage import Storage

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SectorBackfillResult:
    symbols_targeted: int
    symbols_updated: int
    symbols_skipped: int
    symbols_failed: int


async def run_sector_backfill(
    *,
    settings: Settings,
    storage: Storage,
    cse: CSEClient,
    limit: int | None = None,
    sleep_seconds: float | None = None,
    only_missing: bool = True,
    force: bool = False,
) -> SectorBackfillResult:
    """Backfill ``stocks.sector`` via companyProfile.

    When ``force`` is False and ``SECTOR_BACKFILL_ENABLED`` is off, no-op.
    """
    if not force and not settings.sector_backfill_enabled:
        log.info("sector_backfill_disabled")
        return SectorBackfillResult(0, 0, 0, 0)

    pause = (
        sleep_seconds
        if sleep_seconds is not None
        else settings.sector_backfill_sleep_seconds
    )
    if not isinstance(pause, int | float) or isinstance(pause, bool) or pause < 0:
        pause = 0.35

    if only_missing:
        targets = await storage.list_symbols_missing_sector()
    else:
        targets = await storage.list_symbols_with_daily_bars()

    if (
        limit is not None
        and isinstance(limit, int)
        and not isinstance(limit, bool)
        and limit > 0
    ):
        targets = targets[:limit]

    updated = 0
    skipped = 0
    failed = 0
    for idx, symbol in enumerate(targets):
        try:
            sector = await cse.fetch_company_sector(symbol)
            if not sector:
                skipped += 1
            else:
                await storage.upsert_stock(symbol, sector=sector)
                updated += 1
                log.info("sector_backfill_ok", symbol=symbol, sector=sector)
        except Exception as exc:
            failed += 1
            log.warning("sector_backfill_failed", symbol=symbol, error=str(exc))
        if pause > 0 and idx + 1 < len(targets):
            await asyncio.sleep(float(pause))

    result = SectorBackfillResult(
        symbols_targeted=len(targets),
        symbols_updated=updated,
        symbols_skipped=skipped,
        symbols_failed=failed,
    )
    log.info("sector_backfill_done", **asdict(result))
    return result
