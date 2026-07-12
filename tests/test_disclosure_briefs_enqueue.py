"""Idempotent disclosure_briefs enqueue (new disclosures only)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from chime.briefs import BriefSettings, BriefStatus
from chime.briefs.worker import enqueue_or_skip_brief
from chime.domain import Disclosure
from tests.test_storage_unit import _Conn, _store


def _disc(**kwargs: object) -> Disclosure:
    base = dict(
        external_id="ann-brief-1",
        symbol="JKH.N0000",
        title="Filing",
        url="https://www.cse.lk/a/1",
        published_at=datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
        seen_at=datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
        company_name="John Keells",
    )
    base.update(kwargs)
    return Disclosure(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_enqueue_disclosure_brief_inserts_pending() -> None:
    conn = _Conn([{"disclosure_id": 42}])
    store = _store(conn)
    assert await store.enqueue_disclosure_brief(42) is True
    assert "INSERT INTO disclosure_briefs" in conn.sql[0]
    assert conn.params[0] == (42, "pending")


@pytest.mark.asyncio
async def test_enqueue_disclosure_brief_idempotent_on_conflict() -> None:
    """Second enqueue for the same disclosure_id is a no-op (DO NOTHING)."""
    conn = _Conn([{"disclosure_id": 7}, None])
    store = _store(conn)
    assert await store.enqueue_disclosure_brief(7, status="pending") is True
    assert await store.enqueue_disclosure_brief(7, status="pending") is False
    assert len(conn.sql) == 2
    assert all("ON CONFLICT" in s and "DO NOTHING" in s for s in conn.sql)


@pytest.mark.asyncio
async def test_enqueue_disclosure_brief_accepts_skipped() -> None:
    conn = _Conn([{"disclosure_id": 9}])
    store = _store(conn)
    assert await store.enqueue_disclosure_brief(9, status="skipped") is True
    assert conn.params[0] == (9, "skipped")


@pytest.mark.asyncio
async def test_upsert_new_disclosure_enqueues_skipped_when_briefs_disabled() -> None:
    conn = _Conn([None, {"id": 11, "inserted": True}, None])
    store = _store(conn)
    with patch("chime.briefs.briefs_enabled", return_value=False):
        out = await store.upsert_disclosure(_disc())
    assert out.id == 11
    brief_sql = [s for s in conn.sql if "disclosure_briefs" in s]
    assert len(brief_sql) == 1
    assert conn.params[-1] == (11, "skipped")


@pytest.mark.asyncio
async def test_upsert_new_disclosure_enqueues_pending_when_briefs_enabled() -> None:
    conn = _Conn([None, {"id": 12, "inserted": True}, None])
    store = _store(conn)
    with patch("chime.briefs.briefs_enabled", return_value=True):
        out = await store.upsert_disclosure(_disc(external_id="ann-brief-2"))
    assert out.id == 12
    assert conn.params[-1] == (12, "pending")


@pytest.mark.asyncio
async def test_upsert_existing_disclosure_does_not_enqueue() -> None:
    conn = _Conn([None, {"id": 13, "inserted": False}])
    store = _store(conn)
    out = await store.upsert_disclosure(_disc(external_id="ann-brief-3"))
    assert out.id == 13
    assert not any("disclosure_briefs" in s for s in conn.sql)


@pytest.mark.asyncio
async def test_enqueue_or_skip_brief_persists_via_storage() -> None:
    conn = _Conn([{"disclosure_id": 5}, None])
    store = _store(conn)
    status = await enqueue_or_skip_brief(
        disclosure_id=5,
        settings=BriefSettings(enabled=False, api_key=""),
        storage=store,
    )
    assert status is BriefStatus.SKIPPED
    assert conn.params[0] == (5, "skipped")

    status2 = await enqueue_or_skip_brief(
        disclosure_id=5,
        settings=BriefSettings(enabled=True, api_key="k"),
        storage=store,
    )
    assert status2 is BriefStatus.PENDING
    # Idempotent: conflict → False, but status still pending decision
    assert conn.params[1] == (5, "pending")
