"""E9-C01: Settings.from_env env validation (missing TELEGRAM_BOT_TOKEN)."""

from __future__ import annotations

import pytest

from chime.config import Settings

_DSN = "postgresql://chime:chime@localhost:5432/chime"


def test_from_env_missing_telegram_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("DATABASE_URL", _DSN)
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        Settings.from_env(require_token=True)


def test_from_env_blank_telegram_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "   ")
    monkeypatch.setenv("DATABASE_URL", _DSN)
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        Settings.from_env(require_token=True)


def test_from_env_require_token_false_allows_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("DATABASE_URL", _DSN)
    settings = Settings.from_env(require_token=False)
    assert settings.telegram_bot_token == ""
    assert settings.database_url == _DSN


def test_from_env_missing_database_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        Settings.from_env(require_token=True)
