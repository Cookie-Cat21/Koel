"""TradingView symbol mapping — display-only, never the data spine."""

from __future__ import annotations

# Pure TS helper mirrored for contract tests via node; keep a thin Python
# parity check on the documented CSELK format used in docs/factory/CHART_LAYERS.md.


def test_cselk_format_documented() -> None:
    from pathlib import Path

    src = Path("web/src/lib/tradingview-symbol.ts").read_text(encoding="utf-8")
    assert 'TV_CSE_EXCHANGE = "CSELK"' in src
    assert "${TV_CSE_EXCHANGE}:${symbol}" in src
    assert "tradingview.com/symbols/" in src
    assert "MARKET" in src
