"""Regime tagger unit tests."""

from datetime import date

from koel.ml.regime import tag_regime


def test_tag_regime_up_high() -> None:
    r = tag_regime(
        as_of=date(2026, 7, 1),
        aspi_ret_20d=0.05,
        cross_section_dispersion=0.04,
    )
    assert r.trend == "up"
    assert r.vol == "high"
    assert r.tag == "up_high"


def test_tag_regime_flat_low() -> None:
    r = tag_regime(as_of=date(2026, 7, 1), aspi_ret_20d=0.0)
    assert r.trend == "flat"
    assert r.vol == "low"
