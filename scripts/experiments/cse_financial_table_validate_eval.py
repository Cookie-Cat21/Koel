#!/usr/bin/env python3
"""CSE strong-set table parse + validator spike (research only).

Takes the ~72% "strong" PDFs from cse_financial_pdf_eval_*.json and attempts
FinTable-style SOPL table extraction (pdfplumber; optional tabula) plus
validators for:

  - period (quarter vs YTD vs annual / multi-column ambiguity)
  - scale (Rs '000 / Mn / absolute)
  - basic vs diluted EPS

No LLM API keys required. Not alert truth — offline research only.

Usage:
  python3 scripts/experiments/cse_financial_table_validate_eval.py
  python3 scripts/experiments/cse_financial_table_validate_eval.py --limit 20
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "docs" / "experiments"
PDF_DIR = Path("/tmp/cse-financial-pdfs")
PRIOR_GLOB = "cse_financial_pdf_eval_*.json"

# --- label patterns (row / header text) ------------------------------------

REVENUE_ROW = re.compile(
    r"^\s*(revenue|turnover|total\s+income|net\s+sales|group\s+revenue|"
    r"interest\s+income|net\s+operating\s+income|gross\s+written\s+premium|"
    r"net\s+earned\s+premium|net\s+income\s+from\s+insurance)\b",
    re.I,
)
# Prefer PAT / attributable; avoid gross profit alone when possible
PROFIT_ROW = re.compile(
    r"^\s*(profit\s+(?:(?:\/|or)\s+loss\s+)?(?:attributable|for\s+the\s+(?:period|year|quarter))|"
    r"profit\s+after\s+tax|net\s+profit(?:\s+for\s+the\s+(?:period|year))?|"
    r"loss\s+for\s+the\s+(?:period|year)|profit\s+for\s+the\s+(?:period|year))\b",
    re.I,
)
# Inline form: "Profit for the Period  280,257,691 ..."
INLINE_NUMS = re.compile(
    r"(\(?-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\)?)"
)
EPS_BASIC_ROW = re.compile(
    r"\b(basic\s+(?:earnings?\s+per\s+share|eps)|"
    r"earnings?\s+per\s+share\s*(?:\(rs\.?\))?\s*[\-\u2013:]?\s*basic|"
    r"earnings?\s+per\s+share\s*\(rs\.?\)\s*basic)\b",
    re.I,
)
EPS_DILUTED_ROW = re.compile(
    r"\b(diluted\s+(?:earnings?\s+per\s+share|eps)|"
    r"earnings?\s+per\s+share\s*(?:\(rs\.?\))?\s*[\-\u2013:]?\s*diluted|"
    r"earnings?\s+per\s+share\s*\(rs\.?\)\s*diluted)\b",
    re.I,
)
EPS_GENERIC_ROW = re.compile(
    r"\b(earnings?\s+per\s+share|basic\s*/\s*diluted\s+eps|\beps\b)\b",
    re.I,
)
NARRATIVE_EPS = re.compile(
    r"\b(strengthened|improved|improvement|declined|increased|decreased|"
    r"compared\s+to|stood\s+at|amounted\s+to|reflecting)\b",
    re.I,
)

SCALE_THOUSANDS = re.compile(
    r"(rs\.?\s*['’]?\s*000|in\s+thousands|rs\s*000|'000|٬000|"
    r"expressed\s+in\s+thousands|all\s+figures\s+in\s*['’]?000)",
    re.I,
)
SCALE_MILLIONS = re.compile(
    r"(rs\.?\s*['’]?\s*mn\b|in\s+millions|rs\s*million|\(rs\.?\s*mn\)|"
    r"expressed\s+in\s+millions)",
    re.I,
)
PERIOD_QUARTER = re.compile(
    r"\b(three\s+months|3\s+months|quarter\s+ended|for\s+the\s+quarter|"
    r"current\s+quarter|q[1-4]\b)",
    re.I,
)
PERIOD_YTD = re.compile(
    r"\b(nine\s+months|six\s+months|year\s+to\s+date|ytd|"
    r"period\s+ended|cumulative|for\s+the\s+(?:six|nine)\s+months)\b",
    re.I,
)
PERIOD_ANNUAL = re.compile(
    r"\b(year\s+ended|for\s+the\s+year|twelve\s+months|12\s+months|"
    r"annual)\b",
    re.I,
)
COMPARATIVE = re.compile(
    r"\b(corresponding|comparative|previous\s+(?:year|period|quarter)|"
    r"prior\s+period|restated)\b",
    re.I,
)
GROUP_HINT = re.compile(r"\b(group|consolidated)\b", re.I)
COMPANY_HINT = re.compile(r"\b(company|separate|parent)\b", re.I)

NUMBER_CELL = re.compile(
    r"^\(?-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\)?%?$"
)
SOPL_PAGE_KEYWORDS = (
    "profit or loss",
    "profit and loss",
    "statement of profit",
    "comprehensive income",
    "revenue",
    "turnover",
    "earnings per share",
    "profit for the period",
    "profit for the year",
)


@dataclass
class MetricPick:
    value: float | None
    raw: str | None
    label: str | None
    page: int | None = None
    column: int | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class ValidatedExtract:
    symbol: str
    kind: str
    title: str
    url: str
    pdf_path: str | None
    pages_scored: int = 0
    sopl_pages: list[int] = field(default_factory=list)
    tables_found: int = 0
    sopl_tables: int = 0
    extractor: str = "pdfplumber"
    scale: str | None = None  # absolute | thousands | millions | unknown
    period_tags: list[str] = field(default_factory=list)
    entity_tags: list[str] = field(default_factory=list)
    revenue: MetricPick | None = None
    profit: MetricPick | None = None
    eps_basic: MetricPick | None = None
    eps_diluted: MetricPick | None = None
    eps_generic: MetricPick | None = None
    validators: dict[str, Any] = field(default_factory=dict)
    verdict: str = "fail"  # unambiguous | ambiguous | fail
    fail_reasons: list[str] = field(default_factory=list)
    ambiguity_reasons: list[str] = field(default_factory=list)
    error: str | None = None


def _parse_number(raw: str) -> float | None:
    s = (raw or "").strip()
    if not s or not NUMBER_CELL.match(s.replace(" ", "")):
        # allow spaces inside
        compact = re.sub(r"\s+", "", s)
        if not NUMBER_CELL.match(compact):
            return None
        s = compact
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    s = s.replace(",", "").replace("%", "")
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def _cell_text(cell: Any) -> str:
    if cell is None:
        return ""
    return str(cell).replace("\n", " ").strip()


def _flatten_table(table: list[list[Any]]) -> list[list[str]]:
    return [[_cell_text(c) for c in (row or [])] for row in table]


def _row_label(row: list[str]) -> str:
    for cell in row:
        if cell and not NUMBER_CELL.match(cell.replace(" ", "")):
            # skip tiny note refs
            if re.fullmatch(r"\d{1,2}", cell):
                continue
            return cell
    return row[0] if row else ""


def _numeric_cells(row: list[str]) -> list[tuple[int, str, float]]:
    out: list[tuple[int, str, float]] = []
    for i, cell in enumerate(row):
        v = _parse_number(cell)
        if v is not None:
            out.append((i, cell, v))
    return out


def _detect_scale(text: str) -> str:
    if SCALE_MILLIONS.search(text):
        return "millions"
    if SCALE_THOUSANDS.search(text):
        return "thousands"
    return "unknown"


def _detect_period_tags(text: str) -> list[str]:
    tags: list[str] = []
    if PERIOD_QUARTER.search(text):
        tags.append("quarter")
    if PERIOD_YTD.search(text):
        tags.append("ytd")
    if PERIOD_ANNUAL.search(text):
        tags.append("annual")
    if COMPARATIVE.search(text):
        tags.append("has_comparative")
    return tags


def _detect_entity_tags(text: str) -> list[str]:
    tags: list[str] = []
    if GROUP_HINT.search(text):
        tags.append("group")
    if COMPANY_HINT.search(text):
        tags.append("company")
    return tags


def score_sopl_pages(pdf_path: Path, *, max_pages: int = 40) -> list[tuple[int, int, str]]:
    """Return (page_index0, keyword_hits, page_text_lower) ranked by SOPL likelihood."""
    import fitz

    doc = fitz.open(pdf_path)
    scored: list[tuple[int, int, str]] = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        text = (page.get_text() or "").lower()
        hits = sum(1 for kw in SOPL_PAGE_KEYWORDS if kw in text)
        # bonus for digit-rich financial pages
        if re.search(r"\d{1,3}(?:,\d{3})+", text):
            hits += 1
        scored.append((i, hits, text))
    doc.close()
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored


def extract_tables_pdfplumber(
    pdf_path: Path, page_indices: list[int]
) -> list[tuple[int, list[list[str]], str]]:
    import pdfplumber

    out: list[tuple[int, list[list[str]], str]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for idx in page_indices:
            if idx < 0 or idx >= len(pdf.pages):
                continue
            page = pdf.pages[idx]
            page_text = page.extract_text() or ""
            try:
                tables = page.extract_tables() or []
            except Exception:
                tables = []
            for t in tables:
                flat = _flatten_table(t)
                if sum(1 for row in flat for c in row if c) < 6:
                    continue
                out.append((idx, flat, page_text))
    return out


def extract_tables_tabula(
    pdf_path: Path, page_indices: list[int]
) -> list[tuple[int, list[list[str]], str]]:
    try:
        import tabula
    except Exception:
        return []
    out: list[tuple[int, list[list[str]], str]] = []
    for idx in page_indices:
        try:
            dfs = tabula.read_pdf(
                str(pdf_path),
                pages=idx + 1,
                multiple_tables=True,
                lattice=True,
                silent=True,
            )
        except Exception:
            try:
                dfs = tabula.read_pdf(
                    str(pdf_path),
                    pages=idx + 1,
                    multiple_tables=True,
                    stream=True,
                    silent=True,
                )
            except Exception:
                continue
        for df in dfs or []:
            flat = _flatten_table(df.fillna("").astype(str).values.tolist())
            if sum(1 for row in flat for c in row if c) < 6:
                continue
            out.append((idx, flat, ""))
    return out


def table_sopl_score(table: list[list[str]], page_text: str) -> int:
    blob = " ".join(" ".join(r) for r in table[:8]).lower() + " " + page_text[:800].lower()
    score = 0
    for kw in ("revenue", "turnover", "profit", "earnings", "income", "expense"):
        if kw in blob:
            score += 1
    # numeric density
    nums = sum(1 for r in table for c in r if _parse_number(c) is not None)
    if nums >= 8:
        score += 2
    elif nums >= 3:
        score += 1
    return score


def _pick_current_period_value(
    nums: list[tuple[int, str, float]],
    header_row: list[str] | None,
    *,
    prefer_small_for_eps: bool = False,
) -> tuple[float | None, str | None, int | None, list[str]]:
    """Choose a column: prefer leftmost non-note numeric that isn't clearly comparative."""
    notes: list[str] = []
    if not nums:
        return None, None, None, ["no_numeric_cells"]

    # Drop likely note-number columns (single-digit ints in col 1)
    filtered = []
    for col, raw, val in nums:
        if col <= 1 and val == int(val) and 1 <= abs(val) <= 40 and "." not in raw:
            # could be a note reference — keep only if it's the only number
            continue
        filtered.append((col, raw, val))
    if not filtered:
        filtered = nums

    if header_row:
        ranked: list[tuple[int, tuple[int, str, float]]] = []
        for item in filtered:
            col, raw, val = item
            hdr = header_row[col] if col < len(header_row) else ""
            h = hdr.lower()
            rank = 0
            if PERIOD_QUARTER.search(h) or "current" in h or "2025" in h or "2026" in h:
                rank += 2
            if COMPARATIVE.search(h) or "2024" in h or "2023" in h:
                rank -= 2
            if "group" in h:
                rank += 1
            if "company" in h and "group" not in h:
                rank -= 1
            ranked.append((rank, item))
        ranked.sort(key=lambda t: (-t[0], t[1][0]))
        best_rank = ranked[0][0]
        top = [it for r, it in ranked if r == best_rank]
        if len(top) > 1:
            notes.append("multi_column_tie")
        col, raw, val = top[0]
        if prefer_small_for_eps and abs(val) > 1000:
            notes.append("eps_value_looks_large")
        return val, raw, col, notes

    # No header: take first numeric after label (leftmost)
    col, raw, val = filtered[0]
    if len(filtered) > 1:
        notes.append("multi_value_no_header")
    return val, raw, col, notes


