"""W5/W6: format_alert_message provenance (As of) + context_line."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from koel.domain import AlertEvent, AlertType, disclaimer, format_alert_message

_COLOMBO = ZoneInfo("Asia/Colombo")


def _event(**kwargs: object) -> AlertEvent:
    base: dict[str, object] = {
        "rule_id": 1,
        "user_id": 1,
        "telegram_id": 1001,
        "symbol": "JKH.N0000",
        "type": AlertType.PRICE_ABOVE,
        "threshold": 100.0,
        "trigger": "price crossed above 100.00",
        "current_price": 101.5,
        "event_key": "price:1:1",
    }
    base.update(kwargs)
    return AlertEvent.model_validate(base)


def test_format_alert_message_includes_as_of_slt() -> None:
    as_of = datetime(2026, 7, 21, 8, 12, tzinfo=UTC)  # 13:42 SLT
    msg = format_alert_message(_event(as_of=as_of))
    local = as_of.astimezone(_COLOMBO)
    assert f"As of {local.strftime('%H:%M')} SLT" in msg
    assert "As of 13:42 SLT" in msg
    assert msg.index("As of 13:42 SLT") < msg.index(disclaimer())


def test_format_alert_message_includes_context_line_before_nfa() -> None:
    msg = format_alert_message(
        _event(context_line="Recent filing: Interim Financials Q1")
    )
    assert "Recent filing: Interim Financials Q1" in msg
    assert msg.index("Recent filing:") < msg.index(disclaimer())


def test_format_alert_message_context_and_as_of_order() -> None:
    as_of = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    msg = format_alert_message(
        _event(
            as_of=as_of,
            context_line="Recent filing: Board Meeting",
            filing_brief="Brief body here.",
        )
    )
    assert "Recent filing: Board Meeting" in msg
    assert "Brief body here." in msg
    assert "As of" in msg and "SLT" in msg
    assert msg.index("Recent filing:") < msg.index("Brief body here.")
    assert msg.index("Brief body here.") < msg.index("As of")
    assert msg.index("As of") < msg.index(disclaimer())


def test_format_alert_message_omits_provenance_when_unset() -> None:
    msg = format_alert_message(_event())
    assert "As of" not in msg
    assert "Recent filing:" not in msg
    assert disclaimer() in msg
