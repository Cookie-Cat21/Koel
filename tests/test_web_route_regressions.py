"""E12-Q01 — dash route/page regressions for health degradation and CSE isolation."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
UNIT_MTS = Path(__file__).resolve().parent / "web_health_route_unit.mts"
UNIT_SYMBOLS_MTS = Path(__file__).resolve().parent / "web_symbols_route_unit.mts"
UNIT_MOVERS_MTS = Path(__file__).resolve().parent / "web_movers_route_unit.mts"
UNIT_DISCLOSURES_MTS = Path(__file__).resolve().parent / "web_disclosures_route_unit.mts"

RUNTIME_SUFFIXES = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}
SKIP_DIRS = {".next", "node_modules"}
FORBIDDEN_RUNTIME_TOKENS = (
    "cse.lk",
    "www.cse.lk",
    "CSE_BASE_URL",
    "CSEClient",
    "chime.adapters.cse",
    "companyInfoSummery",
    "chartData",
    "dailyMarketSummery",
    "allSectors",
    "snpData",
    "detailedTrades",
)


def _npx() -> str:
    found = shutil.which("npx")
    if not found:
        pytest.skip("npx not available")
    return found


def _require_web_node_modules() -> None:
    """tsx imports resolve `next` from web/node_modules — skip when absent (CI unit)."""
    if not (WEB / "node_modules" / "next").is_dir():
        pytest.skip("web/node_modules not installed (npm ci in web CI job)")


def _runtime_files() -> list[Path]:
    files: list[Path] = []
    for path in WEB.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        # Staged tsx harnesses written under web/ during unit tests (cleaned in finally).
        if path.name.startswith(".web_") and path.name.endswith("_unit.mts"):
            continue
        if path.suffix in RUNTIME_SUFFIXES:
            files.append(path)
    return sorted(files)


def _is_comment_only_hit(line: str, token: str) -> bool:
    idx = line.lower().find(token.lower())
    if idx < 0:
        return False
    prefix = line[:idx].strip()
    return prefix in {"", "/", "/*"} or prefix.startswith(("//", "/*", "*"))


def test_health_route_degrades_on_poller_missing_and_unreachable() -> None:
    """Real Next route handler: watched_missing/HEALTH_URL failure ⇒ 503 degraded."""
    assert UNIT_MTS.is_file(), f"missing {UNIT_MTS}"
    assert (WEB / "src" / "app" / "api" / "v1" / "health" / "route.ts").is_file()
    _require_web_node_modules()
    npx = _npx()
    staged = WEB / ".web_health_route_unit.mts"
    staged.write_text(UNIT_MTS.read_text(encoding="utf-8"), encoding="utf-8")
    try:
        proc = subprocess.run(
            [npx, "--yes", "tsx", str(staged.name)],
            cwd=str(WEB),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    finally:
        staged.unlink(missing_ok=True)
    if proc.returncode != 0:
        pytest.fail(
            f"web_health_route_unit.mts failed ({proc.returncode}):\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    assert "WEB_HEALTH_ROUTE_UNIT_OK" in proc.stdout


def test_web_runtime_sources_do_not_import_or_call_cse_lk() -> None:
    """web/ runtime code stays Postgres/HEALTH_URL-only, never direct CSE HTTP."""
    hits: list[str] = []
    for path in _runtime_files():
        rel = path.relative_to(ROOT)
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            lowered = line.lower()
            for token in FORBIDDEN_RUNTIME_TOKENS:
                if token.lower() not in lowered:
                    continue
                if _is_comment_only_hit(line, token):
                    continue
                hits.append(f"{rel}:{lineno}: {line.strip()}")

    assert hits == [], "web runtime CSE references found:\n" + "\n".join(hits)


def test_dashboard_pages_render_nfa_footer() -> None:
    """Watchlist, alerts, browse, and health keep the global NFA footer visible."""
    page_paths = [
        WEB / "src" / "app" / "watchlist" / "page.tsx",
        WEB / "src" / "app" / "market" / "page.tsx",
        WEB / "src" / "app" / "alerts" / "page.tsx",
        WEB / "src" / "app" / "health" / "page.tsx",
    ]

    missing: list[str] = []
    for path in page_paths:
        source = path.read_text(encoding="utf-8")
        if 'import { NfaFooter } from "@/components/nfa-footer";' not in source:
            missing.append(f"{path.relative_to(ROOT)} missing import")
        if "<NfaFooter />" not in source:
            missing.append(f"{path.relative_to(ROOT)} missing render")

    assert missing == []


def test_symbols_list_route_requires_snapshots_and_session() -> None:
    """P1-C: GET /api/v1/symbols is Postgres browse from snapshots only (INNER JOIN)."""
    route = WEB / "src" / "app" / "api" / "v1" / "symbols" / "route.ts"
    browse = WEB / "src" / "lib" / "api" / "market-browse.ts"
    assert route.is_file()
    assert browse.is_file()
    source = route.read_text(encoding="utf-8")
    browse_src = browse.read_text(encoding="utf-8")
    assert "requireSession" in source
    # Safe GET: session only — must not demand CSRF.
    assert "requireSessionAndCsrf" not in source
    assert "queryMarketBrowse" in source
    assert "INNER JOIN LATERAL" in browse_src
    assert "LEFT JOIN LATERAL" not in browse_src
    assert "price_snapshots" in browse_src
    assert "escapeLikePattern" in browse_src
    assert "ESCAPE" in browse_src
    assert "normalizeMarketQuery" in source
    assert "MAX_SYMBOLS_OFFSET" in source
    assert "cse.lk" not in source.lower() or all(
        _is_comment_only_hit(line, "cse.lk")
        for line in source.splitlines()
        if "cse.lk" in line.lower()
    )
    assert "cse.lk" not in browse_src.lower() or all(
        _is_comment_only_hit(line, "cse.lk")
        for line in browse_src.splitlines()
        if "cse.lk" in line.lower()
    )


def test_symbols_list_query_validation_static() -> None:
    """P1-C: limit clamp (default 50, max 200) + sort whitelist in route source."""
    route = WEB / "src" / "app" / "api" / "v1" / "symbols" / "route.ts"
    browse = WEB / "src" / "lib" / "api" / "market-browse.ts"
    source = route.read_text(encoding="utf-8")
    browse_src = browse.read_text(encoding="utf-8")
    assert "const DEFAULT_LIMIT = 50;" in source
    assert "const MAX_LIMIT = 200;" in source
    assert "Math.min(limit, MAX_LIMIT)" in source
    assert "limit < 1) limit = DEFAULT_LIMIT" in source or (
        "limit < 1" in source and "DEFAULT_LIMIT" in source
    )
    # Sort whitelist: only symbol|change_pct; anything else → change_pct.
    assert 'sortRaw === "symbol" ? "symbol" : "change_pct"' in source
    assert "queryMarketBrowse" in source
    assert "ps.change_pct DESC NULLS LAST" in browse_src
    assert "s.symbol ASC" in browse_src
    assert "INNER JOIN LATERAL" in browse_src
    assert "LEFT JOIN LATERAL" not in browse_src
    mq = WEB / "src" / "lib" / "api" / "market-query.ts"
    assert mq.is_file()
    mq_src = mq.read_text(encoding="utf-8")
    assert "MAX_MARKET_Q_LENGTH = 64" in mq_src
    assert "escapeLikePattern" in mq_src
    assert "normalizeMarketQuery" in mq_src


def test_market_movers_route_static() -> None:
    """Wave5: GET /api/v1/market/movers reuses browse; sign-filtered; thin fence."""
    route = WEB / "src" / "app" / "api" / "v1" / "market" / "movers" / "route.ts"
    browse = WEB / "src" / "lib" / "api" / "market-browse.ts"
    market = WEB / "src" / "app" / "market" / "page.tsx"
    assert route.is_file()
    assert browse.is_file()
    source = route.read_text(encoding="utf-8")
    browse_src = browse.read_text(encoding="utf-8")
    market_src = market.read_text(encoding="utf-8")
    assert "requireSession" in source
    assert "requireSessionAndCsrf" not in source
    assert "queryMarketBrowse" in source
    assert 'direction === "down" ? "change_pct_asc" : "change_pct"' in source
    assert "direction," in source  # pass sign filter into browse query
    assert 'validation_error"' in source
    assert "direction must be up or down." in source
    assert "const DEFAULT_LIMIT = 20;" in source
    assert "const MAX_LIMIT = 50;" in source
    assert "Math.min(limit, MAX_LIMIT)" in source
    # Thin fence: no search/sector/volume filters on movers (comments ok).
    assert "normalizeMarketQuery" not in source
    for tok in ("sector", "volume", "market_cap", "ohlc"):
        hits = [
            line.strip()
            for line in source.splitlines()
            if tok in line.lower() and not _is_comment_only_hit(line, tok)
        ]
        assert hits == [], f"movers route must not use {tok}: {hits}"
    assert "INNER JOIN LATERAL" in browse_src
    assert "change_pct_asc" in browse_src
    assert "ps.change_pct ASC NULLS LAST" in browse_src
    assert "ps.change_pct > 0" in browse_src
    assert "ps.change_pct < 0" in browse_src
    assert "toFiniteNumber" in browse_src
    # Market page fails closed on bad JSON / missing items[].
    assert "readJsonPayload" in market_src
    assert "asMarketItems" in market_src
    assert "cse.lk" not in source.lower() or all(
        _is_comment_only_hit(line, "cse.lk")
        for line in source.splitlines()
        if "cse.lk" in line.lower()
    )


def test_market_movers_route_unit() -> None:
    """Runtime: sign filter, invalid direction 400, finite egress, session/CSRF."""
    assert UNIT_MOVERS_MTS.is_file(), f"missing {UNIT_MOVERS_MTS}"
    assert (WEB / "src" / "app" / "api" / "v1" / "market" / "movers" / "route.ts").is_file()
    _require_web_node_modules()
    npx = _npx()
    staged = WEB / ".web_movers_route_unit.mts"
    staged.write_text(UNIT_MOVERS_MTS.read_text(encoding="utf-8"), encoding="utf-8")
    try:
        proc = subprocess.run(
            [npx, "--yes", "tsx", str(staged.name)],
            cwd=str(WEB),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    finally:
        staged.unlink(missing_ok=True)
    if proc.returncode != 0:
        pytest.fail(
            f"web_movers_route_unit.mts failed ({proc.returncode}):\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    assert "WEB_MOVERS_ROUTE_UNIT_OK" in proc.stdout


def test_symbols_list_query_validation_unit() -> None:
    """Runtime: session/CSRF/LIKE escape/info disclosure + clamp/whitelist."""
    assert UNIT_SYMBOLS_MTS.is_file(), f"missing {UNIT_SYMBOLS_MTS}"
    assert (WEB / "src" / "app" / "api" / "v1" / "symbols" / "route.ts").is_file()
    _require_web_node_modules()
    npx = _npx()
    staged = WEB / ".web_symbols_route_unit.mts"
    staged.write_text(UNIT_SYMBOLS_MTS.read_text(encoding="utf-8"), encoding="utf-8")
    try:
        proc = subprocess.run(
            [npx, "--yes", "tsx", str(staged.name)],
            cwd=str(WEB),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    finally:
        staged.unlink(missing_ok=True)
    if proc.returncode != 0:
        pytest.fail(
            f"web_symbols_route_unit.mts failed ({proc.returncode}):\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    assert "WEB_SYMBOLS_ROUTE_UNIT_OK" in proc.stdout


def test_market_page_and_nav_browse_link() -> None:
    """P1-D: /market page exists; nav exposes Browse; empty watchlist points at it."""
    market = WEB / "src" / "app" / "market" / "page.tsx"
    nav = WEB / "src" / "components" / "app-nav.tsx"
    watchlist = WEB / "src" / "app" / "watchlist" / "page.tsx"
    assert market.is_file()
    market_src = market.read_text(encoding="utf-8")
    assert "/api/v1/symbols" in market_src
    assert "/api/v1/market/movers" in market_src
    assert "/api/v1/sectors" in market_src
    assert "direction=up" in market_src
    assert "direction=down" in market_src
    assert "Top movers" in market_src
    assert "NfaInline" in market_src
    assert "requirePageSession" in market_src
    assert "normalizeMarketQuery" in market_src
    assert 'role="search"' in market_src
    assert "maxLength={MAX_MARKET_Q_LENGTH}" in market_src
    assert "dangerouslySetInnerHTML" not in market_src
    assert 'aria-label="Market symbols"' in market_src
    assert "tradeSummary" not in market_src
    assert "tick --force" not in market_src
    nav_src = nav.read_text(encoding="utf-8")
    assert 'href: "/market", label: "Browse"' in nav_src
    assert "hidden={!open}" in nav_src
    assert "{open ? (" not in nav_src
    watch_src = watchlist.read_text(encoding="utf-8")
    assert 'href="/market"' in watch_src
    assert "Browse symbols" in watch_src


def test_market_page_fence_no_screener_or_quote_board() -> None:
    """Browse stays thin: no screener/OHLC/volume board tokens in the page source."""
    market_src = (WEB / "src" / "app" / "market" / "page.tsx").read_text(encoding="utf-8")
    forbidden = (
        "market_cap",
        "OHLC",
        "ohlc",
        "order book",
        "heatmap",
        "screener",
        "volume",
        "dangerouslySetInnerHTML",
    )
    hits: list[str] = []
    for tok in forbidden:
        for line in market_src.splitlines():
            if tok in line and not _is_comment_only_hit(line, tok):
                hits.append(tok)
                break
    assert hits == [], f"screener/quote-board fence tokens on /market: {hits}"
    assert 'sort: "change_pct"' in market_src or "sort=change_pct" in market_src
    assert "sort=symbol" not in market_src
    # Movers section is a thin gainers/losers peek — not a multi-filter board.
    assert "Top movers" in market_src
    assert "/api/v1/market/movers?direction=up&limit=5" in market_src
    assert "/api/v1/market/movers?direction=down&limit=5" in market_src
    # Wave6: optional sectors strip (Postgres /api/v1/sectors; thin browse only).
    assert "/api/v1/sectors" in market_src
    assert 'aria-labelledby="sectors-heading"' in market_src


def test_sectors_route_static() -> None:
    """Wave6: GET /api/v1/sectors reads Postgres sectors; session GET; no cse.lk."""
    route = WEB / "src" / "app" / "api" / "v1" / "sectors" / "route.ts"
    assert route.is_file()
    source = route.read_text(encoding="utf-8")
    assert "requireSession" in source
    assert "requireSessionAndCsrf" not in source
    assert "FROM sectors" in source
    assert "ORDER BY change_pct DESC NULLS LAST" in source
    assert "getPool" in source
    assert "jsonOk({ items })" in source or "jsonOk({ items" in source
    # Thin fence: not a heatmap / multi-filter board (comments may negate).
    for tok in ("heatmap", "cse.lk", "allSectors"):
        hits = [
            line.strip()
            for line in source.splitlines()
            if tok in line.lower() and not _is_comment_only_hit(line, tok)
        ]
        assert hits == [], f"sectors route must not use {tok}: {hits}"


def test_disclosures_route_joins_briefs_and_pdf_fields() -> None:
    """Wave2/3: disclosures API LEFT JOINs briefs; sanitizes pdf_url/brief egress."""
    route = WEB / "src" / "app" / "api" / "v1" / "symbols" / "[symbol]" / "disclosures" / "route.ts"
    assert route.is_file()
    source = route.read_text(encoding="utf-8")
    assert "requireSession" in source
    assert "requireSessionAndCsrf" not in source
    assert "LEFT JOIN disclosure_briefs" in source
    assert "d.pdf_url" in source
    assert "b.brief" in source
    assert "b.status AS brief_status" in source
    assert "safePdfUrl" in source
    assert "safeAnnouncementUrl" in source
    assert "sanitizeBriefText" in source
    assert "FROM disclosures d" in source
    assert "cse.lk" not in source.lower() or all(
        _is_comment_only_hit(line, "cse.lk")
        for line in source.splitlines()
        if "cse.lk" in line.lower()
    )


def test_symbol_page_prefers_pdf_and_shows_ready_brief() -> None:
    """Wave2/3: symbol page uses safeFilingHref; brief only via sanitizeBriefText."""
    page = WEB / "src" / "app" / "symbols" / "[symbol]" / "page.tsx"
    assert page.is_file()
    source = page.read_text(encoding="utf-8")
    assert "safeFilingHref" in source
    assert "sanitizeBriefText" in source
    assert "safePdfUrl" in source
    assert "item.pdf_url?.trim() || item.url" not in source
    assert "dangerouslySetInnerHTML" not in source
    assert "NfaInline" in source
    assert "NfaFooter" in source
    assert "cse.lk" not in source.lower() or all(
        _is_comment_only_hit(line, "cse.lk")
        for line in source.splitlines()
        if "cse.lk" in line.lower()
    )


def test_disclosure_safe_helpers_fence() -> None:
    """Allowlist helpers must not embed contiguous cse.lk (fence) outside comments."""
    helper = WEB / "src" / "lib" / "api" / "disclosure-safe.ts"
    assert helper.is_file()
    source = helper.read_text(encoding="utf-8")
    assert "safePdfUrl" in source
    assert "safeAnnouncementUrl" in source
    assert "safeFilingHref" in source
    assert "sanitizeBriefText" in source
    assert 'briefStatus !== "ready"' in source or 'briefStatus !== "ready"' in source
    assert "cse.lk" not in source.lower() or all(
        _is_comment_only_hit(line, "cse.lk")
        for line in source.splitlines()
        if "cse.lk" in line.lower()
    )


def test_disclosures_route_brief_pdf_unit() -> None:
    """Runtime: LEFT JOIN mapping + XSS egress nulling; SQL never mentions cse.lk."""
    assert UNIT_DISCLOSURES_MTS.is_file(), f"missing {UNIT_DISCLOSURES_MTS}"
    route = WEB / "src" / "app" / "api" / "v1" / "symbols" / "[symbol]" / "disclosures" / "route.ts"
    assert route.is_file()
    _require_web_node_modules()
    npx = _npx()
    # Dot-prefix so concurrent fence greps skip staged harnesses.
    staged = WEB / ".web_disclosures_route_unit.mts"
    staged.write_text(UNIT_DISCLOSURES_MTS.read_text(encoding="utf-8"), encoding="utf-8")
    try:
        proc = subprocess.run(
            [npx, "--yes", "tsx", str(staged.name)],
            cwd=str(WEB),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    finally:
        staged.unlink(missing_ok=True)
    if proc.returncode != 0:
        pytest.fail(
            f".web_disclosures_route_unit.mts failed ({proc.returncode}):\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    assert "WEB_DISCLOSURES_ROUTE_UNIT_OK" in proc.stdout
