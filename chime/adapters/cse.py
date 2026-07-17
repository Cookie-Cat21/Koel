"""Adapter for cse.lk's undocumented JSON endpoints (prices, announcements).

Verified 2026-07-11 — see docs/endpoint_probe_report.md. Inbound payloads are
validated/normalized into domain models. Failed calls are logged and retried
with backoff; a per-endpoint circuit breaker short-circuits sustained outages.
"""

from __future__ import annotations

import asyncio
import math
import re
import time
from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import Any, cast
from urllib.parse import unquote, urlparse
from zoneinfo import ZoneInfo

import httpx
import structlog
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from chime.circuit import CircuitBreaker, CircuitOpenError
from chime.domain import (
    BigPrint,
    DailyBar,
    Disclosure,
    IndexSnapshot,
    MarketNotice,
    OrderBookSnapshot,
    PriceSnapshot,
    SectorSnapshot,
)

log = structlog.get_logger(__name__)

_COLOMBO = ZoneInfo("Asia/Colombo")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ChimeBot/0.1; +https://github.com/chime-cse; "
        "informational CSE alerts)"
    ),
    "Origin": "https://www.cse.lk",
    "Referer": "https://www.cse.lk/",
    "Accept": "application/json",
}

ANNOUNCEMENTS_PAGE = "https://www.cse.lk/announcements"
ANNOUNCEMENTS_HOST = "www.cse.lk"
CDN_HOST = "cdn.cse.lk"
CDN_BASE = f"https://{CDN_HOST}"
# Telegram egress budget: unbounded path/fragment must not blow past 4096.
FILING_URL_MAX = 512
_URL_CTRL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_BAD_PERCENT_ESCAPE_RE = re.compile(r"%(?![0-9A-Fa-f]{2})")
TRADE_SUMMARY_ENDPOINT = "tradeSummary"
TRADE_SUMMARY_PATH = "/tradeSummary"
ALL_SECTORS_ENDPOINT = "allSectors"
ALL_SECTORS_PATH = "/allSectors"
ASPI_DATA_ENDPOINT = "aspiData"
ASPI_DATA_PATH = "/aspiData"
SNP_DATA_ENDPOINT = "snpData"
SNP_DATA_PATH = "/snpData"
DAYS_TRADE_ENDPOINT = "daysTrade"
DAYS_TRADE_PATH = "/daysTrade"
COMPANY_CHART_ENDPOINT = "companyChartDataByStock"
COMPANY_CHART_PATH = "/companyChartDataByStock"
INDEX_CHART_ENDPOINT = "chartData"
INDEX_CHART_PATH = "/chartData"
COMPANY_FINANCIALS_ENDPOINT = "financials"
COMPANY_FINANCIALS_PATH = "/financials"
FINANCIAL_ANNOUNCEMENT_ENDPOINT = "getFinancialAnnouncement"
FINANCIAL_ANNOUNCEMENT_PATH = "/getFinancialAnnouncement"
DAILY_MARKET_SUMMARY_ENDPOINT = "dailyMarketSummery"
DAILY_MARKET_SUMMARY_PATH = "/dailyMarketSummery"
COMPANY_PROFILE_ENDPOINT = "companyProfile"
COMPANY_PROFILE_PATH = "/companyProfile"
# Observed period map — docs/experiments/CSE_PATH_HISTORY_PROBE.md
CHART_PERIOD_INTRADAY = 1
CHART_PERIOD_1W = 2
CHART_PERIOD_1M = 3
CHART_PERIOD_2M = 4
CHART_PERIOD_1Y = 5
# Daily path backfill uses period=5 (~1 year). Intraday (1) is not daily_bars.
CHART_DAILY_PERIODS = frozenset(
    {
        CHART_PERIOD_1W,
        CHART_PERIOD_1M,
        CHART_PERIOD_2M,
        CHART_PERIOD_1Y,
    }
)
BUY_IN_ENDPOINT = "getBuyInBoardAnnouncements"
BUY_IN_PATH = "/getBuyInBoardAnnouncements"
NON_COMPLIANCE_ENDPOINT = "getNonComplianceAnnouncements"
NON_COMPLIANCE_PATH = "/getNonComplianceAnnouncements"
NOTIFICATIONS_ENDPOINT = "notifications"
NOTIFICATIONS_PATH = "/notifications"
ORDER_BOOK_ENDPOINT = "orderBook"
ORDER_BOOK_PATH = "/orderBook"
LEGACY_ANNOUNCEMENTS_ENDPOINT = "announcements"
LEGACY_ANNOUNCEMENTS_PATH = "/announcements"


def _flatten_daily_market_rows(raw: Any) -> list[dict[str, Any]]:
    """CSE returns a nested list of single-element lists of objects."""
    out: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if isinstance(item, dict):
            out.append(item)
            continue
        if isinstance(item, list):
            for sub in item:
                if isinstance(sub, dict):
                    out.append(sub)
    return out


def _ms_to_date(ms: Any) -> date | None:
    if isinstance(ms, bool) or not isinstance(ms, int | float):
        return None
    try:
        return datetime.fromtimestamp(float(ms) / 1000.0, tz=_COLOMBO).date()
    except (OverflowError, OSError, ValueError):
        return None


def _reject_bool_numeric_value(value: Any) -> Any:
    """Keep hostile JSON booleans from becoming CSE numeric values."""
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid CSE numeric value")
    return value


def _announcement_url(external_id: str) -> str:
    """Public CSE announcement page anchor used in Telegram disclosure alerts."""
    return f"{ANNOUNCEMENTS_PAGE}#{external_id}"


def _safe_url_path_segments(path: str) -> list[str] | None:
    """Return non-empty path segments, rejecting encoded traversal separators."""
    segments = [s for s in path.split("/") if s != ""]
    for segment in segments:
        current = segment
        for _ in range(5):
            if _BAD_PERCENT_ESCAPE_RE.search(current):
                return None
            if (
                current in {".", ".."}
                or "/" in current
                or "\\" in current
                or _URL_CTRL_RE.search(current)
            ):
                return None
            try:
                decoded = unquote(current, errors="strict")
            except UnicodeDecodeError:
                return None
            if decoded == current:
                break
            current = decoded
        else:
            return None
    return segments


def allowed_cdn_pdf_url(url: str | None) -> str | None:
    """Normalize to ``https://cdn.cse.lk/...`` or ``None`` (SSRF guard).

    Only the CSE CDN host is accepted. Credentials, non-http(s) schemes,
    other hosts, path traversal segments, C0/C1 controls, and over-long
    URLs (``FILING_URL_MAX``) are rejected.
    """
    if url is None:
        return None
    # Fail closed — non-strings used to throw on .strip mid Telegram / enrich.
    if not isinstance(url, str):
        return None
    raw = url.strip()
    if not raw:
        return None
    if _URL_CTRL_RE.search(raw):
        return None
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        return None
    if parsed.hostname != CDN_HOST:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    path = parsed.path or "/"
    segments = _safe_url_path_segments(path)
    if segments is None:
        return None
    normalized_path = "/" + "/".join(segments) if segments else "/"
    out = f"{CDN_BASE}{normalized_path}"
    if len(out) > FILING_URL_MAX:
        return None
    return out


def allowed_filing_url(url: str | None) -> str | None:
    """Telegram/dash egress: CDN PDF or ``www.cse.lk`` announcement page only.

    Rejects ``javascript:`` / credentials / off-allowlist hosts / C0–C1
    controls / over-long URLs so bot replies never echo a hostile DB ``url``
    as an auto-linked Telegram href or blow past Telegram's 4096 limit.
    """
    if url is None:
        return None
    # Fail closed — non-strings used to throw on .strip mid alert format.
    if not isinstance(url, str):
        return None
    raw = url.strip()
    if not raw:
        return None
    if _URL_CTRL_RE.search(raw):
        return None
    cdn = allowed_cdn_pdf_url(raw)
    if cdn is not None:
        return cdn
    parsed = urlparse(raw)
    if parsed.scheme != "https":
        return None
    if parsed.hostname != ANNOUNCEMENTS_HOST:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    path = parsed.path or "/"
    segments = _safe_url_path_segments(path)
    if segments is None:
        return None
    normalized_path = "/" + "/".join(segments) if segments else "/"
    out = f"https://{ANNOUNCEMENTS_HOST}{normalized_path}"
    if parsed.query:
        out = f"{out}?{parsed.query}"
    if parsed.fragment:
        out = f"{out}#{parsed.fragment}"
    if len(out) > FILING_URL_MAX:
        return None
    return out


def resolve_pdf_url(file_path: str | None) -> str | None:
    """Map legacy ``filePath`` to a public CDN PDF URL.

    Observed shape: ``uploadAnnounceFiles/....pdf`` →
    ``https://cdn.cse.lk/uploadAnnounceFiles/....pdf``. Absolute http(s) URLs
    are accepted only when the host is exactly ``cdn.cse.lk`` (normalized to
    https). Empty / null / hostile paths yield ``None``.
    """
    if file_path is None:
        return None
    # Fail closed — non-strings used to throw on .strip mid PDF enrich.
    if not isinstance(file_path, str):
        return None
    path = file_path.strip()
    if not path:
        return None
    lower = path.lower()
    if lower.startswith("https://") or lower.startswith("http://"):
        return allowed_cdn_pdf_url(path)
    if path.startswith("//"):
        return None
    first = path.split("/", 1)[0]
    if ":" in first:
        return None
    path = path.lstrip("/")
    segments = _safe_url_path_segments(path)
    if not segments:
        return None
    return allowed_cdn_pdf_url(f"{CDN_BASE}/{'/'.join(segments)}")


class TradeSummaryRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # Same id space as companyInfoSummery.reqSymbolInfo.id (chart stockId).
    id: int | None = None
    symbol: str
    name: str | None = None
    price: float
    previousClose: float | None = None
    change: float | None = None
    percentageChange: float | None = None
    sharevolume: float | None = None
    tradevolume: float | None = None
    turnover: float | None = None
    high: float | None = None
    low: float | None = None
    open: float | None = None
    marketCap: float | None = None
    crossingVolume: float | None = None
    lastTradedTime: int | None = None

    @field_validator(
        "id",
        "price",
        "previousClose",
        "change",
        "percentageChange",
        "sharevolume",
        "tradevolume",
        "turnover",
        "high",
        "low",
        "open",
        "marketCap",
        "crossingVolume",
        "lastTradedTime",
        mode="before",
    )
    @classmethod
    def _reject_bool_numeric(cls, value: Any) -> Any:
        return _reject_bool_numeric_value(value)


class SymbolInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    symbol: str
    name: str | None = None
    lastTradedPrice: float
    previousClose: float | None = None
    change: float | None = None
    changePercentage: float | None = None
    tdyShareVolume: float | None = None
    tdyTradeVolume: float | None = None
    tdyTurnover: float | None = None
    hiTrade: float | None = None
    lowTrade: float | None = None
    marketCap: float | None = None

    @field_validator(
        "id",
        "lastTradedPrice",
        "previousClose",
        "change",
        "changePercentage",
        "tdyShareVolume",
        "tdyTradeVolume",
        "tdyTurnover",
        "hiTrade",
        "lowTrade",
        "marketCap",
        mode="before",
    )
    @classmethod
    def _reject_bool_numeric(cls, value: Any) -> Any:
        return _reject_bool_numeric_value(value)


class CompanyInfoResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reqSymbolInfo: SymbolInfo


class AnnouncementRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    announcementId: int | None = None
    id: int | None = None
    createdDate: int | None = None
    dateOfAnnouncement: str | None = None
    announcementCategory: str | None = None
    company: str | None = None
    remarks: str | None = None
    symbol: str | None = None

    @field_validator("announcementId", "id", "createdDate", mode="before")
    @classmethod
    def _reject_bool_numeric(cls, value: Any) -> Any:
        return _reject_bool_numeric_value(value)


class CompanyAnnouncementResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reqCompanyAnnouncement: list[AnnouncementRow] = Field(default_factory=list)


class ApprovedAnnouncementResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    approvedAnnouncements: list[AnnouncementRow] = Field(default_factory=list)


class SectorRow(BaseModel):
    """Row from ``POST /allSectors`` (see docs/sample_responses/allSectors.json)."""

    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    sectorId: int
    symbol: str
    indexCode: str | None = None
    indexCodeSp: str | None = None
    indexName: str | None = None
    name: str
    indexValue: float | None = None
    change: float | None = None
    percentage: float | None = None
    sectorTradeToday: float | None = None
    sectorVolumeToday: float | None = None
    sectorTurnoverToday: float | None = None
    sectorPreviousClose: float | None = None
    transactionTime: int | None = None

    @field_validator(
        "id",
        "sectorId",
        "indexValue",
        "change",
        "percentage",
        "sectorTradeToday",
        "sectorVolumeToday",
        "sectorTurnoverToday",
        "sectorPreviousClose",
        "transactionTime",
        mode="before",
    )
    @classmethod
    def _reject_bool_numeric(cls, value: Any) -> Any:
        return _reject_bool_numeric_value(value)


class IndexDataRow(BaseModel):
    """Loose row from ``POST /aspiData`` / ``POST /snpData``."""

    model_config = ConfigDict(extra="ignore")

    code: str | None = None
    name: str | None = None
    indexCode: str | None = None
    indexName: str | None = None
    value: float | None = None
    indexValue: float | None = None
    change: float | None = None
    percentage: float | None = None
    percentageChange: float | None = None
    changePct: float | None = None
    timestamp: int | None = None
    transactionTime: int | None = None

    @field_validator(
        "value",
        "indexValue",
        "change",
        "percentage",
        "percentageChange",
        "changePct",
        "timestamp",
        "transactionTime",
        mode="before",
    )
    @classmethod
    def _reject_bool_numeric(cls, value: Any) -> Any:
        return _reject_bool_numeric_value(value)


class LegacyAnnouncementRow(BaseModel):
    """Row from legacy ``POST /announcements`` (PDF archive via ``filePath``)."""

    model_config = ConfigDict(extra="ignore")

    announcementId: int | None = None
    securityId: int | None = None
    title: str | None = None
    body: str | None = None
    manualDate: int | None = None
    addedDate: int | None = None
    edited: int | None = None
    deleted: int | None = None
    filePath: str | None = None

    @field_validator(
        "announcementId",
        "securityId",
        "manualDate",
        "addedDate",
        "edited",
        "deleted",
        mode="before",
    )
    @classmethod
    def _reject_bool_numeric(cls, value: Any) -> Any:
        return _reject_bool_numeric_value(value)


class LegacyAnnouncementResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    infoAnnouncement: list[LegacyAnnouncementRow] = Field(default_factory=list)


def legacy_pdf_urls_by_id(rows: list[LegacyAnnouncementRow]) -> dict[str, str]:
    """Build ``announcementId`` → CDN PDF URL map (skips null / empty paths)."""
    out: dict[str, str] = {}
    for row in rows:
        raw_id = row.announcementId
        # Fail closed — bool soft-accepts via str(True)=="True" map keys.
        if isinstance(raw_id, bool) or not isinstance(raw_id, int):
            continue
        pdf_url = resolve_pdf_url(row.filePath)
        if pdf_url is None:
            continue
        out[str(raw_id)] = pdf_url
    return out


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        raw_status = getattr(exc.response, "status_code", None)
        # Fail closed — bool soft-accepts via ``True in {…}`` never, but
        # ``int(True)==1`` must not classify a poisoned status as retryable.
        status = (
            raw_status
            if isinstance(raw_status, int) and not isinstance(raw_status, bool)
            else None
        )
        return status in {429, 500, 502, 503, 504}
    return False


_UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _try_ms_to_dt(ms: int | None) -> datetime | None:
    """Convert CSE millisecond epoch to UTC, or ``None`` on overflow / invalid."""
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000.0, tz=UTC)
    except (OverflowError, ValueError, OSError):
        return None


def _ms_to_dt(ms: int | None) -> datetime:
    """Convert CSE millisecond epoch to aware UTC datetime.

    ``None`` and unconvertible / overflow values are treated as the Unix
    epoch — never ``datetime.now()`` — so a missing or hostile timestamp
    cannot look "fresh" and bypass disclosure backfill gates. Callers that
    need a poll-time fallback (trade / sector ticks) should use
    ``_try_ms_to_dt`` instead.
    """
    if ms is None:
        return _UNIX_EPOCH
    return _try_ms_to_dt(ms) or _UNIX_EPOCH


def _finite_or_none(value: float | None) -> float | None:
    """Pass through finite floats; coerce ``None`` / NaN / ±Inf to ``None``."""
    if value is None or not math.isfinite(value):
        return None
    return value


_DATE_OF_ANNOUNCEMENT_FORMATS = (
    "%d %b %Y",  # "30 Jun 2026" — primary CSE portal format
    "%d %B %Y",  # "30 June 2026"
    "%Y-%m-%d",
)

# Buy-in / non-compliance boards often ship createdDate as a local clock string.
_NOTICE_CREATED_DATE_FORMATS = (
    "%d %b %Y %I:%M:%S %p",  # "14 Jul 2026 05:10:30 PM"
    "%d %B %Y %I:%M:%S %p",
    "%d %b %Y %H:%M:%S",
    "%d %b %Y",
    "%d %B %Y",
    "%Y-%m-%d",
)


def _parse_date_of_announcement(value: str | None) -> datetime | None:
    """Parse CSE dateOfAnnouncement as Asia/Colombo midnight, converted to UTC.

    Calendar-only strings (no time) are local midnight in Colombo, not UTC midnight.
    Returns None if unparseable.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    for fmt in _DATE_OF_ANNOUNCEMENT_FORMATS:
        try:
            naive = datetime.strptime(text, fmt)
            return naive.replace(tzinfo=_COLOMBO).astimezone(UTC)
        except ValueError:
            continue
    return None


def _parse_notice_created_date(value: Any) -> datetime | None:
    """Parse notice ``createdDate`` as epoch-ms int or Colombo clock string."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return _try_ms_to_dt(value)
    if isinstance(value, float) and math.isfinite(value):
        return _try_ms_to_dt(int(value))
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    # Digits-only → treat as epoch ms.
    if text.isdigit():
        try:
            return _try_ms_to_dt(int(text))
        except ValueError:
            return None
    for fmt in _NOTICE_CREATED_DATE_FORMATS:
        try:
            naive = datetime.strptime(text, fmt)
            return naive.replace(tzinfo=_COLOMBO).astimezone(UTC)
        except ValueError:
            continue
    return None


