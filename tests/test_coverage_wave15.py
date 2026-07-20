"""Wave15: residual coverage push — modules still under 100% after w14.

Covers remaining branches in bot.py, briefs/extract.py, briefs/provider.py,
and config._int ValueError fallback.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from koel.bot import (
    BAD_SYMBOL_HINT,
    _env_cmd_rate_per_minute,
    _rate_limited,
    _user_id,
    build_application,
    cmd_cancel,
    cmd_myalerts,
    cmd_mywatchlist,
    cmd_start,
    cmd_unwatch,
    cmd_watch,
    on_error,
    reset_cmd_rate_limits,
)
from koel.briefs.extract import extract_pdf_text
from koel.briefs.provider import _extract_openai_chat_text
from koel.config import Settings
from koel.notify import _retry_delay_seconds


@pytest.fixture(autouse=True)
def _clear_rate_limits() -> None:
    reset_cmd_rate_limits()
    yield
    reset_cmd_rate_limits()


_DSN = "postgresql://koel:koel@localhost:5432/koel"


def _make_update_context(
    *,
    args: list[str] | None = None,
    storage: AsyncMock | None = None,
    cse: AsyncMock | None = None,
    telegram_id: int | None = 1001,
    cmd_rate_per_minute: int = 20,
    effective_message: object | None = ...,  # type: ignore[assignment]
) -> tuple[MagicMock, MagicMock]:
    message: object
    if effective_message is ...:
        message = AsyncMock()
        message.reply_text = AsyncMock()  # type: ignore[attr-defined]
    else:
        message = effective_message

    update = MagicMock()
    update.effective_message = message
    if telegram_id is None:
        update.effective_user = None
    else:
        user = MagicMock()
        user.id = telegram_id
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


# --- config._int ValueError -------------------------------------------------------


def test_int_env_invalid_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", _DSN)
    monkeypatch.setenv("CIRCUIT_FAIL_MAX", "not-an-int")
    monkeypatch.setenv("HEALTH_PORT", "nope")
    monkeypatch.setenv("BOT_CMD_RATE_PER_MINUTE", "twelve")
    settings = Settings.from_env(require_token=True)
    assert settings.circuit_fail_max == 5
    assert settings.health_port == 8080
    assert settings.bot_cmd_rate_per_minute == 20


# --- briefs/provider multimodal string parts --------------------------------------


def test_extract_openai_chat_text_string_parts_in_list() -> None:
    """Line 398: multimodal content list may include bare strings."""
    out = _extract_openai_chat_text(
        {
            "choices": [
                {
                    "message": {
                        "content": [
                            "  plain string  ",
                            {"type": "text", "text": "dict part"},
                            "",
                            {"type": "text", "text": "   "},
                            42,
                        ]
                    }
                }
            ]
        }
    )
    assert out == "plain string\ndict part"


# --- briefs/extract char caps -----------------------------------------------------


def test_extract_pdf_text_char_cap_truncates_page(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("pypdf")
    from koel.briefs import extract as extract_mod

    class _Page:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class _Reader:
        def __init__(self, *_a: object, **_k: object) -> None:
            self.pages = [_Page("abcdefghijklmnop")]  # 16 chars

    monkeypatch.setattr(extract_mod, "_MAX_EXTRACT_CHARS", 10)
    with patch("pypdf.PdfReader", _Reader):
        text = extract_pdf_text(b"%PDF")
    assert text == "abcdefghij"
    assert len(text) == 10


def test_extract_pdf_text_char_cap_stops_on_exact_fill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After a page fills the budget exactly, remaining<=0 breaks before more text."""
    pytest.importorskip("pypdf")
    from koel.briefs import extract as extract_mod

    class _Page:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class _Reader:
        def __init__(self, *_a: object, **_k: object) -> None:
            self.pages = [_Page("abcdefghij"), _Page("SHOULD_NOT_APPEAR")]

    monkeypatch.setattr(extract_mod, "_MAX_EXTRACT_CHARS", 10)
    with patch("pypdf.PdfReader", _Reader):
        text = extract_pdf_text(b"%PDF")
    assert text == "abcdefghij"
    assert "SHOULD_NOT_APPEAR" not in text


