"""Wave51: medium+ bugs — fail-closed maxBytes for bounded body readers.

1. ``readBoundedResponseText`` must reject non-integer / non-finite / ≤0
   ``maxBytes`` — ``Math.max(1, NaN) === NaN`` and ``total > NaN`` is always
   false, so a hostile / misbuilt cap used to disable the stream gate.
2. ``readJsonBody`` must use the same fail-closed cap resolution (parity) —
   chunked request bodies used to bypass the length gate under NaN maxBytes.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_read_bounded_max_bytes_fail_closed() -> None:
    source = (WEB / "src" / "lib" / "api" / "read-bounded-text.ts").read_text(
        encoding="utf-8"
    )
    assert "readBoundedResponseText" in source
    # W62: shared resolveBoundedBodyCap (NaN/≤0 → 1 + abs ceiling).
    assert "resolveBoundedBodyCap" in source
    assert "Number.isInteger(maxBytes)" in source
    assert "maxBytes < 1" in source
    assert "Math.max(1, maxBytes)" not in source
    assert "total > cap" in source
    assert "reader.cancel()" in source


def test_read_json_body_max_bytes_fail_closed() -> None:
    source = (WEB / "src" / "lib" / "api" / "read-json-body.ts").read_text(
        encoding="utf-8"
    )
    # W62: abs-cap via shared helper (parity response body reader).
    assert "resolveBoundedBodyCap" in source
    assert "resolveBoundedBodyCap(maxBytes)" in source
    assert "Math.max(1, maxBytes)" not in source
    assert "total > cap" in source
