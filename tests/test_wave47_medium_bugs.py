"""Wave47: medium+ bugs — client Content-Length early-reject.

w53: stream-bound ``readBoundedResponseText`` supersedes allocate-then-check
``res.text()`` while retaining CL early-reject inside the helper.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


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
    assert "toNonNegativeSafeInt" in helper
    assert 'res.headers.get("content-length")' in helper
    assert "claimed > cap" in helper
    assert "getReader" in helper


def test_login_content_length_early_reject() -> None:
    login = (WEB / "src" / "components" / "login-form.tsx").read_text(
        encoding="utf-8"
    )
    assert "readBoundedResponseText" in login
    assert "CLIENT_API_BODY_MAX_CHARS" in login
    assert "await res.text()" not in login
    assert "response too large" in login


def test_nav_session_content_length_early_reject() -> None:
    nav = (WEB / "src" / "components" / "nav-session.tsx").read_text(
        encoding="utf-8"
    )
    assert "readBoundedResponseText" in nav
    assert "MAX_ME_BODY_CHARS" in nav
    assert "await res.text()" not in nav
    assert "readBoundedResponseText(res, MAX_ME_BODY_CHARS)" in nav
