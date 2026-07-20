"""Backfill per-symbol CSE announcements into ``disclosures``.

Uses ``POST /getAnnouncementByCompany`` with both ``fromDate`` and ``toDate``
(CSE requires both). Flag-gated; CLI may ``--force``.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import date, timedelta

from koel.adapters.cse import CSEClient
from koel.config import Settings
from koel.logging_setup import get_logger
from koel.storage import Storage

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class DisclosuresBackfillResult:
    symbols_targeted: int
    symbols_ok: int
    symbols_failed: int
    disclosures_upserted: int


async def run_disclosures_backfill(
    *,
    settings: Settings,
    storage: Storage,
    cse: CSEClient,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int | None = None,
    sleep_seconds: float = 0.35,
    force: bool = False,
) -> DisclosuresBackfillResult:
    """Fetch announcement history for symbols that have ``daily_bars``."""
    # Reuse path_backfill flag family or always allow with force.
    # Dedicated env optional later; for now force or PATH_BACKFILL_ENABLED.
    if not force and not settings.path_backfill_enabled:
        log.info("disclosures_backfill_disabled")
        return DisclosuresBackfillResult(0, 0, 0, 0)

    symbols = await storage.list_symbols_with_daily_bars()
    if (
        limit is not None
        and isinstance(limit, int)
        and not isinstance(limit, bool)
        and limit > 0
    ):
        symbols = symbols[:limit]

    end = to_date or date.today()
    start = from_date or (end - timedelta(days=400))
    fd = start.isoformat()
    td = end.isoformat()

    ok = 0
    failed = 0
    upserted = 0
    for i, symbol in enumerate(symbols):
        try:
            rows = await cse.fetch_announcements_for_symbol(
                symbol, from_date=fd, to_date=td
            )
            for disc in rows:
                await storage.upsert_disclosure(disc)
                upserted += 1
            ok += 1
            log.info(
                "disclosures_backfill_symbol_ok",
                symbol=symbol,
                n=len(rows),
                from_date=fd,
                to_date=td,
            )
        except Exception as exc:
            failed += 1
            log.warning(
                "disclosures_backfill_symbol_failed",
                symbol=symbol,
                error=str(exc),
            )
        if sleep_seconds > 0 and i + 1 < len(symbols):
            await asyncio.sleep(sleep_seconds)

    result = DisclosuresBackfillResult(
        symbols_targeted=len(symbols),
        symbols_ok=ok,
        symbols_failed=failed,
        disclosures_upserted=upserted,
    )
    log.info("disclosures_backfill_done", **asdict(result))
    return result
