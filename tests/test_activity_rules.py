"""Activity alert rule engine — volume / gap / big print / notices."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from koel.domain import (
    AlertRule,
    AlertType,
    BigPrint,
    MarketNotice,
    PreviousPriceState,
    PriceSnapshot,
)
from koel.rules import (
    evaluate_big_print_rules,
    evaluate_notice_rules,
    evaluate_price_rules,
    filter_fireable,
)


def _snap(**kwargs: object) -> PriceSnapshot:
    base = {
        "symbol": "JKH.N0000",
        "price": 20.0,
        "previous_close": 19.0,
        "change": 1.0,
        "change_pct": 5.26,
        "volume": 1_000_000.0,
        "crossing_volume": 500_000.0,
        "open": 19.5,
        "ts": datetime(2026, 7, 13, 5, 0, tzinfo=UTC),
        "id": 42,
    }
    base.update(kwargs)
    return PriceSnapshot.model_validate(base)


def _rule(
    alert_type: AlertType,
    *,
    threshold: float | None = 3.0,
    created_at: datetime | None = None,
) -> AlertRule:
    return AlertRule(
        id=7,
        user_id=1,
        telegram_id=99,
        symbol="JKH.N0000",
        type=alert_type,
        threshold=threshold,
        active=True,
        armed=True,
        created_at=created_at or datetime(2026, 7, 1, tzinfo=UTC),
    )


def test_volume_spike_fires_when_multiple_of_avg() -> None:
    events = evaluate_price_rules(
        snapshot=_snap(volume=900_000),
        previous=PreviousPriceState(
            price=19.5,
            change_pct=2.0,
            avg_volume=100_000.0,
            activity_fired_keys=set(),
        ),
        rules=[_rule(AlertType.VOLUME_SPIKE, threshold=5.0)],
    )
    fireable = filter_fireable(events)
    assert len(fireable) == 1
    assert fireable[0].event_key.startswith("volspike:7:")
    assert "unusual volume" in fireable[0].trigger


def test_volume_spike_skips_without_avg_baseline() -> None:
    events = evaluate_price_rules(
        snapshot=_snap(volume=900_000),
        previous=PreviousPriceState(price=19.5, avg_volume=None),
        rules=[_rule(AlertType.VOLUME_SPIKE, threshold=2.0)],
    )
    assert filter_fireable(events) == []


def test_volume_up_requires_positive_change() -> None:
    rules = [_rule(AlertType.VOLUME_UP, threshold=2.0)]
    prev = PreviousPriceState(price=20.0, avg_volume=100_000.0)
    up = evaluate_price_rules(
        snapshot=_snap(volume=300_000, change_pct=3.0),
        previous=prev,
        rules=rules,
    )
    down = evaluate_price_rules(
        snapshot=_snap(volume=300_000, change_pct=-3.0, price=18.0),
        previous=prev,
        rules=rules,
    )
    assert len(filter_fireable(up)) == 1
    assert filter_fireable(down) == []


def test_volume_down_requires_negative_change() -> None:
    rules = [_rule(AlertType.VOLUME_DOWN, threshold=2.0)]
    prev = PreviousPriceState(price=20.0, avg_volume=100_000.0)
    events = evaluate_price_rules(
        snapshot=_snap(volume=300_000, change_pct=-4.0, price=18.0),
        previous=prev,
        rules=rules,
    )
    assert len(filter_fireable(events)) == 1
    assert "heavy volume down" in events[0].trigger


def test_crossing_volume_spike() -> None:
    events = evaluate_price_rules(
        snapshot=_snap(crossing_volume=800_000),
        previous=PreviousPriceState(
            price=20.0,
            avg_crossing_volume=100_000.0,
        ),
        rules=[_rule(AlertType.CROSSING_VOLUME, threshold=4.0)],
    )
    fireable = filter_fireable(events)
    assert len(fireable) == 1
    assert fireable[0].event_key.startswith("xvol:7:")


def test_gap_alert_fires_on_open_vs_prev_close() -> None:
    # open 22 vs prev 20 = 10% gap
    events = evaluate_price_rules(
        snapshot=_snap(open=22.0, previous_close=20.0, price=22.0),
        previous=PreviousPriceState(price=20.0),
        rules=[_rule(AlertType.GAP, threshold=5.0)],
    )
    fireable = filter_fireable(events)
    assert len(fireable) == 1
    assert "gap up" in fireable[0].trigger


def test_activity_day_key_dedup() -> None:
    key = "volspike:7:2026-07-13"
    events = evaluate_price_rules(
        snapshot=_snap(volume=900_000),
        previous=PreviousPriceState(
            price=19.5,
            avg_volume=100_000.0,
            activity_fired_keys={key},
        ),
        rules=[_rule(AlertType.VOLUME_SPIKE, threshold=5.0)],
    )
    assert filter_fireable(events) == []


def test_big_print_fires_above_threshold() -> None:
    created = datetime(2026, 7, 1, tzinfo=UTC)
    bp = BigPrint(
        external_id="57215840",
        symbol="JKH.N0000",
        price=20.1,
        quantity=50_000,
        traded_at=created + timedelta(days=5),
        seen_at=created + timedelta(days=5),
    )
    events = evaluate_big_print_rules(
        print_=bp,
        rules=[_rule(AlertType.BIG_PRINT, threshold=10_000, created_at=created)],
    )
    assert len(events) == 1
    assert events[0].event_key == "bigprint:7:57215840"


def test_big_print_skips_below_threshold_and_backfill() -> None:
    created = datetime(2026, 7, 10, tzinfo=UTC)
    small = BigPrint(
        external_id="1",
        symbol="JKH.N0000",
        quantity=100,
        traded_at=created + timedelta(hours=1),
        seen_at=created + timedelta(hours=1),
    )
    old = BigPrint(
        external_id="2",
        symbol="JKH.N0000",
        quantity=50_000,
        traded_at=created - timedelta(days=1),
        seen_at=created - timedelta(days=1),
    )
    rules = [_rule(AlertType.BIG_PRINT, threshold=10_000, created_at=created)]
    assert evaluate_big_print_rules(print_=small, rules=rules) == []
    assert evaluate_big_print_rules(print_=old, rules=rules) == []


def test_buy_in_notice_matches_symbol() -> None:
    created = datetime(2026, 7, 1, tzinfo=UTC)
    notice = MarketNotice(
        external_id="buy_in:99",
        notice_type="buy_in",
        symbol="JKH.N0000",
        title="Buy-in Board",
        url="https://www.cse.lk/announcements#99",
        published_at=created + timedelta(days=2),
    )
    events = evaluate_notice_rules(
        notice=notice,
        rules=[_rule(AlertType.BUY_IN, threshold=None, created_at=created)],
    )
    assert len(events) == 1
    assert "buy-in board" in events[0].trigger


def test_halt_notice_fires_for_market_rule() -> None:
    created = datetime(2026, 7, 1, tzinfo=UTC)
    notice = MarketNotice(
        external_id="halt:abc",
        notice_type="halt",
        symbol="MARKET",
        title="NOTICE",
        body="Trading extended",
        published_at=created + timedelta(hours=1),
    )
    rule = AlertRule(
        id=3,
        user_id=1,
        telegram_id=99,
        symbol="MARKET",
        type=AlertType.HALT,
        threshold=None,
        active=True,
        armed=True,
        created_at=created,
    )
    events = evaluate_notice_rules(notice=notice, rules=[rule])
    assert len(events) == 1
    assert events[0].event_key == "halt:3:halt:abc"
