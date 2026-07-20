"""Wave14 fuzz: evaluate_price_rules + format_alert_message never raise.

Mirrors wave7 (parse) / wave10 (disclosure rules) invariants:
weird floats, timestamps, and hostile strings must fail closed — return a
list / Telegram-safe body — never throw into the poller.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from koel.domain import (
    TELEGRAM_SAFE_MAX,
    AlertEvent,
    AlertType,
    disclaimer,
    format_alert_message,
)
from koel.rules import crossed_above, crossed_below, evaluate_price_rules, filter_fireable
from tests.conftest import make_previous, make_rule, make_snapshot

_COLOMBO = ZoneInfo("Asia/Colombo")

_WEIRD_FLOATS: list[float | None] = [
    None,
    0.0,
    -0.0,
    1.0,
    -1.0,
    99.0,
    100.0,
    100.01,
    1e-12,
    -1e-12,
    1e-300,
    1e308,
    -1e308,
    float("nan"),
    float("inf"),
    float("-inf"),
]

_WEIRD_TIMESTAMPS: list[datetime] = [
    datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
    datetime(2026, 7, 11, 6, 0, 0),  # naive
    datetime(2026, 7, 11, 6, 0, 0, tzinfo=_COLOMBO),
    datetime(1970, 1, 1, tzinfo=UTC),
    datetime(1, 1, 1),
    datetime(1, 1, 1, tzinfo=UTC),
    datetime(9999, 12, 31, 23, 59, 59, 999999),
    datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=UTC),
    # Extreme offsets — astimezone(Colombo) can OverflowError / ValueError.
    datetime(1, 1, 1, 0, 0, 0, tzinfo=timezone(timedelta(hours=14))),
    datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=timezone(timedelta(hours=-14))),
    datetime(2026, 7, 11, 6, 0, 0, tzinfo=timezone(timedelta(hours=14))),
    datetime(2026, 7, 11, 6, 0, 0, tzinfo=ZoneInfo("Pacific/Kiritimati")),
    datetime(2026, 7, 11, 6, 0, 0, tzinfo=ZoneInfo("America/Adak")),
]

_WEIRD_STRINGS: list[str] = [
    "",
    " ",
    "\t",
    "\n",
    "\x00",
    "\x01\x02",
    "\ufffd",
    "🚀",
    "ราคา",
    "مبلغ",
    "JKH.N0000\u200b",
    "above\ufeff",
    "a" * 10_000,
    "1" * 5000,
    "' OR 1=1 --",
    '"; DROP TABLE alert_rules;--',
    "<script>alert(1)</script>",
    "{{7*7}}",
    "%s%s%s%s",
    "\u202eTRIGGER",
    "👍" * 100,
    "price crossed above 100.00",
    "new disclosure: AGM Notice",
]

_WEIRD_URLS: list[str | None] = [
    None,
    "",
    "https://www.cse.lk/announcements#99",
    "https://www.cse.lk/announcements#" + ("9" * 10_000),
    "https://www.cse.lk/announcements#foo\x00bar",
    "javascript:alert(1)",
    "https://evil.example/phish",
    "http://www.cse.lk/announcements",
]


def _assert_telegram_safe(msg: str) -> None:
    assert isinstance(msg, str)
    assert len(msg) < TELEGRAM_SAFE_MAX
    assert disclaimer() in msg
    assert "\x00" not in msg
    for ch in msg:
        if ch in ("\n", "\t"):
            continue
        assert ord(ch) >= 0x20, f"control leaked: {ch!r}"
    last = [ln for ln in msg.strip().splitlines() if ln.strip()][-1]
    assert "Not financial advice" in last


@pytest.mark.parametrize("prev", _WEIRD_FLOATS, ids=lambda v: repr(v)[:40])
@pytest.mark.parametrize("curr", _WEIRD_FLOATS, ids=lambda v: repr(v)[:40])
@pytest.mark.parametrize("thr", _WEIRD_FLOATS, ids=lambda v: repr(v)[:40])
def test_crossed_helpers_fuzz_never_raises(
    prev: float | None,
    curr: float | None,
    thr: float | None,
) -> None:
    """Wave14: crossed_above/below must not throw on weird floats."""
    if curr is None or thr is None:
        return
    try:
        a = crossed_above(prev, curr, thr)
        b = crossed_below(prev, curr, thr)
    except Exception as exc:  # pragma: no cover
        pytest.fail(
            f"crossed_* raised {type(exc).__name__}: {exc!r} "
            f"prev={prev!r} curr={curr!r} thr={thr!r}"
        )
    assert isinstance(a, bool)
    assert isinstance(b, bool)


@pytest.mark.parametrize("alert_type", [AlertType.PRICE_ABOVE, AlertType.PRICE_BELOW])
@pytest.mark.parametrize("prev", _WEIRD_FLOATS[::2], ids=lambda v: f"p={v!r}"[:40])
@pytest.mark.parametrize("curr", _WEIRD_FLOATS[::2], ids=lambda v: f"c={v!r}"[:40])
@pytest.mark.parametrize("thr", _WEIRD_FLOATS[::2], ids=lambda v: f"t={v!r}"[:40])
def test_evaluate_price_rules_fuzz_floats_never_raises(
    alert_type: AlertType,
    prev: float | None,
    curr: float | None,
    thr: float | None,
) -> None:
    """Wave14: price_above/below evaluation never raises on weird floats."""
    if curr is None:
        return
    rule = make_rule(type=alert_type, threshold=thr, armed=True)
    snap = make_snapshot(price=curr)
    try:
        events = evaluate_price_rules(
            snapshot=snap,
            previous=make_previous(price=prev),
            rules=[rule],
        )
    except Exception as exc:  # pragma: no cover
        pytest.fail(
            f"evaluate_price_rules raised {type(exc).__name__}: {exc!r} "
            f"type={alert_type} prev={prev!r} curr={curr!r} thr={thr!r}"
        )
    assert isinstance(events, list)
    assert isinstance(filter_fireable(events), list)


@pytest.mark.parametrize("ts", _WEIRD_TIMESTAMPS, ids=lambda t: repr(t)[:80])
@pytest.mark.parametrize(
    "pct,prev_pct,thr",
    [
        (3.0, 1.0, 2.0),
        (5.0, None, 3.0),
        (float("nan"), 1.0, 2.0),
        (3.0, float("nan"), 2.0),
        (float("inf"), 1.0, 2.0),
        (3.0, 1.0, float("nan")),
        (None, 1.0, 2.0),
        (-4.0, -1.0, 3.0),
        (1e308, 1.0, 100.0),
    ],
    ids=lambda v: repr(v)[:50],
)
def test_evaluate_price_rules_fuzz_daily_move_never_raises(
    ts: datetime,
    pct: float | None,
    prev_pct: float | None,
    thr: float | None,
) -> None:
    """Wave14: daily_move must fail closed on weird timestamps / pcts."""
    rule = make_rule(type=AlertType.DAILY_MOVE, threshold=thr)
    snap = make_snapshot(price=103.0, change_pct=pct, ts=ts, previous_close=100.0)
    try:
        events = evaluate_price_rules(
            snapshot=snap,
            previous=make_previous(price=100.0, change_pct=prev_pct),
            rules=[rule],
        )
    except Exception as exc:  # pragma: no cover
        pytest.fail(
            f"evaluate_price_rules raised {type(exc).__name__}: {exc!r} "
            f"ts={ts!r} pct={pct!r} prev_pct={prev_pct!r} thr={thr!r}"
        )
    assert isinstance(events, list)


def test_evaluate_price_rules_fuzz_cartesian_types_prices() -> None:
    """Wave14 property-ish: type × price grid returns without raising."""
    prices = [v for v in _WEIRD_FLOATS if v is not None][::2]
    thrs = [None, 0.0, 100.0, float("nan"), float("inf"), 1e308]
    stamps = _WEIRD_TIMESTAMPS[::3]
    for alert_type in (AlertType.PRICE_ABOVE, AlertType.PRICE_BELOW, AlertType.DAILY_MOVE):
        for thr in thrs:
            for curr in prices:
                for prev in (None, 95.0, curr):
                    for armed in (True, False):
                        for ts in stamps:
                            rule = make_rule(
                                type=alert_type,
                                threshold=thr,
                                armed=armed,
                            )
                            snap = make_snapshot(
                                price=curr,
                                change_pct=curr if alert_type == AlertType.DAILY_MOVE else None,
                                ts=ts,
                            )
                            try:
                                events = evaluate_price_rules(
                                    snapshot=snap,
                                    previous=make_previous(
                                        price=prev,
                                        change_pct=1.0
                                        if alert_type == AlertType.DAILY_MOVE
                                        else None,
                                    ),
                                    rules=[rule],
                                )
                            except Exception as exc:  # pragma: no cover
                                pytest.fail(
                                    f"evaluate_price_rules raised {type(exc).__name__}: "
                                    f"{exc!r} type={alert_type} thr={thr!r} "
                                    f"curr={curr!r} prev={prev!r} ts={ts!r}"
                                )
                            assert isinstance(events, list)


def test_overflow_timestamp_daily_move_fail_closed_no_fire() -> None:
    """Unconvertible extreme-offset timestamps must not raise and must not fire."""
    overflow = datetime(1, 1, 1, 0, 0, 0, tzinfo=timezone(timedelta(hours=14)))
    rule = make_rule(type=AlertType.DAILY_MOVE, threshold=2.0)
    snap = make_snapshot(price=103.0, change_pct=5.0, ts=overflow)
    assert (
        evaluate_price_rules(
            snapshot=snap,
            previous=make_previous(price=100.0, change_pct=1.0),
            rules=[rule],
        )
        == []
    )


def test_nonfinite_price_and_threshold_fail_closed_no_fire() -> None:
    """NaN / Inf prices and thresholds never fire price_above/below."""
    for thr in (float("nan"), float("inf"), float("-inf")):
        rule = make_rule(type=AlertType.PRICE_ABOVE, threshold=thr)
        events = evaluate_price_rules(
            snapshot=make_snapshot(price=105.0),
            previous=make_previous(price=95.0),
            rules=[rule],
        )
        assert events == []

    for price in (float("nan"), float("inf"), float("-inf")):
        rule = make_rule(type=AlertType.PRICE_ABOVE, threshold=100.0)
        events = evaluate_price_rules(
            snapshot=make_snapshot(price=price),
            previous=make_previous(price=95.0),
            rules=[rule],
        )
        assert events == []


def _price_event(**kwargs: object) -> AlertEvent:
    base: dict[str, object] = dict(
        rule_id=1,
        user_id=2,
        telegram_id=3,
        symbol="JKH.N0000",
        type=AlertType.PRICE_ABOVE,
        threshold=100.0,
        trigger="price crossed above 100.00",
        current_price=105.5,
        event_key="price:1:above:100:s42",
    )
    base.update(kwargs)
    return AlertEvent(**base)  # type: ignore[arg-type]


def _disclosure_event(**kwargs: object) -> AlertEvent:
    base: dict[str, object] = dict(
        rule_id=1,
        user_id=2,
        telegram_id=3,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        threshold=None,
        trigger="new disclosure: AGM Notice",
        current_price=None,
        disclosure_title="AGM Notice",
        disclosure_url="https://www.cse.lk/announcements#99",
        event_key="disclosure:1:99",
    )
    base.update(kwargs)
    return AlertEvent(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize("symbol", _WEIRD_STRINGS, ids=lambda s: repr(s)[:50])
@pytest.mark.parametrize("trigger", _WEIRD_STRINGS[::3], ids=lambda s: repr(s)[:50])
def test_format_alert_message_fuzz_symbol_trigger_never_raises(
    symbol: str,
    trigger: str,
) -> None:
    """Wave14: hostile symbol/trigger strings must not throw and stay Telegram-safe."""
    try:
        msg = format_alert_message(_price_event(symbol=symbol, trigger=trigger))
    except Exception as exc:  # pragma: no cover
        pytest.fail(
            f"format_alert_message raised {type(exc).__name__}: {exc!r} "
            f"symbol={symbol!r} trigger={trigger!r}"
        )
    _assert_telegram_safe(msg)


@pytest.mark.parametrize("price", _WEIRD_FLOATS, ids=lambda v: repr(v)[:40])
def test_format_alert_message_fuzz_prices_never_raises(price: float | None) -> None:
    """Wave14: weird current_price values render without raising."""
    try:
        msg = format_alert_message(_price_event(current_price=price))
    except Exception as exc:  # pragma: no cover
        pytest.fail(f"format_alert_message raised {type(exc).__name__}: {exc!r} price={price!r}")
    _assert_telegram_safe(msg)
    if price is None:
        assert "Price:" not in msg
    else:
        assert "Price:" in msg


@pytest.mark.parametrize("title", _WEIRD_STRINGS, ids=lambda s: repr(s)[:50])
@pytest.mark.parametrize("url", _WEIRD_URLS, ids=lambda u: repr(u)[:60])
@pytest.mark.parametrize(
    "brief",
    [None, "", "ok", "\x00\x01", "B" * 9000, "brief\x00inject"],
    ids=lambda b: repr(b)[:40],
)
def test_format_alert_message_fuzz_disclosure_fields_never_raises(
    title: str,
    url: str | None,
    brief: str | None,
) -> None:
    """Wave14: disclosure title/url/brief corpus stays Telegram-safe."""
    try:
        msg = format_alert_message(
            _disclosure_event(
                disclosure_title=title,
                disclosure_url=url,
                filing_brief=brief,
            )
        )
    except Exception as exc:  # pragma: no cover
        pytest.fail(
            f"format_alert_message raised {type(exc).__name__}: {exc!r} "
            f"title={title!r} url={url!r} brief={brief!r}"
        )
    _assert_telegram_safe(msg)
    assert "evil.example" not in msg
    assert "javascript:" not in msg


def test_format_alert_message_fuzz_cartesian_price_disclosure() -> None:
    """Wave14 property-ish: mixed price + disclosure fields never raise."""
    prices = [v for v in _WEIRD_FLOATS if v is not None][::3]
    for symbol in ("JKH.N0000", "\x00X", "🚀", "S" * 500):
        for trigger in ("price crossed above 100.00", "\x00t", "T" * 500):
            for price in prices:
                try:
                    msg = format_alert_message(
                        _price_event(symbol=symbol, trigger=trigger, current_price=price)
                    )
                except Exception as exc:  # pragma: no cover
                    pytest.fail(f"format_alert_message raised {type(exc).__name__}: {exc!r}")
                _assert_telegram_safe(msg)

    for title in ("AGM", "\x00", "D" * 500):
        for url in _WEIRD_URLS[::2]:
            for brief in (None, "ok", "B" * 5000):
                try:
                    msg = format_alert_message(
                        _disclosure_event(
                            disclosure_title=title,
                            disclosure_url=url,
                            filing_brief=brief,
                            current_price=12.34,
                        )
                    )
                except Exception as exc:  # pragma: no cover
                    pytest.fail(f"format_alert_message raised {type(exc).__name__}: {exc!r}")
                _assert_telegram_safe(msg)
