"""Deterministic Qlib-compatible CSE CSV/calendar/instrument export."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from koel.domain import DailyBar
from koel.ml.snapshot import LoadedSnapshot, composite_snapshot_sha, load_bar_snapshot

ORDINARY_SUFFIXES = (".N0000", ".X0000")
QLIB_FIELDS = (
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "factor",
    "change",
    "source_is_cse",
)


@dataclass(frozen=True, slots=True)
class QlibExportManifest:
    schema_version: int
    source_snapshot_sha256: str
    symbols: int
    rows: int
    first_date: str | None
    last_date: str | None
    fields: tuple[str, ...]
    adjusted: bool
    qualification_allowed: bool
    instrument_map: dict[str, str]
    file_sha256: dict[str, str]
    qlib_version: str
    qlib_release_commit: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _value(value: float | None) -> float | str:
    return value if value is not None and math.isfinite(value) else ""


def _write_instrument_csv(path: Path, bars: list[DailyBar]) -> int:
    ordered = sorted(bars, key=lambda bar: bar.trade_date)
    dates = [bar.trade_date for bar in ordered]
    if len(set(dates)) != len(dates):
        raise ValueError(f"duplicate trade date in {ordered[0].symbol}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(QLIB_FIELDS)
        previous: float | None = None
        for bar in ordered:
            change: float | str = ""
            if previous is not None and previous > 0:
                change = (bar.price / previous) - 1.0
            writer.writerow(
                (
                    bar.trade_date.isoformat(),
                    _value(bar.open),
                    _value(bar.high),
                    _value(bar.low),
                    bar.price,
                    _value(bar.volume),
                    1.0,
                    change,
                    float(bar.source_period == 5),
                )
            )
            previous = bar.price
    return len(ordered)


def export_qlib_compatible(
    loaded: LoadedSnapshot,
    *,
    output_dir: Path,
    min_history: int = 60,
) -> QlibExportManifest:
    """Export immutable per-instrument CSV plus Qlib calendar/instrument files."""
    if min_history < 1:
        raise ValueError("min_history must be positive")
    csv_dir = output_dir / "csv"
    calendars_dir = output_dir / "calendars"
    instruments_dir = output_dir / "instruments"
    for directory in (csv_dir, calendars_dir, instruments_dir):
        directory.mkdir(parents=True, exist_ok=True)

    instrument_map: dict[str, str] = {}
    file_hashes: dict[str, str] = {}
    calendar = set()
    instrument_lines: list[str] = []
    total_rows = 0
    first_date = None
    last_date = None

    for symbol, bars in sorted(loaded.series.items()):
        normalized = symbol.strip().upper()
        if not normalized.endswith(ORDINARY_SUFFIXES):
            continue
        valid = [
            bar
            for bar in sorted(bars, key=lambda item: item.trade_date)
            if bar.price > 0 and math.isfinite(bar.price)
        ]
        if len(valid) < min_history:
            continue
        filename = f"{normalized.lower()}.csv"
        path = csv_dir / filename
        total_rows += _write_instrument_csv(path, valid)
        instrument_map[normalized] = filename
        file_hashes[str(path.relative_to(output_dir))] = _sha256(path)
        start, end = valid[0].trade_date, valid[-1].trade_date
        instrument_lines.append(f"{normalized}\t{start.isoformat()}\t{end.isoformat()}")
        calendar.update(bar.trade_date for bar in valid)
        first_date = start if first_date is None or start < first_date else first_date
        last_date = end if last_date is None or end > last_date else last_date

    calendar_path = calendars_dir / "day.txt"
    calendar_path.write_text(
        "".join(f"{session.isoformat()}\n" for session in sorted(calendar)),
        encoding="utf-8",
    )
    instruments_path = instruments_dir / "cse_equities.txt"
    instruments_path.write_text(
        "".join(f"{line}\n" for line in instrument_lines),
        encoding="utf-8",
    )
    file_hashes[str(calendar_path.relative_to(output_dir))] = _sha256(calendar_path)
    file_hashes[str(instruments_path.relative_to(output_dir))] = _sha256(
        instruments_path
    )

    manifest = QlibExportManifest(
        schema_version=1,
        source_snapshot_sha256=composite_snapshot_sha(loaded.manifest),
        symbols=len(instrument_map),
        rows=total_rows,
        first_date=first_date.isoformat() if first_date else None,
        last_date=last_date.isoformat() if last_date else None,
        fields=QLIB_FIELDS,
        adjusted=False,
        qualification_allowed=False,
        instrument_map=instrument_map,
        file_sha256=dict(sorted(file_hashes.items())),
        qlib_version="0.9.7",
        qlib_release_commit="da920b7f954f48ab1bb64117c976710de198373e",
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Export a Qlib-compatible CSE panel")
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--min-history", type=int, default=60)
    args = parser.parse_args(argv)
    loaded = load_bar_snapshot(args.snapshot)
    manifest = export_qlib_compatible(
        loaded,
        output_dir=args.output,
        min_history=args.min_history,
    )
    print(json.dumps(asdict(manifest), sort_keys=True))


if __name__ == "__main__":
    main()
