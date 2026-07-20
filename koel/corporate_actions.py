"""CSE share-split / consolidation parse + price-ratio detect helpers.

Persists into ``corporate_actions`` for dash chart adjustment and
``share_split`` Telegram alerts. ``daily_bars`` stay CSE-unadjusted.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

_COLOMBO = ZoneInfo("Asia/Colombo")

# Common CSE wording: subdivision, sub-division, share split, consolidation.
SPLIT_HINT_RE = re.compile(
    r"\bsub[-\s]?divisions?\b|\bshare\s+splits?\b|\bstock\s+splits?\b"
    r"|\bsplits?\s+of\s+shares?\b|\bconsolidation\s+of\s+shares?\b"
    r"|\bshare\s+consolidations?\b|\bsubdivision\s+of\s+shares?\b",
    re.I,
)

# 1:3 / 1 for 3 / one into three / 3 for 1 (consolidation often "3:1").
RATIO_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(\d{1,2})\s*[:/]\s*(\d{1,2})\b",
        re.I,
    ),
    re.compile(
        r"\b(\d{1,2})\s+for\s+(\d{1,2})\b",
        re.I,
    ),
    re.compile(
        r"\b(\d{1,2})\s+into\s+(\d{1,2})\b",
        re.I,
    ),
)

# Integer ratios we accept for price-cliff detection (forward or reverse).
COMMON_SPLIT_NS: tuple[int, ...] = (2, 3, 4, 5, 8, 10)

# Relative tolerance vs exact N (12% covers real CSE ticks — JINS 127.75→46.30
# is ~2.76× vs exact 3, ≈8.03% error, so 8% was too tight).
RATIO_TOLERANCE = 0.12

# Require at least this absolute session move before calling it a split cliff.
MIN_ABS_MOVE_PCT = 35.0

MAX_TEXT = 8_000


class CorporateAction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    symbol: str
    disclosure_id: int | None = None
    effective_date: date
    kind: str  # split | consolidation
    ratio_from: int
    ratio_to: int
    title: str | None = None
    source: str = "cse_disclosure"
    raw_hash: str | None = None


@dataclass(frozen=True, slots=True)
class SplitRatioHit:
    """Near-integer session price ratio (forward split or consolidation)."""

    kind: str  # split | consolidation
    ratio_from: int
    ratio_to: int
    n: int
    observed_ratio: float


class SplitHints(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: str | None = None
    ratio_from: int | None = None
    ratio_to: int | None = None
    effective_date: date | None = None


def is_split_disclosure(category: str | None, title: str | None) -> bool:
    hay = f"{category or ''} {title or ''}".strip()
    return bool(hay and SPLIT_HINT_RE.search(hay))


def colombo_today(as_of: datetime | date | None = None) -> date:
    if isinstance(as_of, date) and not isinstance(as_of, datetime):
        return as_of
    if isinstance(as_of, datetime):
        return as_of.astimezone(_COLOMBO).date()
    return datetime.now(_COLOMBO).date()


def adjust_factor(ratio_from: int, ratio_to: int) -> float:
    """Multiply pre-effective OHLC by this to compare with post-effective prices.

    Forward 1→3: factor 1/3. Consolidation 3→1: factor 3.
    """
    if ratio_from <= 0 or ratio_to <= 0:
        return 1.0
    return float(ratio_from) / float(ratio_to)


def detect_share_split_ratio(
    prev_price: float | None,
    curr_price: float | None,
    *,
    tolerance: float = RATIO_TOLERANCE,
    min_abs_move_pct: float = MIN_ABS_MOVE_PCT,
    candidates: tuple[int, ...] = COMMON_SPLIT_NS,
) -> SplitRatioHit | None:
    """Detect near-integer N:1 / 1:N cliffs between consecutive session prices.

    Uses last koel / bar close vs current — not CSE ``previous_close``, which
    is often already reset on split day so board % looks normal.
    """
    if (
        prev_price is None
        or curr_price is None
        or not math.isfinite(prev_price)
        or not math.isfinite(curr_price)
        or prev_price <= 0
        or curr_price <= 0
    ):
        return None
    move_pct = abs((curr_price - prev_price) / prev_price) * 100.0
    if move_pct < min_abs_move_pct:
        return None

    # Forward split: price drops ~÷N → prev/curr ≈ N
    forward = prev_price / curr_price
    # Consolidation: price rises ~×N → curr/prev ≈ N
    reverse = curr_price / prev_price

    best: SplitRatioHit | None = None
    best_err = float("inf")
    for n in candidates:
        if n < 2:
            continue
        err_f = abs(forward - n) / n
        if err_f <= tolerance and err_f < best_err:
            best_err = err_f
            best = SplitRatioHit(
                kind="split",
                ratio_from=1,
                ratio_to=n,
                n=n,
                observed_ratio=forward,
            )
        err_r = abs(reverse - n) / n
        if err_r <= tolerance and err_r < best_err:
            best_err = err_r
            best = SplitRatioHit(
                kind="consolidation",
                ratio_from=n,
                ratio_to=1,
                n=n,
                observed_ratio=reverse,
            )
    return best


def parse_split_hints(*texts: str | None) -> SplitHints:
    """Extract split/consolidation ratio from CSE announcement text."""
    joined = " ".join(t.strip() for t in texts if isinstance(t, str) and t.strip())
    if not joined:
        return SplitHints()
    if len(joined) > MAX_TEXT:
        joined = joined[:MAX_TEXT]

    kind: str | None = None
    low = joined.casefold()
    if re.search(r"consolidat", low):
        kind = "consolidation"
    elif SPLIT_HINT_RE.search(joined):
        kind = "split"

    ratio_from: int | None = None
    ratio_to: int | None = None
    for pat in RATIO_PATTERNS:
        m = pat.search(joined)
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        if a <= 0 or b <= 0 or a == b or a > 20 or b > 20:
            continue
        # "1:3" / "1 for 3" / "1 into 3" → forward split
        # "3:1" consolidation wording often uses larger:smaller
        if kind == "consolidation" or (kind is None and a > b):
            ratio_from, ratio_to = max(a, b), min(a, b)
            kind = "consolidation"
        else:
            ratio_from, ratio_to = min(a, b), max(a, b)
            kind = kind or "split"
        break

    # Default common CSE subdivision when text matches but ratio omitted.
    if kind == "split" and ratio_from is None:
        ratio_from, ratio_to = 1, 3
    if kind == "consolidation" and ratio_from is None:
        ratio_from, ratio_to = 3, 1

    return SplitHints(kind=kind, ratio_from=ratio_from, ratio_to=ratio_to)


def hints_raw_hash(symbol: str, title: str, hints: SplitHints) -> str:
    payload = (
        f"{symbol}|{title}|{hints.kind}|{hints.ratio_from}|{hints.ratio_to}|"
        f"{hints.effective_date}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def detect_splits_from_closes(
    points: list[tuple[date, float]],
) -> list[tuple[date, SplitRatioHit]]:
    """Scan ascending (trade_date, close) for ratio cliffs."""
    out: list[tuple[date, SplitRatioHit]] = []
    if len(points) < 2:
        return out
    for i in range(1, len(points)):
        d_prev, p_prev = points[i - 1]
        d_curr, p_curr = points[i]
        if d_curr <= d_prev:
            continue
        hit = detect_share_split_ratio(p_prev, p_curr)
        if hit is not None:
            out.append((d_curr, hit))
    return out


def cumulative_adjust_factor(
    actions: list[CorporateAction],
    *,
    as_of: date,
) -> float:
    """Product of adjust factors for actions with effective_date > as_of.

    Bars on/after the effective date keep raw prices; earlier bars are scaled
    so the series is continuous across the split.
    """
    factor = 1.0
    for action in actions:
        if action.effective_date <= as_of:
            continue
        factor *= adjust_factor(action.ratio_from, action.ratio_to)
    return factor


def action_label(action: CorporateAction | SplitRatioHit) -> str:
    kind = getattr(action, "kind", "split")
    rf = getattr(action, "ratio_from", 1)
    rt = getattr(action, "ratio_to", 1)
    if kind == "consolidation":
        return f"{rf}:{rt} share consolidation"
    return f"{rf}:{rt} share split"


def row_to_corporate_action(row: Any) -> CorporateAction:
    d = dict(row) if not isinstance(row, dict) else row
    return CorporateAction(
        id=d.get("id"),
        symbol=str(d["symbol"]),
        disclosure_id=d.get("disclosure_id"),
        effective_date=d["effective_date"],
        kind=str(d["kind"]),
        ratio_from=int(d["ratio_from"]),
        ratio_to=int(d["ratio_to"]),
        title=d.get("title"),
        source=str(d.get("source") or "cse_disclosure"),
        raw_hash=d.get("raw_hash"),
    )
