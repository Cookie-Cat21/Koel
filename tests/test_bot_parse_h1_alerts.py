"""W2 H1 bot parse: high52 / low52 / ma / ref_move."""

from __future__ import annotations

from koel.bot import ALERT_USAGE, parse_alert_args
from koel.domain import AlertType, disclaimer


def test_parse_ref_move_from_price() -> None:
    parsed, err = parse_alert_args(["SAMP.N0000", "move", "5", "from", "82.50"])
    assert err is None
    assert parsed is not None
    assert parsed.alert_type == AlertType.REF_MOVE
    assert parsed.threshold == 5.0
    assert parsed.ref_price == 82.50


def test_parse_daily_move_unchanged() -> None:
    parsed, err = parse_alert_args(["SAMP.N0000", "move", "5"])
    assert err is None
    assert parsed is not None
    assert parsed.alert_type == AlertType.DAILY_MOVE
    assert parsed.threshold == 5.0
    assert parsed.ref_price is None


def test_parse_high52_aliases() -> None:
    for kind in ("high52", "high_52w", "52whigh"):
        parsed, err = parse_alert_args(["JKH.N0000", kind])
        assert err is None, kind
        assert parsed is not None
        assert parsed.alert_type == AlertType.HIGH_52W
        assert parsed.threshold is None


def test_parse_low52_aliases() -> None:
    for kind in ("low52", "low_52w", "52wlow"):
        parsed, err = parse_alert_args(["JKH.N0000", kind])
        assert err is None, kind
        assert parsed is not None
        assert parsed.alert_type == AlertType.LOW_52W
        assert parsed.threshold is None


def test_parse_ma_cross_periods() -> None:
    for period in ("20", "50", "200"):
        parsed, err = parse_alert_args(["JKH.N0000", "ma", period])
        assert err is None, period
        assert parsed is not None
        assert parsed.alert_type == AlertType.MA_CROSS
        assert parsed.threshold == float(period)


def test_parse_ma_cross_aliases() -> None:
    for kind in ("ma", "macross", "ma_cross"):
        parsed, err = parse_alert_args(["JKH.N0000", kind, "50"])
        assert err is None, kind
        assert parsed is not None
        assert parsed.alert_type == AlertType.MA_CROSS
        assert parsed.threshold == 50.0


def test_parse_ma_rejects_non_fidelity_period() -> None:
    parsed, err = parse_alert_args(["JKH.N0000", "ma", "21"])
    assert parsed is None
    assert err is not None
    assert "20, 50, or 200" in err


def test_parse_ref_move_rejects_bad_ref() -> None:
    parsed, err = parse_alert_args(["SAMP.N0000", "move", "5", "from", "nope"])
    assert parsed is None
    assert err is not None
    assert "Reference price" in err


def test_alert_usage_lists_h1_forms() -> None:
    assert "/alert SYMBOL move PERCENT from PRICE" in ALERT_USAGE
    assert "/alert SYMBOL high52" in ALERT_USAGE
    assert "/alert SYMBOL low52" in ALERT_USAGE
    assert "/alert SYMBOL ma 20|50|200" in ALERT_USAGE
    assert disclaimer() in ALERT_USAGE
