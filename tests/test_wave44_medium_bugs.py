"""Wave44: medium+ bugs — residual SYMBOL_RE egress (no sanitize "?").

After w45 tightened alerts/watchlist pages + GET list APIs, these paths still
soft-accepted junk symbols via sanitize ``"?"`` placeholders:

1. ``mapRule`` / create-alert return must ``normalizeSymbol`` or null.
2. History GET must ``normalizeSymbol`` and drop invalid rows.
3. Market browse must ``normalizeSymbol`` (not sanitize-only symbols).
4. Symbol detail GET must egress ``normalizeSymbol(row.symbol) ?? path``.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


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
