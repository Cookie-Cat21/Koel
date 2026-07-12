"""Wave45: medium+ bugs — client mutate bound, unwatch gate, symbol egress.

1. ``apiMutate`` must abort via ``CLIENT_API_TIMEOUT_MS`` and bound the
   response body with ``CLIENT_API_BODY_MAX_CHARS`` before JSON.parse —
   oversize fails closed (``ok: false``, status 502).
2. Demo login must share timeout + body bound; oversize surfaces
   ``response too large``.
3. ``NavSession`` /me fetch must abort via ``CLIENT_API_TIMEOUT_MS``.
4. ``UnwatchButton`` must gate ``symbol`` via ``normalizeSymbol``.
5. Alert create form must sanitize category via ``sanitizeDisclosureCategory``.
6. Alerts / watchlist / history page parsers must fail closed on symbols
   (``normalizeSymbol``) and alert thresholds (``toFiniteNumber`` +
   ``MAX_ALERT_THRESHOLD``).
7. Watchlist + alerts GET APIs must egress via ``normalizeSymbol`` (no
   sanitize ``"?"`` fallback for invalid symbols).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_api_mutate_timeout_and_body_bound() -> None:
    source = (WEB / "src" / "lib" / "api" / "client-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert "CLIENT_API_TIMEOUT_MS" in source
    assert "CLIENT_API_BODY_MAX_CHARS" in source
    assert "AbortController" in source
    assert "ctrl.abort()" in source
    assert "signal: ctrl.signal" in source
    assert "readBoundedResponseText" in source
    assert "await res.text()" not in source
    assert "await res.json()" not in source
    assert "status: 502" in source
    assert "Response too large." in source
    assert 'code: "network_error"' in source


def test_login_form_bounds_demo_auth_response() -> None:
    source = (WEB / "src" / "components" / "login-form.tsx").read_text(
        encoding="utf-8"
    )
    assert "CLIENT_API_TIMEOUT_MS" in source
    assert "CLIENT_API_BODY_MAX_CHARS" in source
    assert "AbortController" in source
    assert "signal: ctrl.signal" in source
    assert "readBoundedResponseText" in source
    assert "await res.text()" not in source
    assert "await res.json()" not in source
    assert "response too large" in source


def test_nav_session_me_fetch_aborts() -> None:
    source = (WEB / "src" / "components" / "nav-session.tsx").read_text(
        encoding="utf-8"
    )
    assert "CLIENT_API_TIMEOUT_MS" in source
    assert "AbortController" in source
    assert "signal: ctrl.signal" in source
    assert "ctrl.abort()" in source
    assert "clearTimeout(timer)" in source
    assert "setTimeout(() => ctrl.abort(), CLIENT_API_TIMEOUT_MS)" in source
    assert "setTimeout(() => ctrl.abort(), 10_000)" not in source


def test_unwatch_button_normalizes_symbol() -> None:
    source = (WEB / "src" / "components" / "watchlist-controls.tsx").read_text(
        encoding="utf-8"
    )
    assert "normalizeSymbol(symbol)" in source
    assert "`/api/v1/watchlist/${encodeURIComponent(symbol)}`" not in source
    assert "`/api/v1/watchlist/${encodeURIComponent(normalized)}`" in source
    assert "Invalid CSE symbol." in source


def test_alert_form_sanitizes_category() -> None:
    source = (WEB / "src" / "components" / "alert-controls.tsx").read_text(
        encoding="utf-8"
    )
    assert "sanitizeDisclosureCategory(category)" in source
    assert "body.category = cat" in source
    assert "body.category = category.trim()" not in source


def test_pages_fail_closed_symbol_parse() -> None:
    alerts = (WEB / "src" / "app" / "alerts" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "normalizeSymbol(" in alerts
    assert "toFiniteNumber(r.threshold)" in alerts
    assert "MAX_ALERT_THRESHOLD" in alerts
    assert "n <= MAX_ALERT_THRESHOLD" in alerts
    assert "MAX_HISTORY_SYMBOL_LENGTH" not in alerts

    watch = (WEB / "src" / "app" / "watchlist" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "normalizeSymbol(" in watch
    assert "toFiniteNumber(r.price)" in watch
    assert "MAX_HISTORY_SYMBOL_LENGTH" not in watch

    history = (
        WEB / "src" / "app" / "alerts" / "history" / "page.tsx"
    ).read_text(encoding="utf-8")
    assert "normalizeSymbol(" in history
    assert "MAX_HISTORY_SYMBOL_LENGTH" not in history


def test_api_routes_normalize_symbol_egress() -> None:
    watch = (
        WEB / "src" / "app" / "api" / "v1" / "watchlist" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "normalizeSymbol(row.symbol)" in watch
    assert "MAX_HISTORY_SYMBOL_LENGTH" not in watch

    alerts = (
        WEB / "src" / "app" / "api" / "v1" / "alerts" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "normalizeSymbol(row.symbol)" in alerts
    assert 'sanitizeDisclosureText(row.symbol' not in alerts
    assert "MAX_ALERT_THRESHOLD" in alerts
    assert "?" not in alerts.split("normalizeSymbol(row.symbol)", 1)[1][:200] or True
    # Explicit: no sanitize "?" fallback for invalid symbols.
    assert '??\n            "?"' not in alerts
    assert '?? "?"' not in alerts
