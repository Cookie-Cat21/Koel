"""Sparse intraday candles must not stretch card-wide (comfort/pack pitch)."""

from __future__ import annotations

from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"


def test_candlestick_auto_comfort_caps_wide_slots() -> None:
    src = (WEB / "src" / "components" / "charts" / "candlestick-chart.tsx").read_text(
        encoding="utf-8"
    )
    assert "MAX_COMFORT_SLOT" in src
    assert "autoComfort" in src
    assert "filledSlot" in src


def test_hero_caps_slot_for_sparse_intraday() -> None:
    src = (
        WEB / "src" / "components" / "charts" / "expandable-price-chart.tsx"
    ).read_text(encoding="utf-8")
    assert "maxSlot={12}" in src
    assert "fitWidth" in src