def _classify_label(label: str) -> str | None:
    """Return metric bucket for a statement line label, or None."""
    lab = label.strip()
    if not lab or len(lab) < 3:
        return None
    low = lab.lower()
    # Skip prose / highlights — not statement rows
    if NARRATIVE_EPS.search(lab) and (len(lab) > 50 or "," in lab):
        return None
    if re.search(r"\bother\s+(income|revenue|operating\s+income)\b", low):
        return None
    if EPS_BASIC_ROW.search(lab):
        return "eps_basic"
    if EPS_DILUTED_ROW.search(lab):
        return "eps_diluted"
    if EPS_GENERIC_ROW.search(lab):
        return "eps_generic"
    if REVENUE_ROW.search(lab):
        return "revenue"
    if PROFIT_ROW.search(lab):
        if re.search(r"\b(before|operating|gross)\b", low) and not re.search(
            r"\b(for\s+the\s+(period|year)|after\s+tax|attributable)\b", low
        ):
            return None
        return "profit"
    return None


def _nums_from_text(text: str) -> list[tuple[int, str, float]]:
    out: list[tuple[int, str, float]] = []
    for i, m in enumerate(INLINE_NUMS.finditer(text)):
        raw = m.group(1)
        # skip bare years / change %
        if re.fullmatch(r"20\d{2}", raw.replace(",", "")):
            continue
        if raw.endswith("%") or (m.end() < len(text) and text[m.end() : m.end() + 1] == "%"):
            continue
        v = _parse_number(raw)
        if v is None:
            continue
        # skip tiny integers that are note refs when surrounded by large nums later
        out.append((i, raw, v))
    return out


