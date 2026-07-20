"""E3-Q02: dual pollers draining claim_unsent_batch never double-send."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from koel.config import Settings
from koel.notify import SendResult
from koel.poller import Poller


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )


@pytest.mark.asyncio
async def test_dual_poller_claim_unsent_no_double_send() -> None:
    """Two concurrent run_once drains: each alert_log id sent at most once.

    Simulates FOR UPDATE SKIP LOCKED by partitioning rows under a lock so each
    claimer gets a disjoint subset (same contract as claim_unsent_batch).
    """
    rows = [
        {
            "id": 701,
            "rule_id": 10,
            "telegram_id": 1001,
            "message_text": "msg-a",
            "attempt_count": 0,
        },
        {
            "id": 702,
            "rule_id": 11,
            "telegram_id": 1002,
            "message_text": "msg-b",
            "attempt_count": 0,
        },
    ]
    claimed: set[int] = set()
    claim_lock = asyncio.Lock()

    async def claim_unsent_batch(
        *, limit: int = 50, lease_seconds: int = 120
    ) -> list[dict[str, object]]:
        async with claim_lock:
            out: list[dict[str, object]] = []
            for row in rows:
                rid = int(row["id"])
                if rid in claimed:
                    continue
                claimed.add(rid)
                out.append(row)
                if len(out) >= max(1, limit):
                    break
            return out[:limit]

    sends: list[tuple[int, str]] = []
    send_lock = asyncio.Lock()

    async def send(chat_id: int, text: str) -> SendResult:
        async with send_lock:
            sends.append((chat_id, text))
        return SendResult.OK

    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=[])
    storage.active_rules_for_symbols = AsyncMock(return_value=[])
    storage.claim_unsent_batch = AsyncMock(side_effect=claim_unsent_batch)
    storage.mark_alert_sent = AsyncMock()
    storage.mark_delivery_attempted_ok = AsyncMock()

    cse = AsyncMock()
    settings = _settings()
    poller_a = Poller(settings, storage, cse, send)
    poller_b = Poller(settings, storage, cse, send)

    await asyncio.gather(poller_a.run_once(force=True), poller_b.run_once(force=True))

    texts = sorted(t for _, t in sends)
    assert texts == ["msg-a", "msg-b"]
    assert len(sends) == 2
    marked = sorted(call.args[0] for call in storage.mark_alert_sent.await_args_list)
    assert marked == [701, 702]


@pytest.mark.asyncio
async def test_dual_retry_unsent_skip_locked_claims_disjoint_rows() -> None:
    """E16-Q01: dual unsent drains model SKIP LOCKED with no duplicate rows."""
    rows = [
        {
            "id": 801,
            "rule_id": 21,
            "telegram_id": 2001,
            "message_text": "retry-a",
            "attempt_count": 0,
        },
        {
            "id": 802,
            "rule_id": 22,
            "telegram_id": 2002,
            "message_text": "retry-b",
            "attempt_count": 0,
        },
        {
            "id": 803,
            "rule_id": 23,
            "telegram_id": 2003,
            "message_text": "retry-c",
            "attempt_count": 0,
        },
    ]
    claimed: set[int] = set()
    claim_lock = asyncio.Lock()

    async def claim_unsent_batch(
        *, limit: int = 50, lease_seconds: int = 120
    ) -> list[dict[str, object]]:
        async with claim_lock:
            assert limit == 1
            for row in rows:
                log_id = int(row["id"])
                if log_id not in claimed:
                    claimed.add(log_id)
                    return [row]
            return []

    sends: list[tuple[int, str]] = []

    async def send(chat_id: int, text: str) -> SendResult:
        sends.append((chat_id, text))
        return SendResult.OK

    storage = AsyncMock()
    storage.claim_unsent_batch = AsyncMock(side_effect=claim_unsent_batch)
    storage.mark_alert_sent = AsyncMock()
    storage.mark_delivery_attempted_ok = AsyncMock()

    poller_a = Poller(_settings(), storage, AsyncMock(), send)
    poller_b = Poller(_settings(), storage, AsyncMock(), send)

    await asyncio.gather(poller_a._retry_unsent(), poller_b._retry_unsent())

    assert sorted(text for _, text in sends) == ["retry-a", "retry-b", "retry-c"]
    assert len(sends) == 3
    assert sorted(claimed) == [801, 802, 803]
    marked = sorted(call.args[0] for call in storage.mark_alert_sent.await_args_list)
    assert marked == [801, 802, 803]
