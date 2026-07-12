"""Wave55: medium+ bugs — sanitize maxLen, empty title, inline typeof.

1. ``sanitizeDisclosureText`` must fail-closed on non-integer / non-finite /
   oversized ``maxLen`` — ``Math.max(1, NaN) === NaN`` used to disable the
   length gate (``length > NaN`` is always false → uncapped egress).
2. ``EmptyState`` must sanitize + length-cap titles (parity with toast /
   inline-error) so a misbuilt caller cannot balloon the status region.
3. ``InlineError`` / ``sanitizeInlineError`` must typeof-guard before
   ``.replace`` — non-string truthy props used to throw TypeError.
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
    assert 'message == null || message === ""' in source
