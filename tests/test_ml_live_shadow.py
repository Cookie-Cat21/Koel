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
