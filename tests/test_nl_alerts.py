"""Natural-language alert parser (W3) — deterministic patterns + confirm payload."""

from __future__ import annotations

import os

import pytest

from koel.domain import AlertType
from koel.nl_alerts import (
    decode_nl_confirm_payload,
    describe_nl_alert,
    encode_nl_confirm_payload,
    nl_alerts_enabled,
    parse_alert_natural_language,
)


@pytest.mark.parametrize(
    ("text", "expected_type", "symbol"),
    [
        ("alert me when JKH.N0000 goes above 100", AlertType.PRICE_ABOVE, "JKH.N0000"),
        ("tell me if COMB drops below 50", AlertType.PRICE_BELOW, "COMB"),
        ("notify me when SAMP drops 5%", AlertType.DAILY_MOVE, "SAMP"),
        ("alert me if LOLC moves 3% from 82.50", AlertType.REF_MOVE, "LOLC"),
        ("when JKH crosses the 50-day MA", AlertType.MA_CROSS, "JKH"),
        ("ping me if HNB hits a 52-week high", AlertType.HIGH_52W, "HNB"),
        ("alert me on DIAL 52w low", AlertType.LOW_52W, "DIAL"),
        ("tell me when CTC has a new disclosure", AlertType.DISCLOSURE, "CTC"),
    ],
)
def test_parse_common_phrases(
    text: str, expected_type: AlertType, symbol: str
) -> None:
    parsed = parse_alert_natural_language(text)
    assert parsed is not None
    assert parsed.alert_type == expected_type
    assert parsed.symbol == symbol


def test_ref_move_captures_threshold_and_ref() -> None:
    parsed = parse_alert_natural_language("SAMP drops 5% from 82.50")
    assert parsed is not None
    assert parsed.alert_type == AlertType.REF_MOVE
    assert parsed.threshold == 5.0
    assert parsed.ref_price == 82.5


def test_ma_rejects_non_standard_period() -> None:
    assert parse_alert_natural_language("JKH crosses the 30-day MA") is None


def test_empty_and_garbage() -> None:
    assert parse_alert_natural_language("") is None
    assert parse_alert_natural_language("hello there") is None
    assert parse_alert_natural_language(None) is None  # type: ignore[arg-type]


def test_confirm_payload_roundtrip() -> None:
    parsed = parse_alert_natural_language("JKH above 120")
    assert parsed is not None
    payload = encode_nl_confirm_payload(parsed)
    assert payload.startswith("nlok:")
    assert len(payload) <= 64
    back = decode_nl_confirm_payload(payload)
    assert back is not None
    assert back.alert_type == parsed.alert_type
    assert back.symbol == parsed.symbol
    assert back.threshold == parsed.threshold


def test_describe_and_flag() -> None:
    parsed = parse_alert_natural_language("alert me when JKH goes above 100")
    assert parsed is not None
    assert "above" in describe_nl_alert(parsed)
    old = os.environ.get("AI_NL_ALERTS_ENABLED")
    try:
        os.environ["AI_NL_ALERTS_ENABLED"] = "0"
        assert nl_alerts_enabled() is False
        os.environ["AI_NL_ALERTS_ENABLED"] = "1"
        assert nl_alerts_enabled() is True
    finally:
        if old is None:
            os.environ.pop("AI_NL_ALERTS_ENABLED", None)
        else:
            os.environ["AI_NL_ALERTS_ENABLED"] = old
