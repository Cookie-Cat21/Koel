"""Walk-forward evaluation for the naive path forecast (leakage-safe).

For each symbol series, at each origin ``t`` with enough history, forecast
``horizon`` steps from bars ``[:t+1]`` and compare direction / error vs
realized future closes. No future bars enter the feature window.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from koel.domain import DailyBar
from koel.signals.forecast import FORECAST_HORIZON, forecast_path


@dataclass(frozen=True, slots=True)
class WalkForwardReport:
    symbols: int
    origins: int
    direction_hits: int
    direction_total: int
    mae: float | None
    hit_rate: float | None
    horizon: int

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _mae(errors: list[float]) -> float | None:
    if not errors:
        return None
    return sum(errors) / len(errors)


def evaluate_walk_forward(
    series_by_symbol: dict[str, list[DailyBar]],
    *,
    horizon: int = FORECAST_HORIZON,
    min_history: int = 25,
    step: int = 5,
) -> WalkForwardReport:
    """Evaluate forecast direction + MAE across symbols.

    ``step`` skips origins for speed (every Nth bar after ``min_history``).
    """
    if horizon < 1 or min_history < 6 or step < 1:
        return WalkForwardReport(0, 0, 0, 0, None, None, horizon)

    origins = 0
    hits = 0
    total_dir = 0
    abs_errors: list[float] = []
    symbols_used = 0

    for _symbol, bars in series_by_symbol.items():
        ordered = sorted(bars, key=lambda b: b.trade_date)
        if len(ordered) < min_history + horizon:
            continue
        symbols_used += 1
        last_origin = len(ordered) - horizon - 1
        for t in range(min_history - 1, last_origin + 1, step):
            window = ordered[: t + 1]
            future = ordered[t + 1 : t + 1 + horizon]
            if len(future) < horizon:
                continue
            preds = forecast_path(window, horizon=horizon)
            if len(preds) < horizon:
                continue
            origins += 1
            last_price = window[-1].price
            # Direction of final horizon vs start.
            pred_end = preds[-1].yhat
            real_end = future[-1].price
            if (
                math.isfinite(last_price)
                and math.isfinite(pred_end)
                and math.isfinite(real_end)
                and last_price != 0
            ):
                pred_dir = pred_end - last_price
                real_dir = real_end - last_price
                if pred_dir == 0 or real_dir == 0:
                    pass
                else:
                    total_dir += 1
                    if (pred_dir > 0 and real_dir > 0) or (
                        pred_dir < 0 and real_dir < 0
                    ):
                        hits += 1
            for pred, real_bar in zip(preds, future, strict=False):
                if math.isfinite(pred.yhat) and math.isfinite(real_bar.price):
                    abs_errors.append(abs(pred.yhat - real_bar.price))

    hit_rate = (hits / total_dir) if total_dir else None
    return WalkForwardReport(
        symbols=symbols_used,
        origins=origins,
        direction_hits=hits,
        direction_total=total_dir,
        mae=_mae(abs_errors),
        hit_rate=hit_rate,
        horizon=horizon,
    )
