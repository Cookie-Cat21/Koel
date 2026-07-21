"""Immutable bar snapshots for distributed ML research jobs."""

from __future__ import annotations

import argparse
import asyncio
import gzip
import hashlib
import json
import math
import os
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from koel.domain import DailyBar
from koel.storage import Storage

SNAPSHOT_SCHEMA_VERSION = 1
BAR_COLUMNS = (
    "symbol",
    "trade_date",
    "price",
    "high",
    "low",
    "open",
    "volume",
    "source",
    "source_period",
    "bar_ts",
)


@dataclass(frozen=True, slots=True)
class SnapshotManifest:
    schema_version: int
    dataset: str
    created_at: str
    postgres_snapshot: str
    bars_file: str
    bars_sha256: str
    columns: tuple[str, ...]
    rows: int
    symbols: int
    first_date: str | None
    last_date: str | None
    source_rows: dict[str, int]
    quality: dict[str, int | float | None]


@dataclass(frozen=True, slots=True)
class LoadedSnapshot:
    manifest: SnapshotManifest
    series: dict[str, list[DailyBar]]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


async def export_bar_snapshot(
    storage: Storage,
    *,
    dataset: str,
    output_dir: Path,
) -> SnapshotManifest:
    """Export one repeatable-read DB view to deterministic gzip JSONL."""
    if dataset not in {"cse", "hybrid"}:
        raise ValueError("dataset must be 'cse' or 'hybrid'")

    output_dir.mkdir(parents=True, exist_ok=True)
    bars_path = output_dir / "bars.jsonl.gz"
    manifest_path = output_dir / "manifest.json"
    if dataset == "hybrid":
        query = """
            SELECT symbol, trade_date, price, high, low, open, volume,
                   source,
                   CASE WHEN source = 'cse' THEN 5 ELSE 0 END AS source_period,
                   bar_ts
            FROM hybrid_daily_bars
            ORDER BY symbol, trade_date
        """
    else:
        query = """
            SELECT symbol, trade_date, price, high, low, open, volume,
                   'cse'::text AS source, source_period, bar_ts
            FROM daily_bars
            WHERE symbol <> 'ASPI'
            ORDER BY symbol, trade_date
        """

    rows = 0
    symbols: set[str] = set()
    first_date: date | None = None
    last_date: date | None = None
    source_rows: dict[str, int] = defaultdict(int)
    nonpositive_prices = 0
    moves_gt_20pct = 0
    moves_gt_50pct = 0
    moves_gt_100pct = 0
    previous_symbol: str | None = None
    previous_price: float | None = None
    postgres_snapshot = ""

    with (
        bars_path.open("wb") as raw_handle,
        gzip.GzipFile(fileobj=raw_handle, mode="wb", mtime=0) as compressed,
    ):
        async with storage._pool.connection() as conn, conn.transaction():
            await conn.execute(
                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
            )
            snapshot_row = await (
                await conn.execute("SELECT txid_current_snapshot() AS snapshot")
            ).fetchone()
            if snapshot_row is not None:
                postgres_snapshot = str(dict(snapshot_row).get("snapshot") or "")

            async with conn.cursor(name="ml_snapshot_export") as cursor:
                await cursor.execute(query)
                async for raw in cursor:
                    row = dict(raw)
                    symbol = str(row["symbol"]).strip().upper()
                    trade_date = row["trade_date"]
                    price = float(row["price"])
                    source = str(row["source"])
                    if price <= 0 or not math.isfinite(price):
                        nonpositive_prices += 1

                    if previous_symbol == symbol and previous_price not in (None, 0):
                        move = (price / float(previous_price)) - 1.0
                        if math.isfinite(move):
                            absolute_move = abs(move)
                            moves_gt_20pct += int(absolute_move > 0.20)
                            moves_gt_50pct += int(absolute_move > 0.50)
                            moves_gt_100pct += int(absolute_move > 1.0)
                    previous_symbol = symbol
                    previous_price = price

                    payload = (
                        symbol,
                        trade_date.isoformat(),
                        price,
                        _optional_float(row.get("high")),
                        _optional_float(row.get("low")),
                        _optional_float(row.get("open")),
                        _optional_float(row.get("volume")),
                        source,
                        int(row["source_period"]),
                        row["bar_ts"].isoformat(),
                    )
                    encoded = json.dumps(
                        payload, separators=(",", ":"), allow_nan=False
                    ).encode("utf-8")
                    compressed.write(encoded + b"\n")

                    rows += 1
                    symbols.add(symbol)
                    source_rows[source] += 1
                    first_date = (
                        trade_date
                        if first_date is None or trade_date < first_date
                        else first_date
                    )
                    last_date = (
                        trade_date
                        if last_date is None or trade_date > last_date
                        else last_date
                    )

    manifest = SnapshotManifest(
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        dataset=dataset,
        created_at=datetime.now(UTC).isoformat(),
        postgres_snapshot=postgres_snapshot,
        bars_file=bars_path.name,
        bars_sha256=_sha256(bars_path),
        columns=BAR_COLUMNS,
        rows=rows,
        symbols=len(symbols),
        first_date=first_date.isoformat() if first_date else None,
        last_date=last_date.isoformat() if last_date else None,
        source_rows=dict(sorted(source_rows.items())),
        quality={
            "nonpositive_prices": nonpositive_prices,
            "moves_gt_20pct": moves_gt_20pct,
            "moves_gt_50pct": moves_gt_50pct,
            "moves_gt_100pct": moves_gt_100pct,
        },
    )
    manifest_path.write_text(
        json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def load_bar_snapshot(snapshot_dir: Path) -> LoadedSnapshot:
    """Load and verify a snapshot artifact before training."""
    manifest_path = snapshot_dir / "manifest.json"
    raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = SnapshotManifest(
        schema_version=int(raw_manifest["schema_version"]),
        dataset=str(raw_manifest["dataset"]),
        created_at=str(raw_manifest["created_at"]),
        postgres_snapshot=str(raw_manifest.get("postgres_snapshot") or ""),
        bars_file=str(raw_manifest["bars_file"]),
        bars_sha256=str(raw_manifest["bars_sha256"]),
        columns=tuple(raw_manifest["columns"]),
        rows=int(raw_manifest["rows"]),
        symbols=int(raw_manifest["symbols"]),
        first_date=raw_manifest.get("first_date"),
        last_date=raw_manifest.get("last_date"),
        source_rows={
            str(key): int(value)
            for key, value in dict(raw_manifest["source_rows"]).items()
        },
        quality={
            str(key): value for key, value in dict(raw_manifest["quality"]).items()
        },
    )
    if manifest.schema_version != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported snapshot schema version {manifest.schema_version}"
        )
    if manifest.columns != BAR_COLUMNS:
        raise ValueError("snapshot columns do not match the current schema")

    bars_path = snapshot_dir / manifest.bars_file
    actual_sha = _sha256(bars_path)
    if actual_sha != manifest.bars_sha256:
        raise ValueError("snapshot SHA-256 mismatch")

    series: dict[str, list[DailyBar]] = defaultdict(list)
    rows = 0
    with gzip.open(bars_path, mode="rt", encoding="utf-8") as handle:
        for line in handle:
            values = json.loads(line)
            if not isinstance(values, list) or len(values) != len(BAR_COLUMNS):
                raise ValueError(f"invalid snapshot row at line {rows + 1}")
            row = dict(zip(BAR_COLUMNS, values, strict=True))
            symbol = str(row["symbol"])
            series[symbol].append(
                DailyBar(
                    symbol=symbol,
                    trade_date=date.fromisoformat(str(row["trade_date"])),
                    price=float(row["price"]),
                    high=_optional_float(row["high"]),
                    low=_optional_float(row["low"]),
                    open=_optional_float(row["open"]),
                    volume=_optional_float(row["volume"]),
                    source_period=int(row["source_period"]),
                    bar_ts=datetime.fromisoformat(str(row["bar_ts"])),
                )
            )
            rows += 1
    if rows != manifest.rows:
        raise ValueError(
            f"snapshot row count mismatch: expected {manifest.rows}, got {rows}"
        )
    if len(series) != manifest.symbols:
        raise ValueError(
            f"snapshot symbol count mismatch: expected {manifest.symbols}, got {len(series)}"
        )
    return LoadedSnapshot(manifest=manifest, series=dict(series))


async def _run_export(args: argparse.Namespace) -> None:
    database_url = os.environ.get("ML_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("ML_DATABASE_URL (or DATABASE_URL) is required")
    storage = Storage(database_url)
    await storage.open()
    try:
        manifest = await export_bar_snapshot(
            storage,
            dataset=args.dataset,
            output_dir=args.output,
        )
    finally:
        await storage.close()
    print(json.dumps(asdict(manifest), sort_keys=True))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Export or inspect an ML bar snapshot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    export = subparsers.add_parser("export")
    export.add_argument("--dataset", choices=("cse", "hybrid"), default="hybrid")
    export.add_argument("--output", type=Path, required=True)
    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "export":
        asyncio.run(_run_export(args))
        return
    loaded = load_bar_snapshot(args.snapshot)
    print(json.dumps(asdict(loaded.manifest), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
