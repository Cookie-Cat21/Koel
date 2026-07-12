"""Wave33: medium+ bugs — session/CSRF token caps + HEALTH_URL body bound.

1. ``verifySessionToken`` must reject overlong forged cookies before HMAC /
   JSON.parse (``MAX_SESSION_TOKEN_LENGTH``).
2. ``csrfTokensMatch`` must reject overlong header/cookie before Buffer alloc
   (``MAX_CSRF_TOKEN_LENGTH``).
3. HEALTH_URL proxy must bound response body bytes before JSON.parse
   (``HEALTH_PROXY_BODY_MAX_BYTES``) so a hostile upstream cannot OOM the dash.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_session_token_length_capped() -> None:
    source = (WEB / "src" / "lib" / "auth" / "session.ts").read_text(
        encoding="utf-8"
    )
    assert "MAX_SESSION_TOKEN_LENGTH" in source
    assert "token.length > MAX_SESSION_TOKEN_LENGTH" in source
    assert "sig.length > 128" in source


def test_csrf_token_length_capped() -> None:
    source = (WEB / "src" / "lib" / "auth" / "csrf.ts").read_text(
        encoding="utf-8"
    )
    assert "MAX_CSRF_TOKEN_LENGTH" in source
    assert "headerToken.length > MAX_CSRF_TOKEN_LENGTH" in source
    assert "cookieToken.length > MAX_CSRF_TOKEN_LENGTH" in source


def test_health_proxy_body_bounded() -> None:
    source = (
        WEB / "src" / "app" / "api" / "v1" / "health" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "HEALTH_PROXY_BODY_MAX_BYTES" in source
    assert "readBoundedResponseText" in source
    assert "await res.json()" not in source
    assert "await res.text()" not in source
