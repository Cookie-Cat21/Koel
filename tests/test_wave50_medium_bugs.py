"""Wave50: medium+ bugs — toast/inline error caps, format digits, sparkline.

1. Toast ``push`` must sanitize + length-cap message copy (parity with
   ``MAX_API_ERROR_MESSAGE_LENGTH``) so a misbuilt caller cannot balloon
   the live region with controls / multi-KB strings.
2. ``InlineError`` must sanitize + length-cap before render (same posture).
3. ``formatNumber`` must fail-closed on non-integer / negative / oversized
   ``digits`` — V8 ``toLocaleString`` throws ``RangeError`` on hostile
   fraction-digit options.
4. ``finiteSparklinePoints`` must cap series length at
   ``MAX_SPARKLINE_POINTS`` (parity with snapshots API max 200) so a
   hostile points array cannot allocate unbounded SVG polylines.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_toast_sanitizes_and_caps_message() -> None:
    source = (WEB / "src" / "components" / "toast.tsx").read_text(
        encoding="utf-8"
    )
    assert "MAX_TOAST_MESSAGE_LENGTH" in source
    assert "sanitizeToastMessage" in source
    assert "sanitizeToastMessage(" in source
    assert "CTRL_RE" in source
    # Must not push raw caller strings into state.
    assert "{ id, message, tone }" not in source
    assert "{ id, message: safe, tone }" in source


def test_inline_error_sanitizes_and_caps_message() -> None:
    source = (WEB / "src" / "components" / "inline-error.tsx").read_text(
        encoding="utf-8"
    )
    assert "MAX_INLINE_ERROR_LENGTH" in source
    assert "sanitizeInlineError" in source
    assert "sanitizeInlineError(message)" in source
    # Must not render raw message prop.
    assert "\n      {message}\n" not in source
    assert "{safe}" in source


def test_format_number_digits_fail_closed() -> None:
    source = (WEB / "src" / "lib" / "format.ts").read_text(encoding="utf-8")
    assert "MAX_FORMAT_FRACTION_DIGITS" in source
    assert "Number.isInteger(digits)" in source
    assert "digits <= MAX_FORMAT_FRACTION_DIGITS" in source
    # Uncapped digits must not reach toLocaleString options.
    assert "minimumFractionDigits: digits," not in source
    assert "minimumFractionDigits: frac," in source


def test_sparkline_caps_series_length() -> None:
    source = (WEB / "src" / "lib" / "sparkline.ts").read_text(encoding="utf-8")
    assert "MAX_SPARKLINE_POINTS" in source
    assert "out.length >= MAX_SPARKLINE_POINTS" in source
    assert "200" in source
