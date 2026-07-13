"""Async worker: PDF → filing_metrics → YoY compare → optional alert events."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

import httpx
import structlog

from chime.briefs.extract import CdnPdfPermanentError, fetch_cdn_pdf
from chime.domain import AlertEvent, AlertRule, Disclosure
from chime.extractors.financial_pdf import (
    extract_filing_from_bytes,
    is_financial_filing,
)
from chime.metrics import MetricsSettings, compare_enabled, metrics_enabled
from chime.metrics.compare import MetricsRow, resolve_prior
from chime.rules import evaluate_filing_metrics_rules

log = structlog.get_logger("chime.metrics.worker")

_DEFAULT_PDF_MAX_BYTES = 5_242_880


class MetricsStorage(Protocol):
    async def upsert_filing_metrics(self, row: dict[str, Any]) -> dict[str, Any]: ...

    async def list_filing_metrics_for_symbol(
        self, symbol: str, *, kind: str | None = None
    ) -> list[dict[str, Any]]: ...

    async def upsert_filing_comparison(self, row: dict[str, Any]) -> dict[str, Any]: ...

    async def get_filing_comparison_for_metrics(
        self, filing_metrics_id: int
    ) -> dict[str, Any] | None: ...


@dataclass(frozen=True)
class MetricsJobResult:
    disclosure_id: int
    metrics_id: int | None
    extract_ok: bool
    compared: bool
    events: list[AlertEvent]


def _row_to_metrics(d: dict[str, Any]) -> MetricsRow:
    period = d.get("fiscal_period_end")
    if isinstance(period, str):
        period = date.fromisoformat(period[:10])
    return MetricsRow(
        id=int(d["id"]) if d.get("id") is not None else None,
        symbol=str(d["symbol"]),
        kind=str(d["kind"]),
        fiscal_period_end=period,
        fiscal_quarter=d.get("fiscal_quarter"),
        entity=str(d.get("entity") or "unknown"),
        scale=str(d.get("scale") or "unknown"),
        currency=str(d.get("currency") or "LKR"),
        revenue=d.get("revenue"),
        profit=d.get("profit"),
        eps_basic=d.get("eps_basic"),
        extract_ok=bool(d.get("extract_ok")),
    )


async def process_disclosure_metrics(
    *,
    storage: MetricsStorage,
    disclosure: Disclosure,
    rules: list[AlertRule] | None = None,
    settings: MetricsSettings | None = None,
    pdf_bytes: bytes | None = None,
) -> MetricsJobResult | None:
    """Extract + compare one disclosure. Returns None if metrics disabled / not financial."""
    cfg = settings or MetricsSettings.from_env()
    if not metrics_enabled(cfg):
        return None
    if disclosure.id is None:
        return None
    if not is_financial_filing(title=disclosure.title, category=disclosure.category):
        log.info(
            "metrics_skip_non_financial",
            disclosure_id=disclosure.id,
            symbol=disclosure.symbol,
        )
        return None

    pdf_url = disclosure.pdf_url
    data = pdf_bytes
    if data is None:
        if not pdf_url:
            return MetricsJobResult(
                disclosure_id=disclosure.id,
                metrics_id=None,
                extract_ok=False,
                compared=False,
                events=[],
            )
        try:
            max_bytes = int(os.getenv("PDF_MAX_BYTES", str(_DEFAULT_PDF_MAX_BYTES)))
        except (TypeError, ValueError):
            max_bytes = _DEFAULT_PDF_MAX_BYTES
        max_bytes = max(1, max_bytes)
        try:
            async with httpx.AsyncClient(
                timeout=60.0,
                follow_redirects=False,
            ) as client:
                data = await fetch_cdn_pdf(
                    pdf_url,
                    max_bytes=max_bytes,
                    client=client,
                )
        except CdnPdfPermanentError as exc:
            log.warning(
                "metrics_pdf_permanent_fail",
                disclosure_id=disclosure.id,
                error=str(exc)[:200],
            )
            data = None
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "metrics_pdf_fetch_fail",
                disclosure_id=disclosure.id,
                error=str(exc)[:200],
            )
            data = None

    if not data:
        extracted_notes = {"error": "pdf_unavailable"}
        metrics_row = {
            "disclosure_id": disclosure.id,
            "symbol": disclosure.symbol,
            "kind": "unknown",
            "fiscal_period_end": None,
            "fiscal_quarter": None,
            "entity": "unknown",
            "scale": "unknown",
            "currency": "LKR",
            "revenue": None,
            "profit": None,
            "eps_basic": None,
            "eps_diluted": None,
            "extract_ok": False,
            "extract_notes": extracted_notes,
            "pdf_url": pdf_url,
        }
    else:
        result = extract_filing_from_bytes(
            data,
            title=disclosure.title,
            category=disclosure.category,
        )
        metrics_row = {
            "disclosure_id": disclosure.id,
            "symbol": disclosure.symbol,
            "kind": result.kind,
            "fiscal_period_end": result.fiscal_period_end,
            "fiscal_quarter": result.fiscal_quarter,
            "entity": result.entity,
            "scale": result.scale,
            "currency": result.currency,
            "revenue": result.revenue,
            "profit": result.profit,
            "eps_basic": result.eps_basic,
            "eps_diluted": result.eps_diluted,
            "extract_ok": result.extract_ok,
            "extract_notes": result.notes,
            "pdf_url": pdf_url,
        }

    saved = await storage.upsert_filing_metrics(metrics_row)
    metrics_id = int(saved["id"])
    compared = False
    comparison: dict[str, Any] | None = None

    if compare_enabled(cfg) and bool(saved.get("extract_ok")):
        candidates_raw = await storage.list_filing_metrics_for_symbol(
            disclosure.symbol, kind=str(saved.get("kind") or "unknown")
        )
        current = _row_to_metrics(saved)
        priors = [_row_to_metrics(r) for r in candidates_raw]
        cmp = resolve_prior(current, priors)
        comparison = {
            "filing_metrics_id": metrics_id,
            "prior_filing_metrics_id": cmp.prior_id,
            "match_quality": cmp.match_quality,
            "eps_delta": cmp.eps_delta,
            "eps_delta_pct": cmp.eps_delta_pct,
            "revenue_delta": cmp.revenue_delta,
            "revenue_delta_pct": cmp.revenue_delta_pct,
            "profit_delta": cmp.profit_delta,
            "profit_delta_pct": cmp.profit_delta_pct,
        }
        await storage.upsert_filing_comparison(comparison)
        compared = True

    events: list[AlertEvent] = []
    if rules:
        events = evaluate_filing_metrics_rules(
            metrics=saved,
            comparison=comparison,
            disclosure=disclosure,
            rules=rules,
            settings=cfg,
        )
    log.info(
        "metrics_processed",
        disclosure_id=disclosure.id,
        metrics_id=metrics_id,
        extract_ok=bool(saved.get("extract_ok")),
        compared=compared,
        events=len(events),
        notes=json.dumps(saved.get("extract_notes") or {})[:200],
    )
    return MetricsJobResult(
        disclosure_id=disclosure.id,
        metrics_id=metrics_id,
        extract_ok=bool(saved.get("extract_ok")),
        compared=compared,
        events=events,
    )
