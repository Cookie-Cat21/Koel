"""Point-in-time-safe corporate-action adjustments for ML bars."""

from __future__ import annotations

import math
from datetime import date

from koel.corporate_actions import CorporateAction, adjust_factor
from koel.domain import DailyBar

PRICE_ADJUSTMENTS = ("none", "split")


def validate_price_adjustment(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in PRICE_ADJUSTMENTS:
        allowed = ", ".join(PRICE_ADJUSTMENTS)
        raise ValueError(f"price_adjustment must be one of: {allowed}")
    return normalized


def bar_adjustment_factor(
    actions: list[CorporateAction],
    *,
    trade_date: date,
    as_of: date,
) -> float:
    """Scale a bar using only actions already effective by ``as_of``."""
    factor = 1.0
    for action in actions:
        if action.effective_date <= as_of and trade_date < action.effective_date:
            factor *= adjust_factor(action.ratio_from, action.ratio_to)
    return factor


def adjusted_bar(
    bar: DailyBar,
    actions: list[CorporateAction],
    *,
    as_of: date,
) -> DailyBar:
    factor = bar_adjustment_factor(
        actions,
        trade_date=bar.trade_date,
        as_of=as_of,
    )
    if factor == 1.0:
        return bar

    def scaled_price(value: float | None) -> float | None:
        if value is None:
            return None
        scaled = float(value) * factor
        return scaled if math.isfinite(scaled) else None

    def scaled_volume(value: float | None) -> float | None:
        if value is None or factor <= 0:
            return value
        scaled = float(value) / factor
        return scaled if math.isfinite(scaled) else None

    return bar.model_copy(
        update={
            "price": bar.price * factor,
            "high": scaled_price(bar.high),
            "low": scaled_price(bar.low),
            "open": scaled_price(bar.open),
            "volume": scaled_volume(bar.volume),
        }
    )


def adjusted_bars_for_as_of(
    bars: list[DailyBar],
    actions: list[CorporateAction],
    *,
    as_of: date,
) -> list[DailyBar]:
    if not actions:
        return bars
    ordered_actions = sorted(actions, key=lambda action: action.effective_date)
    return [adjusted_bar(bar, ordered_actions, as_of=as_of) for bar in bars]
