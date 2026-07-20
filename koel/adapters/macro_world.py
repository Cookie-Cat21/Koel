"""World index research tiles → ``macro_series``.

≤5 delayed EOD closes for Context (US / Europe / Asia / India / VIX).

Sources (research-flagged — never CSE truth):
- FRED public CSV (St. Louis Fed) — SP500, NIKKEI225, VIXCLS
- Yahoo chart JSON (unofficial) — FTSE 100, Nifty 50

Stooq is bot-gated (confirmed). Flag: ``WORLD_INDEX_RESEARCH_ENABLED``.
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import quote

import httpx

log = logging.getLogger(__name__)

# koel series_id → fetch plan
_WORLD_SERIES: tuple[dict[str, str], ...] = (
    {
        "series_id": "WORLD_SPX",
        "provider": "fred",
        "fred_id": "SP500",
        "unit": "index",
        "attribution": "FRED SP500 — research / delayed, not CSE official",
    },
    {
        "series_id": "WORLD_FTSE",
        "provider": "yahoo",
        "yahoo_symbol": "^FTSE",
        "unit": "index",
        "attribution": "Yahoo ^FTSE — research / delayed, not CSE official",
    },
    {
        "series_id": "WORLD_NIKKEI",
        "provider": "fred",
        "fred_id": "NIKKEI225",
        "unit": "index",
        "attribution": "FRED NIKKEI225 — research / delayed, not CSE official",
    },
    {
        "series_id": "WORLD_NSEI",
        "provider": "yahoo",
        "yahoo_symbol": "^NSEI",
        "unit": "index",
        "attribution": "Yahoo ^NSEI — research / delayed, not CSE official",
    },
    {
        "series_id": "WORLD_VIX",
        "provider": "fred",
        "fred_id": "VIXCLS",
        "unit": "index",
        "attribution": "FRED VIXCLS — research / delayed, not CSE official",
    },
)

_FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
_YAHOO_CHART = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    "?interval=1d&range=6mo"
)


def parse_fred_csv(
    text: str,
    *,
    series_id: str,
    attribution: str,
    unit: str = "index",
    max_points: int = 90,
) -> list[dict[str, Any]]:
    """Parse FRED ``DATE,VALUE`` CSV into macro upserts."""
    raw_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
    pairs: list[tuple[date, float]] = []
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if not row or len(row) < 2:
            continue
        if row[0].strip().upper() == "DATE":
            continue
        try:
            d = date.fromisoformat(row[0].strip()[:10])
        except ValueError:
            continue
        val_raw = row[1].strip()
        if not val_raw or val_raw == ".":
            continue
        try:
            value = float(val_raw)
        except ValueError:
            continue
        if not (value > 0):
            continue
        pairs.append((d, value))
    pairs.sort(key=lambda x: x[0])
    if max_points > 0:
        pairs = pairs[-max_points:]
    out: list[dict[str, Any]] = []
    for d, value in pairs:
        ts = datetime(d.year, d.month, d.day, 12, 0, tzinfo=UTC)
        out.append(
            {
                "source": "fred_world",
                "series_id": series_id,
                "ts": ts,
                "value": value,
                "unit": unit,
                "as_of_date": d,
                "attribution": attribution,
                "raw_hash": raw_hash,
            }
        )
    return out


def parse_yahoo_chart(
    payload: dict[str, Any],
    *,
    series_id: str,
    attribution: str,
    unit: str = "index",
    max_points: int = 90,
) -> list[dict[str, Any]]:
    """Parse Yahoo v8 chart JSON closes into macro upserts."""
    chart = payload.get("chart") if isinstance(payload, dict) else None
    results = chart.get("result") if isinstance(chart, dict) else None
    if not isinstance(results, list) or not results:
        return []
    result0 = results[0]
    if not isinstance(result0, dict):
        return []
    timestamps = result0.get("timestamp")
    indicators = result0.get("indicators")
    if not isinstance(timestamps, list) or not isinstance(indicators, dict):
        return []
    quote = indicators.get("quote")
    if not isinstance(quote, list) or not quote or not isinstance(quote[0], dict):
        return []
    closes = quote[0].get("close")
    if not isinstance(closes, list):
        return []

    import json

    raw_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]

    pairs: list[tuple[date, float]] = []
    for ts_raw, close in zip(timestamps, closes, strict=False):
        if close is None:
            continue
        try:
            ts_i = int(ts_raw)
            value = float(close)
        except (TypeError, ValueError):
            continue
        if not (value > 0):
            continue
        d = datetime.fromtimestamp(ts_i, tz=UTC).date()
        pairs.append((d, value))
    pairs.sort(key=lambda x: x[0])
    if max_points > 0:
        pairs = pairs[-max_points:]
    out: list[dict[str, Any]] = []
    for d, value in pairs:
        ts = datetime(d.year, d.month, d.day, 12, 0, tzinfo=UTC)
        out.append(
            {
                "source": "yahoo_world",
                "series_id": series_id,
                "ts": ts,
                "value": value,
                "unit": unit,
                "as_of_date": d,
                "attribution": attribution,
                "raw_hash": raw_hash,
            }
        )
    return out


async def fetch_world_index_rows(
    *,
    client: httpx.AsyncClient | None = None,
    max_points: int = 90,
) -> list[dict[str, Any]]:
    """Fetch all configured world tiles. Fail-soft per series."""
    own = client is None
    http = client or httpx.AsyncClient(timeout=45.0, follow_redirects=True)
    headers = {
        "User-Agent": "koel-macro/0.1 (+https://github.com/ArdenoStudio/Koel)",
        "Accept": "application/json,text/csv,*/*",
    }
    out: list[dict[str, Any]] = []
    try:
        for spec in _WORLD_SERIES:
            series_id = spec["series_id"]
            attribution = spec["attribution"]
            unit = spec["unit"]
            try:
                if spec["provider"] == "fred":
                    url = _FRED_CSV.format(series_id=spec["fred_id"])
                    resp = await http.get(url, headers=headers)
                    resp.raise_for_status()
                    rows = parse_fred_csv(
                        resp.text,
                        series_id=series_id,
                        attribution=attribution,
                        unit=unit,
                        max_points=max_points,
                    )
                else:
                    sym = quote(spec["yahoo_symbol"], safe="")
                    url = _YAHOO_CHART.format(symbol=sym)
                    resp = await http.get(url, headers=headers)
                    resp.raise_for_status()
                    payload = resp.json()
                    if not isinstance(payload, dict):
                        rows = []
                    else:
                        rows = parse_yahoo_chart(
                            payload,
                            series_id=series_id,
                            attribution=attribution,
                            unit=unit,
                            max_points=max_points,
                        )
                log.info(
                    "world_index: %s → %s points",
                    series_id,
                    len(rows),
                )
                out.extend(rows)
            except Exception:
                log.exception("world_index: %s failed", series_id)
        return out
    finally:
        if own:
            await http.aclose()
