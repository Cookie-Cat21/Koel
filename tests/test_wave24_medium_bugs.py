"""Wave24: medium+ bugs — history fail-closed, watchlist decode, login ids.

1. History page must not ``as HistoryPayload`` cast — SafeInteger ids,
   sanitize symbol/event_key, allowlist delivery_status, drop unknown types.
2. DELETE /watchlist/{symbol} must safe-decode the path segment (w33:
   ``normalizeSymbolParam`` — malformed ``%`` must not ``URIError`` 500).
3. Login demo form must parse telegram_id via digits-only toSafePositiveInt
   (Number() precision-loss before SafeInteger check).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_history_page_fail_closed_parse() -> None:
    page = WEB / "src" / "app" / "alerts" / "history" / "page.tsx"
    source = page.read_text(encoding="utf-8")
    assert "toSafePositiveInt" in source
    assert "sanitizeDisclosureText" in source
    assert "isAlertType" in source
    assert "delivered_unmarked" in source
    assert "as HistoryPayload" not in source


def test_watchlist_delete_decodes_symbol() -> None:
    route = (
        WEB / "src" / "app" / "api" / "v1" / "watchlist" / "[symbol]" / "route.ts"
    )
    source = route.read_text(encoding="utf-8")
    # w33: safeDecode via normalizeSymbolParam (URIError → 400).
    assert "normalizeSymbolParam(raw)" in source


def test_login_form_uses_digits_only_telegram_id() -> None:
    form = WEB / "src" / "components" / "login-form.tsx"
    source = form.read_text(encoding="utf-8")
    assert "toSafePositiveInt" in source
    assert "Number(telegramId.trim())" not in source
