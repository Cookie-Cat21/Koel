"""Wave40: medium+ bugs — SSR origin, HEALTH_URL SSRF, JSON body, CSRF path.

1. ``serverApiGet`` must resolve origin via ``resolveInternalOrigin`` /
   ``DASH_INTERNAL_ORIGIN`` / loopback — never client ``Host`` /
   ``X-Forwarded-*`` (cookie-bearing SSR SSRF). ``redirect: "error"``.
2. Paths must pass ``isSafeServerApiPath`` (``/api/v1/*`` only; no ``..`` /
   backslash / controls).
3. ``HEALTH_URL`` proxy must reject non-loopback / non-http URLs
   (``isAllowedHealthProxyUrl``) so a mis-set env is not open SSRF.
4. ``apiMutate`` must reject absolute / scheme-relative paths (CSRF header
   must not leave origin).
5. Mutating routes (demo / watchlist / alerts) must bound JSON via
   ``readJsonBody`` streamed reader (no unbounded ``request.json()`` OOM).
6. Browser CSRF cookie decode must cap length (parity with server
   ``MAX_CSRF_TOKEN_LENGTH``) without importing ``node:crypto``.
7. Symbol disclosure parse must allowlist ``url`` / ``pdf_url`` and
   sanitize brief text at parse time (defense in depth).
8. Login form must sanitize API error messages via ``apiErrorMessage``.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_server_api_origin_not_from_client_host() -> None:
    source = (WEB / "src" / "lib" / "api" / "server-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert "resolveInternalOrigin" in source
    assert "DASH_INTERNAL_ORIGIN" in source
    assert "isSafeServerApiPath" in source
    assert "isLoopbackHost" in source
    assert 'h.get("host")' not in source
    assert "x-forwarded-host" not in source.lower()
    assert "x-forwarded-proto" not in source.lower()
    assert "${proto}://${host}${path}" not in source
    assert "resolveInternalOrigin()}${path}" in source
    assert 'pathOnly.startsWith("/api/v1/")' in source
    assert 'redirect: "error"' in source


def test_health_url_loopback_only() -> None:
    source = (
        WEB / "src" / "app" / "api" / "v1" / "health" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "isAllowedHealthProxyUrl" in source
    assert 'parsed.protocol !== "http:"' in source
    assert 'host !== "127.0.0.1"' in source
    assert "isAllowedHealthProxyUrl(healthUrl)" in source
    fetch_idx = source.index("await fetch(healthUrl")
    gate_idx = source.index("isAllowedHealthProxyUrl(healthUrl)")
    assert gate_idx < fetch_idx


def test_api_mutate_rejects_absolute_paths() -> None:
    source = (WEB / "src" / "lib" / "api" / "client-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert 'path.startsWith("/")' in source
    assert 'path.startsWith("//")' in source
    assert 'path.includes("://")' in source
    assert "apiMutate path must be root-relative" in source


def test_mutating_routes_bound_json_body() -> None:
    helper = (WEB / "src" / "lib" / "api" / "read-json-body.ts").read_text(
        encoding="utf-8"
    )
    assert "MAX_JSON_BODY_BYTES" in helper
    assert "readJsonBody" in helper
    assert "getReader" in helper
    assert "total > cap" in helper
    assert "await request.arrayBuffer()" not in helper
    assert "await request.json()" not in helper

    for rel in (
        "src/app/api/v1/auth/demo/route.ts",
        "src/app/api/v1/watchlist/route.ts",
        "src/app/api/v1/alerts/route.ts",
    ):
        source = (WEB / rel).read_text(encoding="utf-8")
        assert "readJsonBody(request)" in source, rel
        assert "await request.json()" not in source, rel
        assert "Request body too large" in source, rel


def test_browser_csrf_length_capped_client_safe() -> None:
    source = (WEB / "src" / "lib" / "api" / "client-fetch.ts").read_text(
        encoding="utf-8"
    )
    assert "MAX_CSRF_TOKEN_LENGTH" in source
    assert "raw.length > MAX_CSRF_TOKEN_LENGTH" in source
    assert 'from "@/lib/auth/csrf"' not in source
    assert 'from "@/lib/auth/config"' in source
    config = (WEB / "src" / "lib" / "auth" / "config.ts").read_text(
        encoding="utf-8"
    )
    assert "MAX_CSRF_TOKEN_LENGTH" in config
    csrf = (WEB / "src" / "lib" / "auth" / "csrf.ts").read_text(encoding="utf-8")
    assert "from \"./config\"" in csrf or "from './config'" in csrf
    assert "MAX_CSRF_TOKEN_LENGTH" in csrf


def test_symbol_disclosure_parse_allowlists_hrefs() -> None:
    page = WEB / "src" / "app" / "symbols" / "[symbol]" / "page.tsx"
    data = (WEB / "src" / "lib" / "db" / "symbol-page-data.ts").read_text(
        encoding="utf-8"
    )
    source = page.read_text(encoding="utf-8")
    assert "safeFilingHref" in source
    assert "safeAnnouncementUrl(row.url)" in data
    assert "safePdfUrl(row.pdf_url)" in data
    assert "sanitizeBriefText(row.brief, brief_status)" in data
    assert 'url: typeof r.url === "string" ? r.url : null' not in data
    assert 'pdf_url: typeof r.pdf_url === "string" ? r.pdf_url : null' not in data
    assert 'brief: typeof r.brief === "string" ? r.brief : null' not in data


def test_login_form_sanitizes_api_errors() -> None:
    source = (WEB / "src" / "components" / "login-form.tsx").read_text(
        encoding="utf-8"
    )
    assert "apiErrorMessage" in source
    assert "data?.error?.message" not in source
