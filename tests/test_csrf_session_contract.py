"""E9-Q01 / E9-Q02 — CSRF + session contract tests.

Default: pure unit path via Node/tsx against exported dash auth helpers
(``csrfTokensMatch``, ``requireSessionAndCsrf``). No live web server.

Integration (optional): set ``RUN_WEB=1`` and ``DASH_BASE_URL`` to hit a
running Next instance with documented curl expectations in
``scripts/factory/test_csrf_contract.md``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
UNIT_MTS = Path(__file__).resolve().parent / "csrf_session_unit.mts"
CONTRACT_MD = ROOT / "scripts" / "factory" / "test_csrf_contract.md"


def _npx() -> str:
    found = shutil.which("npx")
    if not found:
        pytest.skip("npx not available")
    return found


def test_csrf_helper_and_guard_unit() -> None:
    """Logout without CSRF → 400 csrf_failed; mutate without session → 401."""
    assert UNIT_MTS.is_file(), f"missing {UNIT_MTS}"
    assert (WEB / "src" / "lib" / "auth" / "csrf.ts").is_file()
    npx = _npx()
    # ESM resolves `next` from the importing file's tree — stage under web/.
    staged = WEB / ".csrf_session_unit.mts"
    staged.write_text(UNIT_MTS.read_text(encoding="utf-8"), encoding="utf-8")
    try:
        proc = subprocess.run(
            [npx, "--yes", "tsx", str(staged.name)],
            cwd=str(WEB),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    finally:
        staged.unlink(missing_ok=True)
    if proc.returncode != 0:
        pytest.fail(
            f"csrf_session_unit.mts failed ({proc.returncode}):\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    assert "CSRF_SESSION_UNIT_OK" in proc.stdout


def test_csrf_contract_doc_exists() -> None:
    text = CONTRACT_MD.read_text(encoding="utf-8")
    assert "csrf_failed" in text
    assert "401" in text
    assert "X-CSRF-Token" in text
    assert "/api/v1/auth/logout" in text


@pytest.mark.skipif(os.environ.get("RUN_WEB") != "1", reason="set RUN_WEB=1")
def test_mutate_without_session_live() -> None:
    """E9-Q02 live: POST /watchlist with no cookies → 401 (or 503 fail-closed)."""
    base = os.environ.get("DASH_BASE_URL", "").rstrip("/")
    if not base:
        pytest.skip("DASH_BASE_URL required when RUN_WEB=1")
    req = urllib.request.Request(
        f"{base}/api/v1/watchlist",
        data=b'{"symbol":"JKH.N0000"}',
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            pytest.fail(f"expected 401/503, got {resp.status}")
    except urllib.error.HTTPError as exc:
        assert exc.code in {401, 503}, f"unexpected status {exc.code}"
        body = json.loads(exc.read().decode())
        if exc.code == 401:
            assert body.get("error", {}).get("code") == "unauthorized"


@pytest.mark.skipif(os.environ.get("RUN_WEB") != "1", reason="set RUN_WEB=1")
def test_logout_without_csrf_live() -> None:
    """E9-Q01 live: session cookie only on logout → 400 csrf_failed.

    Requires demo auth so we can mint a session (see test_csrf_contract.md).
    Skips if demo login is disabled (403).
    """
    base = os.environ.get("DASH_BASE_URL", "").rstrip("/")
    if not base:
        pytest.skip("DASH_BASE_URL required when RUN_WEB=1")
    tid = os.environ.get("DASH_DEMO_TELEGRAM_ID", "123456789")
    login_req = urllib.request.Request(
        f"{base}/api/v1/auth/demo",
        data=json.dumps({"telegram_id": int(tid)}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(login_req, timeout=10) as resp:
            set_cookie = resp.headers.get_all("Set-Cookie") or []
            if not set_cookie:
                # urllib may expose single header
                raw = resp.headers.get("Set-Cookie")
                set_cookie = [raw] if raw else []
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            pytest.skip("demo auth disabled — cannot mint session for CSRF live test")
        raise

    session_cookie = None
    for line in set_cookie:
        if line.startswith("chime_session="):
            session_cookie = line.split(";", 1)[0]
            break
    if not session_cookie:
        pytest.skip("no chime_session Set-Cookie from demo login")

    logout_req = urllib.request.Request(
        f"{base}/api/v1/auth/logout",
        data=b"",
        headers={"Cookie": session_cookie},
        method="POST",
    )
    try:
        with urllib.request.urlopen(logout_req, timeout=10) as resp:
            pytest.fail(f"expected 400 csrf_failed, got {resp.status}")
    except urllib.error.HTTPError as exc:
        assert exc.code == 400, f"expected 400 got {exc.code}"
        body = json.loads(exc.read().decode())
        assert body.get("error", {}).get("code") == "csrf_failed"
