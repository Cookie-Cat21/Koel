"""Per-user in-memory command rate limit (no DB)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from koel.bot import (
    RATE_LIMIT_REPLY,
    allow_command,
    cmd_alert,
    cmd_brief,
    cmd_watch,
    reset_cmd_rate_limits,
)


@pytest.fixture(autouse=True)
def _clear_rate_limits() -> None:
    reset_cmd_rate_limits()
    yield
    reset_cmd_rate_limits()


def test_rate_limit_reply_includes_retry_hint() -> None:
    assert "Try again" in RATE_LIMIT_REPLY
    assert "minute" in RATE_LIMIT_REPLY


def test_rate_limit_reply_is_nfa_neutral() -> None:
    assert "Not financial advice" in RATE_LIMIT_REPLY
    assert "informational only" in RATE_LIMIT_REPLY
    assert "buy" not in RATE_LIMIT_REPLY.lower()
    assert "sell" not in RATE_LIMIT_REPLY.lower()


def test_allow_command_sliding_window() -> None:
    tid = 42
    assert allow_command(tid, limit=3, now=100.0) is True
    assert allow_command(tid, limit=3, now=101.0) is True
    assert allow_command(tid, limit=3, now=102.0) is True
    assert allow_command(tid, limit=3, now=103.0) is False
    # After window slides past first hit
    assert allow_command(tid, limit=3, now=160.0) is True


def test_allow_command_isolates_users() -> None:
    assert allow_command(1, limit=1, now=1.0) is True
    assert allow_command(1, limit=1, now=2.0) is False
    assert allow_command(2, limit=1, now=2.0) is True


def test_allow_command_limit_zero_disables() -> None:
    assert allow_command(99, limit=0, now=1.0) is True
    assert allow_command(99, limit=0, now=2.0) is True


def _make_update_context(
    *,
    args: list[str],
    storage: AsyncMock,
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
    bot_data: dict = {"storage": storage, "cmd_rate_per_minute": cmd_rate_per_minute}
    if cse is not None:
        bot_data["cse"] = cse
    application.bot_data = bot_data

    context = MagicMock()
    context.args = args
    context.application = application
    return update, context


@pytest.mark.asyncio
async def test_watch_over_limit_replies_slow_down_no_cse() -> None:
    storage = AsyncMock()
    cse = AsyncMock()
    cse.fetch_company_info = AsyncMock()

    update, context = _make_update_context(
        args=["JKH.N0000"],
        storage=storage,
        cse=cse,
        telegram_id=777,
        cmd_rate_per_minute=2,
    )
    # Exhaust budget with real monotonic time (same clock as handlers)
    assert allow_command(777, 2) is True
    assert allow_command(777, 2) is True

    await cmd_watch(update, context)

    update.effective_message.reply_text.assert_awaited_once_with(RATE_LIMIT_REPLY)
    cse.fetch_company_info.assert_not_called()
    storage.add_watch.assert_not_called()


@pytest.mark.asyncio
async def test_alert_over_limit_replies_slow_down_no_cse() -> None:
    storage = AsyncMock()
    cse = AsyncMock()
    cse.fetch_company_info = AsyncMock()

    update, context = _make_update_context(
        args=["JKH.N0000", "above", "100"],
        storage=storage,
        cse=cse,
        telegram_id=888,
        cmd_rate_per_minute=1,
    )
    assert allow_command(888, 1) is True

    await cmd_alert(update, context)

    update.effective_message.reply_text.assert_awaited_once_with(RATE_LIMIT_REPLY)
    cse.fetch_company_info.assert_not_called()
    storage.create_alert_rule.assert_not_called()


@pytest.mark.asyncio
async def test_watch_under_limit_still_hits_cse() -> None:
    from datetime import UTC, datetime

    from koel.domain import PriceSnapshot

    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.upsert_stock = AsyncMock()
    storage.add_watch = AsyncMock()

    snap = PriceSnapshot(
        symbol="JKH.N0000",
        price=100.0,
        name="John Keells",
        ts=datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
    )
    cse = AsyncMock()
    cse.fetch_company_info = AsyncMock(return_value=snap)

    update, context = _make_update_context(
        args=["JKH.N0000"],
        storage=storage,
        cse=cse,
        telegram_id=999,
        cmd_rate_per_minute=20,
    )
    await cmd_watch(update, context)

    cse.fetch_company_info.assert_awaited_once()
    storage.add_watch.assert_awaited_once()
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Watching JKH.N0000" in reply
    assert RATE_LIMIT_REPLY not in reply


@pytest.mark.asyncio
async def test_brief_over_limit_replies_slow_down_no_storage() -> None:
    storage = AsyncMock()
    storage.get_latest_ready_brief = AsyncMock()

    update, context = _make_update_context(
        args=["JKH.N0000"],
        storage=storage,
        telegram_id=555,
        cmd_rate_per_minute=1,
    )
    assert allow_command(555, 1) is True

    await cmd_brief(update, context)

    update.effective_message.reply_text.assert_awaited_once_with(RATE_LIMIT_REPLY)
    storage.get_latest_ready_brief.assert_not_called()


@pytest.mark.asyncio
async def test_brief_under_limit_still_looks_up() -> None:
    storage = AsyncMock()
    storage.get_latest_ready_brief = AsyncMock(return_value=None)

    update, context = _make_update_context(
        args=["JKH.N0000"],
        storage=storage,
        telegram_id=556,
        cmd_rate_per_minute=20,
    )
    await cmd_brief(update, context)

    storage.get_latest_ready_brief.assert_awaited_once_with("JKH.N0000")
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "JKH.N0000: AI briefs are off" in reply
    assert RATE_LIMIT_REPLY not in reply


@pytest.mark.asyncio
async def test_brief_shares_cmd_rate_budget_with_watch() -> None:
    """Successful /watch consumes the shared per-user budget; /brief is limited too."""
    from datetime import UTC, datetime

    from koel.domain import PriceSnapshot

    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.upsert_stock = AsyncMock()
    storage.add_watch = AsyncMock()
    storage.get_latest_ready_brief = AsyncMock()

    snap = PriceSnapshot(
        symbol="JKH.N0000",
        price=100.0,
        name="John Keells",
        ts=datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
    )
    cse = AsyncMock()
    cse.fetch_company_info = AsyncMock(return_value=snap)

    watch_update, watch_context = _make_update_context(
        args=["JKH.N0000"],
        storage=storage,
        cse=cse,
        telegram_id=557,
        cmd_rate_per_minute=1,
    )
    await cmd_watch(watch_update, watch_context)
    cse.fetch_company_info.assert_awaited_once()
    storage.add_watch.assert_awaited_once()

    brief_update, brief_context = _make_update_context(
        args=["JKH.N0000"],
        storage=storage,
        telegram_id=557,
        cmd_rate_per_minute=1,
    )
    await cmd_brief(brief_update, brief_context)
    brief_update.effective_message.reply_text.assert_awaited_once_with(RATE_LIMIT_REPLY)
    storage.get_latest_ready_brief.assert_not_called()


def test_build_application_stores_rate_from_arg() -> None:
    from koel.bot import build_application

    storage = MagicMock()
    cse = MagicMock()
    with patch("koel.bot.Application") as App:
        builder = MagicMock()
        App.builder.return_value = builder
        builder.token.return_value = builder
        builder.connect_timeout.return_value = builder
        builder.read_timeout.return_value = builder
        builder.write_timeout.return_value = builder
        builder.pool_timeout.return_value = builder
        app = MagicMock()
        app.bot_data = {}
        builder.build.return_value = app

        build_application("tok", storage, cse, cmd_rate_per_minute=7)
        assert app.bot_data["cmd_rate_per_minute"] == 7


def test_all_command_handlers_share_rate_limit_gate() -> None:
    """Every registered cmd_* handler (incl. /brief) must call _rate_limited first."""
    import inspect

    from koel import bot as bot_mod
    from koel.bot import (
        cmd_alert,
        cmd_brief,
        cmd_cancel,
        cmd_help,
        cmd_myalerts,
        cmd_mywatchlist,
        cmd_start,
        cmd_unwatch,
        cmd_watch,
    )

    handlers = (
        cmd_start,
        cmd_help,
        cmd_watch,
        cmd_unwatch,
        cmd_alert,
        cmd_cancel,
        cmd_myalerts,
        cmd_mywatchlist,
        cmd_brief,
    )
    for handler in handlers:
        src = inspect.getsource(handler)
        assert "await _rate_limited(" in src, f"{handler.__name__} missing rate limit"
    # /brief must remain registered alongside the shared gate.
    build_src = inspect.getsource(bot_mod.build_application)
    assert 'CommandHandler("brief", cmd_brief)' in build_src
