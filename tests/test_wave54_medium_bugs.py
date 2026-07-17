"""Wave54: medium+ bugs — sanitize maxLen, empty title, skeleton, page caps.

1. ``sanitizeDisclosureText`` must fail-closed on non-integer / non-finite /
   oversized ``maxLen`` — ``Math.max(1, NaN) === NaN`` used to disable the
   length gate (``length > NaN`` is always false → uncapped egress).
2. ``EmptyState`` must sanitize + length-cap titles (parity with toast /
   inline-error) so a misbuilt caller cannot balloon the status region.
3. ``InlineError`` must typeof-guard before ``.replace`` (non-string truthy
   props used to throw).
4. ``ListPageSkeleton`` must clamp ``rows`` (``Array.from({ length: Inf })``
   throws; huge N OOMs the loading shell).
5. Symbol / history / market page JSON parsers must break at API-parity caps
   so a hostile body within the SSR byte bound cannot allocate unbounded
   React lists.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_sanitize_disclosure_text_maxlen_fail_closed() -> None:
    source = (WEB / "src" / "lib" / "api" / "disclosure-safe.ts").read_text(
        encoding="utf-8"
    )
    assert "MAX_SANITIZE_TEXT_CAP" in source
    assert "resolveSanitizeTextCap" in source
    assert "Number.isInteger(maxLen)" in source
    assert "resolveSanitizeTextCap(maxLen)" in source
    # Uncapped Math.max(1, NaN) footgun must not remain.
    assert "Math.max(1, maxLen)" not in source


def test_empty_state_sanitizes_title() -> None:
    source = (WEB / "src" / "components" / "empty-state.tsx").read_text(
        encoding="utf-8"
    )
    assert "MAX_EMPTY_STATE_TITLE_LENGTH" in source
    assert "sanitizeEmptyStateTitle" in source
    assert "sanitizeEmptyStateTitle(title)" in source
    # Must not render raw title prop.
    assert "\n          {title}\n" not in source
    assert "{safeTitle}" in source


def test_inline_error_typeof_guard() -> None:
    source = (WEB / "src" / "components" / "inline-error.tsx").read_text(
        encoding="utf-8"
    )
    assert 'typeof raw !== "string"' in source
    assert "sanitizeInlineError(message)" in source


def test_list_page_skeleton_clamps_rows() -> None:
    source = (WEB / "src" / "components" / "skeleton.tsx").read_text(
        encoding="utf-8"
    )
    assert "MAX_SKELETON_ROWS" in source
    assert "safeRows" in source
    assert "Number.isInteger(rows)" in source
    assert "Array.from({ length: safeRows }" in source
    # Uncapped rows must not reach Array.from.
    assert "Array.from({ length: rows }" not in source


def test_page_parsers_cap_list_lengths() -> None:
    symbol = (WEB / "src" / "app" / "symbols" / "[symbol]" / "page.tsx").read_text(
        encoding="utf-8"
    )
    data = (WEB / "src" / "lib" / "db" / "symbol-page-data.ts").read_text(
        encoding="utf-8"
    )
    assert "MAX_PAGE_SNAPSHOT_POINTS" in symbol
    assert "points.length >= MAX_PAGE_SNAPSHOT_POINTS" in symbol
    # Disclosures load via Postgres with a hard LIMIT clamp (not client JSON parse).
    assert "Math.min(Math.max(limit, 1), 100)" in data
    assert "loadSymbolPageDisclosures(symbol, 20)" in symbol

    history = (WEB / "src" / "app" / "alerts" / "history" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "MAX_PAGE_HISTORY_EVENTS" in history
    assert "events.length >= MAX_PAGE_HISTORY_EVENTS" in history

    market = (WEB / "src" / "app" / "market" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "MAX_PAGE_MARKET_ITEMS" in market
    assert "MAX_PAGE_SECTOR_ITEMS" in market
    assert "out.length >= MAX_PAGE_MARKET_ITEMS" in market
    assert "out.length >= MAX_PAGE_SECTOR_ITEMS" in market
