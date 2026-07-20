"""Scheduled PDF enrich / brief / metrics drains (Track C).

These run outside the market-hours poller loop so backlog can clear via
``python -m koel drain-pdfs|drain-briefs|drain-metrics`` or GitHub Actions.
Uses existing CSE JSON + CDN adapters only — never scrapes competitor sites.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import structlog

from koel.adapters.cse import CSEClient, legacy_pdf_urls_by_id
from koel.briefs import BriefSettings, briefs_enabled
from koel.briefs.worker import claim_pending_briefs
from koel.config import Settings
from koel.extractors.financial_pdf import is_financial_filing
from koel.graph import GraphSettings, graph_enabled
from koel.graph.people_worker import people_enabled, process_disclosure_people
from koel.graph.worker import process_disclosure_graph
from koel.metrics import MetricsSettings, metrics_enabled
from koel.metrics.worker import process_disclosure_metrics
from koel.storage import Storage

log = structlog.get_logger("koel.drain")


@dataclass(frozen=True, slots=True)
class DrainResult:
    command: str
    examined: int
    updated: int
    skipped: int
    errors: int


async def drain_pdfs(
    *,
    storage: Storage,
    cse: CSEClient,
    settings: Settings,
    limit: int = 20,
    watched_only: bool = True,
) -> DrainResult:
    """Enrich missing ``pdf_url`` via legacy ``POST /announcements`` (polite sleep)."""
    items = await storage.list_disclosures_missing_pdf(
        limit=limit, watched_only=watched_only
    )
    if not items:
        return DrainResult("drain-pdfs", 0, 0, 0, 0)

    by_symbol: dict[str, list[Any]] = {}
    for disc in items:
        by_symbol.setdefault(disc.symbol, []).append(disc)

    sleep_s = max(0.0, float(settings.pdf_enrich_sleep_seconds))
    updated = 0
    errors = 0
    skipped = 0
    for symbol, rows in sorted(by_symbol.items()):
        if sleep_s > 0:
            await asyncio.sleep(sleep_s)
        try:
            legacy = await cse.fetch_legacy_announcements(symbol)
        except Exception as exc:  # noqa: BLE001
            log.warning("drain_pdf_legacy_failed", symbol=symbol, error=str(exc)[:200])
            errors += len(rows)
            continue
        pdf_map = legacy_pdf_urls_by_id(legacy)
        if not pdf_map:
            skipped += len(rows)
            continue
        for disc in rows:
            if disc.id is None:
                skipped += 1
                continue
            pdf_url = pdf_map.get(disc.external_id)
            if not pdf_url:
                skipped += 1
                continue
            try:
                ok = await storage.set_disclosure_pdf_url(disc.id, pdf_url)
                if ok:
                    updated += 1
                else:
                    skipped += 1
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "drain_pdf_set_failed",
                    disclosure_id=disc.id,
                    error=str(exc)[:200],
                )
                errors += 1
    return DrainResult("drain-pdfs", len(items), updated, skipped, errors)


async def drain_briefs(
    *,
    storage: Storage,
    settings: BriefSettings | None = None,
    limit: int = 10,
) -> DrainResult:
    """Drain pending disclosure briefs (no-op when AI briefs disabled)."""
    cfg = settings or BriefSettings.from_env()
    if not briefs_enabled(cfg):
        return DrainResult("drain-briefs", 0, 0, 0, 0)
    processed = await claim_pending_briefs(storage, settings=cfg, limit=limit)
    return DrainResult("drain-briefs", processed, processed, 0, 0)


async def drain_metrics(
    *,
    storage: Storage,
    settings: MetricsSettings | None = None,
    limit: int = 20,
    watched_only: bool = True,
) -> DrainResult:
    """Extract filing metrics (+ YoY compare when compare flag on) for pending PDFs."""
    cfg = settings or MetricsSettings.from_env()
    if not metrics_enabled(cfg):
        return DrainResult("drain-metrics", 0, 0, 0, 0)

    items = await storage.list_disclosures_pending_metrics(
        limit=limit, watched_only=watched_only
    )
    updated = 0
    skipped = 0
    errors = 0
    for disc in items:
        if not is_financial_filing(title=disc.title, category=disc.category):
            skipped += 1
            continue
        try:
            result = await process_disclosure_metrics(
                storage=storage,
                disclosure=disc,
                rules=[],
                settings=cfg,
            )
            if result is None or result.metrics_id is None:
                skipped += 1
            else:
                updated += 1
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "drain_metrics_failed",
                disclosure_id=disc.id,
                error=str(exc)[:200],
            )
            errors += 1
    return DrainResult("drain-metrics", len(items), updated, skipped, errors)


async def drain_graph(
    *,
    storage: Storage,
    settings: GraphSettings | None = None,
    limit: int = 20,
    watched_only: bool = True,
    symbols: list[str] | None = None,
) -> DrainResult:
    """Extract equity + company relationships from pending annual PDFs."""
    cfg = settings or GraphSettings.from_env()
    if not graph_enabled(cfg):
        return DrainResult("drain-graph", 0, 0, 0, 0)

    items = await storage.list_disclosures_pending_graph(
        limit=limit,
        watched_only=watched_only,
        symbols=symbols,
    )
    updated = 0
    skipped = 0
    errors = 0
    for disc in items:
        if not is_financial_filing(title=disc.title, category=disc.category):
            # Still record a skip extract so we don't spin forever on junk titles
            skipped += 1
            continue
        try:
            result = await process_disclosure_graph(
                storage=storage,
                disclosure=disc,
                settings=cfg,
            )
            if result is None or result.extract_id is None:
                skipped += 1
            else:
                updated += 1
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "drain_graph_failed",
                disclosure_id=disc.id,
                error=str(exc)[:200],
            )
            errors += 1
    return DrainResult("drain-graph", len(items), updated, skipped, errors)


async def drain_people(
    *,
    storage: Storage,
    settings: GraphSettings | None = None,
    limit: int = 20,
    watched_only: bool = True,
    symbols: list[str] | None = None,
) -> DrainResult:
    """Extract directors / CEOs from pending annual PDFs."""
    cfg = settings or GraphSettings.from_env()
    if not people_enabled(cfg):
        return DrainResult("drain-people", 0, 0, 0, 0)

    items = await storage.list_disclosures_pending_people(
        limit=limit,
        watched_only=watched_only,
        symbols=symbols,
    )
    updated = 0
    skipped = 0
    errors = 0
    for disc in items:
        if not is_financial_filing(title=disc.title, category=disc.category):
            skipped += 1
            continue
        try:
            result = await process_disclosure_people(
                storage=storage,
                disclosure=disc,
                settings=cfg,
            )
            if result is None or result.extract_id is None:
                skipped += 1
            else:
                updated += 1
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "drain_people_failed",
                disclosure_id=disc.id,
                error=str(exc)[:200],
            )
            errors += 1
    return DrainResult("drain-people", len(items), updated, skipped, errors)