def trade_row_to_snapshot(
    row: TradeSummaryRow, *, now: datetime | None = None
) -> PriceSnapshot | None:
    """Normalize a tradeSummary row. ``None`` when price is non-finite.

    Overflow ``lastTradedTime`` falls back to ``now`` (board tick time) so one
    hostile/corrupt ms value cannot abort the whole market persist loop.
    Optional float fields that are NaN/±Inf become ``None``.
    """
    if not math.isfinite(row.price):
        return None
    # Fail closed — non-string / blank symbol used to throw on .strip mid board.
    if not isinstance(row.symbol, str) or not row.symbol.strip():
        return None
    fallback = now or datetime.now(UTC)
    ts = (
        _try_ms_to_dt(row.lastTradedTime) or fallback
        if row.lastTradedTime
        else fallback
    )
    cse_id = row.id if isinstance(row.id, int) and not isinstance(row.id, bool) else None
    if cse_id is not None and cse_id <= 0:
        cse_id = None
    return PriceSnapshot(
        symbol=row.symbol.strip().upper(),
        price=row.price,
        previous_close=_finite_or_none(row.previousClose),
        change=_finite_or_none(row.change),
        change_pct=_finite_or_none(row.percentageChange),
        volume=_finite_or_none(row.sharevolume),
        trade_count=_finite_or_none(row.tradevolume),
        turnover=_finite_or_none(row.turnover),
        crossing_volume=_finite_or_none(row.crossingVolume),
        high=_finite_or_none(row.high),
        low=_finite_or_none(row.low),
        open=_finite_or_none(row.open),
        market_cap=_finite_or_none(row.marketCap),
        name=row.name,
        ts=ts,
        cse_stock_id=cse_id,
    )


def sector_row_to_snapshot(
    row: SectorRow, *, now: datetime | None = None
) -> SectorSnapshot | None:
    """Normalize an allSectors row; overflow transactionTime → poll time.

    Returns ``None`` when symbol/name are non-string or blank so one hostile
    row cannot abort the whole board normalize loop.
    """
    # Fail closed — non-string / blank symbol or name used to throw on .strip.
    if not isinstance(row.symbol, str) or not row.symbol.strip():
        return None
    if not isinstance(row.name, str) or not row.name.strip():
        return None
    fallback = now or datetime.now(UTC)
    ts = (
        _try_ms_to_dt(row.transactionTime) or fallback
        if row.transactionTime
        else fallback
    )
    return SectorSnapshot(
        sector_id=row.sectorId,
        symbol=row.symbol.strip().upper(),
        name=row.name.strip(),
        index_code=row.indexCode,
        index_code_sp=row.indexCodeSp,
        index_name=row.indexName,
        index_value=_finite_or_none(row.indexValue),
        change=_finite_or_none(row.change),
        change_pct=_finite_or_none(row.percentage),
        trade_today=_finite_or_none(row.sectorTradeToday),
        volume_today=_finite_or_none(row.sectorVolumeToday),
        turnover_today=_finite_or_none(row.sectorTurnoverToday),
        previous_close=_finite_or_none(row.sectorPreviousClose),
        ts=ts,
        cse_row_id=row.id,
    )


def index_row_to_snapshot(
    row: IndexDataRow,
    *,
    default_code: str,
    default_name: str,
    now: datetime | None = None,
) -> IndexSnapshot | None:
    """Normalize an ASPI/S&P index payload; missing timestamp falls back to poll time."""
    code_raw = row.code or row.indexCode or default_code
    if not isinstance(code_raw, str) or not code_raw.strip():
        return None
    value = row.value if row.value is not None else row.indexValue
    if value is None or not math.isfinite(value):
        return None
    name_raw = row.name or row.indexName or default_name
    name = name_raw.strip() if isinstance(name_raw, str) and name_raw.strip() else None
    fallback = now or datetime.now(UTC)
    raw_ts = row.timestamp if row.timestamp is not None else row.transactionTime
    ts = _try_ms_to_dt(raw_ts) or fallback
    pct = (
        row.percentage
        if row.percentage is not None
        else row.percentageChange
        if row.percentageChange is not None
        else row.changePct
    )
    return IndexSnapshot(
        code=code_raw.strip().upper(),
        name=name,
        value=value,
        change=_finite_or_none(row.change),
        change_pct=_finite_or_none(pct),
        ts=ts,
    )


def symbol_info_to_snapshot(
    info: SymbolInfo, *, now: datetime | None = None
) -> PriceSnapshot | None:
    """Normalize companyInfoSummery. ``None`` when last price is non-finite."""
    if not math.isfinite(info.lastTradedPrice):
        return None
    # Fail closed — non-string / blank symbol used to throw on .strip mid quote.
    if not isinstance(info.symbol, str) or not info.symbol.strip():
        return None
    return PriceSnapshot(
        symbol=info.symbol.strip().upper(),
        price=info.lastTradedPrice,
        previous_close=_finite_or_none(info.previousClose),
        change=_finite_or_none(info.change),
        change_pct=_finite_or_none(info.changePercentage),
        volume=_finite_or_none(info.tdyShareVolume),
        trade_count=_finite_or_none(info.tdyTradeVolume),
        turnover=_finite_or_none(info.tdyTurnover),
        high=_finite_or_none(info.hiTrade),
        low=_finite_or_none(info.lowTrade),
        open=None,
        market_cap=_finite_or_none(info.marketCap),
        name=info.name,
        ts=now or datetime.now(UTC),
    )


def announcement_to_disclosure(
    row: AnnouncementRow,
    *,
    symbol: str,
    seen_at: datetime | None = None,
) -> Disclosure | None:
    external = row.announcementId if row.announcementId is not None else row.id
    if external is None:
        return None
    # Fail closed — bool soft-accepts via str(True)=="True" mid disclosure
    # identity / Telegram URL fragment (parity PG id guards).
    if isinstance(external, bool) or not isinstance(external, int):
        return None
    # Prefer createdDate (epoch ms) for published_at / alert gating.
    # Treat <=0 as missing. DOA is never used for gating — laggy calendar
    # strings would fire (or miss) disclosure rules incorrectly. Fail-closed
    # to Unix epoch so rules see published_at as stale. Still parse DOA into
    # doa_display for logging / title context.
    doa = _parse_date_of_announcement(row.dateOfAnnouncement)
    # Fail closed — non-string symbol used to throw on .strip mid disclosure
    # normalize (poller / bulk path must not abort on one hostile symbol).
    if not isinstance(symbol, str) or not symbol.strip():
        return None
    symbol_norm = symbol.strip().upper()
    if row.createdDate is not None and row.createdDate > 0:
        published = _ms_to_dt(row.createdDate)
    else:
        published = _UNIX_EPOCH
        if doa is not None:
            log.warning(
                "cse_disclosure_doa_display_only",
                external_id=str(external),
                symbol=symbol_norm,
                date_of_announcement=row.dateOfAnnouncement,
                doa_display=doa.isoformat(),
                published_at=published.isoformat(),
            )
    title = row.announcementCategory or "Announcement"
    if row.remarks:
        title = f"{title}: {row.remarks}"
    return Disclosure(
        external_id=str(external),
        symbol=symbol_norm,
        company_name=row.company,
        title=title,
        category=row.announcementCategory,
        url=_announcement_url(str(external)),
        published_at=published,
        seen_at=seen_at or datetime.now(UTC),
        doa_display=doa,
    )


def normalize_company_name(name: str) -> str:
    """Collapse whitespace + uppercase for company-name → symbol matching."""
    # Fail closed — non-strings used to throw on .split mid bulk name map.
    if not isinstance(name, str):
        return ""
    return " ".join(name.split()).upper()


def build_unique_company_name_map(
    pairs: Iterable[tuple[str, str | None]],
) -> dict[str, str]:
    """Build normalized-name → symbol map; drop ambiguous names (multi-symbol).

    ``pairs`` are ``(symbol, name)`` rows from the stocks table. Names that
    resolve to more than one symbol are excluded so bulk attribution cannot
    fire the wrong ticker.
    """
    buckets: dict[str, set[str]] = {}
    for symbol, name in pairs:
        # Fail closed — non-string pairs used to throw on .strip mid bulk map.
        if not isinstance(symbol, str) or not isinstance(name, str):
            continue
        sym = symbol.strip().upper()
        if not sym or not name.strip():
            continue
        key = normalize_company_name(name)
        buckets.setdefault(key, set()).add(sym)

    out: dict[str, str] = {}
    for key, symbols in buckets.items():
        if len(symbols) == 1:
            out[key] = next(iter(symbols))
        else:
            log.warning(
                "company_name_map_ambiguous",
                company_name=key,
                symbols=sorted(symbols),
            )
    return out


