"""Wave79: medium+ bugs — cmd_brief / follow-up / category / retry / row ids.

1. ``cmd_brief`` must isinstance-guard PG symbol/brief (no ``str()`` soft-accept).
2. ``_notify_brief_followups`` must isinstance-guard claim ``telegram_id`` / ``id``
   (reject ``bool``; no ``int(list)`` abort / ``str(message_text)`` soft-accept).
3. ``claim_pending_briefs`` drain must isinstance-guard ``disclosure_id``.
4. ``_disclosure_category_matches`` must isinstance-guard disclosure category
   (no ``str(haystack)`` soft-accept of ints/objects).
5. ``_retry_unsent`` must isinstance-guard unsent row ids / message_text so one
   poisoned row cannot abort the retry drain.
6. ``_row_to_rule`` / ``_row_to_snapshot`` must reject ``bool`` ids and fail closed
   on bad ISO ``created_at`` / ``ts`` strings (no ``str()`` soft-accept).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from koel.bot import cmd_brief
from koel.briefs import BriefSettings
from koel.briefs.worker import _notify_brief_followups, claim_pending_briefs
from koel.domain import AlertRule, AlertType, Disclosure
from koel.notify import SendResult
from koel.poller import Poller
from koel.rules import _disclosure_category_matches
from koel.storage import _row_to_rule, _row_to_snapshot

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_cmd_brief_rejects_non_string_pg_fields() -> None:
    update = MagicMock()
    update.effective_message = MagicMock()
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["JKH.N0000"]
    context.application.bot_data = {
        "storage": SimpleNamespace(
            get_latest_ready_brief=AsyncMock(
                return_value={
                    "symbol": 99,
                    "brief": True,
                    "title": None,
                    "url": None,
                }
            )
        )
    }

    with (
        patch("koel.bot._rate_limited", AsyncMock(return_value=False)),
        patch("koel.bot.briefs_enabled", return_value=True),
    ):
        await cmd_brief(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    text = update.effective_message.reply_text.await_args.args[0]
    assert "JKH.N0000" in text
    assert "99" not in text
    assert "True" not in text

    src = (ROOT / "koel" / "bot.py").read_text(encoding="utf-8")
    chunk = src.split("async def cmd_brief")[1].split("async def on_error")[0]
    assert "isinstance(raw_sym, str)" in chunk
    assert "isinstance(raw_brief, str)" in chunk
    assert 'str(row.get("symbol")' not in chunk
    assert 'str(row.get("brief")' not in chunk


@pytest.mark.asyncio
async def test_notify_brief_followups_skips_poisoned_claim_rows() -> None:
    storage = MagicMock()
    storage.claim_brief_followups = AsyncMock(
        return_value=[
            {"id": True, "telegram_id": 1, "message_text": "bad-bool-id"},
            {"id": 2, "telegram_id": [9], "message_text": "bad-tg"},
            {"id": 3, "telegram_id": 42, "message_text": 123},
            {"id": 4, "telegram_id": 99, "message_text": "ok body"},
        ]
    )
    storage.mark_delivery_attempted_ok = AsyncMock()
    storage.mark_alert_sent = AsyncMock()
    sent: list[tuple[int, str]] = []

    async def notify(chat_id: int, text: str) -> SendResult:
        sent.append((chat_id, text))
        return SendResult.OK

    await _notify_brief_followups(
        storage,
        notify=notify,
        row={
            "disclosure_id": 1,
            "symbol": "JKH.N0000",
            "external_id": "ext-1",
            "title": "Results",
        },
        brief="Margins steady.",
    )

    assert len(sent) == 2
    assert sent[0][0] == 42
    assert "123" not in sent[0][1]
    assert sent[1] == (99, "ok body")

    src = (ROOT / "koel" / "briefs" / "worker.py").read_text(encoding="utf-8")
    chunk = src.split("async def _notify_brief_followups")[1].split(
        "async def _promote_skipped_if_needed"
    )[0]
    assert "isinstance(raw_tg, bool)" in chunk
    assert "isinstance(raw_tg, int)" in chunk
    assert 'str(entry.get("message_text")' not in chunk
    assert 'int(entry["telegram_id"])' not in chunk


@pytest.mark.asyncio
async def test_claim_pending_briefs_skips_poisoned_disclosure_id() -> None:
    storage = MagicMock()
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(
        return_value=[
            {"disclosure_id": True, "symbol": "JKH.N0000", "title": "t"},
            {"disclosure_id": [1], "symbol": "JKH.N0000", "title": "t"},
        ]
    )
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=0)
    cfg = BriefSettings(
        enabled=True,
        api_key="test-key",
        max_briefs_per_day=10,
        pdf_grace_seconds=0,
        cdn_backoff_seconds=0,
        sleep_seconds=0,
        http_timeout_seconds=1.0,
        skipped_promote_hours=0,
    )
    provider = MagicMock()
    provider.summarize = AsyncMock(return_value="brief")

    n = await claim_pending_briefs(
        storage,
        settings=cfg,
        limit=5,
        provider=provider,
        http_client=MagicMock(),
        notify=None,
    )
    assert n == 0
    provider.summarize.assert_not_awaited()

    src = (ROOT / "koel" / "briefs" / "worker.py").read_text(encoding="utf-8")
    drain = src.split("for i, row in enumerate(rows):")[1].split("try:")[0]
    assert "isinstance(raw_did, bool)" in drain
    assert "isinstance(raw_did, int)" in drain
    assert 'int(row["disclosure_id"])' not in drain


def test_disclosure_category_rejects_non_string_haystack() -> None:
    rule = AlertRule.model_construct(
        id=1,
        user_id=1,
        telegram_id=1,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        threshold=None,
        category="12",
        active=True,
        armed=True,
    )
    disc = Disclosure.model_construct(
        external_id="ext-1",
        symbol="JKH.N0000",
        title="t",
        url="https://www.cse.lk/x",
        published_at=datetime(2024, 6, 1, tzinfo=UTC),
        seen_at=datetime(2024, 6, 1, tzinfo=UTC),
        category=12345,  # type: ignore[arg-type]
    )
    assert _disclosure_category_matches(rule, disc) is False

    ok = Disclosure.model_construct(
        external_id="ext-1",
        symbol="JKH.N0000",
        title="t",
        url="https://www.cse.lk/x",
        published_at=datetime(2024, 6, 1, tzinfo=UTC),
        seen_at=datetime(2024, 6, 1, tzinfo=UTC),
        category="Financial 12Q",
    )
    assert _disclosure_category_matches(rule, ok) is True

    src = (ROOT / "koel" / "rules.py").read_text(encoding="utf-8")
    chunk = src.split("def _disclosure_category_matches")[1].split("def _safe_utc_aware")[0]
    assert "isinstance(haystack, str)" in chunk
    assert "hay = str(haystack)" not in chunk


@pytest.mark.asyncio
async def test_retry_unsent_skips_poisoned_rows() -> None:
    poller = object.__new__(Poller)
    poller.storage = SimpleNamespace(
        claim_unsent_batch=AsyncMock(
            side_effect=[
                [
                    {
                        "id": True,
                        "telegram_id": 1,
                        "rule_id": 1,
                        "message_text": "x",
                    }
                ],
                [
                    {
                        "id": 2,
                        "telegram_id": [9],
                        "rule_id": 1,
                        "message_text": "x",
                    }
                ],
                [
                    {
                        "id": 3,
                        "telegram_id": 9,
                        "rule_id": 1,
                        "message_text": 123,
                    }
                ],
                [],
            ]
        )
    )
    poller._delivery_ok_already_recorded = MagicMock(return_value=False)  # type: ignore[method-assign]
    poller._deliver_one = AsyncMock()  # type: ignore[method-assign]

    await poller._retry_unsent()

    poller._deliver_one.assert_awaited_once()
    item = poller._deliver_one.await_args.args[0]
    assert item.log_id == 3
    assert item.telegram_id == 9
    assert item.message == ""

    src = (ROOT / "koel" / "poller.py").read_text(encoding="utf-8")
    chunk = src.split("async def _retry_unsent(self)")[1].split(
        "async def _scheduled_tick"
    )[0]
    assert "isinstance(raw_id, bool)" in chunk
    assert "isinstance(raw_tg, int)" in chunk
    assert 'int(row["id"])' not in chunk
    assert 'row["message_text"] or ""' not in chunk


def test_row_to_rule_and_snapshot_reject_bool_ids_and_bad_iso() -> None:
    base = {
        "id": True,
        "user_id": 2,
        "telegram_id": 3,
        "symbol": "JKH.N0000",
        "type": "price_above",
        "threshold": 10.0,
        "category": None,
        "active": True,
        "armed": True,
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
    }
    assert _row_to_rule(base) is None
    assert _row_to_rule({**base, "id": 1, "user_id": False}) is None
    assert _row_to_rule({**base, "id": 1, "telegram_id": True}) is None
    bad_created = _row_to_rule({**base, "id": 1, "created_at": "not-a-timestamp"})
    assert bad_created is not None and bad_created.created_at is None
    obj_created = _row_to_rule({**base, "id": 1, "created_at": object()})
    assert obj_created is not None and obj_created.created_at is None
    ok = _row_to_rule({**base, "id": 1})
    assert ok is not None and ok.id == 1

    assert (
        _row_to_snapshot(
            {
                "id": True,
                "symbol": "JKH.N0000",
                "price": 1.0,
                "ts": datetime.now(UTC),
            }
        )
        is None
    )
    assert (
        _row_to_snapshot(
            {
                "id": 1,
                "symbol": "JKH.N0000",
                "price": True,
                "ts": datetime.now(UTC),
            }
        )
        is None
    )
    assert (
        _row_to_snapshot(
            {
                "id": 1,
                "symbol": "JKH.N0000",
                "price": 1.0,
                "ts": "not-a-timestamp",
            }
        )
        is None
    )
    assert (
        _row_to_snapshot(
            {
                "id": 1,
                "symbol": "JKH.N0000",
                "price": 1.0,
                "ts": object(),
            }
        )
        is None
    )
    snap = _row_to_snapshot(
        {
            "id": 7,
            "symbol": "JKH.N0000",
            "price": 1.0,
            "ts": datetime(2024, 6, 1, tzinfo=UTC),
        }
    )
    assert snap is not None and snap.id == 7
    snap_iso = _row_to_snapshot(
        {
            "id": 8,
            "symbol": "JKH.N0000",
            "price": 2.0,
            "ts": "2024-06-01T00:00:00+00:00",
        }
    )
    assert snap_iso is not None and snap_iso.id == 8

    src = (ROOT / "koel" / "storage.py").read_text(encoding="utf-8")
    rule_chunk = src.split("def _row_to_rule")[1]
    snap_chunk = src.split("def _row_to_snapshot")[1].split("def _row_to_rule")[0]
    assert "isinstance(raw_id, bool)" in rule_chunk
    assert "isinstance(raw_id, bool)" in snap_chunk
    assert "id=raw_id" in snap_chunk
    assert 'id=int(row["id"])' not in snap_chunk
    assert "datetime.fromisoformat(str(ts))" not in snap_chunk
    assert "datetime.fromisoformat(str(created))" not in rule_chunk
    create = src.split("async def create_alert_rule")[1].split(
        "async def _fetch_active_rule"
    )[0]
    assert "_row_to_rule(r)" in create
