"""W4: /start inline keyboard + deep-link watch confirm."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import InlineKeyboardMarkup

from koel.bot import (
    cmd_start,
    on_callback_query,
    parse_start_deep_link,
    reset_cmd_rate_limits,
)
from koel.bot_keyboards import WATCH_HELP_TEXT, start_menu_keyboard
from koel.domain import PriceSnapshot, disclaimer


@pytest.fixture(autouse=True)
def _clear_rate_limits() -> None:
    reset_cmd_rate_limits()
    yield
    reset_cmd_rate_limits()


def _make_update_context(
    *,
    args: list[str] | None = None,
    storage: AsyncMock,
    cse: AsyncMock | None = None,
    telegram_id: int = 4242,
    callback_data: str | None = None,
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
    bot_data: dict = {"storage": storage, "cmd_rate_per_minute": 100}
    if cse is not None:
        bot_data["cse"] = cse
    application.bot_data = bot_data
    context = MagicMock()
    context.args = args or []
    context.application = application
    return update, context


def test_parse_start_deep_link_sym_and_watch() -> None:
    assert parse_start_deep_link(["sym_JKH.N0000"]) == "JKH.N0000"
    assert parse_start_deep_link(["watch_COMB.N0000"]) == "COMB.N0000"
    assert parse_start_deep_link(["sym_jkh.n0000"]) == "JKH.N0000"
    assert parse_start_deep_link([]) is None
    assert parse_start_deep_link(["nope"]) is None
    assert parse_start_deep_link(["sym_BAD SYMBOL"]) is None


@pytest.mark.asyncio
async def test_cmd_start_sends_reply_markup() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=1)
    update, context = _make_update_context(args=[], storage=storage)

    await cmd_start(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    args, kwargs = update.effective_message.reply_text.await_args
    assert "koel watches the Colombo Stock Exchange" in args[0]
    assert disclaimer() in args[0]
    markup = kwargs.get("reply_markup")
    assert isinstance(markup, InlineKeyboardMarkup)
    # Same shape as the shared helper (callback_data targets).
    expected = start_menu_keyboard()
    got_data = {
        btn.callback_data
        for row in markup.inline_keyboard
        for btn in row
    }
    exp_data = {
        btn.callback_data
        for row in expected.inline_keyboard
        for btn in row
    }
    assert got_data == exp_data
    assert "menu:watch_help" in got_data
    assert "menu:myalerts" in got_data
    assert "menu:mywatchlist" in got_data
    assert "menu:help" in got_data


@pytest.mark.asyncio
async def test_cmd_start_deep_link_sym_jkh() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=1)
    update, context = _make_update_context(
        args=["sym_JKH.N0000"], storage=storage
    )

    await cmd_start(update, context)

    assert update.effective_message.reply_text.await_count == 2
    first = update.effective_message.reply_text.await_args_list[0]
    assert isinstance(first.kwargs.get("reply_markup"), InlineKeyboardMarkup)
    second = update.effective_message.reply_text.await_args_list[1]
    assert "Watch JKH.N0000?" in second.args[0]
    assert "/watch JKH.N0000" in second.args[0]
    confirm = second.kwargs.get("reply_markup")
    assert isinstance(confirm, InlineKeyboardMarkup)
    callbacks = {
        btn.callback_data
        for row in confirm.inline_keyboard
        for btn in row
    }
    assert callbacks == {"watch:JKH.N0000"}


@pytest.mark.asyncio
async def test_callback_menu_watch_help() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=1)
    update, context = _make_update_context(
        storage=storage, callback_data="menu:watch_help"
    )

    await on_callback_query(update, context)

    update.callback_query.answer.assert_awaited_once()
    update.effective_message.reply_text.assert_awaited_once_with(WATCH_HELP_TEXT)


@pytest.mark.asyncio
async def test_callback_watch_adds_symbol() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=7)
    storage.upsert_stock = AsyncMock()
    storage.add_watch = AsyncMock()
    cse = AsyncMock()
    cse.fetch_company_info = AsyncMock(
        return_value=PriceSnapshot(
            symbol="JKH.N0000",
            price=20.0,
            name="John Keells Holdings PLC",
            ts=datetime(2026, 7, 13, 5, 0, tzinfo=UTC),
        )
    )
    update, context = _make_update_context(
        storage=storage, cse=cse, callback_data="watch:JKH.N0000"
    )

    await on_callback_query(update, context)

    update.callback_query.answer.assert_awaited_once()
    storage.add_watch.assert_awaited_once_with(7, "JKH.N0000")
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Watching JKH.N0000" in reply
    assert disclaimer() in reply
