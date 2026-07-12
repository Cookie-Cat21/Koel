"""Wave53: medium+ bugs — stream-bound response bodies.

``Content-Length`` early-reject alone is insufficient: a missing or
understated CL still lets ``res.text()`` allocate the full stream before
any length check. ``readBoundedResponseText`` streams + cancels past the
byte cap (parity with ``readJsonBody``) for apiMutate, serverApiGet,
HEALTH_URL proxy, demo login, and NavSession ``/me``.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_read_bounded_response_text_streams() -> None:
    source = (WEB / "src" / "lib" / "api" / "read-bounded-text.ts").read_text(
        encoding="utf-8"
    )
    assert "export async function readBoundedResponseText" in source
    assert "getReader" in source
    assert "total > cap" in source
    assert "reader.cancel()" in source
    assert 'res.headers.get("content-length")' in source
    assert "toNonNegativeSafeInt" in source
    assert "await res.text()" not in source
    assert "res.text()" not in source.replace("``res.text()``", "")


def test_client_mutate_uses_bounded_reader() -> None:
    source = (WEB / "src" / "lib" / "api" / "client-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert "readBoundedResponseText" in source
    assert "CLIENT_API_BODY_MAX_CHARS" in source
    assert "await res.text()" not in source
    assert "Response too large." in source


def test_server_api_get_uses_bounded_reader() -> None:
    source = (WEB / "src" / "lib" / "api" / "server-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert "readBoundedResponseText" in source
    assert "SERVER_API_BODY_MAX_BYTES" in source
    assert "await res.text()" not in source
    assert "application/json; charset=utf-8" in source


def test_health_proxy_uses_bounded_reader() -> None:
    source = (
        WEB / "src" / "app" / "api" / "v1" / "health" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "readBoundedResponseText" in source
    assert "HEALTH_PROXY_BODY_MAX_BYTES" in source
    assert "await res.text()" not in source
    assert "health_url_body_too_large" in source


def test_login_and_nav_use_bounded_reader() -> None:
    login = (WEB / "src" / "components" / "login-form.tsx").read_text(
        encoding="utf-8"
    )
    assert "readBoundedResponseText" in login
    assert "CLIENT_API_BODY_MAX_CHARS" in login
    assert "await res.text()" not in login
    assert "response too large" in login

    nav = (WEB / "src" / "components" / "nav-session.tsx").read_text(
        encoding="utf-8"
    )
    assert "readBoundedResponseText" in nav
    assert "MAX_ME_BODY_CHARS" in nav
    assert "await res.text()" not in nav