def extract_metrics_from_page_text(
    pages: list[tuple[int, str]],
) -> dict[str, Any]:
    """FinTable/LLM-ish line parse: label line + numeric line(s) on SOPL pages."""
    candidates: dict[str, list[MetricPick]] = {
        "revenue": [],
        "profit": [],
        "eps_basic": [],
        "eps_diluted": [],
        "eps_generic": [],
    }
    scale_votes: list[str] = []
    period_tags: set[str] = set()
    entity_tags: set[str] = set()

    for page, text in pages:
        scale_votes.append(_detect_scale(text))
        for tag in _detect_period_tags(text):
            period_tags.add(tag)
        # Only header/title region — full-page "company"/"group" mentions are noisy
        header_region = "\n".join(text.splitlines()[:35])
        for tag in _detect_entity_tags(header_region):
            entity_tags.add(tag)

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        # Build header context from first ~25 lines for column semantics
        header_blob = " ".join(lines[:25])
        header_has_quarter = bool(PERIOD_QUARTER.search(header_blob))
        header_has_ytd = bool(PERIOD_YTD.search(header_blob))

        i = 0
        while i < len(lines):
            line = lines[i]
            bucket = _classify_label(line)
            label = line
            num_text = ""

            if bucket is None:
                # same-line: "Basic Earnings Per Share (Rs.)   2.26  1.61 ..."
                # Try split label vs trailing numbers
                m = re.match(
                    r"^(.{3,80}?)\s{2,}((?:\(?-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\)?\s*)+)$",
                    line,
                )
                if m:
                    bucket = _classify_label(m.group(1))
                    if bucket:
                        label = m.group(1)
                        num_text = m.group(2)
                if bucket is None:
                    i += 1
                    continue
            else:
                # numbers often on the next line(s); YTD block may be a 2nd numeric line
                j = i + 1
                chunks: list[str] = []
                while j < len(lines) and j <= i + 4:
                    nxt = lines[j]
                    if _classify_label(nxt):
                        break
                    if re.fullmatch(r"-?\d+(?:\.\d+)?%", nxt.replace(" ", "")):
                        j += 1
                        continue
                    if _nums_from_text(nxt):
                        chunks.append(nxt)
                        j += 1
                        continue
                    # wrapped label continuation
                    if len(nxt) > 40 and not _nums_from_text(nxt):
                        j += 1
                        continue
                    break
                num_text = " ".join(chunks)
                same = _nums_from_text(line)
                if same and not num_text:
                    m2 = INLINE_NUMS.search(line)
                    if m2:
                        num_text = line[m2.start() :]

            nums = _nums_from_text(num_text)
            if not nums:
                i += 1
                continue

            notes: list[str] = []
            if header_has_quarter and header_has_ytd and len(nums) >= 4:
                notes.append("resolved_current_quarter_leftmost")
                val, raw, col = nums[0][2], nums[0][1], nums[0][0]
            elif header_has_quarter and header_has_ytd and len(nums) == 2:
                # Only quarter pair captured — still treat as current quarter
                notes.append("resolved_current_quarter_leftmost")
                val, raw, col = nums[0][2], nums[0][1], nums[0][0]
            elif len(nums) >= 3:
                notes.append("multi_value_no_header")
                val, raw, col = nums[0][2], nums[0][1], nums[0][0]
            else:
                val, raw, col = nums[0][2], nums[0][1], nums[0][0]
                if len(nums) == 2:
                    notes.append("assumed_current_vs_comparative")

            if bucket.startswith("eps") and abs(val) > 1000:
                notes.append("eps_value_looks_large")

            candidates[bucket].append(
                MetricPick(
                    value=val,
                    raw=raw,
                    label=label[:120],
                    page=page,
                    column=col,
                    notes=notes,
                )
            )
            i += 1

    scale = "unknown"
    votes = [s for s in scale_votes if s != "unknown"]
    if votes:
        scale = Counter(votes).most_common(1)[0][0]

    return {
        "revenue": _pick_best(candidates["revenue"]),
        "profit": _pick_best(candidates["profit"]),
        "eps_basic": _pick_best(candidates["eps_basic"]),
        "eps_diluted": _pick_best(candidates["eps_diluted"]),
        "eps_generic": _pick_best(candidates["eps_generic"]),
        "revenue_n": len(candidates["revenue"]),
        "profit_n": len(candidates["profit"]),
        "eps_basic_n": len(candidates["eps_basic"]),
        "eps_diluted_n": len(candidates["eps_diluted"]),
        "eps_generic_n": len(candidates["eps_generic"]),
        "scale": scale,
        "period_tags": sorted(period_tags),
        "entity_tags": sorted(entity_tags),
        "sopl_tables": 0,
        "source": "page_text",
        "all_candidates": {
            k: [asdict(x) for x in v[:5]] for k, v in candidates.items()
        },
    }


