"""Wave76: medium+ bugs — cmd_brief / claim rows / unsent / category / mappers.

1. ``cmd_brief`` must isinstance-guard PG symbol/brief (no ``str()`` soft-accept).
2. ``_notify_brief_followups`` must isinstance-guard claimed telegram_id/id/
   message_text (bool→1 soft-accept / list int() abort).
3. Brief drain must isinstance-guard ``disclosure_id`` before use.
4. ``_retry_unsent`` must isinstance-guard id/telegram_id/rule_id/message_text.
5. ``_disclosure_category_matches`` must isinstance-guard haystack (no
   ``str()`` soft-accept of ints/objects).
6. ``_row_to_snapshot`` / ``_row_to_rule`` must reject bool ids/price/flags and
   never ``str()``-coerce non-string timestamps; ``create_alert`` reuses
   ``_row_to_rule``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
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
    )
    base.update(kwargs)
    return BriefSettings(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_cmd_brief_rejects_non_string_symbol_and_brief() -> None:
    storage = AsyncMock()
    storage.get_latest_ready_brief = AsyncMock(
        return_value={
            "symbol": 99,
            "brief": True,
            "title": None,
            "url": None,
        }
    )
    update = MagicMock()
    update.effective_user.id = 1001
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    context.application.bot_data = {"storage": storage}
    context.args = ["JKH.N0000"]

    with (
        patch("koel.bot._rate_limited", AsyncMock(return_value=False)),
        patch("koel.bot.briefs_enabled", return_value=True),
    ):
        await cmd_brief(update, context)

    text = update.effective_message.reply_text.await_args.args[0]
    assert "99" not in text
    assert "True" not in text
    assert "JKH.N0000" in text

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
            {"id": True, "telegram_id": 1001, "message_text": "bad-bool-id"},
            {"id": 2, "telegram_id": [1001], "message_text": "bad-tg"},
            {"id": 3, "telegram_id": 1001, "message_text": 123},
            {"id": 4, "telegram_id": 1001, "message_text": "ok follow-up"},
        ]
    )
    storage.mark_delivery_attempted_ok = AsyncMock()
    storage.mark_alert_sent = AsyncMock()
    notify = AsyncMock(return_value=SendResult.OK)

    await _notify_brief_followups(
        storage,
        notify=notify,
        row={
            "disclosure_id": 1,
            "symbol": "JKH.N0000",
            "external_id": "ext-9",
            "title": "AGM",
            "url": None,
        },
        brief="Margins steady.",
    )

    assert notify.await_count == 2
    texts = [c.args[1] for c in notify.await_args_list]
    assert "ok follow-up" in texts
    assert "123" not in texts[0]
    assert "Margins steady." in texts[0]
    storage.mark_delivery_attempted_ok.assert_any_await(4)

    src = (ROOT / "koel" / "briefs" / "worker.py").read_text(encoding="utf-8")
    chunk = src.split("async def _notify_brief_followups")[1].split(
        "async def _promote_skipped_if_needed"
    )[0]
    assert "isinstance(raw_tg, bool)" in chunk
    assert "isinstance(raw_log, bool)" in chunk
    assert 'str(entry.get("message_text")' not in chunk


@pytest.mark.asyncio
async def test_brief_drain_skips_poisoned_disclosure_id() -> None:
    storage = MagicMock()
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=0)
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(
        return_value=[
            {
                "disclosure_id": True,
                "symbol": "JKH.N0000",
                "title": "AGM",
                "pdf_url": None,
                "external_id": "1",
            },
            {
                "disclosure_id": ["x"],
                "symbol": "JKH.N0000",
                "title": "AGM",
                "pdf_url": None,
                "external_id": "2",
            },
        ]
    )
    storage.list_ready_briefs_for_followup_sweep = AsyncMock(return_value=[])
    storage.mark_brief_ready = AsyncMock()
    storage.mark_brief_failed = AsyncMock()

    provider = AsyncMock()
    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(),
        provider=provider,
        http_client=AsyncMock(),
    )
    assert n == 0
    provider.summarize.assert_not_awaited()
    storage.mark_brief_ready.assert_not_awaited()
    storage.mark_brief_failed.assert_not_awaited()

    src = (ROOT / "koel" / "briefs" / "worker.py").read_text(encoding="utf-8")
    drain = src.split("async def claim_pending_briefs(\n    storage:")[1]
    assert "isinstance(raw_did, bool)" in drain
    assert 'int(row["disclosure_id"])' not in drain.split("for i, row in enumerate")[
        1
    ].split("try:")[0]


@pytest.mark.asyncio
async def test_retry_unsent_skips_poisoned_rows() -> None:
    storage = AsyncMock()
    storage.claim_unsent_batch = AsyncMock(
        side_effect=[
            [
                {
                    "id": True,
                    "telegram_id": 9,
                    "message_text": "🔔 JKH.N0000\nbad",
                    "rule_id": 1,
                }
            ],
            [
                {
                    "id": 7,
                    "telegram_id": 9,
                    "message_text": ["not", "str"],
                    "rule_id": 1,
                }
            ],
            [],
        ]
    )
    poller = object.__new__(Poller)
    poller.storage = storage
    poller._deliver_one = AsyncMock()  # type: ignore[method-assign]
    poller._delivery_ok_already_recorded = MagicMock(return_value=False)  # type: ignore[method-assign]
    poller._reconcile_delivery_ok = AsyncMock()  # type: ignore[method-assign]

    with patch("koel.poller.RETRY_UNSENT_MAX", 5):
        await poller._retry_unsent()

    assert poller._deliver_one.await_count == 1
    pending = poller._deliver_one.await_args.args[0]
    assert pending.log_id == 7
    assert pending.message == ""

    src = (ROOT / "koel" / "poller.py").read_text(encoding="utf-8")
    chunk = src.split("async def _retry_unsent(self)")[1].split(
        "async def _scheduled_tick"
    )[0]
    assert "isinstance(raw_id, bool)" in chunk
    assert "isinstance(raw_tg, bool)" in chunk
    assert "isinstance(raw_rule, bool)" in chunk
    assert 'int(row["id"])' not in chunk


def test_disclosure_category_rejects_non_string_haystack() -> None:
    rule = AlertRule.model_construct(
        id=1,
        user_id=1,
        telegram_id=1,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        threshold=None,
        category="Financial",
        active=True,
        armed=True,
        created_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    for bad in (123, True, {"c": "Financial"}, ["Financial"], None):
        disc = Disclosure.model_construct(
            external_id="ext-1",
            symbol="JKH.N0000",
            title="t",
            url="https://www.cse.lk/announcements",
            published_at=datetime(2024, 6, 1, tzinfo=UTC),
            seen_at=datetime(2024, 6, 1, tzinfo=UTC),
            category=bad,  # type: ignore[arg-type]
        )
        assert _disclosure_category_matches(rule, disc) is False

    ok = Disclosure.model_construct(
        external_id="ext-1",
        symbol="JKH.N0000",
        title="t",
        url="https://www.cse.lk/announcements",
        published_at=datetime(2024, 6, 1, tzinfo=UTC),
        seen_at=datetime(2024, 6, 1, tzinfo=UTC),
        category="Q1 Financial Results",
    )
    assert _disclosure_category_matches(rule, ok) is True

    src = (ROOT / "koel" / "rules.py").read_text(encoding="utf-8")
    chunk = src.split("def _disclosure_category_matches")[1].split(
        "def _safe_utc_aware"
    )[0]
    assert "isinstance(haystack, str)" in chunk
    assert "str(haystack)" not in chunk


def test_row_to_snapshot_rejects_poisoned_id_price_ts() -> None:
    ts = datetime(2024, 6, 1, tzinfo=UTC)
    assert (
        _row_to_snapshot({"id": ["x"], "symbol": "JKH.N0000", "price": 1.0, "ts": ts})
        is None
    )
    assert (
        _row_to_snapshot({"id": True, "symbol": "JKH.N0000", "price": 1.0, "ts": ts})
        is None
    )
    assert (
        _row_to_snapshot({"id": 5, "symbol": "JKH.N0000", "price": True, "ts": ts})
        is None
    )
    assert (
        _row_to_snapshot(
            {"id": 5, "symbol": "JKH.N0000", "price": 1.0, "ts": object()}
        )
        is None
    )
    assert (
        _row_to_snapshot(
            {"id": 5, "symbol": "JKH.N0000", "price": 1.0, "ts": "not-a-timestamp"}
        )
        is None
    )
    from_iso = _row_to_snapshot(
        {
            "id": 5,
            "symbol": "JKH.N0000",
            "price": 1.0,
            "ts": "2024-06-01T00:00:00+00:00",
        }
    )
    assert from_iso is not None and from_iso.id == 5
    ok = _row_to_snapshot({"id": 5, "symbol": "JKH.N0000", "price": 1.0, "ts": ts})
    assert ok is not None and ok.id == 5

    src = (ROOT / "koel" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("def _row_to_snapshot")[1].split("def _row_to_rule")[0]
    assert "isinstance(raw_id, bool)" in chunk
    assert "isinstance(raw_price, bool)" in chunk
    assert "str(ts)" not in chunk


def test_row_to_rule_rejects_bool_ids_and_non_bool_flags() -> None:
    base = {
        "id": 1,
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
    assert _row_to_rule({**base, "id": True}) is None
    assert _row_to_rule({**base, "user_id": False}) is None
    assert _row_to_rule({**base, "telegram_id": True}) is None
    assert _row_to_rule({**base, "active": 1}) is None
    assert _row_to_rule({**base, "armed": "yes"}) is None
    poisoned = _row_to_rule({**base, "created_at": object()})
    assert poisoned is not None and poisoned.created_at is None
    bad_iso = _row_to_rule({**base, "created_at": "not-a-timestamp"})
    assert bad_iso is not None and bad_iso.created_at is None
    good_iso = _row_to_rule({**base, "created_at": "2024-01-01T00:00:00+00:00"})
    assert good_iso is not None and good_iso.created_at is not None
    assert _row_to_rule(base) is not None

    src = (ROOT / "koel" / "storage.py").read_text(encoding="utf-8")
    create = src.split("async def create_alert")[1].split(
        "async def _fetch_active_rule"
    )[0]
    assert "_row_to_rule(r)" in create
    rule_fn = src.split("def _row_to_rule")[1]
    assert "isinstance(raw_active, bool)" in rule_fn
    assert "isinstance(raw_id, bool)" in rule_fn
    assert "str(created)" not in rule_fn.split("sanitize_disclosure_category")[0]
