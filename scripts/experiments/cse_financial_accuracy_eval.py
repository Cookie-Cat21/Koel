#!/usr/bin/env python3
"""CSE financial extract accuracy spike — iterate toward ≥99% verified.

Research only (not alert truth). Builds on the strong-set PDFs and measures
*verified* accuracy: each picked (label → value) must be confirmable by
adjacency in the PDF page text.

Usage:
  python3 scripts/experiments/cse_financial_accuracy_eval.py
  python3 scripts/experiments/cse_financial_accuracy_eval.py --target 0.99
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

# ---------------------------------------------------------------------------
# Patterns — deliberately broad for CSE (banks, insurers, takaful, hotels)
# ---------------------------------------------------------------------------

REVENUE_LABEL = re.compile(
    r"^\s*("
    r"revenue(?:\s+from\s+contracts\s+with\s+customers)?|"
    r"net\s+revenue|gross\s+revenue|gross\s+income|turnover|net\s+sales|"
    r"total\s+(?:net\s+)?revenue|total\s+income|total\s+operating\s+income|"
    r"net\s+interest\s+income|interest\s+income|financing\s+income|net\s+financing\s+income|"
    r"net\s+rental\s+income|direct\s+income|net\s+trading\s+income|"
    r"gross\s+written\s+premiums?|"
    r"net\s+(?:written|earned)\s+premiums?|"
    r"gross\s+written\s+contribution(?:\s*\(premium\))?|"
    r"net\s+earned\s+contribution(?:\s*\(premium\))?|"
    r"net\s+operating\s+income|net\s+income(?!\s+from)"
    r")\b",
    re.I,
)
# Skip these as primary revenue
REVENUE_SKIP = re.compile(
    r"\b(other\s+(?:operating\s+)?(?:income|revenue)|revenue\s+taxes?|"
    r"revenue\s+reserve|revaluation|"
    r"premiums?\s+ceded|retakaful|reinsurance|deferred\s+revenue|"
    r"inter\s+segment\s+revenue|external\s+revenue)\b",
    re.I,
)

PROFIT_LABEL = re.compile(
    r"^\s*("
    r"(?:basic\s+)?profit\s*(?:\(\s*/?\s*loss\s*\)|/\s*\(?\s*loss\s*\)?)?\s+for\s+the\s+(?:period|year|quarter)|"
    r"loss\s+for\s+the\s+(?:period|year|quarter)|"
    r"net\s+profit\s*(?:\(\s*/?\s*loss\s*\)|/\s*\(?\s*loss\s*\)?)?\s+for\s+the\s+(?:period|year)|"
    r"net\s+profit\s+for\s+the\s+(?:period|year)|"
    r"net\s+profit\s*/\s*\(?\s*loss\s*\)?|"
    r"profit\s*/\s*\(?\s*loss\s*\)?\s+for\s+the\s+(?:period|year)|"
    r"profit\s*/\s*\(?\s*loss\s*\)?\s+after\s+(?:income\s+)?tax(?:ation)?|"
    r"profit\s*\(\s*/?\s*loss\s*\)\s+after\s+(?:income\s+)?tax(?:ation)?|"
    r"profit\s*/\s*\(?\s*loss\s*\)?\s+after\s+tax|"
    r"group\s+profit\s+after\s+tax|"
    r"profit\s+after\s+tax(?:ation)?|"
    r"profit\s+before\s+tax(?:ation)?|"  # last-resort; ranked lower via before-tax skip unless needed
    r"profit\s*(?:\(\s*/?\s*loss\s*\)|/\s*\(?\s*loss\s*\)?)?\s+attributable|"
    r"profit\s+attributable\s+to"
    r")\b",
    re.I,
)
PROFIT_SKIP = re.compile(
    r"\b(from\s+operations|operating\s+profit|gross\s+profit|"
    r"comprehensive|share\s+of\s+profit|discontinu)\b",
    re.I,
)
# Soft demote (still allowed) — used in ranking, not hard skip
PROFIT_BEFORE_TAX = re.compile(r"\bbefore\s+tax", re.I)

# NOTE: optional "(loss)" must be a full optional group — do NOT require the word "loss".
EPS_BASIC = re.compile(
    r"^\s*("
    r"basic\s+(?:and\s+diluted\s+)?earnings?(?:\s*/\s*\(?\s*loss\s*\)?)?\s+per\s+(?:ordinary\s+)?share|"
    r"basic\s+(?:and\s+diluted\s+)?(?:loss|earning)\s+per\s+(?:ordinary\s+)?share|"
    r"basic\s+loss\s+per\s+share|"
    r"basic\s*,?\s*profit\s*/?\s*\(?\s*loss\s*\)?\s+for\s+the\s+year|"  # ASCO note style
    r"basic\s+eps|"
    r"basic\s+\(loss\)/\s*earning\s+per\s+share|"
    r"earnings?(?:\s*/\s*\(?\s*loss\s*\)?)?\s+per\s+(?:ordinary\s+)?share\s*(?:\(rs\.?\))?\s*[\-\u2013:]?\s*basic|"
    r"weighted\s+average\s+earnings?\s+per\s+share|"
    r"earnings?\s+per\s+share\s*\(rs\.?\)\s*basic|"
    r"earnings?\s+per\s+(?:ordinary\s+)?share\s*[\-\u2013:]?\s*basic|"
    r"earnings?\s+per\s+ordinary\s+share|"
    r"basic\s+earnings?/\s*\(?\s*loss\s*\)?\s+per\s+share|"
    r"loss\s+per\s+share|"
    r"earning\s+per\s+share"  # ACME typo singular
    r")",
    re.I,
)
EPS_DILUTED = re.compile(
    r"^\s*("
    r"diluted\s+earnings?(?:\s*/\s*\(?\s*loss\s*\)?)?\s+per\s+(?:ordinary\s+)?share|"
    r"diluted\s+eps|"
    r"earnings?(?:\s*/\s*\(?\s*loss\s*\)?)?\s+per\s+share\s*(?:\(rs\.?\))?\s*[\-\u2013:]?\s*diluted|"
    r"earnings?\s+per\s+share\s*\(rs\.?\)\s*diluted|"
    r"diluted\s+and\s+basic\s+earnings?"
    r")",
    re.I,
)
EPS_COMBINED = re.compile(
    r"("
    r"basic\s*/\s*di[a-z]*lut[a-z]*ed|"  # diluted + Dialuted typo
    r"basic\s+and\s+di[a-z]*lut[a-z]*ed|"
    r"diluted\s+and\s+basic|"
    r"earnings?\s+per\s+share\s*[\-\u2013:]?\s*.{0,20}basic\s*/\s*di|"
    r"\(loss\)/earnings\s+per\s+share\s*basic\s*/\s*diluted"
    r")",
    re.I,
)
EPS_GENERIC = re.compile(
    r"^\s*("
    r"earnings?(?:\s*/\s*\(?\s*loss\s*\)?)?\s+per\s+(?:ordinary\s+)?share|"
    r"earning\s+per\s+share|"
    r"earnings?\s+per\s+share|"
    r"loss\s+per\s+share|"
    r"\(loss\)/earnings\s+per\s+share|"
    r"(?<![a-z])eps(?![a-z])"
    r")",
    re.I,
)

EPS_SKIP = re.compile(
    r"\b(annualised|annualized|graph\s*[–\-]|\(usd\)|usd\)|"
    r"before\s+sub-?division)\b",
    re.I,
)

SCALE_THOUSANDS = re.compile(
    r"(rs\.?\s*['’]?\s*000|in\s+thousands|rs\s*['’]?000|expressed\s+in\s+thousands|"
    r"rs\s*['’]\s*000)",
    re.I,
)
SCALE_MILLIONS = re.compile(
    r"(rs\.?\s*['’]?\s*mn\b|in\s+millions|rs\s*million|\(rs\.?\s*mn\))",
    re.I,
)
PERIOD_QUARTER = re.compile(
    r"\b(three\s+months|3\s+months|quarter\s+ended|for\s+the\s+quarter|"
    r"for\s+the\s+three\s+months)\b",
    re.I,
)
PERIOD_YTD = re.compile(
    r"\b(nine\s+months|six\s+months|year\s+to\s+date|"
    r"for\s+the\s+(?:six|nine)\s+months)\b",
    re.I,
)
PERIOD_ANNUAL = re.compile(
    r"\b(year\s+ended|for\s+the\s+year|twelve\s+months|annual)\b",
    re.I,
)
INLINE_NUM = re.compile(
    r"(\(?-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\)?)"
)
NOTE_ONLY = re.compile(r"^\d{1,2}$")
PCT_ONLY = re.compile(r"^-?\d+(?:\.\d+)?%$")
NARRATIVE = re.compile(
    r"\b(strengthened|improved|improvement|declined|increased|decreased|"
    r"compared\s+to|stood\s+at|amounted\s+to|reflecting|reported\s+a)\b",
    re.I,
)
SOPL_KEYWORDS = (
    "statement of profit",
    "profit or loss",
    "income statement",
    "comprehensive income",
    "earnings per share",
    "profit for the period",
    "profit for the year",
    "gross written",
    "interest income",
    "financing income",
    "net revenue",
)


@dataclass
class Pick:
    value: float
    raw: str
    label: str
    page: int
    verified: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass
class FilingResult:
    symbol: str
    kind: str
    title: str
    url: str
    pdf_path: str | None
    scale: str = "unknown"
    period: str = "unknown"
    revenue: Pick | None = None
    profit: Pick | None = None
    eps_basic: Pick | None = None
    eps_diluted: Pick | None = None
    verified_metrics: int = 0
    required_ok: bool = False  # rev+profit+eps_basic all verified
    fail_reasons: list[str] = field(default_factory=list)
    error: str | None = None


def _normalize_pdf_text(text: str) -> str:
    """Normalize common PDF ligatures / odd spaces so label regexes match."""
    if not text:
        return text
    return (
        text.replace("\ufb01", "fi")
        .replace("\ufb02", "fl")
        .replace("ﬁ", "fi")
        .replace("ﬂ", "fl")
        .replace("\xa0", " ")
    )


def _parse_num(raw: str) -> float | None:
    s = (raw or "").strip()
    if not s:
        return None
    # Broken table cells like "-3-" / "3-" are not EPS values
    if re.fullmatch(r"-?\d+-", s):
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace(",", "").replace("%", "")
    # Trailing dash remnants
    s = s.strip("-")
    if not s or s in {".", "-", "–", "—"}:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def _nums_in(text: str) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    for m in INLINE_NUM.finditer(text):
        raw = m.group(1)
        bare = raw.strip().strip("()")
        # skip years (incl. "(Restated – 2025)" capturing "2025)")
        if re.fullmatch(r"20\d{2}", bare.replace(",", "")):
            continue
        # skip if followed by % 
        end = m.end()
        if end < len(text) and text[end : end + 1] == "%":
            continue
        # Broken cells like "-3-" where INLINE_NUM only captured "-3"
        if end < len(text) and text[end : end + 1] == "-" and re.fullmatch(
            r"-?\d+", raw.replace(",", "")
        ):
            continue
        v = _parse_num(raw)
        if v is None:
            continue
        out.append((raw, v))
    return out


def _classify(line: str) -> str | None:
    lab = line.strip()
    if not lab or len(lab) < 3:
        return None
    if NARRATIVE.search(lab) and len(lab) > 50:
        return None
    low = lab.lower()
    # Note-section / formula blurbs — not the SOPL value row
    if re.match(r"^\d{1,2}\s+basic\b", low):
        return None
    if "is calculated by dividing" in low or "weighted average number" in low:
        return None
    if "is calculated by" in low and "earning" in low:
        return None
    if re.search(r"presents?\s+basic\s+and\s+diluted", low):
        return None
    if len(lab) > 120 and re.search(r"per\s+share|eps", low):
        return None
    # Bare continuation tag
    if re.fullmatch(r"\(?\s*basic\s*/\s*diluted\s*\)?", low):
        return "eps_combined_tag"
    if re.fullmatch(r"[\-\u2013—]?\s*basic\b.*", low) and "earning" not in low and "share" not in low and "loss" not in low:
        return "eps_basic_tag"
    # Continuation row: "- Basic Earnings Per Share"
    if re.match(r"^[\-\u2013—]\s*basic\b.*(earning|share)", low):
        if "dilut" in low:
            return "eps_combined"
        return "eps_basic"
    if re.fullmatch(r"[\-\u2013—]?\s*diluted\b.*", low) and "earning" not in low and "share" not in low:
        return "eps_diluted_tag"
    # Skip annualized / continuing-ops / USD EPS lines as primary picks
    if EPS_SKIP.search(lab) and re.search(r"per\s+share|eps", lab, re.I):
        return None
    if EPS_BASIC.search(lab):
        return "eps_basic"
    if EPS_DILUTED.search(lab):
        return "eps_diluted"
    if EPS_COMBINED.search(lab) and ("earning" in low or "eps" in low or "per share" in low or "loss" in low):
        return "eps_combined"
    if EPS_GENERIC.search(lab):
        return "eps_generic"
    if REVENUE_SKIP.search(lab):
        return None
    if REVENUE_LABEL.search(lab):
        return "revenue"
    if PROFIT_SKIP.search(lab) and not re.search(
        r"\b(for\s+the\s+(period|year)|after\s+tax|attributable)\b", lab, re.I
    ):
        return None
    if PROFIT_LABEL.search(lab):
        return "profit"
    return None


def _is_leading_note_or_toc_token(raw: str, v: float) -> bool:
    """True for CSE note-column / TOC tokens that often precede the real EPS."""
    t = raw.strip().strip("()")
    if not t:
        return False
    # Parenthetical small ints are note refs: |(10)|0.78|0.73
    if re.fullmatch(r"\(\d{1,2}\)", raw.strip()) and v == int(v) and 1 <= abs(v) <= 40:
        return True
    # Parenthetical / negative values otherwise are never note refs.
    if raw.strip().startswith("(") or v < 0:
        return False
    # Bare note numbers (Notes column): 5, 10, 38
    if re.fullmatch(r"\d{1,2}", t) and v == int(v) and 1 <= abs(v) <= 40:
        return True
    # Subsection note refs with *one* decimal place: 8.1, 10.3, 38.1
    # (Real EPS like 3.55 / 9.16 have two+ decimals and are kept.)
    if re.fullmatch(r"\d{1,2}\.\d", t):
        return True
    # TOC / contents page numbers (e.g. "EPS .... 253")
    if re.fullmatch(r"\d{2,3}", t) and v == int(v) and 50 <= abs(v) <= 450:
        return True
    return False


def _is_prose_or_address_line(nxt: str) -> bool:
    """True for narrative/address lines that must not supply EPS numbers."""
    if re.search(
        r"located at|mawatha|registered office|incorporated and domiciled|"
        r"colombo\s+\d+|authorised for issue|board of directors|"
        r"accounting standards|interim financial",
        nxt,
        re.I,
    ):
        return True
    # Long sentence-like lines (not a pure number row)
    if len(nxt) > 70 and not re.fullmatch(r"[\d\s.,()/\-%RsLKR'’]+", nxt):
        wordish = len(re.findall(r"[A-Za-z]{3,}", nxt))
        if wordish >= 6:
            return True
    return False


def _collect_preceding_eps_nums(
    lines: list[str], i: int
) -> list[tuple[str, float]]:
    """CSE notes often print EPS values *above* the label row.

    Only accept EPS-shaped values (decimal and/or signed paren loss). Bare
    integers are almost always note refs when they sit above the label.
    """
    for back in range(1, 4):
        if i - back < 0:
            break
        prev = lines[i - back].strip()
        if not prev or _is_prose_or_address_line(prev):
            continue
        if _classify(prev):
            break
        found = _nums_in(prev)
        if not found:
            continue
        usable: list[tuple[str, float]] = []
        for raw, v in found:
            if _is_leading_note_or_toc_token(raw, v):
                continue
            if abs(v) > 500:
                continue
            # Preceding-only: require a decimal (3.47) or paren loss ((0.14)).
            # Bare ints above a label are note columns (CHMX 27, CDB 22, PACK 20).
            if "." not in raw and not raw.strip().startswith("("):
                continue
            usable.append((raw, v))
        if usable:
            return usable
    return []


def _collect_following_nums(
    lines: list[str], i: int, *, eps_mode: bool = False
) -> list[tuple[str, float]]:
    """Gather numeric values after label; skip note refs and % rows."""
    nums: list[tuple[str, float]] = []
    same = _nums_in(lines[i])
    if same:
        nums.extend(same)

    j = i + 1
    empty_streak = 0
    hit_prose = False
    while j < len(lines) and j <= i + (14 if not eps_mode else 8):
        nxt = lines[j].strip()
        if not nxt:
            empty_streak += 1
            if empty_streak > 1:
                break
            j += 1
            continue
        empty_streak = 0
        if eps_mode and _is_prose_or_address_line(nxt):
            hit_prose = True
            break
        cls = _classify(nxt)
        if cls and cls not in (
            "eps_combined_tag",
            "eps_basic_tag",
            "eps_diluted_tag",
        ):
            break
        if cls in ("eps_combined_tag", "eps_basic_tag", "eps_diluted_tag"):
            j += 1
            continue
        if PCT_ONLY.match(nxt.replace(" ", "")):
            j += 1
            continue
        if NOTE_ONLY.match(nxt):
            j += 1
            continue
        if re.search(r"basic\s*/\s*diluted", nxt, re.I) and not _nums_in(nxt):
            j += 1
            continue
        # Skip parenthetical annotations between label and numbers
        if re.fullmatch(r"\([^)]{1,40}\)", nxt) and not _nums_in(nxt):
            j += 1
            continue
        if re.fullmatch(r"annualised|annualized|unaudited|audited|restated", nxt, re.I):
            j += 1
            continue
        if re.fullmatch(r"rs\.?|lkr|usd|rs\.?\s*['’]?\s*000", nxt, re.I):
            j += 1
            continue
        if re.match(
            r"figures in brackets|the above figures|provisional and subject",
            nxt,
            re.I,
        ):
            j += 1
            continue
        if re.fullmatch(r"group|company|note|notes|total|rs\.?['’]?000", nxt, re.I):
            j += 1
            continue
        if nxt in {"-", "–", "—"}:
            j += 1
            continue
        found = _nums_in(nxt)
        if found:
            for raw, v in found:
                # Non-EPS: skip lone note ints
                if (
                    not eps_mode
                    and raw.replace(",", "").isdigit()
                    and v == int(v)
                    and 1 <= abs(v) <= 40
                    and len(found) == 1
                ):
                    continue
                # EPS: drop street-number-like bare integers (BIL: "481, T B Jayah…")
                if (
                    eps_mode
                    and v == int(v)
                    and abs(v) >= 100
                    and "." not in raw
                ):
                    continue
                nums.append((raw, v))
            j += 1
            if eps_mode:
                # Strip leading note/TOC tokens when a real EPS follows
                # (AAF: 38.1 note → 3.55 / 2.77). Keep scanning while only notes seen.
                while len(nums) >= 2 and _is_leading_note_or_toc_token(
                    nums[0][0], nums[0][1]
                ):
                    nums = nums[1:]
                if not nums:
                    continue
                # Note-like single (38.1 / 10 / 253): peek further lines before committing.
                if _is_leading_note_or_toc_token(nums[0][0], nums[0][1]):
                    continue
                break
            continue
        break

    cleaned: list[tuple[str, float]] = []
    for raw, v in nums:
        if eps_mode and abs(v) > 5000:
            continue
        if eps_mode and abs(v) > 500 and v == int(v) and "." not in raw:
            continue
        if (
            not eps_mode
            and raw.replace(",", "").isdigit()
            and v == int(v)
            and 1 <= abs(v) <= 40
        ):
            continue
        cleaned.append((raw, v))
    if eps_mode:
        while len(cleaned) >= 2 and _is_leading_note_or_toc_token(
            cleaned[0][0], cleaned[0][1]
        ):
            cleaned = cleaned[1:]
        # Drop sole note/TOC token — never treat note refs as EPS by themselves
        # (HUNT: "Basic/Diluted | 10.1" note with no numeric EPS on the page).
        if len(cleaned) == 1 and _is_leading_note_or_toc_token(
            cleaned[0][0], cleaned[0][1]
        ):
            cleaned = []
        if not cleaned:
            cleaned = _collect_preceding_eps_nums(lines, i)
        return cleaned
    return cleaned or nums


def _verify_adjacency(page_text: str, label: str, raw: str) -> bool:
    """Confirm label and raw number appear near each other on the page."""
    if not page_text or not label or not raw:
        return False
    # normalize whitespace
    text = re.sub(r"[ \t]+", " ", page_text)
    lab = re.escape(label[:80].strip())
    num = re.escape(raw.strip())
    # label then number within ~250 chars (allows note lines / newlines)
    pat = re.compile(lab + r".{0,250}?" + num, re.I | re.S)
    if pat.search(text):
        return True
    # number then label (CSE notes often print values above the EPS row)
    pat_rev = re.compile(num + r".{0,250}?" + lab, re.I | re.S)
    if pat_rev.search(text):
        return True
    # sometimes number then repeated label — also try compact lines
    lines = [ln.strip() for ln in page_text.splitlines()]
    for i, ln in enumerate(lines):
        if label[:40].lower() in ln.lower() or ln.lower() == label.lower():
            window = " ".join(lines[i : i + 5])
            if raw in window:
                return True
    return False


def score_pages(pdf_path: Path, *, max_pages: int | None = None) -> list[tuple[int, int, str]]:
    import fitz

    doc = fitz.open(pdf_path)
    n = len(doc) if max_pages is None else min(len(doc), max_pages)
    scored: list[tuple[int, int, str]] = []
    toc_hints: list[int] = []
    # Pass 1: TOC / contents page-number hints from early pages
    for i in range(min(20, len(doc))):
        text = doc[i].get_text() or ""
        for m in re.finditer(
            r"(?:statement\s+of\s+profit[^\n]{0,60}?|profit\s+or\s+loss[^\n]{0,40}?)"
            r"(?:\.{2,}|\s{2,}|\t+)(\d{1,3})\b",
            text,
            re.I,
        ):
            toc_hints.append(int(m.group(1)))
        for m in re.finditer(
            r"\b(\d{2,3})\s+statement\s+of\s+profit",
            text,
            re.I,
        ):
            toc_hints.append(int(m.group(1)))

    for i in range(n):
        text = doc[i].get_text() or ""
        low = text.lower()
        hits = sum(1 for kw in SOPL_KEYWORDS if kw in low)
        if re.search(r"\d{1,3}(?:,\d{3})+", text):
            hits += 1
        # boost real statements with both revenue-ish and EPS
        if ("revenue" in low or "turnover" in low or "interest income" in low) and (
            "per share" in low or "profit for the" in low
        ):
            hits += 3
        if "statement of profit" in low and len(text) > 1500:
            hits += 4
        scored.append((i, hits, text))

    # Also pull TOC-hinted pages (printed page ≈ index or index-1)
    for hint in toc_hints:
        for cand in (hint, hint - 1, hint + 1):
            if 0 <= cand < len(doc):
                # ensure present
                if not any(p == cand for p, _, _ in scored):
                    text = doc[cand].get_text() or ""
                    scored.append((cand, 5, text))
                else:
                    # boost
                    scored = [
                        (p, h + (8 if p == cand else 0), t) for p, h, t in scored
                    ]
    doc.close()
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored


def _stitch_broken_parens(lines: list[str]) -> list[str]:
    """Join CSE layouts where '(' and '825,505)' are split across lines."""
    out: list[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        if ln == "(" and i + 1 < len(lines):
            nxt = lines[i + 1].strip()
            if re.match(r"^-?\d", nxt) or nxt.endswith(")"):
                out.append(f"({nxt}" if not nxt.startswith("(") else nxt)
                i += 2
                continue
        out.append(lines[i])
        i += 1
    return out


def extract_from_pages(
    pages: list[tuple[int, str]], *, kind: str
) -> dict[str, Any]:
    cands: dict[str, list[Pick]] = {
        "revenue": [],
        "profit": [],
        "eps_basic": [],
        "eps_diluted": [],
        "eps_generic": [],
        "eps_combined": [],
    }
    scale_votes: list[str] = []
    period_tags: set[str] = set()
    page_is_sopl: dict[int, bool] = {}
    page_is_quarter: dict[int, bool] = {}
    page_is_ytd: dict[int, bool] = {}
    page_is_group: dict[int, bool] = {}
    page_is_company_only: dict[int, bool] = {}
    page_is_analysis: dict[int, bool] = {}
    page_has_period_profit: dict[int, bool] = {}
    page_has_year_profit_only: dict[int, bool] = {}
    page_is_highlights: dict[int, bool] = {}
    page_is_usd: dict[int, bool] = {}

    for page, text in pages:
        text = _normalize_pdf_text(text)
        low_page = text.lower()
        head = "\n".join(text.splitlines()[:25]).lower()
        # Notes / restatement schedules often mention SOPL phrases — require a
        # real statement shape (revenue + EPS), not just the words.
        head25 = "\n".join(text.splitlines()[:25]).lower()
        notes_band = bool(
            re.search(
                r"notes?\s+to\s+the\s+financial|as\s+previously\s+reported|"
                r"cumulative\s+impact\s+of\s+adjustments|restated\s+balance|"
                r"corporate\s+information|basis\s+of\s+preparation",
                head25,
            )
        )
        page_is_usd[page] = bool(
            re.search(
                r"indicative\s+us\s*dollar|us\s*dollar\s+income|"
                r"income\s+statement\s+in\s+usd|\(usd\)|in\s+us\s*dollars",
                head25,
            )
        )
        # USD / indicative dollar statements are not primary LKR SOPL
        page_is_sopl[page] = (not notes_band) and (not page_is_usd[page]) and (
            "statement of profit" in low_page
            or "income statement" in low_page
            or (
                "profit or loss" in low_page
                and "earnings per share" in low_page
                and bool(
                    re.search(
                        r"\brevenue\b|\bturnover\b|interest\s+income|"
                        r"gross\s+income|gross\s+written",
                        low_page,
                    )
                )
                and len(text) > 1200
            )
        )
        # Prefer explicit quarter headers in the *title band*, not footnotes
        # Also treat "for the quarter" as a quarter page signal
        page_is_quarter[page] = bool(
            re.search(
                r"for\s+the\s+(?:three\s+months|quarter)\s+ended|three\s+months\s+ended|"
                r"profit\s+for\s+the\s+quarter|loss\s+for\s+the\s+quarter",
                head,
            )
        ) or bool(
            re.search(r"profit\s+for\s+the\s+quarter|loss\s+for\s+the\s+quarter", low_page)
        )
        page_is_ytd[page] = bool(
            re.search(
                r"for\s+the\s+(?:period|six\s+months|nine\s+months|year)\s+ended|"
                r"nine\s+months\s+ended|six\s+months\s+ended",
                head,
            )
        ) and not page_is_quarter[page]
        page_is_group[page] = bool(re.search(r"\bgroup\b", head))
        page_is_company_only[page] = bool(
            re.search(r"\bcompany\b", head)
        ) and not page_is_group[page]
        # Quarterly analysis / highlights / TOC — not the primary SOPL EPS source
        page_is_analysis[page] = bool(
            re.search(
                r"quarterly\s+analysis|segment\s+information|"
                r"financial\s+highlights|table\s+of\s+contents|"
                r"^\s*contents\b",
                head,
                re.M,
            )
        ) and not page_is_sopl[page]
        page_has_period_profit[page] = bool(
            re.search(r"profit\s+for\s+the\s+period|loss\s+for\s+the\s+period", low_page, re.I)
        )
        page_is_highlights[page] = bool(
            re.search(r"price\s+earnings|earnings\s+yield|earnings\s+highlights", low_page, re.I)
        ) and not (
            "statement of profit" in low_page
            and re.search(r"revenue|turnover|interest income", low_page)
            and len(text) > 2000
        )
        scale_votes.append(
            "millions"
            if SCALE_MILLIONS.search(text)
            else "thousands"
            if SCALE_THOUSANDS.search(text)
            else "unknown"
        )
        if PERIOD_QUARTER.search(text):
            period_tags.add("quarter")
        if PERIOD_YTD.search(text):
            period_tags.add("ytd")
        if PERIOD_ANNUAL.search(text):
            period_tags.add("annual")

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        lines = _stitch_broken_parens(lines)
        header = " ".join(lines[:30])
        has_q = bool(PERIOD_QUARTER.search(header))
        has_ytd = bool(PERIOD_YTD.search(header))

        i = 0
        while i < len(lines):
            bucket = _classify(lines[i])
            if bucket is None or bucket in (
                "eps_combined_tag",
                "eps_basic_tag",
                "eps_diluted_tag",
            ):
                i += 1
                continue
            label = lines[i]
            collect_idx = i
            # Merge "Earnings Per Share" + next "Basic / Diluted" / full basic line.
            # Values sit under the typed row — never preceding-fill the bare header
            # (CIC/HNB/COMB: header above Basic picked prior-year / note junk).
            if bucket == "eps_generic" and i + 1 < len(lines):
                nxt = lines[i + 1]
                tag = _classify(nxt)
                if tag in ("eps_basic_tag", "eps_basic"):
                    bucket = "eps_basic"
                    label = f"{lines[i]} {nxt}".strip()
                    collect_idx = i + 1
                elif tag in ("eps_diluted_tag", "eps_diluted"):
                    bucket = "eps_diluted"
                    label = f"{lines[i]} {nxt}".strip()
                    collect_idx = i + 1
                elif tag in ("eps_combined", "eps_combined_tag") or re.search(
                    r"basic\s*/\s*di|basic\s+and\s+di", nxt, re.I
                ):
                    bucket = "eps_combined"
                    label = f"{label} {nxt}".strip()
                    collect_idx = i + 1
            if bucket in ("eps_generic", "eps_combined", "eps_basic", "eps_diluted") and i + 2 < len(lines):
                for k in (i + 1, i + 2):
                    if re.search(r"basic\s*/\s*di|basic\s+and\s+di", lines[k], re.I):
                        bucket = "eps_combined"
                        label = f"{label} {lines[k]}".strip()
                        collect_idx = max(collect_idx, k)
                        break
                    tag = _classify(lines[k])
                    if tag in ("eps_basic_tag", "eps_basic") and bucket in (
                        "eps_generic",
                        "eps_combined",
                    ):
                        bucket = "eps_basic"
                        label = f"{lines[i]} {lines[k]}".strip()
                        collect_idx = max(collect_idx, k)
                        break
                    if tag in ("eps_diluted_tag", "eps_diluted") and bucket in (
                        "eps_generic",
                        "eps_combined",
                    ):
                        bucket = "eps_diluted"
                        label = f"{lines[i]} {lines[k]}".strip()
                        collect_idx = max(collect_idx, k)
                        break

            nums = _collect_following_nums(
                lines, collect_idx, eps_mode=bucket.startswith("eps")
            )
            # When header+typed row merged but typed row had no nums, try header
            # only if collect_idx moved (avoid double preceding junk on header).
            if not nums and collect_idx != i and bucket.startswith("eps"):
                nums = _collect_following_nums(lines, i, eps_mode=True)
                # Header preceding-fill is untrusted when a typed row exists
                if nums and collect_idx != i:
                    # Keep only same-line nums from the header itself
                    same = _nums_in(lines[i])
                    nums = same if same else []
            if not nums and bucket.startswith("eps") and collect_idx + 1 < len(lines):
                nums = _collect_following_nums(
                    lines, collect_idx + 1, eps_mode=True
                )
            if not nums:
                i += 1
                continue

            notes: list[str] = []
            if has_q and has_ytd and len(nums) >= 2:
                notes.append("resolved_current_quarter_leftmost")
            if page_is_sopl.get(page):
                notes.append("on_sopl_page")
            if page_is_quarter.get(page):
                notes.append("on_quarter_page")
            if page_is_ytd.get(page):
                notes.append("on_ytd_page")
            if page_is_group.get(page):
                notes.append("on_group_page")
            if page_is_company_only.get(page):
                notes.append("on_company_only_page")
            if page_is_analysis.get(page):
                notes.append("on_analysis_page")
            if page_has_period_profit.get(page):
                notes.append("page_has_period_profit")
            if page_has_year_profit_only.get(page):
                notes.append("page_has_year_profit_only")
            if page_is_highlights.get(page):
                notes.append("on_highlights_page")
            if page_is_usd.get(page):
                notes.append("on_usd_page")
            raw, val = nums[0]
            if bucket.startswith("eps") and abs(val) > 5000:
                i += 1
                continue
            if raw in ("-", "–", "—"):
                i += 1
                continue

            pick = Pick(
                value=val,
                raw=raw,
                label=label[:140],
                page=page,
                notes=notes,
            )
            # Verify against original label line (not merged) when needed
            verify_label = lines[i][:80]
            pick.verified = _verify_adjacency(text, verify_label, raw)
            if not pick.verified:
                # softer: raw appears within 5 lines after label
                for ln in lines[i : i + 6]:
                    if raw in ln:
                        pick.verified = True
                        pick.notes.append("verified_nearby_line")
                        break
            cands[bucket].append(pick)
            i += 1

    def rank_revenue(p: Pick) -> tuple:
        low = p.label.lower()
        score = 0
        if "on_sopl_page" in p.notes:
            score += 10
        if kind == "quarterly":
            if "on_quarter_page" in p.notes:
                score += 12
            if "on_ytd_page" in p.notes:
                score -= 8
        if "on_group_page" in p.notes:
            score += 4
        if "on_company_only_page" in p.notes:
            score -= 3
        if "resolved_current_quarter_leftmost" in p.notes:
            score += 5
        if low.startswith("interest income") or low.startswith("financing income"):
            score += 6
        if low.startswith("gross income"):
            score += 6
        if (low.startswith("revenue") or low.startswith("turnover")) and "total" not in low:
            score += 6
        if "from contracts" in low:
            score += 6
        if "gross written" in low or "net earned" in low:
            score += 6
        if "total" in low and "revenue" in low:
            score += 1
        if p.verified:
            score += 1
        return (-score, p.page)

    def rank_profit(p: Pick) -> tuple:
        low = p.label.lower()
        score = 0
        if "on_sopl_page" in p.notes:
            score += 10
        if kind == "quarterly":
            if "on_quarter_page" in p.notes:
                score += 12
            if "on_ytd_page" in p.notes:
                score -= 8
        if "on_group_page" in p.notes:
            score += 4
        if "on_company_only_page" in p.notes:
            score -= 3
        if "resolved_current_quarter_leftmost" in p.notes:
            score += 5
        if "attributable" in low:
            score += 4
        if "for the period" in low:
            score += 5
        elif "for the year" in low:
            score += 2
        if "after tax" in low or "after taxation" in low:
            score += 6
        if "before tax" in low or "before taxation" in low:
            score -= 10
        if low.startswith("net profit"):
            score += 1
        if "ended" in low:
            score -= 4
        if "for the year" in low and kind == "quarterly":
            score -= 8
        if p.verified:
            score += 1
        return (-score, p.page)

    def rank_eps(p: Pick) -> tuple:
        score = 0
        low = (p.label or "").lower()
        if "on_sopl_page" in p.notes:
            score += 15
        if "on_analysis_page" in p.notes:
            score -= 25
        if "on_highlights_page" in p.notes:
            score -= 20
        if "on_usd_page" in p.notes:
            score -= 40
        if kind == "quarterly":
            if "on_quarter_page" in p.notes:
                score += 12
            if "on_ytd_page" in p.notes:
                score -= 18
            if "page_has_period_profit" in p.notes:
                score += 14
            if "page_has_year_profit_only" in p.notes:
                score -= 20
            # Strongly prefer the current-quarter statement when present
            if re.search(r"for the quarter|three months", (p.label or ""), re.I):
                score += 8
            low_notes = " ".join(p.notes)
            if "on_quarter_page" in p.notes and "on_ytd_page" not in p.notes:
                score += 8
        if "on_group_page" in p.notes:
            score += 4
        if "on_company_only_page" in p.notes:
            score -= 3
        if "resolved_current_quarter_leftmost" in p.notes:
            score += 3
        # Prefer period EPS over annualized; prefer total over continuing-only
        if "for the period" in low:
            score += 6
        if kind == "quarterly" and ("for the year" in low or "year ended" in low):
            score -= 12
        if "annualised" in low or "annualized" in low:
            score -= 20
        if "continuing" in low or "discontinued" in low:
            score -= 10
        if "(usd)" in low or low.endswith("usd"):
            score -= 15
        if "restated" in low:
            score -= 2
        if "basic / diluted" in low or "basic and diluted" in low or "basic/diluted" in low:
            score += 3
        if "after sub-division" in low or "after subdivision" in low:
            score += 5
        if "after share" in low:  # CALH: after share subdivision
            score += 8
        if "before sub-division" in low or "before subdivision" in low:
            score -= 15
        if re.search(r"before\s*$", low) or "per share before" in low:
            score -= 12
        if "restated" in low:
            score -= 2
        if "price earnings" in low or "earnings yield" in low:
            score -= 6
        if p.verified:
            score += 1
        # Prefer earlier rows on the same page (Group usually listed before Company)
        return (-score, p.page)

    def best(bucket: str, key) -> Pick | None:
        items = cands.get(bucket) or []
        if not items:
            return None
        return sorted(items, key=key)[0]

    revenue = best("revenue", rank_revenue)
    profit = best("profit", rank_profit)
    eps_basic = best("eps_basic", rank_eps)
    eps_diluted = best("eps_diluted", rank_eps)
    eps_combined = best("eps_combined", rank_eps)
    eps_generic = best("eps_generic", rank_eps)

    def _on_sopl(p: Pick | None) -> bool:
        return bool(p and "on_sopl_page" in p.notes)

    def _promote(src: Pick, tag: str) -> Pick:
        return Pick(
            value=src.value,
            raw=src.raw,
            label=src.label,
            page=src.page,
            verified=src.verified,
            notes=list(src.notes) + [tag],
        )

    # Prefer SOPL combined / "diluted and basic" over non-SOPL "basic" hits
    # (ALUM: quarterly-analysis (1.45) vs SOPL Diluted and Basic 1.45).
    if eps_basic is not None and not _on_sopl(eps_basic):
        for alt, tag in (
            (eps_combined, "replaced_nonssopl_from_combined"),
            (eps_diluted, "replaced_nonssopl_from_diluted_and_basic"),
            (eps_generic, "replaced_nonssopl_from_generic"),
        ):
            if not _on_sopl(alt):
                continue
            low = (alt.label or "").lower()
            if alt is eps_diluted and "basic" not in low and "combined" not in low:
                continue
            eps_basic = _promote(alt, tag)
            break

    # Prefer current-quarter EPS page over year-to-date statement (MELS etc.)
    if (
        kind == "quarterly"
        and eps_basic is not None
        and "on_ytd_page" in eps_basic.notes
    ):
        for alt, tag in (
            (eps_combined, "replaced_ytd_from_combined_quarter"),
            (eps_basic, "noop"),
            (eps_generic, "replaced_ytd_from_generic_quarter"),
            (eps_diluted, "replaced_ytd_from_diluted_quarter"),
        ):
            if tag == "noop" or alt is None:
                continue
            if "on_ytd_page" in alt.notes:
                continue
            if "on_quarter_page" not in alt.notes and "page_has_period_profit" not in alt.notes:
                continue
            eps_basic = _promote(alt, tag)
            break
    # Also consider other eps_basic candidates on quarter pages via re-best
    if kind == "quarterly" and eps_basic is not None and "on_ytd_page" in eps_basic.notes:
        quarter_basics = [
            p
            for p in (cands.get("eps_basic") or [])
            if "on_ytd_page" not in p.notes
            and ("on_quarter_page" in p.notes or "page_has_period_profit" in p.notes)
        ]
        if quarter_basics:
            eps_basic = sorted(quarter_basics, key=rank_eps)[0]
        for alt, tag in (
            (eps_combined, "replaced_highlights_from_combined"),
            (eps_diluted, "replaced_highlights_from_diluted"),
            (eps_generic, "replaced_highlights_from_generic"),
        ):
            if alt is None:
                continue
            if "on_highlights_page" in alt.notes:
                continue
            if not _on_sopl(alt):
                continue
            eps_basic = _promote(alt, tag)
            break

    # Promote combined / generic → basic when typed basic missing
    if eps_basic is None and eps_combined is not None:
        eps_basic = _promote(eps_combined, "promoted_from_combined")
        if eps_diluted is None:
            eps_diluted = _promote(eps_combined, "same_as_basic_combined")
    if eps_basic is None and eps_diluted is not None:
        low = (eps_diluted.label or "").lower()
        if "and basic" in low or "basic" in low:
            eps_basic = _promote(eps_diluted, "promoted_from_diluted_and_basic")
    if eps_basic is None and eps_generic is not None:
        eps_basic = _promote(eps_generic, "promoted_from_generic")

    scale = "unknown"
    votes = [s for s in scale_votes if s != "unknown"]
    if votes:
        scale = Counter(votes).most_common(1)[0][0]

    if kind == "quarterly":
        if "quarter" in period_tags or "ytd" in period_tags:
            period = "ok_resolved_current_quarter"
        else:
            period = "untagged"
    else:
        period = "ok_or_assumed_annual"

    return {
        "revenue": revenue,
        "profit": profit,
        "eps_basic": eps_basic,
        "eps_diluted": eps_diluted,
        "scale": scale,
        "period": period,
        "cand_counts": {k: len(v) for k, v in cands.items()},
    }


def local_pdf_for(row: dict) -> Path | None:
    if row.get("pdf_path"):
        p = Path(row["pdf_path"])
        if p.exists():
            return p
    symbol, kind = row["symbol"], row["kind"]
    matches = sorted(PDF_DIR.glob(f"{symbol}_{kind}_*.pdf"))
    if matches:
        return max(matches, key=lambda p: p.stat().st_mtime)
    matches = sorted(PDF_DIR.glob(f"{symbol}_*.pdf"))
    return matches[0] if matches else None


def load_strong_rows(prior_path: Path) -> list[dict]:
    data = json.loads(prior_path.read_text())
    strong: list[dict] = []
    seen: set[str] = set()
    for r in data.get("rows") or []:
        if not isinstance(r, dict) or not r.get("text_ok") or not r.get("metrics_found"):
            continue
        m = r["metrics_found"]
        if not (
            m.get("revenue")
            and m.get("profit")
            and m.get("eps")
            and int(r.get("number_hits") or 0) >= 40
        ):
            continue
        # One filing per symbol+kind (local PDFs often collide across URL variants)
        key = f"{r['symbol']}|{r['kind']}"
        if key in seen:
            continue
        seen.add(key)
        strong.append(r)
    return strong


def eval_one(meta: dict) -> FilingResult:
    row = FilingResult(
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
        return row
    row.pdf_path = str(path)
    try:
        # Annuals: scan full PDF (CSE annuals bury SOPL past page 200)
        max_pages = None if meta["kind"] == "annual" else 50
        scored = score_pages(path, max_pages=max_pages)
        # Prefer high-scoring SOPL pages, but always keep any page that
        # actually contains an EPS / revenue / profit label row.
        budget = 40 if meta["kind"] == "annual" else 20
        top_idx = [p for p, h, _ in scored if h >= 2][:budget]
        if len(top_idx) < 4:
            top_idx = [p for p, _, _ in scored[:10]]
        text_by_page = {p: t for p, _, t in scored}
        # Force-include EPS label pages (highlights + notes often score low)
        eps_page_re = re.compile(
            r"earnings?\s+per\s+share|earning\s+per\s+share|loss\s+per\s+share|"
            r"basic\s+and\s+diluted|basic\s+eps",
            re.I,
        )
        for p, h, t in scored:
            if p in top_idx:
                continue
            if eps_page_re.search(t or ""):
                top_idx.append(p)
            if len(top_idx) >= budget + 25:
                break
        pages = [(i, text_by_page[i]) for i in top_idx if i in text_by_page]
        for p, h, t in scored[:12]:
            if p not in {i for i, _ in pages}:
                pages.append((p, t))

        extracted = extract_from_pages(pages, kind=meta["kind"])
        row.scale = extracted["scale"]
        row.period = extracted["period"]
        row.revenue = extracted["revenue"]
        row.profit = extracted["profit"]
        row.eps_basic = extracted["eps_basic"]
        row.eps_diluted = extracted["eps_diluted"]

        fails: list[str] = []
        verified = 0
        for name, pick in (
            ("revenue", row.revenue),
            ("profit", row.profit),
            ("eps_basic", row.eps_basic),
        ):
            if pick is None:
                fails.append(f"{name}:missing")
            elif not pick.verified:
                fails.append(f"{name}:unverified")
            else:
                verified += 1
        row.verified_metrics = verified
        row.fail_reasons = fails
        row.required_ok = verified == 3 and not fails
    except Exception as exc:
        row.error = str(exc)[:240]
        row.fail_reasons = ["exception"]
    return row


def score_gold(gold_path: Path) -> dict:
    gold = json.loads(gold_path.read_text())
    hits = 0
    rows_out = []
    for g in gold:
        r = eval_one(g)
        ok = bool(r.eps_basic and abs(r.eps_basic.value - float(g["eps_basic"])) < 0.05)
        if g.get("revenue") is not None:
            ok = ok and bool(
                r.revenue
                and abs(r.revenue.value - float(g["revenue"]))
                / max(abs(float(g["revenue"])), 1.0)
                < 0.001
            )
        if g.get("profit") is not None:
            ok = ok and bool(
                r.profit
                and abs(r.profit.value - float(g["profit"]))
                / max(abs(float(g["profit"])), 1.0)
                < 0.001
            )
        # When rev+profit are both labeled, still require the full verified gate
        if g.get("revenue") is not None and g.get("profit") is not None:
            ok = ok and bool(r.required_ok)
        hits += int(ok)
        rows_out.append(
            {
                "symbol": g["symbol"],
                "kind": g["kind"],
                "ok": ok,
                "expected": {
                    "revenue": g.get("revenue"),
                    "profit": g.get("profit"),
                    "eps_basic": g["eps_basic"],
                },
                "got": {
                    "revenue": r.revenue.value if r.revenue else None,
                    "profit": r.profit.value if r.profit else None,
                    "eps_basic": r.eps_basic.value if r.eps_basic else None,
                },
            }
        )
    n = len(gold)
    return {
        "n": n,
        "hits": hits,
        "accuracy_pct": round(100.0 * hits / n, 2) if n else 0.0,
        "rows": rows_out,
    }


def summarize(rows: list[FilingResult]) -> dict:
    n = len(rows)
    ok = sum(1 for r in rows if r.required_ok)
    # soft: all three present even if one unverified — not used for target
    present = sum(
        1
        for r in rows
        if r.revenue and r.profit and r.eps_basic
    )
    verified_counts = Counter(r.verified_metrics for r in rows)
    fail_c = Counter()
    for r in rows:
        for f in r.fail_reasons:
            fail_c[f] += 1

    def pct(x: int) -> float:
        return round(100.0 * x / n, 2) if n else 0.0

    return {
        "n": n,
        "required_ok": ok,
        "accuracy_pct": pct(ok),
        "all_three_present": present,
        "all_three_present_pct": pct(present),
        "verified_metric_hist": dict(verified_counts),
        "top_fail_reasons": fail_c.most_common(20),
        "by_kind": {
            k: {
                "n": sum(1 for r in rows if r.kind == k),
                "ok": sum(1 for r in rows if r.kind == k and r.required_ok),
            }
            for k in ("quarterly", "annual")
        },
    }


def write_report(
    summary: dict,
    rows: list[FilingResult],
    path: Path,
    meta: dict,
    gold: dict | None = None,
) -> None:
    gold = gold or {}
    lines = [
        "# CSE financial extract — verified accuracy spike",
        "",
        f"Generated: `{meta['generated_at']}`  ",
        f"Sample: **{summary['n']}** unique strong-set PDFs  ",
        "Research only — not alert truth.",
        "",
        "## Headline",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| **Human gold accuracy** (value match) | **{gold.get('accuracy_pct', 'n/a')}%** "
        f"({gold.get('hits', '?')}/{gold.get('n', '?')}) |",
        f"| Coverage gate (required_ok, adjacency-verified) | **{summary['accuracy_pct']}%** "
        f"({summary['required_ok']}/{summary['n']}) |",
        f"| All three metrics present (pre-verify) | {summary['all_three_present_pct']}% |",
        "",
        "Human gold = hand-checked revenue / PAT / basic EPS from the SOPL page "
        "(current quarter when both Q + YTD exist; Group when Company+Group exist). "
        "See `cse_financial_gold_labels.json`.",
        "",
        "### By kind (coverage)",
        "",
        "```json",
        json.dumps(summary["by_kind"], indent=2),
        "```",
        "",
        "### Fail reasons (coverage)",
        "",
        "```json",
        json.dumps(summary["top_fail_reasons"], indent=2),
        "```",
        "",
        "## Human gold panel",
        "",
    ]
    for g in gold.get("rows") or []:
        mark = "PASS" if g["ok"] else "FAIL"
        lines.append(
            f"- {mark} `{g['symbol']}` ({g['kind']}) "
            f"exp={g['expected']} got={g['got']}"
        )
    lines += ["", "## Sample coverage OK", ""]
    for r in [x for x in rows if x.required_ok][:8]:
        lines.append(
            f"- `{r.symbol}` ({r.kind}) scale={r.scale}  \n"
            f"  rev={r.revenue.value if r.revenue else None} "
            f"pat={r.profit.value if r.profit else None} "
            f"eps={r.eps_basic.value if r.eps_basic else None}"
        )
    lines += ["", "## Sample coverage FAIL", ""]
    fails = [x for x in rows if not x.required_ok][:10]
    if not fails:
        lines.append("- _(none)_")
    for r in fails:
        lines.append(
            f"- `{r.symbol}` ({r.kind}): {', '.join(r.fail_reasons)} "
            f"err={r.error}"
        )
    lines += [
        "",
        "## Method",
        "",
        "1. Rank SOPL-like pages (PyMuPDF; annuals scan full PDF; TOC page hints).",
        "2. Prefer **quarter** pages over YTD, **Group** over Company-only.",
        "3. Line-parse revenue / profit / EPS with CSE aliases "
        "(premiums, financing income, Profit/(Loss), Dialuted typo, Basic/Diluted).",
        "4. Skip note-number lines; stitch broken `( 825,505)` layouts; leftmost column.",
        "5. Adjacency-verify each pick in page text.",
        "6. Score against hand gold labels for true value accuracy.",
        "",
        "**Still not Telegram alert truth** — scale/unit and issuer quirks remain.",
        "",
        f"Raw: `{meta['json_name']}`",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=float, default=0.99)
    ap.add_argument("--prior", type=str, default="")
    ap.add_argument(
        "--gold",
        type=str,
        default=str(OUT_DIR / "cse_financial_gold_labels.json"),
    )
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prior = Path(args.prior) if args.prior else sorted(OUT_DIR.glob(PRIOR_GLOB))[-1]
    strong = load_strong_rows(prior)
    print(f"Unique strong PDFs: {len(strong)} from {prior.name}")

    rows: list[FilingResult] = []
    for i, m in enumerate(strong, 1):
        print(f"[{i}/{len(strong)}] {m['symbol']} {m['kind']} ...", flush=True)
        r = eval_one(m)
        rows.append(r)
        status = "OK" if r.required_ok else f"FAIL:{','.join(r.fail_reasons)}"
        print(f"  → {status}", flush=True)

    summary = summarize(rows)
    gold_path = Path(args.gold)
    gold = score_gold(gold_path) if gold_path.exists() else {"n": 0, "hits": 0, "accuracy_pct": 0.0, "rows": []}
    print("GOLD", json.dumps({k: gold[k] for k in ("n", "hits", "accuracy_pct")}, indent=2))

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_name = f"cse_financial_accuracy_eval_{ts}.json"
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "prior": str(prior.name),
        "target": args.target,
        "note": "Research only. Primary metric = human gold value match; coverage = adjacency-verified extract.",
        "summary": summary,
        "gold": gold,
        "rows": [asdict(r) for r in rows],
    }
    (OUT_DIR / json_name).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    write_report(
        summary,
        rows,
        OUT_DIR / "CSE_FINANCIAL_ACCURACY_EVAL.md",
        {"generated_at": payload["generated_at"], "json_name": json_name},
        gold=gold,
    )
    print(json.dumps(summary, indent=2))
    cov = summary["accuracy_pct"] / 100.0
    gold_acc = gold.get("accuracy_pct", 0) / 100.0
    hit = cov >= args.target and gold_acc >= args.target
    print(
        f"TARGET {args.target:.0%} → {'HIT' if hit else 'MISS'} "
        f"(coverage {summary['accuracy_pct']}%, gold {gold.get('accuracy_pct')}%)"
    )
    if not hit:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
