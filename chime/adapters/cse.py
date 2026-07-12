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
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
import structlog
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from chime.circuit import CircuitBreaker, CircuitOpenError
from chime.domain import Disclosure, PriceSnapshot, SectorSnapshot

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
TRADE_SUMMARY_ENDPOINT = "tradeSummary"
TRADE_SUMMARY_PATH = "/tradeSummary"
ALL_SECTORS_ENDPOINT = "allSectors"
ALL_SECTORS_PATH = "/allSectors"
LEGACY_ANNOUNCEMENTS_ENDPOINT = "announcements"
LEGACY_ANNOUNCEMENTS_PATH = "/announcements"


def _announcement_url(external_id: str) -> str:
    """Public CSE announcement page anchor used in Telegram disclosure alerts."""
    return f"{ANNOUNCEMENTS_PAGE}#{external_id}"


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
    segments = [s for s in path.split("/") if s != ""]
    if any(seg == ".." or seg == "." for seg in segments):
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
    segments = [s for s in path.split("/") if s != ""]
    if any(seg == ".." or seg == "." for seg in segments):
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
    segments = [s for s in path.split("/") if s != ""]
    if not segments or any(seg == ".." or seg == "." for seg in segments):
        return None
    return allowed_cdn_pdf_url(f"{CDN_BASE}/{'/'.join(segments)}")


class TradeSummaryRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

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
    lastTradedTime: int | None = None


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


class LegacyAnnouncementResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    infoAnnouncement: list[LegacyAnnouncementRow] = Field(default_factory=list)


def legacy_pdf_urls_by_id(rows: list[LegacyAnnouncementRow]) -> dict[str, str]:
    """Build ``announcementId`` → CDN PDF URL map (skips null / empty paths)."""
    out: dict[str, str] = {}
    for row in rows:
        if row.announcementId is None:
            continue
        pdf_url = resolve_pdf_url(row.filePath)
        if pdf_url is None:
            continue
        out[str(row.announcementId)] = pdf_url
    return out


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {429, 500, 502, 503, 504}
    return False


_UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _try_ms_to_dt(ms: int) -> datetime | None:
    """Convert CSE millisecond epoch to UTC, or ``None`` on overflow / invalid."""
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
    fallback = now or datetime.now(UTC)
    ts = (
        _try_ms_to_dt(row.lastTradedTime) or fallback
        if row.lastTradedTime
        else fallback
    )
    return PriceSnapshot(
        symbol=row.symbol.strip().upper(),
        price=row.price,
        previous_close=_finite_or_none(row.previousClose),
        change=_finite_or_none(row.change),
        change_pct=_finite_or_none(row.percentageChange),
        volume=_finite_or_none(row.sharevolume),
        trade_count=_finite_or_none(row.tradevolume),
        turnover=_finite_or_none(row.turnover),
        high=_finite_or_none(row.high),
        low=_finite_or_none(row.low),
        open=_finite_or_none(row.open),
        market_cap=_finite_or_none(row.marketCap),
        name=row.name,
        ts=ts,
    )


def sector_row_to_snapshot(row: SectorRow, *, now: datetime | None = None) -> SectorSnapshot:
    """Normalize an allSectors row; overflow transactionTime → poll time."""
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


def symbol_info_to_snapshot(
    info: SymbolInfo, *, now: datetime | None = None
) -> PriceSnapshot | None:
    """Normalize companyInfoSummery. ``None`` when last price is non-finite."""
    if not math.isfinite(info.lastTradedPrice):
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
    # Prefer createdDate (epoch ms) for published_at / alert gating.
    # Treat <=0 as missing. DOA is never used for gating — laggy calendar
    # strings would fire (or miss) disclosure rules incorrectly. Fail-closed
    # to Unix epoch so rules see published_at as stale. Still parse DOA into
    # doa_display for logging / title context.
    doa = _parse_date_of_announcement(row.dateOfAnnouncement)
    if row.createdDate is not None and row.createdDate > 0:
        published = _ms_to_dt(row.createdDate)
    else:
        published = _UNIX_EPOCH
        if doa is not None:
            log.warning(
                "cse_disclosure_doa_display_only",
                external_id=str(external),
                symbol=symbol.strip().upper(),
                date_of_announcement=row.dateOfAnnouncement,
                doa_display=doa.isoformat(),
                published_at=published.isoformat(),
            )
    title = row.announcementCategory or "Announcement"
    if row.remarks:
        title = f"{title}: {row.remarks}"
    return Disclosure(
        external_id=str(external),
        symbol=symbol.strip().upper(),
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
            content_type = response.headers.get("content-type", "")
            if response.status_code >= 400:
                log.warning(
                    "cse_http_error",
                    path=path,
                    status=response.status_code,
                    body=response.text[:300],
                    **context,
                )
                response.raise_for_status()
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
                if not row.symbol.strip() or not row.name.strip():
                    log.warning(
                        "cse_sector_row_skipped",
                        endpoint=ALL_SECTORS_ENDPOINT,
                        error="blank symbol or name",
                        row=str(item)[:200],
                    )
                    continue
                out.append(sector_row_to_snapshot(row, now=now))
            return out

        return cast(list[SectorSnapshot], await self._guarded(ALL_SECTORS_ENDPOINT, _call))

    async def fetch_company_info(self, symbol: str) -> PriceSnapshot | None:
        symbol = symbol.strip().upper()

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
        symbol = symbol.strip().upper()
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
        symbol = symbol.strip().upper()

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
