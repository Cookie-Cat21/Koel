"""Wave48: medium+ bugs — sectors SYMBOL_RE, SSR statusText, client CL.

1. Sectors GET must ``normalizeSymbol`` sector codes (EGY-style) — sanitize
   ``MAX_SECTOR_SYMBOL_LENGTH`` used to egress non-ticker junk into board JSON.
2. ``serverApiGet`` must not reflect upstream ``statusText`` (hostile
   Reason-Phrase used to balloon SSR Response metadata).
3. Browser ``apiMutate`` / demo login / NavSession ``/me`` must early-reject
   oversized claimed ``Content-Length`` before allocating the body buffer
   (parity with SSR ``serverApiGet`` / HEALTH_URL proxy).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_sectors_route_normalizes_symbol() -> None:
    source = (
        WEB / "src" / "app" / "api" / "v1" / "sectors" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "normalizeSymbol(row.symbol)" in source
    assert "MAX_SECTOR_SYMBOL_LENGTH" not in source
    assert "sanitizeDisclosureText(\n        row.symbol" not in source


def test_server_api_get_drops_status_text_reflection() -> None:
    source = (WEB / "src" / "lib" / "api" / "server-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert "statusText: res.statusText" not in source
    assert "statusText:" not in source
    assert "application/json; charset=utf-8" in source


def test_api_mutate_content_length_early_reject() -> None:
    source = (WEB / "src" / "lib" / "api" / "client-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert "readBoundedResponseText" in source
    assert "CLIENT_API_BODY_MAX_CHARS" in source
    assert "await res.text()" not in source
    assert "Response too large." in source
    helper = (WEB / "src" / "lib" / "api" / "read-bounded-text.ts").read_text(
        encoding="utf-8"
    )
    assert 'res.headers.get("content-length")' in helper
    assert "claimed > cap" in helper
    assert "getReader" in helper


def test_login_and_nav_content_length_early_reject() -> None:
    login = (WEB / "src" / "components" / "login-form.tsx").read_text(
        encoding="utf-8"
    )
    assert "readBoundedResponseText" in login
    assert "CLIENT_API_BODY_MAX_CHARS" in login
    assert "await res.text()" not in login

    nav = (WEB / "src" / "components" / "nav-session.tsx").read_text(
        encoding="utf-8"
    )
    assert "readBoundedResponseText" in nav
    assert "MAX_ME_BODY_CHARS" in nav
    assert "await res.text()" not in nav
    assert "readBoundedResponseText(res, MAX_ME_BODY_CHARS)" in nav
