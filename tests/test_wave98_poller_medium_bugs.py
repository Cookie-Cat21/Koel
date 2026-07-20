"""Wave98: medium+ poller disclosure batch bugs."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from koel.config import Settings
from koel.domain import AlertType
from koel.poller import Poller
from tests.conftest import make_disclosure, make_rule


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
        pdf_enrich_sleep_seconds=0,
    )


@pytest.mark.asyncio
async def test_disclosure_upsert_failure_does_not_abort_later_alerts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One bad disclosure row must not suppress later valid disclosure alerts."""
    monkeypatch.setenv("KOEL_DELIVERY_OK_LEDGER", "")
    rule = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=datetime(2026, 7, 10, 6, 0, tzinfo=UTC),
    )
    bad = make_disclosure(external_id="ann-bad", title="Bad row")
    good = make_disclosure(external_id="ann-good", title="Good row").model_copy(
        update={"id": 77, "just_inserted": False}
    )

    storage = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[rule])
    storage.upsert_disclosure = AsyncMock(
        side_effect=[RuntimeError("upsert boom"), good]
    )
    storage.get_ready_filing_brief = AsyncMock(return_value=None)
    storage.claim_alert = AsyncMock(return_value=501)
    storage.mark_delivery_attempted_ok = AsyncMock()
    storage.mark_alert_sent = AsyncMock()

    cse = AsyncMock()
    cse.fetch_announcements_for_symbol = AsyncMock(return_value=[bad, good])
    send = AsyncMock(return_value=True)
    poller = Poller(_settings(), storage, cse, send)

    events, ok = await poller._poll_disclosures()

    assert ok is False
    assert poller.last_error == "upsert boom"
    assert [event.event_key for event in events] == ["disclosure:1:ann-good"]
    storage.upsert_disclosure.assert_any_await(bad)
    storage.upsert_disclosure.assert_any_await(good)
    storage.claim_alert.assert_awaited_once()
    send.assert_awaited_once()
    storage.mark_alert_sent.assert_awaited_once_with(501)
