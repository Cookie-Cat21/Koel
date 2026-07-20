"""Advisory lock must hold the same pooled connection until unlock."""

from __future__ import annotations

import os

import pytest

from koel.migrate import apply_migrations
from koel.storage import Storage

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set"),
]


@pytest.mark.asyncio
async def test_advisory_lock_blocks_second_holder() -> None:
    apply_migrations(DATABASE_URL)
    a = Storage(DATABASE_URL, min_size=1, max_size=2)
    b = Storage(DATABASE_URL, min_size=1, max_size=2)
    await a.open()
    await b.open()
    try:
        assert await a.try_advisory_lock(9_001_001) is True
        assert await b.try_advisory_lock(9_001_001) is False
        await a.advisory_unlock()
        assert await b.try_advisory_lock(9_001_001) is True
        await b.advisory_unlock()
    finally:
        await a.close()
        await b.close()
