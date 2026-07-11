"""WS-068: Unit tests for cmd_cancel / cmd_unwatch — no network."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from chime.bot import cmd_cancel, cmd_unwatch


def _make_update_context(
    *,
    args: list[str],
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
    context.args = args
    context.application = application
    return update, context


@pytest.mark.asyncio
async def test_cancel_missing_id_replies_kind_error() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.deactivate_alert = AsyncMock(return_value=False)

    update, context = _make_update_context(args=["99"], storage=storage)
    await cmd_cancel(update, context)

    storage.deactivate_alert.assert_awaited_once_with(42, 99)
    update.effective_message.reply_text.assert_awaited_once()
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "No active alert #99" in reply
    assert "/myalerts" in reply


@pytest.mark.asyncio
async def test_cancel_success() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.deactivate_alert = AsyncMock(return_value=True)

    update, context = _make_update_context(args=["7"], storage=storage)
    await cmd_cancel(update, context)

    storage.deactivate_alert.assert_awaited_once_with(42, 7)
    update.effective_message.reply_text.assert_awaited_once_with("Cancelled alert #7.")


@pytest.mark.asyncio
async def test_unwatch_deactivates_rules_for_symbol() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.remove_watch = AsyncMock(return_value=True)
    storage.deactivate_rules_for_symbol = AsyncMock(return_value=2)

    update, context = _make_update_context(args=["JKH.N0000"], storage=storage)
    await cmd_unwatch(update, context)

    storage.remove_watch.assert_awaited_once_with(42, "JKH.N0000")
    storage.deactivate_rules_for_symbol.assert_awaited_once_with(42, "JKH.N0000")
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Removed JKH.N0000" in reply
    assert "Deactivated 2 alert(s)." in reply
