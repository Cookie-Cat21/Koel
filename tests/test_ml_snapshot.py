"""Immutable ML snapshot format tests."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from koel.ml.snapshot import BAR_COLUMNS, SNAPSHOT_SCHEMA_VERSION, load_bar_snapshot


def _write_snapshot(path: Path) -> None:
    path.mkdir()
    rows = [
        [
            "A.N0000",
            "2025-01-02",
            10.0,
            10.5,
            9.5,
            9.8,
            1000.0,
            "yahoo",
            0,
            "2025-01-02T09:00:00+00:00",
        ],
        [
            "A.N0000",
            "2025-01-03",
            10.2,
            10.6,
            9.9,
            None,
            1200.0,
            "cse",
            5,
            "2025-01-03T09:00:00+00:00",
        ],
    ]
    bars_path = path / "bars.jsonl.gz"
    with gzip.open(bars_path, mode="wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")
    digest = hashlib.sha256(bars_path.read_bytes()).hexdigest()
    manifest = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "dataset": "hybrid",
        "created_at": "2025-01-04T00:00:00+00:00",
        "postgres_snapshot": "1:2:",
        "bars_file": bars_path.name,
        "bars_sha256": digest,
        "columns": list(BAR_COLUMNS),
        "rows": 2,
        "symbols": 1,
        "first_date": "2025-01-02",
        "last_date": "2025-01-03",
        "source_rows": {"cse": 1, "yahoo": 1},
        "quality": {
            "nonpositive_prices": 0,
            "moves_gt_20pct": 0,
            "moves_gt_50pct": 0,
            "moves_gt_100pct": 0,
        },
    }
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_snapshot_load_verifies_and_reconstructs_bars(tmp_path) -> None:
    snapshot = tmp_path / "snapshot"
    _write_snapshot(snapshot)
    loaded = load_bar_snapshot(snapshot)
    assert loaded.manifest.rows == 2
    assert loaded.manifest.bars_sha256
    assert list(loaded.series) == ["A.N0000"]
    assert [bar.price for bar in loaded.series["A.N0000"]] == [10.0, 10.2]
    assert [bar.source_period for bar in loaded.series["A.N0000"]] == [0, 5]


def test_snapshot_rejects_tampering(tmp_path) -> None:
    snapshot = tmp_path / "snapshot"
    _write_snapshot(snapshot)
    with (snapshot / "bars.jsonl.gz").open("ab") as handle:
        handle.write(b"tampered")
    with pytest.raises(ValueError, match="SHA-256"):
        load_bar_snapshot(snapshot)
