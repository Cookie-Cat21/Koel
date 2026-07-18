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
UNIT_SPARKLINE_MTS = Path(__file__).resolve().parent / "web_sparkline_finite_unit.mts"

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
    """Every dash page keeps sitewide NFA footer chrome (WS-028).

    Marketing landing uses KoelFooter (embeds NFA_FOOTER) instead of NfaFooter.
    """
    landing = WEB / "src" / "app" / "page.tsx"
    landing_src = landing.read_text(encoding="utf-8")
    assert 'import { KoelFooter } from "@/components/marketing/koel-footer";' in landing_src
    assert "<KoelFooter" in landing_src
    assert "NFA_FOOTER" in (
        WEB / "src" / "components" / "marketing" / "koel-footer.tsx"
    ).read_text(encoding="utf-8")

    page_paths = [
        WEB / "src" / "app" / "login" / "page.tsx",
        WEB / "src" / "app" / "overview" / "page.tsx",
        WEB / "src" / "app" / "watchlist" / "page.tsx",
        WEB / "src" / "app" / "market" / "page.tsx",
        WEB / "src" / "app" / "alerts" / "page.tsx",
        WEB / "src" / "app" / "alerts" / "history" / "page.tsx",
        WEB / "src" / "app" / "symbols" / "[symbol]" / "page.tsx",
        WEB / "src" / "app" / "symbols" / "[symbol]" / "not-found.tsx",
        WEB / "src" / "app" / "health" / "page.tsx",
        WEB / "src" / "app" / "scenarios" / "page.tsx",
    ]

    missing: list[str] = []
    for path in page_paths:
        assert path.is_file(), f"missing dash page {path.relative_to(ROOT)}"
        source = path.read_text(encoding="utf-8")
        if 'import { NfaFooter } from "@/components/nfa-footer";' not in source:
            missing.append(f"{path.relative_to(ROOT)} missing import")
        if "<NfaFooter />" not in source:
            missing.append(f"{path.relative_to(ROOT)} missing render")

    assert missing == []


def test_dashboard_price_surfaces_render_nfa_inline() -> None:
    """Price-adjacent / explainer surfaces keep NfaInline near copy (WS-028)."""
    page_paths = [
        WEB / "src" / "app" / "page.tsx",
        WEB / "src" / "app" / "login" / "page.tsx",
        WEB / "src" / "app" / "overview" / "page.tsx",
        WEB / "src" / "app" / "watchlist" / "page.tsx",
        WEB / "src" / "app" / "market" / "page.tsx",
        WEB / "src" / "app" / "alerts" / "page.tsx",
        WEB / "src" / "app" / "alerts" / "history" / "page.tsx",
        WEB / "src" / "app" / "symbols" / "[symbol]" / "page.tsx",
        WEB / "src" / "app" / "scenarios" / "page.tsx",
    ]

    missing: list[str] = []
    for path in page_paths:
        assert path.is_file(), f"missing dash page {path.relative_to(ROOT)}"
        source = path.read_text(encoding="utf-8")
        if 'import { NfaInline } from "@/components/nfa-inline";' not in source:
            missing.append(f"{path.relative_to(ROOT)} missing import")
        if "<NfaInline" not in source:
            missing.append(f"{path.relative_to(ROOT)} missing render")

    assert missing == []


def test_login_page_a11y_contract() -> None:
    """W17 a11y: labelled explainer list, form associations, busy submit."""
    page = WEB / "src" / "app" / "login" / "page.tsx"
    form = WEB / "src" / "components" / "login-form.tsx"
    assert page.is_file()
    assert form.is_file()
    page_src = page.read_text(encoding="utf-8")
    form_src = form.read_text(encoding="utf-8")

    assert 'id="main-content"' in page_src
    assert 'aria-label="koel home"' in page_src
    assert 'id="login-explainer"' in page_src
    assert 'aria-labelledby="login-explainer"' in page_src
    assert 'rounded-full bg-foreground/55' in page_src
    assert "<li>- " not in page_src

    assert 'aria-labelledby="login-sign-in-heading"' in form_src
    assert 'id="login-sign-in-heading"' in form_src
    assert "aria-describedby={describedBy}" in form_src
    assert "aria-invalid={error ? true : undefined}" in form_src
    assert "aria-busy={pending || undefined}" in form_src
    assert "InlineError" in form_src
    assert 'role="status"' in form_src
    assert 'autoComplete="username"' in form_src


def test_alert_create_category_a11y_contract() -> None:
    """W30 a11y: disclosure category keeps hint + error via aria-describedby."""
    form = WEB / "src" / "components" / "alert-controls.tsx"
    assert form.is_file()
    src = form.read_text(encoding="utf-8")

    assert 'id="alert_category"' in src
    assert 'htmlFor="alert_category"' in src
    assert 'id="alert_category_hint"' in src
    assert 'aria-invalid={errors.category ? true : undefined}' in src
    assert '"alert_category_hint alert_form_error"' in src
    assert ': "alert_category_hint"' in src
    assert "maxLength={DISCLOSURE_CATEGORY_MAX}" in src
    assert "aria-busy={pending || undefined}" in src
    assert 'id="alert_form_error"' in src


