"""Unit tests for macro storage helpers + macro_tick orchestration."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from koel.adapters.macro_cbsl import _mid
from koel.adapters.macro_eia import _parse_bulk_series_line, _parse_eia_payload
from koel.adapters.macro_world import parse_fred_csv, parse_yahoo_chart
from koel.macro_ingest import run_macro_tick
from koel.storage import Storage


class _Cursor:
    def __init__(self, *, one: Any = None, many: list[Any] | None = None) -> None:
        self._one = one
        self._many = many or []

    async def fetchone(self) -> Any:
        return self._one

    async def fetchall(self) -> list[Any]:
        return list(self._many)


class _Conn:
    def __init__(self, results: list[Any] | None = None) -> None:
        self._results = list(results or [])
        self.sql: list[str] = []

    async def execute(self, sql: str, params: Any = None) -> _Cursor:
        self.sql.append(sql)
        if not self._results:
            return _Cursor()
        nxt = self._results.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        if isinstance(nxt, list):
            return _Cursor(many=nxt)
        return _Cursor(one=nxt)


class _Pool:
    def __init__(self, conn: _Conn) -> None:
        self._conn = conn

    @asynccontextmanager
    async def connection(self) -> Any:
        yield self._conn


def _store(conn: _Conn) -> Storage:
    store = Storage("postgresql://unused", min_size=1, max_size=2)
    store._pool = _Pool(conn)  # type: ignore[assignment]
    return store


def test_mid_rejects_bad_inputs() -> None:
    assert _mid(300, 310) == 305.0
    assert _mid("x", 310) is None
    assert _mid(0, 310) is None
    assert _mid(-1, 310) is None


def test_parse_eia_bulk_line_yyyyymmdd() -> None:
    line = (
        b'{"series_id":"PET.RBRTE.D","data":[["20260713",81.62],'
        b'["20260710",74.34],["bad",1],["20260701",0]]}'
    )
    rows = _parse_bulk_series_line(
        line,
        wanted={"PET.RBRTE.D": "BRENT_SPOT"},
        length=10,
    )
    assert len(rows) == 2
    assert rows[0]["series_id"] == "BRENT_SPOT"
    assert rows[0]["as_of_date"].isoformat() == "2026-07-10"
    assert rows[-1]["as_of_date"].isoformat() == "2026-07-13"
    assert rows[-1]["value"] == 81.62
    assert "demo" not in rows[-1]["attribution"].lower()


def test_parse_eia_payload_mids() -> None:
    payload = {
        "response": {
            "data": [
                {"period": "2026-07-18", "value": "80.5"},
                {"period": "2026-07-19", "value": 81.0},
                {"period": "bad", "value": 82},
                {"period": "2026-07-20", "value": "nope"},
                {"period": "2026-07-21", "value": 0},
                "skip-me",
            ]
        }
    }
    rows = _parse_eia_payload(payload, series_id="BRENT_SPOT")
    assert len(rows) == 2
    assert rows[0]["as_of_date"] == date(2026, 7, 18)
    assert rows[1]["value"] == 81.0
    assert rows[1]["series_id"] == "BRENT_SPOT"
    assert "EIA" in rows[1]["attribution"]


def test_parse_eia_payload_empty_shapes() -> None:
    assert _parse_eia_payload({"response": {"data": "x"}}, series_id="WTI_SPOT") == []
    assert _parse_eia_payload({}, series_id="WTI_SPOT") == []


@pytest.mark.asyncio
async def test_upsert_macro_series_skips_invalid() -> None:
    conn = _Conn([None, None])
    store = _store(conn)
    n = await store.upsert_macro_series(
        [
            {"source": "eia_oil"},  # missing fields
            {
                "source": "eia_oil",
                "series_id": "BRENT_SPOT",
                "ts": datetime(2026, 7, 19, 12, 0, tzinfo=UTC),
                "value": 81.0,
                "unit": "USD/bbl",
                "as_of_date": date(2026, 7, 19),
                "attribution": "EIA",
                "raw_hash": "abc",
            },
            "not-a-dict",  # type: ignore[list-item]
        ]
    )
    assert n == 1
    assert len(conn.sql) == 1


@pytest.mark.asyncio
async def test_upsert_macro_series_empty() -> None:
    assert await _store(_Conn([])).upsert_macro_series([]) == 0


@pytest.mark.asyncio
async def test_latest_macro_change_pct() -> None:
    conn = _Conn(
        [
            [
                {"value": 310.0, "as_of_date": date(2026, 7, 19), "ts": None},
                {"value": 300.0, "as_of_date": date(2026, 7, 18), "ts": None},
            ]
        ]
    )
    pct = await _store(conn).latest_macro_change_pct("USD_LKR")
    assert pct is not None
    assert abs(pct - ((310 / 300) - 1) * 100) < 1e-9
    assert await _store(_Conn([[]])).latest_macro_change_pct("USD_LKR") is None
    assert await _store(_Conn([])).latest_macro_change_pct("  ") is None


@pytest.mark.asyncio
async def test_market_book_imbalance_pct() -> None:
    conn = _Conn(
        [
            [
                {"total_bids": 120.0, "total_asks": 80.0},
                {"total_bids": 0, "total_asks": 50},
                {"total_bids": True, "total_asks": 1},
            ]
        ]
    )
    pct = await _store(conn).market_book_imbalance_pct()
    assert pct is not None
    assert abs(pct - 20.0) < 1e-9
    assert await _store(_Conn([[]])).market_book_imbalance_pct() is None


@pytest.mark.asyncio
async def test_market_regime_fired_keys() -> None:
    conn = _Conn(
        [
            [
                {"event_key": "appetite_band:1:2026-07-19"},
                {"event_key": "  "},
                {"event_key": None},
            ]
        ]
    )
    keys = await _store(conn).market_regime_fired_keys()
    assert keys == {"appetite_band:1:2026-07-19"}


@pytest.mark.asyncio
async def test_run_macro_tick_disabled() -> None:
    storage = MagicMock()
    settings = MagicMock()
    settings.cbsl_fx_enabled = False
    settings.eia_oil_enabled = False
    settings.world_index_research_enabled = False
    settings.sltda_tourism_enabled = False
    settings.dcs_food_enabled = False
    result = await run_macro_tick(storage, settings)
    assert result["cbsl_fx"] == 0
    assert result["eia_oil"] == 0
    assert result["world_indexes"] == 0
    assert "cbsl_fx_disabled" in result["skipped"]
    assert "eia_oil_disabled" in result["skipped"]
    assert "world_indexes_disabled" in result["skipped"]
    storage.upsert_macro_series.assert_not_called()


@pytest.mark.asyncio
async def test_run_macro_tick_force_upserts() -> None:
    storage = MagicMock()
    storage.upsert_macro_series = AsyncMock(side_effect=[3, 2, 5])
    settings = MagicMock()
    settings.cbsl_fx_enabled = False
    settings.eia_oil_enabled = False
    settings.world_index_research_enabled = False
    settings.sltda_tourism_enabled = True
    settings.dcs_food_enabled = True
    with (
        patch(
            "koel.macro_ingest.fetch_cbsl_fx_rows",
            new=AsyncMock(return_value=[{"series_id": "USD_LKR"}]),
        ),
        patch(
            "koel.macro_ingest.fetch_eia_oil_rows",
            new=AsyncMock(return_value=[{"series_id": "BRENT_SPOT"}]),
        ),
        patch(
            "koel.macro_ingest.fetch_world_index_rows",
            new=AsyncMock(return_value=[{"series_id": "WORLD_SPX"}]),
        ),
    ):
        result = await run_macro_tick(storage, settings, force=True)
    assert result["cbsl_fx"] == 3
    assert result["eia_oil"] == 2
    assert result["world_indexes"] == 5
    assert result["skipped"] == []


def test_parse_fred_csv_skips_dots() -> None:
    text = "DATE,SP500\n2026-07-15,7572.40\n2026-07-16,.\n2026-07-17,7457.69\n"
    rows = parse_fred_csv(
        text,
        series_id="WORLD_SPX",
        attribution="FRED SP500 — research / delayed, not CSE official",
        max_points=10,
    )
    assert len(rows) == 2
    assert rows[-1]["value"] == 7457.69
    assert rows[-1]["as_of_date"].isoformat() == "2026-07-17"


def test_parse_yahoo_chart_closes() -> None:
    from datetime import UTC, datetime

    day = int(datetime(2026, 7, 17, 12, tzinfo=UTC).timestamp())
    prev = int(datetime(2026, 7, 16, 12, tzinfo=UTC).timestamp())
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [prev, day],
                    "indicators": {"quote": [{"close": [100.0, 105.5]}]},
                }
            ]
        }
    }
    rows = parse_yahoo_chart(
        payload,
        series_id="WORLD_FTSE",
        attribution="Yahoo ^FTSE — research / delayed, not CSE official",
    )
    assert len(rows) == 2
    assert rows[-1]["value"] == 105.5
    assert "research" in rows[-1]["attribution"].lower()
