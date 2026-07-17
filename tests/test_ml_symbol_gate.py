"""Tests for symbol reliability allowlist helpers."""

from __future__ import annotations

import json
from pathlib import Path

from chime.ml.symbol_gate import DEFAULT_CONF_THR, load_symbol_gate


def test_load_symbol_gate_missing(tmp_path: Path) -> None:
    assert load_symbol_gate(tmp_path / "missing.json") is None


def test_load_symbol_gate_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "reliable_symbols.json"
    path.write_text(
        json.dumps(
            {
                "symbols": ["tess.n0000", "JKH.N0000", ""],
                "sym_hit_thr": 0.61,
                "conf_thr": 0.71,
                "min_rows": 20,
                "n_scored_symbols": 2,
                "updated_at": "2026-07-17T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    cfg = load_symbol_gate(path)
    assert cfg is not None
    assert cfg.symbols == ("JKH.N0000", "TESS.N0000")
    assert cfg.conf_thr == DEFAULT_CONF_THR
    assert cfg.sym_hit_thr == 0.61