def test_list_loading_skeleton_keeps_nfa_footer() -> None:
    """Every route loading.tsx keeps NFA footer while content pulses."""
    skeleton = WEB / "src" / "components" / "skeleton.tsx"
    source = skeleton.read_text(encoding="utf-8")
    assert 'import { NfaFooter } from "@/components/nfa-footer";' in source
    assert "<NfaFooter />" in source
    assert "ListPageSkeleton" in source

    loading_files = sorted((WEB / "src" / "app").rglob("loading.tsx"))
    assert loading_files, "expected at least one route loading.tsx"
    missing: list[str] = []
    for path in loading_files:
        text = path.read_text(encoding="utf-8")
        uses_shared = "ListPageSkeleton" in text
        has_footer = (
            'import { NfaFooter } from "@/components/nfa-footer";' in text
            and "<NfaFooter />" in text
        )
        if not (uses_shared or has_footer):
            missing.append(str(path.relative_to(ROOT)))
    assert missing == [], "loading.tsx missing NFA footer chrome:\n" + "\n".join(
        missing
    )


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
    # Digits-only SafeInteger — invalid / missing limit → DEFAULT_LIMIT.
    assert "toSafePositiveInt" in source
    assert "limitParsed == null ? DEFAULT_LIMIT" in source
    assert "Number.parseInt" not in source
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


def test_alerts_post_rejects_non_positive_threshold() -> None:
    """Wave15: POST /alerts mirrors bot/UI — threshold must be > 0."""
    route = WEB / "src" / "app" / "api" / "v1" / "alerts" / "route.ts"
    assert route.is_file()
    source = route.read_text(encoding="utf-8")
    assert "obj.threshold <= 0" in source
    assert "threshold must be a positive number." in source
    assert "Number.isFinite(obj.threshold)" in source


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
    assert "browsed.filter" in source
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
    assert "toFiniteNumber" in market_src
    assert "finiteOrNull" not in market_src
    # Both movers sides must succeed — do not paint API failure as empty gainers.
    assert "gainerItems !== null && loserItems !== null" in market_src
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
    """P1-D: /market page exists; nav exposes Browse; empty watchlist/alerts point at it."""
    market = WEB / "src" / "app" / "market" / "page.tsx"
    nav = WEB / "src" / "components" / "app-nav.tsx"
    watchlist = WEB / "src" / "app" / "watchlist" / "page.tsx"
    alerts = WEB / "src" / "app" / "alerts" / "page.tsx"
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
    assert "BrowseTable" in market_src
    assert "BROWSE_PAGE_SIZE" in market_src
    assert "All symbols" in market_src
    browse_table = (
        WEB / "src" / "components" / "market" / "browse-table.tsx"
    ).read_text(encoding="utf-8")
    assert 'aria-label="Market symbols"' in browse_table
    assert "tradeSummary" not in market_src
    assert "make tick" in market_src
    assert "tick --force" not in market_src
    assert "No snapshot data yet" in market_src
    nav_src = nav.read_text(encoding="utf-8")
    assert 'href: "/market", label: "Browse"' in nav_src
    assert "hidden={!open}" in nav_src
    assert "{open ? (" not in nav_src
    watch_src = watchlist.read_text(encoding="utf-8")
    assert 'href="/market"' in watch_src
    assert '<Link href="/market">Browse</Link>' in watch_src
    assert "Browse symbols" not in watch_src
    alerts_src = alerts.read_text(encoding="utf-8")
    assert 'href="/market"' in alerts_src
    assert '<Link href="/market">Browse</Link>' in alerts_src
    assert 'href="#alert_symbol">Create an alert</a>' in alerts_src


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
    assert 'aria-label="Sectors"' not in market_src
    # Wave9 a11y: movers Watch is one labelled link; sectors list labelled by heading.
    # Bars live in kit/movers-bar-list (extracted from page); keep page heading ids.
    movers_kit = (
        WEB / "src" / "components" / "kit" / "movers-bar-list.tsx"
    ).read_text(encoding="utf-8")
    assert "Open ${item.symbol} detail to watch" in movers_kit
    assert "movers-gainers-heading" in market_src
    assert "movers-losers-heading" in market_src
    assert "Watch" in movers_kit and "</span>" in movers_kit
    assert "title={item.name}" in market_src
    assert 'role="status"' in market_src
    assert "changeDirectionSr" in market_src or "changeDirectionSr" in movers_kit
    assert "MoversBarList" in market_src
    assert "ChangeBadge" in market_src


