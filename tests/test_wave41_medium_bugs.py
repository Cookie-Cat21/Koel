"""Wave41: medium+ bugs — CSRF cookie cap, mapRule threshold, SSR CL early-reject.

1. ``readCsrfCookie`` must reject overlong cookie values before compare
   (parity with browser CSRF decode / ``MAX_CSRF_TOKEN_LENGTH``).
2. ``mapRule`` must cap thresholds via ``MAX_ALERT_THRESHOLD`` so create /
   idempotent JSON cannot balloon with ``Number.MAX_VALUE`` from a poisoned row.
3. ``serverApiGet`` must early-reject oversized ``Content-Length`` before
   ``res.text()`` allocates (defense in depth with the existing body char cap).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_read_csrf_cookie_length_capped() -> None:
    source = (WEB / "src" / "lib" / "auth" / "csrf.ts").read_text(
        encoding="utf-8"
    )
    assert "MAX_CSRF_TOKEN_LENGTH" in source
    assert "raw.length > MAX_CSRF_TOKEN_LENGTH" in source
    assert "return undefined" in source
    # Must not return uncapped cookie values straight from cookies.get.
    assert "return cookies.get(CSRF_COOKIE)?.value;" not in source


def test_map_rule_caps_alert_threshold() -> None:
    source = (WEB / "src" / "lib" / "db.ts").read_text(encoding="utf-8")
    assert "MAX_ALERT_THRESHOLD" in source
    assert "toFiniteNumber(row.threshold)" in source
    assert "n <= MAX_ALERT_THRESHOLD" in source


def test_server_api_get_content_length_early_reject() -> None:
    source = (WEB / "src" / "lib" / "api" / "server-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert "readBoundedResponseText" in source
    assert "SERVER_API_BODY_MAX_BYTES" in source
    assert "await res.text()" not in source
    helper = (WEB / "src" / "lib" / "api" / "read-bounded-text.ts").read_text(
        encoding="utf-8"
    )
    assert 'res.headers.get("content-length")' in helper
    assert "claimed > cap" in helper
    assert "getReader" in helper
