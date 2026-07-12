"""Wave25: medium+ bugs — toIso egress, delivery honesty, history/market harden.

1. ``toIso`` must fail closed on unparseable / control-laden / overlong
   strings — never echo raw hostile DB text into JSON timestamps.
2. History ``delivery_status`` must not collapse ``delivery_attempted_ok``
   into ``sent`` — contract requires ``delivered_unmarked``.
3. History OFFSET must soft-cap; id/attempt parsing via digits-only
   SafeInteger helpers (no float trunc alias).
4. ``ensureUser`` must reject non-SafeInteger / non-positive ids.
5. History UI must render ``delivered_unmarked`` distinctly from sent.
6. Market browse page must sanitize symbol/name/sector (controls + cap).
7. Symbols / movers limit(+offset) must use SafeInteger, not mere isFinite.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_to_iso_fails_closed_on_unparseable() -> None:
    source = (WEB / "src" / "lib" / "api" / "time.ts").read_text(encoding="utf-8")
    assert "MAX_ISO_INPUT_LENGTH" in source
    assert "CTRL_RE" in source
    assert "if (Number.isNaN(d.getTime())) return value;" not in source
    assert "return value;" not in source
    assert "if (value instanceof Date) return value.toISOString();" not in source
    assert "if (Number.isNaN(d.getTime())) return null;" in source
    assert "\\u0000-\\u001F" in source


def test_safe_int_helper_digits_only() -> None:
    helper = WEB / "src" / "lib" / "api" / "safe-int.ts"
    source = helper.read_text(encoding="utf-8")
    assert "toSafePositiveInt" in source
    assert "toNonNegativeSafeInt" in source
    assert r"/^\d{1,15}$/" in source or "/^\\d{1,15}$/" in source
    assert "Math.trunc(" not in source


def test_history_delivery_offset_and_safe_ids() -> None:
    route = WEB / "src" / "app" / "api" / "v1" / "alerts" / "history" / "route.ts"
    source = route.read_text(encoding="utf-8")
    assert "deriveDeliveryStatus" in source
    assert "delivered_unmarked" in source
    assert "toSafePositiveInt" in source
    assert "toNonNegativeSafeInt" in source
    assert "MAX_HISTORY_OFFSET" in source
    assert "Math.min(n, MAX_HISTORY_OFFSET)" in source
    assert "offset = n;" not in source
    assert "Math.trunc(" not in source
    assert "toNonNegativeSafeInt(row.attempt_count" in source
    assert 'delivery_attempted_ok\n                  ? "sent"' not in source


def test_history_ui_renders_delivered_unmarked() -> None:
    page = WEB / "src" / "app" / "alerts" / "history" / "page.tsx"
    source = page.read_text(encoding="utf-8")
    assert "delivered_unmarked" in source
    assert "Delivered (unmarked)" in source


def test_ensure_user_requires_safe_integer_id() -> None:
    db = WEB / "src" / "lib" / "db.ts"
    source = db.read_text(encoding="utf-8")
    assert "toSafePositiveInt" in source
    assert "ensure_user returned non-safe id" in source
    assert "return Number(row.id);" not in source


def test_market_page_sanitizes_symbol_name_sector() -> None:
    page = WEB / "src" / "app" / "market" / "page.tsx"
    source = page.read_text(encoding="utf-8")
    assert "normalizeSymbol(" in source
    assert "MAX_HISTORY_SYMBOL_LENGTH" not in source
    assert "MAX_STOCK_NAME_LENGTH" in source
    assert "MAX_STOCK_SECTOR_LENGTH" in source
    assert "MAX_SECTOR_NAME_LENGTH" in source
    assert "r.symbol.trim()" not in source
    assert "r.name.trim()" not in source


def test_symbols_and_movers_use_safe_integer_limits() -> None:
    symbols = WEB / "src" / "app" / "api" / "v1" / "symbols" / "route.ts"
    movers = WEB / "src" / "app" / "api" / "v1" / "market" / "movers" / "route.ts"
    for path in (symbols, movers):
        source = path.read_text(encoding="utf-8")
        # Digits-only helpers — reject float trunc / sci-notation soft-accept.
        assert "toSafePositiveInt" in source
        assert "Number.parseInt" not in source
        assert "Number.isFinite(limit)" not in source
    symbols_src = symbols.read_text(encoding="utf-8")
    assert "toNonNegativeSafeInt" in symbols_src
    assert "Number.isFinite(offset)" not in symbols_src
    movers_src = movers.read_text(encoding="utf-8")
    assert 'toSafePositiveInt(sp.get("limit")' in movers_src
