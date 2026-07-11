"""CRITICAL crossing semantics for price_above / price_below rules."""

from __future__ import annotations

from datetime import UTC, datetime

from chime.domain import AlertType
from chime.rules import crossed_above, crossed_below, evaluate_price_rules, filter_fireable
from tests.conftest import make_previous, make_rule, make_snapshot


class TestCrossedAboveBelow:
    def test_crossed_above_basic(self) -> None:
        assert crossed_above(99.0, 100.0, 100.0) is True
        assert crossed_above(100.0, 101.0, 100.0) is False
        assert crossed_above(101.0, 102.0, 100.0) is False
        assert crossed_above(98.0, 99.0, 100.0) is False

    def test_crossed_below_basic(self) -> None:
        assert crossed_below(101.0, 100.0, 100.0) is True
        assert crossed_below(100.0, 99.0, 100.0) is False
        assert crossed_below(99.0, 98.0, 100.0) is False
        assert crossed_below(102.0, 101.0, 100.0) is False

    def test_prev_none_never_fires(self) -> None:
        assert crossed_above(None, 105.0, 100.0) is False
        assert crossed_below(None, 95.0, 100.0) is False

    def test_boundary_helpers_fire_on_first_touch_only(self) -> None:
        assert crossed_above(99.99, 100.0, 100.0) is True
        assert crossed_above(100.0, 100.01, 100.0) is False
        assert crossed_above(100.0, 100.0, 100.0) is False

        assert crossed_below(100.01, 100.0, 100.0) is True
        assert crossed_below(100.0, 99.99, 100.0) is False
        assert crossed_below(100.0, 100.0, 100.0) is False


class TestFirstSnapshotOfDay:
    def test_prev_none_must_not_fire_above(self) -> None:
        rule = make_rule(type=AlertType.PRICE_ABOVE, threshold=100.0)
        snap = make_snapshot(price=105.0)
        events = evaluate_price_rules(
            snapshot=snap,
            previous=make_previous(price=None),
            rules=[rule],
        )
        assert filter_fireable(events) == []

    def test_prev_none_must_not_fire_below(self) -> None:
        rule = make_rule(type=AlertType.PRICE_BELOW, threshold=100.0)
        snap = make_snapshot(price=95.0)
        events = evaluate_price_rules(
            snapshot=snap,
            previous=make_previous(price=None),
            rules=[rule],
        )
        assert filter_fireable(events) == []


class TestGapOpen:
    def test_gap_open_over_threshold_fires_above_once(self) -> None:
        rule = make_rule(type=AlertType.PRICE_ABOVE, threshold=100.0, armed=True)
        snap = make_snapshot(price=105.0, id=7)
        events = evaluate_price_rules(
            snapshot=snap,
            previous=make_previous(price=95.0),
            rules=[rule],
        )
        fireable = filter_fireable(events)
        assert len(fireable) == 1
        assert fireable[0].set_armed is False
        assert "above" in fireable[0].trigger
        assert fireable[0].event_key == "price:1:above:100:s7"

    def test_gap_open_under_threshold_fires_below(self) -> None:
        rule = make_rule(type=AlertType.PRICE_BELOW, threshold=100.0, armed=True)
        snap = make_snapshot(price=90.0, id=8)
        events = evaluate_price_rules(
            snapshot=snap,
            previous=make_previous(price=105.0),
            rules=[rule],
        )
        fireable = filter_fireable(events)
        assert len(fireable) == 1
        assert fireable[0].set_armed is False
        assert "below" in fireable[0].trigger


