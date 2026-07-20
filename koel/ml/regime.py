"""Deterministic market regime tags (rules, not ML)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class RegimeSnapshot:
    as_of: date
    trend: str  # up | flat | down
    vol: str  # high | low
    tag: str  # e.g. up_lowvol


def tag_regime(
    *,
    as_of: date,
    aspi_ret_20d: float | None,
    cross_section_dispersion: float | None = None,
) -> RegimeSnapshot:
    """Label a session from ASPI 20d return (+ optional dispersion)."""
    if aspi_ret_20d is None or not math.isfinite(aspi_ret_20d):
        trend = "flat"
    elif aspi_ret_20d > 0.02:
        trend = "up"
    elif aspi_ret_20d < -0.02:
        trend = "down"
    else:
        trend = "flat"

    if (
        cross_section_dispersion is not None
        and math.isfinite(cross_section_dispersion)
        and cross_section_dispersion > 0.025
    ):
        vol = "high"
    else:
        vol = "low"

    return RegimeSnapshot(as_of=as_of, trend=trend, vol=vol, tag=f"{trend}_{vol}")


async def aspi_ret_20d_as_of(storage, as_of: date) -> float | None:
    """ASPI 20-session return ending on/before ``as_of`` from daily_bars."""
    bars = await storage.list_daily_bars("ASPI")
    if not bars:
        return None
    closes = [b.price for b in bars if b.trade_date <= as_of and math.isfinite(b.price)]
    if len(closes) < 21:
        return None
    a, b = closes[-21], closes[-1]
    if a == 0:
        return None
    return (b / a) - 1.0
