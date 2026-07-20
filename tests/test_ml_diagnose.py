"""Unit tests for diagnose bucketing and recommendations."""

from __future__ import annotations

from datetime import date

from koel.ml.diagnose import (
    PredRow,
    _bucket,
    analyze_rows,
    build_recommendations,
)
from koel.ml.features import FEATURE_NAMES


def _feat(**overrides: float) -> tuple[float, ...]:
    base = [0.0] * len(FEATURE_NAMES)
    for k, v in overrides.items():
        base[FEATURE_NAMES.index(k)] = v
    return tuple(base)


def test_bucket_thresholds() -> None:
    assert _bucket(0.25) == "HIGH"
    assert _bucket(-0.12) == "MID"
    assert _bucket(0.05) == "LOW"


def test_analyze_rows_reports_high_hit() -> None:
    rows = [
        PredRow(
            symbol="WIN.N0000",
            as_of=date(2025, 1, 1),
            fold=0,
            score=0.3,
            y_dir=1.0,
            y_ret=0.02,
            hit=True,
            features=_feat(liquidity_20d=1e6, vol_20d=0.01),
        ),
        PredRow(
            symbol="LOSE.N0000",
            as_of=date(2025, 1, 1),
            fold=0,
            score=0.05,
            y_dir=1.0,
            y_ret=0.01,
            hit=False,
            features=_feat(liquidity_20d=100.0, vol_20d=0.08),
        ),
    ]
    # pad so n_symbols filter doesn't matter for bucket hits
    for i in range(25):
        rows.append(
            PredRow(
                symbol="WIN.N0000",
                as_of=date(2025, 1, 2 + i),
                fold=0,
                score=0.25,
                y_dir=1.0,
                y_ret=0.01,
                hit=True,
                features=_feat(liquidity_20d=1e6, vol_20d=0.01),
            )
        )
    result = analyze_rows(rows, model_id="M1_hgb_clf", horizon=1, panel=True)
    assert result.bucket_hits["HIGH"] == 1.0
    assert result.n_rows == len(rows)
    assert result.recommendations


def test_build_recommendations_mentions_target() -> None:
    recs = build_recommendations(
        gaps=[
            {
                "feature": "liquidity_20d",
                "std_gap_hit_vs_low": 0.5,
                "high_hit_mean": 1.0,
                "high_miss_mean": 0.5,
                "low_mean": 0.1,
            }
        ],
        sym_stats=[{"hit_rate": 0.55, "n": 50}],
        pooled_hit=0.56,
        mean_symbol_hit=0.55,
        liq_mix={
            "HIGH_HIT": {"low": 0.2, "mid": 0.3, "high": 0.5},
            "LOW": {"low": 0.5, "mid": 0.3, "high": 0.2},
        },
        vol_mix={},
    )
    assert any("0.70" in r for r in recs)
    assert any("liquidity" in r.lower() for r in recs)
