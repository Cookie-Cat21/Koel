"""Wave58: medium+ bugs — threshold abs-cap + typeof sanitize guards.

1. ``cappedAlertThreshold`` must reject absurd finite magnitudes via
   ``Math.abs(n) > MAX_ALERT_THRESHOLD`` — upper-bound-only
   ``n <= MAX_ALERT_THRESHOLD`` used to egress ``-1e308`` /
   ``-Number.MAX_VALUE`` from mapRule / GET ``/alerts`` / alerts page.
2. ``sanitizeHistoryMessage`` must typeof-guard non-strings (``.replace``
   used to throw on hostile PG / wrong-shape values).
3. ``sanitizeToastMessage`` must typeof-guard non-strings (parity
   InlineError).
4. ``jsonError`` sanitizers must typeof-guard ``code`` / ``message`` so a
   misbuilt caller cannot 500 the route on ``.replace``.
5. Filing URL allowlist (``normalizeHttpsUrl`` / ``safePdfUrl``) must
   typeof-guard — non-string ``pdf_url`` / ``url`` used to throw on
   ``.trim()`` and 503 the whole disclosures list.
6. ``normalizeBriefStatus`` must typeof-guard non-strings.
7. ``escapeLikePattern`` must typeof-guard (non-string used to throw mid
   browse LIKE escape).
8. ``apiErrorMessage`` must sanitize non-empty fallbacks (uncapped /
   control-laden fallbacks used to balloon toast / inline UI).
9. EmptyState string descriptions must sanitize + length-cap (parity
   title / toast).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_capped_alert_threshold_abs_cap() -> None:
    finite = (WEB / "src" / "lib" / "api" / "finite-number.ts").read_text(
        encoding="utf-8"
    )
    assert "export function cappedAlertThreshold" in finite
    assert "Math.abs(n) > MAX_ALERT_THRESHOLD" in finite
    assert "Number.isFinite(n)" in finite

    db = (WEB / "src" / "lib" / "db.ts").read_text(encoding="utf-8")
    assert "cappedAlertThreshold(toFiniteNumber(row.threshold))" in db
    assert "n <= MAX_ALERT_THRESHOLD" not in db

    alerts = (
        WEB / "src" / "app" / "api" / "v1" / "alerts" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "cappedAlertThreshold(toFiniteNumber(row.threshold))" in alerts
    assert "thresholdRaw != null && thresholdRaw <= MAX_ALERT_THRESHOLD" not in alerts

    page = (WEB / "src" / "app" / "alerts" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "cappedAlertThreshold(toFiniteNumber(r.threshold))" in page
    assert "n <= MAX_ALERT_THRESHOLD" not in page


def test_history_message_typeof_guard() -> None:
    source = (
        WEB / "src" / "app" / "api" / "v1" / "alerts" / "history" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "raw: unknown" in source
    chunk = source.split("function sanitizeHistoryMessage")[1].split(
        "function deriveDeliveryStatus"
    )[0]
    assert 'typeof raw !== "string"' in chunk


def test_toast_sanitize_typeof_guard() -> None:
    source = (WEB / "src" / "components" / "toast.tsx").read_text(
        encoding="utf-8"
    )
    assert "export function sanitizeToastMessage(raw: unknown)" in source
    assert 'typeof raw !== "string"' in source
    assert 'typeof message === "string" ? message : "Something went wrong."' not in source
    assert "sanitizeToastMessage(message)" in source


def test_json_error_sanitize_typeof_guards() -> None:
    source = (WEB / "src" / "lib" / "auth" / "errors.ts").read_text(
        encoding="utf-8"
    )
    assert "function sanitizeErrorCode(code: unknown)" in source
    assert "function sanitizeErrorMessage(message: unknown)" in source
    assert source.count('typeof code !== "string"') >= 1
    assert source.count('typeof message !== "string"') >= 1


def test_filing_url_and_brief_status_typeof_guards() -> None:
    source = (WEB / "src" / "lib" / "api" / "disclosure-safe.ts").read_text(
        encoding="utf-8"
    )
    chunk = source.split("function normalizeHttpsUrl")[1].split(
        "export function safePdfUrl"
    )[0]
    assert 'typeof raw !== "string"' in chunk
    assert "export function safePdfUrl(raw: unknown)" in source
    assert "export function safeAnnouncementUrl(raw: unknown)" in source
    brief = source.split("export function normalizeBriefStatus")[1]
    assert 'typeof raw !== "string"' in brief


def test_escape_like_pattern_typeof_guard() -> None:
    source = (WEB / "src" / "lib" / "api" / "market-query.ts").read_text(
        encoding="utf-8"
    )
    assert "export function escapeLikePattern(literal: unknown)" in source
    assert 'typeof literal !== "string"' in source


def test_api_error_message_sanitizes_fallback() -> None:
    source = (WEB / "src" / "lib" / "api" / "client-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert "function sanitizeApiErrorCopy" in source
    assert "sanitizeApiErrorCopy(fallback" in source
    # Uncapped raw fallback return must not remain.
    assert 'if (typeof raw !== "string" || !raw.trim()) return fallback;' not in source


def test_empty_state_sanitizes_string_description() -> None:
    source = (WEB / "src" / "components" / "empty-state.tsx").read_text(
        encoding="utf-8"
    )
    assert "MAX_EMPTY_STATE_DESCRIPTION_LENGTH" in source
    assert "sanitizeEmptyStateDescription" in source
    assert "safeDescription" in source
    assert "{description}" not in source.split("safeDescription")[1].split(
        "{action"
    )[0]
    assert "{safeDescription}" in source
