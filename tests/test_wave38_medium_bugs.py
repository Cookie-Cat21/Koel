"""Wave38: medium+ bugs — SSR fetch timeout/body bound + alert threshold cap.

1. ``serverApiGet`` must abort via ``SERVER_API_TIMEOUT_MS`` and bound the
   response body with ``SERVER_API_BODY_MAX_BYTES`` before page ``res.json()``
   — a stuck / hostile /api route used to hang or OOM the SSR worker
   (parity with HEALTH_URL proxy bounds). Fail closed to 502 on abort/oversize.
2. Alert create (API + form) must reject thresholds above
   ``MAX_ALERT_THRESHOLD`` — ``Number.MAX_VALUE`` / 1e308 used to persist
   useless rules and balloon JSON.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_server_api_get_timeout_and_body_bound() -> None:
    source = (WEB / "src" / "lib" / "api" / "server-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert "SERVER_API_TIMEOUT_MS" in source
    assert "SERVER_API_BODY_MAX_BYTES" in source
    assert "AbortController" in source
    assert "ctrl.abort()" in source
    assert "readBoundedResponseText" in source
    assert "await res.text()" not in source
    # Must not hand an unbounded fetch Response straight to page parsers.
    assert "return fetch(url," not in source
    assert 'redirect: "error"' in source
    assert "signal: ctrl.signal" in source


def test_alert_threshold_capped() -> None:
    finite = (WEB / "src" / "lib" / "api" / "finite-number.ts").read_text(
        encoding="utf-8"
    )
    assert "MAX_ALERT_THRESHOLD" in finite
    assert "1_000_000_000" in finite

    route = (WEB / "src" / "app" / "api" / "v1" / "alerts" / "route.ts").read_text(
        encoding="utf-8"
    )
    assert "MAX_ALERT_THRESHOLD" in route
    assert "obj.threshold > MAX_ALERT_THRESHOLD" in route
    assert "threshold is too large" in route

    form = (WEB / "src" / "components" / "alert-controls.tsx").read_text(
        encoding="utf-8"
    )
    assert "MAX_ALERT_THRESHOLD" in form
    assert "n > MAX_ALERT_THRESHOLD" in form
    assert "Threshold is too large." in form
    # Cancel must re-validate id — hostile prop must not hit DELETE.
    assert "toSafePositiveInt(ruleId)" in form
