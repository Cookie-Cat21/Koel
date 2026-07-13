"""Wave94: medium+ bot command edge regressions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from chime.bot import cmd_cancel, reset_cmd_rate_limits
from chime.domain import disclaimer


@pytest.fixture(autouse=True)
def _clear_rate_limits() -> None:
    reset_cmd_rate_limits()
    yield
    reset_cmd_rate_limits()


def _make_update_context(
    *,
    args: list[str],
    storage: AsyncMock,
) -> tuple[MagicMock, MagicMock]:
    message = AsyncMock()
    message.reply_text = AsyncMock()

    user = MagicMock()
    user.id = 94001

    update = MagicMock()
    update.effective_message = message
    update.effective_user = user

    application = MagicMock()
    application.bot_data = {
        "storage": storage,
        "cmd_rate_per_minute": 20,
    }

    context = MagicMock()
    context.args = args
    context.application = application
    return update, context


@pytest.mark.asyncio
async def test_cmd_cancel_rejects_trailing_tokens_before_deactivate() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.deactivate_alert = AsyncMock(return_value=True)

    update, context = _make_update_context(args=["7", "extra"], storage=storage)

    await cmd_cancel(update, context)

    storage.ensure_user.assert_not_awaited()
    storage.deactivate_alert.assert_not_awaited()
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Unexpected extra text" in reply
    assert "Usage: /cancel ALERT_ID" in reply
    assert "/myalerts" in reply
    assert disclaimer() in reply
