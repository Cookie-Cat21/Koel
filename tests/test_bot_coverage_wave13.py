"""Wave13: cover remaining bot.py /brief edges + disclosure category alerts."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from koel.bot import (
    BRIEF_AI_OFF,
    BRIEF_NONE_YET,
    BRIEF_USAGE,
    cmd_alert,
    cmd_brief,
    cmd_myalerts,
    format_brief_lookup_reply,
    reset_cmd_rate_limits,
)
from koel.domain import AlertRule, AlertType, PriceSnapshot, disclaimer


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
    effective_message: object | None = ...,  # type: ignore[assignment]
) -> tuple[MagicMock, MagicMock]:
    message: object
    if effective_message is ...:
        message = AsyncMock()
        message.reply_text = AsyncMock()  # type: ignore[attr-defined]
    else:
        message = effective_message

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


def _category_create_side_effect() -> AsyncMock:
    async def _create(
        user_id: int,
        symbol: str,
        alert_type: AlertType,
        threshold: float | None,
        category: str | None = None,
    ) -> AlertRule:
        return AlertRule(
            id=11,
            user_id=user_id,
            telegram_id=1001,
            symbol=symbol,
            type=alert_type,
            threshold=threshold,
            category=category,
        )

    return AsyncMock(side_effect=_create)


# --- /brief edges -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_brief_no_effective_message_is_noop() -> None:
    storage = AsyncMock()
    storage.get_latest_ready_brief = AsyncMock()
    update, context = _make_update_context(
        args=["JKH.N0000"],
        storage=storage,
        effective_message=None,
    )
    await cmd_brief(update, context)
    storage.get_latest_ready_brief.assert_not_awaited()


@pytest.mark.asyncio
async def test_cmd_brief_ready_row_blank_brief_ai_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = AsyncMock()
    storage.get_latest_ready_brief = AsyncMock(
        return_value={
            "brief": "   ",
            "symbol": "JKH.N0000",
            "title": "Interim Dividend",
            "url": "https://cdn.cse.lk/cmt/upload_report_file/x.pdf",
        }
    )
    monkeypatch.setenv("AI_BRIEFS_ENABLED", "0")
    monkeypatch.delenv("AI_API_KEY", raising=False)

    update, context = _make_update_context(args=["JKH.N0000"], storage=storage)
    await cmd_brief(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert f"JKH.N0000: {BRIEF_AI_OFF}" in reply
    assert "Interim Dividend" not in reply
    assert disclaimer() in reply


@pytest.mark.asyncio
async def test_cmd_brief_ready_row_empty_brief_ai_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = AsyncMock()
    storage.get_latest_ready_brief = AsyncMock(
        return_value={
            "brief": "",
            "symbol": "",
            "title": 123,  # non-str → dropped
            "url": {"evil": True},  # non-str → dropped
        }
    )
    monkeypatch.setenv("AI_BRIEFS_ENABLED", "1")
    monkeypatch.setenv("AI_API_KEY", "test-key")

    update, context = _make_update_context(args=["JKH.N0000"], storage=storage)
    await cmd_brief(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    # Empty row.symbol falls back to requested symbol in empty-state path.
    assert f"JKH.N0000: {BRIEF_NONE_YET}" in reply
    assert BRIEF_AI_OFF not in reply


@pytest.mark.asyncio
async def test_cmd_brief_ready_row_strips_hostile_url_and_control_title() -> None:
    storage = AsyncMock()
    storage.get_latest_ready_brief = AsyncMock(
        return_value={
            "brief": "Board met and approved the circular.",
            "symbol": None,
            "title": "\x00Board\nCircular",
            "url": "https://evil.example/steal.pdf",
        }
    )
    update, context = _make_update_context(args=["comb.n0000"], storage=storage)
    await cmd_brief(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "COMB.N0000 filing brief" in reply
    assert "BoardCircular" in reply or "Board" in reply
    assert "evil.example" not in reply
    assert "Board met and approved" in reply
    assert disclaimer() in reply


@pytest.mark.asyncio
async def test_cmd_brief_usage_mentions_symbol_example() -> None:
    storage = AsyncMock()
    update, context = _make_update_context(args=[], storage=storage)
    await cmd_brief(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert reply == BRIEF_USAGE
    assert "/brief SYMBOL" in reply
    assert disclaimer() in reply


def test_format_brief_lookup_whitespace_title_and_blank_body() -> None:
    ai_off = format_brief_lookup_reply(
        symbol="JKH.N0000",
        brief="\t\n",
        title="   ",
        url=None,
        ai_enabled=False,
    )
    assert ai_off == f"JKH.N0000: {BRIEF_AI_OFF}\n{disclaimer()}"

    none_yet = format_brief_lookup_reply(
        symbol="JKH.N0000",
        brief=None,
        title="\x00\x01",
        ai_enabled=True,
    )
    assert none_yet == f"JKH.N0000: {BRIEF_NONE_YET}\n{disclaimer()}"

    # ai_enabled omitted → none-yet wording (not AI-off).
    defaulted = format_brief_lookup_reply(symbol="HNB.N0000", brief="")
    assert defaulted == f"HNB.N0000: {BRIEF_NONE_YET}\n{disclaimer()}"

    # Control-only title is omitted; safe URL kept.
    ok = format_brief_lookup_reply(
        symbol="JKH.N0000",
        brief="Dividend declared.",
        title="\x07\x1b",
        url="https://cdn.cse.lk/cmt/upload_report_file/ok.pdf",
    )
    assert "Disclosure:" not in ok
    assert "cdn.cse.lk" in ok
    assert "Dividend declared." in ok
    assert disclaimer() in ok


# --- category alerts --------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_alert_disclosure_multiword_category() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.upsert_stock = AsyncMock()
    storage.create_alert_rule = _category_create_side_effect()
    cse = AsyncMock()
    cse.fetch_company_info = AsyncMock(return_value=_snap())

    update, context = _make_update_context(
        args=["JKH.N0000", "disclosure", "Q1", "Interim", "Financial"],
        storage=storage,
        cse=cse,
    )
    await cmd_alert(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "matching category 'Q1 Interim Financial'" in reply
    assert storage.create_alert_rule.await_args.kwargs.get("category") == "Q1 Interim Financial"
    assert disclaimer() in reply


@pytest.mark.asyncio
async def test_cmd_alert_announcement_alias_with_category() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.upsert_stock = AsyncMock()
    storage.create_alert_rule = _category_create_side_effect()
    cse = AsyncMock()
    cse.fetch_company_info = AsyncMock(return_value=_snap("COMB.N0000"))

    update, context = _make_update_context(
        args=["COMB.N0000", "announcement", "Dividend"],
        storage=storage,
        cse=cse,
    )
    await cmd_alert(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "matching category 'Dividend'" in reply
    assert storage.create_alert_rule.await_args.args[2] == AlertType.DISCLOSURE
    assert storage.create_alert_rule.await_args.kwargs.get("category") == "Dividend"


@pytest.mark.asyncio
async def test_cmd_alert_disclosure_whitespace_category_is_any() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.upsert_stock = AsyncMock()
    storage.create_alert_rule = _category_create_side_effect()
    cse = AsyncMock()
    cse.fetch_company_info = AsyncMock(return_value=_snap())

    update, context = _make_update_context(
        args=["JKH.N0000", "disclosure", " ", "\t"],
        storage=storage,
        cse=cse,
    )
    await cmd_alert(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "matching category" not in reply
    assert "new disclosure for JKH.N0000" in reply
    assert storage.create_alert_rule.await_args.kwargs.get("category") is None


@pytest.mark.asyncio
async def test_cmd_alert_disclosure_category_upstream_and_not_found() -> None:
    storage = AsyncMock()
    storage.create_alert_rule = AsyncMock()
    cse = AsyncMock()
    cse.fetch_company_info = AsyncMock(side_effect=RuntimeError("down"))

    update, context = _make_update_context(
        args=["JKH.N0000", "disclosure", "Financial"],
        storage=storage,
        cse=cse,
    )
    await cmd_alert(update, context)
    assert "cse.lk unreachable" in update.effective_message.reply_text.await_args.args[0]
    storage.create_alert_rule.assert_not_awaited()

    cse2 = AsyncMock()
    cse2.fetch_company_info = AsyncMock(return_value=None)
    update2, context2 = _make_update_context(
        args=["ZZZ.N0000", "disclosure", "Board"],
        storage=storage,
        cse=cse2,
    )
    await cmd_alert(update2, context2)
    assert "Couldn't find ZZZ.N0000" in update2.effective_message.reply_text.await_args.args[0]
    storage.create_alert_rule.assert_not_awaited()


@pytest.mark.asyncio
async def test_cmd_alert_no_message_and_empty_args() -> None:
    storage = AsyncMock()
    cse = AsyncMock()
    update, context = _make_update_context(
        args=["JKH.N0000", "disclosure", "Financial"],
        storage=storage,
        cse=cse,
        effective_message=None,
    )
    await cmd_alert(update, context)
    cse.fetch_company_info.assert_not_called()
    storage.create_alert_rule.assert_not_called()

    update2, context2 = _make_update_context(args=[], storage=storage, cse=cse)
    await cmd_alert(update2, context2)
    reply = update2.effective_message.reply_text.await_args.args[0]
    assert "/alert SYMBOL disclosure [CATEGORY]" in reply
    assert disclaimer() in reply


@pytest.mark.asyncio
async def test_cmd_myalerts_shows_multiword_disclosure_category() -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=42)
    storage.list_alerts = AsyncMock(
        return_value=[
            AlertRule(
                id=8,
                user_id=42,
                telegram_id=1001,
                symbol="SAMP.N0000",
                type=AlertType.DISCLOSURE,
                threshold=None,
                category="Corporate Disclosure",
            ),
            AlertRule(
                id=9,
                user_id=42,
                telegram_id=1001,
                symbol="HNB.N0000",
                type=AlertType.DISCLOSURE,
                threshold=None,
                category=None,
            ),
        ]
    )
    update, context = _make_update_context(storage=storage)
    await cmd_myalerts(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    lines = reply.splitlines()
    assert "#8 SAMP.N0000 disclosure Corporate Disclosure" in lines
    assert "#9 HNB.N0000 disclosure" in lines
    assert not any(ln.startswith("#9 HNB.N0000 disclosure ") for ln in lines)
    assert disclaimer() in reply
