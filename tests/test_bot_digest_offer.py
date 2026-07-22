"""W8: digest-by-default offer on /start + prefs:digest_on callback."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import InlineKeyboardMarkup

from koel.bot import cmd_start, on_callback_query, reset_cmd_rate_limits
from koel.bot_keyboards import (
    DIGEST_ENABLED_CONFIRM,
    DIGEST_OFFER_TEXT,
    digest_offer_keyboard,
)
from koel.domain import disclaimer


@pytest.fixture(autouse=True)
def _clear_rate_limits() -> None:
    reset_cmd_rate_limits()
    yield
    reset_cmd_rate_limits()


def _make_update_context(
    *,
    storage: AsyncMock,
    telegram_id: int = 4242,
    callback_data: str | None = None,
    args: list[str] | None = None,
) -> tuple[MagicMock, MagicMock]:
    message = AsyncMock()
    message.reply_text = AsyncMock()
    user = MagicMock()
    user.id = telegram_id
    update = MagicMock()
    update.effective_message = message
    update.effective_user = user
    if callback_data is not None:
        query = AsyncMock()
        query.answer = AsyncMock()
        query.data = callback_data
        query.message = message
        update.callback_query = query
    else:
        update.callback_query = None
    application = MagicMock()
    application.bot_data = {"storage": storage, "cmd_rate_per_minute": 100}
    context = MagicMock()
    context.args = args or []
    context.application = application
    return update, context


@pytest.mark.asyncio
async def test_cmd_start_offers_digest_when_off() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=9)
    storage.get_user_preferences = AsyncMock(
        return_value={"digest_enabled": False}
    )
    update, context = _make_update_context(storage=storage)

    await cmd_start(update, context)

    assert update.effective_message.reply_text.await_count == 2
    second = update.effective_message.reply_text.await_args_list[1]
    assert second.args[0] == DIGEST_OFFER_TEXT
    markup = second.kwargs.get("reply_markup")
    assert isinstance(markup, InlineKeyboardMarkup)
    callbacks = {
        btn.callback_data
        for row in markup.inline_keyboard
        for btn in row
    }
    assert callbacks == {"prefs:digest_on"}
    expected = digest_offer_keyboard()
    exp = {
        btn.callback_data
        for row in expected.inline_keyboard
        for btn in row
    }
    assert callbacks == exp


@pytest.mark.asyncio
async def test_cmd_start_skips_offer_when_digest_already_on() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=9)
    storage.get_user_preferences = AsyncMock(
        return_value={"digest_enabled": True}
    )
    update, context = _make_update_context(storage=storage)

    await cmd_start(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    storage.update_user_preferences.assert_not_called()


@pytest.mark.asyncio
async def test_callback_prefs_digest_on_enables() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=11)
    storage.update_user_preferences = AsyncMock(
        return_value={"digest_enabled": True}
    )
    update, context = _make_update_context(
        storage=storage, callback_data="prefs:digest_on"
    )

    await on_callback_query(update, context)

    update.callback_query.answer.assert_awaited_once()
    storage.update_user_preferences.assert_awaited_once_with(
        11, digest_enabled=True
    )
    update.effective_message.reply_text.assert_awaited_once_with(
        DIGEST_ENABLED_CONFIRM
    )
    assert disclaimer() in DIGEST_ENABLED_CONFIRM


@pytest.mark.asyncio
async def test_callback_prefs_digest_on_fails_closed() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=11)
    storage.update_user_preferences = AsyncMock(return_value=None)
    update, context = _make_update_context(
        storage=storage, callback_data="prefs:digest_on"
    )

    await on_callback_query(update, context)

    text = update.effective_message.reply_text.await_args.args[0]
    assert "Couldn't enable" in text
    assert disclaimer() in text
