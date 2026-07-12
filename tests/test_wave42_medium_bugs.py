"""Wave42: medium+ bugs — SSR Cookie cap, JSON Content-Type, CL early-reject.

1. ``serverApiGet`` must cap the forwarded ``Cookie`` header via
   ``SERVER_API_COOKIE_MAX_CHARS`` — a multi-MB Cookie used to amplify into
   the loopback fetch and pressure the SSR worker. Oversize → 502 degraded
   (no internal fetch).
2. ``serverApiGet`` must force ``application/json; charset=utf-8`` on the
   reconstructed Response — never reflect a hostile upstream Content-Type
   into page parsers.
3. ``serverApiGet`` must early-reject oversize claimed ``Content-Length``
   via ``toNonNegativeSafeInt`` before ``res.text()`` allocation.
4. Client mutate / login /me / unwatch contracts retained on branch.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_server_api_cookie_capped() -> None:
    source = (WEB / "src" / "lib" / "api" / "server-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert "SERVER_API_COOKIE_MAX_CHARS" in source
    assert "cookieRaw.length > SERVER_API_COOKIE_MAX_CHARS" in source
    assert 'const cookie = h.get("cookie") ?? ""' not in source
    assert "cookieRaw" in source


def test_server_api_forces_json_content_type() -> None:
    source = (WEB / "src" / "lib" / "api" / "server-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert 'headers: { "Content-Type": "application/json; charset=utf-8" }' in source
    assert 'res.headers.get("content-type")' not in source
    assert "Content-Type\": contentType" not in source
    assert "const contentType" not in source


def test_server_api_content_length_early_reject() -> None:
    source = (WEB / "src" / "lib" / "api" / "server-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert "toNonNegativeSafeInt" in source
    assert 'res.headers.get("content-length")' in source
    assert "claimed > SERVER_API_BODY_MAX_BYTES" in source
    # Content-Length gate must precede body allocation.
    cl_idx = source.index('res.headers.get("content-length")')
    text_idx = source.index("await res.text()")
    assert cl_idx < text_idx


def test_api_mutate_timeout_and_body_bound() -> None:
    source = (WEB / "src" / "lib" / "api" / "client-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert "CLIENT_API_TIMEOUT_MS" in source
    assert "CLIENT_API_BODY_MAX_CHARS" in source
    assert "status: 502" in source
    assert "await res.json()" not in source


def test_login_form_bounds_demo_auth_response() -> None:
    source = (WEB / "src" / "components" / "login-form.tsx").read_text(
        encoding="utf-8"
    )
    assert "CLIENT_API_TIMEOUT_MS" in source
    assert "CLIENT_API_BODY_MAX_CHARS" in source
    assert "await res.json()" not in source


def test_nav_session_me_fetch_aborts() -> None:
    source = (WEB / "src" / "components" / "nav-session.tsx").read_text(
        encoding="utf-8"
    )
    assert "CLIENT_API_TIMEOUT_MS" in source
    assert "AbortController" in source
    assert "signal: ctrl.signal" in source


def test_unwatch_button_normalizes_symbol() -> None:
    source = (WEB / "src" / "components" / "watchlist-controls.tsx").read_text(
        encoding="utf-8"
    )
    assert "normalizeSymbol(symbol)" in source
    assert "`/api/v1/watchlist/${encodeURIComponent(normalized)}`" in source