class TestStickyAndRecross:
    def test_sticky_above_disarmed_does_not_refire(self) -> None:
        rule = make_rule(type=AlertType.PRICE_ABOVE, threshold=100.0, armed=False)
        snap = make_snapshot(price=105.0)
        events = evaluate_price_rules(
            snapshot=snap,
            previous=make_previous(price=104.0),
            rules=[rule],
        )
        assert filter_fireable(events) == []
        assert events == []  # still above → no rearm either

    def test_rearm_then_recross_fires(self) -> None:
        rule = make_rule(type=AlertType.PRICE_ABOVE, threshold=100.0, armed=False)
        # Dip below threshold → rearm event
        dip = make_snapshot(price=98.0, id=10)
        rearm_events = evaluate_price_rules(
            snapshot=dip,
            previous=make_previous(price=102.0),
            rules=[rule],
        )
        assert len(rearm_events) == 1
        assert rearm_events[0].trigger == "rearm"
        assert rearm_events[0].set_armed is True
        assert filter_fireable(rearm_events) == []

        # After rearm, cross again → fire
        armed = make_rule(type=AlertType.PRICE_ABOVE, threshold=100.0, armed=True)
        cross = make_snapshot(price=101.0, id=11)
        fire_events = evaluate_price_rules(
            snapshot=cross,
            previous=make_previous(price=98.0),
            rules=[armed],
        )
        fireable = filter_fireable(fire_events)
        assert len(fireable) == 1
        assert fireable[0].set_armed is False
        assert fireable[0].event_key == "price:1:above:100:s11"

    def test_same_minute_same_price_recross_distinct_keys(self) -> None:
        """CORE-002: re-cross after re-arm at same minute+price gets a new key."""
        ts = datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC)
        first = make_rule(type=AlertType.PRICE_ABOVE, threshold=100.0, armed=True)
        snap1 = make_snapshot(price=105.0, id=30, ts=ts)
        key1 = filter_fireable(
            evaluate_price_rules(
                snapshot=snap1,
                previous=make_previous(price=95.0),
                rules=[first],
            )
        )[0].event_key

        rearmed = make_rule(type=AlertType.PRICE_ABOVE, threshold=100.0, armed=True)
        snap2 = make_snapshot(price=105.0, id=31, ts=ts)
        key2 = filter_fireable(
            evaluate_price_rules(
                snapshot=snap2,
                previous=make_previous(price=98.0),
                rules=[rearmed],
            )
        )[0].event_key

        assert key1 == "price:1:above:100:s30"
        assert key2 == "price:1:above:100:s31"
        assert key1 != key2


class TestExactTouch:
    def test_exact_touch_above(self) -> None:
        assert crossed_above(99.9, 100.0, 100.0) is True
        rule = make_rule(type=AlertType.PRICE_ABOVE, threshold=100.0)
        events = evaluate_price_rules(
            snapshot=make_snapshot(price=100.0),
            previous=make_previous(price=99.9),
            rules=[rule],
        )
        assert len(filter_fireable(events)) == 1

    def test_exact_touch_below(self) -> None:
        assert crossed_below(100.1, 100.0, 100.0) is True
        rule = make_rule(type=AlertType.PRICE_BELOW, threshold=100.0)
        events = evaluate_price_rules(
            snapshot=make_snapshot(price=100.0),
            previous=make_previous(price=100.1),
            rules=[rule],
        )
        assert len(filter_fireable(events)) == 1


class TestRuleFiltering:
    def test_wrong_symbol_ignored(self) -> None:
        rule = make_rule(symbol="COMB.N0000", type=AlertType.PRICE_ABOVE, threshold=100.0)
        events = evaluate_price_rules(
            snapshot=make_snapshot(symbol="JKH.N0000", price=105.0),
            previous=make_previous(price=95.0),
            rules=[rule],
        )
        assert events == []

    def test_inactive_rules_ignored(self) -> None:
        rule = make_rule(
            type=AlertType.PRICE_ABOVE,
            threshold=100.0,
            active=False,
        )
        events = evaluate_price_rules(
            snapshot=make_snapshot(price=105.0),
            previous=make_previous(price=95.0),
            rules=[rule],
        )
        assert events == []

    def test_above_rule_missing_threshold_skipped(self) -> None:
        rule = make_rule(type=AlertType.PRICE_ABOVE, threshold=None)
        events = evaluate_price_rules(
            snapshot=make_snapshot(price=105.0),
            previous=make_previous(price=95.0),
            rules=[rule],
        )
        assert events == []

    def test_below_rule_missing_threshold_skipped(self) -> None:
        rule = make_rule(type=AlertType.PRICE_BELOW, threshold=None)
        events = evaluate_price_rules(
            snapshot=make_snapshot(price=95.0),
            previous=make_previous(price=105.0),
            rules=[rule],
        )
        assert events == []

    def test_below_rearm_when_price_rises_back_above(self) -> None:
        rule = make_rule(type=AlertType.PRICE_BELOW, threshold=100.0, armed=False)
        events = evaluate_price_rules(
            snapshot=make_snapshot(price=105.0, id=20),
            previous=make_previous(price=98.0),
            rules=[rule],
        )
        assert len(events) == 1
        assert events[0].trigger == "rearm"
        assert events[0].set_armed is True
