"""Wave44: medium+ bugs — mapRule threshold cap + SYMBOL_RE egress pin.

1. ``mapRule`` must cap thresholds at ``MAX_ALERT_THRESHOLD`` (parity with
   GET ``/api/v1/alerts``) — poisoned DB / create-return used to egress
   ``Number.MAX_VALUE``-scale thresholds into dash JSON.
2. Residual SYMBOL_RE egress (no sanitize ``"?"``) remains pinned for
   mapRule / history / browse / symbol detail.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_map_rule_caps_alert_threshold() -> None:
    source = (WEB / "src" / "lib" / "db.ts").read_text(encoding="utf-8")
    assert "MAX_ALERT_THRESHOLD" in source
    assert "toFiniteNumber(row.threshold)" in source
    assert "n <= MAX_ALERT_THRESHOLD" in source
    # Bare uncapped toFiniteNumber assign must not remain.
    assert "threshold: toFiniteNumber(row.threshold)," not in source


def test_map_rule_normalizes_symbol() -> None:
    source = (WEB / "src" / "lib" / "db.ts").read_text(encoding="utf-8")
    assert "normalizeSymbol(row.symbol)" in source
    assert '?? "?"' not in source
    assert "sanitizeDisclosureText(row.symbol" not in source


def test_history_api_normalizes_symbol_no_placeholder() -> None:
    source = (
        WEB / "src" / "app" / "api" / "v1" / "alerts" / "history" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "normalizeSymbol(row.symbol)" in source
    assert '?? "?"' not in source
    assert "sanitizeDisclosureText(row.symbol" not in source
    assert "MAX_HISTORY_SYMBOL_LENGTH" not in source


def test_market_browse_normalizes_symbol() -> None:
    source = (WEB / "src" / "lib" / "api" / "market-browse.ts").read_text(
        encoding="utf-8"
    )
    assert "normalizeSymbol(row.symbol)" in source
    assert "sanitizeDisclosureText(row.symbol" not in source
    assert "MAX_HISTORY_SYMBOL_LENGTH" not in source


def test_symbol_detail_normalizes_egress() -> None:
    source = (
        WEB / "src" / "app" / "api" / "v1" / "symbols" / "[symbol]" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "normalizeSymbol(row.symbol) ?? symbol" in source
    assert "sanitizeDisclosureText(row.symbol" not in source
    assert "MAX_HISTORY_SYMBOL_LENGTH" not in source
