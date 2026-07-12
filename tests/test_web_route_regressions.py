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
    assert route.is_file()
    source = route.read_text(encoding="utf-8")
    assert "requireSession" in source
    # Safe GET: session only — must not demand CSRF.
    assert "requireSessionAndCsrf" not in source
    assert "INNER JOIN LATERAL" in source
    assert "LEFT JOIN LATERAL" not in source
    assert "price_snapshots" in source
    assert "escapeLikePattern" in source
    assert "ESCAPE" in source
    assert "normalizeMarketQuery" in source
    assert "MAX_SYMBOLS_OFFSET" in source
    assert "cse.lk" not in source.lower() or all(
        _is_comment_only_hit(line, "cse.lk")
        for line in source.splitlines()
        if "cse.lk" in line.lower()
    )


def test_symbols_list_query_validation_static() -> None:
    """P1-C: limit clamp (default 50, max 200) + sort whitelist in route source."""
    route = WEB / "src" / "app" / "api" / "v1" / "symbols" / "route.ts"
    source = route.read_text(encoding="utf-8")
    assert "const DEFAULT_LIMIT = 50;" in source
    assert "const MAX_LIMIT = 200;" in source
    assert "Math.min(limit, MAX_LIMIT)" in source
    assert 'limit < 1) limit = DEFAULT_LIMIT' in source or (
        "limit < 1" in source and "DEFAULT_LIMIT" in source
    )
    # Sort whitelist: only symbol|change_pct; anything else → change_pct.
    assert 'sortRaw === "symbol" ? "symbol" : "change_pct"' in source
    assert 'sort === "symbol"' in source
    assert "ps.change_pct DESC NULLS LAST" in source
    assert "s.symbol ASC" in source
    assert "INNER JOIN LATERAL" in source
    assert "LEFT JOIN LATERAL" not in source
    mq = WEB / "src" / "lib" / "api" / "market-query.ts"
    assert mq.is_file()
    mq_src = mq.read_text(encoding="utf-8")
    assert "MAX_MARKET_Q_LENGTH = 64" in mq_src
    assert "escapeLikePattern" in mq_src
    assert "normalizeMarketQuery" in mq_src


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
    hits = [tok for tok in forbidden if tok in market_src]
    assert hits == [], f"screener/quote-board fence tokens on /market: {hits}"
    assert 'sort: "change_pct"' in market_src or "sort=change_pct" in market_src
    assert "sort=symbol" not in market_src
