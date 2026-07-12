"""Internal domain models — validated with pydantic, independent of cse.lk shapes."""

from __future__ import annotations

import math
import re
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AlertType(StrEnum):
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    DAILY_MOVE = "daily_move"
    DISCLOSURE = "disclosure"


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
    high: float | None = None
    low: float | None = None
    open: float | None = None
    market_cap: float | None = None
    name: str | None = None
    ts: datetime
    # Optional DB id after persistence
    id: int | None = None


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
    active: bool = True
    armed: bool = True
    created_at: datetime | None = None


class AlertEvent(BaseModel):
    """Pure evaluation result — no I/O. Caller claims + sends."""

    rule_id: int
    user_id: int
    telegram_id: int
    symbol: str
    type: AlertType
    threshold: float | None = None
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


class PreviousPriceState(BaseModel):
    """Prior observation used for crossing semantics."""

    price: float | None = None
    change_pct: float | None = None
    # Whether a daily_move rule already fired for this symbol/session key
    move_fired_keys: set[str] = Field(default_factory=set)


DISCLOSURE_TITLE_MAX = 120
# Disclosure alert category substring — short CSE labels; keep confirm/myalerts safe.
DISCLOSURE_CATEGORY_MAX = 64
# Telegram hard cap is 4096; leave headroom for title/URL/NFA framing.
BRIEF_BODY_MAX = 3500
TELEGRAM_SAFE_MAX = 4096
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
        n = int(raw)  # type: ignore[arg-type]
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
    if not math.isfinite(price):
        return "n/a"
    if abs(price) >= 1_000_000_000:
        return f"{price:.6g}"
    return f"{price:.2f}"


def brief_budget_for_prefix(prefix_lines: list[str]) -> int:
    """Chars available for a brief body under Telegram's hard cap.

    Prefix is everything before the brief; reserves blank lines around the
    brief (when present) plus the NFA disclaimer.
    """
    nfa = disclaimer()
    # join(prefix) + "\\n\\n" + brief + "\\n\\n" + nfa
    fixed = len("\n".join(prefix_lines)) + 2 + 2 + len(nfa)
    return max(0, TELEGRAM_SAFE_MAX - 1 - fixed)


def _clamp_telegram_message(msg: str) -> str:
    """Hard cap Telegram body length while keeping the NFA suffix."""
    if len(msg) < TELEGRAM_SAFE_MAX:
        return msg
    nfa = disclaimer()
    suffix = "\n\n" + nfa
    head = msg
    if nfa in msg:
        head = msg[: msg.rfind(nfa)].rstrip()
    budget = max(1, TELEGRAM_SAFE_MAX - 1 - len(suffix))
    if len(head) > budget:
        head = head[: budget - 1].rstrip() + "…"
    return head + suffix


def format_alert_message(
    event: AlertEvent,
    *,
    filing_brief: str | None = None,
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
    """
    # Lazy import: adapters.cse imports domain at module load.
    from chime.adapters.cse import allowed_filing_url

    symbol = _CTRL_RE.sub("", event.symbol).strip() or "?"
    trigger = _CTRL_RE.sub("", event.trigger).strip() or "alert"
    lines = [
        f"🔔 {symbol}",
        f"Trigger: {trigger}",
    ]
    if event.current_price is not None:
        lines.append(f"Price: {format_price_lkr(event.current_price)} LKR")
    if event.disclosure_title:
        title = truncate_disclosure_title(event.disclosure_title)
        if title:
            lines.append(f"Disclosure: {title}")
    if event.disclosure_url:
        safe_url = allowed_filing_url(event.disclosure_url)
        if safe_url:
            lines.append(safe_url)
    brief = filing_brief if filing_brief is not None else event.filing_brief
    budget = min(BRIEF_BODY_MAX, brief_budget_for_prefix(lines))
    brief_text = sanitize_brief_body(brief, max_len=budget) if budget > 0 else None
    if brief_text:
        lines.append("")
        lines.append(brief_text)
    lines.append("")
    lines.append(disclaimer())
    return _clamp_telegram_message("\n".join(lines))


def format_dead_letter_notify(symbol: str, attempts: int) -> str:
    """One-shot user message when an alert is abandoned after delivery failures.

    Symbol is control-stripped and length-capped (same egress bar as ``/brief``)
    so a hostile DB/parsed symbol cannot inject nulls/newlines or blow past
    Telegram's 4096 limit — an oversize dead-letter notify would itself fail
    to send. Non-finite / unconvertible ``attempts`` fail closed to ``0``.
    """
    clean = _CTRL_RE.sub("", symbol or "").strip() or "?"
    if len(clean) > 32:
        clean = clean[:31].rstrip() + "…"
    try:
        n = int(attempts)
    except (TypeError, ValueError, OverflowError):
        n = 0
    # Bound display so a pathological int cannot pad the body past 4096.
    if n < 0 or n > 1_000_000:
        n = 0 if n < 0 else 1_000_000
    return (
        f"Chime could not deliver an alert for {clean} after {n} tries. "
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
    from chime.adapters.cse import allowed_filing_url

    clean_symbol = _CTRL_RE.sub("", symbol).strip() or "?"
    lines = [
        f"🔔 {clean_symbol}",
        "Filing brief ready",
    ]
    if title and title.strip():
        clean_title = truncate_disclosure_title(title)
        if clean_title:
            lines.append(f"Disclosure: {clean_title}")
    if url and str(url).strip():
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
