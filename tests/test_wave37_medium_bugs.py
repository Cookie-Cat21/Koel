"""Wave37: medium+ bugs — SSR origin, HEALTH_URL SSRF, apiMutate, JSON body.

1. ``serverApiGet`` must fetch via loopback only (``resolveInternalOrigin`` →
   ``http://127.0.0.1:<port>`` / loopback ``DASH_INTERNAL_ORIGIN``) — spoofed
   ``Host: evil.com`` must not become the cookie-bearing fetch authority;
   ``redirect: \"error\"`` so a manual Cookie header cannot follow off-origin;
   paths gated to ``/api/v1/*`` (``isSafeServerApiPath``).
2. ``HEALTH_URL`` proxy must allowlist loopback HTTP only
   (``isAllowedHealthProxyUrl``) so a mis-set env cannot open SSRF.
3. ``apiMutate`` must reject absolute / scheme-relative paths (CSRF header leak)
   and cap browser CSRF cookie + API error.message length.
4. Mutating routes (demo / alerts / watchlist) must stream-bound JSON via
   ``readJsonBody`` / ``MAX_JSON_BODY_BYTES`` — unbounded ``request.json()``
   used to OOM Node on huge POSTs.
5. Symbol disclosures UI parse must allowlist pdf/url + sanitize brief at
   parse-time (defense in depth vs API shape drift).
6. ``MAX_CSRF_TOKEN_LENGTH`` lives in client-safe ``config.ts`` (no
   ``node:crypto``) so browser decode can share the server cap.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_server_api_get_uses_loopback_origin() -> None:
    source = (WEB / "src" / "lib" / "api" / "server-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert "resolveInternalOrigin" in source
    assert "isLoopbackHost" in source
    assert "isSafeServerApiPath" in source
    assert "http://127.0.0.1:${port}" in source
    assert 'redirect: "error"' in source
    assert "${proto}://${host}${path}" not in source
    assert 'h.get("x-forwarded-host")' not in source
    assert 'h.get("host")' not in source
    assert 'const hostRaw = (h.get("host")' not in source
    assert "isLoopbackHost(u.host)" in source
    assert "VERCEL_URL" not in source


def test_health_url_loopback_allowlisted() -> None:
    source = (
        WEB / "src" / "app" / "api" / "v1" / "health" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "isAllowedHealthProxyUrl" in source
    assert 'host !== "127.0.0.1"' in source
    assert 'host !== "localhost"' in source
    assert 'host !== "::1"' in source
    assert 'parsed.protocol !== "http:"' in source
    assert "if (!isAllowedHealthProxyUrl(healthUrl))" in source
    assert source.count("export function isAllowedHealthProxyUrl") == 1


def test_api_mutate_rejects_absolute_paths_and_caps_egress() -> None:
    source = (WEB / "src" / "lib" / "api" / "client-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert "isSafeClientApiPath" in source
    assert 'pathOnly.startsWith("/api/v1/")' in source
    assert "apiMutate path must be root-relative /api/v1/*" in source
    assert "MAX_CSRF_TOKEN_LENGTH" in source
    assert "MAX_API_ERROR_MESSAGE_LENGTH" in source


def test_nav_session_created_at_to_iso() -> None:
    source = (WEB / "src" / "components" / "nav-session.tsx").read_text(
        encoding="utf-8"
    )
    assert "toIso(r.created_at)" in source
    assert "MAX_CSRF_TOKEN_LENGTH" in source
    assert 'typeof r.created_at === "string" && r.created_at ? r.created_at' not in source


def test_csrf_max_length_shared_via_config() -> None:
    config = (WEB / "src" / "lib" / "auth" / "config.ts").read_text(
        encoding="utf-8"
    )
    assert "export const MAX_CSRF_TOKEN_LENGTH = 128" in config
    csrf = (WEB / "src" / "lib" / "auth" / "csrf.ts").read_text(
        encoding="utf-8"
    )
    assert "MAX_CSRF_TOKEN_LENGTH" in csrf
    assert "export const MAX_CSRF_TOKEN_LENGTH = 128" not in csrf


def test_mutating_routes_bound_json_body() -> None:
    helper = (WEB / "src" / "lib" / "api" / "read-json-body.ts").read_text(
        encoding="utf-8"
    )
    assert "MAX_JSON_BODY_BYTES" in helper
    assert "readJsonBody" in helper
    assert "getReader" in helper
    assert "total > cap" in helper

    routes = (
        WEB / "src" / "app" / "api" / "v1" / "auth" / "demo" / "route.ts",
        WEB / "src" / "app" / "api" / "v1" / "alerts" / "route.ts",
        WEB / "src" / "app" / "api" / "v1" / "watchlist" / "route.ts",
    )
    for path in routes:
        source = path.read_text(encoding="utf-8")
        assert "readJsonBody" in source, path.name
        assert "await request.json()" not in source, path.name


def test_symbol_disclosures_parse_allowlists_hrefs() -> None:
    page = WEB / "src" / "app" / "symbols" / "[symbol]" / "page.tsx"
    source = page.read_text(encoding="utf-8")
    assert "safeAnnouncementUrl" in source
    assert "safePdfUrl(" in source
    assert "sanitizeBriefText(briefRaw" in source
    assert 'url: typeof r.url === "string" ? r.url : null' not in source
    assert 'pdf_url: typeof r.pdf_url === "string" ? r.pdf_url : null' not in source