def test_scenarios_dash_stub_page() -> None:
    """Wave11/w14: /scenarios is a thin NFA stub; disabled unless AI_SCENARIOS_ENABLED=1."""
    page = WEB / "src" / "app" / "scenarios" / "page.tsx"
    helper = WEB / "src" / "lib" / "scenarios.ts"
    nav = WEB / "src" / "components" / "app-nav.tsx"
    assert page.is_file()
    assert helper.is_file()
    page_src = page.read_text(encoding="utf-8")
    helper_src = helper.read_text(encoding="utf-8")
    nav_src = nav.read_text(encoding="utf-8")

    assert "requirePageSession" in page_src
    assert "scenariosEnabled" in page_src
    assert 'export const dynamic = "force-dynamic"' in page_src
    assert 'title: "Scenarios · koel"' in page_src
    assert "stub only" in page_src
    assert 'id="main-content"' in page_src
    assert 'active="/scenarios"' in page_src
    assert "Coming soon" in page_src
    assert "Scenarios opted in — runs not wired" in page_src
    assert "AI_SCENARIOS_ENABLED=1" in page_src
    assert "no LLM scenario runner" in page_src
    assert "no LLM calls" in page_src
    assert "Not a\n          trading terminal" in page_src or (
        "Not a" in page_src and "trading terminal" in page_src
    )
    assert "no personas" in page_src
    assert "no queued runs" in page_src
    assert "Phase 3 stub" in page_src
    assert "NfaInline" in page_src
    assert "NfaFooter" in page_src
    assert "EmptyState" in page_src
    assert "AlertTitle" in page_src
    # No LLM / provider / DB wiring on the dash stub.
    assert "fetch(" not in page_src
    assert "getPool" not in page_src
    assert "useEffect" not in page_src
    for tok in ("openai", "gemini", "groq", "openrouter", "generatecontent", "anthropic"):
        assert tok not in page_src.lower()
        assert tok not in helper_src.lower()

    assert "AI_SCENARIOS_ENABLED" in helper_src
    assert '.trim() === "1"' in helper_src
    # Loose truthy env values must not opt in (only exact "1" after trim).
    assert "`true` / `yes` / `on`" in helper_src
    # Scenarios stays off primary nav until Phase 3 runs exist (deep-link OK).
    assert 'href: "/scenarios", label: "Scenarios"' not in nav_src

    # No scenarios API surface — page is chrome-only.
    assert not (WEB / "src" / "app" / "api" / "v1" / "scenarios").exists()

    # Fence: not a portfolio / advice surface.
    forbidden = ("portfolio", "P&L", "buy now", "sell now", "price target")
    hits = [
        tok
        for tok in forbidden
        for line in page_src.splitlines()
        if tok.lower() in line.lower() and not _is_comment_only_hit(line, tok)
    ]
    assert hits == [], f"scenarios stub fence tokens: {hits}"


def test_next_config_security_headers() -> None:
    """w14: next.config.ts pins baseline dash security headers on all routes."""
    config = WEB / "next.config.ts"
    assert config.is_file()
    source = config.read_text(encoding="utf-8")

    assert "securityHeaders" in source
    assert 'key: "X-Frame-Options", value: "DENY"' in source
    assert 'key: "X-Content-Type-Options", value: "nosniff"' in source
    assert 'key: "Referrer-Policy", value: "strict-origin-when-cross-origin"' in source
    assert 'key: "Permissions-Policy"' in source
    assert "camera=(), microphone=(), geolocation=()" in source
    # Legacy XSS auditors opted out (modern browsers ignore / mishandle them).
    assert 'key: "X-XSS-Protection", value: "0"' in source
    assert "poweredByHeader: false" in source
    assert 'source: "/:path*"' in source
    assert "async headers()" in source
    # Cloud Agent previews need non-localhost Hosts allowlisted in next dev,
    # otherwise /_next/* is blocked → login never hydrates.
    assert "allowedDevOrigins" in source
    assert '"*.agent.cvm.dev"' in source or "'*.agent.cvm.dev'" in source
    # Strict CSP stays deferred — do not claim a full CSP ship.
    csp_lines = [
        line
        for line in source.splitlines()
        if "Content-Security-Policy" in line
        and not _is_comment_only_hit(line, "Content-Security-Policy")
    ]
    assert csp_lines == [], f"unexpected CSP header ship: {csp_lines}"
    assert "deferred" in source.lower()  # comment documents CSP deferral


def test_login_form_posts_demo_auth() -> None:
    """Demo form: JS fetch preferred; native POST + relative redirect as fallback."""
    form = WEB / "src" / "components" / "login-form.tsx"
    route = WEB / "src" / "app" / "api" / "v1" / "auth" / "demo" / "route.ts"
    assert form.is_file()
    assert route.is_file()
    form_src = form.read_text(encoding="utf-8")
    route_src = route.read_text(encoding="utf-8")

    assert 'fetch("/api/v1/auth/demo"' in form_src
    assert "e.preventDefault()" in form_src
    assert 'method="post"' in form_src
    assert 'action="/api/v1/auth/demo"' in form_src
    assert "application/x-www-form-urlencoded" in route_src
    assert "overviewRedirect" in route_src
    # Relative Location — absolute http://0.0.0.0 breaks Cloud Agent routing.
    assert 'Location: "/overview"' in route_src
    assert "toSafePositiveInt" in route_src
    assert "allowlist.has(telegramId)" in route_src


