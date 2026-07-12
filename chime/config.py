"""Runtime configuration loaded from environment variables / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    database_url: str
    cse_base_url: str = "https://www.cse.lk/api"
    poll_interval_seconds: float = 60.0
    poll_jitter_seconds: float = 5.0
    http_timeout_seconds: float = 15.0
    circuit_fail_max: int = 5
    circuit_reset_seconds: float = 60.0
    health_host: str = "127.0.0.1"
    health_port: int = 8080
    log_level: str = "INFO"
    market_tz: str = "Asia/Colombo"
    market_open: str = "09:30"
    market_close: str = "14:30"
    bot_cmd_rate_per_minute: int = 20
    # Polite pause between legacy /announcements PDF enrichment calls (per symbol).
    pdf_enrich_sleep_seconds: float = 0.5

    @classmethod
    def from_env(cls, *, require_token: bool = True) -> Settings:
        token = _require("TELEGRAM_BOT_TOKEN") if require_token else os.getenv(
            "TELEGRAM_BOT_TOKEN", ""
        )
        return cls(
            telegram_bot_token=token,
            database_url=_require("DATABASE_URL"),
            cse_base_url=os.getenv("CSE_BASE_URL", "https://www.cse.lk/api").rstrip("/"),
            poll_interval_seconds=_float("POLL_INTERVAL_SECONDS", 60.0),
            poll_jitter_seconds=_float("POLL_JITTER_SECONDS", 5.0),
            http_timeout_seconds=_float("HTTP_TIMEOUT_SECONDS", 15.0),
            circuit_fail_max=_int("CIRCUIT_FAIL_MAX", 5),
            circuit_reset_seconds=_float("CIRCUIT_RESET_SECONDS", 60.0),
            health_host=os.getenv("HEALTH_HOST", "127.0.0.1"),
            health_port=_int("HEALTH_PORT", 8080),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            market_tz=os.getenv("MARKET_TZ", "Asia/Colombo"),
            market_open=os.getenv("MARKET_OPEN", "09:30"),
            market_close=os.getenv("MARKET_CLOSE", "14:30"),
            bot_cmd_rate_per_minute=_int("BOT_CMD_RATE_PER_MINUTE", 20),
            pdf_enrich_sleep_seconds=_float("PDF_ENRICH_SLEEP_SECONDS", 0.5),
        )


def migrations_dir() -> Path:
    return _ROOT / "db" / "migrations"
