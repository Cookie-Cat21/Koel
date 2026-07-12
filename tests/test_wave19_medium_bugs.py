"""Wave19: medium+ bugs — history/watchlist/browse string egress + safe ids.

1. Alerts history must sanitize symbol/event_key (controls + cap) and drop
   non-SafeInteger ids (precision-loss alias risk).
2. Watchlist / symbol detail / market browse must sanitize stock name/sector.
3. Alerts GET must use SafeInteger (not merely isFinite) for rule ids.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_history_route_sanitizes_symbol_event_key_and_safe_ids() -> None:
    route = WEB / "src" / "app" / "api" / "v1" / "alerts" / "history" / "route.ts"
    source = route.read_text(encoding="utf-8")
    assert "sanitizeDisclosureText" in source
    assert "MAX_HISTORY_SYMBOL_LENGTH" in source
    assert "MAX_HISTORY_EVENT_KEY_LENGTH" in source
    assert "Number.isSafeInteger(id)" in source
    assert "Number.isSafeInteger(rule_id)" in source
    # Ban raw symbol/event_key egress.
    assert "symbol: row.symbol" not in source
    assert "event_key: row.event_key" not in source


def test_watchlist_route_sanitizes_name_sector() -> None:
    route = WEB / "src" / "app" / "api" / "v1" / "watchlist" / "route.ts"
    source = route.read_text(encoding="utf-8")
    assert "sanitizeDisclosureText" in source
    assert "MAX_STOCK_NAME_LENGTH" in source
    assert "MAX_STOCK_SECTOR_LENGTH" in source
    assert "name: row.name" not in source
    assert "sector: row.sector" not in source


def test_symbol_detail_route_sanitizes_name_sector() -> None:
    route = WEB / "src" / "app" / "api" / "v1" / "symbols" / "[symbol]" / "route.ts"
    source = route.read_text(encoding="utf-8")
    assert "sanitizeDisclosureText" in source
    assert "MAX_STOCK_NAME_LENGTH" in source
    assert "name: row.name" not in source
    assert "sector: row.sector" not in source


def test_market_browse_sanitizes_name_sector() -> None:
    helper = WEB / "src" / "lib" / "api" / "market-browse.ts"
    source = helper.read_text(encoding="utf-8")
    assert "sanitizeDisclosureText" in source
    assert "MAX_STOCK_NAME_LENGTH" in source
    assert "name: row.name" not in source
    assert "sector: row.sector" not in source


def test_alerts_get_uses_safe_integer_ids() -> None:
    route = WEB / "src" / "app" / "api" / "v1" / "alerts" / "route.ts"
    source = route.read_text(encoding="utf-8")
    assert "Number.isSafeInteger(id)" in source
    assert "Number.isFinite(id)" not in source


def test_disclosure_safe_stock_history_caps_present() -> None:
    helper = WEB / "src" / "lib" / "api" / "disclosure-safe.ts"
    source = helper.read_text(encoding="utf-8")
    assert "MAX_STOCK_NAME_LENGTH" in source
    assert "MAX_STOCK_SECTOR_LENGTH" in source
    assert "MAX_HISTORY_EVENT_KEY_LENGTH" in source
    assert "MAX_HISTORY_SYMBOL_LENGTH" in source
