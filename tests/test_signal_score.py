"""Transparent Signal Board path scores — unit only."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from chime.domain import DailyBar
from chime.scenarios.guardrails import contains_buy_sell_language
from chime.signals.eval import evaluate_walk_forward
from chime.signals.forecast import forecast_path
from chime.signals.score import MODEL_VERSION, ExtraFactors, score_symbol_path


def _bars(prices: list[float], *, start: date | None = None) -> list[DailyBar]:
    day0 = start or date(2025, 8, 1)
    out: list[DailyBar] = []
    for i, price in enumerate(prices):
        d = day0 + timedelta(days=i)
        out.append(
            DailyBar(
                symbol="JKH.N0000",
                trade_date=d,
                price=price,
                high=price * 1.01,
                low=price * 0.99,
                open=None,
                volume=100_000.0 + i * 1000,
                source_period=5,
                bar_ts=datetime(d.year, d.month, d.day, 18, 30, tzinfo=UTC),
            )
        )
    return out


def test_score_uptrend_positive() -> None:
    prices = [10.0 + i * 0.2 for i in range(40)]
    result = score_symbol_path(_bars(prices))
    assert result is not None
    assert result.score > 0
    assert result.bar_count == 40
    assert result.model_version == MODEL_VERSION
    assert result.reasons
    for reason in result.reasons:
        assert not contains_buy_sell_language(reason)


def test_score_downtrend_negative() -> None:
    # Steep decline so momentum dominates the liquidity tilt.
    prices = [40.0 - i * 0.8 for i in range(40)]
    result = score_symbol_path(_bars(prices))
    assert result is not None
    assert result.score < 0


def test_score_too_few_bars() -> None:
    assert score_symbol_path(_bars([10.0, 10.1, 10.2])) is None


def test_reasons_never_invest_tips() -> None:
    result = score_symbol_path(_bars([10.0 + i * 0.1 for i in range(25)]))
    assert result is not None
    blob = " ".join(result.reasons).lower()
    assert "buy" not in blob
    assert "sell" not in blob
    assert "invest" not in blob


def test_score_includes_filing_yoy_reason() -> None:
    prices = [10.0 + i * 0.05 for i in range(25)]
    result = score_symbol_path(
        _bars(prices),
        extra=ExtraFactors(eps_yoy_pct=25.0, rev_yoy_pct=10.0),
    )
    assert result is not None
    assert result.components["eps_yoy_pct"] == 25.0
    assert any("EPS YoY" in r for r in result.reasons)
    assert result.score > score_symbol_path(_bars(prices)).score  # type: ignore[operator]


def test_score_sector_rs_reason() -> None:
    prices = [10.0 + i * 0.2 for i in range(30)]
    result = score_symbol_path(
        _bars(prices),
        extra=ExtraFactors(sector_peer_ret_20d=-0.05),
    )
    assert result is not None
    assert result.components["rs_gap_20d"] is not None
    assert any("sector peers" in r for r in result.reasons)


def test_volume_spike_component() -> None:
    bars = _bars([10.0 + i * 0.01 for i in range(25)])
    # Inflate last bar volume.
    last = bars[-1]
    bars[-1] = last.model_copy(update={"volume": 5_000_000.0})
    result = score_symbol_path(bars)
    assert result is not None
    assert result.components["vol_spike"] is not None
    assert result.components["vol_spike"] > 1.5
    assert any("volume" in r.lower() and "×" in r for r in result.reasons)


def test_range_and_aspi_components() -> None:
    prices = [10.0 + i * 0.05 for i in range(25)]
    bars = _bars(prices)
    # Widen ranges.
    bars = [
        b.model_copy(update={"high": b.price * 1.05, "low": b.price * 0.95})
        for b in bars
    ]
    result = score_symbol_path(
        bars,
        extra=ExtraFactors(aspi_change_pct=-1.0, financial_disclosure_share=0.8),
    )
    assert result is not None
    assert result.components["range_20d"] is not None
    assert result.components["range_20d"] > 0.03
    assert result.components["aspi_gap_1d"] is not None
    assert any("ASPI" in r for r in result.reasons)
    assert any("Financial-category" in r for r in result.reasons)


def test_forecast_path_projects_forward() -> None:
    prices = [10.0 + i * 0.1 for i in range(20)]
    points = forecast_path(_bars(prices), horizon=5)
    assert len(points) == 5
    assert points[0].horizon_i == 1
    assert points[-1].yhat > prices[-1]


def test_forecast_path_too_short() -> None:
    assert forecast_path(_bars([10.0, 10.1, 10.2]), horizon=5) == []


def test_walk_forward_eval_runs() -> None:
    # Strong uptrend — forecast should often match direction.
    prices = [10.0 + i * 0.15 for i in range(80)]
    report = evaluate_walk_forward(
        {"JKH.N0000": _bars(prices)},
        horizon=5,
        min_history=30,
        step=5,
    )
    assert report.symbols == 1
    assert report.origins > 0
    assert report.direction_total > 0
    assert report.hit_rate is not None
    assert report.hit_rate >= 0.5
    assert report.mae is not None and report.mae >= 0
