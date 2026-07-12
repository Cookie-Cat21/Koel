"""Wave20: medium+ bugs — cancel id overflow, category read sanitize, dash egress.

1. Hostile ``/cancel`` digit floods must not blow Telegram past 4096 or
   become pathological DB params (digits-only + ≤18).
2. Storage read path sanitizes poisoned disclosure categories.
3. DELETE alert id is SafeInteger/digits-only; /me rejects non-finite ids;
   disclosures strip C0/cap title/category/company/external_id.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chime.bot import cmd_cancel, parse_cancel_alert_id
from chime.domain import DISCLOSURE_CATEGORY_MAX, TELEGRAM_SAFE_MAX
from chime.storage import _row_to_rule

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_parse_cancel_alert_id_rejects_hostile_and_oversize() -> None:
    assert parse_cancel_alert_id("42") == 42
    assert parse_cancel_alert_id("#12") == 12
    assert parse_cancel_alert_id("0") is None
    assert parse_cancel_alert_id("-1") is None
    assert parse_cancel_alert_id("abc") is None
    assert parse_cancel_alert_id("12.5") is None
    # 19 digits — beyond our bigint-safe cap
    assert parse_cancel_alert_id("1" * 19) is None
    # Digit flood that used to become a multi-KB error body
    assert parse_cancel_alert_id("9" * 10_000) is None


@pytest.mark.asyncio
async def test_cmd_cancel_hostile_id_stays_under_telegram_limit() -> None:
    storage = AsyncMock()
    update = MagicMock()
    update.effective_user.id = 1001
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    context.application.bot_data = {"storage": storage}
    context.args = ["9" * 10_000]

    with patch("chime.bot._rate_limited", AsyncMock(return_value=False)):
        await cmd_cancel(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    body = update.effective_message.reply_text.await_args.args[0]
    assert len(body) < TELEGRAM_SAFE_MAX
    assert "must be a number" in body
    storage.deactivate_alert.assert_not_awaited()


@pytest.mark.asyncio
async def test_cmd_cancel_zero_still_positive_copy() -> None:
    storage = AsyncMock()
    update = MagicMock()
    update.effective_user.id = 1001
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    context.application.bot_data = {"storage": storage}
    context.args = ["0"]

    with patch("chime.bot._rate_limited", AsyncMock(return_value=False)):
        await cmd_cancel(update, context)

    body = update.effective_message.reply_text.await_args.args[0]
    assert "positive" in body
    storage.deactivate_alert.assert_not_awaited()


@pytest.mark.asyncio
async def test_cmd_cancel_success_clamped() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=1)
    storage.deactivate_alert = AsyncMock(return_value=True)
    update = MagicMock()
    update.effective_user.id = 1001
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    context.application.bot_data = {"storage": storage}
    context.args = ["#7"]

    with patch("chime.bot._rate_limited", AsyncMock(return_value=False)):
        await cmd_cancel(update, context)

    storage.deactivate_alert.assert_awaited_once_with(1, 7)
    body = update.effective_message.reply_text.await_args.args[0]
    assert body == "Cancelled alert #7."
    assert len(body) < TELEGRAM_SAFE_MAX


def test_row_to_rule_sanitizes_hostile_category() -> None:
    rule = _row_to_rule(
        {
            "id": 2,
            "user_id": 2,
            "telegram_id": 3,
            "symbol": "JKH.N0000",
            "type": "disclosure",
            "threshold": None,
            "category": "Fin\x00ancial\nReport" + ("X" * 200),
            "active": True,
            "armed": True,
            "created_at": "2026-07-11T06:00:00+00:00",
        }
    )
    assert rule.category is not None
    assert "\x00" not in rule.category
    assert "\n" not in rule.category
    assert len(rule.category) <= DISCLOSURE_CATEGORY_MAX


def test_alerts_delete_rejects_unsafe_ids() -> None:
    route = WEB / "src" / "app" / "api" / "v1" / "alerts" / "[id]" / "route.ts"
    source = route.read_text(encoding="utf-8")
    assert r"/^\d{1,15}$/" in source or "/^\\d{1,15}$/" in source
    assert "Number.isSafeInteger" in source
    assert "Number.isInteger(ruleId)" not in source


def test_me_route_fails_closed_on_nonfinite_ids() -> None:
    route = WEB / "src" / "app" / "api" / "v1" / "me" / "route.ts"
    source = route.read_text(encoding="utf-8")
    assert "toSafeId" in source
    assert "Number.isSafeInteger" in source
    # Ban raw Number(row.id) egress without guard.
    assert "id: Number(row.id)" not in source
    assert "telegram_id: Number(row.telegram_id)" not in source


def test_disclosures_route_sanitizes_text_fields() -> None:
    route = (
        WEB
        / "src"
        / "app"
        / "api"
        / "v1"
        / "symbols"
        / "[symbol]"
        / "disclosures"
        / "route.ts"
    )
    source = route.read_text(encoding="utf-8")
    assert "sanitizeDisclosureText" in source
    assert "MAX_DISCLOSURE_TITLE_LENGTH" in source
    assert "MAX_DISCLOSURE_CATEGORY_LENGTH" in source
    assert "MAX_DISCLOSURE_COMPANY_LENGTH" in source
    assert "MAX_DISCLOSURE_EXTERNAL_ID_LENGTH" in source
    # Ban raw title/category egress.
    assert "title: row.title" not in source
    assert "category: row.category" not in source
    assert "company_name: row.company_name" not in source
    assert "external_id: row.external_id" not in source
