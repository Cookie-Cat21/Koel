"""Production financial PDF extract API (promoted from research spike).

Fail closed: callers must check ``extract_ok`` before using numbers as alert truth.
"""

from __future__ import annotations

import os
import re
import tempfile
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from koel.extractors import cse_pdf_core as core

_FINANCIAL_TITLE = re.compile(
    r"\b("
    r"interim\s+financial|financial\s+statements?|quarterly\s+results?|"
    r"annual\s+report|audited\s+financial|unaudited\s+financial|"
    r"condensed\s+financial|statement\s+of\s+profit|"
    r"q[1-4]\s+results?|nine\s+months|six\s+months|three\s+months"
    r")\b",
    re.I,
)
_ANNUAL_HINT = re.compile(r"\b(annual\s+report|year\s+ended|audited\s+financial)\b", re.I)
_QUARTER_HINT = re.compile(
    r"\b(interim|quarterly|three\s+months|six\s+months|nine\s+months|q[1-4])\b",
    re.I,
)
_PERIOD_END = re.compile(
    r"(?:ended|as\s+at|as\s+of)\s+"
    r"(?:the\s+)?"
    r"(\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+(\d{4})",
    re.I,
)
_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


@dataclass
class FilingExtractResult:
    kind: str  # quarterly|annual|unknown
    entity: str  # group|company|unknown
    scale: str
    currency: str
    revenue: float | None = None
    profit: float | None = None
    eps_basic: float | None = None
    eps_diluted: float | None = None
    fiscal_period_end: date | None = None
    fiscal_quarter: int | None = None
    extract_ok: bool = False
    notes: dict[str, Any] = field(default_factory=dict)


def is_financial_filing(*, title: str | None, category: str | None = None) -> bool:
    """Strict allowlist: only titles/categories that look like financial statements."""
    blob = f"{title or ''} {category or ''}"
    return bool(_FINANCIAL_TITLE.search(blob))


def infer_filing_kind(*, title: str | None, category: str | None = None) -> str:
    blob = f"{title or ''} {category or ''}"
    if _ANNUAL_HINT.search(blob) and not _QUARTER_HINT.search(blob):
        return "annual"
    if _QUARTER_HINT.search(blob):
        return "quarterly"
    if _ANNUAL_HINT.search(blob):
        return "annual"
    return "unknown"


def _parse_period_end(text: str) -> date | None:
    m = _PERIOD_END.search(text or "")
    if not m:
        return None
    day = int(m.group(1))
    month = _MONTHS.get(m.group(2).lower())
    year = int(m.group(3))
    if not month:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _fiscal_quarter(period_end: date | None) -> int | None:
    if period_end is None:
        return None
    # CSE common calendar: Mar=Q4/Q1-end variants; map by month end
    m = period_end.month
    if m in (3,):
        return 4  # year / Q4 ended 31 Mar (common CSE FY)
    if m in (6,):
        return 1
    if m in (9,):
        return 2
    if m in (12,):
        return 3
    return None


