"""Seed ``disclosures`` (+ pdf_url) from ``POST /financials`` PDF archives.

Enables ``drain-metrics`` / YoY compare without legacy announcements.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta

from koel.adapters.cse import CSEClient
from koel.config import Settings
from koel.domain import Disclosure
from koel.logging_setup import get_logger
from koel.storage import Storage

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class FinancialsBackfillResult:
    symbols_targeted: int
    symbols_ok: int
    symbols_failed: int
    disclosures_upserted: int


def _title_for(kind: str, filing_date: date) -> str:
    if kind == "annual":
        return f"Annual Report / Audited Financial Statements ({filing_date.isoformat()})"
    if kind == "quarterly":
        return (
            "Interim Financial Statements / Quarterly Results "
            f"({filing_date.isoformat()})"
        )
    return f"Financial filing ({filing_date.isoformat()})"


async def run_financials_backfill(
    *,
    settings: Settings,
    storage: Storage,
    cse: CSEClient,
    from_date: date | None = None,
    kinds: tuple[str, ...] = ("quarterly", "annual"),
    limit: int | None = None,
    sleep_seconds: float = 0.2,
    force: bool = False,
) -> FinancialsBackfillResult:
    if not force and not settings.path_backfill_enabled:
        log.info("financials_backfill_disabled")
        return FinancialsBackfillResult(0, 0, 0, 0)

    symbols = await storage.list_symbols_with_daily_bars()
    if (
        limit is not None
        and isinstance(limit, int)
        and not isinstance(limit, bool)
        and limit > 0
    ):
        symbols = symbols[:limit]

    cutoff = from_date or (date.today() - timedelta(days=800))
    kind_set = set(kinds)
    ok = failed = upserted = 0
    seen_at = datetime.now(UTC)

    for i, symbol in enumerate(symbols):
        try:
            docs = await cse.fetch_company_financial_docs(symbol)
            for kind, filing_date, pdf_url in docs:
                if kind not in kind_set:
                    continue
                if filing_date < cutoff:
                    continue
                if not pdf_url:
                    continue
                # Stable external id from CDN path basename when possible.
                ext = f"financials:{kind}:{filing_date.isoformat()}:{symbol}"
                disc = Disclosure(
                    external_id=ext[:200],
                    symbol=symbol,
                    company_name=None,
                    title=_title_for(kind, filing_date),
                    category=(
                        "FINANCIAL STATEMENTS - QUARTERLY"
                        if kind == "quarterly"
                        else "FINANCIAL STATEMENTS - ANNUAL"
                    ),
                    url=pdf_url,
                    published_at=datetime(
                        filing_date.year,
                        filing_date.month,
                        filing_date.day,
                        12,
                        0,
                        tzinfo=UTC,
                    ),
                    seen_at=seen_at,
                    pdf_url=pdf_url,
                )
                await storage.upsert_disclosure(disc)
                upserted += 1
            ok += 1
            log.info(
                "financials_backfill_symbol_ok",
                symbol=symbol,
                docs=len(docs),
            )
        except Exception as exc:
            failed += 1
            log.warning(
                "financials_backfill_symbol_failed",
                symbol=symbol,
                error=str(exc)[:200],
            )
        if sleep_seconds > 0 and i + 1 < len(symbols):
            await asyncio.sleep(sleep_seconds)

    result = FinancialsBackfillResult(
        symbols_targeted=len(symbols),
        symbols_ok=ok,
        symbols_failed=failed,
        disclosures_upserted=upserted,
    )
    log.info("financials_backfill_done", **asdict(result))
    return result
