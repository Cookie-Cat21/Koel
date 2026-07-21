"""Prospective shadow standards reporting."""

from __future__ import annotations

from datetime import date, timedelta

from koel.ml.live_shadow_report import summarize_shadow_rows


def test_shadow_report_excludes_partial_and_enforces_support() -> None:
    rows = [
        {
            "model_version": "model-v1",
            "symbol": f"S{index % 90}",
            "issued_at": date(2026, 1, 1) + timedelta(days=index % 70),
            "gate": "shadow_all",
            "scored": True,
            "hit": index % 20 != 0,
        }
        for index in range(600)
    ]
    rows.append(
        {
            "model_version": "model-v1_partial",
            "symbol": "CANARY",
            "issued_at": date(2026, 1, 1),
            "gate": "shadow_partial",
            "scored": True,
            "hit": True,
        }
    )
    report = summarize_shadow_rows(rows)
    assert len(report) == 1
    metrics = report[0]
    assert metrics.model_version == "model-v1"
    assert metrics.scored == 600
    assert metrics.precision == 0.95
    assert metrics.symbols == 90
    assert metrics.sessions == 70
    assert metrics.contract_met is True


def test_shadow_report_does_not_count_unscored_rows() -> None:
    rows = [
        {
            "model_version": "model-v2",
            "symbol": "A",
            "issued_at": date(2026, 1, 1),
            "gate": "shadow_all",
            "scored": False,
            "hit": None,
        }
    ]
    metrics = summarize_shadow_rows(rows)[0]
    assert metrics.rows == 1
    assert metrics.scored == 0
    assert metrics.precision is None
    assert metrics.contract_met is False
