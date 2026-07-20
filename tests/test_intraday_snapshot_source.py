"""Intraday chart ticks must not poison alert previous_snapshot."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from koel.adapters.cse import ChartPointRow, chart_point_to_intraday_snapshot
from koel.domain import PriceSnapshot
from koel.migrate import apply_migrations
from koel.storage import Storage

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set"),
]


@pytest.fixture
async def storage() -> Storage:
    assert DATABASE_URL
    apply_migrations(DATABASE_URL)
    store = Storage(DATABASE_URL, min_size=1, max_size=2)
    await store.open()
    yield store
    await store.close()


@pytest.mark.asyncio
async def test_previous_snapshot_skips_cse_intraday(storage: Storage) -> None:
    await storage.upsert_stock("TSRC.N0000", name="Source Test")
    t0 = datetime(2026, 7, 17, 4, 0, tzinfo=UTC)
    t1 = datetime(2026, 7, 17, 4, 5, tzinfo=UTC)
    t2 = datetime(2026, 7, 17, 4, 10, tzinfo=UTC)

    poller = await storage.persist_market_snapshots(
        [PriceSnapshot(symbol="TSRC.N0000", price=10.0, ts=t0)]
    )
    assert len(poller) == 1

    n = await storage.persist_intraday_snapshots(
        [
            PriceSnapshot(symbol="TSRC.N0000", price=99.0, ts=t1),
            PriceSnapshot(symbol="TSRC.N0000", price=100.0, ts=t2),
        ]
    )
    assert n == 2

    later = await storage.persist_market_snapshots(
        [
            PriceSnapshot(
                symbol="TSRC.N0000",
                price=11.0,
                ts=datetime(2026, 7, 17, 5, 0, tzinfo=UTC),
            )
        ]
    )
    assert later[0].id is not None
    prev = await storage.previous_snapshot("TSRC.N0000", before_id=later[0].id)
    assert prev is not None
    assert prev.price == 10.0


def test_intraday_snapshot_rejects_non_positive() -> None:
    row = ChartPointRow(p=0.0, t=1_784_278_690_833)
    assert chart_point_to_intraday_snapshot(row, symbol="X.N0000") is None
