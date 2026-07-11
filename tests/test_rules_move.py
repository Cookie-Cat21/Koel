from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from chime.domain import AlertEvent, AlertType
from chime.rules import evaluate_price_rules, filter_fireable
from tests.conftest import make_previous, make_rule, make_snapshot

_COLOMBO = ZoneInfo("Asia/Colombo")


def test_filter_fireable_drops_rearm_only_events() -> None:
    rearm = AlertEvent(
        rule_id=1,
        user_id=10,
        telegram_id=1001,
        symbol="JKH.N0000",
        type=AlertType.PRICE_ABOVE,
        threshold=100.0,
        trigger="rearm",
        current_price=98.0,
        snapshot_id=21,
        event_key="rearm:1:21",
        set_armed=True,
    )
    fire = AlertEvent(
        rule_id=2,
        user_id=10,
        telegram_id=1001,
        symbol="JKH.N0000",
        type=AlertType.PRICE_BELOW,
        threshold=95.0,
        trigger="price crossed below 95.00",
        current_price=94.5,
        snapshot_id=22,
        event_key="price:2:below:95:s22",
        set_armed=False,
    )

    assert filter_fireable([rearm]) == []
    assert filter_fireable([rearm, fire]) == [fire]


def test_cross_above_threshold_fires() -> None:
    """prev |pct| below thr, curr at/above thr → fire."""
    rule = make_rule(type=AlertType.DAILY_MOVE, threshold=3.0)
    snap = make_snapshot(price=103.0, change_pct=3.0)
    events = evaluate_price_rules(
        snapshot=snap,
        previous=make_previous(price=100.0, change_pct=2.0),
        rules=[rule],
    )
    fireable = filter_fireable(events)
    assert len(fireable) == 1
    assert "up" in fireable[0].trigger
    day = snap.ts.astimezone(_COLOMBO).date().isoformat()
    assert fireable[0].event_key == f"move:{rule.id}:{day}"


def test_daily_move_exact_threshold_boundary() -> None:
    """E11-Q01: |pct| == thr fires; just-below does not (crossing semantics)."""
    rule = make_rule(type=AlertType.DAILY_MOVE, threshold=5.0)
    # Exact: prev 4.9 → curr 5.0
    fire_exact = filter_fireable(
        evaluate_price_rules(
            snapshot=make_snapshot(price=105.0, change_pct=5.0),
            previous=make_previous(price=104.9, change_pct=4.9),
            rules=[rule],
        )
    )
    assert len(fire_exact) == 1
    # Just below: prev 4.8 → curr 4.999 does not cross 5.0
    no_fire = filter_fireable(
        evaluate_price_rules(
            snapshot=make_snapshot(price=104.999, change_pct=4.999),
            previous=make_previous(price=104.8, change_pct=4.8),
            rules=[rule],
        )
    )
    assert no_fire == []


def test_cross_below_threshold_down_fires() -> None:
    rule = make_rule(type=AlertType.DAILY_MOVE, threshold=2.5)
    snap = make_snapshot(price=95.0, change_pct=-2.5)
    events = evaluate_price_rules(
        snapshot=snap,
        previous=make_previous(price=100.0, change_pct=-2.0),
        rules=[rule],
    )
    fireable = filter_fireable(events)
    assert len(fireable) == 1
    assert "down" in fireable[0].trigger


def test_already_exceeded_with_prev_above_no_fire() -> None:
    """Already over threshold on previous tick — no re-fire."""
    rule = make_rule(type=AlertType.DAILY_MOVE, threshold=3.0)
    snap = make_snapshot(price=110.0, change_pct=8.0)
    events = evaluate_price_rules(
        snapshot=snap,
        previous=make_previous(price=105.0, change_pct=5.0),
        rules=[rule],
    )
    assert filter_fireable(events) == []


def test_prev_change_pct_none_no_fire() -> None:
    """First observation / no previous pct — baseline only, no fire."""
    rule = make_rule(type=AlertType.DAILY_MOVE, threshold=3.0)
    snap = make_snapshot(price=110.0, change_pct=8.0)
    events = evaluate_price_rules(
        snapshot=snap,
        previous=make_previous(price=100.0, change_pct=None),
        rules=[rule],
    )
    assert filter_fireable(events) == []


