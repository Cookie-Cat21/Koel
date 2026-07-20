"""Wave9: unit coverage for storage brief / follow-up methods (mock pool)."""

from __future__ import annotations

import pytest

from tests.test_storage_unit import _Conn, _store


@pytest.mark.asyncio
async def test_claim_brief_followups_sql_and_params() -> None:
    conn = _Conn(
        [
            [
                {
                    "id": 88,
                    "rule_id": 9,
                    "message_text": "follow-up body",
                    "telegram_id": 1001,
                }
            ]
        ]
    )
    store = _store(conn)
    rows = await store.claim_brief_followups(
        external_id=" 99 ",
        symbol="jkh.n0000",
        brief="  AGM set for August.  ",
        message_text="follow-up body",
        lease_seconds=90,
    )
    assert len(rows) == 1
    assert rows[0]["telegram_id"] == 1001
    sql = conn.sql[0]
    assert "'brief_followup:' || p.rule_id::text || ':' || %s" in sql
    assert "al.event_key = 'disclosure:' || ar.id::text || ':' || %s" in sql
    assert "ON CONFLICT (rule_id, event_key) DO NOTHING" in sql
    assert "message_sent OR al.delivery_attempted_ok" in sql
    assert "chr(10) || chr(10) || %s || chr(10) || chr(10)" in sql
    assert "delivery_lease_until" in sql
    # Strip + upper symbol; brief trimmed; lease is last param.
    assert conn.params[0] == (
        "99",
        "JKH.N0000",
        "AGM set for August.",
        "99",
        "follow-up body",
        90,
    )


@pytest.mark.asyncio
async def test_claim_brief_followups_noop_on_incomplete_inputs() -> None:
    store = _store(_Conn([[{"id": 1}]]))
    assert (
        await store.claim_brief_followups(
            external_id="",
            symbol="JKH.N0000",
            brief="x",
            message_text="y",
        )
        == []
    )
    assert (
        await store.claim_brief_followups(
            external_id="99",
            symbol="  ",
            brief="x",
            message_text="y",
        )
        == []
    )
    assert (
        await store.claim_brief_followups(
            external_id="99",
            symbol="JKH.N0000",
            brief="   ",
            message_text="y",
        )
        == []
    )
    assert (
        await store.claim_brief_followups(
            external_id="99",
            symbol="JKH.N0000",
            brief="x",
            message_text="  \n\t  ",
        )
        == []
    )
    # No SQL when guards trip.
    conn = _Conn([[{"id": 1}]])
    store2 = _store(conn)
    await store2.claim_brief_followups(
        external_id="",
        symbol="",
        brief="",
        message_text="",
    )
    assert conn.sql == []


@pytest.mark.asyncio
async def test_list_ready_briefs_for_followup_sweep_sql() -> None:
    conn = _Conn(
        [
            [
                {
                    "disclosure_id": 7,
                    "brief": "Board met.",
                    "external_id": "99",
                    "symbol": "JKH.N0000",
                    "title": "AGM",
                    "url": "https://www.cse.lk/announcements#99",
                }
            ]
        ]
    )
    store = _store(conn)
    rows = await store.list_ready_briefs_for_followup_sweep(limit=10, max_age_days=3)
    assert len(rows) == 1
    assert rows[0]["disclosure_id"] == 7
    sql = conn.sql[0]
    assert "status = 'ready'" in sql
    assert "brief_followup:" in sql
    assert "NOT EXISTS" in sql
    assert "message_sent OR al.delivery_attempted_ok" in sql
    assert "ORDER BY b.updated_at ASC" in sql
    assert conn.params[0] == (3, 10)


@pytest.mark.asyncio
async def test_list_ready_briefs_for_followup_sweep_noop_and_clamps_age() -> None:
    conn = _Conn([])
    store = _store(conn)
    assert await store.list_ready_briefs_for_followup_sweep(limit=0) == []
    assert await store.list_ready_briefs_for_followup_sweep(limit=-1) == []
    assert conn.sql == []

    conn2 = _Conn([[]])
    store2 = _store(conn2)
    await store2.list_ready_briefs_for_followup_sweep(limit=5, max_age_days=0)
    # max_age_days floored to 1.
    assert conn2.params[0] == (1, 5)


