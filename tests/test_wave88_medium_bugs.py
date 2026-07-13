"""Wave88: medium+ bugs — brief daily-cap / lease soft-accepts.

1. ``claim_pending_briefs`` must reject bool ``count_briefs_today`` (no
   ``True==1`` arithmetic understating daily use → over-claim).
2. ``claim_pending_briefs`` must reject bool ``max_briefs_per_day`` on settings.
3. Storage ``claim_pending_briefs`` must reject bool ``max_briefs_per_day``.
4. Claim lease helpers must reject bool ``lease_seconds`` (no ``int(True)==1``
   shorten reclaim races) while still flooring via ``max(1, int(lease_seconds))``.
5. ``_promote_skipped_if_needed`` must reject bool ``skipped_promote_hours``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from chime.briefs import BriefSettings
from chime.briefs.worker import _promote_skipped_if_needed, claim_pending_briefs
from chime.domain import AlertEvent, AlertType
from chime.storage import Storage

ROOT = Path(__file__).resolve().parents[1]


def _enabled_settings(**kwargs: object) -> BriefSettings:
    base: dict[str, object] = dict(
        enabled=True,
        api_key="test-key",
        provider="gemini",
        model="gemini-2.0-flash",
        max_briefs_per_day=50,
        max_input_chars=12_000,
        pdf_grace_seconds=0,
        skipped_promote_hours=0,
        sleep_seconds=0,
        cdn_backoff_seconds=0,
        http_timeout_seconds=5.0,
        pdf_max_bytes=1_024,
    )
    base.update(kwargs)
    return BriefSettings(**base)  # type: ignore[arg-type]


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
        self.params: list[Any] = []

    async def execute(self, sql: str, params: Any = None) -> _Cursor:
        self.sql.append(sql)
        self.params.append(params)
        if not self._results:
            return _Cursor()
        nxt = self._results.pop(0)
        if isinstance(nxt, list):
            return _Cursor(many=nxt)
        return _Cursor(one=nxt)

    @asynccontextmanager
    async def transaction(self) -> Any:
        yield


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


def _event() -> AlertEvent:
    return AlertEvent(
        rule_id=1,
        user_id=3,
        telegram_id=1001,
        symbol="JKH.N0000",
        type=AlertType.PRICE_ABOVE,
        threshold=100.0,
        trigger="cross",
        current_price=101.0,
        event_key="w88:above:100",
        snapshot_id=5,
    )


@pytest.mark.asyncio
async def test_claim_pending_briefs_rejects_bool_used_and_cap() -> None:
    storage = MagicMock()
    storage.count_briefs_today = AsyncMock(return_value=True)
    storage.claim_pending_briefs = AsyncMock(return_value=[{"disclosure_id": 1}])
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=0)

    assert (
        await claim_pending_briefs(
            storage,
            settings=_enabled_settings(),
            limit=5,
        )
        == 0
    )
    storage.claim_pending_briefs.assert_not_awaited()

    storage.count_briefs_today = AsyncMock(return_value=0)
    assert (
        await claim_pending_briefs(
            storage,
            settings=_enabled_settings(max_briefs_per_day=True),
            limit=5,
        )
        == 0
    )
    storage.claim_pending_briefs.assert_not_awaited()

    src = (ROOT / "chime" / "briefs" / "worker.py").read_text(encoding="utf-8")
    impl = src.split("async def claim_pending_briefs(\n    storage:")[1]
    assert "brief_drain_used_poisoned" in impl
    assert "brief_drain_cap_poisoned" in impl
    assert "isinstance(used_raw, bool)" in impl
    assert "isinstance(cap, bool)" in impl
    assert "int(cfg.max_briefs_per_day)" not in impl


@pytest.mark.asyncio
async def test_storage_claim_pending_rejects_bool_cap() -> None:
    conn = _Conn(results=[{"n": 0}])
    store = _store(conn)
    assert await store.claim_pending_briefs(limit=3, max_briefs_per_day=True) == []
    assert conn.sql == []  # rejected before advisory lock / COUNT

    src = (ROOT / "chime" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("async def claim_pending_briefs(\n        self,")[1].split(
        "async def claim_brief_followups"
    )[0]
    assert "isinstance(max_briefs_per_day, bool)" in chunk
    assert "int(max_briefs_per_day)" not in chunk
    assert "isinstance(pdf_grace_seconds, int)" in chunk
    assert "isinstance(cdn_backoff_seconds, int)" in chunk


@pytest.mark.asyncio
async def test_claim_lease_rejects_bool_soft_accept() -> None:
    conn = _Conn(results=[{"id": 42}])
    store = _store(conn)
    log_id = await store.claim_alert(
        _event(),
        "ping",
        lease_seconds=True,  # type: ignore[arg-type]
    )
    assert log_id == 42
    assert conn.params[0][-1] == 120

    conn2 = _Conn(results=[{"id": 7}])
    store2 = _store(conn2)
    log_id2 = await store2.claim_and_disarm(
        _event(),
        "ping",
        lease_seconds=False,  # type: ignore[arg-type]
    )
    assert log_id2 == 7
    assert conn2.params[0][-1] == 120

    conn3 = _Conn(results=[[]])
    store3 = _store(conn3)
    assert (
        await store3.claim_unsent_batch(limit=1, lease_seconds=True)  # type: ignore[arg-type]
        == []
    )
    # leased UPDATE uses defaulted 120, not int(True)==1
    assert any(params and params[-1] == 120 for params in conn3.params)

    conn4 = _Conn(results=[[]])
    store4 = _store(conn4)
    assert (
        await store4.claim_brief_followups(
            external_id="ext-1",
            symbol="JKH.N0000",
            brief="brief body",
            message_text="follow-up body",
            lease_seconds=False,  # type: ignore[arg-type]
        )
        == []
    )
    assert any(params and 120 in params for params in conn4.params if params)

    for name in (
        "claim_alert",
        "claim_and_disarm",
        "claim_unsent_batch",
        "claim_brief_followups",
    ):
        src = __import__("inspect").getsource(getattr(Storage, name))
        assert "isinstance(lease_seconds, bool)" in src
        assert "max(1, int(lease_seconds))" in src


@pytest.mark.asyncio
async def test_promote_skipped_rejects_bool_hours() -> None:
    storage = MagicMock()
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=3)
    await _promote_skipped_if_needed(
        storage,
        cfg=_enabled_settings(skipped_promote_hours=True),
    )
    storage.promote_recent_skipped_briefs.assert_not_awaited()

    src = (ROOT / "chime" / "briefs" / "worker.py").read_text(encoding="utf-8")
    chunk = src.split("async def _promote_skipped_if_needed")[1].split(
        "async def _sweep_brief_followups"
    )[0]
    assert "isinstance(raw_hours, bool)" in chunk
    assert "int(cfg.skipped_promote_hours)" not in chunk
