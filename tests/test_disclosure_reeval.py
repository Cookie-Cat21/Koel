"""H2: upsert_disclosure always returns id; poller re-evaluates existing rows."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from koel.config import Settings
from koel.domain import AlertType, Disclosure, PreviousPriceState, PriceSnapshot
from koel.poller import Poller
from koel.storage import Storage
from tests.conftest import make_disclosure, make_rule


class _FakeResult:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self._row = row

    async def fetchone(self) -> dict[str, Any] | None:
        return self._row


class _FakeConn:
    def __init__(self, ids: dict[tuple[str, str], int]) -> None:
        self._ids = ids
        self._next = max(ids.values(), default=0) + 1

    async def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> _FakeResult:
        assert params is not None
        # Briefs enqueue uses (disclosure_id, status) — ignore for this fake.
        if "disclosure_briefs" in sql:
            return _FakeResult(None)
        key = (str(params[0]), str(params[1]))
        is_new = key not in self._ids
        if is_new:
            self._ids[key] = self._next
            self._next += 1
        return _FakeResult({"id": self._ids[key], "inserted": is_new, "pdf_url": None})

    @asynccontextmanager
    async def transaction(self) -> Any:
        yield


class _FakeCM:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self._conn

    async def __aexit__(self, *args: object) -> None:
        return None


@pytest.mark.asyncio
async def test_upsert_disclosure_returns_same_id_on_conflict() -> None:
    """First upsert assigns id; second upsert for same external_id returns it."""
    storage = Storage("postgresql://unused", min_size=1, max_size=2)
    storage.upsert_stock = AsyncMock()  # type: ignore[method-assign]
    ids: dict[tuple[str, str], int] = {}
    storage._pool = MagicMock()
    storage._pool.connection = MagicMock(return_value=_FakeCM(_FakeConn(ids)))

    disc = make_disclosure(external_id="ann-reeval-1", symbol="JKH.N0000")
    first = await storage.upsert_disclosure(disc)
    assert first.id is not None
    second = await storage.upsert_disclosure(disc.model_copy(update={"title": "Updated Title"}))
    assert second.id == first.id
    assert second.title == "Updated Title"


@pytest.mark.asyncio
async def test_insert_disclosure_if_new_wraps_upsert() -> None:
    storage = Storage("postgresql://unused", min_size=1, max_size=2)
    stored = make_disclosure(external_id="ann-wrap").model_copy(update={"id": 55})
    storage.upsert_disclosure = AsyncMock(return_value=stored)  # type: ignore[method-assign]

    result = await storage.insert_disclosure_if_new(make_disclosure(external_id="ann-wrap"))
    assert result is not None
    assert result.id == 55
    storage.upsert_disclosure.assert_awaited_once()


@pytest.mark.asyncio
async def test_poller_reevaluates_existing_disclosure_after_upsert() -> None:
    """Crash-before-claim recovery: upsert returns existing row; evaluate still claims."""
    published = datetime(2026, 7, 11, 8, 0, 0, tzinfo=UTC)
    created = published - timedelta(hours=2)
    disc_rule = make_rule(
        id=9,
        symbol="COMB.N0000",
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=created,
    )
    existing = Disclosure(
        id=404,
        external_id="ann-existing",
        symbol="COMB.N0000",
        title="Board Meeting",
        url="https://www.cse.lk/announcements#ann-existing",
        published_at=published,
        seen_at=published,
    )

    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["COMB.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[disc_rule])
    storage.persist_market_snapshots = AsyncMock(
        side_effect=lambda snaps: [
            s.model_copy(update={"id": i}) for i, s in enumerate(snaps, start=1)
        ]
    )
    storage.get_previous_state = AsyncMock(return_value=PreviousPriceState(price=None))
    # Simulate row already in DB (prior poll inserted, crashed before claim)
    storage.upsert_disclosure = AsyncMock(return_value=existing)
    storage.claim_alert = AsyncMock(return_value=9001)
    storage.mark_alert_sent = AsyncMock()
    storage.claim_unsent_batch = AsyncMock(return_value=[])

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(
        return_value=[
            PriceSnapshot(symbol="COMB.N0000", price=90.0, ts=datetime.now(UTC)),
        ]
    )
    cse.fetch_announcements_for_symbol = AsyncMock(
        return_value=[
            make_disclosure(
                external_id="ann-existing",
                symbol="COMB.N0000",
                title="Board Meeting",
                url=existing.url,
                published_at=published,
            )
        ]
    )

    sent: list[str] = []

    async def send(chat_id: int, text: str) -> bool:
        sent.append(text)
        return True

    settings = Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )
    poller = Poller(settings, storage, cse, send)
    events = await poller.run_once(force=True)

    storage.upsert_disclosure.assert_awaited_once()
    storage.claim_alert.assert_awaited_once()
    claim_event = storage.claim_alert.await_args.args[0]
    assert claim_event.event_key == "disclosure:9:ann-existing"
    assert claim_event.rule_id == 9
    assert len(events) == 1
    assert events[0].event_key == "disclosure:9:ann-existing"
    assert sent and "Board Meeting" in sent[0]


@pytest.mark.asyncio
async def test_poller_new_disclosure_rule_skips_historical_already_in_feed() -> None:
    """New disclosure rule + CSE year backfill → zero Telegram; post-baseline fires once.

    Historical rows may already exist (upsert returns id) or be first inserts;
    created_at from create_alert_rule is the only baseline watermark.
    """
    created = datetime(2026, 7, 11, 12, 0, 0, tzinfo=UTC)
    disc_rule = make_rule(
        id=77,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=created,
    )
    historical = [
        make_disclosure(
            external_id=f"hist-{i}",
            symbol="JKH.N0000",
            title=f"Legacy {i}",
            published_at=created - timedelta(days=30 * (i + 1)),
        ).model_copy(update={"id": 100 + i, "just_inserted": i % 2 == 0})
        for i in range(5)
    ]
    fresh = make_disclosure(
        external_id="fresh-99",
        symbol="JKH.N0000",
        title="Brand New Filing",
        published_at=created + timedelta(hours=1),
    ).model_copy(update={"id": 999, "just_inserted": True})

    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[disc_rule])
    storage.persist_market_snapshots = AsyncMock(
        side_effect=lambda snaps: [
            s.model_copy(update={"id": i}) for i, s in enumerate(snaps, start=1)
        ]
    )
    storage.get_previous_state = AsyncMock(return_value=PreviousPriceState(price=None))
    # Upsert returns stored rows in feed order (already-existed + new inserts).
    feed = [*historical, fresh]
    storage.upsert_disclosure = AsyncMock(side_effect=list(feed))
    storage.claim_alert = AsyncMock(return_value=5001)
    storage.mark_alert_sent = AsyncMock()
    storage.claim_unsent_batch = AsyncMock(return_value=[])

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(
        return_value=[
            PriceSnapshot(symbol="JKH.N0000", price=200.0, ts=datetime.now(UTC)),
        ]
    )
    cse.fetch_announcements_for_symbol = AsyncMock(
        return_value=[
            make_disclosure(
                external_id=d.external_id,
                symbol=d.symbol,
                title=d.title,
                published_at=d.published_at,
            )
            for d in feed
        ]
    )

    sent: list[str] = []

    async def send(chat_id: int, text: str) -> bool:
        sent.append(text)
        return True

    settings = Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )
    poller = Poller(settings, storage, cse, send)
    events = await poller.run_once(force=True)

    assert storage.upsert_disclosure.await_count == 6
    # Only the post-baseline filing may claim/send.
    storage.claim_alert.assert_awaited_once()
    claim_event = storage.claim_alert.await_args.args[0]
    assert claim_event.event_key == "disclosure:77:fresh-99"
    assert len(events) == 1
    assert events[0].event_key == "disclosure:77:fresh-99"
    assert len(sent) == 1
    assert "Brand New Filing" in sent[0]
    assert all("Legacy" not in body for body in sent)