# --- bot helpers / edges ----------------------------------------------------------


def test_env_cmd_rate_per_minute_default_and_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BOT_CMD_RATE_PER_MINUTE", raising=False)
    assert _env_cmd_rate_per_minute() == 20
    monkeypatch.setenv("BOT_CMD_RATE_PER_MINUTE", "  ")
    assert _env_cmd_rate_per_minute() == 20
    monkeypatch.setenv("BOT_CMD_RATE_PER_MINUTE", "15")
    assert _env_cmd_rate_per_minute() == 15
    # Invalid / negative → default 20 (harden: ValueError path + clamp).
    monkeypatch.setenv("BOT_CMD_RATE_PER_MINUTE", "twelve")
    assert _env_cmd_rate_per_minute() == 20
    monkeypatch.setenv("BOT_CMD_RATE_PER_MINUTE", "-1")
    assert _env_cmd_rate_per_minute() == 20
    monkeypatch.setenv("BOT_CMD_RATE_PER_MINUTE", "0")
    assert _env_cmd_rate_per_minute() == 0  # 0 = unlimited


def test_retry_delay_seconds_rejects_unparseable() -> None:
    """notify._retry_delay_seconds TypeError/ValueError → 0.0 (w15 harden)."""
    assert _retry_delay_seconds("not-a-number") == 0.0  # type: ignore[arg-type]
    assert _retry_delay_seconds(None) == 0.0  # type: ignore[arg-type]
    assert _retry_delay_seconds(object()) == 0.0  # type: ignore[arg-type]


def test_build_application_reads_cmd_rate_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_CMD_RATE_PER_MINUTE", "9")
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

        build_application("tok", storage, cse)  # cmd_rate_per_minute=None → env
        assert app.bot_data["cmd_rate_per_minute"] == 9


@pytest.mark.asyncio
async def test_rate_limited_no_user_returns_false() -> None:
    update, context = _make_update_context(telegram_id=None)
    assert await _rate_limited(update, context) is False


@pytest.mark.asyncio
async def test_user_id_none_when_no_effective_user() -> None:
    storage = AsyncMock()
    update, _context = _make_update_context(telegram_id=None, storage=storage)
    assert await _user_id(storage, update) is None
    storage.ensure_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_cmd_start_no_user_still_replies() -> None:
    """Rate-limit skip (no user) + _user_id None path; message still sent."""
    storage = AsyncMock()
    update, context = _make_update_context(telegram_id=None, storage=storage)
    await cmd_start(update, context)
    storage.ensure_user.assert_not_awaited()
    update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "handler,args",
    [
        (cmd_watch, ["JKH.N0000"]),
        (cmd_unwatch, ["JKH.N0000"]),
        (cmd_cancel, ["1"]),
        (cmd_myalerts, []),
        (cmd_mywatchlist, []),
    ],
)
async def test_handlers_no_effective_message_are_noop(
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
        effective_message=None,
    )
    await handler(update, context)  # type: ignore[operator]
    storage.ensure_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_cmd_unwatch_usage_and_bad_symbol() -> None:
    storage = AsyncMock()
    update, context = _make_update_context(args=[], storage=storage)
    await cmd_unwatch(update, context)
    assert "Usage: /unwatch" in update.effective_message.reply_text.await_args.args[0]
    storage.unwatch_symbol.assert_not_awaited()

    update2, context2 = _make_update_context(args=["!!!"], storage=storage)
    await cmd_unwatch(update2, context2)
    assert update2.effective_message.reply_text.await_args.args[0] == BAD_SYMBOL_HINT
    storage.unwatch_symbol.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_error_logs_exception() -> None:
    context = MagicMock()
    context.error = RuntimeError("boom")
    with patch("koel.bot.log") as log:
        await on_error(update={"message": "x"}, context=context)
    log.exception.assert_called_once()
    kwargs = log.exception.call_args.kwargs
    assert "boom" in kwargs["error"]
