"""Wave27: medium+ bugs — toIso fail-closed, delivery honesty, digits-only ids."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_to_iso_fail_closed_no_raw_echo() -> None:
    source = (WEB / "src" / "lib" / "api" / "time.ts").read_text(encoding="utf-8")
    assert "MAX_ISO_INPUT_LENGTH" in source
    assert "if (Number.isNaN(d.getTime())) return value;" not in source
    assert "return value;" not in source
    assert "if (value instanceof Date) return value.toISOString();" not in source


def test_safe_int_helper_digits_only() -> None:
    source = (WEB / "src" / "lib" / "api" / "safe-int.ts").read_text(encoding="utf-8")
    assert "toSafePositiveInt" in source
    assert "toNonNegativeSafeInt" in source
    assert "Math.trunc(" not in source


def test_history_delivery_status_and_offset() -> None:
    source = (
        WEB / "src" / "app" / "api" / "v1" / "alerts" / "history" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "deriveDeliveryStatus" in source
    assert "delivered_unmarked" in source
    assert "toNonNegativeSafeInt" in source
    assert "toSafePositiveInt" in source
    assert "MAX_HISTORY_OFFSET" in source
    assert "Math.min(n, MAX_HISTORY_OFFSET)" in source
    assert "offset = n;" not in source
    assert "Math.trunc(" not in source


def test_history_ui_renders_delivered_unmarked() -> None:
    source = (WEB / "src" / "app" / "alerts" / "history" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "delivered_unmarked" in source
    assert "Delivered (unmarked)" in source


def test_ensure_user_requires_safe_integer_id() -> None:
    source = (WEB / "src" / "lib" / "db.ts").read_text(encoding="utf-8")
    assert "ensure_user returned non-safe id" in source
    assert "return Number(row.id);" not in source


def test_market_page_sanitizes_symbol_name_sector() -> None:
    source = (WEB / "src" / "app" / "market" / "page.tsx").read_text(encoding="utf-8")
    assert "sanitizeDisclosureText" in source
    assert "r.symbol.trim()" not in source


def test_symbols_and_movers_use_safe_integer_limits() -> None:
    for rel in (
        "src/app/api/v1/symbols/route.ts",
        "src/app/api/v1/market/movers/route.ts",
    ):
        source = (WEB / rel).read_text(encoding="utf-8")
        # Digits-only helpers — reject float trunc / sci-notation soft-accept.
        assert "toSafePositiveInt" in source
        assert "Number.parseInt" not in source
        assert "Number.isFinite(limit)" not in source


def test_routes_use_safe_positive_int() -> None:
    for rel in (
        "src/app/api/v1/me/route.ts",
        "src/app/api/v1/sectors/route.ts",
        "src/app/api/v1/alerts/route.ts",
        "src/app/api/v1/symbols/[symbol]/disclosures/route.ts",
    ):
        source = (WEB / rel).read_text(encoding="utf-8")
        assert "toSafePositiveInt" in source


def test_health_timestamps_require_parseable_iso() -> None:
    source = (WEB / "src" / "app" / "api" / "v1" / "health" / "route.ts").read_text(
        encoding="utf-8"
    )
    assert "toIso(cleaned)" in source
    assert "toIso(startedClean)" in source
