"""Wave26: medium+ bugs — mapRule SafeInteger, alerts/watchlist fail-closed.

1. ``mapRule`` must use digits-only ``toSafePositiveInt`` (not ``Number(row.id)``)
   and drop unknown alert types — create/idempotent JSON must not alias rows.
2. ``createAlertRule`` must fail closed when mapped id/type is unsafe.
3. Alerts / watchlist pages must fail-closed parse API JSON (safe ids, sanitize
   symbol/name, drop unknown types) so a hostile body cannot 500 the page or
   mint bad React keys / cancel targets.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_map_rule_uses_safe_positive_int_and_alert_type() -> None:
    db = WEB / "src" / "lib" / "db.ts"
    source = db.read_text(encoding="utf-8")
    assert "toSafePositiveInt(row.id)" in source
    assert "isAlertType(row.type)" in source
    assert "AlertRuleRow | null" in source
    assert "const id = Number(row.id);" not in source
    assert "create_alert_rule returned non-safe rule" in source


def test_alerts_page_fail_closed_parse() -> None:
    page = WEB / "src" / "app" / "alerts" / "page.tsx"
    source = page.read_text(encoding="utf-8")
    assert "toSafePositiveInt" in source
    assert "isAlertType" in source
    assert "normalizeSymbol(" in source
    assert "as AlertsPayload" not in source


def test_watchlist_page_fail_closed_parse() -> None:
    page = WEB / "src" / "app" / "watchlist" / "page.tsx"
    source = page.read_text(encoding="utf-8")
    assert "sanitizeDisclosureText" in source
    assert "normalizeSymbol(" in source
    assert "as WatchlistPayload" not in source
    assert "toFiniteNumber(r.price)" in source