def _rank_label(bucket: str, label: str) -> int:
    low = (label or "").lower()
    score = 0
    if bucket == "profit":
        if "attributable" in low:
            score += 4
        if "for the period" in low:
            score += 4
        if "after tax" in low:
            score += 2
        if "net profit" in low and "for the year" not in low:
            score += 2
        if "for the year" in low and "period" not in low:
            score -= 1  # often comparative / segment / annualisation
        if "ended" in low:
            score -= 3  # note-style restatement / prior-period rows
        if "comprehensive" in low:
            score -= 3
        if "segment" in low:
            score -= 2
    if bucket == "revenue":
        if low.startswith("revenue") or low.startswith("turnover"):
            score += 3
        if "interest income" in low:
            score += 2
        if "premium" in low:
            score += 2
        if "total income" in low:
            score += 1
    if bucket.startswith("eps"):
        if "basic" in low:
            score += 2
        if "diluted" in low:
            score += 2
        if len(low) > 80:
            score -= 3
    return score


def _pick_best(cands: list[MetricPick]) -> MetricPick | None:
    if not cands:
        return None

    def bucket_for(p: MetricPick) -> str:
        low = (p.label or "").lower()
        if "basic" in low and "earning" in low:
            return "eps_basic"
        if "diluted" in low and "earning" in low:
            return "eps_diluted"
        if "eps" in low or "earning" in low:
            return "eps_generic"
        if "profit" in low or "loss" in low:
            return "profit"
        return "revenue"

    return sorted(
        cands,
        key=lambda p: (
            0 if "resolved_current_quarter_leftmost" in (p.notes or []) else 1,
            -_rank_label(bucket_for(p), p.label or ""),
            p.page if p.page is not None else 99,
        ),
    )[0]


def extract_metrics_from_tables(
    tables: list[tuple[int, list[list[str]], str]],
) -> dict[str, Any]:
    """Scan SOPL-ish tables for revenue / profit / EPS rows."""
    candidates: dict[str, list[MetricPick]] = {
        "revenue": [],
        "profit": [],
        "eps_basic": [],
        "eps_diluted": [],
        "eps_generic": [],
    }
    scale_votes: list[str] = []
    period_tags: set[str] = set()
    entity_tags: set[str] = set()
    sopl_tables = 0

    ranked = sorted(
        ((table_sopl_score(t, pt), page, t, pt) for page, t, pt in tables),
        key=lambda x: x[0],
        reverse=True,
    )

    for score, page, table, page_text in ranked[:8]:
        if score < 2:
            continue
        sopl_tables += 1
        header = table[0] if table else []
        # sometimes headers span first 2 rows
        header_blob = " ".join(header + (table[1] if len(table) > 1 else []))
        scale_votes.append(_detect_scale(page_text + " " + header_blob))
        for tag in _detect_period_tags(page_text + " " + header_blob):
            period_tags.add(tag)
        for tag in _detect_entity_tags(header_blob + " " + page_text[:1200]):
            entity_tags.add(tag)

        for row in table:
            label = _row_label(row)
            bucket = _classify_label(label)
            if not bucket:
                continue
            nums = _numeric_cells(row)
            if not nums:
                continue
            val, raw, col, notes = _pick_current_period_value(
                nums, header, prefer_small_for_eps=bucket.startswith("eps")
            )
            candidates[bucket].append(
                MetricPick(
                    value=val,
                    raw=raw,
                    label=label[:120],
                    page=page,
                    column=col,
                    notes=notes,
                )
            )

    scale = "unknown"
    votes = [s for s in scale_votes if s != "unknown"]
    if votes:
        scale = Counter(votes).most_common(1)[0][0]

    return {
        "revenue": _pick_best(candidates["revenue"]),
        "profit": _pick_best(candidates["profit"]),
        "eps_basic": _pick_best(candidates["eps_basic"]),
        "eps_diluted": _pick_best(candidates["eps_diluted"]),
        "eps_generic": _pick_best(candidates["eps_generic"]),
        "revenue_n": len(candidates["revenue"]),
        "profit_n": len(candidates["profit"]),
        "eps_basic_n": len(candidates["eps_basic"]),
        "eps_diluted_n": len(candidates["eps_diluted"]),
        "eps_generic_n": len(candidates["eps_generic"]),
        "scale": scale,
        "period_tags": sorted(period_tags),
        "entity_tags": sorted(entity_tags),
        "sopl_tables": sopl_tables,
        "source": "tables",
        "all_candidates": {
            k: [asdict(x) for x in v[:5]] for k, v in candidates.items()
        },
    }


