"""Wave18: medium+ bugs — category confirm overflow, history egress, health nested.

1. Hostile/huge disclosure category must not blow Telegram confirm past 4096
   (rule already persisted — oversize reply looks like a failed set).
2. parse/storage must strip controls and cap category length.
3. Alerts history must drop non-finite ids and sanitize message_text egress.
4. HEALTH_URL nested ``poller`` must not raw-spread overwrite sanitized fields.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from koel.bot import cmd_alert, parse_alert_args
from koel.domain import (
    DISCLOSURE_CATEGORY_MAX,
    TELEGRAM_SAFE_MAX,
    AlertRule,
    AlertType,
    sanitize_disclosure_category,
)

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_sanitize_disclosure_category_strips_controls_and_caps() -> None:
    assert sanitize_disclosure_category(None) is None
    # W59: non-strings must fail closed (isinstance guard — cov line).
    assert sanitize_disclosure_category(123) is None  # type: ignore[arg-type]
    assert sanitize_disclosure_category(["x"]) is None  # type: ignore[arg-type]
    assert sanitize_disclosure_category("  \x00\x01  ") is None
    assert sanitize_disclosure_category("Rights\nIssue") == "RightsIssue"
    huge = "F" * 500
    cleaned = sanitize_disclosure_category(huge)
    assert cleaned is not None
    assert len(cleaned) == DISCLOSURE_CATEGORY_MAX
    assert "\n" not in cleaned


def test_parse_alert_args_caps_hostile_category() -> None:
    parsed, err = parse_alert_args(["JKH.N0000", "disclosure", "X" * 5000])
    assert err is None
    assert parsed is not None
    assert parsed.category is not None
    assert len(parsed.category) == DISCLOSURE_CATEGORY_MAX

    parsed2, err2 = parse_alert_args(["JKH.N0000", "disclosure", "Fin\x00ancial"])
    assert err2 is None
    assert parsed2 is not None
    assert parsed2.category == "Financial"


@pytest.mark.asyncio
async def test_cmd_alert_confirm_clamps_hostile_category_under_telegram_limit() -> None:
    """Persisted rule + oversize confirm must still send under 4096."""
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=1)
    storage.upsert_stock = AsyncMock()
    # Simulate a legacy/poisoned row that somehow still has a huge category.
    storage.create_alert_rule = AsyncMock(
        return_value=AlertRule(
            id=99,
            user_id=1,
            telegram_id=1001,
            symbol="JKH.N0000",
            type=AlertType.DISCLOSURE,
            threshold=None,
            category="C" * 10_000,
            active=True,
        )
    )
    cse = AsyncMock()
    cse.fetch_company_info = AsyncMock(
        return_value=MagicMock(name="John Keells", price=100.0)
    )

    update = MagicMock()
    update.effective_user.id = 1001
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    context.application.bot_data = {"storage": storage, "cse": cse}
    context.args = ["JKH.N0000", "disclosure", "Financial"]

    with (
        patch("koel.bot._rate_limited", AsyncMock(return_value=False)),
        patch(
            "koel.bot._lookup_symbol",
            AsyncMock(return_value=("ok", MagicMock(name="JKH"))),
        ),
    ):
        await cmd_alert(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    body = update.effective_message.reply_text.await_args.args[0]
    assert len(body) < TELEGRAM_SAFE_MAX
    assert "\x00" not in body
    assert "Alert #99 set" in body
    assert "Not financial advice" in body


def test_history_route_finite_ids_and_message_sanitize() -> None:
    route = WEB / "src" / "app" / "api" / "v1" / "alerts" / "history" / "route.ts"
    source = route.read_text(encoding="utf-8")
    assert "sanitizeHistoryMessage" in source
    assert "HISTORY_MESSAGE_TEXT_MAX" in source
    assert "toSafePositiveInt" in source
    assert "toNonNegativeSafeInt" in source
    # Ban raw Number(row.attempt_count) without finite guard.
    assert "attempt_count: Number(row.attempt_count)" not in source
    assert "message_text: row.message_text" not in source


def test_alerts_get_drops_nonfinite_ids() -> None:
    route = WEB / "src" / "app" / "api" / "v1" / "alerts" / "route.ts"
    source = route.read_text(encoding="utf-8")
    assert "toSafePositiveInt" in source
    assert "flatMap" in source


def test_health_route_sanitizes_nested_poller_no_raw_spread() -> None:
    route = WEB / "src" / "app" / "api" / "v1" / "health" / "route.ts"
    source = route.read_text(encoding="utf-8")
    assert "sanitizePollerHealth" in source
    assert "HEALTH_WATCHED_MISSING_MAX" in source
    # Raw nested spread was the medium bug — must stay gone.
    assert "...(body.poller" not in source
    assert "pick(nested)" in source
