"""Wave34: medium+ bugs — history pagination, strict booleans, client finite.

1. Fire history UI must pass digits-only ``offset`` (API already paginated) and
   expose Previous/Next — WS-034 acceptance is paginated audit trail.
   W58 hardens prev/next a11y (``rel``, page ``aria-label``, ``aria-disabled``).
2. History API/UI delivery flags must use ``=== true`` (not ``Boolean(...)``
   which treats ``"false"`` / ``1`` as sent/dead-lettered).
3. Alerts list/API/db ``active``/``armed`` must use ``=== true`` for the same
   reason (Armed mislabel from hostile JSON).
4. Alert type ``<select>`` must gate via ``isAlertType`` (no ``as AlertType``).
5. ``toFiniteNumber`` lives in client-safe ``finite-number.ts`` (no ``pg``).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_history_ui_paginates_with_offset() -> None:
    page = WEB / "src" / "app" / "alerts" / "history" / "page.tsx"
    source = page.read_text(encoding="utf-8")
    assert "toNonNegativeSafeInt(sp.offset" in source
    assert 'qs.set("offset"' in source
    assert "MAX_HISTORY_OFFSET" in source
    assert 'aria-label="Fire history pages"' in source
    assert "historyHref" in source
    assert "hasPrev" in source
    assert "hasNext" in source
    # W58 a11y: labelled prev/next links + aria-disabled on unavailable side.
    assert 'aria-label="Previous page of fire history"' in source
    assert 'aria-label="Next page of fire history"' in source
    assert 'rel="prev"' in source
    assert 'rel="next"' in source
    assert 'aria-disabled="true"' in source
    # Filter Apply must not drop limit; new filter omits offset (reset page).
    assert 'name="limit"' in source


def test_history_delivery_flags_strict_true() -> None:
    route = (
        WEB / "src" / "app" / "api" / "v1" / "alerts" / "history" / "route.ts"
    )
    source = route.read_text(encoding="utf-8")
    assert "row.message_sent === true" in source
    assert "row.dead_lettered === true" in source
    assert "row.delivery_attempted_ok === true" in source
    assert "Boolean(row.message_sent)" not in source
    assert "Boolean(row.dead_lettered)" not in source
    assert "Boolean(row.delivery_attempted_ok)" not in source

    page = WEB / "src" / "app" / "alerts" / "history" / "page.tsx"
    page_src = page.read_text(encoding="utf-8")
    assert "r.message_sent === true" in page_src
    assert "r.dead_lettered === true" in page_src
    assert "Boolean(r.message_sent)" not in page_src
    assert "Boolean(r.dead_lettered)" not in page_src


def test_alerts_armed_active_strict_true() -> None:
    route = WEB / "src" / "app" / "api" / "v1" / "alerts" / "route.ts"
    source = route.read_text(encoding="utf-8")
    assert "row.active === true" in source
    assert "row.armed === true" in source
    assert "Boolean(row.active)" not in source
    assert "Boolean(row.armed)" not in source

    page = WEB / "src" / "app" / "alerts" / "page.tsx"
    page_src = page.read_text(encoding="utf-8")
    assert "r.active === true" in page_src
    assert "r.armed === true" in page_src
    assert "Boolean(r.active)" not in page_src
    assert "Boolean(r.armed)" not in page_src

    db = WEB / "src" / "lib" / "db.ts"
    db_src = db.read_text(encoding="utf-8")
    assert "row.active === true" in db_src
    assert "row.armed === true" in db_src
    assert "Boolean(row.active)" not in db_src
    assert "Boolean(row.armed)" not in db_src


def test_alert_type_select_uses_is_alert_type() -> None:
    source = (WEB / "src" / "components" / "alert-controls.tsx").read_text(
        encoding="utf-8"
    )
    # Fail-closed on Select onValueChange (or legacy native change events).
    assert "isAlertType(value)" in source or "isAlertType(e.target.value)" in source
    assert "as AlertType" not in source


def test_finite_number_module_client_safe() -> None:
    finite = WEB / "src" / "lib" / "api" / "finite-number.ts"
    assert finite.is_file()
    source = finite.read_text(encoding="utf-8")
    assert "FINITE_DECIMAL_RE" in source
    assert 'from "pg"' not in source
    controls = (WEB / "src" / "components" / "alert-controls.tsx").read_text(
        encoding="utf-8"
    )
    assert 'from "@/lib/api/finite-number"' in controls
