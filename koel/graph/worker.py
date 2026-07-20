"""Async worker: annual PDF → equity node + relationship edges."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
import structlog

from koel.adapters.cse import normalize_company_name
from koel.briefs.extract import CdnPdfPermanentError, fetch_cdn_pdf
from koel.domain import Disclosure
from koel.extractors.company_graph_pdf import extract_company_graph_from_bytes
from koel.extractors.financial_pdf import is_financial_filing
from koel.graph import GraphSettings, graph_enabled
from koel.graph.resolve import maps_from_stock_pairs, resolve_company_name

log = structlog.get_logger("koel.graph.worker")


class GraphStorage(Protocol):
    async def list_stock_name_pairs(self) -> list[tuple[str, str | None]]: ...

    async def upsert_filing_graph_extract(self, row: dict[str, Any]) -> dict[str, Any]: ...

    async def upsert_company_graph_node(self, row: dict[str, Any]) -> dict[str, Any]: ...

    async def upsert_company_graph_edge(self, row: dict[str, Any]) -> dict[str, Any]: ...

    async def get_company_graph_node_by_symbol(
        self, symbol: str
    ) -> dict[str, Any] | None: ...


@dataclass(frozen=True)
class GraphJobResult:
    disclosure_id: int
    extract_id: int | None
    extract_ok: bool
    edges_written: int
    equity_ok: bool


async def process_disclosure_graph(
    *,
    storage: GraphStorage,
    disclosure: Disclosure,
    settings: GraphSettings | None = None,
    pdf_bytes: bytes | None = None,
) -> GraphJobResult | None:
    cfg = settings or GraphSettings.from_env()
    if not graph_enabled(cfg):
        return None
    if disclosure.id is None:
        return None

    if not is_financial_filing(title=disclosure.title, category=disclosure.category):
        log.info(
            "graph_skip_non_financial",
            disclosure_id=disclosure.id,
            symbol=disclosure.symbol,
        )
        return None

    pdf_url = disclosure.pdf_url
    data = pdf_bytes
    if data is None and pdf_url:
        try:
            async with httpx.AsyncClient(
                timeout=90.0,
                follow_redirects=False,
            ) as client:
                data = await fetch_cdn_pdf(
                    pdf_url,
                    max_bytes=cfg.pdf_max_bytes,
                    client=client,
                )
        except CdnPdfPermanentError as exc:
            log.warning(
                "graph_pdf_permanent_fail",
                disclosure_id=disclosure.id,
                error=str(exc)[:200],
            )
            data = None
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "graph_pdf_fetch_fail",
                disclosure_id=disclosure.id,
                error=str(exc)[:200],
            )
            data = None

    if not data:
        saved = await storage.upsert_filing_graph_extract(
            {
                "disclosure_id": disclosure.id,
                "symbol": disclosure.symbol,
                "kind": "unknown",
                "fiscal_period_end": None,
                "entity": "unknown",
                "scale": "unknown",
                "currency": "LKR",
                "equity": None,
                "equity_label": None,
                "equity_ok": False,
                "relations_ok": False,
                "extract_ok": False,
                "extract_notes": {"error": "pdf_unavailable"},
                "pdf_url": pdf_url,
            }
        )
        return GraphJobResult(
            disclosure_id=disclosure.id,
            extract_id=int(saved["id"]),
            extract_ok=False,
            edges_written=0,
            equity_ok=False,
        )

    result = extract_company_graph_from_bytes(
        data,
        title=disclosure.title,
        category=disclosure.category,
        symbol=disclosure.symbol,
        max_pages=cfg.max_pages,
    )

    extract_row = {
        "disclosure_id": disclosure.id,
        "symbol": disclosure.symbol,
        "kind": result.kind,
        "fiscal_period_end": result.fiscal_period_end,
        "entity": result.entity,
        "scale": result.scale,
        "currency": result.currency,
        "equity": result.equity,
        "equity_label": result.equity_label,
        "equity_ok": result.equity_ok,
        "relations_ok": result.relations_ok,
        "extract_ok": result.extract_ok,
        "extract_notes": {
            **result.notes,
            "equity_confidence": result.equity_confidence,
            "edge_candidates": len(result.edges),
        },
        "pdf_url": pdf_url,
    }
    saved = await storage.upsert_filing_graph_extract(extract_row)
    extract_id = int(saved["id"])

    # Ensure source listed node exists
    pairs = await storage.list_stock_name_pairs()
    exact_map, suffix_map = maps_from_stock_pairs(pairs)
    issuer_name = next(
        (n for s, n in pairs if s == disclosure.symbol and n),
        disclosure.symbol,
    )
    src = await storage.upsert_company_graph_node(
        {
            "symbol": disclosure.symbol,
            "display_name": issuer_name or disclosure.symbol,
            "name_norm": normalize_company_name(issuer_name or disclosure.symbol),
            "node_kind": "listed",
            "equity": result.equity if result.equity_ok else None,
            "equity_as_of": result.fiscal_period_end if result.equity_ok else None,
            "equity_scale": result.scale if result.equity_ok else "unknown",
            "equity_currency": result.currency,
            "equity_disclosure_id": disclosure.id if result.equity_ok else None,
            "equity_confidence": result.equity_confidence
            if result.equity_ok
            else "none",
            "update_equity": result.equity_ok,
        }
    )
    src_id = int(src["id"])

    edges_written = 0
    unresolved: list[str] = []
    for edge in result.edges:
        if edge.confidence == "low" and not cfg.keep_low_confidence:
            continue
        resolved = resolve_company_name(
            edge.raw_name,
            exact_map=exact_map,
            suffix_map=suffix_map,
        )
        if resolved.status != "resolved" or not resolved.symbol:
            # Unlisted nodes are opt-in — default keeps the graph listed-only
            # so narrative junk ("Directors of X Limited") does not explode nodes.
            keep_unlisted = os.getenv("COMPANY_GRAPH_UNLISTED", "0").strip() == "1"
            if (
                keep_unlisted
                and edge.confidence in {"medium", "high"}
                and edge.relation in {"subsidiary", "associate", "joint_venture"}
                and len(edge.raw_name) <= 60
            ):
                name_norm = normalize_company_name(edge.raw_name)
                if not name_norm:
                    unresolved.append(edge.raw_name[:80])
                    continue
                dst = await storage.upsert_company_graph_node(
                    {
                        "symbol": None,
                        "display_name": edge.raw_name[:120],
                        "name_norm": name_norm,
                        "node_kind": "unlisted",
                        "equity": None,
                        "equity_as_of": None,
                        "equity_scale": "unknown",
                        "equity_currency": "LKR",
                        "equity_disclosure_id": None,
                        "equity_confidence": "none",
                        "update_equity": False,
                    }
                )
            else:
                unresolved.append(edge.raw_name[:80])
                continue
        else:
            if resolved.symbol == disclosure.symbol:
                continue
            # Look up display name
            dst_name = next(
                (n for s, n in pairs if s == resolved.symbol and n),
                resolved.symbol,
            )
            dst = await storage.upsert_company_graph_node(
                {
                    "symbol": resolved.symbol,
                    "display_name": dst_name or resolved.symbol,
                    "name_norm": normalize_company_name(dst_name or resolved.symbol),
                    "node_kind": "listed",
                    "equity": None,
                    "equity_as_of": None,
                    "equity_scale": "unknown",
                    "equity_currency": "LKR",
                    "equity_disclosure_id": None,
                    "equity_confidence": "none",
                    "update_equity": False,
                }
            )

        dst_id = int(dst["id"])
        if dst_id == src_id:
            continue

        conf = edge.confidence
        if resolved.status == "resolved" and getattr(resolved, "method", "") == "fuzzy":
            conf = "low" if conf == "medium" else conf
            if conf == "low" and not cfg.keep_low_confidence:
                continue

        await storage.upsert_company_graph_edge(
            {
                "src_node_id": src_id,
                "dst_node_id": dst_id,
                "relation": edge.relation,
                "ownership_pct": edge.ownership_pct,
                "ownership_pct_confidence": edge.ownership_pct_confidence,
                "confidence": conf,
                "evidence_disclosure_id": disclosure.id,
                "evidence_page": edge.evidence_page,
                "evidence_snippet": (edge.evidence_snippet or "")[:280],
                "extract_notes": {
                    "raw_name": edge.raw_name[:120],
                    "resolve": resolved.status,
                    "method": getattr(resolved, "method", ""),
                },
            }
        )
        edges_written += 1

    if unresolved:
        # Patch notes with unresolved sample (best-effort; extract already saved)
        log.info(
            "graph_unresolved_names",
            disclosure_id=disclosure.id,
            count=len(unresolved),
            sample=unresolved[:8],
        )

    log.info(
        "graph_processed",
        disclosure_id=disclosure.id,
        extract_id=extract_id,
        extract_ok=result.extract_ok,
        equity_ok=result.equity_ok,
        edges_written=edges_written,
    )
    return GraphJobResult(
        disclosure_id=disclosure.id,
        extract_id=extract_id,
        extract_ok=result.extract_ok,
        edges_written=edges_written,
        equity_ok=result.equity_ok,
    )
