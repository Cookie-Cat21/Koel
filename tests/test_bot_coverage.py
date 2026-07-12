"""E4-C02: Bot handler coverage + parametrized rate-limit across commands."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from chime.bot import (
    RATE_LIMIT_REPLY,
    allow_command,
    cmd_alert,
    cmd_cancel,
    cmd_help,
    cmd_myalerts,
    cmd_mywatchlist,
    cmd_start,
    cmd_unwatch,
    cmd_watch,
    reset_cmd_rate_limits,
    watch_upstream_error,
)
from chime.domain import AlertRule, AlertType, PriceSnapshot, disclaimer


@pytest.fixture(autouse=True)
def _clear_rate_limits() -> None:
    reset_cmd_rate_limits()
    yield
    reset_cmd_rate_limits()


def _make_update_context(
    *,
    args: list[str] | None = None,
    storage: AsyncMock | None = None,
    cse: AsyncMock | None = None,
    telegram_id: int = 1001,
    cmd_rate_per_minute: int = 20,
) -> tuple[MagicMock, MagicMock]:
    message = AsyncMock()
    message.reply_text = AsyncMock()

    user = MagicMock()
    user.id = telegram_id

    update = MagicMock()
    update.effective_message = message
    update.effective_user = user

    application = MagicMock()
    bot_data: dict = {
        "storage": storage or AsyncMock(),
        "cmd_rate_per_minute": cmd_rate_per_minute,
    }
    if cse is not None:
        bot_data["cse"] = cse
    application.bot_data = bot_data

    context = MagicMock()
    context.args = args or []
    context.application = application
    return update, context


def _snap(symbol: str = "JKH.N0000") -> PriceSnapshot:
    return PriceSnapshot(
        symbol=symbol,
        price=100.0,
        name="John Keells",
        ts=datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "handler,args",
    [
        (cmd_start, []),
        (cmd_help, []),
        (cmd_watch, ["JKH.N0000"]),
        (cmd_unwatch, ["JKH.N0000"]),
        (cmd_alert, ["JKH.N0000", "above", "100"]),
        (cmd_cancel, ["1"]),
        (cmd_myalerts, []),
        (cmd_mywatchlist, []),
    ],
)
async def test_all_handlers_rate_limited(
    handler: object,
    args: list[str],
) -> None:
    storage = AsyncMock()
    cse = AsyncMock()
    cse.fetch_company_info = AsyncMock()
    update, context = _make_update_context(
        args=args,
        storage=storage,
        cse=cse,
        telegram_id=4242,
        cmd_rate_per_minute=1,
    )
    assert allow_command(4242, 1) is True
    await handler(update, context)  # type: ignore[operator]
    update.effective_message.reply_text.assert_awaited_once_with(RATE_LIMIT_REPLY)
    cse.fetch_company_info.assert_not_called()
    storage.ensure_user.assert_not_called()


@pytest.mark.asyncio
async def test_cmd_start_registers_and_explains() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=7)
    update, context = _make_update_context(storage=storage)
    await cmd_start(update, context)
    storage.ensure_user.assert_awaited_once_with(1001)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Chime watches" in reply
    assert "/help" in reply
    assert "/watch SYMBOL" not in reply  # command dump is /help only
    assert disclaimer() in reply
    assert len([ln for ln in reply.strip().splitlines() if ln.strip()]) <= 3


@pytest.mark.asyncio
async def test_cmd_help_lists_commands() -> None:
    update, context = _make_update_context()
    await cmd_help(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "/watch SYMBOL" in reply
    assert "/alert SYMBOL disclosure" in reply
    assert len([ln for ln in reply.strip().splitlines() if ln.strip()]) <= 12


@pytest.mark.asyncio
async def test_cmd_watch_usage_and_bad_symbol() -> None:
    storage = AsyncMock()
    cse = AsyncMock()
    update, context = _make_update_context(args=[], storage=storage, cse=cse)
    await cmd_watch(update, context)
    assert "Usage: /watch" in update.effective_message.reply_text.await_args.args[0]

    update2, context2 = _make_update_context(args=["!!!"], storage=storage, cse=cse)
    await cmd_watch(update2, context2)
    reply = update2.effective_message.reply_text.await_args.args[0]
    assert "doesn't look like a CSE symbol" in reply
    assert "JKH.N0000" in reply


@pytest.mark.asyncio
async def test_cmd_watch_upstream_and_not_found() -> None:
    storage = AsyncMock()
    cse = AsyncMock()
    cse.fetch_company_info = AsyncMock(side_effect=RuntimeError("down"))
    update, context = _make_update_context(args=["JKH.N0000"], storage=storage, cse=cse)
    await cmd_watch(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert reply == watch_upstream_error("JKH.N0000")
    assert "couldn't verify JKH.N0000" in reply
    assert "Nothing was added" in reply
    assert disclaimer() in reply
    storage.upsert_stock.assert_not_called()
    storage.add_watch.assert_not_called()

    cse2 = AsyncMock()
    cse2.fetch_company_info = AsyncMock(return_value=None)
    update2, context2 = _make_update_context(args=["ZZZ.N0000"], storage=storage, cse=cse2)
    await cmd_watch(update2, context2)
    assert "Couldn't find" in update2.effective_message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_cmd_unwatch_not_on_list() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.unwatch_symbol = AsyncMock(return_value=(False, 0))
    update, context = _make_update_context(args=["JKH.N0000"], storage=storage)
    await cmd_unwatch(update, context)
    assert "wasn't on your watchlist" in update.effective_message.reply_text.await_args.args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "args,needle",
    [
        (["JKH.N0000", "above", "100"], "crosses above 100"),
        (["JKH.N0000", "below", "50"], "crosses below 50"),
        (["JKH.N0000", "move", "5"], "daily move ≥ 5%"),
        (["JKH.N0000", "disclosure"], "new disclosure"),
    ],
)
async def test_cmd_alert_kinds(args: list[str], needle: str) -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.upsert_stock = AsyncMock()
    storage.create_alert_rule = AsyncMock(
        return_value=AlertRule(
            id=9,
            user_id=42,
            telegram_id=1001,
            symbol="JKH.N0000",
            type=AlertType.PRICE_ABOVE,
            threshold=100.0,
        )
    )
    cse = AsyncMock()
    cse.fetch_company_info = AsyncMock(return_value=_snap())
    update, context = _make_update_context(args=args, storage=storage, cse=cse)
    await cmd_alert(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Alert #9 set:" in reply
    assert needle in reply
    assert disclaimer() in reply


@pytest.mark.asyncio
async def test_cmd_alert_validation_errors() -> None:
    storage = AsyncMock()
    cse = AsyncMock()
    update, context = _make_update_context(args=["JKH.N0000"], storage=storage, cse=cse)
    await cmd_alert(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "couldn't parse" in reply.lower()
    assert "/alert SYMBOL above" in reply

    update2, context2 = _make_update_context(
        args=["JKH.N0000", "above"], storage=storage, cse=cse
    )
    await cmd_alert(update2, context2)
    assert "need a number" in update2.effective_message.reply_text.await_args.args[0].lower()

    update3, context3 = _make_update_context(
        args=["JKH.N0000", "above", "nope"], storage=storage, cse=cse
    )
    await cmd_alert(update3, context3)
    assert "must be a number" in update3.effective_message.reply_text.await_args.args[0]

    update4, context4 = _make_update_context(
        args=["JKH.N0000", "above", "-1"], storage=storage, cse=cse
    )
    await cmd_alert(update4, context4)
    assert "positive" in update4.effective_message.reply_text.await_args.args[0]

    update5, context5 = _make_update_context(
        args=["JKH.N0000", "sideways", "1"], storage=storage, cse=cse
    )
    await cmd_alert(update5, context5)
    reply5 = update5.effective_message.reply_text.await_args.args[0]
    assert "didn't catch that alert type" in reply5.lower()
    assert "above" in reply5

    update6, context6 = _make_update_context(args=["!!!", "above", "1"], storage=storage, cse=cse)
    await cmd_alert(update6, context6)
    reply6 = update6.effective_message.reply_text.await_args.args[0]
    assert "doesn't look like a CSE symbol" in reply6
    assert "JKH.N0000" in reply6


@pytest.mark.asyncio
async def test_cmd_cancel_validation() -> None:
    storage = AsyncMock()
    update, context = _make_update_context(args=[], storage=storage)
    await cmd_cancel(update, context)
    assert "Usage: /cancel" in update.effective_message.reply_text.await_args.args[0]

    update2, context2 = _make_update_context(args=["abc"], storage=storage)
    await cmd_cancel(update2, context2)
    assert "must be a number" in update2.effective_message.reply_text.await_args.args[0]

    update3, context3 = _make_update_context(args=["0"], storage=storage)
    await cmd_cancel(update3, context3)
    assert "positive" in update3.effective_message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_cmd_myalerts_empty_and_formatted() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.list_alerts = AsyncMock(return_value=[])
    update, context = _make_update_context(storage=storage)
    await cmd_myalerts(update, context)
    empty_reply = update.effective_message.reply_text.await_args.args[0]
    assert "No active alerts" in empty_reply
    assert "/alert JKH.N0000 above 100" in empty_reply
    assert "/alert JKH.N0000 below 90" in empty_reply
    assert "/alert JKH.N0000 move 5" in empty_reply
    assert "/alert JKH.N0000 disclosure" in empty_reply
    assert disclaimer() in empty_reply

    rules = [
        AlertRule(
            id=1,
            user_id=42,
            telegram_id=1001,
            symbol="JKH.N0000",
            type=AlertType.PRICE_ABOVE,
            threshold=100.0,
        ),
        AlertRule(
            id=2,
            user_id=42,
            telegram_id=1001,
            symbol="COMB.N0000",
            type=AlertType.PRICE_BELOW,
            threshold=50.0,
        ),
        AlertRule(
            id=3,
            user_id=42,
            telegram_id=1001,
            symbol="SAMP.N0000",
            type=AlertType.DAILY_MOVE,
            threshold=5.0,
        ),
        AlertRule(
            id=4,
            user_id=42,
            telegram_id=1001,
            symbol="HNB.N0000",
            type=AlertType.DISCLOSURE,
            threshold=None,
        ),
    ]
    storage.list_alerts = AsyncMock(return_value=rules)
    update2, context2 = _make_update_context(storage=storage)
    await cmd_myalerts(update2, context2)
    reply = update2.effective_message.reply_text.await_args.args[0]
    assert "#1 JKH.N0000 above 100" in reply
    assert "#2 COMB.N0000 below 50" in reply
    assert "#3 SAMP.N0000 move 5%" in reply
    assert "#4 HNB.N0000 disclosure" in reply
    assert disclaimer() in reply


@pytest.mark.asyncio
async def test_cmd_mywatchlist_empty_and_list() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.list_watchlist = AsyncMock(return_value=[])
    update, context = _make_update_context(storage=storage)
    await cmd_mywatchlist(update, context)
    empty_reply = update.effective_message.reply_text.await_args.args[0]
    assert "Watchlist empty" in empty_reply
    assert "/watch SYMBOL" in empty_reply
    assert "Example: /watch JKH.N0000" in empty_reply

    storage.list_watchlist = AsyncMock(return_value=["COMB.N0000", "JKH.N0000"])
    update2, context2 = _make_update_context(storage=storage)
    await cmd_mywatchlist(update2, context2)
    reply = update2.effective_message.reply_text.await_args.args[0]
    assert "Watchlist:" in reply
    assert "JKH.N0000" in reply


@pytest.mark.asyncio
async def test_cmd_alert_disclosure_category() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.upsert_stock = AsyncMock()

    async def _create(
        user_id: int,
        symbol: str,
        alert_type: AlertType,
        threshold: float | None,
        category: str | None = None,
    ) -> AlertRule:
        return AlertRule(
            id=9,
            user_id=user_id,
            telegram_id=1001,
            symbol=symbol,
            type=alert_type,
            threshold=threshold,
            category=category,
        )

    storage.create_alert_rule = AsyncMock(side_effect=_create)
    cse = AsyncMock()
    cse.fetch_company_info = AsyncMock(return_value=_snap())
    update, context = _make_update_context(
        args=["JKH.N0000", "disclosure", "Financial"], storage=storage, cse=cse
    )
    await cmd_alert(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "matching category 'Financial'" in reply
    assert storage.create_alert_rule.await_args.kwargs.get("category") == "Financial"


@pytest.mark.asyncio
async def test_cmd_myalerts_shows_disclosure_category() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.list_alerts = AsyncMock(
        return_value=[
            AlertRule(
                id=5,
                user_id=42,
                telegram_id=1001,
                symbol="JKH.N0000",
                type=AlertType.DISCLOSURE,
                threshold=None,
                category="Financial",
            )
        ]
    )
    update, context = _make_update_context(storage=storage)
    await cmd_myalerts(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "#5 JKH.N0000 disclosure Financial" in reply
