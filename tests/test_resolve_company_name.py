"""Company-name → symbol resolution collapses CSE double spaces."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from koel.storage import Storage


class _FakeCM:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    async def __aenter__(self) -> Any:
        return self._conn

    async def __aexit__(self, *args: object) -> None:
        return None


class _FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    async def fetchall(self) -> list[dict[str, Any]]:
        return self._rows


class _FakeConn:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.last_params: tuple[Any, ...] | None = None

    async def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> _FakeResult:
        self.last_params = params
        return _FakeResult(self._rows)


@pytest.mark.asyncio
async def test_resolve_collapses_whitespace() -> None:
    storage = Storage.__new__(Storage)
    conn = _FakeConn([{"symbol": "MADU.N0000"}])
    storage._pool = MagicMock()
    storage._pool.connection = MagicMock(return_value=_FakeCM(conn))

    sym = await storage.resolve_symbol_by_company_name("MADULSIMA  PLANTATIONS  PLC")
    assert sym == "MADU.N0000"
    assert conn.last_params == ("MADULSIMA PLANTATIONS PLC",)


@pytest.mark.asyncio
async def test_resolve_skips_market_surveillance() -> None:
    storage = Storage.__new__(Storage)
    storage._pool = MagicMock()
    assert (
        await storage.resolve_symbol_by_company_name(
            "TRADING AND MARKET SURVEILLANCE"
        )
        is None
    )


@pytest.mark.asyncio
async def test_resolve_ambiguous_returns_none() -> None:
    storage = Storage.__new__(Storage)
    conn = _FakeConn([{"symbol": "A.N0000"}, {"symbol": "B.N0000"}])
    storage._pool = MagicMock()
    storage._pool.connection = MagicMock(return_value=_FakeCM(conn))
    assert await storage.resolve_symbol_by_company_name("DUP PLC") is None
