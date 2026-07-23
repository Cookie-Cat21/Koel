"""Penny-stock hero step path must explain itself in UI + help."""

from __future__ import annotations

from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"


def test_candlestick_line_mode_footnote_explains_step_path() -> None:
    src = (WEB / "src" / "components" / "charts" / "candlestick-chart.tsx").read_text(
        encoding="utf-8"
    )
    assert "lineMode" in src
    assert "Step path (not candles)" in src
    assert "under LKR 3" in src
    assert "mostly flat" in src


def test_help_documents_step_path_and_stale_poller() -> None:
    src = (WEB / "src" / "lib" / "help-content.ts").read_text(encoding="utf-8")
    assert "Why a step line instead of candles on some names?" in src
    assert "under LKR 3" in src
    assert "market-tick" in src
    assert "long-running" in src
