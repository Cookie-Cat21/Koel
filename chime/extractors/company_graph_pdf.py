"""Equity + relationship extract from CSE annual report PDFs.

Fail-closed: equity and edges are only emitted with confidence flags.
Ownership % is never invented.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from io import BytesIO
from typing import Any

from chime.extractors.financial_pdf import (
    infer_filing_kind,
    is_financial_filing,
)

_EQUITY_LABEL = re.compile(
    r"(?im)^\s*("
    r"total\s+equity|"
    r"equity\s+attributable\s+to\s+(?:owners|equity\s+holders|shareholders)"
    r"(?:\s+of\s+the\s+(?:parent|company))?|"
    r"shareholders['’]?\s+funds|"
    r"net\s+assets"
    r")\s*[:=\-]?\s*"
    r"(\(?-?(?:\d{1,3}(?:,\d{3})+|\d{4,})(?:\.\d+)?\)?)"
)

_SCALE = re.compile(
    r"(?i)\b(?:in\s+)?(?:rs\.?\s*)?(thousands|millions|000['’]?s?)\b"
)
_GROUP = re.compile(r"(?i)\b(group|consolidated)\b")
_COMPANY = re.compile(r"(?i)\b(company|parent)\b")

_SECTION_SUB = re.compile(
    r"(?i)(subsidiar|group\s+structure|investment\s+in\s+subsidiar|"
    r"principal\s+subsidiar|details\s+of\s+subsidiar)"
)
_SECTION_ASSOC = re.compile(
    r"(?i)(associate\s+compan|investment\s+in\s+associate|joint\s+venture)"
)
_SECTION_RP = re.compile(r"(?i)(related\s+part(?:y|ies)|transactions\s+with\s+related)")
_SECTION_SOFP = re.compile(
    r"(?i)(statement\s+of\s+financial\s+position|balance\s+sheet|"
    r"statement\s+of\s+changes\s+in\s+equity)"
)

_COMPANY_PHRASE = re.compile(
    r"\b([A-Z][A-Za-z0-9&.'/\-][A-Za-z0-9&.'/\-\s]{1,70}?)\s+"
    r"(PLC|Limited|Ltd\.?)\b"
)
_OWNERSHIP_PCT = re.compile(
    r"(?i)(?:held|holding|ownership|interest(?:\s+of)?|owns?)\s*"
    r"[^\n%]{0,40}?(\d{1,3}(?:\.\d+)?)\s*%"
)
_PCT_NEAR = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")

_NOISE_NAME = re.compile(
    r"(?i)^(form\s+of\s+proxy|annual\s+report|directors?\s+of|board\s+of|"
    r"on\s+behalf\s+of|audited\s+financial|we\s+are|the\s+achievements|"
    r"issuer\s+rating|corporate\s+affairs|across\s+every|at\s+|for\s+|"
    r"ms\.|mr\.|dr\.|chairman\s+of)"
)

_PERIOD_END = re.compile(
    r"(?:ended|as\s+at|as\s+of)\s+(?:the\s+)?"
    r"(\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(january|february|march|april|may|june|july|august|september|october|"
    r"november|december)\s+(\d{4})",
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
class GraphEdgeCandidate:
    raw_name: str
    relation: str
    confidence: str
    ownership_pct: float | None = None
    ownership_pct_confidence: str = "none"
    evidence_page: int | None = None
    evidence_snippet: str = ""


@dataclass
class GraphExtractResult:
    kind: str
    entity: str = "unknown"
    scale: str = "unknown"
    currency: str = "LKR"
    fiscal_period_end: date | None = None
    equity: float | None = None
    equity_label: str | None = None
    equity_ok: bool = False
    equity_confidence: str = "none"
    relations_ok: bool = False
    extract_ok: bool = False
    edges: list[GraphEdgeCandidate] = field(default_factory=list)
    notes: dict[str, Any] = field(default_factory=dict)


def _parse_num(raw: str) -> float | None:
    if not isinstance(raw, str):
        return None
    s = raw.strip().replace(",", "")
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        val = float(s)
    except ValueError:
        return None
    if not (val == val) or abs(val) > 1e15:  # NaN / absurd
        return None
    # Reject year-like stubs unless large enough to be equity in thousands
    if 1900 <= val <= 2100:
        return None
    return -val if neg else val


def _detect_scale(text: str) -> str:
    m = _SCALE.search(text[:8000] if text else "")
    if not m:
        return "unknown"
    token = m.group(1).lower()
    if "million" in token:
        return "millions"
    return "thousands"


def _detect_entity(text: str) -> str:
    head = text[:6000] if text else ""
    g = bool(_GROUP.search(head))
    c = bool(_COMPANY.search(head))
    if g and not c:
        return "group"
    if c and not g:
        return "company"
    if g:
        return "group"
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


def extract_pdf_pages(data: bytes, *, max_pages: int = 140) -> list[tuple[int, str]]:
    """Return (1-based page, text) pairs. Soft-fail → []."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return []
    try:
        reader = PdfReader(BytesIO(data))
    except Exception:
        return []
    out: list[tuple[int, str]] = []
    for i, page in enumerate(reader.pages[: max(1, max_pages)]):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        out.append((i + 1, text))
    return out


