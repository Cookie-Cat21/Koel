"""E12-Q01 — dash route/page regressions for health degradation and CSE isolation."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
UNIT_MTS = Path(__file__).resolve().parent / "web_health_route_unit.mts"

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
    """Watchlist, alerts, and health keep the global NFA footer visible."""
    page_paths = [
        WEB / "src" / "app" / "watchlist" / "page.tsx",
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
