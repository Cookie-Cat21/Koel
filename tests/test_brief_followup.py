"""Wave4/5: brief-ready Telegram follow-up (claim-gated + NFA)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from chime.briefs import BriefSettings
from chime.briefs.worker import claim_pending_briefs
from chime.domain import AlertType, disclaimer, format_brief_followup
from chime.notify import SendResult
from chime.rules import _event_key_disclosure
from tests.conftest import make_disclosure, make_rule
from tests.test_storage_unit import _Conn, _store


def _brief_followup_event_key(rule_id: int, external_id: str) -> str:
    """Mirror storage.claim_brief_followups INSERT event_key shape."""
    return f"brief_followup:{rule_id}:{external_id}"


def _enabled_settings(**kwargs: Any) -> BriefSettings:
    base = dict(
        enabled=True,
        api_key="test-key",
        provider="gemini",
        model="gemini-2.0-flash",
        max_briefs_per_day=50,
        max_input_chars=12_000,
    )
    base.update(kwargs)
    return BriefSettings(**base)  # type: ignore[arg-type]


def _pending_row(**kwargs: Any) -> dict[str, Any]:
    row = {
        "disclosure_id": 7,
        "external_id": "99",
        "symbol": "JKH.N0000",
        "title": "AGM Notice",
        "url": "https://www.cse.lk/announcements#99",
    }
    row.update(kwargs)
    return row


def test_format_brief_followup_nfa_last() -> None:
    msg = format_brief_followup(
        symbol="JKH.N0000",
        brief="Board met; no dividend.",
        title="AGM Notice",
    )
    assert "Filing brief ready" in msg
    assert "Board met; no dividend." in msg
    last = [ln for ln in msg.strip().splitlines() if ln.strip()][-1]
    assert last == disclaimer()


def test_brief_followup_event_key_isolated_from_disclosure() -> None:
    """Follow-up keys must not collide with primary disclosure keys.

    alert_log UNIQUE(rule_id, event_key) is shared; if prefixes matched,
    claim_brief_followups would ON CONFLICT against the primary fire and
    silently skip the Telegram follow-up.
    """
    rule = make_rule(id=9, type=AlertType.DISCLOSURE, threshold=None)
    cases = (
        "99",
        "ann-12345",
        "disclosure:9:99",  # adversarial: looks like a disclosure key
        "brief_followup:9:99",  # adversarial: looks like a follow-up key
        "9:99",
        "a:b:c",
    )
    for external_id in cases:
        disclosure = make_disclosure(external_id=external_id)
        primary = _event_key_disclosure(rule, disclosure)
        followup = _brief_followup_event_key(rule.id, external_id)
        assert primary == f"disclosure:{rule.id}:{external_id}"
        assert followup == f"brief_followup:{rule.id}:{external_id}"
        assert primary != followup
        assert primary.startswith("disclosure:")
        assert followup.startswith("brief_followup:")
        assert not primary.startswith("brief_followup:")
        assert not followup.startswith("disclosure:")


@pytest.mark.asyncio
async def test_claim_pending_briefs_followup_when_notify_and_disclosure_rules() -> None:
    brief = "AGM set for August."
    storage = MagicMock()
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(return_value=[_pending_row()])
    storage.mark_brief_ready = AsyncMock(return_value=True)
    storage.mark_brief_failed = AsyncMock(return_value=True)
    storage.claim_brief_followups = AsyncMock(
        return_value=[
            {
                "id": 501,
                "rule_id": 9,
                "telegram_id": 1001,
                "message_text": format_brief_followup(
                    symbol="JKH.N0000",
                    brief=brief,
                    title="AGM Notice",
                    url="https://www.cse.lk/announcements#99",
                ),
            }
        ]
    )
    storage.mark_delivery_attempted_ok = AsyncMock()
    storage.mark_alert_sent = AsyncMock()

    provider = AsyncMock()
    provider.summarize = AsyncMock(return_value=brief)

    sent: list[tuple[int, str]] = []

    async def notify(chat_id: int, text: str) -> SendResult:
        sent.append((chat_id, text))
        return SendResult.OK

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(),
        provider=provider,
        notify=notify,
        http_client=AsyncMock(),
    )
    assert n == 1
    storage.claim_brief_followups.assert_awaited_once()
    claim_kwargs = storage.claim_brief_followups.await_args.kwargs
    assert claim_kwargs["external_id"] == "99"
    assert claim_kwargs["symbol"] == "JKH.N0000"
    assert claim_kwargs["brief"] == brief
    assert "Filing brief ready" in claim_kwargs["message_text"]
    assert len(sent) == 1
    assert sent[0][0] == 1001
    assert brief in sent[0][1]
    assert disclaimer() in sent[0][1]
    storage.mark_delivery_attempted_ok.assert_awaited_once_with(501)
    storage.mark_alert_sent.assert_awaited_once_with(501)


@pytest.mark.asyncio
async def test_claim_pending_briefs_skips_followup_when_no_prior_alert_claim() -> None:
    """Ready-before-alert: no primary disclosure claim → no follow-up Telegram."""
    storage = MagicMock()
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(return_value=[_pending_row()])
    storage.mark_brief_ready = AsyncMock(return_value=True)
    storage.claim_brief_followups = AsyncMock(return_value=[])
    storage.mark_delivery_attempted_ok = AsyncMock()
    storage.mark_alert_sent = AsyncMock()
    provider = AsyncMock()
    provider.summarize = AsyncMock(return_value="ok brief")
    notify = AsyncMock()

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(),
        provider=provider,
        notify=notify,
        http_client=AsyncMock(),
    )
    assert n == 1
    storage.claim_brief_followups.assert_awaited_once()
    notify.assert_not_awaited()
    storage.mark_alert_sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_pending_briefs_followup_fail_soft_on_notify_error() -> None:
    storage = MagicMock()
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(return_value=[_pending_row()])
    storage.mark_brief_ready = AsyncMock(return_value=True)
    storage.mark_brief_failed = AsyncMock(return_value=True)
    storage.claim_brief_followups = AsyncMock(
        return_value=[
            {
                "id": 501,
                "rule_id": 9,
                "telegram_id": 1001,
                "message_text": "follow-up body",
            }
        ]
    )
    storage.mark_delivery_attempted_ok = AsyncMock()
    storage.mark_alert_sent = AsyncMock()
    provider = AsyncMock()
    provider.summarize = AsyncMock(return_value="ok brief")

    async def notify(_chat_id: int, _text: str) -> None:
        raise RuntimeError("telegram down")

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(),
        provider=provider,
        notify=notify,
        http_client=AsyncMock(),
    )
    assert n == 1
    storage.mark_brief_ready.assert_awaited_once()
    storage.mark_brief_failed.assert_not_awaited()
    # Leave alert_log leased/unsent for drain retry — do not mark sent.
    storage.mark_alert_sent.assert_not_awaited()
    storage.mark_delivery_attempted_ok.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_pending_briefs_followup_skips_mark_on_send_failed() -> None:
    """SendResult.FAILED must not mark message_sent (retry via unsent drain)."""
    storage = MagicMock()
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(return_value=[_pending_row()])
    storage.mark_brief_ready = AsyncMock(return_value=True)
    storage.claim_brief_followups = AsyncMock(
        return_value=[
            {
                "id": 501,
                "rule_id": 9,
                "telegram_id": 1001,
                "message_text": "follow-up body",
            }
        ]
    )
    storage.mark_delivery_attempted_ok = AsyncMock()
    storage.mark_alert_sent = AsyncMock()
    provider = AsyncMock()
    provider.summarize = AsyncMock(return_value="ok brief")

    async def notify(_chat_id: int, _text: str) -> SendResult:
        return SendResult.FAILED

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(),
        provider=provider,
        notify=notify,
        http_client=AsyncMock(),
    )
    assert n == 1
    storage.mark_alert_sent.assert_not_awaited()
    storage.mark_delivery_attempted_ok.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_pending_briefs_followup_skips_mark_on_send_deferred() -> None:
    storage = MagicMock()
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(return_value=[_pending_row()])
    storage.mark_brief_ready = AsyncMock(return_value=True)
    storage.claim_brief_followups = AsyncMock(
        return_value=[
            {
                "id": 502,
                "rule_id": 9,
                "telegram_id": 1001,
                "message_text": "follow-up body",
            }
        ]
    )
    storage.mark_delivery_attempted_ok = AsyncMock()
    storage.mark_alert_sent = AsyncMock()
    provider = AsyncMock()
    provider.summarize = AsyncMock(return_value="ok brief")

    async def notify(_chat_id: int, _text: str) -> SendResult:
        return SendResult.DEFERRED

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(),
        provider=provider,
        notify=notify,
        http_client=AsyncMock(),
    )
    assert n == 1
    storage.mark_alert_sent.assert_not_awaited()
    storage.mark_delivery_attempted_ok.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_pending_briefs_followup_bool_false_not_marked() -> None:
    storage = MagicMock()
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(return_value=[_pending_row()])
    storage.mark_brief_ready = AsyncMock(return_value=True)
    storage.claim_brief_followups = AsyncMock(
        return_value=[
            {
                "id": 503,
                "rule_id": 9,
                "telegram_id": 1001,
                "message_text": "follow-up body",
            }
        ]
    )
    storage.mark_delivery_attempted_ok = AsyncMock()
    storage.mark_alert_sent = AsyncMock()
    provider = AsyncMock()
    provider.summarize = AsyncMock(return_value="ok brief")

    async def notify(_chat_id: int, _text: str) -> bool:
        return False

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(),
        provider=provider,
        notify=notify,
        http_client=AsyncMock(),
    )
    assert n == 1
    storage.mark_alert_sent.assert_not_awaited()
    storage.mark_delivery_attempted_ok.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_pending_briefs_skips_followup_when_mark_ready_false() -> None:
    storage = MagicMock()
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(return_value=[_pending_row()])
    storage.mark_brief_ready = AsyncMock(return_value=False)
    storage.claim_brief_followups = AsyncMock(return_value=[])
    provider = AsyncMock()
    provider.summarize = AsyncMock(return_value="brief")
    notify = AsyncMock()
    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(),
        provider=provider,
        notify=notify,
        http_client=AsyncMock(),
    )
    assert n == 1
    notify.assert_not_awaited()
    storage.claim_brief_followups.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_pending_briefs_skips_followup_without_external_id() -> None:
    storage = MagicMock()
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(
        return_value=[_pending_row(external_id="")]
    )
    storage.mark_brief_ready = AsyncMock(return_value=True)
    storage.claim_brief_followups = AsyncMock(return_value=[])
    provider = AsyncMock()
    provider.summarize = AsyncMock(return_value="brief")
    notify = AsyncMock()
    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(),
        provider=provider,
        notify=notify,
        http_client=AsyncMock(),
    )
    assert n == 1
    storage.claim_brief_followups.assert_not_awaited()
    notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_poller_drain_briefs_passes_notify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import chime.poller as poller_mod
    from chime.config import Settings
    from chime.poller import Poller

    settings = Settings(
        telegram_bot_token="t",
        database_url="postgresql://unused",
    )
    send = AsyncMock(return_value=True)
    poller = Poller(settings, MagicMock(), MagicMock(), send)
    captured: dict[str, Any] = {}

    async def fake_claim(storage: Any, **kwargs: Any) -> int:
        captured["kwargs"] = kwargs
        return 1

    monkeypatch.setattr(poller_mod, "claim_pending_briefs", fake_claim)
    await poller._drain_briefs_safe()
    assert captured["kwargs"].get("notify") is send


@pytest.mark.asyncio
async def test_storage_claim_brief_followups_sql_gates_on_primary_alert() -> None:
    conn = _Conn(
        [
            [
                {
                    "id": 88,
                    "rule_id": 9,
                    "message_text": "follow-up",
                    "telegram_id": 1001,
                }
            ]
        ]
    )
    store = _store(conn)
    rows = await store.claim_brief_followups(
        external_id="99",
        symbol="jkh.n0000",
        brief="AGM set for August.",
        message_text="follow-up body",
        lease_seconds=90,
    )
    assert len(rows) == 1
    assert rows[0]["id"] == 88
    sql = conn.sql[0]
    assert "'brief_followup:' || p.rule_id::text || ':' || %s" in sql
    assert "al.event_key = 'disclosure:' || ar.id::text || ':' || %s" in sql
    assert "ON CONFLICT (rule_id, event_key) DO NOTHING" in sql
    assert "message_sent OR al.delivery_attempted_ok" in sql
    assert "chr(10) || chr(10) || %s || chr(10) || chr(10)" in sql
    assert "delivery_lease_until" in sql
    assert conn.params[0][0] == "99"
    assert conn.params[0][1] == "JKH.N0000"
    assert conn.params[0][2] == "AGM set for August."
    assert conn.params[0][5] == 90


@pytest.mark.asyncio
async def test_storage_claim_brief_followups_noop_on_incomplete() -> None:
    store = _store(_Conn([]))
    assert await store.claim_brief_followups(
        external_id="",
        symbol="JKH.N0000",
        brief="x",
        message_text="y",
    ) == []
    assert await store.claim_brief_followups(
        external_id="99",
        symbol="",
        brief="x",
        message_text="y",
    ) == []