def test_overview_page_is_signed_in_home() -> None:
    """Cake layer: signed-in home is /overview with movers + watch + alerts."""
    page = WEB / "src" / "app" / "overview" / "page.tsx"
    landing = WEB / "src" / "app" / "page.tsx"
    nav = WEB / "src" / "components" / "app-nav.tsx"
    login = WEB / "src" / "components" / "login-form.tsx"
    assert page.is_file()
    page_src = page.read_text(encoding="utf-8")
    landing_src = landing.read_text(encoding="utf-8")
    nav_src = nav.read_text(encoding="utf-8")
    login_src = login.read_text(encoding="utf-8")

    assert "requirePageSession" in page_src
    assert "PageHeader" in page_src
    assert 'eyebrow="Home"' in page_src
    assert "/api/v1/watchlist" in page_src
    assert "/api/v1/market/movers" in page_src
    assert "/api/v1/alerts" in page_src
    assert "ArmedBadge" in page_src
    assert "StatCard" in page_src
    assert "Telegram" in page_src
    assert 'href: "/overview", label: "Overview"' in nav_src
    assert 'redirect("/overview")' in landing_src
    assert 'router.push("/overview")' in login_src
    assert "max-w-6xl" in page_src


def test_price_refresh_soft_reloads_from_postgres() -> None:
    """Near-realtime: client refresh from Postgres — never cse.lk from web/."""
    comp = WEB / "src" / "components" / "price-refresh.tsx"
    assert comp.is_file()
    src = comp.read_text(encoding="utf-8")
    assert "router.refresh()" in src
    assert "DEFAULT_PRICE_REFRESH_MS" in src
    assert "MIN_PRICE_REFRESH_MS" in src
    assert "cse.lk" not in src.lower()
    for page in (
        WEB / "src" / "app" / "overview" / "page.tsx",
        WEB / "src" / "app" / "market" / "page.tsx",
        WEB / "src" / "app" / "watchlist" / "page.tsx",
        WEB / "src" / "app" / "symbols" / "[symbol]" / "page.tsx",
    ):
        page_src = page.read_text(encoding="utf-8")
        assert "PriceRefresh" in page_src, f"{page} missing PriceRefresh"
        assert "cse.lk" not in page_src.lower() or all(
            line.strip().startswith("//") or "cse.lk" not in line.lower()
            for line in page_src.splitlines()
            if "cse.lk" in line.lower()
        )


def test_sectors_route_static() -> None:
    """Wave6: GET /api/v1/sectors reads Postgres sectors; session GET; no cse.lk."""
    route = WEB / "src" / "app" / "api" / "v1" / "sectors" / "route.ts"
    assert route.is_file()
    source = route.read_text(encoding="utf-8")
    assert "requireSession" in source
    assert "requireSessionAndCsrf" not in source
    assert "FROM sectors" in source
    assert "ORDER BY change_pct DESC NULLS LAST" in source
    assert "LIMIT $1" in source
    assert "MAX_SECTORS" in source
    assert "getPool" in source
    assert "jsonOk({ items })" in source or "jsonOk({ items" in source
    assert "toSafeSectorId" in source or "Number.isSafeInteger" in source
    assert "sanitizeDisclosureText" in source
    assert "MAX_SECTOR_NAME_LENGTH" in source
    # Ban raw trim-only name/symbol egress (controls + length must be stripped).
    assert "row.name.trim()" not in source
    assert "row.symbol.trim()" not in source
    assert "index_code: row.index_code" not in source
    assert "index_name: row.index_name" not in source
    # Shared finite helper — do not reintroduce a local NaN-leaky copy.
    assert 'from "@/lib/api/market-browse"' in source
    assert "function toFiniteNumber" not in source


def test_price_egress_routes_use_to_finite_number() -> None:
    """w17: symbol detail / snapshots / watchlist / alerts GET finite-only prices."""
    paths = [
        WEB / "src" / "app" / "api" / "v1" / "symbols" / "[symbol]" / "route.ts",
        WEB / "src" / "app" / "api" / "v1" / "symbols" / "[symbol]" / "snapshots" / "route.ts",
        WEB / "src" / "app" / "api" / "v1" / "watchlist" / "route.ts",
        WEB / "src" / "app" / "api" / "v1" / "alerts" / "route.ts",
    ]
    for path in paths:
        assert path.is_file(), path
        source = path.read_text(encoding="utf-8")
        assert 'from "@/lib/api/market-browse"' in source, path.name
        assert "toFiniteNumber" in source, path.name
        # Ban raw Number(...) on price-like fields (not substrings of toFiniteNumber).
        for line in source.splitlines():
            stripped = line.strip()
            if "Number(" not in stripped or "toFiniteNumber(" in stripped:
                continue
            if "Number.is" in stripped or "Number.isFinite" in stripped:
                continue
            # Allow id / limit / offset ints — not quote/threshold egress.
            if any(
                tok in stripped
                for tok in (
                    "Number(row.id)",
                    "Number(rawId)",
                    "Number(limitRaw)",
                    "Number(offsetRaw)",
                    "Number(n)",
                    "Number(limit)",
                )
            ):
                continue
            if any(
                tok in stripped
                for tok in (".price)", ".change)", ".change_pct)", ".threshold)", ".volume)")
            ):
                raise AssertionError(f"{path}: raw Number on price-like field: {stripped}")
    # Thin fence: not a heatmap / multi-filter board (comments may negate).
    for tok in ("heatmap", "cse.lk", "allSectors"):
        hits = [
            line.strip()
            for line in source.splitlines()
            if tok in line.lower() and not _is_comment_only_hit(line, tok)
        ]
        assert hits == [], f"sectors route must not use {tok}: {hits}"


