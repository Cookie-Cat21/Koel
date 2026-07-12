"""Runtime configuration loaded from environment variables / .env."""

from __future__ import annotations

import math
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
    """Parse a float env var; blank / invalid / non-finite → default.

    Rejects ``nan`` / ``±inf`` so ops knobs like ``POLL_INTERVAL_SECONDS``
    cannot silently become non-finite and break APScheduler / sleep loops.
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if not math.isfinite(value):
        return default
    return value


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _positive_float(name: str, default: float) -> float:
    """Float env that must be ``> 0``; otherwise ``default`` (fail closed)."""
    value = _float(name, default)
    return value if value > 0 else default


def _positive_float_at_least(name: str, default: float, minimum: float) -> float:
    """Positive float env that must be ``>= minimum``; otherwise ``default``.

    Catches tiny positives (``1e-9``, ``0.001``) that pass ``> 0`` but would
    hammer cse.lk / poison httpx timeouts / half-open the circuit instantly.
    """
    value = _positive_float(name, default)
    return value if value >= minimum else default


def _nonneg_float(name: str, default: float) -> float:
    """Float env that must be ``>= 0``; otherwise ``default`` (fail closed)."""
    value = _float(name, default)
    return value if value >= 0 else default


def _positive_int(name: str, default: int) -> int:
    """Int env that must be ``>= 1``; otherwise ``default`` (fail closed)."""
    value = _int(name, default)
    return value if value >= 1 else default


# Soft floors for ops knobs (fail closed to defaults when below).
_MIN_POLL_INTERVAL_SECONDS = 5.0
_MIN_HTTP_TIMEOUT_SECONDS = 1.0
_MIN_CIRCUIT_RESET_SECONDS = 1.0


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
    # CSE_MIN_INTERVAL_SECONDS — soft gap between CSE HTTP calls on a shared
    # CSEClient (bot + poller). Default 0 = off; raise if cse.lk rate-limits.
    # Distinct from PDF_ENRICH_SLEEP_SECONDS (legacy /announcements enrich).
    cse_min_interval_seconds: float = 0.0
    health_host: str = "127.0.0.1"
    health_port: int = 8080
    log_level: str = "INFO"
    market_tz: str = "Asia/Colombo"
    market_open: str = "09:30"
    market_close: str = "14:30"
    bot_cmd_rate_per_minute: int = 20
    # PDF_ENRICH_SLEEP_SECONDS — polite pause between legacy /announcements
    # PDF enrichment calls (per symbol). Default 0.5; 0 disables sleep.
    pdf_enrich_sleep_seconds: float = 0.5
    # DISCLOSURE_BULK_FEED=1 — optional market-wide discovery via
    # POST /approvedAnnouncement + stocks name map. Default off (0);
    # per-symbol getAnnouncementByCompany remains the safe path.
    disclosure_bulk_feed: bool = False
    # SNAPSHOT_RETENTION_DAYS — after market persist, delete price_snapshots
    # older than N days for symbols NOT on any watchlist. Default 0 = off
    # (keep everything). Watched symbols keep full history forever.
    snapshot_retention_days: int = 0
    # SECTORS_INGEST=1 — optional POST /allSectors → sectors table persist.
    # Default off (0); thin GET /api/v1/sectors reads Postgres only.
    sectors_ingest: bool = False

    @classmethod
    def from_env(cls, *, require_token: bool = True) -> Settings:
        token = (
            _require("TELEGRAM_BOT_TOKEN") if require_token else os.getenv("TELEGRAM_BOT_TOKEN", "")
        )
        health_port = _int("HEALTH_PORT", 8080)
        if not (1 <= health_port <= 65535):
            health_port = 8080
        # bot_cmd_rate: 0 = unlimited; negative → default (fail closed).
        bot_rate = _int("BOT_CMD_RATE_PER_MINUTE", 20)
        if bot_rate < 0:
            bot_rate = 20
        return cls(
            telegram_bot_token=token,
            database_url=_require("DATABASE_URL"),
            cse_base_url=os.getenv("CSE_BASE_URL", "https://www.cse.lk/api").rstrip("/"),
            # ≤0 or <5s poll interval → IntervalTrigger hammer; reject.
            poll_interval_seconds=_positive_float_at_least(
                "POLL_INTERVAL_SECONDS", 60.0, _MIN_POLL_INTERVAL_SECONDS
            ),
            poll_jitter_seconds=_nonneg_float("POLL_JITTER_SECONDS", 5.0),
            http_timeout_seconds=_positive_float_at_least(
                "HTTP_TIMEOUT_SECONDS", 15.0, _MIN_HTTP_TIMEOUT_SECONDS
            ),
            circuit_fail_max=_positive_int("CIRCUIT_FAIL_MAX", 5),
            circuit_reset_seconds=_positive_float_at_least(
                "CIRCUIT_RESET_SECONDS", 60.0, _MIN_CIRCUIT_RESET_SECONDS
            ),
            cse_min_interval_seconds=_nonneg_float("CSE_MIN_INTERVAL_SECONDS", 0.0),
            health_host=os.getenv("HEALTH_HOST", "127.0.0.1"),
            health_port=health_port,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            market_tz=os.getenv("MARKET_TZ", "Asia/Colombo"),
            market_open=os.getenv("MARKET_OPEN", "09:30"),
            market_close=os.getenv("MARKET_CLOSE", "14:30"),
            bot_cmd_rate_per_minute=bot_rate,
            pdf_enrich_sleep_seconds=_nonneg_float("PDF_ENRICH_SLEEP_SECONDS", 0.5),
            disclosure_bulk_feed=os.getenv("DISCLOSURE_BULK_FEED", "0").strip() == "1",
            snapshot_retention_days=max(0, _int("SNAPSHOT_RETENTION_DAYS", 0)),
            sectors_ingest=os.getenv("SECTORS_INGEST", "0").strip() == "1",
        )


def migrations_dir() -> Path:
    return _ROOT / "db" / "migrations"