@pytest.mark.asyncio
async def test_claim_pending_briefs_without_daily_cap() -> None:
    """max_briefs_per_day=None skips advisory lock + cap count."""
    conn = _Conn(
        [
            [
                {
                    "disclosure_id": 1,
                    "external_id": "42",
                    "symbol": "JKH.N0000",
                    "title": "Filing",
                    "url": "https://www.cse.lk/announcements#42",
                    "pdf_url": "https://cdn.cse.lk/x.pdf",
                }
            ]
        ]
    )
    store = _store(conn)
    rows = await store.claim_pending_briefs(limit=2, max_briefs_per_day=None)
    assert len(rows) == 1
    assert rows[0]["disclosure_id"] == 1
    assert not any("pg_advisory_xact_lock" in s for s in conn.sql)
    assert not any("COUNT(*)" in s for s in conn.sql)
    claim_sql = conn.sql[0]
    assert "FOR UPDATE OF b SKIP LOCKED" in claim_sql
    assert "status = 'processing'" in claim_sql
    # stale minutes, pdf grace (120), CDN backoff (300), batch=limit
    assert conn.params[0] == (15, 120, 300, 2)


@pytest.mark.asyncio
async def test_claim_pending_briefs_noop_when_limit_non_positive() -> None:
    conn = _Conn([[{"disclosure_id": 1}]])
    store = _store(conn)
    assert await store.claim_pending_briefs(limit=0) == []
    assert await store.claim_pending_briefs(limit=-3, max_briefs_per_day=10) == []
    assert conn.sql == []


@pytest.mark.asyncio
async def test_mark_brief_ready_and_failed_false_when_no_row() -> None:
    store = _store(_Conn([None]))
    assert (
        await store.mark_brief_ready(9, brief="ok", model="gemini-2.0-flash") is False
    )
    store2 = _store(_Conn([None]))
    assert await store2.mark_brief_failed(10, error="nope") is False


@pytest.mark.asyncio
async def test_mark_brief_failed_truncates_error_and_coalesces_model() -> None:
    conn = _Conn([{"disclosure_id": 10}])
    store = _store(conn)
    long_err = "e" * 2500
    assert await store.mark_brief_failed(10, error=long_err, model=None) is True
    sql = conn.sql[0]
    assert "status = 'failed'" in sql
    assert "COALESCE(%s, model)" in sql
    assert conn.params[0][0] == "e" * 2000
    assert conn.params[0][1] is None
    assert conn.params[0][2] == 10


@pytest.mark.asyncio
async def test_requeue_brief_pending_sql_and_truncate() -> None:
    conn = _Conn([{"disclosure_id": 42}])
    store = _store(conn)
    long_err = "cdn" * 800
    assert await store.requeue_brief_pending(42, error=long_err) is True
    sql = conn.sql[0]
    assert "status = 'pending'" in sql
    assert "AND status IN ('pending', 'processing')" in sql
    assert conn.params[0][0] == long_err[:2000]
    assert conn.params[0][1] == 42

    store2 = _store(_Conn([None]))
    assert await store2.requeue_brief_pending(99, error="miss") is False


@pytest.mark.asyncio
async def test_mark_brief_ready_passes_token_counts() -> None:
    conn = _Conn([{"disclosure_id": 3}])
    store = _store(conn)
    assert (
        await store.mark_brief_ready(
            3,
            brief="ok",
            model="llama-3.3-70b-versatile",
            tokens_in=11,
            tokens_out=22,
        )
        is True
    )
    assert conn.params[0] == ("ok", "llama-3.3-70b-versatile", 11, 22, 3)


@pytest.mark.asyncio
async def test_count_briefs_today_null_row_and_stale_param() -> None:
    assert await _store(_Conn([None])).count_briefs_today() == 0
    conn = _Conn([{"n": 4}])
    store = _store(conn)
    assert await store.count_briefs_today(stale_processing_minutes=30) == 4
    assert conn.params[0] == (30,)


@pytest.mark.asyncio
async def test_count_pending_disclosure_briefs() -> None:
    conn = _Conn([{"n": 7}])
    store = _store(conn)
    assert await store.count_pending_disclosure_briefs() == 7
    assert "status = 'pending'" in conn.sql[0]
    assert "disclosure_briefs" in conn.sql[0]

    assert await _store(_Conn([None])).count_pending_disclosure_briefs() == 0


@pytest.mark.asyncio
async def test_promote_recent_skipped_briefs_clamps_limit() -> None:
    conn = _Conn([[{"disclosure_id": 1}]])
    store = _store(conn)
    assert await store.promote_recent_skipped_briefs(max_age_hours=6, limit=0) == 1
    # limit floored to 1
    assert conn.params[0] == (6, 1)

def test_brief_cap_lock_distinct_from_poll_lock() -> None:
    """Wave10: poll session lock and brief xact lock must stay different keys."""
    from koel.poller import POLL_LOCK_ID
    from koel.storage import BRIEF_CAP_LOCK_ID

    assert POLL_LOCK_ID == 4_201_337
    assert BRIEF_CAP_LOCK_ID == 4_201_339
    assert POLL_LOCK_ID != BRIEF_CAP_LOCK_ID

