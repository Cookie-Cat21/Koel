"""Wave41: medium+ bugs — client mutate timeout/body, login bound, unwatch gate.

1. ``apiMutate`` must abort via ``CLIENT_API_TIMEOUT_MS`` and bound the
   response body with ``CLIENT_API_BODY_MAX_CHARS`` before JSON.parse —
   a stuck / hostile /api used to hang or OOM the browser tab (parity with
   ``serverApiGet`` SSR bounds). Oversize must fail closed (``ok: false``,
   status 502).
2. Demo login must share the same timeout + body bound (no unbounded
   ``res.json()``); oversize surfaces ``response too large``.
3. ``NavSession`` /me fetch must abort on timeout (``AbortController`` +
   ``CLIENT_API_TIMEOUT_MS``) so a hung /me cannot leave a zombie chip.
4. ``UnwatchButton`` must gate ``symbol`` via ``normalizeSymbol`` before
   DELETE ``/api/v1/watchlist/{symbol}`` (hostile props must not hit the
   route — parity with ``CancelAlertButton`` SafeInteger gate).
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
    assert "rawText.length > CLIENT_API_BODY_MAX_CHARS" in source
    assert "res.text()" in source
    assert "await res.json()" not in source
    assert "status: 502" in source
    assert "Response too large." in source


def test_login_form_bounds_demo_auth_response() -> None:
    source = (WEB / "src" / "components" / "login-form.tsx").read_text(
        encoding="utf-8"
    )
    assert "CLIENT_API_TIMEOUT_MS" in source
    assert "CLIENT_API_BODY_MAX_CHARS" in source
    assert "AbortController" in source
    assert "signal: ctrl.signal" in source
    assert "res.text()" in source
    assert "rawText.length > CLIENT_API_BODY_MAX_CHARS" in source
    assert "response too large" in source
    assert "await res.json()" not in source


def test_nav_session_me_fetch_aborts() -> None:
    source = (WEB / "src" / "components" / "nav-session.tsx").read_text(
        encoding="utf-8"
    )
    assert "CLIENT_API_TIMEOUT_MS" in source
    assert "AbortController" in source
    assert "signal: ctrl.signal" in source
    assert "ctrl.abort()" in source
    assert "clearTimeout(timer)" in source
    assert "MAX_ME_BODY_CHARS" in source


def test_unwatch_button_normalizes_symbol() -> None:
    source = (WEB / "src" / "components" / "watchlist-controls.tsx").read_text(
        encoding="utf-8"
    )
    assert "normalizeSymbol(symbol)" in source
    assert "`/api/v1/watchlist/${encodeURIComponent(symbol)}`" not in source
    assert "`/api/v1/watchlist/${encodeURIComponent(normalized)}`" in source
    assert "Invalid CSE symbol." in source
