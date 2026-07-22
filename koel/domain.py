"""Internal domain models — validated with pydantic, independent of cse.lk shapes."""

from __future__ import annotations

import math
import os
import re
from datetime import date, datetime
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator

_COLOMBO = ZoneInfo("Asia/Colombo")


def _none_if_bool_numeric(value: Any) -> Any:
    """Reject bool-as-number soft accepts while preserving normal numeric coercion."""
    return None if isinstance(value, bool) else value


def _reject_bool_numeric(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid numeric value")
    return value


class AlertType(StrEnum):
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    DAILY_MOVE = "daily_move"
    DISCLOSURE = "disclosure"
    # Activity / flow proxies (not true buy/sell attribution).
    VOLUME_SPIKE = "volume_spike"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    CROSSING_VOLUME = "crossing_volume"
    BIG_PRINT = "big_print"
    GAP = "gap"
    BUY_IN = "buy_in"
    NON_COMPLIANCE = "non_compliance"
    HALT = "halt"
    # Public order book imbalance (POST /orderBook totalBids / totalAsks).
    BID_HEAVY = "bid_heavy"
    ASK_HEAVY = "ask_heavy"
    # Financial PDF calc / YoY alerts (feature-flagged).
    EPS_ABOVE = "eps_above"
    EPS_BELOW = "eps_below"
    EPS_YOY_ABOVE = "eps_yoy_above"
    EPS_YOY_BELOW = "eps_yoy_below"
    REV_YOY_ABOVE = "rev_yoy_above"
    REV_YOY_BELOW = "rev_yoy_below"
    PROFIT_YOY_ABOVE = "profit_yoy_above"
    PROFIT_YOY_BELOW = "profit_yoy_below"
    # Market-wide regime alerts (symbol = MARKET).
    APPETITE_BAND = "appetite_band"
    FOREIGN_FLOW = "foreign_flow"
    BOOK_PRESSURE = "book_pressure"
    USDLKR_MOVE = "usdlkr_move"
    OIL_MOVE = "oil_move"
    # Dividend calendar (CSE disclosures → dividend_events).
    XD_SOON = "xd_soon"
    XD_DIGEST = "xd_digest"
    # Share split / consolidation (price-ratio cliff or CSE subdivision filing).
    SHARE_SPLIT = "share_split"
    # Path / MA / reference-price alerts (daily_bars + live snapshot).
    HIGH_52W = "high_52w"
    LOW_52W = "low_52w"
    MA_CROSS = "ma_cross"
    REF_MOVE = "ref_move"


# MA periods accepted for ma_cross (Fidelity-style set).
MA_CROSS_PERIODS: frozenset[int] = frozenset({20, 50, 200})


# Alert types that need a positive numeric threshold.
THRESHOLD_ALERT_TYPES: frozenset[AlertType] = frozenset(
    {
        AlertType.PRICE_ABOVE,
        AlertType.PRICE_BELOW,
        AlertType.DAILY_MOVE,
        AlertType.VOLUME_SPIKE,
        AlertType.VOLUME_UP,
        AlertType.VOLUME_DOWN,
        AlertType.CROSSING_VOLUME,
        AlertType.BIG_PRINT,
        AlertType.GAP,
        AlertType.BID_HEAVY,
        AlertType.ASK_HEAVY,
        AlertType.EPS_ABOVE,
        AlertType.EPS_BELOW,
        AlertType.EPS_YOY_ABOVE,
        AlertType.EPS_YOY_BELOW,
        AlertType.REV_YOY_ABOVE,
        AlertType.REV_YOY_BELOW,
        AlertType.PROFIT_YOY_ABOVE,
        AlertType.PROFIT_YOY_BELOW,
        AlertType.APPETITE_BAND,
        AlertType.FOREIGN_FLOW,
        AlertType.BOOK_PRESSURE,
        AlertType.USDLKR_MOVE,
        AlertType.OIL_MOVE,
        AlertType.XD_SOON,
        AlertType.XD_DIGEST,
        AlertType.MA_CROSS,
        AlertType.REF_MOVE,
    }
)

# Synthetic MARKET symbol only (no per-stock CSE lookup).
MARKET_REGIME_ALERT_TYPES: frozenset[AlertType] = frozenset(
    {
        AlertType.HALT,
        AlertType.APPETITE_BAND,
        AlertType.FOREIGN_FLOW,
        AlertType.BOOK_PRESSURE,
        AlertType.USDLKR_MOVE,
        AlertType.OIL_MOVE,
        AlertType.XD_DIGEST,
    }
)

# Filing-metrics alerts (absolute EPS or YoY %).
FILING_METRICS_ALERT_TYPES: frozenset[AlertType] = frozenset(
    {
        AlertType.EPS_ABOVE,
        AlertType.EPS_BELOW,
        AlertType.EPS_YOY_ABOVE,
        AlertType.EPS_YOY_BELOW,
        AlertType.REV_YOY_ABOVE,
        AlertType.REV_YOY_BELOW,
        AlertType.PROFIT_YOY_ABOVE,
        AlertType.PROFIT_YOY_BELOW,
    }
)

YOY_ALERT_TYPES: frozenset[AlertType] = frozenset(
    {
        AlertType.EPS_YOY_ABOVE,
        AlertType.EPS_YOY_BELOW,
        AlertType.REV_YOY_ABOVE,
        AlertType.REV_YOY_BELOW,
        AlertType.PROFIT_YOY_ABOVE,
        AlertType.PROFIT_YOY_BELOW,
    }
)

# Alert types evaluated from price_snapshots (no extra CSE endpoint).
PRICE_BOARD_ALERT_TYPES: frozenset[AlertType] = frozenset(
    {
        AlertType.PRICE_ABOVE,
        AlertType.PRICE_BELOW,
        AlertType.DAILY_MOVE,
        AlertType.VOLUME_SPIKE,
        AlertType.VOLUME_UP,
        AlertType.VOLUME_DOWN,
        AlertType.CROSSING_VOLUME,
        AlertType.GAP,
        AlertType.SHARE_SPLIT,
        AlertType.HIGH_52W,
        AlertType.LOW_52W,
        AlertType.MA_CROSS,
        AlertType.REF_MOVE,
    }
)

# Notice types with no threshold (disclosure-like).
NOTICE_ALERT_TYPES: frozenset[AlertType] = frozenset(
    {
        AlertType.BUY_IN,
        AlertType.NON_COMPLIANCE,
        AlertType.HALT,
        AlertType.SHARE_SPLIT,
        AlertType.HIGH_52W,
        AlertType.LOW_52W,
    }
)

# Synthetic stock for market-wide halt / system notices.
MARKET_SYMBOL = "MARKET"


class PriceSnapshot(BaseModel):
    """Normalized price tick stored every poll cycle."""

    model_config = ConfigDict(extra="ignore")

    symbol: str
    price: float
    previous_close: float | None = None
    change: float | None = None
    change_pct: float | None = None
    volume: float | None = None
    trade_count: float | None = None
    turnover: float | None = None
    crossing_volume: float | None = None
    high: float | None = None
    low: float | None = None
    open: float | None = None
    market_cap: float | None = None
    name: str | None = None
    ts: datetime
    # Optional DB id after persistence
    id: int | None = None
    # CSE board id (tradeSummary.id / companyInfoSummery.reqSymbolInfo.id)
    # for companyChartDataByStock path backfill — not the Postgres snapshot id.
    cse_stock_id: int | None = None

    @field_validator("price", mode="before")
    @classmethod
    def _price_must_not_be_bool(cls, value: Any) -> Any:
        return _reject_bool_numeric(value)

    @field_validator(
        "previous_close",
        "change",
        "change_pct",
        "volume",
        "trade_count",
        "turnover",
        "crossing_volume",
        "high",
        "low",
        "open",
        "market_cap",
        mode="before",
    )
    @classmethod
    def _optional_numeric_must_not_be_bool(cls, value: Any) -> Any:
        return _none_if_bool_numeric(value)

    @field_validator("cse_stock_id", mode="before")
    @classmethod
    def _cse_stock_id_must_not_be_bool(cls, value: Any) -> Any:
        if isinstance(value, bool):
            return None
        return value


class Disclosure(BaseModel):
    """Normalized company announcement / disclosure."""

    model_config = ConfigDict(extra="ignore")

    external_id: str
    symbol: str
    company_name: str | None = None
    title: str
    category: str | None = None
    url: str
    published_at: datetime
    seen_at: datetime
    # Parsed dateOfAnnouncement for logging/display only — never used for alert gating.
    doa_display: datetime | None = None
    # CDN PDF from legacy ``filePath`` enrichment (optional; alerts do not wait on it).
    pdf_url: str | None = None
    id: int | None = None
    # Ephemeral: True when upsert inserted a new row (not ON CONFLICT update).
    # Poller uses this to queue PDF enrichment once — never on every re-poll.
    just_inserted: bool = False


class SectorSnapshot(BaseModel):
    """Normalized CSE sector index row (POST /allSectors).

    Optional browse layer — not used by alert rules. Poller persists only when
    ``SECTORS_INGEST=1``.
    """

    model_config = ConfigDict(extra="ignore")

    sector_id: int
    symbol: str
    name: str
    index_code: str | None = None
    index_code_sp: str | None = None
    index_name: str | None = None
    index_value: float | None = None
    change: float | None = None
    change_pct: float | None = None
    trade_today: float | None = None
    volume_today: float | None = None
    turnover_today: float | None = None
    previous_close: float | None = None
    ts: datetime
    cse_row_id: int | None = None


class IndexSnapshot(BaseModel):
    """Normalized CSE market index row (POST /aspiData, /snpData)."""

    model_config = ConfigDict(extra="ignore")

    code: str
    name: str | None = None
    value: float
    change: float | None = None
    change_pct: float | None = None
    ts: datetime

    @field_validator("value", mode="before")
    @classmethod
    def _value_must_not_be_bool(cls, value: Any) -> Any:
        return _reject_bool_numeric(value)

    @field_validator("change", "change_pct", mode="before")
    @classmethod
    def _optional_numeric_must_not_be_bool(cls, value: Any) -> Any:
        return _none_if_bool_numeric(value)


class DailyBar(BaseModel):
    """One CSE daily path bar (``companyChartDataByStock`` period 2–5).

    ``price`` is last/close (CSE field ``p``). ``open`` is often null upstream.
    ``trade_date`` is the Asia/Colombo calendar date of ``bar_ts``.
    """

    model_config = ConfigDict(extra="ignore")

    symbol: str
    trade_date: date
    price: float
    high: float | None = None
    low: float | None = None
    open: float | None = None
    volume: float | None = None
    source_period: int
    bar_ts: datetime

    @field_validator("price", mode="before")
    @classmethod
    def _price_must_not_be_bool(cls, value: Any) -> Any:
        return _reject_bool_numeric(value)

    @field_validator("high", "low", "open", "volume", mode="before")
    @classmethod
    def _optional_numeric_must_not_be_bool(cls, value: Any) -> Any:
        return _none_if_bool_numeric(value)

    @field_validator("source_period", mode="before")
    @classmethod
    def _period_must_not_be_bool(cls, value: Any) -> Any:
        return _reject_bool_numeric(value)


class ForecastPoint(BaseModel):
    """One model path estimate for sparkline overlay (not a price target)."""

    model_config = ConfigDict(extra="ignore")

    symbol: str
    as_of: date
    horizon_i: int
    ts: datetime
    yhat: float
    model_version: str
    # Optional confidence metadata (migration 018).
    confidence: float | None = None
    confidence_band: str | None = None  # high | medium | low | none
    gate: str | None = None
    reasons: list[str] = Field(default_factory=list)

    @field_validator("yhat", mode="before")
    @classmethod
    def _yhat_must_not_be_bool(cls, value: Any) -> Any:
        return _reject_bool_numeric(value)

    @field_validator("horizon_i", mode="before")
    @classmethod
    def _horizon_must_not_be_bool(cls, value: Any) -> Any:
        return _reject_bool_numeric(value)

    @field_validator("confidence", mode="before")
    @classmethod
    def _confidence_must_not_be_bool(cls, value: Any) -> Any:
        if value is None:
            return None
        return _reject_bool_numeric(value)


class AlertRule(BaseModel):
    """Active user alert rule loaded from storage for evaluation."""

    model_config = ConfigDict(extra="ignore")

    id: int
    user_id: int
    telegram_id: int
    symbol: str
    type: AlertType
    threshold: float | None = None
    # Disclosure rules only: optional case-insensitive substring filter on
    # Disclosure.category. None = match any category (backward compatible).
    category: str | None = None
    # ref_move only: user-supplied reference price for % move.
    ref_price: float | None = None
    active: bool = True
    armed: bool = True
    created_at: datetime | None = None
    muted_until: datetime | None = None

    @field_validator("threshold", "ref_price", mode="before")
    @classmethod
    def _threshold_must_not_be_bool(cls, value: Any) -> Any:
        return _none_if_bool_numeric(value)


class AlertEvent(BaseModel):
    """Pure evaluation result — no I/O. Caller claims + sends."""

    rule_id: int
    user_id: int
    telegram_id: int
    symbol: str
    type: AlertType
    threshold: float | None = None
    ref_price: float | None = None
    trigger: str
    current_price: float | None = None
    disclosure_url: str | None = None
    disclosure_title: str | None = None
    # DB id of disclosures row (disclosure alerts); used to look up ready briefs.
    disclosure_id: int | None = None
    # Optional plain-language filing brief (Phase 2); never generated here.
    filing_brief: str | None = None
    snapshot_id: int | None = None
    event_key: str
    # Optional arming update for sticky-above/below rules
    set_armed: bool | None = None
    # Provenance / context for Telegram fires (W5/W6). Optional; formatters
    # omit when unset. Never investment advice.
    as_of: datetime | None = None
    context_line: str | None = None

    @field_validator("threshold", "ref_price", mode="before")
    @classmethod
    def _event_numeric_must_not_be_bool(cls, value: Any) -> Any:
        return _none_if_bool_numeric(value)


class PreviousPriceState(BaseModel):
    """Prior observation used for crossing semantics."""

    price: float | None = None
    change_pct: float | None = None
    # Whether a daily_move rule already fired for this symbol/session key
    move_fired_keys: set[str] = Field(default_factory=set)
    # Avg daily volume / crossing volume over recent sessions (excludes today).
    avg_volume: float | None = None
    avg_crossing_volume: float | None = None
    # Day-bucket keys already claimed for volume/gap activity rules.
    activity_fired_keys: set[str] = Field(default_factory=set)
    # Prior 52-week extremes from daily_bars (excludes incomplete today).
    high_52w: float | None = None
    low_52w: float | None = None
    # Simple moving averages of daily closes keyed by period (20 / 50 / 200).
    sma_by_period: dict[int, float] = Field(default_factory=dict)
    # Prior snapshot timestamp (for gap-aware %-move annotations).
    prev_ts: datetime | None = None

    @field_validator(
        "price",
        "change_pct",
        "avg_volume",
        "avg_crossing_volume",
        "high_52w",
        "low_52w",
        mode="before",
    )
    @classmethod
    def _state_numeric_must_not_be_bool(cls, value: Any) -> Any:
        return _none_if_bool_numeric(value)


class BigPrint(BaseModel):
    """Single day-tape print used for big_print alerts."""

    model_config = ConfigDict(extra="ignore")

    external_id: str
    symbol: str
    price: float | None = None
    quantity: float
    traded_at: datetime | None = None
    seen_at: datetime | None = None
    id: int | None = None
    just_inserted: bool = False

    @field_validator("quantity", mode="before")
    @classmethod
    def _qty_must_not_be_bool(cls, value: Any) -> Any:
        return _reject_bool_numeric(value)

    @field_validator("price", mode="before")
    @classmethod
    def _price_opt_must_not_be_bool(cls, value: Any) -> Any:
        return _none_if_bool_numeric(value)



class OrderBookSnapshot(BaseModel):
    """Normalized public order-book totals from ``POST /orderBook``.

    Full depth is truncated on the public API (often one bid level), but
    ``total_bids`` / ``total_asks`` are populated and usable for imbalance.
    """

    model_config = ConfigDict(extra="ignore")

    symbol: str
    total_bids: float
    total_asks: float
    best_bid: float | None = None
    best_bid_qty: float | None = None
    ts: datetime
    id: int | None = None

    @field_validator("total_bids", "total_asks", mode="before")
    @classmethod
    def _totals_must_not_be_bool(cls, value: Any) -> Any:
        return _reject_bool_numeric(value)

    @field_validator("best_bid", "best_bid_qty", mode="before")
    @classmethod
    def _opt_must_not_be_bool(cls, value: Any) -> Any:
        return _none_if_bool_numeric(value)


class MarketNotice(BaseModel):
    """Buy-in / non-compliance / halt notice normalized from CSE feeds."""

    model_config = ConfigDict(extra="ignore")

    external_id: str
    notice_type: str  # buy_in | non_compliance | halt
    symbol: str | None = None
    title: str
    body: str | None = None
    url: str | None = None
    published_at: datetime
    seen_at: datetime | None = None
    id: int | None = None
    just_inserted: bool = False


DISCLOSURE_TITLE_MAX = 120
# Disclosure alert category substring — short CSE labels; keep confirm/myalerts safe.
DISCLOSURE_CATEGORY_MAX = 64
# Telegram hard cap is 4096; leave headroom for title/URL/NFA framing.
BRIEF_BODY_MAX = 3500
TELEGRAM_SAFE_MAX = 4096
MAX_ALERT_THRESHOLD = 1_000_000_000
_CTRL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def resolve_positive_int_cap(
    raw: object,
    *,
    default: int = 1,
    absolute_max: int | None = None,
) -> int:
    """Fail-closed positive int cap (parity web ``resolveSanitizeTextCap``).

    Medium: ``max(1, int(max_len))`` raises on ``None`` / ``NaN`` / ``inf`` /
    non-numerics mid Telegram format / PDF fetch / prompt build. Non-positive
    and oversized values clamp instead of crashing the alert path.
    """
    try:
        if isinstance(raw, float) and not math.isfinite(raw):
            return default
        # Narrow before int() — mypy rejects int(object); fail closed otherwise.
        if isinstance(raw, bool):
            # bool is an int subclass; treat as invalid for size caps.
            return default
        if isinstance(raw, int):
            n = raw
        elif isinstance(raw, (float, str, bytes, bytearray)):
            n = int(raw)
        else:
            return default
    except (TypeError, ValueError, OverflowError):
        return default
    if n < 1:
        return default
    if absolute_max is not None and n > absolute_max:
        return absolute_max
    return n



def sanitize_disclosure_category(category: str | None) -> str | None:
    """Strip C0/C1 controls and cap length for disclosure category filters.

    Returns ``None`` when empty after sanitize.
    """
    if category is None:
        return None
    # Fail closed — non-strings used to throw on re.sub mid bot/API path.
    if not isinstance(category, str):
        return None
    cleaned = _CTRL_RE.sub("", category).strip()
    if not cleaned:
        return None
    if len(cleaned) > DISCLOSURE_CATEGORY_MAX:
        cleaned = cleaned[:DISCLOSURE_CATEGORY_MAX].rstrip()
    return cleaned or None


def disclaimer() -> str:
    return "Not financial advice — informational only."


def _dash_symbol_link(symbol: str) -> str | None:
    """Optional deep link to the dash symbol page (C3).

    Only when ``DASH_PUBLIC_URL`` is an https origin. Symbol must already be
    control-stripped; path-encodes for safety.
    """
    from urllib.parse import quote

    raw = os.environ.get("DASH_PUBLIC_URL", "")
    if not isinstance(raw, str):
        return None
    base = raw.strip().rstrip("/")
    if not base.startswith("https://") or len(base) > 200:
        return None
    if any(ch in base for ch in (" ", "\n", "\r", "\t")):
        return None
    # Fail closed — reject userinfo / query / fragment in base.
    if "@" in base or "?" in base or "#" in base:
        return None
    if not symbol or symbol == "?" or len(symbol) > 32:
        return None
    return f"{base}/symbols/{quote(symbol, safe='')}"


def format_yoy_comparison_block(
    *,
    metrics: dict[str, Any],
    comparison: dict[str, Any] | None,
) -> str | None:
    """Short YoY block for disclosure Telegram append. None if not comparable."""
    if not metrics.get("extract_ok"):
        return None
    if not comparison or comparison.get("match_quality") not in (
        "exact_yoy",
        "approx_yoy",
    ):
        return None
    lines: list[str] = []
    kind = str(metrics.get("kind") or "filing")
    entity = str(metrics.get("entity") or "unknown")
    eps = metrics.get("eps_basic")
    if eps is not None and comparison.get("eps_delta_pct") is not None:
        lines.append(
            f"Basic EPS {float(eps):.4g} "
            f"(YoY {float(comparison['eps_delta_pct']):+.2f}%)"
        )
    elif eps is not None:
        lines.append(f"Basic EPS {float(eps):.4g}")
    rev_pct = comparison.get("revenue_delta_pct")
    pat_pct = comparison.get("profit_delta_pct")
    bits: list[str] = []
    if rev_pct is not None:
        bits.append(f"Revenue YoY {float(rev_pct):+.2f}%")
    if pat_pct is not None:
        bits.append(f"Profit YoY {float(pat_pct):+.2f}%")
    if bits:
        lines.append(" · ".join(bits))
    lines.append(
        f"{kind} · {entity} · {metrics.get('currency') or 'LKR'} · "
        f"{comparison.get('match_quality')}"
    )
    lines.append("Extracted numbers — verify in the filing.")
    return "\n".join(lines)

def truncate_disclosure_title(title: str, max_len: int = DISCLOSURE_TITLE_MAX) -> str:
    """Truncate long filing titles so Telegram alert bodies stay readable.

    Strips C0/C1 controls so a hostile DB title cannot inject nulls/newlines
    into Telegram egress.
    """
    # Fail closed — non-strings used to throw on re.sub mid alert format.
    if not isinstance(title, str):
        return ""
    t = _CTRL_RE.sub("", title).strip()
    if not t:
        return ""
    cap = resolve_positive_int_cap(
        max_len, default=DISCLOSURE_TITLE_MAX, absolute_max=DISCLOSURE_TITLE_MAX
    )
    if len(t) <= cap:
        return t
    if cap <= 1:
        return "…"
    return t[: cap - 1].rstrip() + "…"


def sanitize_brief_body(
    brief: str | None,
    *,
    max_len: int = BRIEF_BODY_MAX,
) -> str | None:
    """Strip C0/C1 controls and cap length for Telegram / storage egress.

    Returns ``None`` when empty after sanitize so callers omit the body.
    """
    if brief is None:
        return None
    # Fail closed — non-strings used to throw on re.sub mid alert format.
    if not isinstance(brief, str):
        return None
    body = _CTRL_RE.sub("", brief).strip()
    if not body:
        return None
    # Fail closed — int(NaN)/None/inf used to raise; oversized caps clamp.
    cap = resolve_positive_int_cap(
        max_len, default=1, absolute_max=TELEGRAM_SAFE_MAX
    )
    if len(body) > cap:
        body = body[: cap - 1].rstrip() + "…"
    return body


def format_price_lkr(price: float) -> str:
    """Compact LKR price for Telegram — avoids pathological ``.2f`` on huge floats."""
    # Fail closed — non-numeric / bool used to throw in math.isfinite mid alert.
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        return "n/a"
    if not math.isfinite(price):
        return "n/a"
    if abs(price) >= 1_000_000_000:
        return f"{price:.6g}"
    return f"{price:.2f}"


def brief_budget_for_prefix(
    prefix_lines: list[str],
    *,
    nfa: str | None = None,
) -> int:
    """Chars available for a brief body under Telegram's hard cap.

    Prefix is everything before the brief; reserves blank lines around the
    brief (when present) plus the NFA disclaimer.
    """
    nfa_text = nfa if isinstance(nfa, str) and nfa else disclaimer()
    # join(prefix) + "\\n\\n" + brief + "\\n\\n" + nfa
    fixed = len("\n".join(prefix_lines)) + 2 + 2 + len(nfa_text)
    return max(0, TELEGRAM_SAFE_MAX - 1 - fixed)


def _clamp_telegram_message(msg: str, *, nfa: str | None = None) -> str:
    """Hard cap Telegram body length while keeping the NFA suffix."""
    if len(msg) < TELEGRAM_SAFE_MAX:
        return msg
    nfa_text = nfa if isinstance(nfa, str) and nfa else disclaimer()
    suffix = "\n\n" + nfa_text
    head = msg
    if nfa_text in msg:
        head = msg[: msg.rfind(nfa_text)].rstrip()
    budget = max(1, TELEGRAM_SAFE_MAX - 1 - len(suffix))
    if len(head) > budget:
        head = head[: budget - 1].rstrip() + "…"
    return head + suffix


def format_alert_message(
    event: AlertEvent,
    *,
    filing_brief: str | None = None,
    locale: str = "en",
) -> str:
    """Render a Telegram alert body. Always ends with NFA.

    ``filing_brief`` kwarg overrides ``event.filing_brief`` when not None.
    Neither path calls an LLM — callers supply precomputed text only.
    Filing URLs are egress-hardened (CDN / www.cse.lk only) so a hostile DB
    ``url`` cannot become an auto-linked Telegram href. Brief bodies are
    control-stripped and length-capped (dynamic Telegram budget) so a
    hostile/huge LLM string cannot blow past Telegram's 4096 limit.
    Symbol / trigger are control-stripped; prices use compact formatting;
    the final body is hard-clamped under Telegram's 4096 limit.

    ``locale`` selects structural labels / NFA (W9). Trigger *content* stays
    English for v1. Unknown locales fail closed to English.
    """
    # Lazy import: adapters.cse imports domain at module load.
    from koel.adapters.cse import allowed_filing_url
    from koel.i18n import normalize_locale, t

    loc = normalize_locale(locale)
    nfa_text = t("alert.nfa", loc)

    # Fail closed — non-string symbol/trigger used to throw on re.sub mid
    # Telegram alert egress (parity dead-letter / brief-followup).
    raw_symbol = event.symbol if isinstance(event.symbol, str) else ""
    raw_trigger = event.trigger if isinstance(event.trigger, str) else ""
    symbol = _CTRL_RE.sub("", raw_symbol).strip() or "?"
    trigger = _CTRL_RE.sub("", raw_trigger).strip() or "alert"
    lines = [
        t("alert.header", loc, symbol=symbol),
        t("alert.trigger", loc, trigger=trigger),
    ]
    if event.current_price is not None:
        lines.append(
            t("alert.price", loc, price=format_price_lkr(event.current_price))
        )
    if event.disclosure_title:
        title = truncate_disclosure_title(event.disclosure_title)
        if title:
            lines.append(f"Disclosure: {title}")
    if event.disclosure_url:
        safe_url = allowed_filing_url(event.disclosure_url)
        if safe_url:
            lines.append(safe_url)
    dash_link = _dash_symbol_link(symbol)
    if dash_link:
        lines.append(dash_link)
    # W5: one-line "why it moved" from Postgres facts (before brief / NFA).
    raw_ctx = event.context_line
    if isinstance(raw_ctx, str):
        ctx = _CTRL_RE.sub("", raw_ctx).strip()
        if len(ctx) > 120:
            ctx = ctx[:119].rstrip() + "…"
        if ctx:
            lines.append(ctx)
    brief = filing_brief if filing_brief is not None else event.filing_brief
    budget = min(BRIEF_BODY_MAX, brief_budget_for_prefix(lines, nfa=nfa_text))
    brief_text = sanitize_brief_body(brief, max_len=budget) if budget > 0 else None
    if brief_text:
        lines.append("")
        lines.append(brief_text)
    # W6: snapshot provenance stamp before NFA.
    as_of = event.as_of
    if isinstance(as_of, datetime):
        try:
            local = (
                as_of.astimezone(_COLOMBO)
                if as_of.tzinfo is not None
                else as_of.replace(tzinfo=_COLOMBO)
            )
            lines.append(t("alert.as_of", loc, time=local.strftime("%H:%M")))
        except Exception:
            pass
    lines.append("")
    lines.append(nfa_text)
    return _clamp_telegram_message("\n".join(lines), nfa=nfa_text)


def format_dead_letter_notify(symbol: str, attempts: int) -> str:
    """One-shot user message when an alert is abandoned after delivery failures.

    Symbol is control-stripped and length-capped (same egress bar as ``/brief``)
    so a hostile DB/parsed symbol cannot inject nulls/newlines or blow past
    Telegram's 4096 limit — an oversize dead-letter notify would itself fail
    to send. Non-finite / unconvertible ``attempts`` fail closed to ``0``.
    """
    # Fail closed — non-strings used to throw on re.sub mid dead-letter notify.
    if not isinstance(symbol, str):
        symbol = ""
    clean = _CTRL_RE.sub("", symbol).strip() or "?"
    if len(clean) > 32:
        clean = clean[:31].rstrip() + "…"
    # Fail closed — bool soft-accepts via int(True)==1 mid dead-letter notify.
    n = (
        0
        if isinstance(attempts, bool) or not isinstance(attempts, int)
        else attempts
    )
    # Bound display so a pathological int cannot pad the body past 4096.
    if n < 0 or n > 1_000_000:
        n = 0 if n < 0 else 1_000_000
    return (
        f"koel could not deliver an alert for {clean} after {n} tries. "
        "Not financial advice."
    )


def format_brief_followup(
    *,
    symbol: str,
    brief: str,
    title: str | None = None,
    url: str | None = None,
) -> str:
    """Telegram follow-up when a filing brief becomes ready after the alert.

    Always ends with NFA. Callers supply precomputed brief text only.
    Filing URLs are egress-hardened (CDN / www.cse.lk only), matching ``/brief``.
    Brief bodies are control-stripped and length-capped (Telegram 4096).
    Symbol is control-stripped; final body is hard-clamped under 4096.
    """
    # Lazy import: adapters.cse imports domain at module load.
    from koel.adapters.cse import allowed_filing_url

    # Fail closed — non-strings used to throw on re.sub mid brief follow-up.
    if not isinstance(symbol, str):
        symbol = ""
    clean_symbol = _CTRL_RE.sub("", symbol).strip() or "?"
    lines = [
        f"🔔 {clean_symbol}",
        "Filing brief ready",
    ]
    # Fail closed — non-string title used to throw on .strip before truncate.
    if isinstance(title, str) and title.strip():
        clean_title = truncate_disclosure_title(title)
        if clean_title:
            lines.append(f"Disclosure: {clean_title}")
    # Fail closed — non-string url used to soft-accept via str(url) before
    # allowlist (objects became noise in the truthiness gate).
    if isinstance(url, str) and url.strip():
        safe_url = allowed_filing_url(url)
        if safe_url:
            lines.append(safe_url)
    budget = min(BRIEF_BODY_MAX, brief_budget_for_prefix(lines))
    brief_text = sanitize_brief_body(brief, max_len=budget) if budget > 0 else None
    if brief_text:
        lines.append("")
        lines.append(brief_text)
    lines.append("")
    lines.append(disclaimer())
    return _clamp_telegram_message("\n".join(lines))


def as_dict(model: BaseModel) -> dict[str, Any]:
    return model.model_dump()
