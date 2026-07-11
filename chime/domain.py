"""Internal domain models — validated with pydantic, independent of cse.lk shapes."""

from __future__ import annotations

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
    id: int | None = None


class AlertRule(BaseModel):
    """Active user alert rule loaded from storage for evaluation."""

    model_config = ConfigDict(extra="ignore")

    id: int
    user_id: int
    telegram_id: int
    symbol: str
    type: AlertType
    threshold: float | None = None
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


def format_alert_message(event: AlertEvent) -> str:
    lines = [
        f"🔔 {event.symbol}",
        f"Trigger: {event.trigger}",
    ]
    if event.current_price is not None:
        lines.append(f"Price: {event.current_price:.2f} LKR")
    if event.disclosure_title:
        lines.append(f"Disclosure: {truncate_disclosure_title(event.disclosure_title)}")
    if event.disclosure_url:
        lines.append(event.disclosure_url)
    lines.append("")
    lines.append(disclaimer())
    return "\n".join(lines)


def format_dead_letter_notify(symbol: str, attempts: int) -> str:
    """One-shot user message when an alert is abandoned after delivery failures."""
    return (
        f"Chime could not deliver an alert for {symbol} after {attempts} tries. "
        "Not financial advice."
    )


def as_dict(model: BaseModel) -> dict[str, Any]:
    return model.model_dump()
