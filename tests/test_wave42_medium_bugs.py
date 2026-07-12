"""Wave42: medium+ bugs — SSR Cookie/JSON CT + jsonError egress caps.

1. ``serverApiGet`` must cap the forwarded ``Cookie`` header via
   ``SERVER_API_COOKIE_MAX_CHARS`` (oversize → 502, no loopback fetch).
2. ``serverApiGet`` must force ``application/json; charset=utf-8`` —
   never reflect upstream Content-Type.
3. ``serverApiGet`` must early-reject oversize claimed ``Content-Length``.
4. ``jsonError`` must strip controls and length-cap ``code`` /
   ``message`` so a misbuilt caller cannot balloon API JSON egress
   (parity with browser ``apiErrorMessage`` / ``MAX_API_ERROR_MESSAGE_LENGTH``).
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


def test_server_api_forces_json_content_type() -> None:
    source = (WEB / "src" / "lib" / "api" / "server-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert 'res.headers.get("content-type")' not in source
    assert "Content-Type\": contentType" not in source
    assert "const contentType" not in source


def test_server_api_content_length_early_reject() -> None:
    source = (WEB / "src" / "lib" / "api" / "server-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert "readBoundedResponseText" in source
    assert "SERVER_API_BODY_MAX_BYTES" in source
    assert "await res.text()" not in source
    helper = (WEB / "src" / "lib" / "api" / "read-bounded-text.ts").read_text(
        encoding="utf-8"
    )
    assert "toNonNegativeSafeInt" in helper
    assert 'res.headers.get("content-length")' in helper
    assert "claimed > cap" in helper
    assert "getReader" in helper


def test_json_error_caps_code_and_message() -> None:
    source = (WEB / "src" / "lib" / "auth" / "errors.ts").read_text(
        encoding="utf-8"
    )
    assert "MAX_JSON_ERROR_CODE_LENGTH" in source
    assert "MAX_JSON_ERROR_MESSAGE_LENGTH" in source
    assert "sanitizeErrorCode" in source
    assert "sanitizeErrorMessage" in source
    assert "sanitizeErrorCode(code)" in source
    assert "sanitizeErrorMessage(message)" in source
    # Must not raw-egress caller strings.
    assert "error: { code, message }" not in source
