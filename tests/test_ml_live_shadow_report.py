"""Prospective shadow standards reporting."""

from __future__ import annotations

from datetime import date, timedelta

from koel.ml.live_shadow_report import summarize_shadow_rows


def test_shadow_report_excludes_partial_and_enforces_support() -> None:
    rows = [
        {
            "model_id": "policy-v1",
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
            "model_id": "policy-v1",
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
    assert metrics.policy_id == "policy-v1"
    assert metrics.instances == 1
    assert metrics.latest_model_version == "model-v1"
    assert metrics.scored == 600
    assert metrics.precision == 0.95
    assert metrics.coverage == 1.0
    assert metrics.symbols == 90
    assert metrics.sessions == 70
    assert metrics.contract_met is True


def test_shadow_report_does_not_count_unscored_rows() -> None:
    rows = [
        {
            "model_id": "policy-v2",
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
    assert metrics.coverage == 1.0
    assert metrics.contract_met is False


def test_scored_flat_outcome_counts_as_miss() -> None:
    rows = [
        {
            "model_id": "policy-v3",
            "model_version": "model-v3-a",
            "symbol": "A",
            "issued_at": date(2026, 1, 1),
            "gate": "shadow_all",
            "scored": True,
            "hit": None,
        },
        {
            "model_id": "policy-v3",
            "model_version": "model-v3-b",
            "symbol": "B",
            "issued_at": date(2026, 1, 2),
            "gate": "shadow_all",
            "scored": True,
            "hit": True,
        },
    ]
    metrics = summarize_shadow_rows(rows)[0]
    assert metrics.instances == 2
    assert metrics.scored == 2
    assert metrics.correct == 1
    assert metrics.precision == 0.5


def test_shadow_report_includes_rank_calibration_and_cost_metrics() -> None:
    rows = [
        {
            "model_id": "rank-policy",
            "model_version": "rank-instance",
            "symbol": f"S{index:02d}",
            "issued_at": date(2026, 1, 1),
            "gate": "shadow_all",
            "scored": True,
            "hit": True,
            "y_pred": float(index - 10),
            "y_real": float(index - 10) / 100,
            "confidence": 1.0,
        }
        for index in range(20)
    ]
    metrics = summarize_shadow_rows(rows)[0]
    assert metrics.rank_ic == 1.0
    assert metrics.rank_ic_sessions == 1
    assert metrics.balanced_accuracy == 1.0
    assert metrics.mcc == 1.0
    assert metrics.brier == 0.0
    assert metrics.ece == 0.0
    assert metrics.post_cost_sessions == 1