def _clean_name(raw: str) -> str | None:
    name = re.sub(r"\s+", " ", (raw or "").strip())
    if len(name) < 3 or len(name) > 80:
        return None
    if _NOISE_NAME.search(name):
        return None
    letters = [c for c in name if c.isalpha()]
    if not letters:
        return None
    # Accept ALL CAPS, Title Case, or mixed — reject mostly-lowercase narrative
    upper = sum(1 for c in letters if c.isupper())
    words = [w for w in name.split() if any(c.isalpha() for c in w)]
    titleish = bool(words) and sum(1 for w in words if w[0].isupper()) >= max(
        1, len(words) // 2
    )
    if upper / len(letters) < 0.12 and not titleish:
        return None
    return name


def _relation_for_section(section: str) -> str:
    if section == "sub":
        return "subsidiary"
    if section == "assoc":
        return "joint_venture" if "joint" in section else "associate"
    if section == "rp":
        return "related_party"
    return "group_mention"


def _classify_window(text: str) -> str | None:
    if _SECTION_SUB.search(text):
        return "sub"
    if _SECTION_ASSOC.search(text):
        return "assoc"
    if _SECTION_RP.search(text):
        return "rp"
    if _SECTION_SOFP.search(text):
        return "sofp"
    return None


def _extract_equity(pages: list[tuple[int, str]]) -> tuple[
    float | None, str | None, str, dict[str, Any]
]:
    notes: dict[str, Any] = {}
    # Prefer SOFP-ish pages
    ranked = sorted(
        pages,
        key=lambda p: (0 if _SECTION_SOFP.search(p[1]) else 1, p[0]),
    )
    candidates: list[tuple[float, str, int]] = []
    for page_no, text in ranked[:40]:
        for m in _EQUITY_LABEL.finditer(text):
            label = re.sub(r"\s+", " ", m.group(1)).strip()
            num = _parse_num(m.group(2))
            if num is None or abs(num) < 100:
                continue
            candidates.append((num, label, page_no))
    if not candidates:
        notes["equity"] = "no_candidate"
        return None, None, "none", notes
    # Prefer "Total equity" / attributable, largest magnitude among top labels
    def score(item: tuple[float, str, int]) -> tuple[int, float]:
        _, label, _ = item
        lab = label.lower()
        pri = 0
        if lab.startswith("total equity"):
            pri = 3
        elif "attributable" in lab:
            pri = 2
        elif "shareholders" in lab:
            pri = 1
        return (pri, abs(item[0]))

    best = max(candidates, key=score)
    conf = "medium"
    if best[1].lower().startswith("total equity") or "attributable" in best[1].lower():
        conf = "high"
    notes["equity_candidates"] = len(candidates)
    notes["equity_page"] = best[2]
    return best[0], best[1][:120], conf, notes