def test_sparkline_hardens_empty_nan_points() -> None:
    """w18: sparkline + snapshots drop non-finite prices; empty when <2 ticks."""
    spark_lib = WEB / "src" / "lib" / "sparkline.ts"
    spark_ui = WEB / "src" / "components" / "sparkline.tsx"
    snaps = WEB / "src" / "app" / "api" / "v1" / "symbols" / "[symbol]" / "snapshots" / "route.ts"
    page = WEB / "src" / "app" / "symbols" / "[symbol]" / "page.tsx"
    for path in (spark_lib, spark_ui, snaps, page):
        assert path.is_file(), path

    lib_src = spark_lib.read_text(encoding="utf-8")
    assert "Number.isFinite" in lib_src
    assert "finiteSparklinePoints" in lib_src

    ui_src = spark_ui.read_text(encoding="utf-8")
    assert "finiteSparklinePoints" in ui_src
    assert 'c.includes("NaN")' in ui_src or "NaN" in ui_src
    assert "series.length < 2" in ui_src

    snaps_src = snaps.read_text(encoding="utf-8")
    assert "toFiniteNumber" in snaps_src
    assert "price == null" in snaps_src
    assert "flatMap" in snaps_src

    page_src = page.read_text(encoding="utf-8")
    assert "finiteSparklinePoints" in page_src
    assert 'from "@/lib/sparkline"' in page_src


def test_sparkline_finite_points_unit() -> None:
    """w18: unit harness for finiteSparklinePoints empty/NaN filter."""
    assert UNIT_SPARKLINE_MTS.is_file(), f"missing {UNIT_SPARKLINE_MTS}"
    assert (WEB / "src" / "lib" / "sparkline.ts").is_file()
    _require_web_node_modules()
    npx = _npx()
    staged = WEB / ".web_sparkline_finite_unit.mts"
    staged.write_text(UNIT_SPARKLINE_MTS.read_text(encoding="utf-8"), encoding="utf-8")
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
            f".web_sparkline_finite_unit.mts failed ({proc.returncode}):\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    assert "WEB_SPARKLINE_FINITE_UNIT_OK" in proc.stdout


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
    assert (
        "Number.isSafeInteger(id)" in source or "toSafePositiveInt" in source
    )
    assert "Number.isFinite(id)" not in source
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
    data = (WEB / "src" / "lib" / "db" / "symbol-page-data.ts").read_text(
        encoding="utf-8"
    )
    assert "safeFilingHref" in source
    assert "sanitizeBriefText" in data
    assert "safePdfUrl" in data
    assert "item.pdf_url?.trim() || item.url" not in source
    assert "dangerouslySetInnerHTML" not in source
    assert "NfaInline" in source
    assert "NfaFooter" in source
    assert '"processing"' in source
    # W16 a11y: disclosures list labelled by heading; ready brief is a named group.
    # Timeline kit owns brief group markup (Wave D6).
    timeline = (
        WEB / "src" / "components" / "kit" / "disclosure-timeline.tsx"
    ).read_text(encoding="utf-8")
    assert 'id="disclosures-heading"' in source
    assert 'aria-labelledby="disclosures-heading"' in source
    assert 'role="group"' in timeline
    assert "Filing brief" in timeline
    assert "disclosure-brief-" in timeline
    assert "(opens in new tab)" in timeline
    assert "DisclosureTimeline" in source
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


def test_post_watchlist_duplicate_soft_messaging() -> None:
    """w18: POST /watchlist exposes created; UI distinguishes already-watching toast."""
    route = WEB / "src" / "app" / "api" / "v1" / "watchlist" / "route.ts"
    controls = WEB / "src" / "components" / "watchlist-controls.tsx"
    assert route.is_file()
    assert controls.is_file()
    route_src = route.read_text(encoding="utf-8")
    controls_src = controls.read_text(encoding="utf-8")
    # API: body includes created; 201 only when newly inserted.
    assert "created" in route_src
    assert "created ? 201 : 200" in route_src
    assert "Soft messaging" in route_src
    # UI: distinct toast for duplicate vs new watch.
    assert "Already watching" in controls_src
    assert "Pushes still go to Telegram" in controls_src
    assert '"created"' in controls_src or "created" in controls_src