def resolve_announcement_symbol(
    row: AnnouncementRow,
    *,
    name_map: dict[str, str],
    allowed_symbols: set[str],
) -> str | None:
    """Attribute a bulk announcement row to a watched symbol, or None.

    Prefer an explicit ``row.symbol`` when present and allowed; otherwise map
    ``row.company`` via ``name_map``. Unmatched / ambiguous → None (caller
    must not invent a ticker).
    """
    # Fail closed — non-string members used to throw on .strip mid bulk resolve.
    allowed = {
        s.strip().upper()
        for s in allowed_symbols
        if isinstance(s, str) and s.strip()
    }
    row_sym = row.symbol if isinstance(row.symbol, str) else None
    if row_sym and row_sym.strip():
        sym = row_sym.strip().upper()
        return sym if sym in allowed else None
    row_company = row.company if isinstance(row.company, str) else None
    if not row_company or not row_company.strip():
        return None
    mapped = name_map.get(normalize_company_name(row_company))
    if mapped is None:
        return None
    return mapped if mapped in allowed else None




class DayTradeRow(BaseModel):
    """Row from ``POST /daysTrade`` (intraday tape)."""

    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    price: float | None = None
    quantity: float | None = None
    lastTradedTime: int | None = None
    tradeDate: int | None = None
    time: str | None = None
    symbol: str | None = None
    securityId: int | None = None

    @field_validator(
        "id",
        "price",
        "quantity",
        "lastTradedTime",
        "tradeDate",
        "securityId",
        mode="before",
    )
    @classmethod
    def _reject_bool_numeric(cls, value: Any) -> Any:
        return _reject_bool_numeric_value(value)


class DayTradeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    trades: list[DayTradeRow] = Field(default_factory=list)


