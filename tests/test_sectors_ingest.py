"""Optional SECTORS_INGEST path: POST /allSectors → sectors table."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from koel.adapters.cse import CSEClient, SectorRow, sector_row_to_snapshot
from koel.config import Settings
from koel.domain import SectorSnapshot
from koel.poller import Poller


def _settings(*, sectors_ingest: bool = False) -> Settings:
    return Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
        sectors_ingest=sectors_ingest,
    )


def test_sectors_ingest_env_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("DATABASE_URL", "postgresql://koel:koel@localhost:5432/koel")
    monkeypatch.delenv("SECTORS_INGEST", raising=False)
    assert Settings.from_env().sectors_ingest is False
    monkeypatch.setenv("SECTORS_INGEST", "1")
    assert Settings.from_env().sectors_ingest is True
    monkeypatch.setenv("SECTORS_INGEST", "0")
    assert Settings.from_env().sectors_ingest is False


def test_sector_row_to_snapshot_maps_sample_fields() -> None:
    row = SectorRow(
        id=104331,
        sectorId=223,
        symbol="egy",
        indexCode="1010",
        indexCodeSp="SPCSEEIP",
        indexName="S&P/CSE Energy Industry Group Index",
        name="Energy",
        indexValue=2951.6,
        change=-67.62,
        percentage=-2.2396513006670595,
        sectorTradeToday=302.0,
        sectorVolumeToday=74378,
        sectorTurnoverToday=9844386.05,
        sectorPreviousClose=3019.22,
        transactionTime=1_720_000_000_000,
    )
    snap = sector_row_to_snapshot(row)
    assert snap is not None
    assert snap.sector_id == 223
    assert snap.symbol == "EGY"
    assert snap.name == "Energy"
    assert snap.index_value == 2951.6
    assert snap.change_pct == pytest.approx(-2.2396513006670595)
    assert snap.volume_today == 74378
    assert snap.cse_row_id == 104331
    assert snap.ts == datetime.fromtimestamp(1_720_000_000_000 / 1000.0, tz=UTC)


@pytest.mark.asyncio
async def test_fetch_all_sectors_parses_array_and_skips_junk() -> None:
    client = CSEClient(client=AsyncMock())
    client._request = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            {
                "id": 1,
                "sectorId": 223,
                "symbol": "EGY",
                "name": "Energy",
                "indexValue": 100.0,
                "change": 1.0,
                "percentage": 1.0,
                "transactionTime": 1_720_000_000_000,
            },
            {"_note": "Truncated; full list has 22 sectors"},
            {"sectorId": 224, "symbol": "  ", "name": "Materials"},
        ]
    )

    out = await client.fetch_all_sectors()
    assert len(out) == 1
    assert out[0].symbol == "EGY"
    assert out[0].sector_id == 223
    client._request.assert_awaited_once()
    assert client._request.await_args.args[:2] == ("POST", "/allSectors")


@pytest.mark.asyncio
async def test_poll_sectors_skipped_when_flag_off() -> None:
    cse = AsyncMock()
    cse.fetch_all_sectors = AsyncMock()
    storage = AsyncMock()
    storage.persist_sectors = AsyncMock()
    poller = Poller(_settings(sectors_ingest=False), storage, cse, AsyncMock())

    await poller._poll_sectors()

    cse.fetch_all_sectors.assert_not_awaited()
    storage.persist_sectors.assert_not_awaited()


@pytest.mark.asyncio
async def test_poll_sectors_persists_when_enabled() -> None:
    board = [
        SectorSnapshot(
            sector_id=223,
            symbol="EGY",
            name="Energy",
            index_value=2951.6,
            ts=datetime.now(UTC),
        )
    ]
    cse = AsyncMock()
    cse.fetch_all_sectors = AsyncMock(return_value=board)
    storage = AsyncMock()
    storage.persist_sectors = AsyncMock(return_value=board)
    poller = Poller(_settings(sectors_ingest=True), storage, cse, AsyncMock())

    await poller._poll_sectors()

    cse.fetch_all_sectors.assert_awaited_once()
    storage.persist_sectors.assert_awaited_once_with(board)


@pytest.mark.asyncio
async def test_poll_sectors_fail_soft_on_fetch_error() -> None:
    cse = AsyncMock()
    cse.fetch_all_sectors = AsyncMock(side_effect=RuntimeError("boom"))
    storage = AsyncMock()
    storage.persist_sectors = AsyncMock()
    poller = Poller(_settings(sectors_ingest=True), storage, cse, AsyncMock())

    await poller._poll_sectors()

    storage.persist_sectors.assert_not_awaited()


@pytest.mark.asyncio
async def test_poll_sectors_fail_soft_on_persist_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    board = [
        SectorSnapshot(
            sector_id=223,
            symbol="EGY",
            name="Energy",
            ts=datetime.now(UTC),
        )
    ]
    cse = AsyncMock()
    cse.fetch_all_sectors = AsyncMock(return_value=board)
    storage = AsyncMock()
    storage.persist_sectors = AsyncMock(side_effect=RuntimeError("db down"))
    poller = Poller(_settings(sectors_ingest=True), storage, cse, AsyncMock())

    await poller._poll_sectors()  # must not raise

    storage.persist_sectors.assert_awaited_once()
    assert "sectors_persist_failed" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_poll_sectors_logs_ok_on_success() -> None:
    board = [
        SectorSnapshot(
            sector_id=223,
            symbol="EGY",
            name="Energy",
            ts=datetime.now(UTC),
        )
    ]
    cse = AsyncMock()
    cse.fetch_all_sectors = AsyncMock(return_value=board)
    storage = AsyncMock()
    storage.persist_sectors = AsyncMock(return_value=board)
    poller = Poller(_settings(sectors_ingest=True), storage, cse, AsyncMock())

    await poller._poll_sectors()

    storage.persist_sectors.assert_awaited_once_with(board)


@pytest.mark.asyncio
async def test_poll_sectors_fail_soft_on_fetch_logs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cse = AsyncMock()
    cse.fetch_all_sectors = AsyncMock(side_effect=RuntimeError("boom"))
    storage = AsyncMock()
    storage.persist_sectors = AsyncMock()
    poller = Poller(_settings(sectors_ingest=True), storage, cse, AsyncMock())

    await poller._poll_sectors()

    assert "sectors_poll_failed" in capsys.readouterr().out
    storage.persist_sectors.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_once_invokes_sectors_ingest_when_enabled() -> None:
    """Tick path wires _poll_sectors after price/disclosure polls."""
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=[])
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    storage.persist_market_snapshots = AsyncMock(return_value=[])
    storage.claim_unsent_batch = AsyncMock(return_value=[])
    storage.persist_sectors = AsyncMock(return_value=[])

    board = [
        SectorSnapshot(
            sector_id=223,
            symbol="EGY",
            name="Energy",
            ts=datetime.now(UTC),
        )
    ]
    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(return_value=[])
    cse.fetch_all_sectors = AsyncMock(return_value=board)

    poller = Poller(_settings(sectors_ingest=True), storage, cse, AsyncMock(return_value=True))
    await poller.run_once(force=True)

    cse.fetch_all_sectors.assert_awaited_once()
    storage.persist_sectors.assert_awaited_once_with(board)


@pytest.mark.asyncio
async def test_fetch_all_sectors_rejects_non_array() -> None:
    client = CSEClient(client=AsyncMock())
    client._request = AsyncMock(return_value={"sectors": []})  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="expected JSON array"):
        await client.fetch_all_sectors()


@pytest.mark.asyncio
async def test_fetch_all_sectors_empty_array_ok() -> None:
    client = CSEClient(client=AsyncMock())
    client._request = AsyncMock(return_value=[])  # type: ignore[method-assign]

    out = await client.fetch_all_sectors()
    assert out == []


def test_sector_row_to_snapshot_uses_now_when_no_transaction_time() -> None:
    now = datetime(2026, 7, 12, 10, 0, tzinfo=UTC)
    row = SectorRow(
        sectorId=1,
        symbol="egy",
        name="Energy",
        indexValue=10.0,
        transactionTime=None,
    )
    snap = sector_row_to_snapshot(row, now=now)
    assert snap is not None
    assert snap.ts == now
    assert snap.symbol == "EGY"
