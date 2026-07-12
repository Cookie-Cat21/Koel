"""Wave32: medium+ bugs — toFiniteNumber, health SafeInt, alert threshold.

1. ``toFiniteNumber`` must reject empty/bool/array/sci-notation (no bare
   ``Number(value)`` soft-accept that mapped ``""``→0 / ``true``→1).
2. Health API ``parseBriefQueue`` / ``sanitizeCircuits`` must use digits-only
   ``toNonNegativeSafeInt`` (not ``Number.isFinite`` + ``Math.floor``).
3. Health page timestamps must fail-closed via ``toIso`` (no raw echo).
4. Alert create form thresholds must parse via ``toFiniteNumber`` (not
   ``Number(raw)`` sci-notation soft-accept).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_to_finite_number_rejects_empty_bool_array_sci() -> None:
    source = (WEB / "src" / "lib" / "api" / "finite-number.ts").read_text(
        encoding="utf-8"
    )
    assert "FINITE_DECIMAL_RE" in source
    assert "MAX_FINITE_NUMBER_STRING_LENGTH" in source
    assert 'typeof value === "number"' in source
    assert 'typeof value === "string"' in source
    # Must not coerce arbitrary unknowns via Number(value).
    assert "Number(value)" not in source
    assert (
        'const n = typeof value === "number" ? value : Number(value);'
        not in source
    )
    # Client-safe module — no pg import (alert form is "use client").
    assert 'from "pg"' not in source
    browse = (WEB / "src" / "lib" / "api" / "market-browse.ts").read_text(
        encoding="utf-8"
    )
    assert 'from "@/lib/api/finite-number"' in browse
    assert "toFiniteNumber" in browse


def test_health_api_brief_circuit_safe_int() -> None:
    source = (
        WEB / "src" / "app" / "api" / "v1" / "health" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "toNonNegativeSafeInt(obj.pending_briefs, -1)" in source
    assert "toNonNegativeSafeInt(src[key], -1)" in source
    assert "toNonNegativeSafeInt(src[numKey], -1)" in source
    assert "Math.floor(obj.pending_briefs)" not in source
    assert "Math.floor(v)" not in source
    assert "Number.isFinite(obj.pending_briefs)" not in source


def test_health_page_timestamps_use_to_iso() -> None:
    source = (WEB / "src" / "app" / "health" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "function healthTs" in source
    assert "toIso(cleaned)" in source
    assert "started_at: healthTs(r.started_at)" in source
    assert "last_snapshot_at: healthTs(r.last_snapshot_at)" in source
    assert "healthUiString(p.last_tick_at)" not in source
    assert "healthUiString(r.started_at)" not in source


def test_alert_form_threshold_uses_to_finite_number() -> None:
    source = (WEB / "src" / "components" / "alert-controls.tsx").read_text(
        encoding="utf-8"
    )
    assert "toFiniteNumber(raw)" in source
    assert "const n = Number(raw);" not in source
    # Client must not import pg-coupled market-browse for thresholds.
    assert 'from "@/lib/api/finite-number"' in source
    assert 'from "@/lib/api/market-browse"' not in source
