"""CSE dividend calendar parse + sync helpers (no LOLC).

Parses DPS / XD / payment from disclosure title, category, and ready briefs.
Persists into ``dividend_events`` for dash calendar + ``xd_soon`` alerts.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict

_COLOMBO = ZoneInfo("Asia/Colombo")

DIVIDEND_HINT_RE = re.compile(
    r"\bdividends?\b|\bcash\s*div(?:idend)?\b|\binterim\s+div|\bfinal\s+div",
    re.I,
)
DATES_TBD_RE = re.compile(r"dates?\s+to\s+be\s+notified", re.I)

DPS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"rate\s+of\s+dividend\s*[:.\-\s]*rs\.?\s*([0-9]+(?:\.[0-9]+)?)",
        re.I,
    ),
    re.compile(r"(?:rs\.?|lkr)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:per\s*share)?", re.I),
    re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*(?:lkr|rs\.?)\s*per\s*share", re.I),
)

XD_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\bxd\s*[:.\-\s]+([0-9]{1,2}[./\-\s][A-Za-z]{3,}[./\-\s][0-9]{2,4})",
        re.I,
    ),
    re.compile(
        r"\bxd\s*[:.\-\s]+([0-9]{1,2}[./\-][0-9]{1,2}[./\-][0-9]{2,4})",
        re.I,
    ),
    re.compile(
        r"\bex[-\s]?dividend\s*(?:date)?\s*[:.\-\s]+"
        r"([0-9]{1,2}[./\-\s][A-Za-z0-9]{1,}[./\-\s][0-9]{2,4})",
        re.I,
    ),
)

PAY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\bpayment\s*[:.\-\s]+([0-9]{1,2}[./\-\s][A-Za-z]{3,}[./\-\s][0-9]{2,4})",
        re.I,
    ),
    re.compile(
        r"\bpayment\s*[:.\-\s]+([0-9]{1,2}[./\-][0-9]{1,2}[./\-][0-9]{2,4})",
        re.I,
    ),
    re.compile(
        r"\bpayable\s*(?:on|date)?\s*[:.\-\s]+"
        r"([0-9]{1,2}[./\-\s][A-Za-z0-9]{1,}[./\-\s][0-9]{2,4})",
        re.I,
    ),
)

ANN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"date\s+of\s+announcement\s*[:.\-\s]+"
        r"([0-9]{1,2}[./\-\s][A-Za-z]{3,}[./\-\s][0-9]{2,4})",
        re.I,
    ),
)

KIND_RE = re.compile(
    r"\b(second\s+interim|first\s+interim|interim|final|special)\b",
    re.I,
)
FY_RE = re.compile(
    r"(?:financial\s+year|fy)\s*[:.\-\s]*([0-9]{4}\s*/\s*[0-9]{2,4})",
    re.I,
)

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

MAX_DPS = 1_000_000.0
MAX_TEXT = 8_000
MAX_XD_HORIZON_DAYS = 90


class DividendHints(BaseModel):
    model_config = ConfigDict(extra="ignore")

    dps: float | None = None
    d_xd: date | None = None
    d_pay: date | None = None
    d_ann: date | None = None
    kind: str | None = None
    fy: str | None = None
    dates_tbd: bool = False
    xd_raw: str | None = None
    payment_raw: str | None = None


class DividendEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    symbol: str
    disclosure_id: int | None = None
    d_ann: date | None = None
    d_xd: date | None = None
    d_pay: date | None = None
    dps: float | None = None
    kind: str | None = None
    fy: str | None = None
    dates_tbd: bool = False
    title: str | None = None
    source: str = "cse_disclosure"
    raw_hash: str | None = None


def is_dividend_disclosure(
    category: str | None,
    title: str | None,
) -> bool:
    hay = f"{category or ''} {title or ''}".strip()
    return bool(hay and DIVIDEND_HINT_RE.search(hay))


def parse_cse_date(raw: str | None) -> date | None:
    """Parse CSE-ish date strings to a calendar date."""
    if not isinstance(raw, str):
        return None
    s = re.sub(r"\s+", " ", raw.strip())
    if not s or len(s) > 40:
        return None
    # ISO
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    # 12.Feb.2019 / 12 Feb 2019 / 12-Feb-2019
    m = re.fullmatch(
        r"(\d{1,2})[./\-\s]+([A-Za-z]{3,9})[./\-\s]+(\d{2,4})",
        s,
    )
    if m:
        day = int(m.group(1))
        mon = _MONTHS.get(m.group(2).lower())
        year = int(m.group(3))
        if year < 100:
            year += 2000 if year < 70 else 1900
        if mon is None:
            return None
        try:
            return date(year, mon, day)
        except ValueError:
            return None
    # 12/02/2019 or 12-02-19
    m = re.fullmatch(r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{2,4})", s)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000 if y < 70 else 1900
        # Prefer D/M/Y (CSE convention)
        day, month = a, b
        if month > 12 and a <= 12:
            day, month = b, a
        if month < 1 or month > 12:
            return None
        try:
            return date(y, month, day)
        except ValueError:
            return None
    return None


def _first_capture(text: str, patterns: tuple[re.Pattern[str], ...]) -> str | None:
    for re_p in patterns:
        m = re_p.search(text)
        if not m:
            continue
        raw = (m.group(1) or "").strip()
        if raw and len(raw) <= 40:
            return re.sub(r"\s+", " ", raw)
    return None


def parse_dps(text: str) -> float | None:
    for re_p in DPS_PATTERNS:
        m = re_p.search(text)
        if not m:
            continue
        try:
            n = float(m.group(1))
        except (TypeError, ValueError):
            continue
        if n > 0 and n <= MAX_DPS and n == n:  # noqa: PLR0124 — NaN guard
            return n
    return None


def parse_dividend_hints(text: Any) -> DividendHints:
    if not isinstance(text, str) or not text.strip():
        return DividendHints()
    sample = text[:MAX_TEXT]
    xd_raw = _first_capture(sample, XD_PATTERNS)
    pay_raw = _first_capture(sample, PAY_PATTERNS)
    ann_raw = _first_capture(sample, ANN_PATTERNS)
    kind_m = KIND_RE.search(sample)
    fy_m = FY_RE.search(sample)
    kind = None
    if kind_m:
        kind = re.sub(r"\s+", " ", kind_m.group(1).strip().lower())
    fy = None
    if fy_m:
        fy = re.sub(r"\s+", "", fy_m.group(1).strip())
    return DividendHints(
        dps=parse_dps(sample),
        d_xd=parse_cse_date(xd_raw),
        d_pay=parse_cse_date(pay_raw),
        d_ann=parse_cse_date(ann_raw),
        kind=kind,
        fy=fy,
        dates_tbd=bool(DATES_TBD_RE.search(sample)),
        xd_raw=xd_raw,
        payment_raw=pay_raw,
    )


def merge_dividend_hints(*parts: str | None) -> DividendHints:
    out = DividendHints()
    for part in parts:
        if not isinstance(part, str) or not part.strip():
            continue
        h = parse_dividend_hints(part)
        if out.dps is None and h.dps is not None:
            out.dps = h.dps
        if out.d_xd is None and h.d_xd is not None:
            out.d_xd = h.d_xd
        if out.d_pay is None and h.d_pay is not None:
            out.d_pay = h.d_pay
        if out.d_ann is None and h.d_ann is not None:
            out.d_ann = h.d_ann
        if out.kind is None and h.kind is not None:
            out.kind = h.kind
        if out.fy is None and h.fy is not None:
            out.fy = h.fy
        if out.xd_raw is None and h.xd_raw is not None:
            out.xd_raw = h.xd_raw
        if out.payment_raw is None and h.payment_raw is not None:
            out.payment_raw = h.payment_raw
        out.dates_tbd = out.dates_tbd or h.dates_tbd
    return out


def hints_raw_hash(symbol: str, title: str, hints: DividendHints) -> str:
    payload = (
        f"{symbol}|{title}|{hints.dps}|{hints.d_xd}|{hints.d_pay}|"
        f"{hints.d_ann}|{hints.kind}|{hints.fy}|{hints.dates_tbd}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def colombo_today(as_of: datetime | None = None) -> date:
    if as_of is None:
        return datetime.now(_COLOMBO).date()
    try:
        return as_of.astimezone(_COLOMBO).date()
    except (OverflowError, ValueError, OSError):
        return datetime.now(_COLOMBO).date()


def xd_within_horizon(
    d_xd: date | None,
    *,
    horizon_days: float | int,
    today: date | None = None,
) -> bool:
    if d_xd is None:
        return False
    try:
        days = int(horizon_days)
    except (TypeError, ValueError):
        return False
    if days < 1 or days > MAX_XD_HORIZON_DAYS:
        return False
    base = today or colombo_today()
    return base <= d_xd <= base + timedelta(days=days)


def iso_week_key(today: date | None = None) -> str:
    d = today or colombo_today()
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"
