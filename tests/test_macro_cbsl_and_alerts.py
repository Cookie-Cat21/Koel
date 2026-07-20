"""Unit tests for CBSL FX parse + MARKET regime alert evaluation."""

from __future__ import annotations

import io
from datetime import UTC, date, datetime

from chime.adapters.macro_cbsl import parse_cbsl_fx_xlsx
from chime.domain import MARKET_SYMBOL, AlertRule, AlertType
from chime.macro_alerts import evaluate_market_regime_rules


def _tiny_cbsl_xlsx() -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "2005-2026"
    ws.append([None] * 10)
    ws.append([None, "Buying & Selling Exchange Rates of Commercial Banks (a)"])
    ws.append([None] * 10)
    ws.append([None, None, "United States", None, "Great Britain", None, "European Union"])
    ws.append([None, None, "Buying", "Selling", "Buying", "Selling", "Buying", "Selling"])
    ws.append([None, None, "USD", "USD", "GBP", "GBP", "EUR", "EUR"])
    ws.append([None] * 10)
    ws.append([None, datetime(2026, 7, 18), 300.0, 310.0, 400.0, 410.0, 350.0, 360.0])
    ws.append([None, datetime(2026, 7, 19), 301.0, 311.0, 401.0, 411.0, 351.0, 361.0])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_cbsl_fx_xlsx_mids() -> None:
    rows = parse_cbsl_fx_xlsx(_tiny_cbsl_xlsx(), max_rows=10)
    assert rows
    series = {r["series_id"] for r in rows}
    assert "USD_LKR" in series
    assert "EUR_LKR" in series
    usd = [r for r in rows if r["series_id"] == "USD_LKR"]
    assert usd[-1]["value"] == 306.0
    assert usd[-1]["as_of_date"] == date(2026, 7, 19)
    assert "CBSL" in usd[-1]["attribution"]


def _rule(alert_type: AlertType, threshold: float, rule_id: int = 1) -> AlertRule:
    return AlertRule(
        id=rule_id,
        user_id=1,
        telegram_id=9001,
        symbol=MARKET_SYMBOL,
        type=alert_type,
        threshold=threshold,
        active=True,
        created_at=datetime.now(tz=UTC),
    )


def test_appetite_band_fires_above_threshold() -> None:
    events = evaluate_market_regime_rules(
        rules=[_rule(AlertType.APPETITE_BAND, 60)],
        appetite_score=72,
    )
    assert len(events) == 1
    assert events[0].type == AlertType.APPETITE_BAND


def test_foreign_and_book_thresholds() -> None:
    rules = [
        _rule(AlertType.FOREIGN_FLOW, 1_000_000, 2),
        _rule(AlertType.BOOK_PRESSURE, 10, 3),
    ]
    events = evaluate_market_regime_rules(
        rules=rules,
        foreign_net=-2_500_000,
        book_imbalance_pct=12.5,
    )
    types = {e.type for e in events}
    assert AlertType.FOREIGN_FLOW in types
    assert AlertType.BOOK_PRESSURE in types


def test_day_bucket_dedupe() -> None:
    rule = _rule(AlertType.APPETITE_BAND, 50, 9)
    claimed: set[str] = set()
    first = evaluate_market_regime_rules(
        rules=[rule], appetite_score=80, fired_keys=claimed
    )
    assert len(first) == 1
    claimed.add(first[0].event_key)
    second = evaluate_market_regime_rules(
        rules=[rule], appetite_score=90, fired_keys=claimed
    )
    assert second == []


def test_usdlkr_and_oil_move_thresholds() -> None:
    rules = [
        _rule(AlertType.USDLKR_MOVE, 1.0, 11),
        _rule(AlertType.OIL_MOVE, 2.0, 12),
    ]
    events = evaluate_market_regime_rules(
        rules=rules,
        usdlkr_change_pct=-1.5,
        oil_change_pct=3.25,
    )
    types = {e.type for e in events}
    assert AlertType.USDLKR_MOVE in types
    assert AlertType.OIL_MOVE in types


def test_regime_skips_when_inputs_missing() -> None:
    events = evaluate_market_regime_rules(
        rules=[
            _rule(AlertType.APPETITE_BAND, 50, 21),
            _rule(AlertType.FOREIGN_FLOW, 1_000_000, 22),
            _rule(AlertType.USDLKR_MOVE, 1.0, 23),
        ],
        appetite_score=None,
        foreign_net=None,
        usdlkr_change_pct=None,
    )
    assert events == []