def _extract_edges(
    pages: list[tuple[int, str]],
    *,
    issuer_symbol: str,
) -> tuple[list[GraphEdgeCandidate], dict[str, Any]]:
    notes: dict[str, Any] = {"windows": 0, "raw_names": 0}
    edges: list[GraphEdgeCandidate] = []
    seen: set[tuple[str, str]] = set()

    # Sliding windows of 2 pages for section context
    for i in range(len(pages)):
        page_no, text = pages[i]
        window = text
        if i + 1 < len(pages):
            window = text + "\n" + pages[i + 1][1]
        section = _classify_window(window)
        if section is None:
            # Still allow group_mention for listed PLC co-mentions near "group"
            if not re.search(r"(?i)\bgroup\b", window[:2000]):
                continue
            section = "mention"
        notes["windows"] = int(notes["windows"]) + 1

        if section == "sofp":
            continue

        relation = {
            "sub": "subsidiary",
            "assoc": "associate",
            "rp": "related_party",
            "mention": "group_mention",
        }.get(section, "group_mention")

        base_conf = {
            "sub": "medium",
            "assoc": "medium",
            "rp": "medium",
            "mention": "low",
        }.get(section, "low")

        # Relation cue must sit near the company name (cuts false "subsidiary"
        # edges from a page that merely contains the word once in a heading).
        relation_cue = {
            "sub": re.compile(
                r"(?i)(subsidiar|wholly\s+owned|owned\s+subsidiar|group\s+compan)"
            ),
            "assoc": re.compile(r"(?i)(associate|joint\s+venture|equity\s+accounted)"),
            "rp": re.compile(r"(?i)(related\s+part|key\s+management|affiliate)"),
            "mention": re.compile(r"(?i)(group|subsidiary|associate)"),
        }.get(section)

        for m in _COMPANY_PHRASE.finditer(window):
            raw = _clean_name(f"{m.group(1)} {m.group(2)}")
            if not raw:
                continue
            notes["raw_names"] = int(notes["raw_names"]) + 1
            key = (raw.upper(), relation)
            if key in seen:
                continue

            # Local context for ownership % + relation proximity
            start = max(0, m.start() - 120)
            end = min(len(window), m.end() + 120)
            local = window[start:end]
            if relation_cue is not None and not relation_cue.search(local):
                # Allow group_mention without tight cue; skip others
                if section != "mention":
                    continue

            seen.add(key)
            conf = base_conf
            ownership = None
            own_conf = "none"
            om = _OWNERSHIP_PCT.search(local)
            if om:
                try:
                    pct = float(om.group(1))
                    if 0 <= pct <= 100:
                        ownership = pct
                        own_conf = "medium"
                        if conf == "medium":
                            conf = "high"
                except ValueError:
                    pass

            snippet = re.sub(r"\s+", " ", local).strip()[:240]
            edges.append(
                GraphEdgeCandidate(
                    raw_name=raw,
                    relation=relation,
                    confidence=conf,
                    ownership_pct=ownership,
                    ownership_pct_confidence=own_conf,
                    evidence_page=page_no,
                    evidence_snippet=snippet,
                )
            )
            if len(edges) >= 80:
                notes["truncated"] = True
                return edges, notes

    # Drop self-name edges later at resolve time using issuer_symbol
    notes["issuer"] = issuer_symbol
    return edges, notes


def extract_company_graph_from_bytes(
    data: bytes,
    *,
    title: str | None = None,
    category: str | None = None,
    symbol: str = "",
    max_pages: int = 140,
) -> GraphExtractResult:
    kind = infer_filing_kind(title=title, category=category)
    if not is_financial_filing(title=title, category=category):
        return GraphExtractResult(
            kind=kind,
            notes={"skip": "not_financial"},
        )
    if kind != "annual":
        return GraphExtractResult(
            kind=kind,
            notes={"skip": "not_annual"},
        )

    pages = extract_pdf_pages(data, max_pages=max_pages)
    if not pages:
        return GraphExtractResult(kind=kind, notes={"error": "no_text"})

    full = "\n".join(t for _, t in pages[:30])
    entity = _detect_entity(full)
    scale = _detect_scale(full)
    period = _parse_period_end(full)

    equity, label, eq_conf, eq_notes = _extract_equity(pages)
    edges, edge_notes = _extract_edges(pages, issuer_symbol=symbol)

    equity_ok = equity is not None and eq_conf in {"medium", "high"}
    relations_ok = any(e.confidence in {"medium", "high"} for e in edges)

    notes = {**eq_notes, "edges": edge_notes, "pages": len(pages)}
    return GraphExtractResult(
        kind=kind,
        entity=entity,
        scale=scale,
        currency="LKR",
        fiscal_period_end=period,
        equity=equity if equity_ok else None,
        equity_label=label if equity_ok else None,
        equity_ok=equity_ok,
        equity_confidence=eq_conf if equity_ok else "none",
        relations_ok=relations_ok,
        extract_ok=equity_ok or relations_ok or bool(edges),
        edges=edges,
        notes=notes,
    )
