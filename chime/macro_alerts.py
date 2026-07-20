"""Evaluate MARKET regime alerts (appetite / foreign / book / FX / oil)."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from chime.domain import (
    MARKET_SYMBOL,
    AlertEvent,
    AlertRule,
    AlertType,
)
from chime.rules import _rule_inactive_or_muted

_COLOMBO = ZoneInfo("Asia/Colombo")


def _finite(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(
        value
    )


def evaluate_market_regime_rules(
    *,
    rules: list[AlertRule],
    appetite_score: float | None = None,
    foreign_net: float | None = None,
    book_imbalance_pct: float | None = None,
    usdlkr_change_pct: float | None = None,
    oil_change_pct: float | None = None,
    as_of: datetime | None = None,
    fired_keys: set[str] | None = None,
) -> list[AlertEvent]:
    """Fire MARKET rules when tape/context thresholds cross.

    Threshold meanings:
    - appetite_band: fire when score >= threshold (e.g. 61 ≈ Appetite)
    - foreign_flow: fire when abs(foreign_net) >= threshold (LKR)
    - book_pressure: fire when abs(imbalance_pct) >= threshold
    - usdlkr_move / oil_move: fire when abs(daily % change) >= threshold
    """
    now = as_of or datetime.now(tz=_COLOMBO)
    try:
        day = now.astimezone(_COLOMBO).date().isoformat()
    except (OverflowError, ValueError, OSError):
        day = date.today().isoformat()
    claimed = fired_keys or set()
    events: list[AlertEvent] = []

    for rule in rules:
        if rule.symbol != MARKET_SYMBOL:
            continue
        if _rule_inactive_or_muted(rule, as_of=now):
            continue
        if rule.threshold is None or not _finite(rule.threshold):
            continue
        thr = abs(float(rule.threshold))
        if thr <= 0:
            continue

        trigger: str | None = None
        key_prefix = rule.type.value

        if rule.type == AlertType.APPETITE_BAND:
            if appetite_score is None or not _finite(appetite_score):
                continue
            if float(appetite_score) < thr:
                continue
            trigger = (
                f"Market Appetite {float(appetite_score):.0f} "
                f"(threshold ≥ {thr:g}). Not financial advice."
            )
        elif rule.type == AlertType.FOREIGN_FLOW:
            if foreign_net is None or not _finite(foreign_net):
                continue
            if abs(float(foreign_net)) < thr:
                continue
            sign = "buying" if float(foreign_net) > 0 else "selling"
            trigger = (
                f"Foreign net {sign} {float(foreign_net):,.0f} LKR "
                f"(threshold {thr:g}). Not financial advice."
            )
        elif rule.type == AlertType.BOOK_PRESSURE:
            if book_imbalance_pct is None or not _finite(book_imbalance_pct):
                continue
            if abs(float(book_imbalance_pct)) < thr:
                continue
            side = "bid" if float(book_imbalance_pct) > 0 else "ask"
            trigger = (
                f"Public book {side}-heavy {float(book_imbalance_pct):+.1f}% "
                f"(threshold ±{thr:g}%). Sample totals only — not L2. NFA."
            )
        elif rule.type == AlertType.USDLKR_MOVE:
            if usdlkr_change_pct is None or not _finite(usdlkr_change_pct):
                continue
            if abs(float(usdlkr_change_pct)) < thr:
                continue
            trigger = (
                f"USD/LKR moved {float(usdlkr_change_pct):+.2f}% "
                f"(threshold ±{thr:g}%). Source CBSL when ingested. NFA."
            )
        elif rule.type == AlertType.OIL_MOVE:
            if oil_change_pct is None or not _finite(oil_change_pct):
                continue
            if abs(float(oil_change_pct)) < thr:
                continue
            trigger = (
                f"Brent moved {float(oil_change_pct):+.2f}% "
                f"(threshold ±{thr:g}%). Source EIA when ingested. NFA."
            )
        else:
            continue

        key = f"{key_prefix}:{rule.id}:{day}"
        if key in claimed:
            continue
        claimed.add(key)
        events.append(
            AlertEvent(
                rule_id=rule.id,
                user_id=rule.user_id,
                telegram_id=rule.telegram_id,
                symbol=MARKET_SYMBOL,
                type=rule.type,
                threshold=thr,
                trigger=trigger,
                current_price=None,
                snapshot_id=None,
                event_key=key,
            )
        )
    return events
