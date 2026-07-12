"""Wave35: medium+ bugs — SSRF host, session mint, CSRF decode, formatTs, symbol decode.

1. ``serverApiGet`` must reject absolute/scheme-relative paths and must not
   prefer spoofable ``Host`` / ``X-Forwarded-Host`` (cookie-bearing SSR fetch
   SSRF) — origin from ``resolveInternalOrigin`` / env / loopback only.
2. ``mintSessionToken`` must require positive SafeInteger ``userId``.
3. Browser CSRF cookie decode must catch ``URIError`` (malformed ``%``).
4. ``formatTs`` must reject overlong / control-laden strings (parity with
   ``toIso``).
5. Dynamic ``[symbol]`` routes/pages must use ``normalizeSymbolParam`` /
   ``safeDecodeURIComponent`` so malformed percent-encoding is 400/notFound,
   not an uncaught 500; metadata must not echo hostile raw.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_server_api_get_rejects_absolute_and_xfh() -> None:
    source = (WEB / "src" / "lib" / "api" / "server-fetch.ts").read_text(encoding="utf-8")
    assert "isSafeInternalHost" in source
    assert "resolveInternalOrigin" in source
    assert "isSafeServerApiPath" in source
    assert "isLoopbackHost" in source
    assert "DASH_INTERNAL_ORIGIN" in source
    # Must not prefer client-spoofable Host / X-Forwarded-Host for cookie fetch.
    assert 'h.get("x-forwarded-host")' not in source
    assert "${proto}://${host}${path}" not in source
    assert 'path.startsWith("http") ? path' not in source
    assert 'redirect: "error"' in source


def test_mint_session_requires_safe_positive_user_id() -> None:
    source = (WEB / "src" / "lib" / "auth" / "session.ts").read_text(encoding="utf-8")
    assert "Number.isSafeInteger(userId)" in source
    assert "userId <= 0" in source
    assert 'throw new Error("userId must be a positive SafeInteger")' in source


def test_csrf_cookie_decode_fail_closed() -> None:
    source = (WEB / "src" / "lib" / "api" / "client-fetch.ts").read_text(encoding="utf-8")
    assert "decodeURIComponent(raw)" in source or (
        "decodeURIComponent(trimmed.slice(prefix.length))" in source
    )
    # Must wrap decode in try/catch — bare decodeURIComponent used to throw.
    assert "try {" in source
    assert "catch {" in source


def test_format_ts_rejects_overlong_and_controls() -> None:
    source = (WEB / "src" / "lib" / "format.ts").read_text(encoding="utf-8")
    assert "MAX_ISO_INPUT_LENGTH" in source
    assert "CTRL_RE" in source
    assert "trimmed.length > MAX_ISO_INPUT_LENGTH" in source
    assert "const d = new Date(iso);" not in source
    # W62: range-gate parity with safeToIsoString (length alone was insufficient).
    assert "MAX_DATE_MS" in source
    assert "Math.abs(t) > MAX_DATE_MS" in source


def test_symbol_routes_use_normalize_symbol_param() -> None:
    helper = (WEB / "src" / "lib" / "api" / "symbol.ts").read_text(encoding="utf-8")
    assert "safeDecodeURIComponent" in helper
    assert "normalizeSymbolParam" in helper

    paths = (
        WEB / "src" / "app" / "api" / "v1" / "watchlist" / "[symbol]" / "route.ts",
        WEB / "src" / "app" / "api" / "v1" / "symbols" / "[symbol]" / "route.ts",
        WEB / "src" / "app" / "api" / "v1" / "symbols" / "[symbol]" / "snapshots" / "route.ts",
        WEB / "src" / "app" / "api" / "v1" / "symbols" / "[symbol]" / "disclosures" / "route.ts",
        WEB / "src" / "app" / "symbols" / "[symbol]" / "page.tsx",
    )
    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert "normalizeSymbolParam(raw)" in source, path.name
        assert "normalizeSymbol(decodeURIComponent(raw))" not in source, path.name


def test_symbol_metadata_fail_closed() -> None:
    page = WEB / "src" / "app" / "symbols" / "[symbol]" / "page.tsx"
    source = page.read_text(encoding="utf-8")
    assert 'normalizeSymbolParam(raw) ?? "Symbol"' in source
    assert "normalizeSymbol(decodeURIComponent(raw)) ?? raw" not in source
