"""Confidence mapping unit tests."""

from koel.ml.confidence import confidence_band, score_to_confidence


def test_score_to_confidence_clf_range() -> None:
    assert abs(score_to_confidence(0.0) - 0.0) < 1e-9
    assert abs(score_to_confidence(0.25) - 0.5) < 1e-9
    assert abs(score_to_confidence(-0.5) - 1.0) < 1e-9


def test_hpe_band() -> None:
    assert confidence_band(0.8, gate="hpe_p90") == "high"
    assert confidence_band(0.4, gate="hpe_p90") == "medium"
    assert confidence_band(0.2, gate="always_on") == "low"
