"""Wave96: config market-hours env must fail closed before poller runtime."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from chime.config import Settings
from chime.poller import is_market_open

_DSN = "postgresql://chime:chime@localhost:5432/chime"


def _base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", _DSN)


def test_market_time_env_rejects_malformed_values_before_poller_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed MARKET_* env used to raise every tick in is_market_open."""
    _base_env(monkeypatch)
    monkeypatch.setenv("MARKET_TZ", "No/Such_Zone")
    monkeypatch.setenv("MARKET_OPEN", "not-hhmm")
    monkeypatch.setenv("MARKET_CLOSE", "25:99")

    settings = Settings.from_env(require_token=True)

    assert settings.market_tz == "Asia/Colombo"
    assert settings.market_open == "09:30"
    assert settings.market_close == "14:30"
    assert is_market_open(datetime(2026, 7, 13, 5, 0, tzinfo=UTC), settings) is True


def test_market_close_before_open_falls_back_to_default_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reversed window silently disables polling; default instead."""
    _base_env(monkeypatch)
    monkeypatch.setenv("MARKET_OPEN", "14:30")
    monkeypatch.setenv("MARKET_CLOSE", "09:30")

    settings = Settings.from_env(require_token=True)

    assert settings.market_open == "09:30"
    assert settings.market_close == "14:30"