def test_ardeno_kit_components_exist_and_are_wired() -> None:
    """Brand kit ports stay MIT/pattern-only and land on landing + health."""
    kit = WEB / "src" / "components" / "kit"
    required = (
        "chat-bubble.tsx",
        "steps.tsx",
        "faq-section.tsx",
        "stat-card.tsx",
        "alert-banner.tsx",
        "status-badge.tsx",
    )
    for name in required:
        path = kit / name
        assert path.is_file(), f"missing kit component {name}"
        src = path.read_text(encoding="utf-8")
        # Fence: no marketplace dumps / second design systems.
        for tok in ("daisyui", "tremor", "aceternity", "reactbits", "shadcnblocks"):
            assert tok not in src.lower() or all(
                _is_comment_only_hit(line, tok)
                for line in src.splitlines()
                if tok in line.lower()
            ), f"{name} must not vendor {tok}"

    landing = (WEB / "src" / "app" / "page.tsx").read_text(encoding="utf-8")
    # Option A landing: Telegram proof + HowItWorks + Watermelon faq-6 split.
    assert "TelegramProof" in landing
    assert "HowItWorks" in landing
    assert "FaqSplit" in landing or "FaqSection" in landing
    assert "AnnouncementBar" in landing
    assert "KoelWordmark" in landing
    assert "KoelFooter" in landing
    assert (WEB / "src" / "components" / "kit" / "chat-bubble.tsx").is_file()
    assert (WEB / "src" / "components" / "kit" / "steps.tsx").is_file()
    assert (WEB / "src" / "components" / "kit" / "faq-section.tsx").is_file()
    assert (WEB / "src" / "components" / "marketing" / "faq-split.tsx").is_file()
    assert (WEB / "src" / "components" / "marketing" / "how-it-works.tsx").is_file()
    assert (WEB / "src" / "components" / "marketing" / "telegram-proof.tsx").is_file()

    health = (WEB / "src" / "app" / "health" / "page.tsx").read_text(encoding="utf-8")
    assert "StatCard" in health
    assert "AlertBanner" in health
    assert "LiveIndicator" in health
    assert "PageHeader" in health


def test_dash_status_badges_and_page_headers() -> None:
    """P0 Badge wiring: armed on alerts, delivery on history, PageHeader chrome."""
    badge = WEB / "src" / "components" / "ui" / "badge.tsx"
    status = WEB / "src" / "components" / "kit" / "status-badge.tsx"
    alerts = WEB / "src" / "app" / "alerts" / "page.tsx"
    history = WEB / "src" / "app" / "alerts" / "history" / "page.tsx"
    assert badge.is_file()
    assert status.is_file()

    status_src = status.read_text(encoding="utf-8")
    assert "export function ArmedBadge" in status_src
    assert "export function DeliveryBadge" in status_src
    for key in ("sent", "delivered_unmarked", "retrying", "dead_lettered"):
        assert key in status_src
    # Soft-fill chips — not solid KPI walls.
    assert "bg-primary/10" in status_src
    assert "border-emerald-500/30" in status_src

    alerts_src = alerts.read_text(encoding="utf-8")
    assert "ArmedBadge" in alerts_src
    assert "PageHeader" in alerts_src
    assert 'eyebrow="Rules"' in alerts_src
    assert "rule.armed ? \"Armed\"" not in alerts_src  # chip, not plain text pair

    history_src = history.read_text(encoding="utf-8")
    assert "DeliveryBadge" in history_src
    assert "PageHeader" in history_src
    assert 'eyebrow="Audit"' in history_src
    assert "deliveryBadgeClassName" not in history_src


def test_alert_create_uses_radix_select_fail_closed() -> None:
    """Alert type control is shadcn Select; values still gate via isAlertType."""
    form = WEB / "src" / "components" / "alert-controls.tsx"
    select = WEB / "src" / "components" / "ui" / "select.tsx"
    assert form.is_file()
    assert select.is_file()
    src = form.read_text(encoding="utf-8")
    assert 'from "@/components/ui/select"' in src
    assert "SelectTrigger" in src
    assert "SelectItem" in src
    assert "onValueChange" in src
    assert "isAlertType(value)" in src
    assert "as AlertType" not in src
    assert 'id="alert_type"' in src
    # Native <select> must not return for alert type (Radix owns this control).
    assert "<select" not in src


def test_history_limit_control_native_get_form() -> None:
    """History limit stays a native GET select (works without client JS)."""
    page = WEB / "src" / "app" / "alerts" / "history" / "page.tsx"
    src = page.read_text(encoding="utf-8")
    assert 'method="get"' in src
    assert 'id="history_limit"' in src
    assert 'name="limit"' in src
    for value in ("25", "50", "100", "200"):
        assert f'value="{value}"' in src
    # Radix Select must not replace GET form controls (no name= submit).
    assert "SelectTrigger" not in src
    assert 'id="history_symbol_filter"' in src


def test_symbol_page_watch_and_new_alert_shortcuts() -> None:
    """DASH_IA: symbol detail exposes Watch + New alert without leaving the page."""
    page = WEB / "src" / "app" / "symbols" / "[symbol]" / "page.tsx"
    controls = WEB / "src" / "components" / "watchlist-controls.tsx"
    page_src = page.read_text(encoding="utf-8")
    controls_src = controls.read_text(encoding="utf-8")

    assert "WatchButton" in page_src
    assert "export function WatchButton" in controls_src
    assert 'method: "POST"' in controls_src
    assert "/api/v1/watchlist" in controls_src
    assert "normalizeSymbol(symbol)" in controls_src
    assert "New alert" in page_src
    assert "/alerts?symbol=${encoded}" in page_src or (
        "href={`/alerts?symbol=${encoded}`}" in page_src
    )
    assert "PageHeader" in page_src
    assert 'eyebrow="Symbol"' in page_src
    # Still no direct CSE scrape from the symbol page.
    assert "cse.lk" not in page_src.lower() or all(
        _is_comment_only_hit(line, "cse.lk")
        for line in page_src.splitlines()
        if "cse.lk" in line.lower()
    )


