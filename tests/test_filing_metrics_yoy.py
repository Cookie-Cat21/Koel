"""Unit tests: YoY compare + filing-metrics rule evaluation + bot parse."""

from __future__ import annotations

from datetime import UTC, date, datetime

from chime.bot import ALERT_USAGE, parse_alert_args
from chime.domain import AlertRule, AlertType, Disclosure, disclaimer, format_yoy_comparison_block
from chime.metrics import MetricsSettings
from chime.metrics.compare import MetricsRow, resolve_prior
from chime.rules import evaluate_filing_metrics_rules


def _disc(**kwargs: object) -> Disclosure:
    base = dict(
        external_id="ext-1",
        symbol="VONE.N0000",
        title="Interim Financial Statements",
        category="Financial",
        url="https://www.cse.lk/pages/announcements/announcements.component.html",
        published_at=datetime(2026, 5, 1, tzinfo=UTC),
        seen_at=datetime(2026, 5, 1, tzinfo=UTC),
        id=42,
        pdf_url="https://cdn.cse.lk/cse-pdf/x.pdf",
    )
    base.update(kwargs)
    return Disclosure(**base)  # type: ignore[arg-type]


def _rule(alert_type: AlertType, threshold: float) -> AlertRule:
    return AlertRule(
        id=7,
        user_id=1,
        telegram_id=99,
        symbol="VONE.N0000",
        type=alert_type,
        threshold=threshold,
        active=True,
        armed=True,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_alert_usage_lists_eps_and_yoy() -> None:
    for needle in (
        "/alert SYMBOL eps above|below X",
        "/alert SYMBOL eps yoy above|below PCT",
        "/alert SYMBOL rev yoy above|below PCT",
        disclaimer(),
    ):
        assert needle in ALERT_USAGE


def test_parse_eps_and_yoy_alert_kinds() -> None:
    cases = [
        (["VONE.N0000", "eps", "above", "3.5"], AlertType.EPS_ABOVE, 3.5),
        (["VONE.N0000", "eps", "below", "1"], AlertType.EPS_BELOW, 1.0),
        (["VONE.N0000", "eps", "yoy", "above", "10"], AlertType.EPS_YOY_ABOVE, 10.0),
        (["VONE.N0000", "eps", "yoy", "below", "20"], AlertType.EPS_YOY_BELOW, 20.0),
        (["VONE.N0000", "rev", "yoy", "above", "15"], AlertType.REV_YOY_ABOVE, 15.0),
        (["VONE.N0000", "profit", "yoy", "below", "5"], AlertType.PROFIT_YOY_BELOW, 5.0),
    ]
    for args, alert_type, threshold in cases:
        parsed, err = parse_alert_args(args)
        assert err is None, args
        assert parsed is not None
        assert parsed.alert_type == alert_type
        assert parsed.threshold == threshold


def test_resolve_prior_exact_yoy() -> None:
    current = MetricsRow(
        id=2,
        symbol="VONE.N0000",
        kind="annual",
        fiscal_period_end=date(2026, 3, 31),
        fiscal_quarter=None,
        entity="group",
        scale="thousands",
        currency="LKR",
        revenue=200.0,
        profit=50.0,
        eps_basic=3.69,
        extract_ok=True,
    )
    prior = MetricsRow(
        id=1,
        symbol="VONE.N0000",
        kind="annual",
        fiscal_period_end=date(2025, 3, 31),
        fiscal_quarter=None,
        entity="group",
        scale="thousands",
        currency="LKR",
        revenue=100.0,
        profit=25.0,
        eps_basic=2.48,
        extract_ok=True,
    )
    cmp = resolve_prior(current, [prior])
    assert cmp.match_quality == "exact_yoy"
    assert cmp.prior_id == 1
    assert cmp.eps_delta_pct is not None
    assert abs(cmp.eps_delta_pct - ((3.69 - 2.48) / 2.48 * 100)) < 0.01
    assert cmp.revenue_delta_pct == 100.0


def test_resolve_prior_missing() -> None:
    current = MetricsRow(
        id=2,
        symbol="VONE.N0000",
        kind="annual",
        fiscal_period_end=date(2026, 3, 31),
        fiscal_quarter=None,
        entity="group",
        scale="thousands",
        currency="LKR",
        revenue=1.0,
        profit=1.0,
        eps_basic=1.0,
        extract_ok=True,
    )
    cmp = resolve_prior(current, [])
    assert cmp.match_quality == "missing_prior"
    assert cmp.prior_id is None


def test_evaluate_eps_above_and_yoy() -> None:
    cfg = MetricsSettings(
        financial_metrics_enabled=True,
        filing_compare_enabled=True,
        eps_calc_alerts_enabled=True,
        yoy_compare_alerts_enabled=True,
        metrics_shadow_mode=False,
    )
    metrics = {
        "extract_ok": True,
        "currency": "LKR",
        "kind": "annual",
        "eps_basic": 3.69,
        "pdf_url": "https://cdn.cse.lk/cse-pdf/x.pdf",
    }
    comparison = {
        "match_quality": "exact_yoy",
        "eps_delta_pct": 48.8,
        "revenue_delta_pct": 10.0,
        "profit_delta_pct": 12.0,
    }
    disc = _disc()
    events = evaluate_filing_metrics_rules(
        metrics=metrics,
        comparison=comparison,
        disclosure=disc,
        rules=[
            _rule(AlertType.EPS_ABOVE, 3.5),
            _rule(AlertType.EPS_YOY_ABOVE, 10.0),
            _rule(AlertType.EPS_YOY_BELOW, 10.0),  # should not fire
        ],
        settings=cfg,
    )
    types = {e.type for e in events}
    assert AlertType.EPS_ABOVE in types
    assert AlertType.EPS_YOY_ABOVE in types
    assert AlertType.EPS_YOY_BELOW not in types


def test_evaluate_fail_closed_without_extract() -> None:
    cfg = MetricsSettings(
        financial_metrics_enabled=True,
        eps_calc_alerts_enabled=True,
        metrics_shadow_mode=False,
    )
    events = evaluate_filing_metrics_rules(
        metrics={"extract_ok": False, "currency": "LKR", "eps_basic": 9.0},
        comparison=None,
        disclosure=_disc(),
        rules=[_rule(AlertType.EPS_ABOVE, 1.0)],
        settings=cfg,
    )
    assert events == []


def test_format_yoy_block() -> None:
    block = format_yoy_comparison_block(
        metrics={
            "extract_ok": True,
            "kind": "annual",
            "entity": "group",
            "currency": "LKR",
            "eps_basic": 3.69,
        },
        comparison={
            "match_quality": "exact_yoy",
            "eps_delta_pct": 48.79,
            "revenue_delta_pct": 10.0,
            "profit_delta_pct": 5.0,
        },
    )
    assert block is not None
    assert "3.69" in block
    assert "YoY" in block
    assert "verify in the filing" in block
