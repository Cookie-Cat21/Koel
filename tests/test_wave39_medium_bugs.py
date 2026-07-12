"""Wave39: medium+ bugs — /me parse, cancel id, session TTL, threshold, SSR bound.

1. ``NavSession`` ``parseMePayload`` must use ``toIso`` for ``created_at`` and
   cap ``csrf_token`` via ``MAX_CSRF_TOKEN_LENGTH``; body read capped by
   ``MAX_ME_BODY_CHARS`` before JSON.parse (hostile /me must not balloon state).
2. ``CancelAlertButton`` must gate ``ruleId`` via ``toSafePositiveInt`` before
   DELETE ``/api/v1/alerts/{id}`` (NaN/float must not hit the route).
3. ``mintSessionToken`` must require positive SafeInteger ``ttlSeconds``.
4. Alert create (API + form) must reject thresholds above
   ``MAX_ALERT_THRESHOLD``.
5. ``serverApiGet`` must abort + bound body (``SERVER_API_TIMEOUT_MS`` /
   ``SERVER_API_BODY_MAX_BYTES``) before page parsers call ``res.json()``.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_nav_session_me_parse_fail_closed() -> None:
    source = (WEB / "src" / "components" / "nav-session.tsx").read_text(
        encoding="utf-8"
    )
    assert "toIso(r.created_at)" in source
    assert "MAX_CSRF_TOKEN_LENGTH" in source
    assert "MAX_ME_BODY_CHARS" in source
    assert "readBoundedResponseText" in source
    assert "MAX_ME_BODY_CHARS" in source
    assert "await res.text()" not in source
    assert 'typeof r.created_at === "string" && r.created_at' not in source
    assert (
        'csrf_token: typeof r.csrf_token === "string" ? r.csrf_token : undefined'
        not in source
    )


def test_cancel_alert_uses_safe_positive_int() -> None:
    source = (WEB / "src" / "components" / "alert-controls.tsx").read_text(
        encoding="utf-8"
    )
    assert "toSafePositiveInt(ruleId)" in source
    assert "toSafePositiveInt" in source
    assert "`/api/v1/alerts/${ruleId}`" not in source
    assert "`/api/v1/alerts/${id}`" in source


def test_mint_session_ttl_safe_integer() -> None:
    source = (WEB / "src" / "lib" / "auth" / "session.ts").read_text(
        encoding="utf-8"
    )
    assert "Number.isSafeInteger(ttlSeconds)" in source
    assert "ttlSeconds <= 0" in source
    assert 'throw new Error("ttlSeconds must be a positive SafeInteger")' in source


def test_alert_threshold_capped() -> None:
    finite = (WEB / "src" / "lib" / "api" / "finite-number.ts").read_text(
        encoding="utf-8"
    )
    assert "MAX_ALERT_THRESHOLD" in finite
    route = (WEB / "src" / "app" / "api" / "v1" / "alerts" / "route.ts").read_text(
        encoding="utf-8"
    )
    assert "MAX_ALERT_THRESHOLD" in route
    assert "obj.threshold > MAX_ALERT_THRESHOLD" in route
    form = (WEB / "src" / "components" / "alert-controls.tsx").read_text(
        encoding="utf-8"
    )
    assert "n > MAX_ALERT_THRESHOLD" in form


def test_server_api_get_timeout_and_body_bound() -> None:
    source = (WEB / "src" / "lib" / "api" / "server-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert "SERVER_API_TIMEOUT_MS" in source
    assert "SERVER_API_BODY_MAX_BYTES" in source
    assert "AbortController" in source
    assert "readBoundedResponseText" in source
    assert "await res.text()" not in source
    assert 'redirect: "error"' in source
    assert "signal: ctrl.signal" in source