def test_wave_master_plan_kit_wiring() -> None:
    """Waves 1–5: kit + API surfaces stay wired (cake/cherry fence)."""
    overview = (WEB / "src" / "app" / "overview" / "page.tsx").read_text(encoding="utf-8")
    market = (WEB / "src" / "app" / "market" / "page.tsx").read_text(encoding="utf-8")
    health = (WEB / "src" / "app" / "health" / "page.tsx").read_text(encoding="utf-8")
    alerts = (WEB / "src" / "app" / "alerts" / "page.tsx").read_text(encoding="utf-8")
    nav = (WEB / "src" / "components" / "app-nav.tsx").read_text(encoding="utf-8")
    assert "CakeCherryBanner" in overview
    assert "ChangeBadge" in overview
    assert "MoversBarList" in overview
    assert "IndexStrip" in overview
    assert "SectorHeatStrip" in overview
    assert "/api/v1/indexes" in overview
    assert "MoversBarList" in market
    assert "ChangeBadge" in market
    assert "delivery-heading" in health
    assert "retention-heading" in health
    assert "TestFireButton" in alerts
    assert "CommandPalette" in nav or "command-palette" in nav
    assert (WEB / "src" / "app" / "api" / "v1" / "indexes" / "route.ts").is_file()
    assert (WEB / "src" / "app" / "api" / "v1" / "stream" / "snapshots" / "route.ts").is_file()
    assert (WEB / "src" / "app" / "api" / "v1" / "auth" / "telegram" / "route.ts").is_file()
    assert (WEB / "src" / "app" / "api" / "v1" / "auth" / "logout-all" / "route.ts").is_file()
    assert (WEB / "src" / "components" / "command-palette.tsx").is_file()
    parity = Path("docs/factory/BOT_DASH_PARITY.md")
    assert parity.is_file()
    assert "price_above" in parity.read_text(encoding="utf-8")


def test_bot_dash_parity_filing_metrics_and_settings() -> None:
    """P0–P3: full alert types, metrics API, mute, settings on dash."""
    symbol_ts = (WEB / "src" / "lib" / "api" / "symbol.ts").read_text(encoding="utf-8")
    fmt = (WEB / "src" / "lib" / "format.ts").read_text(encoding="utf-8")
    alerts_ctrl = (WEB / "src" / "components" / "alert-controls.tsx").read_text(
        encoding="utf-8"
    )
    nav = (WEB / "src" / "components" / "app-nav.tsx").read_text(encoding="utf-8")
    assert '"eps_yoy_above"' in symbol_ts
    assert '"profit_yoy_below"' in symbol_ts
    assert "bid_heavy" not in symbol_ts.split("NOTICE_ALERT_TYPES")[1].split("]")[0]
    assert "isThresholdAlertType" in alerts_ctrl
    assert "eps_yoy_above" in alerts_ctrl
    assert "MuteAlertButton" in alerts_ctrl
    assert "EPS YoY above" in fmt
    metrics_route = (
        WEB
        / "src"
        / "app"
        / "api"
        / "v1"
        / "symbols"
        / "[symbol]"
        / "metrics"
        / "route.ts"
    )
    assert metrics_route.is_file()
    prefs_route = (
        WEB / "src" / "app" / "api" / "v1" / "me" / "preferences" / "route.ts"
    )
    assert prefs_route.is_file()
    assert (WEB / "src" / "app" / "settings" / "page.tsx").is_file()
    assert 'href: "/settings"' in nav
    assert "FilingMetricsPanel" in (
        WEB / "src" / "app" / "symbols" / "[symbol]" / "page.tsx"
    ).read_text(encoding="utf-8")
    panel = (
        WEB / "src" / "components" / "kit" / "filing-metrics-panel.tsx"
    ).read_text(encoding="utf-8")
    assert "formatCompactNumber" in panel
    assert "truncate" not in panel.split("MetricValue")[1].split("YoyBadge")[0]
    assert "formatCompactNumber" in fmt
    parity = Path("docs/factory/BOT_DASH_PARITY.md").read_text(encoding="utf-8")
    assert "EPS above / below" in parity and "| Yes | Yes |" in parity


