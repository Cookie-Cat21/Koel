"""Extended leakage-safe finance metric tests."""

from __future__ import annotations

from datetime import date

import pytest

from koel.ml.metrics import (
    balanced_direction_accuracy,
    brier_score,
    cost_adjusted_top_bottom_spread,
    expected_calibration_error,
    gated_direction_stats,
    matthews_direction_correlation,
    spearman,
)


def test_spearman_uses_average_ranks_for_ties() -> None:
    assert spearman([0.0, 0.0, 1.0, 1.0], [1.0, 2.0, 3.0, 4.0]) == pytest.approx(
        0.8944271909999159
    )
    assert spearman([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) is None


def test_balanced_accuracy_and_mcc() -> None:
    actual = [1.0] * 5 + [-1.0] * 3
    scores = [1.0, 1.0, 1.0, -1.0, -1.0, -1.0, -1.0, 1.0]
    assert balanced_direction_accuracy(actual, scores) == pytest.approx(
        0.6333333333333333
    )
    assert matthews_direction_correlation(actual, scores) == pytest.approx(
        0.29814239699997197
    )


def test_brier_and_ece() -> None:
    outcomes = [True, True, False, False]
    probabilities = [0.9, 0.8, 0.2, 0.1]
    assert brier_score(outcomes, probabilities) == pytest.approx(0.025)
    assert expected_calibration_error(
        outcomes,
        probabilities,
        bins=2,
    ) == pytest.approx(0.15)


def test_flat_emission_counts_as_selective_miss() -> None:
    precision, emits, coverage = gated_direction_stats(
        [1.0, 0.0, -1.0],
        [0.5, 0.5, -0.5],
        threshold=0.1,
    )
    assert precision == pytest.approx(2 / 3)
    assert emits == 3
    assert coverage == 1.0


def test_cost_adjusted_spread_charges_initial_and_rebalance_trades() -> None:
    sessions = [date(2026, 1, 1)] * 4 + [date(2026, 1, 2)] * 4
    symbols = ["A", "B", "C", "D"] * 2
    scores = [-2.0, -1.0, 1.0, 2.0, 2.0, 1.0, -1.0, -2.0]
    returns = [-0.01, 0.0, 0.0, 0.01, 0.01, 0.0, 0.0, -0.01]
    result = cost_adjusted_top_bottom_spread(
        sessions,
        symbols,
        scores,
        returns,
        fraction=0.25,
        cost_bps=10.0,
        min_names=4,
    )
    assert result is not None
    assert result.sessions == 2
    assert result.mean_gross_return == pytest.approx(0.02)
    assert result.mean_one_way_turnover == pytest.approx(1.5)
    assert result.mean_net_return == pytest.approx(0.017)
