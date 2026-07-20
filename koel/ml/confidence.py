"""Map raw model scores to confidence + band labels (research / NFA)."""

from __future__ import annotations


def score_to_confidence(score: float) -> float:
    """Map signed score (e.g. P(up)-0.5 or predicted return) to [0, 1]."""
    # Classifiers: |P-0.5| in [0, 0.5] → ×2. Regressors: soft-cap |ret|.
    a = abs(float(score))
    if a <= 0.5:
        return max(0.0, min(1.0, a * 2.0))
    # Large |ŷ|: asymptote toward 1
    return max(0.0, min(1.0, 0.5 + min(0.5, a)))


def confidence_band(confidence: float, *, gate: str | None = None) -> str:
    if gate and gate.startswith("hpe"):
        if confidence >= 0.55:
            return "high"
        if confidence >= 0.35:
            return "medium"
        return "low"
    if confidence >= 0.70:
        return "high"
    if confidence >= 0.45:
        return "medium"
    if confidence > 0:
        return "low"
    return "none"
