"""Wave59: medium+ bugs — sparkline abs-cap, toIso range, decode/age.

1. ``finiteSparklinePoints`` must abs-cap prices via ``MAX_SPARKLINE_ABS_PRICE``
   (parity ``MAX_FORMAT_ABS_VALUE``) — hostile ``1e308`` used to enter SVG
   span math and balloon ``toFixed`` polyline coordinates.
2. ``toIso`` must fail-closed on out-of-range Date/number values (and wrap
   ``toISOString``) so extreme timestamps cannot throw or egress overlong
   expanded-year ISO into dash JSON.
3. ``safeDecodeURIComponent`` must typeof-guard non-strings (ToString coerce
   used to mint junk path segments).
4. Health ``formatAge`` must cap day labels via ``MAX_HEALTH_AGE_DAYS`` —
   extreme past ISO used to render multi-million-day age copy.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_sparkline_abs_caps_price() -> None:
    source = (WEB / "src" / "lib" / "sparkline.ts").read_text(encoding="utf-8")
    assert "MAX_SPARKLINE_ABS_PRICE" in source
    assert "1e15" in source
    assert "Math.abs(price) <= MAX_SPARKLINE_ABS_PRICE" in source


def test_to_iso_fail_closed_date_range() -> None:
    source = (WEB / "src" / "lib" / "api" / "time.ts").read_text(encoding="utf-8")
    assert "safeToIsoString" in source
    assert "MAX_DATE_MS" in source
    assert "8.64e15" in source
    assert "Math.abs(t) > MAX_DATE_MS" in source
    assert "iso.length > MAX_ISO_INPUT_LENGTH" in source
    assert "return value.toISOString();" not in source
    assert "return d.toISOString();" not in source


def test_safe_decode_uri_typeof_guard() -> None:
    source = (WEB / "src" / "lib" / "api" / "symbol.ts").read_text(encoding="utf-8")
    assert "export function safeDecodeURIComponent(raw: unknown)" in source
    chunk = source.split("export function safeDecodeURIComponent")[1].split(
        "export function normalizeSymbol"
    )[0]
    assert 'typeof raw !== "string"' in chunk


def test_health_format_age_day_cap() -> None:
    source = (WEB / "src" / "app" / "health" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "MAX_HEALTH_AGE_DAYS" in source
    assert "9999" in source
    assert "days > MAX_HEALTH_AGE_DAYS" in source