def test_symbol_compare_chart_max_four() -> None:
    """Price compare: SVG overlay capped at 4 symbols (Tremor/shadcn pattern)."""
    compare_route = WEB / "src" / "app" / "api" / "v1" / "compare" / "route.ts"
    compare_lib = WEB / "src" / "lib" / "compare-chart.ts"
    compare_ui = WEB / "src" / "components" / "kit" / "symbol-compare-chart.tsx"
    page = (WEB / "src" / "app" / "symbols" / "[symbol]" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert compare_route.is_file()
    assert compare_lib.is_file()
    assert compare_ui.is_file()
    route_src = compare_route.read_text(encoding="utf-8")
    lib_src = compare_lib.read_text(encoding="utf-8")
    ui_src = compare_ui.read_text(encoding="utf-8")
    assert "MAX_COMPARE_SYMBOLS = 4" in route_src
    assert "MAX_COMPARE_SYMBOLS = 4" in lib_src
    assert "price_snapshots" in route_src
    assert (
        "no cse.lk" in route_src.lower()
        or "No cse.lk" in route_src
        or "no cse" in route_src.lower()
    )
    assert "buildCompareChartRows" in lib_src
    assert "COMPARE_TICK_LIMIT" in lib_src
    assert "indexed" in lib_src and "polyline" in ui_src
    assert "CandlestickChart" not in ui_src
    assert "COMPARE_TICK_LIMIT" in ui_src
    assert "SymbolCompareChart" in page
    assert "SCALE_OPTIONS" in ui_src
    assert "initialPeerSeries" in ui_src
    assert "compare=" in page or "comparePeers" in page
    assert "DEFAULT_LIMIT = 180" in route_src or "DEFAULT_LIMIT=180" in route_src.replace(
        " ", ""
    )

def test_dash_ux_improve_loops() -> None:
    """UX loops: watch state, alert type deep-link, metrics fail, chips, 404."""
    watch = (WEB / "src" / "components" / "watchlist-controls.tsx").read_text(encoding="utf-8")
    alerts = (WEB / "src" / "app" / "alerts" / "page.tsx").read_text(encoding="utf-8")
    panel = (
        (WEB / "src" / "components" / "kit" / "filing-metrics-panel.tsx")
        .read_text(encoding="utf-8")
    )
    overview = (WEB / "src" / "app" / "overview" / "page.tsx").read_text(encoding="utf-8")
    chips = (
        (WEB / "src" / "components" / "kit" / "disclosure-timeline.tsx")
        .read_text(encoding="utf-8")
    )
    spark = (WEB / "src" / "components" / "sparkline.tsx").read_text(encoding="utf-8")
    badge = (WEB / "src" / "components" / "kit" / "change-badge.tsx").read_text(encoding="utf-8")
    assert "watching?: boolean" in watch or "watching = false" in watch
    assert "initialType" in alerts or "typeFilter" in alerts
    assert "loadFailed" in panel
    assert "Exact prior-year" in panel
    assert "rule.armed" in overview
    assert "aria-current" in chips
    assert (WEB / "src" / "app" / "overview" / "loading.tsx").is_file()
    assert (WEB / "src" / "app" / "settings" / "loading.tsx").is_file()
    assert (WEB / "src" / "app" / "not-found.tsx").is_file()
    assert "ExpandableBrief" in panel or (
        WEB / "src" / "components" / "kit" / "expandable-brief.tsx"
    ).is_file()
    assert "stored ticks" in spark
    assert "sr-only" in badge
    symbol_page_src = (
        (WEB / "src" / "app" / "symbols" / "[symbol]" / "page.tsx")
        .read_text(encoding="utf-8")
    )
    assert "safe-area-inset-bottom" in symbol_page_src


def test_symbol_data_quality_notices() -> None:
    """Symbol pages surface honest coverage warnings (extract/filings/briefs)."""
    quality_lib = (WEB / "src" / "lib" / "data-quality.ts").read_text(encoding="utf-8")
    notices_ui = (
        WEB / "src" / "components" / "kit" / "data-quality-notices.tsx"
    ).read_text(encoding="utf-8")
    metrics_route = (
        WEB
        / "src"
        / "app"
        / "api"
        / "v1"
        / "symbols"
        / "[symbol]"
        / "metrics"
        / "route.ts"
    ).read_text(encoding="utf-8")
    symbol_page = (
        WEB / "src" / "app" / "symbols" / "[symbol]" / "page.tsx"
    ).read_text(encoding="utf-8")
    panel = (
        WEB / "src" / "components" / "kit" / "filing-metrics-panel.tsx"
    ).read_text(encoding="utf-8")

    assert "buildDataQualityNotices" in quality_lib
    assert "parseFilingQualitySummary" in quality_lib
    assert "extract-failed" in quality_lib
    assert "no-financial-filings" in quality_lib
    assert "thin-ticks" in quality_lib
    assert "brief-pending" in quality_lib
    assert "DataQualityNotices" in notices_ui
    assert "AlertBanner" in notices_ui
    assert "data-testid=\"data-quality-notices\"" in notices_ui
    assert "quality" in metrics_route
    assert "metrics_failed" in metrics_route
    assert "financial_filings" in metrics_route
    assert "toNonNegativeSafeInt" in metrics_route
    assert "DataQualityNotices" in symbol_page
    assert "parseFilingQualitySummary" in symbol_page
    assert "emptyMetricsHint" in symbol_page
    assert "emptyMetricsHint" in panel
    assert "emptyBriefHint" in panel