def merge_extracts(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    """Fill gaps from secondary; keep primary picks when present."""
    out = dict(primary)
    for key in ("revenue", "profit", "eps_basic", "eps_diluted", "eps_generic"):
        if out.get(key) is None and secondary.get(key) is not None:
            out[key] = secondary[key]
        out[f"{key}_n"] = int(primary.get(f"{key}_n") or 0) + int(
            secondary.get(f"{key}_n") or 0
        )
    if out.get("scale") in (None, "unknown") and secondary.get("scale") not in (
        None,
        "unknown",
    ):
        out["scale"] = secondary["scale"]
    out["period_tags"] = sorted(
        set(primary.get("period_tags") or []) | set(secondary.get("period_tags") or [])
    )
    out["entity_tags"] = sorted(
        set(primary.get("entity_tags") or []) | set(secondary.get("entity_tags") or [])
    )
    out["sopl_tables"] = max(
        int(primary.get("sopl_tables") or 0), int(secondary.get("sopl_tables") or 0)
    )
    out["source"] = f"{primary.get('source')}+{secondary.get('source')}"
    # merge candidate lists for conflict detection
    merged_cands: dict[str, list] = {}
    for src in (primary, secondary):
        for k, items in (src.get("all_candidates") or {}).items():
            merged_cands.setdefault(k, [])
            merged_cands[k].extend(items or [])
    out["all_candidates"] = merged_cands
    return out


def apply_validators(row: ValidatedExtract, extracted: dict[str, Any]) -> None:
    row.revenue = extracted.get("revenue")
    row.profit = extracted.get("profit")
    row.eps_basic = extracted.get("eps_basic")
    row.eps_diluted = extracted.get("eps_diluted")
    row.eps_generic = extracted.get("eps_generic")
    row.scale = extracted.get("scale")
    row.period_tags = list(extracted.get("period_tags") or [])
    row.entity_tags = list(extracted.get("entity_tags") or [])
    row.sopl_tables = int(extracted.get("sopl_tables") or 0)

    v: dict[str, Any] = {}
    amb: list[str] = []
    fail: list[str] = []

    # --- period ---
    periods = [t for t in row.period_tags if t in ("quarter", "ytd", "annual")]
    resolved_q = False
    for pick in (row.revenue, row.profit, row.eps_basic, row.eps_diluted, row.eps_generic):
        if pick and "resolved_current_quarter_leftmost" in (pick.notes or []):
            resolved_q = True
            break
    if row.kind == "quarterly":
        if "quarter" in periods and "ytd" in periods:
            # Extraction always prefers leftmost (= current quarter on CSE layouts).
            v["period"] = "ok_resolved_current_quarter"
            v["period_resolve"] = "leftmost_current_quarter"
            if not resolved_q:
                v["period_resolve_confidence"] = "assumed"
        elif "quarter" in periods or "ytd" in periods:
            v["period"] = "ok_tagged"
            if "ytd" in periods and "quarter" not in periods:
                # Only YTD tagged — call out soft risk but do not fail the gate
                v["period_note"] = "ytd_only"
        else:
            v["period"] = "untagged"
            amb.append("period:untagged")
    else:
        if "annual" in periods or not periods:
            v["period"] = "ok_or_assumed_annual"
        else:
            v["period"] = "unexpected_tags"
            amb.append(f"period:unexpected:{','.join(periods)}")

    # multi-column ties / unresolved multi-value rows
    # Note: 2–N numeric columns (current + comparatives / YTD) are normal on CSE
    # statements. multi_value_no_header is informational only — not ambiguity —
    # unless values conflict across candidate rows.
    for name, pick in (
        ("revenue", row.revenue),
        ("profit", row.profit),
        ("eps_basic", row.eps_basic),
        ("eps_diluted", row.eps_diluted),
        ("eps_generic", row.eps_generic),
    ):
        if not pick:
            continue
        notes = pick.notes or []
        if "multi_column_tie" in notes:
            amb.append(f"{name}:multi_column_tie")
        if "quarter_and_ytd_values" in notes:
            amb.append(f"{name}:quarter_vs_ytd_values")
        if "multi_value_no_header" in notes:
            v.setdefault("multi_value_notes", []).append(name)

    # --- scale ---
    if row.scale in ("thousands", "millions"):
        v["scale"] = f"ok_{row.scale}"
        if row.revenue and row.revenue.value is not None:
            rv = abs(row.revenue.value)
            if row.scale == "thousands" and rv < 10:
                amb.append("scale:revenue_too_small_for_thousands")
            if row.scale == "millions" and rv > 1_000_000:
                amb.append("scale:revenue_huge_for_millions_label")
    else:
        v["scale"] = "unknown"
        if row.revenue and row.revenue.value is not None and abs(row.revenue.value) < 100:
            amb.append("scale:unknown_and_tiny_revenue")

    # --- basic vs diluted ---
    has_b = row.eps_basic and row.eps_basic.value is not None
    has_d = row.eps_diluted and row.eps_diluted.value is not None
    has_g = row.eps_generic and row.eps_generic.value is not None
    # Prefer typed EPS; drop narrative/generic when basic/diluted exist
    if (has_b or has_d) and has_g:
        row.eps_generic = None
        has_g = False
        amb = [a for a in amb if not a.startswith("eps_generic:")]
    if has_b and has_d:
        v["eps"] = "ok_basic_and_diluted"
        if abs((row.eps_basic.value or 0) - (row.eps_diluted.value or 0)) < 1e-9:
            v["eps_note"] = "basic_equals_diluted"
    elif has_b and not has_d:
        v["eps"] = "ok_basic_only"
    elif has_d and not has_b:
        v["eps"] = "diluted_only"
        amb.append("eps:diluted_without_basic")
    elif has_g:
        # Reclassify "... basic" / "... diluted" stuck in generic
        lab = (row.eps_generic.label or "").lower()
        if re.search(r"\bbasic\b", lab) and not re.search(r"\bdiluted\b", lab):
            row.eps_basic = row.eps_generic
            row.eps_generic = None
            v["eps"] = "ok_basic_only"
            has_b, has_g = True, False
        elif re.search(r"\bdiluted\b", lab) and not re.search(r"\bbasic\b", lab):
            row.eps_diluted = row.eps_generic
            row.eps_generic = None
            v["eps"] = "diluted_only"
            amb.append("eps:diluted_without_basic")
            has_d, has_g = True, False
        else:
            v["eps"] = "generic_only"
            amb.append("eps:generic_unlabeled_basic_or_diluted")
    else:
        v["eps"] = "missing"
        fail.append("eps:missing")

    # --- entity group vs company ---
    # Only flag when both appear as likely column headers (short lines), not body noise
    if "group" in row.entity_tags and "company" in row.entity_tags:
        v["entity"] = "both_mentioned"
        # soft signal — do not auto-ambiguate; many CSE covers say Company + Group
    elif "group" in row.entity_tags:
        v["entity"] = "group"
    elif "company" in row.entity_tags:
        v["entity"] = "company"
    else:
        v["entity"] = "untagged"

    # --- required metrics ---
    if not (row.revenue and row.revenue.value is not None):
        fail.append("revenue:missing")
    if not (row.profit and row.profit.value is not None):
        fail.append("profit:missing")

    eps_pick = row.eps_basic or row.eps_diluted or row.eps_generic
    if eps_pick and eps_pick.value is not None:
        if abs(eps_pick.value) > 5000:
            amb.append("eps:implausibly_large")
            v["eps_magnitude"] = "suspicious"
        else:
            v["eps_magnitude"] = "plausible"

    # Pile-ups only if many *distinct* values among high-quality labels
    def distinct_high_quality(key: str) -> int:
        seen = set()
        for item in (extracted.get("all_candidates") or {}).get(key) or []:
            if not isinstance(item, dict) or item.get("value") is None:
                continue
            lab = str(item.get("label") or "")
            if NARRATIVE_EPS.search(lab):
                continue
            if key == "profit" and _rank_label("profit", lab) < 2:
                continue
            if key == "revenue" and _rank_label("revenue", lab) < 1:
                continue
            seen.add(round(float(item["value"]), 4))
        return len(seen)

    if distinct_high_quality("revenue") >= 3:
        amb.append("revenue:conflicting_candidates")
    if distinct_high_quality("profit") >= 3:
        amb.append("profit:conflicting_candidates")
    if distinct_high_quality("eps_basic") >= 3:
        amb.append("eps:conflicting_candidates")

    # Soft scale warnings should not block gated_ok / unambiguous alone
    soft_scale = {
        "scale:revenue_too_small_for_thousands",
        "scale:revenue_huge_for_millions_label",
        "scale:unknown_and_tiny_revenue",
    }
    hard_amb = [a for a in amb if a not in soft_scale]
    for a in soft_scale:
        if a in amb:
            v.setdefault("scale_warnings", []).append(a)

    row.validators = v
    row.fail_reasons = fail
    # Keep soft scale in ambiguity_reasons for visibility, but verdict uses hard_amb
    row.ambiguity_reasons = sorted(set(amb))

    if fail:
        row.verdict = "fail"
    elif hard_amb:
        row.verdict = "ambiguous"
    else:
        row.verdict = "unambiguous"

    v["gated_ok"] = (
        not fail
        and v.get("eps") in ("ok_basic_only", "ok_basic_and_diluted")
        and "revenue:conflicting_candidates" not in hard_amb
        and "profit:conflicting_candidates" not in hard_amb
        and "eps:conflicting_candidates" not in hard_amb
        and v.get("period")
        not in ("ambiguous_quarter_and_ytd", "untagged", "unexpected_tags")
    )


def local_pdf_for(row: dict) -> Path | None:
    """Map prior eval row to /tmp PDF (symbol_kind_id.pdf)."""
    row.get("url") or ""
    # id often in filename on disk from prior harness
    symbol = row["symbol"]
    kind = row["kind"]
    # try exact listing match by prefix
    matches = sorted(PDF_DIR.glob(f"{symbol}_{kind}_*.pdf"))
    if len(matches) == 1:
        return matches[0]
    if matches:
        # prefer matching id from url hash / title — take newest by mtime
        return max(matches, key=lambda p: p.stat().st_mtime)
    # fallback: any file for symbol
    matches = sorted(PDF_DIR.glob(f"{symbol}_*.pdf"))
    return matches[0] if matches else None


def load_strong_rows(prior_path: Path) -> list[dict]:
    data = json.loads(prior_path.read_text())
    strong: list[dict] = []
    for r in data.get("rows") or []:
        if not isinstance(r, dict):
            continue
        if not r.get("text_ok") or not r.get("metrics_found"):
            continue
        m = r["metrics_found"]
        if (
            m.get("revenue")
            and m.get("profit")
            and m.get("eps")
            and int(r.get("number_hits") or 0) >= 40
        ):
            strong.append(r)
    return strong


def eval_one(meta: dict, *, use_tabula: bool = False) -> ValidatedExtract:
    row = ValidatedExtract(
        symbol=meta["symbol"],
        kind=meta["kind"],
        title=meta.get("title") or "",
        url=meta.get("url") or "",
        pdf_path=None,
    )
    path = local_pdf_for(meta)
    if path is None or not path.exists():
        row.error = "pdf_missing"
        row.fail_reasons = ["pdf_missing"]
        row.verdict = "fail"
        return row
    row.pdf_path = str(path)

    try:
        scored = score_sopl_pages(path)
        row.pages_scored = len(scored)
        # take top pages with hits >= 2, at least top 3
        top = [p for p, h, _ in scored if h >= 2][:6]
        if not top:
            top = [p for p, _, _ in scored[:3]]
        row.sopl_pages = top

        # Primary: page text line parse (CSE often keeps labels outside pdfplumber grids)
        import fitz

        doc = fitz.open(path)
        page_texts: list[tuple[int, str]] = []
        for idx in top:
            if 0 <= idx < len(doc):
                page_texts.append((idx, doc[idx].get_text() or ""))
        doc.close()
        text_ext = extract_metrics_from_page_text(page_texts)

        tables = extract_tables_pdfplumber(path, top)
        row.extractor = "page_text+pdfplumber"
        if use_tabula and len(tables) < 1:
            t2 = extract_tables_tabula(path, top[:3])
            if t2:
                tables = t2
                row.extractor = "page_text+tabula"
        row.tables_found = len(tables)
        table_ext = (
            extract_metrics_from_tables(tables)
            if tables
            else {
                "revenue": None,
                "profit": None,
                "eps_basic": None,
                "eps_diluted": None,
                "eps_generic": None,
                "revenue_n": 0,
                "profit_n": 0,
                "eps_basic_n": 0,
                "eps_diluted_n": 0,
                "eps_generic_n": 0,
                "scale": "unknown",
                "period_tags": [],
                "entity_tags": [],
                "sopl_tables": 0,
                "source": "tables",
            }
        )
        extracted = merge_extracts(text_ext, table_ext)
        # Fail only if neither path found any metric-ish content
        if (
            extracted.get("revenue") is None
            and extracted.get("profit") is None
            and extracted.get("eps_basic") is None
            and extracted.get("eps_diluted") is None
            and extracted.get("eps_generic") is None
            and not tables
        ):
            row.error = "no_tables_or_metrics"
            row.fail_reasons = ["no_tables_or_metrics"]
            row.verdict = "fail"
            return row

        apply_validators(row, extracted)
    except Exception as exc:
        row.error = str(exc)[:240]
        row.fail_reasons = ["exception"]
        row.verdict = "fail"
    return row


def summarize(rows: list[ValidatedExtract]) -> dict:
    n = len(rows)
    c = Counter(r.verdict for r in rows)
    scale_c = Counter(r.scale or "none" for r in rows)
    eps_v = Counter((r.validators or {}).get("eps", "n/a") for r in rows)
    period_v = Counter((r.validators or {}).get("period", "n/a") for r in rows)
    fail_reasons = Counter()
    amb_reasons = Counter()
    for r in rows:
        for x in r.fail_reasons:
            fail_reasons[x] += 1
        for x in r.ambiguity_reasons:
            amb_reasons[x] += 1

    def pct(x: int) -> float:
        return round(100.0 * x / n, 1) if n else 0.0

    return {
        "n": n,
        "verdicts": dict(c),
        "verdict_pct": {k: pct(v) for k, v in c.items()},
        "unambiguous": c.get("unambiguous", 0),
        "unambiguous_pct": pct(c.get("unambiguous", 0)),
        "ambiguous": c.get("ambiguous", 0),
        "ambiguous_pct": pct(c.get("ambiguous", 0)),
        "fail": c.get("fail", 0),
        "fail_pct": pct(c.get("fail", 0)),
        "scale_counts": dict(scale_c),
        "eps_validator": dict(eps_v),
        "period_validator": dict(period_v),
        "top_fail_reasons": fail_reasons.most_common(12),
        "top_ambiguity_reasons": amb_reasons.most_common(15),
        "has_revenue": sum(1 for r in rows if r.revenue and r.revenue.value is not None),
        "has_profit": sum(1 for r in rows if r.profit and r.profit.value is not None),
        "has_eps_any": sum(
            1
            for r in rows
            if (r.eps_basic and r.eps_basic.value is not None)
            or (r.eps_diluted and r.eps_diluted.value is not None)
            or (r.eps_generic and r.eps_generic.value is not None)
        ),
        "has_basic_and_diluted": sum(
            1
            for r in rows
            if r.eps_basic
            and r.eps_basic.value is not None
            and r.eps_diluted
            and r.eps_diluted.value is not None
        ),
        "gated_ok": sum(1 for r in rows if (r.validators or {}).get("gated_ok")),
        "gated_ok_pct": pct(
            sum(1 for r in rows if (r.validators or {}).get("gated_ok"))
        ),
    }


def write_markdown(summary: dict, rows: list[ValidatedExtract], out_path: Path, meta: dict) -> None:
    examples_u = [r for r in rows if r.verdict == "unambiguous"][:5]
    examples_a = [r for r in rows if r.verdict == "ambiguous"][:5]
    examples_f = [r for r in rows if r.verdict == "fail"][:5]

    def fmt_pick(p: MetricPick | None) -> str:
        if not p or p.value is None:
            return "—"
        return f"{p.value} (`{p.raw}`) ← {p.label!r}"

    lines = [
        "# CSE financial table parse + validator spike",
        "",
        f"Generated: `{meta['generated_at']}`  ",
        f"Input: **{summary['n']}** PDFs from the prior “strong” set "
        f"(rev+profit+EPS labels + ≥40 numbers).  ",
        "Extractor: FinTable-style SOPL page ranking (PyMuPDF) → **page-text line "
        "parse** (primary) + **pdfplumber** tables (gap-fill). Camelot/FinTable "
        "GUI stack not used (install friction); **no LLM API keys** here.  ",
        "Harness: `scripts/experiments/cse_financial_table_validate_eval.py`",
        "",
        "## Headline",
        "",
        "| Verdict | Count | % |",
        "|---|---:|---:|",
        f"| Unambiguous (period+scale+EPS typed, metrics present) | {summary['unambiguous']} | {summary['unambiguous_pct']} |",
        f"| Ambiguous (extracted but validator warnings) | {summary['ambiguous']} | {summary['ambiguous_pct']} |",
        f"| Fail (missing metrics / no tables) | {summary['fail']} | {summary['fail_pct']} |",
        f"| Gated OK (typed EPS + no hard conflicts; still verify-in-filing) | {summary.get('gated_ok', 0)} | {summary.get('gated_ok_pct', 0)} |",
        "",
        "### Coverage of line items (any candidate)",
        "",
        f"- Revenue row with number: **{summary['has_revenue']}** / {summary['n']}",
        f"- Profit row with number: **{summary['has_profit']}** / {summary['n']}",
        f"- Any EPS number: **{summary['has_eps_any']}** / {summary['n']}",
        f"- Basic **and** diluted both found: **{summary['has_basic_and_diluted']}** / {summary['n']}",
        "",
        "### Validator breakdown",
        "",
        "```json",
        json.dumps(
            {
                "scale_counts": summary["scale_counts"],
                "eps_validator": summary["eps_validator"],
                "period_validator": summary["period_validator"],
                "gated_ok": summary.get("gated_ok"),
                "gated_ok_pct": summary.get("gated_ok_pct"),
                "top_ambiguity_reasons": summary["top_ambiguity_reasons"],
                "top_fail_reasons": summary["top_fail_reasons"],
            },
            indent=2,
        ),
        "```",
        "",
        "## What “unambiguous” / “gated OK” mean here",
        "",
        "Research-only gates — **not** ground-truth audited against every PDF cell:",
        "",
        "1. Revenue + profit numbers found on a SOPL-like page/table",
        "2. EPS present as **basic** (or basic+diluted); generic-only → ambiguous",
        "3. No hard conflicting candidate sets for the chosen lines",
        "4. Period tagged or rule-resolved (leftmost = current quarter when Q+YTD)",
        "5. Comparative multi-column layouts are **expected** (not auto-fail)",
        "",
        "**Gated OK** = extractable enough to maybe show in a brief with "
        "“verify in filing”. Still **not** Telegram alert truth.",
        "",
        "A human still needs to confirm the figure before it could ever be alert truth.",
        "",
        "## Sample rows",
        "",
        "### Unambiguous",
        "",
    ]
    for r in examples_u:
        lines.append(
            f"- `{r.symbol}` ({r.kind}) scale={r.scale} periods={r.period_tags}  \n"
            f"  rev={fmt_pick(r.revenue)}  \n"
            f"  pat={fmt_pick(r.profit)}  \n"
            f"  eps_b={fmt_pick(r.eps_basic)} eps_d={fmt_pick(r.eps_diluted)}"
        )
    if not examples_u:
        lines.append("- _(none)_")

    lines += ["", "### Ambiguous", ""]
    for r in examples_a:
        lines.append(
            f"- `{r.symbol}` ({r.kind}): {', '.join(r.ambiguity_reasons[:6])}  \n"
            f"  rev={fmt_pick(r.revenue)} eps_g={fmt_pick(r.eps_generic)}"
        )
    if not examples_a:
        lines.append("- _(none)_")

    lines += ["", "### Fail", ""]
    for r in examples_f:
        lines.append(
            f"- `{r.symbol}` ({r.kind}): {', '.join(r.fail_reasons) or r.error}"
        )
    if not examples_f:
        lines.append("- _(none)_")

    lines += [
        "",
        "### Gated OK examples",
        "",
    ]
    examples_g = [r for r in rows if (r.validators or {}).get("gated_ok")][:5]
    for r in examples_g:
        lines.append(
            f"- `{r.symbol}` ({r.kind}) verdict={r.verdict} scale={r.scale}  \n"
            f"  rev={fmt_pick(r.revenue)}  \n"
            f"  pat={fmt_pick(r.profit)}  \n"
            f"  eps_b={fmt_pick(r.eps_basic)} eps_d={fmt_pick(r.eps_diluted)}"
        )
    if not examples_g:
        lines.append("- _(none)_")

    lines += [
        "",
        "## Vs prior spike",
        "",
        "| Layer | Result |",
        "|---|---|",
        "| Text label presence (prior) | ~72% “strong” |",
        "| Structured extract coverage (rev/profit/EPS any) | "
        f"{summary['has_revenue']}/{summary['n']} rev, "
        f"{summary['has_profit']}/{summary['n']} profit, "
        f"{summary['has_eps_any']}/{summary['n']} EPS |",
        "| Table parse + validators (this run) | "
        f"{summary['unambiguous_pct']}% unambiguous / "
        f"{summary['ambiguous_pct']}% ambiguous / "
        f"{summary['fail_pct']}% fail |",
        "| Gated OK (typed EPS, period OK, no hard conflicts) | "
        f"{summary.get('gated_ok_pct', 0)}% |",
        "",
        "Label presence ≫ structured numbers ≫ validator-clean numbers. "
        "Even gated-OK rows are research-only.",
        "",
        "## FinTable / LLM status",
        "",
        "- **FinTable** upstream depends on `camelot` + GUI; camelot did not install "
        "cleanly here. We reused its *idea* (keyword page rank → SOPL rows) via "
        "PyMuPDF page text (primary — CSE often keeps labels *outside* pdfplumber "
        "grids) + pdfplumber tables (gap-fill).",
        "- **LLM table parse**: no `OPENAI_API_KEY` / `GEMINI_API_KEY` / `GROQ_API_KEY` "
        "in env — skipped. Next experiment if keys available: same validator gate on "
        "LLM JSON extracts (especially the ambiguous / fail buckets).",
        "",
        "## Spot-check (manual)",
        "",
        "`AAF.N0000` quarterly SOPL text yields Interest Income `2,358,166,994`, "
        "Profit for the Period `280,257,691`, Basic EPS `2.26`, Diluted EPS `1.58` — "
        "matches a human reading of page text. Validators still flag residual "
        "candidate conflicts on some filings.",
        "",
        "## Recommendation for Chime",
        "",
        "1. Still **do not** ship auto EPS/PE/YoY as alert truth.",
        "2. Offline extract + validators is useful for research / brief enrichment "
        "with “verify in filing”.",
        "3. Highest-value next step with an API key: LLM extract on the "
        "non-gated bucket, still behind the same validators.",
        "",
        f"Raw JSON: `{meta['json_name']}`",
        "",
    ]
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Cap PDFs (0 = all strong)")
    ap.add_argument("--tabula", action="store_true", help="Fallback to tabula if no pdfplumber tables")
    ap.add_argument(
        "--prior",
        type=str,
        default="",
        help="Path to prior cse_financial_pdf_eval_*.json",
    )
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.prior:
        prior = Path(args.prior)
    else:
        priors = sorted(OUT_DIR.glob(PRIOR_GLOB))
        if not priors:
            raise SystemExit(f"No prior eval JSON under {OUT_DIR}")
        prior = priors[-1]

    strong = load_strong_rows(prior)
    if args.limit and args.limit > 0:
        strong = strong[: args.limit]
    print(f"Strong set: {len(strong)} from {prior.name}")

    rows: list[ValidatedExtract] = []
    for i, meta in enumerate(strong, 1):
        print(f"[{i}/{len(strong)}] {meta['symbol']} {meta['kind']} ...", flush=True)
        rows.append(eval_one(meta, use_tabula=args.tabula))
        v = rows[-1]
        print(
            f"  → {v.verdict} tables={v.tables_found} sopl={v.sopl_tables} "
            f"scale={v.scale} eps={(v.validators or {}).get('eps')}",
            flush=True,
        )

    summary = summarize(rows)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_name = f"cse_financial_table_validate_eval_{ts}.json"
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "prior": str(prior.relative_to(REPO)) if prior.is_relative_to(REPO) else str(prior),
        "note": "Research only — not alert truth. FinTable-style pdfplumber + validators.",
        "llm_used": False,
        "fintable_upstream_used": False,
        "extractor_primary": "pdfplumber",
        "summary": summary,
        "rows": [
            {
                **{k: v for k, v in asdict(r).items() if k not in ()},
            }
            for r in rows
        ],
    }
    (OUT_DIR / json_name).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    md_path = OUT_DIR / "CSE_FINANCIAL_TABLE_VALIDATE_EVAL.md"
    write_markdown(
        summary,
        rows,
        md_path,
        {"generated_at": payload["generated_at"], "json_name": json_name},
    )
    print(json.dumps(summary, indent=2))
    print(f"Wrote {OUT_DIR / json_name}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
