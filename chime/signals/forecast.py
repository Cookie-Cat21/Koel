"""Path forecast from recent returns (research estimate · not a target).

``path_v2_fc``: blend 5d and 20d mean daily drifts; flatten when |drift|
is below a noise threshold (reduces coin-flip projections).
"""

from __future__ import annotations

import math
from datetime import UTC, timedelta

from chime.domain import DailyBar, ForecastPoint
from chime.signals.score import MODEL_VERSION

FORECAST_HORIZON = 5
FORECAST_MODEL_VERSION = f"{MODEL_VERSION}_fc"
# Below this absolute daily drift, project flat (no fake direction).
_MIN_ABS_DRIFT = 0.002


def forecast_path(
    bars: list[DailyBar],
    *,
    horizon: int = FORECAST_HORIZON,
) -> list[ForecastPoint]:
    """Project last close forward using blended recent daily drifts.

    Fail closed on short history / non-finite prices. Timestamps step +1
    calendar day in UTC from last bar (display-only; not session-aware).
    """
    if horizon < 1 or horizon > 30:
        return []
    if not bars or len(bars) < 6:
        return []
    ordered = sorted(bars, key=lambda b: b.trade_date)
    symbol = ordered[-1].symbol
    as_of = ordered[-1].trade_date
    prices = [b.price for b in ordered if math.isfinite(b.price)]
    if len(prices) < 6:
        return []

    def _mean_daily(window: int) -> float | None:
        if len(prices) <= window:
            return None
        rets: list[float] = []
        for i in range(-window, 0):
            prev, cur = prices[i - 1], prices[i]
            if prev == 0 or not math.isfinite(prev) or not math.isfinite(cur):
                continue
            rets.append((cur / prev) - 1.0)
        if len(rets) < max(3, window // 2):
            return None
        return sum(rets) / len(rets)

    d5 = _mean_daily(5)
    d20 = _mean_daily(20) if len(prices) > 20 else None
    if d5 is None and d20 is None:
        return []
    if d5 is not None and d20 is not None:
        mean_ret = 0.6 * d5 + 0.4 * d20
    elif d5 is not None:
        mean_ret = d5
    elif d20 is not None:
        mean_ret = d20
    else:  # unreachable — both-None returned [] above
        return []
    if not math.isfinite(mean_ret):
        return []
    mean_ret = max(-0.04, min(0.04, mean_ret))
    if abs(mean_ret) < _MIN_ABS_DRIFT:
        mean_ret = 0.0

    last_price = prices[-1]
    last_ts = ordered[-1].bar_ts
    if last_ts.tzinfo is None:
        last_ts = last_ts.replace(tzinfo=UTC)

    out: list[ForecastPoint] = []
    price = last_price
    for i in range(1, horizon + 1):
        price = price * (1.0 + mean_ret)
        if not math.isfinite(price) or price <= 0:
            break
        out.append(
            ForecastPoint(
                symbol=symbol,
                as_of=as_of,
                horizon_i=i,
                ts=last_ts + timedelta(days=i),
                yhat=price,
                model_version=FORECAST_MODEL_VERSION,
            )
        )
    return out
