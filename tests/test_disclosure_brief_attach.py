"""Wave3: attach ready disclosure_briefs text to Telegram claim/push."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from koel.config import Settings
from koel.domain import AlertEvent, AlertType, PreviousPriceState, PriceSnapshot, disclaimer
from koel.notify import SendResult
from koel.poller import Poller
from tests.conftest import make_disclosure, make_rule


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )


def _disclosure_event(**kwargs: object) -> AlertEvent:
    base = dict(
        rule_id=9,
        user_id=10,
        telegram_id=1001,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        threshold=None,
        trigger="new disclosure: AGM Notice",
        current_price=None,
        disclosure_title="AGM Notice",
        disclosure_url="https://www.cse.lk/announcements#99",
        disclosure_id=55,
        event_key="disclosure:9:99",
    )
    base.update(kwargs)
    return AlertEvent(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_claim_only_attaches_ready_filing_brief() -> None:
    brief = "AGM scheduled for 15 August. No dividend declared."
    storage = AsyncMock()
    storage.get_ready_filing_brief = AsyncMock(return_value=brief)
    storage.claim_alert = AsyncMock(return_value=9100)

    poller = Poller(_settings(), storage, AsyncMock(), AsyncMock(return_value=True))
    pending = await poller._claim_only(_disclosure_event())

    assert pending is not None
    assert brief in pending.message
    assert disclaimer() in pending.message
    assert pending.message.index(brief) < pending.message.index(disclaimer())
    storage.get_ready_filing_brief.assert_awaited_once_with(
        disclosure_id=55,
        external_id="99",
        symbol="JKH.N0000",
    )
    claim_msg = storage.claim_alert.await_args.args[1]
    assert brief in claim_msg


@pytest.mark.asyncio
async def test_claim_only_fail_soft_when_brief_missing() -> None:
    storage = AsyncMock()
    storage.get_ready_filing_brief = AsyncMock(return_value=None)
    storage.claim_alert = AsyncMock(return_value=9101)

    poller = Poller(_settings(), storage, AsyncMock(), AsyncMock(return_value=True))
    pending = await poller._claim_only(_disclosure_event())

    assert pending is not None
    assert "AGM Notice" in pending.message
    assert disclaimer() in pending.message
    assert pending.message.count("\n\n") == 1


@pytest.mark.asyncio
async def test_claim_only_fail_soft_when_brief_lookup_raises() -> None:
    storage = AsyncMock()
    storage.get_ready_filing_brief = AsyncMock(side_effect=RuntimeError("db down"))
    storage.claim_alert = AsyncMock(return_value=9102)

    poller = Poller(_settings(), storage, AsyncMock(), AsyncMock(return_value=True))
    pending = await poller._claim_only(_disclosure_event())

    assert pending is not None
    assert "AGM Notice" in pending.message
    storage.claim_alert.assert_awaited_once()


@pytest.mark.asyncio
async def test_claim_only_skips_brief_lookup_for_price_alerts() -> None:
    storage = AsyncMock()
    storage.get_ready_filing_brief = AsyncMock(return_value="should not appear")
    storage.claim_and_disarm = AsyncMock(return_value=501)

    event = AlertEvent(
        rule_id=1,
        user_id=10,
        telegram_id=1001,
        symbol="JKH.N0000",
        type=AlertType.PRICE_ABOVE,
        threshold=100.0,
        trigger="price crossed above 100.00",
        current_price=105.0,
        event_key="price:1:42",
        snapshot_id=42,
        set_armed=False,
    )
    poller = Poller(_settings(), storage, AsyncMock(), AsyncMock(return_value=True))
    pending = await poller._claim_only(event, disarm=True)

    assert pending is not None
    assert "should not appear" not in pending.message
    storage.get_ready_filing_brief.assert_not_awaited()


@pytest.mark.asyncio
async def test_disclosure_poll_push_includes_ready_brief() -> None:
    brief = "Board approved a rights issue of 1:5 at 40.00 LKR."
    published = datetime(2026, 7, 11, 8, 0, 0, tzinfo=UTC)
    disc_rule = make_rule(
        id=9,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=published - timedelta(hours=2),
    )
    stored = make_disclosure(
        external_id="25040",
        symbol="JKH.N0000",
        title="Rights Issue",
        published_at=published,
    ).model_copy(update={"id": 55, "just_inserted": True})

    sent: list[str] = []

    async def send(_chat_id: int, text: str) -> SendResult:
        sent.append(text)
        return SendResult.OK

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
    storage.upsert_disclosure = AsyncMock(return_value=stored)
    storage.get_ready_filing_brief = AsyncMock(return_value=brief)
    storage.claim_alert = AsyncMock(return_value=9100)
    storage.mark_alert_sent = AsyncMock()
    storage.claim_unsent_batch = AsyncMock(return_value=[])

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(
        return_value=[PriceSnapshot(symbol="JKH.N0000", price=100.0, ts=datetime.now(UTC))]
    )
    cse.fetch_announcements_for_symbol = AsyncMock(
        return_value=[
            make_disclosure(
                external_id="25040",
                symbol="JKH.N0000",
                title="Rights Issue",
                published_at=published,
            )
        ]
    )

    poller = Poller(_settings(), storage, cse, send)
    events = await poller.run_once(force=True)

    assert len(events) == 1
    assert events[0].disclosure_id == 55
    assert sent and brief in sent[0]
    assert disclaimer() in sent[0]
    storage.get_ready_filing_brief.assert_awaited()
    assert storage.get_ready_filing_brief.await_args.kwargs["disclosure_id"] == 55
