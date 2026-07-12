"""Wave30: medium+ bugs — symbol/health/nav fail-closed + SafeInteger limits.

1. Symbol detail must not cast API JSON to SymbolPayload — sanitize text,
   finite quotes, SafeInteger disclosure ids so hostile JSON cannot 500.
2. Health page must fail-closed parse (status/db_ok allowlist, capped strings,
   SafeInteger brief-queue counts) — no HealthPayload cast.
3. NavSession /me must parse via digits-only ``toSafePositiveInt`` (no cast).
4. Snapshots/disclosures/history limits + DELETE /alerts/{id} must use
   digits-only SafeInteger helpers (not ``Number(limitRaw)`` / ``Number(rawId)``).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_symbol_detail_fail_closed_parse() -> None:
    page = WEB / "src" / "app" / "symbols" / "[symbol]" / "page.tsx"
    source = page.read_text(encoding="utf-8")
    assert "parseSymbolPayload" in source
    assert "parseSnapshotsPayload" in source
    assert "parseDisclosuresPayload" in source
    assert "toSafePositiveInt" in source
    assert "sanitizeDisclosureText" in source
    assert "normalizeBriefStatus" in source
    assert "as SymbolPayload)" not in source
    assert "as SnapshotsPayload)" not in source
    assert "as DisclosuresPayload)" not in source


def test_health_page_fail_closed_parse() -> None:
    page = WEB / "src" / "app" / "health" / "page.tsx"
    source = page.read_text(encoding="utf-8")
    assert "parseHealthPayload" in source
    assert "toNonNegativeSafeInt" in source
    assert "sanitizeDisclosureText" in source
    assert "as HealthPayload)" not in source
    assert "HEALTH_UI_WATCHED_MAX" in source


def test_nav_session_fail_closed_me_parse() -> None:
    src = (WEB / "src" / "components" / "nav-session.tsx").read_text(
        encoding="utf-8"
    )
    assert "parseMePayload" in src
    assert "toSafePositiveInt" in src
    assert "as MePayload)" not in src


def test_snapshot_disclosure_history_limits_digits_only() -> None:
    paths = (
        WEB
        / "src"
        / "app"
        / "api"
        / "v1"
        / "symbols"
        / "[symbol]"
        / "snapshots"
        / "route.ts",
        WEB
        / "src"
        / "app"
        / "api"
        / "v1"
        / "symbols"
        / "[symbol]"
        / "disclosures"
        / "route.ts",
        WEB / "src" / "app" / "api" / "v1" / "alerts" / "history" / "route.ts",
    )
    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert "toSafePositiveInt(limitRaw)" in source, path.name
        assert "Number(limitRaw)" not in source, path.name


def test_history_offset_and_ui_limit_digits_only() -> None:
    route = (
        WEB / "src" / "app" / "api" / "v1" / "alerts" / "history" / "route.ts"
    )
    source = route.read_text(encoding="utf-8")
    assert "toNonNegativeSafeInt(offsetRaw, -1)" in source
    assert "Number(offsetRaw)" not in source

    page = WEB / "src" / "app" / "alerts" / "history" / "page.tsx"
    page_src = page.read_text(encoding="utf-8")
    assert "toSafePositiveInt(sp.limit" in page_src
    assert "Number(sp.limit)" not in page_src


def test_delete_alert_uses_safe_positive_int() -> None:
    route = WEB / "src" / "app" / "api" / "v1" / "alerts" / "[id]" / "route.ts"
    source = route.read_text(encoding="utf-8")
    assert "toSafePositiveInt(rawId)" in source
    assert "Number(rawId)" not in source
