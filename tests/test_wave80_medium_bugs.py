"""Wave80: medium+ bugs — brief/unsent/category/row-id fail-closed.

1. ``cmd_brief`` must isinstance-guard symbol/brief (no ``str()`` soft-accept).
2. ``_notify_brief_followups`` must reject bool/non-int claim ids and
   non-string ``message_text`` (no ``int(True)==1`` / ``str()`` soft-accept).
3. Brief drain must isinstance-guard ``disclosure_id`` before summarize.
4. ``Poller._retry_unsent`` must skip poisoned ids / non-string message_text.
5. ``_disclosure_category_matches`` must isinstance-guard disclosure.category.
6. ``_row_to_rule`` / ``_row_to_snapshot`` must reject bool ids; create path
   reuses ``_row_to_rule`` (no manual ``int()`` soft-accept after INSERT).
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
from koel.domain import AlertType, Disclosure
from koel.notify import SendResult
from koel.poller import PendingSend, Poller
from koel.rules import _disclosure_category_matches
from koel.storage import Storage, _row_to_rule, _row_to_snapshot

ROOT = Path(__file__).resolve().parents[1]


def _enabled_settings(**kwargs: object) -> BriefSettings:
    base: dict[str, object] = dict(
        enabled=True,
        api_key="test-key",
        provider="gemini",
        model="gemini-2.0-flash",
        max_briefs_per_day=50,
        max_input_chars=12_000,
        sleep_seconds=0.0,
        pdf_grace_seconds=0,
        cdn_backoff_seconds=0,
        skipped_promote_hours=0,
        http_timeout_seconds=5.0,
    )
    base.update(kwargs)
    return BriefSettings(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_cmd_brief_rejects_non_string_row_fields() -> None:
    storage = MagicMock()
    storage.get_latest_ready_brief = AsyncMock(
        return_value={
            "symbol": 123,
            "brief": {"x": 1},
            "title": True,
            "url": None,
        }
    )
    update = MagicMock()
    update.effective_message = MagicMock()
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["JKH.N0000"]
    context.application.bot_data = {"storage": storage}

    with (
        patch("koel.bot._rate_limited", AsyncMock(return_value=False)),
        patch("koel.bot.briefs_enabled", return_value=True),
    ):
        await cmd_brief(update, context)

    sent = update.effective_message.reply_text.await_args.args[0]
    assert "JKH.N0000" in sent
    assert "123" not in sent
    assert "{'x': 1}" not in sent

    src = (ROOT / "koel" / "bot.py").read_text(encoding="utf-8")
    chunk = src.split("async def cmd_brief")[1].split("async def on_error")[0]
    assert "isinstance(raw_sym, str)" in chunk
    assert "isinstance(raw_brief, str)" in chunk
    assert 'str(row.get("symbol")' not in chunk
    assert 'str(row.get("brief")' not in chunk


@pytest.mark.asyncio
async def test_notify_brief_followups_rejects_poisoned_claim_rows() -> None:
    storage = MagicMock()
    storage.claim_brief_followups = AsyncMock(
        return_value=[
            {"id": True, "telegram_id": 9, "message_text": "bad-bool-id"},
            {"id": 2, "telegram_id": [9], "message_text": "bad-tg"},
            {"id": 3, "telegram_id": 9, "message_text": 99},
            {"id": 4, "telegram_id": 9, "message_text": "ok follow-up"},
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
            "external_id": "ext-1",
            "title": "AGM",
            "url": None,
        },
        brief="Margins steady.",
    )
    assert notify.await_count == 2
    texts = [c.args[1] for c in notify.await_args_list]
    assert "ok follow-up" in texts
    assert all("99" not in t for t in texts)
    assert all("bad-bool-id" not in t for t in texts)
    storage.mark_delivery_attempted_ok.assert_any_await(4)

    src = (ROOT / "koel" / "briefs" / "worker.py").read_text(encoding="utf-8")
    chunk = src.split("async def _notify_brief_followups")[1].split(
        "async def _promote_skipped_if_needed"
    )[0]
    assert "isinstance(raw_tg, bool)" in chunk
    assert "isinstance(raw_text, str)" in chunk
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

    src = (ROOT / "koel" / "briefs" / "worker.py").read_text(encoding="utf-8")
    drain = src.split("async def claim_pending_briefs(\n    storage:")[1]
    assert "isinstance(raw_did, bool)" in drain
    assert 'int(row["disclosure_id"])' not in drain.split("async def")[0]


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
                        "message_text": "skip-bool",
                    }
                ],
                [
                    {
                        "id": 2,
                        "telegram_id": 1,
                        "rule_id": 1,
                        "message_text": 123,
                    }
                ],
                [],
            ]
        )
    )
    poller._delivery_ok_already_recorded = MagicMock(return_value=False)  # type: ignore[method-assign]
    poller._reconcile_delivery_ok = AsyncMock()  # type: ignore[method-assign]
    delivered: list[PendingSend] = []

    async def _deliver(item: PendingSend) -> None:
        delivered.append(item)

    poller._deliver_one = _deliver  # type: ignore[method-assign]

    await poller._retry_unsent()
    assert len(delivered) == 1
    item = delivered[0]
    assert item.log_id == 2
    assert item.message == ""

    src = (ROOT / "koel" / "poller.py").read_text(encoding="utf-8")
    chunk = src.split("async def _retry_unsent(self) -> None:")[1].split(
        "async def _scheduled_tick"
    )[0]
    assert "isinstance(raw_id, bool)" in chunk
    assert "isinstance(raw_text, str)" in chunk
    assert 'int(row["id"])' not in chunk
    assert 'row["message_text"] or ""' not in chunk


def test_disclosure_category_rejects_non_string_haystack() -> None:
    rule = SimpleNamespace(category="Financial")
    disc = Disclosure.model_construct(  # type: ignore[call-arg]
        external_id="1",
        symbol="JKH.N0000",
        title="x",
        category=123,  # type: ignore[arg-type]
        url="https://www.cse.lk/x",
        published_at=datetime(2024, 1, 2, tzinfo=UTC),
        seen_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert _disclosure_category_matches(rule, disc) is False  # type: ignore[arg-type]

    ok = Disclosure.model_construct(  # type: ignore[call-arg]
        external_id="1",
        symbol="JKH.N0000",
        title="x",
        category="Quarterly Financial",
        url="https://www.cse.lk/x",
        published_at=datetime(2024, 1, 2, tzinfo=UTC),
        seen_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert _disclosure_category_matches(rule, ok) is True  # type: ignore[arg-type]

    src = (ROOT / "koel" / "rules.py").read_text(encoding="utf-8")
    chunk = src.split("def _disclosure_category_matches")[1].split(
        "def _safe_utc_aware"
    )[0]
    assert "isinstance(haystack, str)" in chunk
    assert "str(haystack)" not in chunk


def test_row_mappers_reject_bool_ids() -> None:
    ts = datetime(2024, 6, 1, tzinfo=UTC)
    assert (
        _row_to_snapshot(
            {"id": True, "symbol": "JKH.N0000", "price": 1.0, "ts": ts}
        )
        is None
    )
    assert (
        _row_to_snapshot(
            {"id": "1", "symbol": "JKH.N0000", "price": 1.0, "ts": ts}
        )
        is None
    )
    snap = _row_to_snapshot(
        {"id": 7, "symbol": "JKH.N0000", "price": 1.0, "ts": ts}
    )
    assert snap is not None and snap.id == 7
    # Bad ISO strings must fail closed (fromisoformat ValueError), not raise.
    assert (
        _row_to_snapshot(
            {"id": 8, "symbol": "JKH.N0000", "price": 1.0, "ts": "not-iso"}
        )
        is None
    )
    assert (
        _row_to_snapshot(
            {"id": 9, "symbol": "JKH.N0000", "price": 1.0, "ts": object()}
        )
        is None
    )

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
    assert _row_to_rule({**base, "telegram_id": False}) is None
    assert _row_to_rule({**base, "user_id": "9"}) is None
    ok = _row_to_rule(base)
    assert ok is not None and ok.type == AlertType.PRICE_ABOVE
    bad_created = _row_to_rule({**base, "created_at": "not-iso"})
    assert bad_created is not None and bad_created.created_at is None
    obj_created = _row_to_rule({**base, "created_at": object()})
    assert obj_created is not None and obj_created.created_at is None

    src = (ROOT / "koel" / "storage.py").read_text(encoding="utf-8")
    snap_fn = src.split("def _row_to_snapshot")[1].split("def _row_to_rule")[0]
    rule_fn = src.split("def _row_to_rule")[1]
    create = src.split("async def create_alert_rule")[1].split(
        "async def _fetch_active_rule"
    )[0]
    assert "isinstance(raw_id, bool)" in snap_fn
    assert "isinstance(raw_id, bool)" in rule_fn
    assert 'int(row["id"])' not in snap_fn
    assert "_row_to_rule(r)" in create
    assert 'int(r["id"])' not in create


@pytest.mark.asyncio
async def test_create_alert_rule_rejects_poisoned_inserted_row() -> None:
    class _Conn:
        async def execute(self, *_a: object, **_k: object) -> SimpleNamespace:
            sql = str(_a[0]) if _a else ""
            if "INSERT INTO alert_rules" in sql:
                return SimpleNamespace(
                    fetchone=AsyncMock(
                        return_value={
                            "id": True,
                            "user_id": 3,
                            "symbol": "JKH.N0000",
                            "type": "price_above",
                            "threshold": 1.0,
                            "category": None,
                            "active": True,
                            "armed": True,
                            "created_at": datetime(2024, 1, 1, tzinfo=UTC),
                        }
                    )
                )
            if "SELECT telegram_id" in sql:
                return SimpleNamespace(
                    fetchone=AsyncMock(return_value={"telegram_id": 100})
                )
            return SimpleNamespace(fetchone=AsyncMock(return_value=None))

        async def rollback(self) -> None:
            return None

        async def __aenter__(self) -> _Conn:
            return self

        async def __aexit__(self, *_a: object) -> None:
            return None

    class _Pool:
        def connection(self) -> _Conn:
            return _Conn()

    store = Storage.__new__(Storage)
    store._pool = _Pool()  # type: ignore[attr-defined]
    store.upsert_stock = AsyncMock()  # type: ignore[method-assign]
    store.add_watch = AsyncMock()  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="failed validation"):
        await store.create_alert_rule(3, "JKH.N0000", AlertType.PRICE_ABOVE, 1.0)
