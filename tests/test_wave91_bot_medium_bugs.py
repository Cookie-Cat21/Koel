"""Wave91: medium+ bot alert lookup compliance regressions."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from koel.bot import cmd_alert, reset_cmd_rate_limits
from koel.domain import disclaimer


@pytest.fixture(autouse=True)
def _clear_rate_limits() -> None:
    reset_cmd_rate_limits()
    yield
    reset_cmd_rate_limits()


def _make_update_context(
    *,
    args: list[Any],
    storage: AsyncMock,
    cse: AsyncMock,
) -> tuple[MagicMock, MagicMock]:
    message = AsyncMock()
    message.reply_text = AsyncMock()

    user = MagicMock()
    user.id = 91091

    update = MagicMock()
    update.effective_message = message
    update.effective_user = user

    application = MagicMock()
    application.bot_data = {
        "storage": storage,
        "cse": cse,
        "cmd_rate_per_minute": 20,
    }

    context = MagicMock()
    context.args = args
    context.application = application
    return update, context


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cse_result", "needle"),
    [
        (RuntimeError("cse down"), "cse.lk unreachable"),
        (None, "Couldn't find JKH.N0000"),
    ],
)
async def test_cmd_alert_lookup_failures_include_nfa_before_persist(
    cse_result: object,
    needle: str,
) -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.upsert_stock = AsyncMock()
    storage.create_alert_rule = AsyncMock()
    cse = AsyncMock()
    if isinstance(cse_result, Exception):
        cse.fetch_company_info = AsyncMock(side_effect=cse_result)
    else:
        cse.fetch_company_info = AsyncMock(return_value=cse_result)

    update, context = _make_update_context(
        args=["JKH.N0000", "above", "100"],
        storage=storage,
        cse=cse,
    )

    await cmd_alert(update, context)

    cse.fetch_company_info.assert_awaited_once_with("JKH.N0000")
    storage.ensure_user.assert_not_awaited()
    storage.upsert_stock.assert_not_awaited()
    storage.create_alert_rule.assert_not_awaited()
    reply = update.effective_message.reply_text.await_args.args[0]
    assert needle in reply
    assert disclaimer() in reply
    assert "Alert #" not in reply
