"""Unit tests for gated serve threshold helpers."""

from __future__ import annotations

import json
from pathlib import Path

from chime.ml.forecast_serve import (
    DEFAULT_GATE_THR,
    P90_GATE_THR,
    _load_gate_threshold,
)
from chime.ml.symbol_gate import DEFAULT_CONF_THR, load_symbol_gate


def test_load_gate_threshold_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert _load_gate_threshold() == DEFAULT_GATE_THR
    assert _load_gate_threshold(p90=True) == P90_GATE_THR


def test_load_gate_threshold_from_calibration(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    art = tmp_path / "data" / "ml_artifacts"
    art.mkdir(parents=True)
    (art / "gate_calibration.json").write_text(
        json.dumps({"threshold": 0.42}),
        encoding="utf-8",
    )
    assert _load_gate_threshold() == 0.42


def test_p90_uses_symbol_gate_conf(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    art = tmp_path / "data" / "ml_artifacts"
    art.mkdir(parents=True)
    (art / "reliable_symbols.json").write_text(
        json.dumps(
            {
                "symbols": ["TESS.N0000"],
                "sym_hit_thr": 0.61,
                "conf_thr": 0.71,
                "min_rows": 20,
            }
        ),
        encoding="utf-8",
    )
    assert _load_gate_threshold(p90=True) == DEFAULT_CONF_THR
    cfg = load_symbol_gate(art / "reliable_symbols.json")
    assert cfg is not None
    assert "TESS.N0000" in cfg.symbols
