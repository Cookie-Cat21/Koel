"""Wave17: medium+ egress / lease bugs that prior harden still missed.

1. Dead-letter Telegram notify must stay under 4096 even with a hostile DB
   symbol (oversize notify fails the one-shot user message).
2. Non-finite / unconvertible ``attempts`` must not raise out of
   ``format_dead_letter_notify``.
3. ``/myalerts`` must not TypeError on null / NaN price thresholds.
4. Claim lease_seconds of 0 / negative must floor to >= 1 so unsent drain
   cannot immediately re-claim an in-flight send.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from koel.bot import cmd_myalerts, cmd_mywatchlist
from koel.domain import (
    TELEGRAM_SAFE_MAX,
    AlertRule,
    AlertType,
    format_dead_letter_notify,
)
from koel.storage import Storage


def test_dead_letter_notify_caps_hostile_symbol_under_telegram_limit() -> None:
    msg = format_dead_letter_notify("S" * 10_000 + "\x00\n", 5)
    assert len(msg) < TELEGRAM_SAFE_MAX
    assert "\x00" not in msg
    assert "\n" not in msg
    assert "after 5 tries" in msg
    assert "Not financial advice" in msg
    assert "…" in msg  # truncated symbol


@pytest.mark.parametrize("attempts", [float("nan"), float("inf"), float("-inf"), "nope", None])
def test_dead_letter_notify_nonfinite_attempts_fail_closed(attempts: object) -> None:
    msg = format_dead_letter_notify("JKH.N0000", attempts)  # type: ignore[arg-type]
    assert "after 0 tries" in msg
    assert "Not financial advice" in msg


def test_dead_letter_notify_negative_attempts_fail_closed() -> None:
    assert "after 0 tries" in format_dead_letter_notify("JKH.N0000", -3)


def test_dead_letter_notify_caps_pathological_attempt_display() -> None:
    msg = format_dead_letter_notify("JKH.N0000", 10**100)
    assert len(msg) < TELEGRAM_SAFE_MAX
    assert "after 1000000 tries" in msg


@pytest.mark.asyncio
async def test_myalerts_null_threshold_does_not_crash() -> None:
    """Corrupt price_above row with null threshold must not TypeError /myalerts."""
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=1)
    storage.list_alerts = AsyncMock(
        return_value=[
            AlertRule(
                id=7,
                user_id=1,
                telegram_id=1001,
                symbol="JKH.N0000",
                type=AlertType.PRICE_ABOVE,
                threshold=None,
                active=True,
            ),
            AlertRule(
                id=8,
                user_id=1,
                telegram_id=1001,
                symbol="COMB.N0000",
                type=AlertType.DAILY_MOVE,
                threshold=float("nan"),
                active=True,
            ),
            AlertRule(
                id=9,
                user_id=1,
                telegram_id=1001,
                symbol="SAMP\x00.N0000",
                type=AlertType.DISCLOSURE,
                threshold=None,
                category="Rights\nIssue",
                active=True,
                created_at=datetime(2026, 7, 1, tzinfo=UTC),
            ),
            AlertRule(
                id=10,
                user_id=1,
                telegram_id=1001,
                symbol="LOLC.N0000",
                type=AlertType.DISCLOSURE,
                threshold=None,
                category="\x00\x01",
                active=True,
                created_at=datetime(2026, 7, 1, tzinfo=UTC),
            ),
            AlertRule(
                id=11,
                user_id=1,
                telegram_id=1001,
                symbol="HNB.N0000",
                type=AlertType.PRICE_BELOW,
                threshold=50.0,
                active=True,
            ),
        ]
    )
    update = MagicMock()
    update.effective_user.id = 1001
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    context.application.bot_data = {"storage": storage}
    context.args = []

    with patch("koel.bot._rate_limited", AsyncMock(return_value=False)):
        await cmd_myalerts(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    body = update.effective_message.reply_text.await_args.args[0]
    assert "#7 JKH.N0000 above ?" in body
    assert "#8 COMB.N0000 move ?%" in body
    assert "#9 SAMP.N0000 disclosure RightsIssue" in body
    assert "#10 LOLC.N0000 disclosure" in body
    assert "#11 HNB.N0000 below 50" in body
    assert "\x00" not in body
    assert "Not financial advice" in body
    assert len(body) < TELEGRAM_SAFE_MAX


@pytest.mark.asyncio
async def test_mywatchlist_strips_controls_and_clamps() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=1)
    storage.list_watchlist = AsyncMock(return_value=["JKH\x00.N0000", "COMB.N0000"])
    update = MagicMock()
    update.effective_user.id = 1001
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    context.application.bot_data = {"storage": storage}

    with patch("koel.bot._rate_limited", AsyncMock(return_value=False)):
        await cmd_mywatchlist(update, context)

    body = update.effective_message.reply_text.await_args.args[0]
    assert "\x00" not in body
    assert "JKH.N0000" in body
    assert "COMB.N0000" in body


def test_claim_lease_seconds_floored_in_source() -> None:
    """Zero/negative lease must floor to >=1 (grep-level pin on Storage methods)."""
    import inspect

    for name in ("claim_alert", "claim_and_disarm", "claim_unsent_batch", "claim_brief_followups"):
        src = inspect.getsource(getattr(Storage, name))
        assert "max(1, int(lease_seconds))" in src, name
