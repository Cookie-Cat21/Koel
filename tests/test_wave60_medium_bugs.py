"""Wave60: medium+ bugs — toFiniteNumber abs-cap + API path typeof.

1. ``toFiniteNumber`` must abs-cap via ``MAX_FINITE_ABS_VALUE`` —
   ``Number.isFinite(1e308)`` is true, so hostile finite extremes used to
   reach market/watchlist/sectors/snapshots JSON and page a11y compare
   paths even after display/sparkline fail-closed (waves 55/59).
2. Market / symbol page parsers must coerce via ``toFiniteNumber`` (not a
   local ``finiteOrNull`` that only checked ``Number.isFinite``).
3. ``isSafeClientApiPath`` / ``isSafeServerApiPath`` must typeof-guard —
   non-string paths used to throw on ``.startsWith`` mid-mutate/SSR.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_to_finite_number_abs_cap() -> None:
    source = (WEB / "src" / "lib" / "api" / "finite-number.ts").read_text(
        encoding="utf-8"
    )
    assert "MAX_FINITE_ABS_VALUE" in source
    assert "1e15" in source
    chunk = source.split("export function toFiniteNumber")[1].split(
        "export function cappedAlertThreshold"
    )[0]
    assert "Math.abs(value) > MAX_FINITE_ABS_VALUE" in chunk
    assert "Math.abs(n) > MAX_FINITE_ABS_VALUE" in chunk


def test_market_page_uses_to_finite_number() -> None:
    source = (WEB / "src" / "app" / "market" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "toFiniteNumber" in source
    assert "finiteOrNull" not in source
    assert "toFiniteNumber(r.price)" in source
    assert "toFiniteNumber(r.change_pct)" in source


def test_symbol_page_uses_to_finite_number() -> None:
    source = (
        WEB / "src" / "app" / "symbols" / "[symbol]" / "page.tsx"
    ).read_text(encoding="utf-8")
    data = (WEB / "src" / "lib" / "db" / "symbol-page-data.ts").read_text(
        encoding="utf-8"
    )
    assert "toFiniteNumber" in source
    assert "finiteOrNull" not in source
    assert "toFiniteNumber(snap.rows[0].price)" in data
    assert "toFiniteNumber(r.price)" in source


def test_api_path_guards_typeof() -> None:
    client = (WEB / "src" / "lib" / "api" / "client-fetch.ts").read_text(
        encoding="utf-8"
    )
    server = (WEB / "src" / "lib" / "api" / "server-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert "export function isSafeClientApiPath(path: unknown)" in client
    cchunk = client.split("export function isSafeClientApiPath")[1].split(
        "export async function apiMutate"
    )[0]
    assert 'typeof path !== "string"' in cchunk

    assert "export function isSafeServerApiPath(path: unknown)" in server
    schunk = server.split("export function isSafeServerApiPath")[1].split(
        "export const SERVER_API_TIMEOUT_MS"
    )[0]
    assert 'typeof path !== "string"' in schunk
