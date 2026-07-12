"""Internal domain models — validated with pydantic, independent of cse.lk shapes."""

from __future__ import annotations

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
# Telegram hard cap is 4096; leave headroom for title/URL/NFA framing.
BRIEF_BODY_MAX = 3500
_CTRL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def disclaimer() -> str:
    return "Not financial advice — informational only."


def truncate_disclosure_title(title: str, max_len: int = DISCLOSURE_TITLE_MAX) -> str:
    """Truncate long filing titles so Telegram alert bodies stay readable."""
    t = title.strip()
    if len(t) <= max_len:
        return t
    if max_len <= 1:
        return "…"
    return t[: max_len - 1].rstrip() + "…"


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
    body = _CTRL_RE.sub("", brief).strip()
    if not body:
        return None
    cap = max(1, int(max_len))
    if len(body) > cap:
        body = body[: cap - 1].rstrip() + "…"
    return body


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
    control-stripped and length-capped so a hostile/huge LLM string cannot
    blow past Telegram's 4096 limit and fail the push.
    """
    # Lazy import: adapters.cse imports domain at module load.
    from chime.adapters.cse import allowed_filing_url

    lines = [
        f"🔔 {event.symbol}",
        f"Trigger: {event.trigger}",
    ]
    if event.current_price is not None:
        lines.append(f"Price: {event.current_price:.2f} LKR")
    if event.disclosure_title:
        lines.append(f"Disclosure: {truncate_disclosure_title(event.disclosure_title)}")
    if event.disclosure_url:
        safe_url = allowed_filing_url(event.disclosure_url)
        if safe_url:
            lines.append(safe_url)
    brief = filing_brief if filing_brief is not None else event.filing_brief
    brief_text = sanitize_brief_body(brief)
    if brief_text:
        lines.append("")
        lines.append(brief_text)
    lines.append("")
    lines.append(disclaimer())
    return "\n".join(lines)


def format_dead_letter_notify(symbol: str, attempts: int) -> str:
    """One-shot user message when an alert is abandoned after delivery failures."""
    return (
        f"Chime could not deliver an alert for {symbol} after {attempts} tries. "
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
    """
    # Lazy import: adapters.cse imports domain at module load.
    from chime.adapters.cse import allowed_filing_url

    lines = [
        f"🔔 {symbol}",
        "Filing brief ready",
    ]
    if title and title.strip():
        lines.append(f"Disclosure: {truncate_disclosure_title(title)}")
    if url and str(url).strip():
        safe_url = allowed_filing_url(url)
        if safe_url:
            lines.append(safe_url)
    brief_text = sanitize_brief_body(brief)
    if brief_text:
        lines.append("")
        lines.append(brief_text)
    lines.append("")
    lines.append(disclaimer())
    return "\n".join(lines)


def as_dict(model: BaseModel) -> dict[str, Any]:
    return model.model_dump()
