"""Unit tests for LTR ship promotion gates (no DB)."""

from __future__ import annotations

from koel.ml.ltr_serve import LtrOosMetrics, _passes_ltr_promotion


def _m(
    *,
    rank_ic: float,
    gated: float,
    vol_ic: float,
) -> LtrOosMetrics:
    return LtrOosMetrics(
        mean_rank_ic=rank_ic,
        gated_hit=gated,
        gated_coverage=0.12,
        pooled_hit=0.58,
        vol_rank_ic=vol_ic,
        folds=8,
        origins=1000,
        ranker="xgb_pairwise",
    )


def test_promote_beats_champion_gated() -> None:
    ok, reasons = _passes_ltr_promotion(
        metrics=_m(rank_ic=0.27, gated=0.74, vol_ic=0.35),
        champion_gated_hit=0.7268,
    )
    assert ok
    assert any("≥" in r or ">=" in r or "champion" in r for r in reasons)


def test_promote_go_ltr_vol_product_gate() -> None:
    ok, reasons = _passes_ltr_promotion(
        metrics=_m(rank_ic=0.27, gated=0.58, vol_ic=0.35),
        champion_gated_hit=0.7268,
    )
    assert ok
    assert any("GO_LTR+VOL" in r for r in reasons)


def test_reject_weak_rankic() -> None:
    ok, _ = _passes_ltr_promotion(
        metrics=_m(rank_ic=0.01, gated=0.70, vol_ic=0.35),
        champion_gated_hit=0.7268,
    )
    assert not ok
