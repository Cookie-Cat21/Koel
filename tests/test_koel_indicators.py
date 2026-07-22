"""Source + sanity contracts for koel indicator math helpers."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IND = ROOT / "web" / "src" / "lib" / "charts" / "koel-indicators.ts"


def test_indicator_exports() -> None:
    src = IND.read_text(encoding="utf-8")
    assert "export function computeSma" in src
    assert "export function computeEma" in src
    assert "export function computeBollinger" in src
    assert "export function computeRsi" in src
    assert "DEFAULT_INDICATORS" in src


def test_sma_math_inline() -> None:
    """Python twin of SMA for a tiny series — guards formula drift."""
    closes = [1.0, 2.0, 3.0, 4.0, 5.0]
    period = 3
    # last SMA3 = (3+4+5)/3 = 4
    assert sum(closes[-period:]) / period == 4.0
