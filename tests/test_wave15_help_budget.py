"""Wave15: HELP/START line budgets still hold after the scenarios note.

Wave12 folded ``scenarios disabled (Phase 3 stub)`` into the Browse-dash
HELP line so the ≤12 non-blank budget was not expanded. This module pins
that fence: START stays ≤3, HELP stays ≤12, and the scenarios note remains
present without leaking a command dump onto ``/start``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from koel.bot import HELP_TEXT, START_TEXT, cmd_help, cmd_start, reset_cmd_rate_limits
from koel.domain import disclaimer

# Factory / WS-014 / E7-B01–B02 budgets (non-blank content lines).
_START_MAX_LINES = 3
_HELP_MAX_LINES = 12


@pytest.fixture(autouse=True)
def _clear_rate_limits() -> None:
    reset_cmd_rate_limits()
    yield
    reset_cmd_rate_limits()


def _nonblank_lines(text: str) -> list[str]:
    return [ln for ln in text.strip().splitlines() if ln.strip()]


def _make_update_context(
    *,
    storage: AsyncMock | None = None,
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
    application.bot_data = {
        "storage": storage or AsyncMock(),
        "cmd_rate_per_minute": cmd_rate_per_minute,
    }

    context = MagicMock()
    context.args = []
    context.application = application
    return update, context


def test_start_line_budget_holds_after_scenarios_note() -> None:
    lines = _nonblank_lines(START_TEXT)
    assert len(lines) <= _START_MAX_LINES
    # Current copy is exactly at the budget — keep the pitch + NFA tight.
    assert len(lines) == _START_MAX_LINES
    assert "scenarios disabled" not in START_TEXT
    assert "/watch SYMBOL" not in START_TEXT  # command dump is /help only
    assert "/help" in START_TEXT
    assert disclaimer() in START_TEXT


def test_help_line_budget_holds_with_scenarios_note() -> None:
    lines = _nonblank_lines(HELP_TEXT)
    assert len(lines) <= _HELP_MAX_LINES
    # Wave12 scenarios note must stay on the Browse-dash line (no extra row).
    assert len(lines) == _HELP_MAX_LINES
    assert "scenarios disabled" in HELP_TEXT
    assert "Phase 3 stub" in HELP_TEXT
    assert "Browse dash" in HELP_TEXT
    assert disclaimer() in HELP_TEXT
    # Scenarios note shares the Browse-dash line — not a 13th content row.
    browse_lines = [ln for ln in lines if "Browse dash" in ln]
    assert len(browse_lines) == 1
    assert "scenarios disabled" in browse_lines[0]


def test_help_still_lists_core_commands_inside_budget() -> None:
    """Budget pin must not regress the alert / watch / brief surface."""
    assert len(_nonblank_lines(HELP_TEXT)) <= _HELP_MAX_LINES
    for needle in (
        "/watch SYMBOL",
        "/unwatch SYMBOL",
        "/alert SYMBOL above PRICE",
        "/alert SYMBOL below PRICE",
        "/alert SYMBOL move PERCENT",
        "/alert SYMBOL disclosure",
        "[CATEGORY]",
        "/cancel ALERT_ID",
        "/myalerts — active only",
        "/brief SYMBOL",
        "optional AI brief",
        "Disclosure alerts:",
        "scenarios disabled",
    ):
        assert needle in HELP_TEXT


@pytest.mark.asyncio
async def test_cmd_start_reply_respects_line_budget() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=1)
    update, context = _make_update_context(storage=storage)

    await cmd_start(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert reply == START_TEXT
    assert len(_nonblank_lines(reply)) <= _START_MAX_LINES
    assert "scenarios disabled" not in reply


@pytest.mark.asyncio
async def test_cmd_help_reply_keeps_scenarios_note_inside_budget() -> None:
    update, context = _make_update_context()

    await cmd_help(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert reply == HELP_TEXT
    assert len(_nonblank_lines(reply)) <= _HELP_MAX_LINES
    assert "scenarios disabled" in reply
    assert disclaimer() in reply
