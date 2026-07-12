"""Wave23: medium+ bugs — sectors/browse/alerts egress + health circuits.

1. Sectors must sanitize name/symbol/index_* (controls + cap) and use
   SafeInteger sector_id — trim-only left hostile DB text in JSON.
2. Alerts GET / create mapRule must sanitize symbol + SafeInteger ids;
   unknown alert types dropped on list/history.
3. Browse/watchlist/symbol detail sanitize symbols; POST watchlist name.
4. HEALTH_URL started_at / last_tick_at / circuits must not raw-egress
   unbounded hostile strings or nested maps.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_sectors_route_sanitizes_text_and_safe_ids() -> None:
    route = WEB / "src" / "app" / "api" / "v1" / "sectors" / "route.ts"
    source = route.read_text(encoding="utf-8")
    assert "sanitizeDisclosureText" in source
    assert "MAX_SECTOR_NAME_LENGTH" in source
    assert "MAX_SECTOR_SYMBOL_LENGTH" in source
    assert "MAX_SECTOR_INDEX_CODE_LENGTH" in source
    assert "MAX_SECTOR_INDEX_NAME_LENGTH" in source
    assert "Number.isSafeInteger" in source
    assert "toFiniteNumber(row.sector_id)" not in source
    assert "row.name.trim()" not in source
    assert "index_code: row.index_code" not in source
    assert "index_name: row.index_name" not in source


def test_alerts_get_sanitizes_symbol_and_drops_unknown_types() -> None:
    route = WEB / "src" / "app" / "api" / "v1" / "alerts" / "route.ts"
    source = route.read_text(encoding="utf-8")
    assert "normalizeSymbol(row.symbol)" in source
    assert "isAlertType(row.type)" in source
    assert "symbol: row.symbol" not in source


def test_history_drops_unknown_alert_types() -> None:
    route = WEB / "src" / "app" / "api" / "v1" / "alerts" / "history" / "route.ts"
    source = route.read_text(encoding="utf-8")
    assert "isAlertType(row.type)" in source


def test_map_rule_uses_safe_integer_and_sanitizes_symbol() -> None:
    db = WEB / "src" / "lib" / "db.ts"
    source = db.read_text(encoding="utf-8")
    assert "Number.isSafeInteger(id)" in source
    assert "Number.isFinite(id)" not in source
    assert "normalizeSymbol(row.symbol)" in source
    assert "symbol: row.symbol" not in source


def test_market_browse_and_watchlist_sanitize_symbol() -> None:
    browse = WEB / "src" / "lib" / "api" / "market-browse.ts"
    watch = WEB / "src" / "app" / "api" / "v1" / "watchlist" / "route.ts"
    for path in (browse, watch):
        source = path.read_text(encoding="utf-8")
        assert "normalizeSymbol(row.symbol)" in source
        assert "symbol: row.symbol" not in source
    watch_src = watch.read_text(encoding="utf-8")
    assert "name: stock.name" not in watch_src
    assert "sanitizeDisclosureText(stock.name" in watch_src


def test_health_sanitizes_started_tick_and_circuits() -> None:
    route = WEB / "src" / "app" / "api" / "v1" / "health" / "route.ts"
    source = route.read_text(encoding="utf-8")
    assert "sanitizeCircuits" in source
    assert "HEALTH_CIRCUITS_MAX" in source
    assert "sanitizeHealthString(body.started_at)" in source
    assert "sanitizeHealthString(body.last_tick_at)" in source
    assert "poller.circuits = body.circuits as Record" not in source
    assert 'typeof body.started_at === "string"' not in source


def test_disclosure_safe_sector_caps_present() -> None:
    helper = WEB / "src" / "lib" / "api" / "disclosure-safe.ts"
    source = helper.read_text(encoding="utf-8")
    assert "MAX_SECTOR_NAME_LENGTH" in source
    assert "MAX_SECTOR_SYMBOL_LENGTH" in source
    assert "MAX_SECTOR_INDEX_CODE_LENGTH" in source
    assert "MAX_SECTOR_INDEX_NAME_LENGTH" in source