def score_pages_pypdf(
    pdf_path: Path, *, max_pages: int | None = None
) -> list[tuple[int, int, str]]:
    """Page scorer using pypdf (production dependency) when pymupdf is absent."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    n = len(reader.pages) if max_pages is None else min(len(reader.pages), max_pages)
    scored: list[tuple[int, int, str]] = []
    for i in range(n):
        try:
            text = reader.pages[i].extract_text() or ""
        except Exception:  # noqa: BLE001
            text = ""
        text = core._normalize_pdf_text(text)
        low = text.lower()
        hits = sum(1 for kw in core.SOPL_KEYWORDS if kw in low)
        if re.search(r"\d{1,3}(?:,\d{3})+", text):
            hits += 1
        if ("revenue" in low or "turnover" in low or "interest income" in low) and (
            "per share" in low or "profit for the" in low
        ):
            hits += 3
        if "statement of profit" in low and len(text) > 1500:
            hits += 4
        scored.append((i, hits, text))
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored


def pick_pages_and_extract(
    pdf_path: Path, *, kind: str
) -> tuple[dict[str, Any], list[tuple[int, str]]]:
    """Score pages and run the hardened extract_from_pages ranker."""
    max_pages = None if kind == "annual" else 50
    try:
        scored = core.score_pages(pdf_path, max_pages=max_pages)
    except Exception:  # noqa: BLE001 — typically missing pymupdf
        scored = score_pages_pypdf(pdf_path, max_pages=max_pages)
    budget = 40 if kind == "annual" else 20
    top_idx = [p for p, h, _ in scored if h >= 2][:budget]
    if len(top_idx) < 4:
        top_idx = [p for p, _, _ in scored[:10]]
    text_by_page = {p: t for p, _, t in scored}
    eps_page_re = re.compile(
        r"earnings?\s+per\s+share|earning\s+per\s+share|loss\s+per\s+share|"
        r"basic\s+and\s+diluted|basic\s+eps",
        re.I,
    )
    for p, _h, t in scored:
        if p in top_idx:
            continue
        if eps_page_re.search(t or ""):
            top_idx.append(p)
        if len(top_idx) >= budget + 25:
            break
    pages = [(i, text_by_page[i]) for i in top_idx if i in text_by_page]
    for p, _h, t in scored[:12]:
        if p not in {i for i, _ in pages}:
            pages.append((p, t))
    extracted = core.extract_from_pages(
        pages, kind=kind if kind in ("quarterly", "annual") else "annual"
    )
    return extracted, pages


def extract_filing_from_path(
    pdf_path: Path | str,
    *,
    kind: str | None = None,
    title: str | None = None,
    category: str | None = None,
) -> FilingExtractResult:
    path = Path(pdf_path)
    resolved_kind = kind or infer_filing_kind(title=title, category=category)
    if resolved_kind == "unknown":
        resolved_kind = "annual"
    notes: dict[str, Any] = {"kind_inferred": kind is None}
    try:
        extracted, pages = pick_pages_and_extract(path, kind=resolved_kind)
    except Exception as exc:  # noqa: BLE001 — fail closed to extract_ok=False
        return FilingExtractResult(
            kind=resolved_kind,
            entity="unknown",
            scale="unknown",
            currency="LKR",
            extract_ok=False,
            notes={"error": str(exc)[:240]},
        )

    sample = "\n".join(t for _, t in pages[:8])
    period_end = _parse_period_end(sample) or _parse_period_end(
        "\n".join(t for _, t in pages)
    )
    currency = (
        "USD"
        if re.search(r"indicative\s+us\s*dollar|us\s*dollar\s+income", sample, re.I)
        else "LKR"
    )

    def _val(pick: Any) -> float | None:
        if pick is None:
            return None
        try:
            return float(pick.value)
        except (TypeError, ValueError, AttributeError):
            return None

    def _entity() -> str:
        eps = extracted.get("eps_basic")
        if eps is None:
            return "unknown"
        notes_list = list(getattr(eps, "notes", []) or [])
        if "on_group_page" in notes_list:
            return "group"
        if "on_company_only_page" in notes_list:
            return "company"
        return "unknown"

    revenue = _val(extracted.get("revenue"))
    profit = _val(extracted.get("profit"))
    eps_basic = _val(extracted.get("eps_basic"))
    eps_diluted = _val(extracted.get("eps_diluted"))
    scale = str(extracted.get("scale") or "unknown")
    if scale not in ("units", "thousands", "millions", "unknown"):
        scale = "unknown"

    extract_ok = (
        currency == "LKR"
        and eps_basic is not None
        and extracted.get("eps_basic") is not None
        and bool(getattr(extracted["eps_basic"], "verified", False))
        and revenue is not None
        and profit is not None
        and bool(getattr(extracted.get("revenue"), "verified", False))
        and bool(getattr(extracted.get("profit"), "verified", False))
    )
    if currency == "USD":
        notes["skipped_usd_page"] = True
        extract_ok = False

    notes["period"] = extracted.get("period")
    notes["cand_counts"] = extracted.get("cand_counts")
    if extracted.get("eps_basic") is not None:
        notes["eps_label"] = getattr(extracted["eps_basic"], "label", None)
        notes["eps_page"] = getattr(extracted["eps_basic"], "page", None)

    return FilingExtractResult(
        kind=resolved_kind if resolved_kind in ("quarterly", "annual") else "unknown",
        entity=_entity(),
        scale=scale,
        currency=currency,
        revenue=revenue,
        profit=profit,
        eps_basic=eps_basic,
        eps_diluted=eps_diluted,
        fiscal_period_end=period_end,
        fiscal_quarter=_fiscal_quarter(period_end) if resolved_kind == "quarterly" else None,
        extract_ok=extract_ok,
        notes=notes,
    )


def extract_filing_from_bytes(
    data: bytes,
    *,
    kind: str | None = None,
    title: str | None = None,
    category: str | None = None,
) -> FilingExtractResult:
    """Write bytes to a temp PDF and extract (production CDN path)."""
    if not data:
        return FilingExtractResult(
            kind=kind or "unknown",
            entity="unknown",
            scale="unknown",
            currency="LKR",
            extract_ok=False,
            notes={"error": "empty_pdf"},
        )
    # delete=False + manual unlink: on Windows, delete=True keeps an exclusive
    # lock on the handle, so a second open (pypdf/fitz reading tmp.name) fails
    # with PermissionError while this file object is still open.
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)  # noqa: SIM115
    try:
        tmp.write(data)
        tmp.flush()
        tmp.close()
        return extract_filing_from_path(
            tmp.name, kind=kind, title=title, category=category
        )
    finally:
        with suppress(OSError):
            os.unlink(tmp.name)
