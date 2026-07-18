"""Wave33: /scenarios page stays deep-linkable; Scenarios off primary nav.

Phase 3 fence: keep the stub page + ``AppNav active="/scenarios"`` prop, but
do not list Scenarios in the primary ``links`` array until LLM runs exist.
Longest-prefix resolution still prefers ``/alerts/history`` over ``/alerts``.
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


def test_app_nav_scenarios_not_in_primary_links() -> None:
    nav = WEB / "src" / "components" / "app-nav.tsx"
    source = nav.read_text(encoding="utf-8")
    assert 'href: "/scenarios", label: "Scenarios"' not in source
    assert "Phase 3" in source or "primary until Phase 3" in source
    assert "resolveActiveNavHref" in source
    assert "usePathname" in source
    assert "activeHref === link.href" in source
    assert 'aria-current={isActive ? "page" : undefined}' in source
    assert "href.length > best.length" in source
    assert "path.startsWith(`${href}/`)" in source
    assert "path === href" in source
    # Phase A: research surfaces nest under Research, not primary chrome.
    assert "primaryLinks" in source
    assert "researchLinks" in source
    assert "Research" in source
    assert 'href: "/appetite"' in source
    assert 'href: "/signals"' in source
    assert 'href: "/people"' in source
    assert 'href: "/graph"' in source
    # resolveActiveNavHref still covers research routes via allNavLinks.
    assert "allNavLinks" in source
