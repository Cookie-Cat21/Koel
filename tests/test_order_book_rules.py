"""Public order-book imbalance alert evaluation."""

from __future__ import annotations

from datetime import UTC, datetime

from chime.adapters.cse import (
    OrderBookLevel,
    OrderBookTotal,
    order_book_to_snapshot,
)
from chime.bot import parse_alert_args
from chime.domain import AlertRule, AlertType, OrderBookSnapshot
from chime.rules import evaluate_order_book_rules, filter_fireable


def _book(*, bids: float, asks: float) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        symbol="JKH.N0000",
        total_bids=bids,
        total_asks=asks,
        best_bid=19.9,
        best_bid_qty=1000.0,
        ts=datetime(2026, 7, 13, 5, 0, tzinfo=UTC),
        id=1,
    )


def _rule(alert_type: AlertType, thr: float = 1.5) -> AlertRule:
    return AlertRule(
        id=9,
        user_id=1,
        telegram_id=99,
        symbol="JKH.N0000",
        type=alert_type,
        threshold=thr,
        active=True,
        armed=True,
        created_at=datetime(2026, 7, 1, tzinfo=UTC),
    )


def test_ask_heavy_fires_when_asks_dominate() -> None:
    events = evaluate_order_book_rules(
        book=_book(bids=100_000, asks=250_000),
        rules=[_rule(AlertType.ASK_HEAVY, 2.0)],
    )
    fireable = filter_fireable(events)
    assert len(fireable) == 1
    assert fireable[0].event_key.startswith("askheavy:9:")
    assert "ask-heavy" in fireable[0].trigger


def test_bid_heavy_fires_when_bids_dominate() -> None:
    events = evaluate_order_book_rules(
        book=_book(bids=300_000, asks=100_000),
        rules=[_rule(AlertType.BID_HEAVY, 2.5)],
    )
    assert len(filter_fireable(events)) == 1


def test_order_book_skips_below_threshold_and_zero_side() -> None:
    assert (
        evaluate_order_book_rules(
            book=_book(bids=100_000, asks=110_000),
            rules=[_rule(AlertType.ASK_HEAVY, 2.0)],
        )
        == []
    )
    assert (
        evaluate_order_book_rules(
            book=_book(bids=0, asks=100_000),
            rules=[_rule(AlertType.ASK_HEAVY, 1.1)],
        )
        == []
    )


def test_order_book_day_key_dedup() -> None:
    events = evaluate_order_book_rules(
        book=_book(bids=100_000, asks=300_000),
        rules=[_rule(AlertType.ASK_HEAVY, 2.0)],
        fired_keys={"askheavy:9:2026-07-13"},
    )
    assert events == []


def test_parse_book_alert_kinds() -> None:
    for args, typ in (
        (["JKH.N0000", "bidheavy", "2"], AlertType.BID_HEAVY),
        (["JKH.N0000", "askheavy", "1.5"], AlertType.ASK_HEAVY),
    ):
        parsed, err = parse_alert_args(args)
        assert err is None and parsed is not None
        assert parsed.alert_type == typ


def test_order_book_normalize_from_cse_shape() -> None:
    snap = order_book_to_snapshot(
        symbol="JKH.N0000",
        total=OrderBookTotal(totalBids=1_000_000, totalAsks=2_000_000),
        levels=[
            OrderBookLevel(buySell=1, price=19.9, quantity=5000.0),
        ],
    )
    assert snap is not None
    assert snap.total_bids == 1_000_000
    assert snap.total_asks == 2_000_000
    assert snap.best_bid == 19.9
