"""W2 H1 alert types: high_52w / low_52w / ma_cross / ref_move."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from koel.dividends import iso_week_key
from koel.domain import AlertType, DailyBar
from koel.rules import evaluate_price_rules, filter_fireable, sma, week52_range
from tests.conftest import make_previous, make_rule, make_snapshot

_COLOMBO = ZoneInfo("Asia/Colombo")


def _bar(
    day: date,
    price: float,
    *,
    high: float | None = None,
    low: float | None = None,
) -> DailyBar:
    return DailyBar(
        symbol="JKH.N0000",
        trade_date=day,
        price=price,
        high=high if high is not None else price,
        low=low if low is not None else price,
        source_period=2,
        bar_ts=datetime(day.year, day.month, day.day, 14, 30, tzinfo=_COLOMBO),
    )


def test_sma_requires_full_window() -> None:
    assert sma([1.0, 2.0, 3.0], 3) == 2.0
    assert sma([1.0, 2.0], 3) is None
    assert sma([1.0, float("nan"), 3.0], 3) is None


def test_week52_range_uses_high_low() -> None:
    bars = [
        _bar(date(2025, 1, 1), 100.0, high=110.0, low=90.0),
        _bar(date(2025, 1, 2), 105.0, high=120.0, low=95.0),
        _bar(date(2025, 1, 3), 102.0, high=108.0, low=85.0),
    ]
    hi, lo = week52_range(bars)
    assert hi == 120.0
    assert lo == 85.0


def test_high_52w_fires_on_new_high_crossing() -> None:
    rule = make_rule(id=1, type=AlertType.HIGH_52W, threshold=None)
    snap = make_snapshot(price=121.0, id=10)
    events = filter_fireable(
        evaluate_price_rules(
            snapshot=snap,
            previous=make_previous(price=119.0, high_52w=120.0),
            rules=[rule],
        )
    )
    assert len(events) == 1
    assert "52-week high" in events[0].trigger
    week = iso_week_key(snap.ts.astimezone(_COLOMBO).date())
    assert events[0].event_key == f"h52w:{rule.id}:{week}"


def test_high_52w_skips_when_prev_already_above() -> None:
    rule = make_rule(id=2, type=AlertType.HIGH_52W, threshold=None)
    events = filter_fireable(
        evaluate_price_rules(
            snapshot=make_snapshot(price=122.0),
            previous=make_previous(price=121.0, high_52w=120.0),
            rules=[rule],
        )
    )
    assert events == []


def test_high_52w_weekly_dedup() -> None:
    rule = make_rule(id=3, type=AlertType.HIGH_52W, threshold=None)
    snap = make_snapshot(price=130.0)
    week = iso_week_key(snap.ts.astimezone(_COLOMBO).date())
    key = f"h52w:{rule.id}:{week}"
    events = filter_fireable(
        evaluate_price_rules(
            snapshot=snap,
            previous=make_previous(
                price=119.0,
                high_52w=120.0,
                activity_fired_keys={key},
            ),
            rules=[rule],
        )
    )
    assert events == []


def test_low_52w_fires_on_new_low_crossing() -> None:
    rule = make_rule(id=4, type=AlertType.LOW_52W, threshold=None)
    snap = make_snapshot(price=79.0, id=11)
    events = filter_fireable(
        evaluate_price_rules(
            snapshot=snap,
            previous=make_previous(price=81.0, low_52w=80.0),
            rules=[rule],
        )
    )
    assert len(events) == 1
    assert "52-week low" in events[0].trigger
    week = iso_week_key(snap.ts.astimezone(_COLOMBO).date())
    assert events[0].event_key == f"l52w:{rule.id}:{week}"


def test_low_52w_skips_missing_bars() -> None:
    rule = make_rule(id=5, type=AlertType.LOW_52W, threshold=None)
    events = filter_fireable(
        evaluate_price_rules(
            snapshot=make_snapshot(price=50.0),
            previous=make_previous(price=55.0, low_52w=None),
            rules=[rule],
        )
    )
    assert events == []


def test_ma_cross_above_and_rearm() -> None:
    rule = make_rule(id=6, type=AlertType.MA_CROSS, threshold=20.0, armed=True)
    fire = filter_fireable(
        evaluate_price_rules(
            snapshot=make_snapshot(price=100.0, id=20),
            previous=make_previous(price=98.0, sma_by_period={20: 99.0}),
            rules=[rule],
        )
    )
    assert len(fire) == 1
    assert "crossed above 20-day MA (99.00)" in fire[0].trigger
    assert fire[0].set_armed is False

    rearm_events = evaluate_price_rules(
        snapshot=make_snapshot(price=97.0, id=21),
        previous=make_previous(price=100.0, sma_by_period={20: 99.0}),
        rules=[make_rule(id=6, type=AlertType.MA_CROSS, threshold=20.0, armed=False)],
    )
    assert any(e.trigger == "rearm" and e.set_armed is True for e in rearm_events)
    assert filter_fireable(rearm_events) == []


def test_ma_cross_below() -> None:
    rule = make_rule(id=7, type=AlertType.MA_CROSS, threshold=50.0, armed=True)
    fire = filter_fireable(
        evaluate_price_rules(
            snapshot=make_snapshot(price=49.0, id=22),
            previous=make_previous(price=51.0, sma_by_period={50: 50.0}),
            rules=[rule],
        )
    )
    assert len(fire) == 1
    assert "crossed below 50-day MA (50.00)" in fire[0].trigger


def test_ma_cross_skips_bad_period_or_missing_sma() -> None:
    bad_period = make_rule(id=8, type=AlertType.MA_CROSS, threshold=21.0, armed=True)
    missing = make_rule(id=9, type=AlertType.MA_CROSS, threshold=200.0, armed=True)
    events = filter_fireable(
        evaluate_price_rules(
            snapshot=make_snapshot(price=100.0),
            previous=make_previous(price=90.0, sma_by_period={20: 95.0}),
            rules=[bad_period, missing],
        )
    )
    assert events == []


def test_ref_move_crossing_fires_once_per_day_key() -> None:
    rule = make_rule(
        id=10,
        type=AlertType.REF_MOVE,
        threshold=5.0,
        ref_price=100.0,
    )
    snap = make_snapshot(price=106.0, id=30)
    # prev abs pct from ref = 4%; curr = 6% → crosses 5
    fire = filter_fireable(
        evaluate_price_rules(
            snapshot=snap,
            previous=make_previous(price=104.0),
            rules=[rule],
        )
    )
    assert len(fire) == 1
    assert "ref move up" in fire[0].trigger
    assert fire[0].ref_price == 100.0
    day = snap.ts.astimezone(_COLOMBO).date().isoformat()
    assert fire[0].event_key == f"refmove:{rule.id}:{day}"

    # Already claimed for the day
    deduped = filter_fireable(
        evaluate_price_rules(
            snapshot=make_snapshot(price=110.0, id=31),
            previous=make_previous(
                price=106.0,
                activity_fired_keys={f"refmove:{rule.id}:{day}"},
            ),
            rules=[rule],
        )
    )
    assert deduped == []


def test_ref_move_baseline_only_no_fire() -> None:
    rule = make_rule(
        id=11,
        type=AlertType.REF_MOVE,
        threshold=5.0,
        ref_price=100.0,
    )
    # No previous price → fail closed (baseline)
    events = filter_fireable(
        evaluate_price_rules(
            snapshot=make_snapshot(price=110.0),
            previous=make_previous(price=None),
            rules=[rule],
        )
    )
    assert events == []


def test_ref_move_requires_ref_price() -> None:
    rule = make_rule(
        id=12,
        type=AlertType.REF_MOVE,
        threshold=5.0,
        ref_price=None,
    )
    events = filter_fireable(
        evaluate_price_rules(
            snapshot=make_snapshot(price=110.0),
            previous=make_previous(price=100.0),
            rules=[rule],
        )
    )
    assert events == []
