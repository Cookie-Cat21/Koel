"""Unit tests for koel.ml.adjustments (no DB)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from koel.corporate_actions import CorporateAction
from koel.domain import DailyBar
from koel.ml.adjustments import (
    adjusted_bar,
    adjusted_bars_for_as_of,
    bar_adjustment_factor,
    validate_price_adjustment,
)


def _bar(
    trade_date: date,
    *,
    price: float = 100.0,
    volume: float | None = 1000.0,
) -> DailyBar:
    return DailyBar(
        symbol="TEST.N0000",
        trade_date=trade_date,
        price=price,
        high=price * 1.02,
        low=price * 0.98,
        open=price * 1.01,
        volume=volume,
        source_period=5,
        bar_ts=datetime(trade_date.year, trade_date.month, trade_date.day, 18, 30, tzinfo=UTC),
    )


def _action(effective_date: date, *, ratio_from: int = 1, ratio_to: int = 2) -> CorporateAction:
    return CorporateAction(
        symbol="TEST.N0000",
        effective_date=effective_date,
        kind="split",
        ratio_from=ratio_from,
        ratio_to=ratio_to,
    )


def test_validate_price_adjustment_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="price_adjustment must be one of"):
        validate_price_adjustment("forward")


def test_validate_price_adjustment_accepts_known() -> None:
    assert validate_price_adjustment(" Split ") == "split"
    assert validate_price_adjustment("NONE") == "none"


def test_bar_adjustment_factor_applies_only_when_effective_and_pre_trade() -> None:
    effective = date(2025, 8, 10)
    action = _action(effective, ratio_from=1, ratio_to=2)
    factor = 0.5  # 1/2 forward split

    # effective_date <= as_of and trade_date < effective_date -> apply
    assert bar_adjustment_factor(
        [action],
        trade_date=date(2025, 8, 9),
        as_of=date(2025, 8, 10),
    ) == pytest.approx(factor)

    # effective_date > as_of -> ignore (no lookahead)
    assert bar_adjustment_factor(
        [action],
        trade_date=date(2025, 8, 9),
        as_of=date(2025, 8, 9),
    ) == pytest.approx(1.0)

    # trade_date >= effective_date -> ignore (post-effective bar)
    assert bar_adjustment_factor(
        [action],
        trade_date=date(2025, 8, 10),
        as_of=date(2025, 8, 10),
    ) == pytest.approx(1.0)


def test_adjusted_bar_scales_price_and_volume() -> None:
    trade_date = date(2025, 8, 9)
    effective = date(2025, 8, 10)
    bar = _bar(trade_date, price=100.0, volume=2000.0)
    action = _action(effective, ratio_from=1, ratio_to=2)
    factor = 0.5

    out = adjusted_bar(bar, [action], as_of=effective)

    assert out.price == pytest.approx(bar.price * factor)
    assert out.high == pytest.approx(bar.high * factor)
    assert out.low == pytest.approx(bar.low * factor)
    assert out.open == pytest.approx(bar.open * factor)
    assert out.volume == pytest.approx(bar.volume / factor)
    assert out.trade_date == bar.trade_date
    assert out.symbol == bar.symbol


def test_adjusted_bars_for_as_of_empty_actions_returns_same_list() -> None:
    bars = [_bar(date(2025, 8, 7)), _bar(date(2025, 8, 8))]
    result = adjusted_bars_for_as_of(bars, [], as_of=date(2025, 8, 10))
    assert result is bars
