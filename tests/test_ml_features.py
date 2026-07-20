"""ML feature / leakage unit tests (no sklearn required)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from koel.domain import DailyBar
from koel.ml.dataset import build_samples
from koel.ml.features import labels_at, path_features


def _bars(prices: list[float], *, start: date | None = None) -> list[DailyBar]:
    day0 = start or date(2025, 8, 1)
    out: list[DailyBar] = []
    for i, price in enumerate(prices):
        d = day0 + timedelta(days=i)
        out.append(
            DailyBar(
                symbol="TEST.N0000",
                trade_date=d,
                price=price,
                high=price * 1.01,
                low=price * 0.99,
                open=None,
                volume=1000.0 + i,
                source_period=5,
                bar_ts=datetime(d.year, d.month, d.day, 18, 30, tzinfo=UTC),
            )
        )
    return out


def test_path_features_uses_last_as_of() -> None:
    bars = _bars([10.0 + i * 0.1 for i in range(30)])
    feats = path_features(bars)
    assert feats is not None
    assert feats.as_of == bars[-1].trade_date
    assert len(feats.values) == 15


def test_labels_horizon() -> None:
    prices = [10.0, 11.0, 12.0, 9.0]
    lab = labels_at(prices, index=0, horizon=1)
    assert lab is not None
    ret, direction = lab
    assert abs(ret - 0.1) < 1e-9
    assert direction == 1.0
    lab5 = labels_at(prices, index=0, horizon=5)
    assert lab5 is None


def test_build_samples_no_future_in_features() -> None:
    """Mutating future prices must not change feature vectors for past as_of."""
    prices = [10.0 + i * 0.05 for i in range(80)]
    bars = _bars(prices)
    samples = build_samples({"TEST.N0000": bars}, horizon=1, min_history=60)
    assert samples
    # Take a mid sample
    mid = samples[len(samples) // 2]
    # Rebuild with poisoned future prices after mid.as_of
    poisoned = []
    for b in bars:
        if b.trade_date > mid.as_of:
            poisoned.append(b.model_copy(update={"price": b.price * 10}))
        else:
            poisoned.append(b)
    samples2 = build_samples({"TEST.N0000": poisoned}, horizon=1, min_history=60)
    match = [s for s in samples2 if s.as_of == mid.as_of]
    assert match
    assert match[0].x == mid.x


def test_sklearn_available_helper() -> None:
    from koel.ml import sklearn_available

    # Just ensure callable; may be True/False depending on env.
    assert isinstance(sklearn_available(), bool)
