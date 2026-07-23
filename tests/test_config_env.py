"""E9-C01: Settings.from_env env validation (missing TELEGRAM_BOT_TOKEN)."""

from __future__ import annotations

import pytest

from koel.config import Settings

_DSN = "postgresql://koel:koel@localhost:5432/koel"


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


def test_snapshot_retention_days_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", _DSN)
    monkeypatch.delenv("SNAPSHOT_RETENTION_DAYS", raising=False)
    settings = Settings.from_env(require_token=True)
    assert settings.snapshot_retention_days == 0


def test_snapshot_retention_days_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", _DSN)
    monkeypatch.setenv("SNAPSHOT_RETENTION_DAYS", "14")
    settings = Settings.from_env(require_token=True)
    assert settings.snapshot_retention_days == 14


def test_snapshot_retention_days_negative_clamped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", _DSN)
    monkeypatch.setenv("SNAPSHOT_RETENTION_DAYS", "-5")
    settings = Settings.from_env(require_token=True)
    assert settings.snapshot_retention_days == 0


@pytest.mark.parametrize("raw", ["nan", "NaN", "inf", "+inf", "-inf", "not-a-float"])
def test_float_env_rejects_nonfinite_and_invalid(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
) -> None:
    """Wave14: POLL_INTERVAL_SECONDS=nan/inf must not break the poller sleep loop."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", _DSN)
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", raw)
    monkeypatch.setenv("HTTP_TIMEOUT_SECONDS", raw)
    settings = Settings.from_env(require_token=True)
    assert settings.poll_interval_seconds == 5.0
    assert settings.http_timeout_seconds == 15.0


@pytest.mark.parametrize("raw", ["0", "-1", "-0.5"])
def test_positive_float_env_rejects_non_positive(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
) -> None:
    """Wave15: ≤0 poll/timeout must not poison APScheduler / httpx."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", _DSN)
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", raw)
    monkeypatch.setenv("HTTP_TIMEOUT_SECONDS", raw)
    monkeypatch.setenv("CIRCUIT_RESET_SECONDS", raw)
    settings = Settings.from_env(require_token=True)
    assert settings.poll_interval_seconds == 5.0
    assert settings.http_timeout_seconds == 15.0
    assert settings.circuit_reset_seconds == 60.0


@pytest.mark.parametrize("raw", ["-1", "-5"])
def test_nonneg_float_env_rejects_negative_jitter(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
) -> None:
    """Wave15: negative jitter → default (uniform(0, neg) yields negative sleep)."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", _DSN)
    monkeypatch.setenv("POLL_JITTER_SECONDS", raw)
    monkeypatch.setenv("PDF_ENRICH_SLEEP_SECONDS", raw)
    monkeypatch.setenv("CSE_MIN_INTERVAL_SECONDS", raw)
    settings = Settings.from_env(require_token=True)
    assert settings.poll_jitter_seconds == 1.0
    assert settings.pdf_enrich_sleep_seconds == 0.5
    assert settings.cse_min_interval_seconds == 0.0


@pytest.mark.parametrize("raw", ["0", "-1", "abc"])
def test_circuit_fail_max_and_health_port_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
) -> None:
    """Wave15: CIRCUIT_FAIL_MAX < 1 and out-of-range HEALTH_PORT → defaults."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", _DSN)
    monkeypatch.setenv("CIRCUIT_FAIL_MAX", raw)
    monkeypatch.setenv("HEALTH_PORT", "70000" if raw != "abc" else raw)
    monkeypatch.setenv("BOT_CMD_RATE_PER_MINUTE", "-3")
    settings = Settings.from_env(require_token=True)
    assert settings.circuit_fail_max == 5
    assert settings.health_port == 8080
    assert settings.bot_cmd_rate_per_minute == 20
