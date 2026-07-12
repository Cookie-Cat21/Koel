"""Wave28: medium+ bugs — sector ids, browse limits, toIso timestamps, session.

1. Market page sector_id must use digits-only toSafePositiveInt (not
   finiteOrNull + isSafeInteger — oversized digit strings precision-lose).
2. GET /symbols and /market/movers limits/offsets must use digits-only helpers
   (not parseInt float trunc / prefix soft-accept).
3. Market / watchlist / alerts / history / symbol timestamps must fail-closed
   via toIso (no raw overlong / control-laden echo).
4. Session verify must digits-only user_id + length-capped sid.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_market_sector_id_uses_safe_positive_int() -> None:
    page = WEB / "src" / "app" / "market" / "page.tsx"
    source = page.read_text(encoding="utf-8")
    assert "toSafePositiveInt(r.sector_id)" in source
    assert "finiteOrNull(r.sector_id)" not in source


def test_symbols_and_movers_limits_digits_only() -> None:
    for rel in (
        "src/app/api/v1/symbols/route.ts",
        "src/app/api/v1/market/movers/route.ts",
    ):
        source = (WEB / rel).read_text(encoding="utf-8")
        assert "toSafePositiveInt" in source, rel
        assert "Number.parseInt" not in source, rel


def test_symbols_offset_digits_only() -> None:
    source = (WEB / "src/app/api/v1/symbols/route.ts").read_text(
        encoding="utf-8"
    )
    assert "toNonNegativeSafeInt" in source
    assert "Number.parseInt" not in source


def test_pages_use_to_iso_for_timestamps() -> None:
    for rel in (
        "src/app/market/page.tsx",
        "src/app/watchlist/page.tsx",
        "src/app/symbols/[symbol]/page.tsx",
        "src/app/alerts/history/page.tsx",
        "src/app/alerts/page.tsx",
    ):
        source = (WEB / rel).read_text(encoding="utf-8")
        assert "toIso" in source, rel


def test_session_verify_safe_user_id_and_sid_cap() -> None:
    source = (WEB / "src/lib/auth/session.ts").read_text(encoding="utf-8")
    assert "toSafePositiveInt" in source
    assert "MAX_SESSION_SID_LENGTH" in source
    assert 'typeof json.user_id !== "number"' not in source
