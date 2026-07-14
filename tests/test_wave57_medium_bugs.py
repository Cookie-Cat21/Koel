"""Wave57: medium+ bugs — API path / nav / CSRF typeof + length caps.

1. ``isSafeClientApiPath`` / ``isSafeServerApiPath`` must typeof-guard and
   length-cap (``MAX_*_API_PATH_LENGTH``) — non-strings used to throw on
   ``.startsWith``; multi-MB forged paths burned CPU before the /api/v1 gate.
2. ``resolveActiveNavHref`` must typeof-guard + ``MAX_NAV_PATH_LENGTH`` —
   non-string ``active`` / pathname used to throw on ``.startsWith``;
   overlong paths burned prefix matching.
3. ``csrfTokensMatch`` / ``readCsrfCookie`` must typeof-guard — non-string
   header/cookie used to hit ``Buffer.from(number)`` (zero-filled alloc of
   that size) instead of a clean CSRF reject.
4. ``isSafeInternalHost`` / ``hostnameOnly`` must typeof-guard.
5. ``ListPageSkeleton`` must allowlist ``titleWidth`` tokens.
6. Health ``OpsNotice`` / ``StaleOpsNotice`` must sanitize title/copy.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_client_api_path_typeof_and_length_cap() -> None:
    source = (WEB / "src" / "lib" / "api" / "client-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert "MAX_CLIENT_API_PATH_LENGTH" in source
    assert "export function isSafeClientApiPath(path: unknown)" in source
    chunk = source.split("export function isSafeClientApiPath")[1].split(
        "export async function apiMutate"
    )[0]
    assert 'typeof path !== "string"' in chunk
    assert "path.length > MAX_CLIENT_API_PATH_LENGTH" in chunk


def test_server_api_path_typeof_and_length_cap() -> None:
    source = (WEB / "src" / "lib" / "api" / "server-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert "MAX_SERVER_API_PATH_LENGTH" in source
    assert "export function isSafeServerApiPath(path: unknown)" in source
    chunk = source.split("export function isSafeServerApiPath")[1].split(
        "export const SERVER_API_TIMEOUT_MS"
    )[0]
    assert 'typeof path !== "string"' in chunk
    assert "path.length > MAX_SERVER_API_PATH_LENGTH" in chunk


def test_resolve_active_nav_href_typeof_and_length_cap() -> None:
    source = (WEB / "src" / "components" / "app-nav.tsx").read_text(
        encoding="utf-8"
    )
    assert "MAX_NAV_PATH_LENGTH" in source
    chunk = source.split("export function resolveActiveNavHref")[1].split(
        "export function AppNav"
    )[0]
    assert 'typeof current !== "string"' in chunk
    assert "current.length > MAX_NAV_PATH_LENGTH" in chunk


def test_csrf_tokens_match_typeof_guard() -> None:
    source = (WEB / "src" / "lib" / "auth" / "csrf.ts").read_text(
        encoding="utf-8"
    )
    chunk = source.split("export function csrfTokensMatch")[1].split(
        "export function readCsrfCookie"
    )[0]
    assert 'typeof headerToken !== "string"' in chunk
    assert 'typeof cookieToken !== "string"' in chunk

    read_chunk = source.split("export function readCsrfCookie")[1]
    assert 'typeof raw !== "string"' in read_chunk


def test_host_helpers_typeof_guard() -> None:
    source = (WEB / "src" / "lib" / "api" / "server-fetch.ts").read_text(
        encoding="utf-8"
    )
    host_chunk = source.split("export function isSafeInternalHost")[1].split(
        "export function hostnameOnly"
    )[0]
    assert 'typeof host !== "string"' in host_chunk

    name_chunk = source.split("export function hostnameOnly")[1].split(
        "export function isLoopbackHost"
    )[0]
    assert 'typeof host !== "string"' in name_chunk


def test_skeleton_title_width_allowlisted() -> None:
    source = (WEB / "src" / "components" / "skeleton.tsx").read_text(
        encoding="utf-8"
    )
    assert "safeSkeletonTitleWidth" in source
    assert "SKELETON_TITLE_WIDTHS" in source
    assert "safeTitleWidth" in source
    assert "safeTitleWidth)} />" in source
    assert 'cn("h-9", titleWidth)' not in source


def test_health_ops_notice_sanitizes_copy() -> None:
    source = (WEB / "src" / "app" / "health" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "sanitizeOpsNoticeText" in source
    assert "MAX_OPS_NOTICE_TITLE" in source
    assert "MAX_OPS_NOTICE_COPY" in source
    assert "safeTitle" in source
    assert "safeCopy" in source
    assert source.count("sanitizeOpsNoticeText(") >= 2
