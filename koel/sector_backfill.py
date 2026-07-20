"""Flag-gated sector label backfill from ``POST /companyProfile``.

Writes ``stocks.sector`` from ``reqComSumInfo[].sector`` (e.g. Banks,
Capital Goods). Polite sleep between symbols. CLI: ``sector-backfill``.

Market indexes (ASPI, SNP_SL20) are not listed companies — ``companyProfile``
returns HTTP 204 / empty. Those are skipped with an exact reason, tagged
``Market Index``, and recorded on ``ops_job_status`` for Health.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass

from koel.adapters.cse import CSEClient
from koel.config import Settings
from koel.logging_setup import get_logger
from koel.storage import Storage

log = get_logger(__name__)

# Index symbols upserted by aspi-backfill into ``stocks`` + ``daily_bars``.
# They have no ``companyProfile`` (CSE returns 204 empty).
MARKET_INDEX_SYMBOLS: frozenset[str] = frozenset({"ASPI", "SNP_SL20"})
MARKET_INDEX_SECTOR = "Market Index"
OPS_JOB_ID = "sector-backfill"
_MAX_ISSUES = 12
_DETAIL_MAX = 480


@dataclass(frozen=True, slots=True)
class SectorBackfillResult:
    symbols_targeted: int
    symbols_updated: int
    symbols_skipped: int
    symbols_failed: int
    issues: tuple[str, ...] = ()


def _index_issue(symbol: str) -> str:
    return (
        f"{symbol}: market index (not a listed company) — "
        "companyProfile returns empty/HTTP 204; sector not applicable"
    )


def _classify_failure(symbol: str, exc: BaseException) -> str:
    msg = str(exc).strip() or type(exc).__name__
    low = msg.lower()
    if (
        "expecting value" in low
        or "json" in low
        or "empty" in low
        or "204" in low
    ):
        if symbol.upper() in MARKET_INDEX_SYMBOLS:
            return _index_issue(symbol)
        return (
            f"{symbol}: companyProfile returned empty/non-JSON "
            f"(not a company profile; {msg[:120]})"
        )
    return f"{symbol}: {msg[:200]}"


def _trim_detail(issues: list[str]) -> str | None:
    if not issues:
        return None
    text = "; ".join(issues[:_MAX_ISSUES])
    if len(issues) > _MAX_ISSUES:
        text = f"{text}; …+{len(issues) - _MAX_ISSUES} more"
    if len(text) > _DETAIL_MAX:
        text = text[: _DETAIL_MAX - 1].rstrip() + "…"
    return text


async def _tag_market_indexes(storage: Storage) -> tuple[list[str], list[str]]:
    """Tag untagged ASPI/SNP_SL20 rows; return (index_symbols, issues)."""
    index_skipped: list[str] = []
    issues: list[str] = []
    try:
        pending = await storage.list_untagged_market_indexes()
    except Exception as exc:
        log.warning("sector_backfill_index_list_failed", error=str(exc))
        return index_skipped, issues

    for sym in pending:
        issue = _index_issue(sym)
        issues.append(issue)
        index_skipped.append(sym)
        log.info(
            "sector_backfill_skip_index",
            symbol=sym,
            reason="market_index_no_company_profile",
        )
        try:
            await storage.upsert_stock(sym, sector=MARKET_INDEX_SECTOR)
        except Exception as exc:
            log.warning(
                "sector_backfill_index_tag_failed",
                symbol=sym,
                error=str(exc),
            )
    return index_skipped, issues


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
        return SectorBackfillResult(0, 0, 0, 0, ())

    pause = (
        sleep_seconds
        if sleep_seconds is not None
        else settings.sector_backfill_sleep_seconds
    )
    if not isinstance(pause, int | float) or isinstance(pause, bool) or pause < 0:
        pause = 0.35

    index_skipped, issues = await _tag_market_indexes(storage)

    if only_missing:
        targets = await storage.list_symbols_missing_sector()
    else:
        targets = [
            s
            for s in await storage.list_symbols_with_daily_bars()
            if isinstance(s, str) and s.strip().upper() not in MARKET_INDEX_SYMBOLS
        ]

    if (
        limit is not None
        and isinstance(limit, int)
        and not isinstance(limit, bool)
        and limit > 0
    ):
        targets = targets[:limit]

    updated = 0
    skipped = len(index_skipped)
    failed = 0

    for idx, symbol in enumerate(targets):
        sym = symbol.strip().upper() if isinstance(symbol, str) else ""
        if not sym or sym in MARKET_INDEX_SYMBOLS:
            if sym in MARKET_INDEX_SYMBOLS and sym not in index_skipped:
                issue = _index_issue(sym)
                issues.append(issue)
                index_skipped.append(sym)
                skipped += 1
                try:
                    await storage.upsert_stock(sym, sector=MARKET_INDEX_SECTOR)
                except Exception as exc:
                    log.warning(
                        "sector_backfill_index_tag_failed",
                        symbol=sym,
                        error=str(exc),
                    )
            elif not sym:
                skipped += 1
            if pause > 0 and idx + 1 < len(targets):
                await asyncio.sleep(float(pause))
            continue

        try:
            sector = await cse.fetch_company_sector(sym)
            if not sector:
                skipped += 1
                log.info("sector_backfill_skip_empty", symbol=sym)
            else:
                await storage.upsert_stock(sym, sector=sector)
                updated += 1
                log.info("sector_backfill_ok", symbol=sym, sector=sector)
        except Exception as exc:
            failed += 1
            issue = _classify_failure(sym, exc)
            issues.append(issue)
            log.warning("sector_backfill_failed", symbol=sym, error=issue)

        if pause > 0 and idx + 1 < len(targets):
            await asyncio.sleep(float(pause))

    targeted = len(targets) + len(index_skipped)

    if failed > 0:
        status = "failed"
        summary = (
            f"failed={failed} updated={updated} skipped={skipped} "
            f"targeted={targeted}"
        )
    elif index_skipped:
        status = "notice"
        summary = (
            f"ok with index skips: {', '.join(index_skipped)} "
            f"(updated={updated} skipped={skipped} targeted={targeted})"
        )
    else:
        status = "ok"
        summary = (
            f"updated={updated} skipped={skipped} failed={failed} "
            f"targeted={targeted}"
        )

    detail = _trim_detail(issues)
    try:
        await storage.upsert_ops_job_status(
            job_id=OPS_JOB_ID,
            status=status,
            summary=summary,
            detail=detail,
        )
    except Exception as exc:
        log.warning("sector_backfill_ops_status_failed", error=str(exc))

    result = SectorBackfillResult(
        symbols_targeted=targeted,
        symbols_updated=updated,
        symbols_skipped=skipped,
        symbols_failed=failed,
        issues=tuple(issues[:_MAX_ISSUES]),
    )
    log.info(
        "sector_backfill_done",
        **{k: v for k, v in asdict(result).items() if k != "issues"},
        status=status,
        issue_count=len(issues),
    )
    return result
