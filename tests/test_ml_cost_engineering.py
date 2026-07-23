from __future__ import annotations

from datetime import date, timedelta

import pytest

from koel.ml.cost_engineering import (
    PortfolioVariant,
    ScoreRow,
    evaluate_portfolio_variant,
)
from koel.ml.metrics import cost_adjusted_top_bottom_spread


def _rows_for_day(
    day: date,
    scores: dict[str, float],
    returns: dict[str, float] | None = None,
) -> list[ScoreRow]:
    returns = returns or {symbol: 0.0 for symbol in scores}
    return [
        ScoreRow(
            partition="test",
            as_of=day,
            symbol=symbol,
            score=score,
            y_ret=returns.get(symbol, 0.0),
        )
        for symbol, score in scores.items()
    ]


def test_daily_variant_matches_existing_cost_metric() -> None:
    sessions = [date(2026, 1, 1)] * 4 + [date(2026, 1, 2)] * 4
    symbols = ["A", "B", "C", "D"] * 2
    scores = [-2.0, -1.0, 1.0, 2.0, 2.0, 1.0, -1.0, -2.0]
    returns = [-0.01, 0.0, 0.0, 0.01, 0.01, 0.0, 0.0, -0.01]
    rows = [
        ScoreRow("test", session, symbol, score, ret)
        for session, symbol, score, ret in zip(
            sessions,
            symbols,
            scores,
            returns,
            strict=True,
        )
    ]

    expected = cost_adjusted_top_bottom_spread(
        sessions,
        symbols,
        scores,
        returns,
        fraction=0.25,
        cost_bps=10.0,
        min_names=4,
    )
    result = evaluate_portfolio_variant(
        rows,
        PortfolioVariant("daily_25", fraction=0.25, min_names=4),
        cost_bps=10.0,
    )

    assert expected is not None
    assert result is not None
    assert result.sessions == expected.sessions
    assert result.mean_gross_return == pytest.approx(expected.mean_gross_return)
    assert result.mean_net_return == pytest.approx(expected.mean_net_return)
    assert result.mean_one_way_turnover == pytest.approx(expected.mean_one_way_turnover)


def test_weekly_rebalance_holds_positions_between_refreshes() -> None:
    day1 = date(2026, 1, 1)
    day2 = day1 + timedelta(days=1)
    rows = _rows_for_day(
        day1,
        {"A": -2.0, "B": -1.0, "C": 1.0, "D": 2.0},
        {"A": -0.01, "D": 0.01},
    ) + _rows_for_day(
        day2,
        {"A": 2.0, "B": 1.0, "C": -1.0, "D": -2.0},
        {"A": -0.02, "D": 0.02},
    )

    result = evaluate_portfolio_variant(
        rows,
        PortfolioVariant("weekly", fraction=0.25, rebalance_every=5, min_names=4),
        cost_bps=0.0,
    )

    assert result is not None
    assert result.sessions == 2
    assert result.mean_gross_return == pytest.approx(0.03)
    assert result.mean_one_way_turnover == pytest.approx(0.5)


def test_persistence_keeps_names_until_exit_rank_breaks() -> None:
    day1 = date(2026, 1, 1)
    day2 = day1 + timedelta(days=1)
    symbols = [chr(ord("A") + index) for index in range(10)]
    day1_scores = {symbol: float(index) for index, symbol in enumerate(symbols)}
    day2_order = ["A", "C", "B", "D", "E", "F", "G", "I", "H", "J"]
    day2_scores = {symbol: float(index) for index, symbol in enumerate(day2_order)}
    rows = _rows_for_day(day1, day1_scores) + _rows_for_day(day2, day2_scores)

    daily = evaluate_portfolio_variant(
        rows,
        PortfolioVariant("daily", fraction=0.20, min_names=10),
        cost_bps=0.0,
    )
    persistent = evaluate_portfolio_variant(
        rows,
        PortfolioVariant(
            "persistent",
            fraction=0.20,
            persistence_exit_fraction=0.30,
            min_names=10,
        ),
        cost_bps=0.0,
    )

    assert daily is not None
    assert persistent is not None
    assert daily.mean_one_way_turnover == pytest.approx(1.0)
    assert persistent.mean_one_way_turnover == pytest.approx(0.5)


def test_minimum_holding_period_locks_positions() -> None:
    first = date(2026, 1, 1)
    rows: list[ScoreRow] = []
    for offset in range(3):
        rows.extend(
            _rows_for_day(
                first + timedelta(days=offset),
                {"A": 2.0, "B": 1.0, "C": -1.0, "D": -2.0}
                if offset
                else {"A": -2.0, "B": -1.0, "C": 1.0, "D": 2.0},
                {"A": -0.01, "D": 0.01},
            )
        )

    result = evaluate_portfolio_variant(
        rows,
        PortfolioVariant(
            "min_hold",
            fraction=0.25,
            min_holding_period=3,
            min_names=4,
        ),
        cost_bps=0.0,
    )

    assert result is not None
    assert result.sessions == 3
    assert result.mean_gross_return == pytest.approx(0.02)
    assert result.mean_one_way_turnover == pytest.approx(1 / 3)


def test_delayed_rebalance_applies_prior_session_scores() -> None:
    day1 = date(2026, 1, 1)
    day2 = day1 + timedelta(days=1)
    rows = _rows_for_day(
        day1,
        {"A": -2.0, "B": -1.0, "C": 1.0, "D": 2.0},
    ) + _rows_for_day(
        day2,
        {"A": 2.0, "B": 1.0, "C": -1.0, "D": -2.0},
        {"A": -0.02, "D": 0.02},
    )

    result = evaluate_portfolio_variant(
        rows,
        PortfolioVariant(
            "delayed",
            fraction=0.25,
            rebalance_delay=1,
            min_names=4,
        ),
        cost_bps=0.0,
    )

    assert result is not None
    assert result.sessions == 1
    assert result.mean_gross_return == pytest.approx(0.04)
    assert result.mean_one_way_turnover == pytest.approx(1.0)
