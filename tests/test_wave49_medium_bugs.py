"""Wave49: medium+ bugs — sparkline ts, circuit allowlist, sectors pin realign.

1. ``finiteSparklinePoints`` must sanitize ``ts`` (string-only, strip controls,
   cap via ``MAX_ISO_INPUT_LENGTH``) so hostile snapshot JSON cannot park
   overlong / non-string timestamps in sparkline series.
2. Health page circuit ``state`` must allowlist closed/open/half_open via
   ``CIRCUIT_STATES`` (parity with health API ``sanitizeCircuits``).
3. Wave22/23 sectors-route pins must expect ``normalizeSymbol(row.symbol)``
   after w48 dropped sanitize ``MAX_SECTOR_SYMBOL_LENGTH`` egress.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_sparkline_sanitizes_timestamp() -> None:
    source = (WEB / "src" / "lib" / "sparkline.ts").read_text(encoding="utf-8")
    assert "sanitizeSparklineTs" in source
    assert "MAX_ISO_INPUT_LENGTH" in source
    assert "sanitizeSparklineTs(p.ts)" in source
    # Must not raw-egress caller ts.
    assert "ts: p.ts," not in source


def test_health_page_circuit_state_allowlist() -> None:
    source = (WEB / "src" / "app" / "health" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "CIRCUIT_STATES" in source
    assert "CIRCUIT_STATES.has(stateRaw)" in source


def test_wave22_23_sectors_pin_uses_normalize_symbol() -> None:
    for name in ("test_wave22_medium_bugs.py", "test_wave23_medium_bugs.py"):
        source = (ROOT / "tests" / name).read_text(encoding="utf-8")
        chunk = source.split("def test_sectors_route_sanitizes_text_and_safe_ids")[
            1
        ].split("def test_")[0]
        assert "normalizeSymbol(row.symbol)" in chunk, name
        assert 'assert "MAX_SECTOR_SYMBOL_LENGTH" not in source' in chunk, name
