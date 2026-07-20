"""Wave18: /myalerts + /cancel must work for disclosure category rules.

Users can hold multiple active disclosure rules on one symbol (any + category
filters). Listing must show the category substring and the numeric id; cancel
must deactivate that id (including the #id form copied from /myalerts).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from koel.bot import CANCEL_USAGE, cmd_cancel, cmd_myalerts
from koel.domain import AlertRule, AlertType, disclaimer


def _make_update_context(
    *,
    args: list[str] | None = None,
    storage: AsyncMock,
    telegram_id: int = 1001,
) -> tuple[MagicMock, MagicMock]:
    message = AsyncMock()
    message.reply_text = AsyncMock()

    user = MagicMock()
    user.id = telegram_id

    update = MagicMock()
    update.effective_message = message
    update.effective_user = user

    application = MagicMock()
    application.bot_data = {"storage": storage}

    context = MagicMock()
    context.args = args or []
    context.application = application
    return update, context


@pytest.mark.asyncio
async def test_myalerts_empty_mentions_category_disclosure() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.list_alerts = AsyncMock(return_value=[])
    update, context = _make_update_context(storage=storage)

    with patch("koel.bot._rate_limited", AsyncMock(return_value=False)):
        await cmd_myalerts(update, context)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "/alert JKH.N0000 disclosure" in reply
    assert "/alert JKH.N0000 disclosure Financial" in reply
    assert disclaimer() in reply


@pytest.mark.asyncio
async def test_myalerts_lists_category_and_any_disclosure_with_cancel_hint() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.list_alerts = AsyncMock(
        return_value=[
            AlertRule(
                id=12,
                user_id=42,
                telegram_id=1001,
                symbol="JKH.N0000",
                type=AlertType.DISCLOSURE,
                threshold=None,
                category="Financial",
            ),
            AlertRule(
                id=13,
                user_id=42,
                telegram_id=1001,
                symbol="JKH.N0000",
                type=AlertType.DISCLOSURE,
                threshold=None,
                category=None,
            ),
            AlertRule(
                id=14,
                user_id=42,
                telegram_id=1001,
                symbol="SAMP.N0000",
                type=AlertType.DISCLOSURE,
                threshold=None,
                category="Q1 Interim Financial",
            ),
        ]
    )
    update, context = _make_update_context(storage=storage)

    with patch("koel.bot._rate_limited", AsyncMock(return_value=False)):
        await cmd_myalerts(update, context)

    reply = update.effective_message.reply_text.await_args.args[0]
    lines = reply.splitlines()
    assert "#12 JKH.N0000 disclosure Financial" in lines
    assert "#13 JKH.N0000 disclosure" in lines
    assert "#14 SAMP.N0000 disclosure Q1 Interim Financial" in lines
    assert "Cancel with /cancel ALERT_ID" in lines
    assert disclaimer() in reply
    # Any-disclosure line must not accidentally append a blank category token.
    assert not any(ln.startswith("#13 JKH.N0000 disclosure ") for ln in lines)


@pytest.mark.asyncio
async def test_cancel_category_disclosure_rule_by_id() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.deactivate_alert = AsyncMock(return_value=True)
    update, context = _make_update_context(args=["12"], storage=storage)

    with patch("koel.bot._rate_limited", AsyncMock(return_value=False)):
        await cmd_cancel(update, context)

    storage.deactivate_alert.assert_awaited_once_with(42, 12)
    assert update.effective_message.reply_text.await_args.args[0] == "Cancelled alert #12."


@pytest.mark.asyncio
async def test_cancel_category_disclosure_rule_hash_prefix_from_myalerts() -> None:
    """Users copy '#12' from /myalerts category lines — strip and cancel."""
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.deactivate_alert = AsyncMock(return_value=True)
    update, context = _make_update_context(args=["#12"], storage=storage)

    with patch("koel.bot._rate_limited", AsyncMock(return_value=False)):
        await cmd_cancel(update, context)

    storage.deactivate_alert.assert_awaited_once_with(42, 12)
    assert update.effective_message.reply_text.await_args.args[0] == "Cancelled alert #12."


@pytest.mark.asyncio
async def test_cancel_missing_category_rule_points_at_myalerts() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.deactivate_alert = AsyncMock(return_value=False)
    update, context = _make_update_context(args=["99"], storage=storage)

    with patch("koel.bot._rate_limited", AsyncMock(return_value=False)):
        await cmd_cancel(update, context)

    storage.deactivate_alert.assert_awaited_once_with(42, 99)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "No active alert #99" in reply
    assert "/myalerts" in reply


def test_cancel_usage_still_points_at_myalerts_ids() -> None:
    assert "/myalerts" in CANCEL_USAGE
    assert "/cancel ALERT_ID" in CANCEL_USAGE
    assert disclaimer() in CANCEL_USAGE
