"""Runtime configuration loaded from environment variables / .env."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")


def _require(name: str) -> str:
    raw = os.getenv(name, "")
    # Fail closed — non-string mocks used to throw on .strip mid process boot.
    value = raw.strip() if isinstance(raw, str) else ""
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _float(name: str, default: float) -> float:
    """Parse a float env var; blank / invalid / non-finite → default.

    Rejects ``nan`` / ``±inf`` so ops knobs like ``POLL_INTERVAL_SECONDS``
    cannot silently become non-finite and break APScheduler / sleep loops.
    """
    raw = os.getenv(name)
    # Fail closed — non-string mocks used to throw on .strip mid Settings load.
    if raw is None or not isinstance(raw, str) or raw.strip() == "":
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
    # Fail closed — non-string mocks used to throw on .strip mid Settings load.
    if raw is None or not isinstance(raw, str) or raw.strip() == "":
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


def _env_str(name: str, default: str) -> str:
    raw = os.getenv(name, default)
    return raw if isinstance(raw, str) else default


def _timezone(name: str, default: str) -> str:
    value = _env_str(name, default).strip()
    if not value:
        return default
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError:
        return default
    return value


def _hhmm(name: str, default: str) -> str:
    value = _env_str(name, default).strip()
    try:
        hour_raw, minute_raw = value.split(":", 1)
        hour = int(hour_raw)
        minute = int(minute_raw)
    except ValueError:
        return default
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return default
    return f"{hour:02d}:{minute:02d}"


def _minutes(value: str) -> int:
    hour_raw, minute_raw = value.split(":", 1)
    return int(hour_raw) * 60 + int(minute_raw)


# Soft floors for ops knobs (fail closed to defaults when below).
_MIN_POLL_INTERVAL_SECONDS = 5.0
_MIN_HTTP_TIMEOUT_SECONDS = 1.0
_MIN_CIRCUIT_RESET_SECONDS = 1.0


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    database_url: str
    cse_base_url: str = "https://www.cse.lk/api"
    poll_interval_seconds: float = 15.0
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
    # PATH_BACKFILL_ENABLED=1 — allow scheduled/ops daily path ingest into
    # daily_bars via companyChartDataByStock. Default 0. CLI may --force.
    path_backfill_enabled: bool = False
    # PATH_BACKFILL_PERIOD — CSE chart period (2–5). Default 5 ≈ 1 year daily.
    path_backfill_period: int = 5
    # PATH_BACKFILL_SLEEP_SECONDS — polite pause between per-symbol chart calls.
    path_backfill_sleep_seconds: float = 0.35
    # SECTOR_BACKFILL_ENABLED=1 — allow companyProfile → stocks.sector ingest.
    sector_backfill_enabled: bool = False
    sector_backfill_sleep_seconds: float = 0.35
    # NOTICES_BACKFILL_ENABLED=1 — allow ops CLI to seed market_notices.
    notices_backfill_enabled: bool = False
    # ML_FORECAST_ENABLED=1 — score-signals / ml-forecast write HGB path
    # estimates into forecast_points (default 0 = keep naive forecast_path).
    ml_forecast_enabled: bool = False
    # ML_HPE_ENABLED=1 — high-precision emitter (ml_hpe_p90_v1) writes gated
    # forecast_points only when locked OOS≥90% gates fire (default 0).
    ml_hpe_enabled: bool = False

    @classmethod
    def from_env(cls, *, require_token: bool = True) -> Settings:
        if require_token:
            token = _require("TELEGRAM_BOT_TOKEN")
        else:
            token_raw = os.getenv("TELEGRAM_BOT_TOKEN", "")
            # Fail closed — non-string mocks must not reach Settings as token.
            token = token_raw if isinstance(token_raw, str) else ""
        health_port = _int("HEALTH_PORT", 8080)
        if not (1 <= health_port <= 65535):
            health_port = 8080
        # bot_cmd_rate: 0 = unlimited; negative → default (fail closed).
        bot_rate = _int("BOT_CMD_RATE_PER_MINUTE", 20)
        if bot_rate < 0:
            bot_rate = 20

        cse_base = _env_str("CSE_BASE_URL", "https://www.cse.lk/api")
        log_raw = _env_str("LOG_LEVEL", "INFO")
        bulk_raw = _env_str("DISCLOSURE_BULK_FEED", "0")
        sectors_raw = _env_str("SECTORS_INGEST", "0")
        path_bf_raw = _env_str("PATH_BACKFILL_ENABLED", "0")
        sector_bf_raw = _env_str("SECTOR_BACKFILL_ENABLED", "0")
        notices_bf_raw = _env_str("NOTICES_BACKFILL_ENABLED", "0")
        ml_fc_raw = _env_str("ML_FORECAST_ENABLED", "0")
        ml_hpe_raw = _env_str("ML_HPE_ENABLED", "0")
        path_period = _int("PATH_BACKFILL_PERIOD", 5)
        if path_period not in {2, 3, 4, 5}:
            path_period = 5
        market_open = _hhmm("MARKET_OPEN", "09:30")
        market_close = _hhmm("MARKET_CLOSE", "14:30")
        if _minutes(market_close) < _minutes(market_open):
            market_open = "09:30"
            market_close = "14:30"
        return cls(
            telegram_bot_token=token,
            database_url=_require("DATABASE_URL"),
            cse_base_url=cse_base.rstrip("/"),
            # ≤0 or <5s poll interval → IntervalTrigger hammer; reject.
            poll_interval_seconds=_positive_float_at_least(
                "POLL_INTERVAL_SECONDS", 15.0, _MIN_POLL_INTERVAL_SECONDS
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
            health_host=_env_str("HEALTH_HOST", "127.0.0.1"),
            health_port=health_port,
            log_level=log_raw.upper(),
            market_tz=_timezone("MARKET_TZ", "Asia/Colombo"),
            market_open=market_open,
            market_close=market_close,
            bot_cmd_rate_per_minute=bot_rate,
            pdf_enrich_sleep_seconds=_nonneg_float("PDF_ENRICH_SLEEP_SECONDS", 0.5),
            disclosure_bulk_feed=bulk_raw.strip() == "1",
            snapshot_retention_days=max(0, _int("SNAPSHOT_RETENTION_DAYS", 0)),
            sectors_ingest=sectors_raw.strip() == "1",
            path_backfill_enabled=path_bf_raw.strip() == "1",
            path_backfill_period=path_period,
            path_backfill_sleep_seconds=_nonneg_float(
                "PATH_BACKFILL_SLEEP_SECONDS", 0.35
            ),
            sector_backfill_enabled=sector_bf_raw.strip() == "1",
            sector_backfill_sleep_seconds=_nonneg_float(
                "SECTOR_BACKFILL_SLEEP_SECONDS", 0.35
            ),
            notices_backfill_enabled=notices_bf_raw.strip() == "1",
            ml_forecast_enabled=ml_fc_raw.strip() == "1",
            ml_hpe_enabled=ml_hpe_raw.strip() == "1",
        )


def migrations_dir() -> Path:
    return _ROOT / "db" / "migrations"
