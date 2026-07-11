"""format_alert_message / disclaimer formatting — NFA suffix always present."""

from __future__ import annotations

import pytest

from chime.domain import (
    AlertEvent,
    AlertType,
    disclaimer,
    format_alert_message,
    format_dead_letter_notify,
    truncate_disclosure_title,
)


def _price_event(**kwargs: object) -> AlertEvent:
    base = dict(
        rule_id=1,
        user_id=2,
        telegram_id=3,
        symbol="JKH.N0000",
        type=AlertType.PRICE_ABOVE,
        threshold=100.0,
        trigger="price crossed above 100.00",
        current_price=105.5,
        event_key="price:1:42",
    )
    base.update(kwargs)
    return AlertEvent(**base)  # type: ignore[arg-type]


def _disclosure_event(**kwargs: object) -> AlertEvent:
    base = dict(
        rule_id=1,
        user_id=2,
        telegram_id=3,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        threshold=None,
        trigger="new disclosure: AGM Notice",
        current_price=None,
        disclosure_title="AGM Notice",
        disclosure_url="https://www.cse.lk/announcements?id=99",
        event_key="disclosure:1:99",
    )
    base.update(kwargs)
    return AlertEvent(**base)  # type: ignore[arg-type]


def test_format_alert_message_includes_symbol_trigger_price_disclaimer() -> None:
    msg = format_alert_message(_price_event())
    assert "JKH.N0000" in msg
    assert "price crossed above 100.00" in msg
    assert "105.50 LKR" in msg
    assert disclaimer() in msg
    assert "Not financial advice" in msg


def test_disclosure_message_includes_url() -> None:
    url = "https://www.cse.lk/announcements?id=99"
    msg = format_alert_message(_disclosure_event(disclosure_url=url))
    assert url in msg
    assert "AGM Notice" in msg
    assert "JKH.N0000" in msg
    assert disclaimer() in msg


def test_disclosure_message_truncates_long_titles() -> None:
    long_title = "A" * 200
    msg = format_alert_message(_disclosure_event(disclosure_title=long_title))
    assert long_title not in msg
    assert "Disclosure: " in msg
    disc_line = next(ln for ln in msg.splitlines() if ln.startswith("Disclosure: "))
    title_part = disc_line.removeprefix("Disclosure: ")
    assert title_part.endswith("…")
    assert len(title_part) == 120
    assert disclaimer() in msg


@pytest.mark.parametrize(
    "title,max_len,expected",
    [
        ("Short", 120, "Short"),
        ("x" * 120, 120, "x" * 120),
        ("x" * 121, 120, "x" * 119 + "…"),
        ("  padded  ", 120, "padded"),
        ("ab", 1, "…"),
    ],
)
def test_truncate_disclosure_title(title: str, max_len: int, expected: str) -> None:
    assert truncate_disclosure_title(title, max_len) == expected


@pytest.mark.parametrize(
    "msg",
    [
        format_alert_message(_price_event()),
        format_alert_message(_disclosure_event()),
        format_alert_message(
            _disclosure_event(disclosure_title="Z" * 250, current_price=12.34)
        ),
        format_dead_letter_notify("JKH.N0000", 5),
        format_dead_letter_notify("COMB.N0000", 1),
    ],
)
def test_format_helpers_nfa_suffix_always_present(msg: str) -> None:
    assert "Not financial advice" in msg
    # NFA is the trailing substance of the message (last non-empty line).
    last = [ln for ln in msg.strip().splitlines() if ln.strip()][-1]
    assert "Not financial advice" in last