def test_computes_pct_from_previous_close_when_change_pct_none() -> None:
    rule = make_rule(type=AlertType.DAILY_MOVE, threshold=5.0)
    # (110 - 100) / 100 * 100 = 10%
    snap = make_snapshot(price=110.0, previous_close=100.0, change_pct=None)
    events = evaluate_price_rules(
        snapshot=snap,
        previous=make_previous(price=100.0, change_pct=4.0),
        rules=[rule],
    )
    fireable = filter_fireable(events)
    assert len(fireable) == 1
    assert "10.00%" in fireable[0].trigger


def test_does_not_fire_when_move_fired_keys_has_day_key() -> None:
    rule = make_rule(id=9, type=AlertType.DAILY_MOVE, threshold=3.0)
    ts = datetime(2026, 7, 11, 8, 0, 0, tzinfo=UTC)
    day_key = f"move:9:{ts.astimezone(_COLOMBO).date().isoformat()}"
    snap = make_snapshot(price=110.0, change_pct=8.0, ts=ts)
    events = evaluate_price_rules(
        snapshot=snap,
        previous=make_previous(price=100.0, change_pct=2.0, move_fired_keys={day_key}),
        rules=[rule],
    )
    assert filter_fireable(events) == []


def test_missing_change_pct_and_previous_close_no_fire() -> None:
    rule = make_rule(type=AlertType.DAILY_MOVE, threshold=3.0)
    snap = make_snapshot(price=110.0, previous_close=None, change_pct=None)
    events = evaluate_price_rules(
        snapshot=snap,
        previous=make_previous(price=100.0, change_pct=1.0),
        rules=[rule],
    )
    assert events == []


def test_previous_close_zero_treated_as_missing() -> None:
    rule = make_rule(type=AlertType.DAILY_MOVE, threshold=3.0)
    snap = make_snapshot(price=110.0, previous_close=0.0, change_pct=None)
    events = evaluate_price_rules(
        snapshot=snap,
        previous=make_previous(price=100.0, change_pct=1.0),
        rules=[rule],
    )
    assert events == []


def test_daily_move_missing_threshold_skipped() -> None:
    rule = make_rule(type=AlertType.DAILY_MOVE, threshold=None)
    snap = make_snapshot(price=110.0, change_pct=8.0)
    events = evaluate_price_rules(
        snapshot=snap,
        previous=make_previous(price=100.0, change_pct=1.0),
        rules=[rule],
    )
    assert events == []


def test_event_key_pattern_once_per_day() -> None:
    rule = make_rule(id=5, type=AlertType.DAILY_MOVE, threshold=1.0)
    ts = datetime(2026, 7, 11, 10, 30, 0, tzinfo=UTC)
    snap = make_snapshot(price=101.0, change_pct=1.5, ts=ts, id=99)
    events = evaluate_price_rules(
        snapshot=snap,
        previous=make_previous(price=100.0, change_pct=0.5),
        rules=[rule],
    )
    assert len(events) == 1
    assert events[0].event_key == "move:5:2026-07-11"


def test_move_event_key_uses_colombo_calendar_day() -> None:
    """UTC evening can still be next Colombo morning — key must use SLT date."""
    rule = make_rule(id=7, type=AlertType.DAILY_MOVE, threshold=1.0)
    # 2026-07-10 20:00 UTC == 2026-07-11 01:30 Asia/Colombo
    ts = datetime(2026, 7, 10, 20, 0, 0, tzinfo=UTC)
    snap = make_snapshot(price=101.0, change_pct=1.5, ts=ts, id=50)
    events = evaluate_price_rules(
        snapshot=snap,
        previous=make_previous(price=100.0, change_pct=0.5),
        rules=[rule],
    )
    assert len(events) == 1
    assert events[0].event_key == "move:7:2026-07-11"
    assert events[0].event_key != "move:7:2026-07-10"


def test_move_event_key_stays_colombo_day_across_utc_midnight() -> None:
    """E17-Q02: UTC midnight must not split one Colombo daily-move session."""
    rule = make_rule(id=8, type=AlertType.DAILY_MOVE, threshold=1.0)
    keys: list[str] = []

    for ts in (
        # Both are 2026-07-11 in Asia/Colombo, but different UTC dates.
        datetime(2026, 7, 10, 23, 59, 0, tzinfo=UTC),
        datetime(2026, 7, 11, 0, 1, 0, tzinfo=UTC),
    ):
        events = evaluate_price_rules(
            snapshot=make_snapshot(price=101.0, change_pct=1.5, ts=ts, id=50),
            previous=make_previous(price=100.0, change_pct=0.5),
            rules=[rule],
        )
        assert len(events) == 1
        keys.append(events[0].event_key)

    assert keys == ["move:8:2026-07-11", "move:8:2026-07-11"]
