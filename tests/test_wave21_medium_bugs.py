"""Wave21: medium+ bugs — symbol filter validation + disclosure SafeInteger.

1. History GET must reject non-CSE symbols via normalizeSymbol (400
   invalid_symbol), matching alerts list — not bare trim/uppercase.
2. History UI must not forward hostile symbol query params to the API.
3. Alerts list UI must normalizeSymbol the same way (not trim/uppercase).
4. Alert/watchlist create forms must reject hostile symbols client-side
   via normalizeSymbol before POST.
5. Disclosures API must drop non-SafeInteger / non-positive ids (precision
   alias risk) — not merely Number.isFinite.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_history_route_validates_symbol_filter() -> None:
    route = WEB / "src" / "app" / "api" / "v1" / "alerts" / "history" / "route.ts"
    source = route.read_text(encoding="utf-8")
    assert "normalizeSymbol" in source
    assert 'jsonError(400, "invalid_symbol"' in source
    # Ban unvalidated trim/uppercase filter push into SQL params.
    assert "symbolRaw.trim().toUpperCase()" not in source
    assert "symbolRaw && symbolRaw.trim() ? symbolRaw.trim().toUpperCase()" not in source


def test_history_page_normalizes_symbol_filter() -> None:
    page = WEB / "src" / "app" / "alerts" / "history" / "page.tsx"
    source = page.read_text(encoding="utf-8")
    assert "normalizeSymbol" in source
    assert "sp.symbol?.trim().toUpperCase()" not in source


def test_alerts_page_normalizes_symbol_filter() -> None:
    page = WEB / "src" / "app" / "alerts" / "page.tsx"
    source = page.read_text(encoding="utf-8")
    assert "normalizeSymbol" in source
    assert "sp.symbol?.trim().toUpperCase()" not in source


def test_alert_and_watchlist_forms_use_normalize_symbol() -> None:
    alert = WEB / "src" / "components" / "alert-controls.tsx"
    watch = WEB / "src" / "components" / "watchlist-controls.tsx"
    for path in (alert, watch):
        source = path.read_text(encoding="utf-8")
        assert "normalizeSymbol" in source
        assert "symbol.trim().toUpperCase()" not in source


def test_disclosures_route_uses_safe_integer_ids() -> None:
    route = (
        WEB
        / "src"
        / "app"
        / "api"
        / "v1"
        / "symbols"
        / "[symbol]"
        / "disclosures"
        / "route.ts"
    )
    source = route.read_text(encoding="utf-8")
    assert "Number.isSafeInteger(id)" in source
    assert "Number.isFinite(id)" not in source
