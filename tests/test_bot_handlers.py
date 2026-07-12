"""WS-068: Unit tests for cmd_cancel / cmd_unwatch — no network."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from chime.bot import cmd_cancel, cmd_unwatch
from chime.domain import disclaimer


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
async def test_cancel_missing_id_reply_actionable_and_nfa_safe() -> None:
    storage = AsyncMock()

    update, context = _make_update_context(args=[], storage=storage)
    await cmd_cancel(update, context)

    storage.deactivate_alert.assert_not_awaited()
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "/myalerts" in reply
    assert "Usage: /cancel ALERT_ID" in reply
    assert "Example: /cancel 7" in reply
    assert disclaimer() in reply


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
    storage.unwatch_symbol = AsyncMock(return_value=(True, 2))

    update, context = _make_update_context(args=["JKH.N0000"], storage=storage)
    await cmd_unwatch(update, context)

    storage.unwatch_symbol.assert_awaited_once_with(42, "JKH.N0000")
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Stopped watching JKH.N0000" in reply
    assert "Deactivated 2 alert(s)" in reply
    assert "no more pushes" in reply


@pytest.mark.asyncio
async def test_unwatch_success_without_alerts_confirms_no_fire() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.unwatch_symbol = AsyncMock(return_value=(True, 0))

    update, context = _make_update_context(args=["JKH.N0000"], storage=storage)
    await cmd_unwatch(update, context)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Stopped watching JKH.N0000" in reply
    assert "won't fire" in reply
    assert "Deactivated" not in reply


@pytest.mark.asyncio
async def test_unwatch_orphan_rules_honest_message() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.unwatch_symbol = AsyncMock(return_value=(False, 1))

    update, context = _make_update_context(args=["JKH.N0000"], storage=storage)
    await cmd_unwatch(update, context)

    storage.unwatch_symbol.assert_awaited_once_with(42, "JKH.N0000")
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "wasn't on your watchlist" in reply
    assert "orphan alert" in reply
    assert "won't fire" in reply


@pytest.mark.asyncio
async def test_unwatch_not_on_list_reply_is_actionable() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.unwatch_symbol = AsyncMock(return_value=(False, 0))

    update, context = _make_update_context(args=["JKH.N0000"], storage=storage)
    await cmd_unwatch(update, context)

    storage.unwatch_symbol.assert_awaited_once_with(42, "JKH.N0000")
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "JKH.N0000 wasn't on your watchlist" in reply
    assert "/mywatchlist" in reply
    assert "/watch JKH.N0000" in reply
