"""Wave33: AppNav highlights /scenarios when active.

1. /scenarios page must pass ``active="/scenarios"`` into AppNav.
2. AppNav must list Scenarios and resolve active via ``resolveActiveNavHref``
   + ``usePathname`` (explicit prop or path) so Scenarios gets ``aria-current``.
3. Longest-prefix resolution prefers ``/alerts/history`` over ``/alerts`` and
   exact-matches ``/scenarios``.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_scenarios_page_passes_active_prop() -> None:
    page = WEB / "src" / "app" / "scenarios" / "page.tsx"
    source = page.read_text(encoding="utf-8")
    assert 'active="/scenarios"' in source
    assert "AppNav" in source


def test_app_nav_resolves_scenarios_active() -> None:
    nav = WEB / "src" / "components" / "app-nav.tsx"
    source = nav.read_text(encoding="utf-8")
    assert 'href: "/scenarios", label: "Scenarios"' in source
    assert "resolveActiveNavHref" in source
    assert "usePathname" in source
    assert "activeHref === link.href" in source
    assert 'aria-current={isActive ? "page" : undefined}' in source
    assert "href.length > best.length" in source
    assert "path.startsWith(`${href}/`)" in source
    assert "path === href" in source
