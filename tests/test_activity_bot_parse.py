"""Bot parser coverage for activity / notice alert kinds."""

from __future__ import annotations

from koel.bot import ALERT_USAGE, parse_alert_args
from koel.domain import AlertType, disclaimer


def test_alert_usage_lists_activity_forms_and_nfa() -> None:
    for needle in (
        "/alert SYMBOL volume MULTIPLIER",
        "/alert SYMBOL volup MULTIPLIER",
        "/alert SYMBOL voldown MULTIPLIER",
        "/alert SYMBOL crossing MULTIPLIER",
        "/alert SYMBOL print QTY",
        "/alert SYMBOL gap PERCENT",
        "/alert SYMBOL buyin",
        "/alert SYMBOL noncompliance",
        "/alert MARKET halt",
        "/alert SYMBOL bidheavy MULTIPLIER",
        "/alert SYMBOL askheavy MULTIPLIER",
        disclaimer(),
    ):
        assert needle in ALERT_USAGE


def test_parse_activity_alert_kinds() -> None:
    cases = [
        (["JKH.N0000", "volume", "5"], AlertType.VOLUME_SPIKE, 5.0),
        (["JKH.N0000", "volup", "3"], AlertType.VOLUME_UP, 3.0),
        (["JKH.N0000", "voldown", "3"], AlertType.VOLUME_DOWN, 3.0),
        (["JKH.N0000", "crossing", "4"], AlertType.CROSSING_VOLUME, 4.0),
        (["JKH.N0000", "print", "10000"], AlertType.BIG_PRINT, 10000.0),
        (["JKH.N0000", "gap", "2.5"], AlertType.GAP, 2.5),
        (["JKH.N0000", "buyin"], AlertType.BUY_IN, None),
        (["JKH.N0000", "noncompliance"], AlertType.NON_COMPLIANCE, None),
        (["MARKET", "halt"], AlertType.HALT, None),
        (["JKH.N0000", "bidheavy", "2"], AlertType.BID_HEAVY, 2.0),
        (["JKH.N0000", "askheavy", "1.5"], AlertType.ASK_HEAVY, 1.5),
    ]
    for args, alert_type, threshold in cases:
        parsed, err = parse_alert_args(args)
        assert err is None, args
        assert parsed is not None
        assert parsed.alert_type == alert_type
        assert parsed.threshold == threshold