class ChartPointRow(BaseModel):
    """Point from ``POST /companyChartDataByStock`` ``chartData[]``."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    p: float | None = None
    h: float | None = None
    # CSE JSON key is ``l`` — alias avoids ruff E741 on attribute name ``l``.
    low: float | None = Field(default=None, alias="l")
    o: float | None = None
    q: float | None = None
    c: float | None = None
    pc: float | None = None
    t: int | None = None
    id: int | None = None

    @field_validator("p", "h", "low", "o", "q", "c", "pc", "t", "id", mode="before")
    @classmethod
    def _reject_bool_numeric(cls, value: Any) -> Any:
        return _reject_bool_numeric_value(value)


class CompanyChartResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    chartData: list[ChartPointRow] = Field(default_factory=list)

    @field_validator("id", mode="before")
    @classmethod
    def _reject_bool_numeric(cls, value: Any) -> Any:
        return _reject_bool_numeric_value(value)


def chart_trade_date(bar_ts: datetime) -> date:
    """Asia/Colombo calendar date for a CSE chart timestamp."""
    if bar_ts.tzinfo is None:
        bar_ts = bar_ts.replace(tzinfo=UTC)
    return bar_ts.astimezone(_COLOMBO).date()


def chart_point_to_daily_bar(
    row: ChartPointRow,
    *,
    symbol: str,
    period: int,
) -> DailyBar | None:
    """Normalize a chart point into a daily bar. Skip intraday / bad rows."""
    if period not in CHART_DAILY_PERIODS:
        return None
    if not isinstance(symbol, str) or not symbol.strip():
        return None
    price = _finite_or_none(row.p)
    if price is None:
        return None
    bar_ts = _try_ms_to_dt(row.t)
    if bar_ts is None:
        return None
    return DailyBar(
        symbol=symbol.strip().upper(),
        trade_date=chart_trade_date(bar_ts),
        price=price,
        high=_finite_or_none(row.h),
        low=_finite_or_none(row.low),
        open=_finite_or_none(row.o),
        volume=_finite_or_none(row.q),
        source_period=period,
        bar_ts=bar_ts,
    )


def chart_point_to_intraday_snapshot(
    row: ChartPointRow,
    *,
    symbol: str,
    cse_stock_id: int | None = None,
    name: str | None = None,
) -> PriceSnapshot | None:
    """Normalize a ``period=1`` chart point into a ``price_snapshots`` tick."""
    if not isinstance(symbol, str) or not symbol.strip():
        return None
    price = _finite_or_none(row.p)
    if price is None or price <= 0:
        return None
    bar_ts = _try_ms_to_dt(row.t)
    if bar_ts is None:
        return None
    sid: int | None = None
    if (
        cse_stock_id is not None
        and not isinstance(cse_stock_id, bool)
        and isinstance(cse_stock_id, int)
        and cse_stock_id > 0
    ):
        sid = cse_stock_id
    return PriceSnapshot(
        symbol=symbol.strip().upper(),
        price=price,
        change=_finite_or_none(row.c),
        change_pct=_finite_or_none(row.pc),
        volume=_finite_or_none(row.q),
        high=_finite_or_none(row.h),
        low=_finite_or_none(row.low),
        open=_finite_or_none(row.o),
        name=name,
        ts=bar_ts,
        cse_stock_id=sid,
    )


class FlexibleNoticeRow(BaseModel):
    """Loose row for buy-in / non-compliance / notifications feeds."""

    model_config = ConfigDict(extra="ignore")

    id: Any = None
    announcementId: int | None = None
    symbol: str | None = None
    company: str | None = None
    name: str | None = None
    title: str | None = None
    body: str | None = None
    remarks: str | None = None
    announcementCategory: str | None = None
    # CSE may send epoch-ms int OR local clock strings — keep raw, parse later.
    createdDate: Any = None
    dateOfAnnouncement: str | None = None
    status: str | None = None

    @field_validator("announcementId", mode="before")
    @classmethod
    def _reject_bool_numeric(cls, value: Any) -> Any:
        return _reject_bool_numeric_value(value)


def day_trade_to_big_print(
    row: DayTradeRow,
    *,
    symbol: str,
    now: datetime | None = None,
) -> BigPrint | None:
    """Normalize a daysTrade row; skip missing id / non-positive quantity."""
    if isinstance(row.id, bool) or not isinstance(row.id, int):
        return None
    qty = _finite_or_none(row.quantity)
    if qty is None or qty <= 0:
        return None
    if not isinstance(symbol, str) or not symbol.strip():
        return None
    fallback = now or datetime.now(UTC)
    traded = _try_ms_to_dt(row.lastTradedTime) or _try_ms_to_dt(row.tradeDate) or fallback
    return BigPrint(
        external_id=str(row.id),
        symbol=symbol.strip().upper(),
        price=_finite_or_none(row.price),
        quantity=qty,
        traded_at=traded,
        seen_at=fallback,
    )


def _notice_external_id(row: FlexibleNoticeRow, *, fallback_idx: int) -> str | None:
    raw = row.announcementId if row.announcementId is not None else row.id
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return str(raw)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()[:128]
    return f"idx-{fallback_idx}"


def flexible_row_to_notice(
    row: FlexibleNoticeRow,
    *,
    notice_type: str,
    symbol: str | None = None,
    company_name: str | None = None,
    now: datetime | None = None,
    fallback_idx: int = 0,
) -> MarketNotice | None:
    """Normalize buy-in / non-compliance / halt rows into MarketNotice."""
    if notice_type not in {"buy_in", "non_compliance", "halt"}:
        return None
    ext = _notice_external_id(row, fallback_idx=fallback_idx)
    if not ext:
        return None
    title = (
        (row.title if isinstance(row.title, str) else None)
        or (row.company if isinstance(row.company, str) else None)
        or (row.announcementCategory if isinstance(row.announcementCategory, str) else None)
        or (row.name if isinstance(row.name, str) else None)
        or notice_type.replace("_", " ")
    )
    title = title.strip() or notice_type.replace("_", " ")
    body_parts: list[str] = []
    for part in (row.body, row.remarks, row.company, row.name):
        if isinstance(part, str) and part.strip():
            body_parts.append(part.strip())
    body = " — ".join(body_parts) if body_parts else None
    published = (
        _parse_notice_created_date(row.createdDate)
        or _parse_date_of_announcement(row.dateOfAnnouncement)
        or (now or datetime.now(UTC))
    )
    sym = None
    if isinstance(symbol, str) and symbol.strip():
        sym = symbol.strip().upper()
    elif isinstance(row.symbol, str) and row.symbol.strip():
        sym = row.symbol.strip().upper()
    url = _announcement_url(ext) if notice_type != "halt" else ANNOUNCEMENTS_PAGE
    return MarketNotice(
        external_id=f"{notice_type}:{ext}",
        notice_type=notice_type,
        symbol=sym,
        title=title[:200],
        body=body,
        url=url,
        published_at=published,
        seen_at=now or datetime.now(UTC),
    )



class OrderBookTotal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    totalBids: float | None = None
    totalAsks: float | None = None

    @field_validator("id", "totalBids", "totalAsks", mode="before")
    @classmethod
    def _reject_bool_numeric(cls, value: Any) -> Any:
        return _reject_bool_numeric_value(value)


class OrderBookLevel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    securityId: int | None = None
    board: str | None = None
    splits: int | None = None
    buySell: int | None = None  # observed: 1 = bid on public feed
    priceLevel: int | None = None
    price: float | None = None
    quantity: float | None = None

    @field_validator(
        "id",
        "securityId",
        "splits",
        "buySell",
        "priceLevel",
        "price",
        "quantity",
        mode="before",
    )
    @classmethod
    def _reject_bool_numeric(cls, value: Any) -> Any:
        return _reject_bool_numeric_value(value)


class OrderBookResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reqOrderBookTotal: OrderBookTotal | None = None
    reqOrderBook: list[OrderBookLevel] = Field(default_factory=list)


def order_book_to_snapshot(
    *,
    symbol: str,
    total: OrderBookTotal | None,
    levels: list[OrderBookLevel],
    now: datetime | None = None,
) -> OrderBookSnapshot | None:
    """Normalize public order-book totals; require finite positive bid+ask sizes."""
    if not isinstance(symbol, str) or not symbol.strip():
        return None
    if total is None:
        return None
    bids = _finite_or_none(total.totalBids)
    asks = _finite_or_none(total.totalAsks)
    if bids is None or asks is None or bids < 0 or asks < 0:
        return None
    if bids == 0 and asks == 0:
        return None
    best_bid = None
    best_bid_qty = None
    # Public feed typically returns one bid level (buySell=1).
    for lvl in levels:
        if lvl.buySell == 1:
            best_bid = _finite_or_none(lvl.price)
            best_bid_qty = _finite_or_none(lvl.quantity)
            break
    return OrderBookSnapshot(
        symbol=symbol.strip().upper(),
        total_bids=bids,
        total_asks=asks,
        best_bid=best_bid,
        best_bid_qty=best_bid_qty,
        ts=now or datetime.now(UTC),
    )

class CSEClient:
    """HTTP adapter for cse.lk with retries + per-endpoint circuit breakers."""

    def __init__(
        self,
        *,
        base_url: str = "https://www.cse.lk/api",
        timeout: float = 15.0,
        fail_max: int = 5,
        reset_timeout: float = 60.0,
        min_interval_seconds: float = 0.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        # Fail closed — non-string base_url used to throw on .rstrip mid boot.
        if not isinstance(base_url, str) or not base_url.strip():
            base_url = "https://www.cse.lk/api"
        self.base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=timeout,
            headers=DEFAULT_HEADERS,
        )
        self._breakers: dict[str, CircuitBreaker] = {}
        self._fail_max = fail_max
        self._reset_timeout = reset_timeout
        # Soft global pacing between CSE HTTP calls (CSE_MIN_INTERVAL_SECONDS).
        # 0 = off (default). Spaces bot + poller traffic on a shared client;
        # distinct from PDF_ENRICH_SLEEP_SECONDS (legacy enrich only).
        # Fail closed — bool soft-accepts via float(True)==1.0 mid pace;
        # non-finite / non-numeric → pacing off.
        if (
            isinstance(min_interval_seconds, bool)
            or not isinstance(min_interval_seconds, (int, float))
            or not math.isfinite(float(min_interval_seconds))
        ):
            self._min_interval = 0.0
        else:
            self._min_interval = max(0.0, float(min_interval_seconds))
        self._last_request_at: float | None = None
        self._pace_lock = asyncio.Lock()

    def _breaker(self, endpoint: str) -> CircuitBreaker:
        if endpoint not in self._breakers:
            self._breakers[endpoint] = CircuitBreaker(
                name=endpoint,
                fail_max=self._fail_max,
                reset_timeout=self._reset_timeout,
            )
        return self._breakers[endpoint]

    def circuit_metrics(self) -> dict[str, Any]:
        """Per-endpoint breaker snapshots for loopback health (E8-C01)."""
        return {name: breaker.snapshot() for name, breaker in self._breakers.items()}

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> CSEClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def _pace(self) -> None:
        """Sleep only when needed so consecutive CSE calls respect min interval.

        No sleep before the first call. Concurrent callers serialize on the
        pace lock so bot + poller sharing one client still honor the gap.
        """
        interval = self._min_interval
        if interval <= 0:
            return
        async with self._pace_lock:
            now = time.monotonic()
            last = self._last_request_at
            if last is not None:
                wait = interval - (now - last)
                if wait > 0:
                    await asyncio.sleep(wait)
            self._last_request_at = time.monotonic()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.5, max=8),
        retry=retry_if_exception(_retryable),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        log_context: dict[str, Any] | None = None,
    ) -> Any:
        await self._pace()
        url = f"{self.base_url}{path}"
        context = log_context or {}
        try:
            response = await self._client.request(
                method,
                url,
                data=data,
                json=json_body,
            )
            # Treat HTML error pages / non-JSON as soft failures
            raw_ct = response.headers.get("content-type", "")
            # Fail closed — non-string CT mocks used to throw on ``"json" not in``.
            content_type = raw_ct if isinstance(raw_ct, str) else ""
            raw_status = getattr(response, "status_code", 0)
            # Fail closed — bool soft-accepts via ``True >= 400`` is False, so a
            # poisoned status used to soft-accept as HTTP success mid poll.
            status: int | None = (
                raw_status
                if isinstance(raw_status, int) and not isinstance(raw_status, bool)
                else None
            )
            if status is None or status >= 400:
                log.warning(
                    "cse_http_error",
                    path=path,
                    status=raw_status,
                    body=response.text[:300],
                    **context,
                )
                if status is not None:
                    response.raise_for_status()
                raise httpx.HTTPStatusError(
                    f"invalid CSE status_code={raw_status!r}",
                    request=response.request,
                    response=response,
                )
            if "json" not in content_type and response.text[:1] not in ("{", "["):
                log.warning("cse_non_json", path=path, content_type=content_type, **context)
                raise httpx.HTTPStatusError(
                    "non-json response",
                    request=response.request,
                    response=response,
                )
            return response.json()
        except httpx.TimeoutException as exc:
            # E10-C01: distinct event so ops can filter timeout vs other soft fails
            log.warning("cse_timeout", path=path, error=str(exc), **context)
            raise
        except Exception as exc:
            log.warning("cse_request_failed", path=path, error=str(exc), **context)
            raise

    async def _guarded(
        self,
        endpoint: str,
        fn: Any,
    ) -> Any:
        breaker = self._breaker(endpoint)
        try:
            return await breaker.call(fn)
        except CircuitOpenError:
            log.error("cse_circuit_open", endpoint=endpoint)
            raise

    async def fetch_trade_summary(self) -> list[PriceSnapshot]:
        async def _call() -> list[PriceSnapshot]:
            raw = await self._request("POST", TRADE_SUMMARY_PATH, json_body={})
            if not isinstance(raw, dict):
                log.error(
                    "cse_schema_error",
                    endpoint=TRADE_SUMMARY_ENDPOINT,
                    error="expected object",
                )
                raise ValueError(f"{TRADE_SUMMARY_ENDPOINT}: expected JSON object")
            rows_raw = raw.get("reqTradeSummery") or []
            if not isinstance(rows_raw, list):
                log.error(
                    "cse_schema_error",
                    endpoint=TRADE_SUMMARY_ENDPOINT,
                    error="reqTradeSummery not a list",
                )
                raise ValueError(f"{TRADE_SUMMARY_ENDPOINT}: reqTradeSummery not a list")
            if not rows_raw:
                log.warning(
                    "cse_trade_summary_empty_ok",
                    endpoint=TRADE_SUMMARY_ENDPOINT,
                    response_keys=sorted(str(key) for key in raw),
                )
            now = datetime.now(UTC)
            out: list[PriceSnapshot] = []
            for item in rows_raw:
                try:
                    row = TradeSummaryRow.model_validate(item)
                except ValidationError as exc:
                    log.warning(
                        "cse_trade_row_skipped",
                        endpoint=TRADE_SUMMARY_ENDPOINT,
                        error=str(exc),
                        row=str(item)[:200],
                    )
                    continue
                snap = trade_row_to_snapshot(row, now=now)
                if snap is None:
                    log.warning(
                        "cse_trade_row_skipped",
                        endpoint=TRADE_SUMMARY_ENDPOINT,
                        error="non-finite price",
                        row=str(item)[:200],
                    )
                    continue
                out.append(snap)
            return out

        return cast(list[PriceSnapshot], await self._guarded(TRADE_SUMMARY_ENDPOINT, _call))

    async def fetch_all_sectors(self) -> list[SectorSnapshot]:
        """Fetch CSE sector index board (``POST /allSectors``, top-level array)."""

        async def _call() -> list[SectorSnapshot]:
            raw = await self._request("POST", ALL_SECTORS_PATH, json_body={})
            if not isinstance(raw, list):
                log.error(
                    "cse_schema_error",
                    endpoint=ALL_SECTORS_ENDPOINT,
                    error="expected array",
                )
                raise ValueError(f"{ALL_SECTORS_ENDPOINT}: expected JSON array")
            if not raw:
                log.warning(
                    "cse_all_sectors_empty_ok",
                    endpoint=ALL_SECTORS_ENDPOINT,
                )
            now = datetime.now(UTC)
            out: list[SectorSnapshot] = []
            for item in raw:
                try:
                    row = SectorRow.model_validate(item)
                except ValidationError as exc:
                    log.warning(
                        "cse_sector_row_skipped",
                        endpoint=ALL_SECTORS_ENDPOINT,
                        error=str(exc),
                        row=str(item)[:200],
                    )
                    continue
                snap = sector_row_to_snapshot(row, now=now)
                if snap is None:
                    log.warning(
                        "cse_sector_row_skipped",
                        endpoint=ALL_SECTORS_ENDPOINT,
                        error="blank symbol or name",
                        row=str(item)[:200],
                    )
                    continue
                out.append(snap)
            return out

        return cast(list[SectorSnapshot], await self._guarded(ALL_SECTORS_ENDPOINT, _call))

    async def _fetch_index_data(
        self,
        *,
        endpoint: str,
        path: str,
        default_code: str,
        default_name: str,
    ) -> IndexSnapshot | None:
        async def _call() -> IndexSnapshot | None:
            raw = await self._request("POST", path, json_body={})
            if not isinstance(raw, dict):
                log.error(
                    "cse_schema_error",
                    endpoint=endpoint,
                    error="expected object",
                )
                raise ValueError(f"{endpoint}: expected JSON object")
            try:
                row = IndexDataRow.model_validate(raw)
            except ValidationError as exc:
                log.warning(
                    "cse_index_row_skipped",
                    endpoint=endpoint,
                    error=str(exc),
                    row=str(raw)[:200],
                )
                return None
            snap = index_row_to_snapshot(
                row,
                default_code=default_code,
                default_name=default_name,
                now=datetime.now(UTC),
            )
            if snap is None:
                log.warning(
                    "cse_index_row_skipped",
                    endpoint=endpoint,
                    error="blank code or non-finite value",
                    row=str(raw)[:200],
                )
            return snap

        return cast(IndexSnapshot | None, await self._guarded(endpoint, _call))

    async def fetch_aspi_data(self) -> IndexSnapshot | None:
        """Fetch ASPI index tick (``POST /aspiData``)."""
        return await self._fetch_index_data(
            endpoint=ASPI_DATA_ENDPOINT,
            path=ASPI_DATA_PATH,
            default_code="ASPI",
            default_name="All Share Price Index",
        )

    async def fetch_snp_data(self) -> IndexSnapshot | None:
        """Fetch S&P Sri Lanka 20 index tick (``POST /snpData``)."""
        return await self._fetch_index_data(
            endpoint=SNP_DATA_ENDPOINT,
            path=SNP_DATA_PATH,
            default_code="SNP_SL20",
            default_name="S&P Sri Lanka 20",
        )

    async def fetch_company_info(self, symbol: str) -> PriceSnapshot | None:
        # Fail closed — non-string symbol used to throw on .strip mid quote fetch.
        if not isinstance(symbol, str):
            return None
        symbol = symbol.strip().upper()
        if not symbol:
            return None

        async def _call() -> PriceSnapshot | None:
            raw = await self._request(
                "POST",
                "/companyInfoSummery",
                data={"symbol": symbol},
                log_context={"symbol": symbol},
            )
            try:
                parsed = CompanyInfoResponse.model_validate(raw)
            except ValidationError as exc:
                log.error(
                    "cse_schema_error",
                    endpoint="companyInfoSummery",
                    symbol=symbol,
                    error=str(exc),
                )
                # Invalid / missing symbol payloads fail validation — treat as not found
                return None
            return symbol_info_to_snapshot(parsed.reqSymbolInfo)

        # CircuitOpenError and transport errors propagate (do not swallow)
        return cast(PriceSnapshot | None, await self._guarded("companyInfoSummery", _call))

    async def fetch_announcements_for_symbol(
        self,
        symbol: str,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[Disclosure]:
        # Fail closed — non-string symbol used to throw on .strip mid disclosure fetch.
        if not isinstance(symbol, str):
            return []
        symbol = symbol.strip().upper()
        if not symbol:
            return []
        form: dict[str, Any] = {"symbol": symbol}
        if from_date:
            form["fromDate"] = from_date
        if to_date:
            form["toDate"] = to_date

        async def _call() -> list[Disclosure]:
            raw = await self._request(
                "POST",
                "/getAnnouncementByCompany",
                data=form,
                log_context={"symbol": symbol},
            )
            try:
                parsed = CompanyAnnouncementResponse.model_validate(raw)
            except ValidationError as exc:
                log.error(
                    "cse_schema_error",
                    endpoint="getAnnouncementByCompany",
                    symbol=symbol,
                    error=str(exc),
                )
                raise
            seen = datetime.now(UTC)
            out: list[Disclosure] = []
            for row in parsed.reqCompanyAnnouncement:
                disc = announcement_to_disclosure(row, symbol=symbol, seen_at=seen)
                if disc is not None:
                    out.append(disc)
            return out

        # CircuitOpenError propagates (do not swallow as [] — empty means HTTP OK)
        return cast(list[Disclosure], await self._guarded("getAnnouncementByCompany", _call))

    async def fetch_approved_announcements(self) -> list[AnnouncementRow]:
        async def _call() -> list[AnnouncementRow]:
            raw = await self._request("POST", "/approvedAnnouncement", json_body={})
            try:
                parsed = ApprovedAnnouncementResponse.model_validate(raw)
            except ValidationError as exc:
                log.error("cse_schema_error", endpoint="approvedAnnouncement", error=str(exc))
                raise
            return list(parsed.approvedAnnouncements)

        # CircuitOpenError propagates (do not swallow as [] — empty means HTTP OK)
        return cast(list[AnnouncementRow], await self._guarded("approvedAnnouncement", _call))

    async def fetch_legacy_announcements(self, symbol: str) -> list[LegacyAnnouncementRow]:
        """Fetch legacy ``POST /announcements`` archive (includes ``filePath`` PDFs).

        Prefer ``fetch_announcements_for_symbol`` for structured categories; use
        this only to resolve CDN PDF URLs for enrichment.
        """
        # Fail closed — non-string symbol used to throw on .strip mid legacy PDF fetch.
        if not isinstance(symbol, str):
            return []
        symbol = symbol.strip().upper()
        if not symbol:
            return []

        async def _call() -> list[LegacyAnnouncementRow]:
            raw = await self._request(
                "POST",
                LEGACY_ANNOUNCEMENTS_PATH,
                data={"symbol": symbol},
                log_context={"symbol": symbol},
            )
            try:
                parsed = LegacyAnnouncementResponse.model_validate(raw)
            except ValidationError as exc:
                log.error(
                    "cse_schema_error",
                    endpoint=LEGACY_ANNOUNCEMENTS_ENDPOINT,
                    symbol=symbol,
                    error=str(exc),
                )
                raise
            return list(parsed.infoAnnouncement)

        return cast(
            list[LegacyAnnouncementRow],
            await self._guarded(LEGACY_ANNOUNCEMENTS_ENDPOINT, _call),
        )

    async def fetch_days_trade(self, symbol: str) -> list[BigPrint]:
        """Fetch day tape for one symbol (``POST /daysTrade``)."""

        if not isinstance(symbol, str) or not symbol.strip():
            return []
        sym = symbol.strip().upper()

        async def _call() -> list[BigPrint]:
            raw = await self._request(
                "POST",
                DAYS_TRADE_PATH,
                data={"symbol": sym},
            )
            if not isinstance(raw, dict):
                log.error(
                    "cse_schema_error",
                    endpoint=DAYS_TRADE_ENDPOINT,
                    error="expected object",
                )
                raise ValueError(f"{DAYS_TRADE_ENDPOINT}: expected JSON object")
            rows_raw = raw.get("trades") or []
            if not isinstance(rows_raw, list):
                log.error(
                    "cse_schema_error",
                    endpoint=DAYS_TRADE_ENDPOINT,
                    error="trades not a list",
                )
                raise ValueError(f"{DAYS_TRADE_ENDPOINT}: trades not a list")
            now = datetime.now(UTC)
            out: list[BigPrint] = []
            for item in rows_raw:
                try:
                    row = DayTradeRow.model_validate(item)
                except ValidationError as exc:
                    log.warning(
                        "cse_days_trade_row_skipped",
                        endpoint=DAYS_TRADE_ENDPOINT,
                        error=str(exc),
                        row=str(item)[:200],
                    )
                    continue
                bp = day_trade_to_big_print(row, symbol=sym, now=now)
                if bp is not None:
                    out.append(bp)
            return out

        return cast(list[BigPrint], await self._guarded(DAYS_TRADE_ENDPOINT, _call))

    async def fetch_company_chart(
        self,
        stock_id: int,
        *,
        symbol: str,
        period: int = CHART_PERIOD_1Y,
    ) -> list[DailyBar]:
        """Fetch path bars for one stock (``POST /companyChartDataByStock``).

        ``period`` must be a daily code (2–5) for ``daily_bars`` persistence.
        Intraday ``period=1`` returns ``[]`` after normalize (not daily).
        """
        if isinstance(stock_id, bool) or not isinstance(stock_id, int) or stock_id <= 0:
            return []
        if isinstance(period, bool) or not isinstance(period, int):
            return []
        if not isinstance(symbol, str) or not symbol.strip():
            return []
        sym = symbol.strip().upper()

        async def _call() -> list[DailyBar]:
            raw = await self._request(
                "POST",
                COMPANY_CHART_PATH,
                data={"stockId": str(stock_id), "period": str(period)},
                log_context={"stock_id": stock_id, "symbol": sym, "period": period},
            )
            try:
                parsed = CompanyChartResponse.model_validate(raw)
            except ValidationError as exc:
                log.error(
                    "cse_schema_error",
                    endpoint=COMPANY_CHART_ENDPOINT,
                    stock_id=stock_id,
                    symbol=sym,
                    period=period,
                    error=str(exc),
                )
                raise
            # Last-wins per trade_date (hostile duplicate stamps).
            by_date: dict[date, DailyBar] = {}
            for row in parsed.chartData:
                bar = chart_point_to_daily_bar(row, symbol=sym, period=period)
                if bar is not None:
                    by_date[bar.trade_date] = bar
            return sorted(by_date.values(), key=lambda b: b.trade_date)

        return cast(list[DailyBar], await self._guarded(COMPANY_CHART_ENDPOINT, _call))

    async def fetch_company_intraday(
        self,
        stock_id: int,
        *,
        symbol: str,
    ) -> list[PriceSnapshot]:
        """Fetch today's trade ticks via ``companyChartDataByStock`` period=1.

        Returns ascending ``PriceSnapshot`` rows suitable for ``price_snapshots``.
        Empty when CSE has no session prints or the id is invalid.
        """
        if isinstance(stock_id, bool) or not isinstance(stock_id, int) or stock_id <= 0:
            return []
        if not isinstance(symbol, str) or not symbol.strip():
            return []
        sym = symbol.strip().upper()

        async def _call() -> list[PriceSnapshot]:
            raw = await self._request(
                "POST",
                COMPANY_CHART_PATH,
                data={"stockId": str(stock_id), "period": str(CHART_PERIOD_INTRADAY)},
                log_context={
                    "stock_id": stock_id,
                    "symbol": sym,
                    "period": CHART_PERIOD_INTRADAY,
                },
            )
            try:
                parsed = CompanyChartResponse.model_validate(raw)
            except ValidationError as exc:
                log.error(
                    "cse_schema_error",
                    endpoint=COMPANY_CHART_ENDPOINT,
                    stock_id=stock_id,
                    symbol=sym,
                    period=CHART_PERIOD_INTRADAY,
                    error=str(exc),
                )
                raise
            # Cap hostile / oversized chart payloads (CSE usually << this).
            max_points = 2_000
            chart_rows = parsed.chartData[:max_points]
            # Last-wins per timestamp (hostile duplicate stamps).
            by_ts: dict[datetime, PriceSnapshot] = {}
            for row in chart_rows:
                snap = chart_point_to_intraday_snapshot(
                    row, symbol=sym, cse_stock_id=stock_id
                )
                if snap is not None:
                    by_ts[snap.ts] = snap
            return sorted(by_ts.values(), key=lambda s: s.ts)

        return cast(
            list[PriceSnapshot], await self._guarded(COMPANY_CHART_ENDPOINT, _call)
        )

    async def fetch_index_chart(
        self,
        *,
        chart_id: int = 1,
        period: int = CHART_PERIOD_1Y,
    ) -> list[tuple[date, float, float | None]]:
        """Index-scale daily series from ``POST /chartData`` (ASPI-like).

        ``symbol`` is ignored by CSE — do not use for per-stock paths.
        Returns ``(trade_date, value, pct_change)`` ascending.
        """
        if isinstance(chart_id, bool) or not isinstance(chart_id, int) or chart_id <= 0:
            return []
        if isinstance(period, bool) or not isinstance(period, int):
            return []
        if period not in CHART_DAILY_PERIODS and period != CHART_PERIOD_INTRADAY:
            return []

        async def _call() -> list[tuple[date, float, float | None]]:
            raw = await self._request(
                "POST",
                INDEX_CHART_PATH,
                data={"chartId": str(chart_id), "period": str(period)},
                log_context={"chart_id": chart_id, "period": period},
            )
            if not isinstance(raw, list):
                log.error(
                    "cse_schema_error",
                    endpoint=INDEX_CHART_ENDPOINT,
                    error="expected array",
                )
                raise ValueError(f"{INDEX_CHART_ENDPOINT}: expected JSON array")
            by_date: dict[date, tuple[date, float, float | None]] = {}
            for item in raw:
                if not isinstance(item, dict):
                    continue
                d_raw = item.get("d")
                v_raw = item.get("v")
                pc_raw = item.get("pc")
                if isinstance(d_raw, bool) or not isinstance(d_raw, int | float):
                    continue
                if isinstance(v_raw, bool) or not isinstance(v_raw, int | float):
                    continue
                if not math.isfinite(float(v_raw)) or float(v_raw) <= 0:
                    continue
                try:
                    td = datetime.fromtimestamp(float(d_raw) / 1000.0, tz=UTC).date()
                except (OverflowError, OSError, ValueError):
                    continue
                pc: float | None = None
                if (
                    not isinstance(pc_raw, bool)
                    and isinstance(pc_raw, int | float)
                    and math.isfinite(float(pc_raw))
                ):
                    pc = float(pc_raw)
                by_date[td] = (td, float(v_raw), pc)
            return [by_date[k] for k in sorted(by_date)]

        return cast(
            list[tuple[date, float, float | None]],
            await self._guarded(INDEX_CHART_ENDPOINT, _call),
        )

    async def fetch_company_financial_docs(
        self, symbol: str
    ) -> list[tuple[str, date, str | None]]:
        """Annual/quarterly PDF metadata from ``POST /financials``.

        Returns ``(kind, manual_date, pdf_url)`` where kind is
        ``annual`` / ``quarterly`` / ``other``. Numeric line items are not in
        this payload — only filing dates + CDN paths.
        """
        if not isinstance(symbol, str) or not symbol.strip():
            return []
        sym = symbol.strip().upper()

        async def _call() -> list[tuple[str, date, str | None]]:
            raw = await self._request(
                "POST",
                COMPANY_FINANCIALS_PATH,
                data={"symbol": sym},
                log_context={"symbol": sym},
            )
            if not isinstance(raw, dict):
                log.error(
                    "cse_schema_error",
                    endpoint=COMPANY_FINANCIALS_ENDPOINT,
                    symbol=sym,
                    error="expected object",
                )
                raise ValueError(f"{COMPANY_FINANCIALS_ENDPOINT}: expected JSON object")
            out: list[tuple[str, date, str | None]] = []
            for kind, key in (
                ("annual", "infoAnnualData"),
                ("quarterly", "infoQuarterlyData"),
                ("other", "infoOtherData"),
            ):
                rows = raw.get(key)
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    md = row.get("manualDate")
                    if isinstance(md, bool) or not isinstance(md, int | float):
                        continue
                    try:
                        td = datetime.fromtimestamp(float(md) / 1000.0, tz=UTC).date()
                    except (OverflowError, OSError, ValueError):
                        continue
                    path = row.get("path")
                    pdf = resolve_pdf_url(path if isinstance(path, str) else None)
                    out.append((kind, td, pdf))
            out.sort(key=lambda t: t[1])
            return out

        return cast(
            list[tuple[str, date, str | None]],
            await self._guarded(COMPANY_FINANCIALS_ENDPOINT, _call),
        )

    async def fetch_financial_announcements_feed(
        self,
    ) -> list[dict[str, Any]]:
        """Recent market-wide financial PDF feed (``getFinancialAnnouncement``)."""

        async def _call() -> list[dict[str, Any]]:
            raw = await self._request(
                "POST",
                FINANCIAL_ANNOUNCEMENT_PATH,
                json_body={},
            )
            if not isinstance(raw, dict):
                return []
            rows = raw.get("reqFinancialAnnouncemnets")
            if not isinstance(rows, list):
                return []
            out: list[dict[str, Any]] = []
            for row in rows:
                if isinstance(row, dict):
                    out.append(row)
            return out

        return cast(
            list[dict[str, Any]],
            await self._guarded(FINANCIAL_ANNOUNCEMENT_ENDPOINT, _call),
        )

    async def fetch_company_sector(self, symbol: str) -> str | None:
        """Return sector label from ``POST /companyProfile`` ``reqComSumInfo``.

        Observed values: ``Banks``, ``Capital Goods``, ``Telecommunication Services``.
        """
        profile = await self.fetch_company_profile(symbol)
        if not profile:
            return None
        sector = profile.get("sector")
        if not isinstance(sector, str) or not sector.strip():
            return None
        cleaned = sector.strip()
        if len(cleaned) > 128:
            cleaned = cleaned[:128].rstrip()
        return cleaned

    async def fetch_company_profile(self, symbol: str) -> dict[str, Any] | None:
        """``POST /companyProfile`` — sector, directors, top posts.

        Returns a normalized dict::

            {
              "symbol": "JKH.N0000",
              "sector": "Capital Goods" | None,
              "name": str | None,
              "top_posts": [raw rows...],
              "directors": [raw rows...],
              "key_executives": [raw rows...],
            }
        """
        if not isinstance(symbol, str) or not symbol.strip():
            return None
        sym = symbol.strip().upper()

        async def _call() -> dict[str, Any] | None:
            raw = await self._request(
                "POST",
                COMPANY_PROFILE_PATH,
                data={"symbol": sym},
                log_context={"symbol": sym},
            )
            if not isinstance(raw, dict):
                log.error(
                    "cse_schema_error",
                    endpoint=COMPANY_PROFILE_ENDPOINT,
                    symbol=sym,
                    error="expected object",
                )
                raise ValueError(f"{COMPANY_PROFILE_ENDPOINT}: expected JSON object")

            def _row_list(key: str) -> list[dict[str, Any]]:
                rows = raw.get(key)
                if not isinstance(rows, list):
                    return []
                out: list[dict[str, Any]] = []
                for row in rows:
                    if isinstance(row, dict):
                        out.append(row)
                return out

            sector: str | None = None
            name: str | None = None
            summary = raw.get("reqComSumInfo")
            if isinstance(summary, list) and summary and isinstance(summary[0], dict):
                sec = summary[0].get("sector")
                if isinstance(sec, str) and sec.strip():
                    sector = sec.strip()[:128]
                nm = summary[0].get("name") or summary[0].get("companyName")
                if isinstance(nm, str) and nm.strip():
                    name = nm.strip()[:200]

            return {
                "symbol": sym,
                "sector": sector,
                "name": name,
                "top_posts": _row_list("topPosts"),
                "directors": _row_list("infoCompanyDirector"),
                "key_executives": _row_list("infoCompanyKeyExecutive"),
            }

        return cast(
            dict[str, Any] | None,
            await self._guarded(COMPANY_PROFILE_ENDPOINT, _call),
        )

    async def fetch_company_directors(self, symbol: str) -> list[dict[str, Any]]:
        """Official board seats from ``companyProfile`` (parsed).

        Each item: ``director_id``, ``display_name``, ``name_norm``, ``roles``,
        ``designation_raw``, ``source_bucket``.
        """
        from chime.extractors.cse_directors import merge_cse_board

        profile = await self.fetch_company_profile(symbol)
        if not profile:
            return []
        seats = merge_cse_board(
            top_posts=profile.get("top_posts"),
            directors=profile.get("directors"),
            key_executives=profile.get("key_executives"),
        )
        return [
            {
                "director_id": s.director_id,
                "display_name": s.display_name,
                "name_norm": s.name_norm,
                "roles": list(s.roles),
                "designation_raw": s.designation_raw,
                "source_bucket": s.source_bucket,
            }
            for s in seats
        ]

    async def fetch_buy_in_announcements(self) -> list[MarketNotice]:
        return await self._fetch_notice_list(
            endpoint=BUY_IN_ENDPOINT,
            path=BUY_IN_PATH,
            notice_type="buy_in",
            keys=("buyInBoardAnnouncements", "buyInAnnouncements", "reqBuyIn"),
        )

    async def fetch_non_compliance_announcements(self) -> list[MarketNotice]:
        return await self._fetch_notice_list(
            endpoint=NON_COMPLIANCE_ENDPOINT,
            path=NON_COMPLIANCE_PATH,
            notice_type="non_compliance",
            keys=(
                "nonComplianceAnnouncements",
                "nonCompliance",
                "reqNonCompliance",
            ),
        )

    async def fetch_market_notifications(self) -> list[MarketNotice]:
        """``GET /notifications`` — market halt / system banners."""

        async def _call() -> list[MarketNotice]:
            raw = await self._request("GET", NOTIFICATIONS_PATH)
            rows_raw: list[Any]
            if isinstance(raw, dict):
                content = raw.get("content")
                rows_raw = content if isinstance(content, list) else []
            elif isinstance(raw, list):
                rows_raw = raw
            else:
                log.error(
                    "cse_schema_error",
                    endpoint=NOTIFICATIONS_ENDPOINT,
                    error="expected object or array",
                )
                raise ValueError(f"{NOTIFICATIONS_ENDPOINT}: unexpected JSON")
            now = datetime.now(UTC)
            out: list[MarketNotice] = []
            for idx, item in enumerate(rows_raw):
                try:
                    row = FlexibleNoticeRow.model_validate(item)
                except ValidationError as exc:
                    log.warning(
                        "cse_notification_row_skipped",
                        endpoint=NOTIFICATIONS_ENDPOINT,
                        error=str(exc),
                        row=str(item)[:200],
                    )
                    continue
                notice = flexible_row_to_notice(
                    row,
                    notice_type="halt",
                    symbol="MARKET",
                    now=now,
                    fallback_idx=idx,
                )
                if notice is not None:
                    out.append(notice)
            return out

        return cast(
            list[MarketNotice], await self._guarded(NOTIFICATIONS_ENDPOINT, _call)
        )

    async def _fetch_notice_list(
        self,
        *,
        endpoint: str,
        path: str,
        notice_type: str,
        keys: tuple[str, ...],
    ) -> list[MarketNotice]:
        async def _call() -> list[MarketNotice]:
            raw = await self._request("POST", path, json_body={})
            rows_raw: list[Any] = []
            if isinstance(raw, list):
                rows_raw = raw
            elif isinstance(raw, dict):
                for key in keys:
                    cand = raw.get(key)
                    if isinstance(cand, list):
                        rows_raw = cand
                        break
                if not rows_raw:
                    for val in raw.values():
                        if isinstance(val, list):
                            rows_raw = val
                            break
            else:
                log.error(
                    "cse_schema_error",
                    endpoint=endpoint,
                    error="expected object or array",
                )
                raise ValueError(f"{endpoint}: unexpected JSON")
            now = datetime.now(UTC)
            out: list[MarketNotice] = []
            for idx, item in enumerate(rows_raw):
                try:
                    row = FlexibleNoticeRow.model_validate(item)
                except ValidationError as exc:
                    log.warning(
                        "cse_notice_row_skipped",
                        endpoint=endpoint,
                        error=str(exc),
                        row=str(item)[:200],
                    )
                    continue
                notice = flexible_row_to_notice(
                    row,
                    notice_type=notice_type,
                    now=now,
                    fallback_idx=idx,
                )
                if notice is not None:
                    out.append(notice)
            return out

        return cast(list[MarketNotice], await self._guarded(endpoint, _call))

    async def fetch_daily_market_summary(self) -> list[dict[str, Any]]:
        """Market-wide daily turnover / foreign flow (``POST /dailyMarketSummery``)."""

        async def _call() -> list[dict[str, Any]]:
            raw = await self._request(
                "POST",
                DAILY_MARKET_SUMMARY_PATH,
                json_body={},
            )
            rows = _flatten_daily_market_rows(raw)
            out: list[dict[str, Any]] = []

            def _num(row: dict[str, Any], key: str) -> float | None:
                val = row.get(key)
                if isinstance(val, bool) or not isinstance(val, int | float):
                    return None
                if not math.isfinite(float(val)):
                    return None
                return float(val)

            for row in rows:
                d = _ms_to_date(row.get("tradeDate"))
                if d is None:
                    continue
                fp = _num(row, "equityForeignPurchase")
                fs = _num(row, "equityForeignSales")
                foreign_net = None
                if fp is not None and fs is not None:
                    foreign_net = fp - fs
                out.append(
                    {
                        "trade_date": d,
                        "market_turnover": _num(row, "marketTurnover"),
                        "market_trades": _num(row, "marketTrades"),
                        "equity_foreign_purchase": fp,
                        "equity_foreign_sales": fs,
                        "foreign_net": foreign_net,
                        "volume_of_turnover": _num(row, "volumeOfTurnOverNumber"),
                        "market_cap": _num(row, "marketCap"),
                        "asi": _num(row, "asi"),
                        "raw": row,
                    }
                )
            return out

        return cast(
            list[dict[str, Any]],
            await self._guarded(DAILY_MARKET_SUMMARY_ENDPOINT, _call),
        )

    async def fetch_order_book(self, symbol: str) -> OrderBookSnapshot | None:
        """Fetch public order-book totals (``POST /orderBook`` form ``symbol=``)."""

        if not isinstance(symbol, str) or not symbol.strip():
            return None
        sym = symbol.strip().upper()

        async def _call() -> OrderBookSnapshot | None:
            raw = await self._request(
                "POST",
                ORDER_BOOK_PATH,
                data={"symbol": sym},
            )
            if not isinstance(raw, dict):
                log.error(
                    "cse_schema_error",
                    endpoint=ORDER_BOOK_ENDPOINT,
                    error="expected object",
                )
                raise ValueError(f"{ORDER_BOOK_ENDPOINT}: expected JSON object")
            try:
                parsed = OrderBookResponse.model_validate(raw)
            except ValidationError as exc:
                log.warning(
                    "cse_order_book_invalid",
                    endpoint=ORDER_BOOK_ENDPOINT,
                    symbol=sym,
                    error=str(exc),
                )
                return None
            return order_book_to_snapshot(
                symbol=sym,
                total=parsed.reqOrderBookTotal,
                levels=parsed.reqOrderBook,
                now=datetime.now(UTC),
            )

        return cast(
            OrderBookSnapshot | None, await self._guarded(ORDER_BOOK_ENDPOINT, _call)
        )
