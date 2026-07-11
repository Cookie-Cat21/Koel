"""Adapter for cse.lk's undocumented JSON endpoints (prices, announcements).

Verified 2026-07-11 — see docs/endpoint_probe_report.md. Inbound payloads are
validated/normalized into domain models. Failed calls are logged and retried
with backoff; a per-endpoint circuit breaker short-circuits sustained outages.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
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
from chime.domain import Disclosure, PriceSnapshot

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


class TradeSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reqTradeSummery: list[TradeSummaryRow] = Field(default_factory=list)


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


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {429, 500, 502, 503, 504}
    return False


def _ms_to_dt(ms: int | None) -> datetime:
    """Convert CSE millisecond epoch to aware UTC datetime.

    ``None`` is treated as the Unix epoch — never ``datetime.now()`` — so a
    missing timestamp cannot look "fresh" and bypass disclosure backfill gates.
    """
    if ms is None:
        return datetime(1970, 1, 1, tzinfo=UTC)
    return datetime.fromtimestamp(ms / 1000.0, tz=UTC)


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
    if value is None:
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


def trade_row_to_snapshot(row: TradeSummaryRow, *, now: datetime | None = None) -> PriceSnapshot:
    ts = _ms_to_dt(row.lastTradedTime) if row.lastTradedTime else (now or datetime.now(UTC))
    return PriceSnapshot(
        symbol=row.symbol.strip().upper(),
        price=row.price,
        previous_close=row.previousClose,
        change=row.change,
        change_pct=row.percentageChange,
        volume=row.sharevolume,
        trade_count=row.tradevolume,
        turnover=row.turnover,
        high=row.high,
        low=row.low,
        open=row.open,
        market_cap=row.marketCap,
        name=row.name,
        ts=ts,
    )


def symbol_info_to_snapshot(info: SymbolInfo, *, now: datetime | None = None) -> PriceSnapshot:
    return PriceSnapshot(
        symbol=info.symbol.strip().upper(),
        price=info.lastTradedPrice,
        previous_close=info.previousClose,
        change=info.change,
        change_pct=info.changePercentage,
        volume=info.tdyShareVolume,
        trade_count=info.tdyTradeVolume,
        turnover=info.tdyTurnover,
        high=info.hiTrade,
        low=info.lowTrade,
        open=None,
        market_cap=info.marketCap,
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
        published = datetime(1970, 1, 1, tzinfo=UTC)
    title = row.announcementCategory or "Announcement"
    if row.remarks:
        title = f"{title}: {row.remarks}"
    return Disclosure(
        external_id=str(external),
        symbol=symbol.strip().upper(),
        company_name=row.company,
        title=title,
        category=row.announcementCategory,
        url=f"{ANNOUNCEMENTS_PAGE}#{external}",
        published_at=published,
        seen_at=seen_at or datetime.now(UTC),
        doa_display=doa,
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
    ) -> Any:
        url = f"{self.base_url}{path}"
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
                )
                response.raise_for_status()
            if "json" not in content_type and response.text[:1] not in ("{", "["):
                log.warning("cse_non_json", path=path, content_type=content_type)
                raise httpx.HTTPStatusError(
                    "non-json response",
                    request=response.request,
                    response=response,
                )
            return response.json()
        except Exception as exc:
            log.warning("cse_request_failed", path=path, error=str(exc))
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
            raw = await self._request("POST", "/tradeSummary", json_body={})
            if not isinstance(raw, dict):
                log.error("cse_schema_error", endpoint="tradeSummary", error="expected object")
                raise ValueError("tradeSummary: expected JSON object")
            rows_raw = raw.get("reqTradeSummery") or []
            if not isinstance(rows_raw, list):
                log.error(
                    "cse_schema_error",
                    endpoint="tradeSummary",
                    error="reqTradeSummery not a list",
                )
                raise ValueError("tradeSummary: reqTradeSummery not a list")
            now = datetime.now(UTC)
            out: list[PriceSnapshot] = []
            for item in rows_raw:
                try:
                    row = TradeSummaryRow.model_validate(item)
                except ValidationError as exc:
                    log.warning(
                        "cse_trade_row_skipped",
                        endpoint="tradeSummary",
                        error=str(exc),
                        row=str(item)[:200],
                    )
                    continue
                out.append(trade_row_to_snapshot(row, now=now))
            return out

        return cast(list[PriceSnapshot], await self._guarded("tradeSummary", _call))

    async def fetch_company_info(self, symbol: str) -> PriceSnapshot | None:
        symbol = symbol.strip().upper()

        async def _call() -> PriceSnapshot | None:
            raw = await self._request(
                "POST",
                "/companyInfoSummery",
                data={"symbol": symbol},
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

    async def symbol_exists(self, symbol: str) -> bool:
        snap = await self.fetch_company_info(symbol)
        return snap is not None
