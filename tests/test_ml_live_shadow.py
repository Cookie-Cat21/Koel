"""Prospective live shadow helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime

from koel.domain import DailyBar, PriceSnapshot
from koel.ml.live_shadow import (
    append_live_board,
    policy_instance_version,
    summarize_pressure_factors,
)


def test_append_live_board_replaces_session_and_ignores_unknown_symbols() -> None:
    prior = DailyBar(
        symbol="A.N0000",
        trade_date=date(2026, 7, 20),
        price=10.0,
        high=10.0,
        low=10.0,
        open=10.0,
        volume=100.0,
        source_period=5,
        bar_ts=datetime(2026, 7, 20, tzinfo=UTC),
    )
    board = [
        PriceSnapshot(
            symbol="A.N0000",
            price=11.0,
            high=11.2,
            low=10.8,
            open=10.9,
            volume=200.0,
            ts=datetime(2026, 7, 21, 8, tzinfo=UTC),
        ),
        PriceSnapshot(
            symbol="RIGHT.R0001",
            price=2.0,
            ts=datetime(2026, 7, 21, 8, tzinfo=UTC),
        ),
    ]
    result = append_live_board(
        {"A.N0000": [prior]},
        board,
        trade_date=date(2026, 7, 21),
    )
    assert set(result) == {"A.N0000"}
    assert len(result["A.N0000"]) == 2
    assert result["A.N0000"][-1].price == 11.0
    assert result["A.N0000"][-1].source_period == 5


def test_pressure_summary_combines_book_and_signed_volume() -> None:
    t0 = datetime(2026, 7, 21, 7, 0, tzinfo=UTC)
    t1 = datetime(2026, 7, 21, 7, 1, tzinfo=UTC)
    factors = summarize_pressure_factors(
        [
            {
                "symbol": "A.N0000",
                "total_bids": 300.0,
                "total_asks": 100.0,
                "ts": t0,
            },
            {
                "symbol": "A.N0000",
                "total_bids": 200.0,
                "total_asks": 200.0,
                "ts": t1,
            },
        ],
        [
            {"symbol": "A.N0000", "price": 10.0, "volume": 100.0, "ts": t0},
            {"symbol": "A.N0000", "price": 11.0, "volume": 150.0, "ts": t1},
        ],
    )["A.N0000"]
    assert factors.book_median == 0.25
    assert factors.book_persistence == 0.5
    assert factors.book_slope == -0.5
    assert factors.signed_volume_proxy == 1.0


def test_policy_instance_version_binds_snapshot_and_revision() -> None:
    kwargs = {
        "policy_id": "policy-v1",
        "snapshot_sha256": "a" * 64,
        "issue_session": date(2026, 7, 21),
        "revision": "abc123",
    }
    first = policy_instance_version(**kwargs)
    assert first == policy_instance_version(**kwargs)
    assert first != policy_instance_version(
        **{**kwargs, "snapshot_sha256": "b" * 64}
    )
    assert first != policy_instance_version(
        **{**kwargs, "revision": "def456"}
    )


def test_parse_holding_age_from_regime_tag() -> None:
    from koel.ml.live_shadow import _parse_holding_age

    assert _parse_holding_age(None) == 1
    assert _parse_holding_age("live_shadow|age=4|side=long") == 4
    assert _parse_holding_age("no-age-here") == 1


def test_relative_training_samples_demean_and_drop_flats() -> None:
    from datetime import UTC, date, datetime, timedelta

    from koel.domain import DailyBar
    from koel.ml.live_shadow import _relative_training_samples
    from koel.ml.snapshot import LoadedSnapshot, SnapshotManifest

    def make_series(symbol: str, start: float, drift: float) -> list[DailyBar]:
        bars: list[DailyBar] = []
        price = start
        day = date(2024, 1, 2)
        for i in range(280):
            # skip weekends roughly
            while day.weekday() >= 5:
                day += timedelta(days=1)
            price = max(1.0, price * (1.0 + drift + ((i % 7) - 3) * 0.001))
            bars.append(
                DailyBar(
                    symbol=symbol,
                    trade_date=day,
                    price=price,
                    high=price * 1.01,
                    low=price * 0.99,
                    open=price,
                    volume=1000.0 + i,
                    source_period=5,
                    bar_ts=datetime(day.year, day.month, day.day, tzinfo=UTC),
                )
            )
            day += timedelta(days=1)
        return bars

    series = {
        "AAA.N0000": make_series("AAA.N0000", 10.0, 0.002),
        "BBB.N0000": make_series("BBB.N0000", 20.0, -0.001),
        "CCC.N0000": make_series("CCC.N0000", 15.0, 0.0005),
    }
    manifest = SnapshotManifest(
        schema_version=2,
        dataset="hybrid",
        created_at="2026-07-23T00:00:00+00:00",
        postgres_snapshot="",
        bars_file="bars.jsonl.gz",
        bars_sha256="",
        fundamentals_file="fundamentals.jsonl.gz",
        fundamentals_sha256="",
        fundamentals_rows=0,
        fundamentals_columns=(),
        columns=(),
        rows=sum(len(v) for v in series.values()),
        symbols=len(series),
        first_date="2024-01-02",
        last_date="2025-01-01",
        source_rows={"cse": 1},
        quality={},
        price_adjustment="none",
    )
    loaded = LoadedSnapshot(
        manifest=manifest,
        series=series,
        fundamentals={},
        corporate_actions={},
    )
    samples = _relative_training_samples(loaded)
    assert samples
    # Relative labels should be demeaned within day => mean y_ret ~0 per day
    from collections import defaultdict
    from statistics import fmean

    by_day: dict[date, list[float]] = defaultdict(list)
    for sample in samples:
        by_day[sample.as_of].append(sample.y_ret)
    # At least some multi-name days with near-zero mean
    checked = 0
    for values in by_day.values():
        if len(values) >= 2:
            assert abs(fmean(values)) < 1e-9
            checked += 1
    assert checked >= 1
