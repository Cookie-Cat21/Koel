"""Ops backfill for ``market_notices`` (buy-in / non-compliance / halt).

Poller only fetches notices when alert rules exist; this CLI seeds Postgres
so Signal Board F-051/F-052 can fire. Resolves company→symbol when missing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from koel.adapters.cse import CSEClient
from koel.config import Settings
from koel.logging_setup import get_logger
from koel.storage import Storage

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class NoticesBackfillResult:
    fetched: int
    persisted: int
    resolved_symbols: int
    failed: int


async def run_notices_backfill(
    *,
    settings: Settings,
    storage: Storage,
    cse: CSEClient,
    force: bool = False,
) -> NoticesBackfillResult:
    """Fetch CSE notice boards and upsert into ``market_notices``.

    When ``force`` is False and ``NOTICES_BACKFILL_ENABLED`` is off, no-op.
    """
    if not force and not settings.notices_backfill_enabled:
        log.info("notices_backfill_disabled")
        return NoticesBackfillResult(0, 0, 0, 0)

    fetchers = (
        ("buy_in", cse.fetch_buy_in_announcements),
        ("non_compliance", cse.fetch_non_compliance_announcements),
        ("halt", cse.fetch_market_notifications),
    )
    fetched = 0
    persisted = 0
    resolved = 0
    failed = 0

    for kind, fetcher in fetchers:
        try:
            batch = await fetcher()
        except Exception as exc:
            failed += 1
            log.warning("notices_backfill_fetch_failed", kind=kind, error=str(exc))
            continue
        if not isinstance(batch, list):
            failed += 1
            continue
        fetched += len(batch)
        for notice in batch:
            try:
                if notice.symbol is None and notice.notice_type != "halt":
                    company = None
                    if isinstance(notice.body, str) and notice.body.strip():
                        company = notice.body.split(" — ", 1)[0].strip()
                    mapped = await storage.resolve_symbol_by_company_name(company)
                    if mapped is None and isinstance(notice.title, str):
                        mapped = await storage.resolve_symbol_by_company_name(
                            notice.title
                        )
                    if mapped is not None:
                        notice = notice.model_copy(update={"symbol": mapped})
                        resolved += 1
                await storage.upsert_market_notice(notice)
                persisted += 1
            except Exception as exc:
                failed += 1
                log.warning(
                    "notices_backfill_persist_failed",
                    kind=kind,
                    error=str(exc),
                )

    result = NoticesBackfillResult(
        fetched=fetched,
        persisted=persisted,
        resolved_symbols=resolved,
        failed=failed,
    )
    log.info("notices_backfill_done", **asdict(result))
    return result
