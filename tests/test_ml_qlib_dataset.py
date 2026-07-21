"""Qlib-compatible CSE export tests."""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime

import pytest

from koel.domain import DailyBar
from koel.ml.qlib_dataset import QLIB_FIELDS, export_qlib_compatible
from koel.ml.snapshot import (
    BAR_COLUMNS,
    FUNDAMENTAL_COLUMNS,
    LoadedSnapshot,
    SnapshotManifest,
)


def _bar(symbol: str, day: int, price: float) -> DailyBar:
    trade_date = date(2026, 1, day)
    return DailyBar(
        symbol=symbol,
        trade_date=trade_date,
        price=price,
        high=price + 1,
        low=price - 1,
        open=price - 0.5,
        volume=1000.0,
        source_period=5,
        bar_ts=datetime(2026, 1, day, tzinfo=UTC),
    )


def _loaded(series: dict[str, list[DailyBar]]) -> LoadedSnapshot:
    manifest = SnapshotManifest(
        schema_version=2,
        dataset="hybrid",
        created_at="2026-01-03T00:00:00+00:00",
        postgres_snapshot="1:2:",
        bars_file="bars.jsonl.gz",
        bars_sha256="a" * 64,
        fundamentals_file="fundamentals.jsonl.gz",
        fundamentals_sha256="b" * 64,
        fundamentals_rows=0,
        fundamentals_columns=FUNDAMENTAL_COLUMNS,
        columns=BAR_COLUMNS,
        rows=sum(len(rows) for rows in series.values()),
        symbols=len(series),
        first_date="2026-01-01",
        last_date="2026-01-02",
        source_rows={"cse": 2},
        quality={},
    )
    return LoadedSnapshot(manifest=manifest, series=series, fundamentals={})


def test_qlib_export_is_deterministic_and_excludes_rights(tmp_path) -> None:
    loaded = _loaded(
        {
            "A.N0000": [_bar("A.N0000", 1, 10.0), _bar("A.N0000", 2, 11.0)],
            "A.R0001": [_bar("A.R0001", 1, 2.0), _bar("A.R0001", 2, 2.1)],
        }
    )
    manifest = export_qlib_compatible(
        loaded,
        output_dir=tmp_path,
        min_history=1,
    )
    assert manifest.symbols == 1
    assert manifest.rows == 2
    assert manifest.adjusted is False
    assert manifest.qualification_allowed is False
    path = tmp_path / "csv" / "a.n0000.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert tuple(rows[0]) == QLIB_FIELDS
    assert rows[2][0] == "2026-01-02"
    assert float(rows[2][7]) == pytest.approx(0.1)
    assert (tmp_path / "calendars" / "day.txt").read_text() == (
        "2026-01-01\n2026-01-02\n"
    )
    assert "A.N0000" in (tmp_path / "instruments" / "cse_equities.txt").read_text()


def test_qlib_export_rejects_duplicate_dates(tmp_path) -> None:
    duplicated = [_bar("A.N0000", 1, 10.0), _bar("A.N0000", 1, 11.0)]
    with pytest.raises(ValueError, match="duplicate"):
        export_qlib_compatible(
            _loaded({"A.N0000": duplicated}),
            output_dir=tmp_path,
            min_history=1,
        )
