"""Async worker: annual PDF → people (directors / CEOs) + roles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx
import structlog

from koel.briefs.extract import CdnPdfPermanentError, fetch_cdn_pdf
from koel.domain import Disclosure
from koel.extractors.financial_pdf import is_financial_filing
from koel.extractors.people_pdf import extract_people_from_bytes, normalize_person_name
from koel.graph import GraphSettings, graph_enabled

log = structlog.get_logger("koel.graph.people_worker")


class PeopleStorage(Protocol):
    async def upsert_filing_people_extract(self, row: dict[str, Any]) -> dict[str, Any]: ...

    async def upsert_person(self, *, display_name: str, name_norm: str) -> dict[str, Any]: ...

    async def upsert_person_company_role(self, row: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class PeopleJobResult:
    disclosure_id: int
    extract_id: int | None
    extract_ok: bool
    people_ok: bool
    roles_written: int


def people_enabled(settings: GraphSettings | None = None) -> bool:
    """People extract rides the company-graph flag (same research surface)."""
    import os

    raw = os.getenv("COMPANY_PEOPLE_ENABLED")
    if isinstance(raw, str) and raw.strip() != "":
        return raw.strip() == "1"
    return graph_enabled(settings)


async def process_disclosure_people(
    *,
    storage: PeopleStorage,
    disclosure: Disclosure,
    settings: GraphSettings | None = None,
    pdf_bytes: bytes | None = None,
) -> PeopleJobResult | None:
    cfg = settings or GraphSettings.from_env()
    if not people_enabled(cfg):
        return None
    if disclosure.id is None:
        return None
    if not is_financial_filing(title=disclosure.title, category=disclosure.category):
        return None

    pdf_url = disclosure.pdf_url
    data = pdf_bytes
    if data is None and pdf_url:
        try:
            async with httpx.AsyncClient(timeout=90.0, follow_redirects=False) as client:
                data = await fetch_cdn_pdf(
                    pdf_url, max_bytes=cfg.pdf_max_bytes, client=client
                )
        except CdnPdfPermanentError as exc:
            log.warning(
                "people_pdf_permanent_fail",
                disclosure_id=disclosure.id,
                error=str(exc)[:200],
            )
            data = None
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "people_pdf_fetch_fail",
                disclosure_id=disclosure.id,
                error=str(exc)[:200],
            )
            data = None

    if not data:
        saved = await storage.upsert_filing_people_extract(
            {
                "disclosure_id": disclosure.id,
                "symbol": disclosure.symbol,
                "people_ok": False,
                "extract_ok": False,
                "extract_notes": {"error": "pdf_unavailable"},
                "pdf_url": pdf_url,
            }
        )
        return PeopleJobResult(
            disclosure_id=disclosure.id,
            extract_id=int(saved["id"]),
            extract_ok=False,
            people_ok=False,
            roles_written=0,
        )

    result = extract_people_from_bytes(
        data,
        title=disclosure.title,
        category=disclosure.category,
        max_pages=max(cfg.max_pages, 160),
    )
    saved = await storage.upsert_filing_people_extract(
        {
            "disclosure_id": disclosure.id,
            "symbol": disclosure.symbol,
            "people_ok": result.people_ok,
            "extract_ok": result.extract_ok,
            "extract_notes": result.notes,
            "pdf_url": pdf_url,
        }
    )

    roles_written = 0
    keep_low = cfg.keep_low_confidence
    for cand in result.people:
        if cand.confidence == "low" and not keep_low:
            continue
        name_norm = normalize_person_name(cand.display_name)
        if not name_norm:
            continue
        person = await storage.upsert_person(
            display_name=cand.display_name,
            name_norm=name_norm,
        )
        await storage.upsert_person_company_role(
            {
                "person_id": int(person["id"]),
                "symbol": disclosure.symbol,
                "role": cand.role,
                "confidence": cand.confidence,
                "evidence_disclosure_id": disclosure.id,
                "evidence_page": cand.evidence_page,
                "evidence_snippet": cand.evidence_snippet,
                "extract_notes": {},
            }
        )
        roles_written += 1

    log.info(
        "people_processed",
        disclosure_id=disclosure.id,
        extract_id=int(saved["id"]),
        people_ok=result.people_ok,
        roles_written=roles_written,
    )
    return PeopleJobResult(
        disclosure_id=disclosure.id,
        extract_id=int(saved["id"]),
        extract_ok=result.extract_ok,
        people_ok=result.people_ok,
        roles_written=roles_written,
    )
