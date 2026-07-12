"""Wave46: medium+ bugs — page SYMBOL_RE + health watched_missing + CL.

1. Market / health / symbol-detail page parsers must fail closed on symbols
   via ``normalizeSymbol`` (drop sanitize ``MAX_HISTORY_SYMBOL_LENGTH``
   fallback that let non-CSE tickers render as links / React keys).
2. Health proxy ``sanitizeWatchedMissing`` must use ``normalizeSymbol`` —
   hostile HEALTH_URL used to egress 512-char non-ticker strings into ops JSON.
3. Health proxy must early-reject oversize claimed ``Content-Length`` before
   ``res.text()`` (parity with ``serverApiGet``).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_market_page_normalizes_symbol_egress() -> None:
    source = (WEB / "src" / "app" / "market" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "normalizeSymbol(r.symbol)" in source
    assert "MAX_HISTORY_SYMBOL_LENGTH" not in source


def test_health_page_normalizes_watched_missing() -> None:
    source = (WEB / "src" / "app" / "health" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "normalizeSymbol(item)" in source
    assert "MAX_HISTORY_SYMBOL_LENGTH" not in source


def test_symbol_detail_normalizes_payload_symbol() -> None:
    source = (
        WEB / "src" / "app" / "symbols" / "[symbol]" / "page.tsx"
    ).read_text(encoding="utf-8")
    assert "normalizeSymbol(r.symbol)" in source
    assert "MAX_HISTORY_SYMBOL_LENGTH" not in source


def test_health_api_watched_missing_normalize_symbol() -> None:
    source = (
        WEB / "src" / "app" / "api" / "v1" / "health" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "normalizeSymbol(item)" in source
    watched_fn = source.split("function sanitizeWatchedMissing", 1)[1].split(
        "export function sanitizeCircuits", 1
    )[0]
    assert "HEALTH_STRING_MAX" not in watched_fn
    assert "item.replace(" not in watched_fn


def test_health_proxy_content_length_early_reject() -> None:
    source = (
        WEB / "src" / "app" / "api" / "v1" / "health" / "route.ts"
    ).read_text(encoding="utf-8")
    assert 'res.headers.get("content-length")' in source
    assert "claimed > HEALTH_PROXY_BODY_MAX_BYTES" in source
    cl_idx = source.index('res.headers.get("content-length")')
    text_idx = source.index("await res.text()")
    assert cl_idx < text_idx
