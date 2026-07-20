"""WS-010/099: advisory lock acquire/unlock must not leak pool connections."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from koel.storage import Storage


class _FakeConn:
    def __init__(self, *, execute_side_effect: Any = None) -> None:
        self.execute = AsyncMock(side_effect=execute_side_effect)
        self._aexit = AsyncMock(return_value=None)


class _FakeCM:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> _FakeConn:
        self.entered = True
        return self._conn

    async def __aexit__(self, *args: object) -> None:
        self.exited = True
        await self._conn._aexit(*args)


@pytest.mark.asyncio
async def test_try_advisory_lock_releases_cm_when_execute_fails() -> None:
    storage = Storage("postgresql://unused", min_size=1, max_size=2)
    conn = _FakeConn(execute_side_effect=RuntimeError("db blip"))
    cm = _FakeCM(conn)
    storage._pool = MagicMock()
    storage._pool.connection = MagicMock(return_value=cm)

    with pytest.raises(RuntimeError, match="db blip"):
        await storage.try_advisory_lock(42)

    assert cm.exited is True
    assert storage._lock_cm is None
    assert storage._lock_conn is None
    assert storage._lock_id is None


@pytest.mark.asyncio
async def test_advisory_unlock_clears_state_when_unlock_execute_fails() -> None:
    storage = Storage("postgresql://unused", min_size=1, max_size=2)
    conn = _FakeConn(execute_side_effect=RuntimeError("unlock failed"))
    cm = _FakeCM(conn)
    storage._lock_cm = cm
    storage._lock_conn = conn
    storage._lock_id = 99

    with pytest.raises(RuntimeError, match="unlock failed"):
        await storage.advisory_unlock(99)

    assert cm.exited is True
    assert storage._lock_cm is None
    assert storage._lock_conn is None
    assert storage._lock_id is None


@pytest.mark.asyncio
async def test_advisory_unlock_clears_state_when_aexit_fails() -> None:
    storage = Storage("postgresql://unused", min_size=1, max_size=2)

    class _BadCM(_FakeCM):
        async def __aexit__(self, *args: object) -> None:
            self.exited = True
            raise RuntimeError("aexit failed")

    conn = _FakeConn()
    # Successful unlock execute, then __aexit__ blows up.
    row = MagicMock()
    conn.execute = AsyncMock(return_value=row)
    cm = _BadCM(conn)
    storage._lock_cm = cm
    storage._lock_conn = conn
    storage._lock_id = 7

    with pytest.raises(RuntimeError, match="aexit failed"):
        await storage.advisory_unlock(7)

    assert storage._lock_cm is None
    assert storage._lock_conn is None
    assert storage._lock_id is None
