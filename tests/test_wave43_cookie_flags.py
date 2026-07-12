"""Wave43: session/CSRF cookie Secure + SameSite flags.

1. Set helpers must emit Secure (prod) + SameSite=Lax + Path=/
   (ADR 001 / API contract).
2. Logout clear must reuse the same Secure/SameSite/Path attrs.
3. Browser CSRF clear must include SameSite (+ Secure in prod) so
   production Secure cookies actually drop.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
AUTH = WEB / "src" / "lib" / "auth"


def test_cookie_flag_helpers_shared() -> None:
    cfg = (AUTH / "config.ts").read_text(encoding="utf-8")
    assert 'COOKIE_SAME_SITE = "lax"' in cfg
    assert "export function cookieSecure()" in cfg
    # W64: typeof-guard NODE_ENV before production Secure match.
    assert 'typeof raw === "string"' in cfg
    assert 'raw === "production"' in cfg


def test_session_and_csrf_set_secure_samesite() -> None:
    src = (AUTH / "session.ts").read_text(encoding="utf-8")
    assert "cookieSecure()" in src
    assert "COOKIE_SAME_SITE" in src
    assert "secure: cookieSecure()" in src
    assert "sameSite: COOKIE_SAME_SITE" in src
    assert "clearAuthCookieOptions" in src
    # Session is HttpOnly; CSRF double-submit is readable.
    assert "httpOnly: true" in src
    assert "httpOnly: false" in src


def test_logout_clear_matches_set_flags() -> None:
    src = (
        WEB / "src" / "app" / "api" / "v1" / "auth" / "logout" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "clearAuthCookieOptions" in src
    assert "clearAuthCookieOptions(true)" in src
    assert "clearAuthCookieOptions(false)" in src
    # No divergent inline Secure/SameSite that can drift from set helpers.
    assert 'sameSite: "lax"' not in src
    assert "NODE_ENV" not in src


def test_browser_csrf_clear_includes_samesite_secure() -> None:
    src = (AUTH / "session-redirect.ts").read_text(encoding="utf-8")
    assert "clearBrowserCsrfCookie" in src
    assert "SameSite=" in src
    assert "cookieSecure()" in src
    assert 'parts.push("Secure")' in src
    assert "Path=/" in src
    assert "Max-Age=0" in src
    # Bare clear without SameSite/Secure must not remain.
    assert "${CSRF_COOKIE}=; Max-Age=0; Path=/" not in src
