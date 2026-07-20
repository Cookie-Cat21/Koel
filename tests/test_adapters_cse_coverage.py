"""Wave11/13: unit coverage push for cse adapter untested branches."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
from structlog.testing import capture_logs

from koel.adapters.cse import (
    CDN_BASE,
    AnnouncementRow,
    CSEClient,
    LegacyAnnouncementRow,
    SectorRow,
    SymbolInfo,
    _ms_to_dt,
    _parse_date_of_announcement,
    _retryable,
    allowed_cdn_pdf_url,
    allowed_filing_url,
    build_unique_company_name_map,
    legacy_pdf_urls_by_id,
    resolve_announcement_symbol,
    sector_row_to_snapshot,
    symbol_info_to_snapshot,
)
from koel.circuit import CircuitOpenError


def test_allowed_cdn_pdf_url_null_empty_and_traversal() -> None:
    assert allowed_cdn_pdf_url(None) is None
    assert allowed_cdn_pdf_url("") is None
    assert allowed_cdn_pdf_url("   ") is None
    assert allowed_cdn_pdf_url("https://cdn.cse.lk/upload/../etc/passwd") is None
    assert allowed_cdn_pdf_url("https://cdn.cse.lk/./ok.pdf") is None
    assert allowed_cdn_pdf_url("https://cdn.cse.lk/") == f"{CDN_BASE}/"
    assert allowed_cdn_pdf_url("https://cdn.cse.lk") == f"{CDN_BASE}/"


def test_allowed_filing_url_null_empty_creds_query_and_traversal() -> None:
    assert allowed_filing_url(None) is None
    assert allowed_filing_url("") is None
    assert allowed_filing_url("   ") is None
    assert allowed_filing_url("https://user:pass@www.cse.lk/announcements") is None
    assert allowed_filing_url("https://www.cse.lk/foo/../bar") is None
    assert allowed_filing_url("https://www.cse.lk/./announcements") is None
    assert (
        allowed_filing_url("https://www.cse.lk/announcements?x=1")
        == "https://www.cse.lk/announcements?x=1"
    )
    assert (
        allowed_filing_url("https://www.cse.lk/announcements?x=1#42")
        == "https://www.cse.lk/announcements?x=1#42"
    )


def test_legacy_pdf_urls_by_id_skips_missing_announcement_id() -> None:
    rows = [
        LegacyAnnouncementRow(announcementId=None, filePath="uploadAnnounceFiles/a.pdf"),
        LegacyAnnouncementRow(announcementId=9, filePath=None),
        LegacyAnnouncementRow(announcementId=10, filePath="uploadAnnounceFiles/b.pdf"),
    ]
    mapping = legacy_pdf_urls_by_id(rows)
    assert mapping == {"10": f"{CDN_BASE}/uploadAnnounceFiles/b.pdf"}


@pytest.mark.asyncio
async def test_fetch_legacy_announcements_schema_error_raises() -> None:
    from pydantic import ValidationError

    client = CSEClient(client=AsyncMock())
    client._request = AsyncMock(return_value=["not", "an", "object"])  # type: ignore[method-assign]

    with capture_logs() as logs, pytest.raises(ValidationError):
        await client.fetch_legacy_announcements("JKH.N0000")

    assert any(
        e.get("event") == "cse_schema_error" and e.get("endpoint") == "announcements" for e in logs
    )


@pytest.mark.asyncio
async def test_fetch_legacy_announcements_reraises_circuit_open() -> None:
    client = CSEClient(fail_max=1, reset_timeout=60.0, client=AsyncMock())
    client._breaker("announcements").record_failure()

    with pytest.raises(CircuitOpenError, match="circuit open"):
        await client.fetch_legacy_announcements("COMB.N0000")


@pytest.mark.asyncio
async def test_fetch_all_sectors_skips_blank_name() -> None:
    client = CSEClient(client=AsyncMock())
    client._request = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            {
                "sectorId": 223,
                "symbol": "EGY",
                "name": "   ",
                "indexValue": 100.0,
            },
            {
                "sectorId": 224,
                "symbol": "MAT",
                "name": "Materials",
                "indexValue": 200.0,
                "transactionTime": 1_720_000_000_000,
            },
        ]
    )

    with capture_logs() as logs:
        out = await client.fetch_all_sectors()

    assert len(out) == 1
    assert out[0].symbol == "MAT"
    assert any(
        e.get("event") == "cse_sector_row_skipped" and "blank" in str(e.get("error", ""))
        for e in logs
    )


@pytest.mark.asyncio
async def test_fetch_all_sectors_empty_ok_log() -> None:
    client = CSEClient(client=AsyncMock())
    client._request = AsyncMock(return_value=[])  # type: ignore[method-assign]

    with capture_logs() as logs:
        assert await client.fetch_all_sectors() == []

    assert {
        "event": "cse_all_sectors_empty_ok",
        "log_level": "warning",
        "endpoint": "allSectors",
    } in logs


@pytest.mark.asyncio
async def test_fetch_all_sectors_reraises_circuit_open() -> None:
    client = CSEClient(fail_max=1, reset_timeout=60.0, client=AsyncMock())
    client._breaker("allSectors").record_failure()

    with pytest.raises(CircuitOpenError, match="circuit open"):
        await client.fetch_all_sectors()


def test_sector_row_to_snapshot_defaults_ts_when_now_omitted() -> None:
    """No transactionTime and no now= → ts falls back to datetime.now(UTC)."""
    before = datetime.now(UTC) - timedelta(seconds=1)
    row = SectorRow(sectorId=1, symbol="egy", name="Energy", indexValue=10.0)
    snap = sector_row_to_snapshot(row)
    after = datetime.now(UTC) + timedelta(seconds=1)
    assert snap is not None
    assert before <= snap.ts <= after
    assert snap.symbol == "EGY"


# --- Wave13: remaining untested branches ---


def test_retryable_http_status_and_non_retryable() -> None:
    req = httpx.Request("POST", "https://www.cse.lk/api/tradeSummary")
    err_429 = httpx.HTTPStatusError(
        "429", request=req, response=httpx.Response(429, request=req)
    )
    err_503 = httpx.HTTPStatusError(
        "503", request=req, response=httpx.Response(503, request=req)
    )
    err_400 = httpx.HTTPStatusError(
        "400", request=req, response=httpx.Response(400, request=req)
    )
    assert _retryable(err_429)
    assert _retryable(err_503)
    assert not _retryable(err_400)
    assert not _retryable(ValueError("nope"))


def test_ms_to_dt_none_is_unix_epoch() -> None:
    assert _ms_to_dt(None) == datetime(1970, 1, 1, tzinfo=UTC)


def test_parse_date_of_announcement_blank_after_strip() -> None:
    assert _parse_date_of_announcement("   ") is None


def test_symbol_info_to_snapshot_maps_fields() -> None:
    now = datetime(2026, 7, 12, 10, 0, 0, tzinfo=UTC)
    info = SymbolInfo(
        symbol="jkh.n0000",
        name="John Keells",
        lastTradedPrice=185.5,
        previousClose=180.0,
        change=5.5,
        changePercentage=3.06,
        tdyShareVolume=12000,
        tdyTradeVolume=45,
        tdyTurnover=2_200_000,
        hiTrade=186.0,
        lowTrade=179.0,
        marketCap=1e11,
    )
    snap = symbol_info_to_snapshot(info, now=now)
    assert snap is not None
    assert snap.symbol == "JKH.N0000"
    assert snap.price == 185.5
    assert snap.previous_close == 180.0
    assert snap.change == 5.5
    assert snap.change_pct == 3.06
    assert snap.volume == 12000
    assert snap.trade_count == 45
    assert snap.turnover == 2_200_000
    assert snap.high == 186.0
    assert snap.low == 179.0
    assert snap.open is None
    assert snap.market_cap == 1e11
    assert snap.name == "John Keells"
    assert snap.ts == now


def test_build_unique_company_name_map_skips_null_and_blank() -> None:
    mapping = build_unique_company_name_map(
        [
            ("JKH.N0000", None),
            ("   ", "Blank Symbol PLC"),
            ("COMB.N0000", "   "),
            ("LOLC.N0000", "LOLC Holdings PLC"),
        ]
    )
    assert mapping == {"LOLC HOLDINGS PLC": "LOLC.N0000"}


def test_resolve_announcement_symbol_blank_company_returns_none() -> None:
    name_map = {"JOHN KEELLS HOLDINGS PLC": "JKH.N0000"}
    allowed = {"JKH.N0000"}
    blank = AnnouncementRow(announcementId=1, company="   ", symbol=None)
    assert resolve_announcement_symbol(blank, name_map=name_map, allowed_symbols=allowed) is None
    missing = AnnouncementRow(announcementId=2, company=None, symbol=None)
    assert resolve_announcement_symbol(missing, name_map=name_map, allowed_symbols=allowed) is None


@pytest.mark.asyncio
async def test_cse_client_owns_client_aclose_and_context_manager() -> None:
    http = AsyncMock()
    http.aclose = AsyncMock()
    client = CSEClient(client=http)
    assert client._owns_client is False
    await client.aclose()
    http.aclose.assert_not_awaited()

    owned = CSEClient(client=None)
    owned._client.aclose = AsyncMock()  # type: ignore[method-assign]
    assert owned._owns_client is True
    await owned.aclose()
    owned._client.aclose.assert_awaited_once()

    ctx_http = AsyncMock()
    ctx_http.aclose = AsyncMock()
    async with CSEClient(client=ctx_http) as entered:
        assert entered is not None
        assert entered._owns_client is False
    ctx_http.aclose.assert_not_awaited()


@pytest.mark.asyncio
async def test_request_http_error_raises_and_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    req = httpx.Request("POST", "https://www.cse.lk/api/tradeSummary")
    response = httpx.Response(500, text="<html>boom</html>", request=req)
    http = AsyncMock()
    http.request = AsyncMock(return_value=response)
    client = CSEClient(fail_max=99, reset_timeout=60.0, client=http)

    with capture_logs() as logs, pytest.raises(httpx.HTTPStatusError):
        await client._request("POST", "/tradeSummary", json_body={})

    assert any(e.get("event") == "cse_http_error" for e in logs)
    assert http.request.await_count == 3


@pytest.mark.asyncio
async def test_request_non_json_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    req = httpx.Request("POST", "https://www.cse.lk/api/tradeSummary")
    response = httpx.Response(
        200,
        text="<html>not json</html>",
        headers={"content-type": "text/html"},
        request=req,
    )
    http = AsyncMock()
    http.request = AsyncMock(return_value=response)
    client = CSEClient(fail_max=99, reset_timeout=60.0, client=http)

    with capture_logs() as logs, pytest.raises(httpx.HTTPStatusError, match="non-json"):
        await client._request("POST", "/tradeSummary", json_body={})

    assert any(e.get("event") == "cse_non_json" for e in logs)


@pytest.mark.asyncio
async def test_request_http_204_empty_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Indexes (ASPI) hit companyProfile with 204 + empty body."""
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    req = httpx.Request("POST", "https://www.cse.lk/api/companyProfile")
    response = httpx.Response(
        204,
        content=b"",
        headers={"content-type": "application/json"},
        request=req,
    )
    http = AsyncMock()
    http.request = AsyncMock(return_value=response)
    client = CSEClient(fail_max=99, reset_timeout=60.0, client=http)

    with capture_logs() as logs:
        out = await client._request(
            "POST",
            "/companyProfile",
            data={"symbol": "ASPI"},
            log_context={"symbol": "ASPI"},
        )

    assert out is None
    assert any(e.get("event") == "cse_empty_response" for e in logs)


@pytest.mark.asyncio
async def test_request_json_success() -> None:
    req = httpx.Request("POST", "https://www.cse.lk/api/tradeSummary")
    response = httpx.Response(
        200,
        json={"ok": True},
        headers={"content-type": "application/json"},
        request=req,
    )
    http = AsyncMock()
    http.request = AsyncMock(return_value=response)
    client = CSEClient(client=http)
    assert await client._request("POST", "/tradeSummary", json_body={}) == {"ok": True}


@pytest.mark.asyncio
async def test_fetch_trade_summary_rejects_non_object() -> None:
    client = CSEClient(client=AsyncMock())
    client._request = AsyncMock(return_value=["not", "object"])  # type: ignore[method-assign]

    with capture_logs() as logs, pytest.raises(ValueError, match="expected JSON object"):
        await client.fetch_trade_summary()

    assert any(
        e.get("event") == "cse_schema_error" and e.get("endpoint") == "tradeSummary" for e in logs
    )


@pytest.mark.asyncio
async def test_fetch_trade_summary_rejects_non_list_rows() -> None:
    client = CSEClient(client=AsyncMock())
    client._request = AsyncMock(  # type: ignore[method-assign]
        return_value={"reqTradeSummery": "oops"}
    )

    with capture_logs() as logs, pytest.raises(ValueError, match="not a list"):
        await client.fetch_trade_summary()

    assert any(
        e.get("event") == "cse_schema_error" and "not a list" in str(e.get("error", ""))
        for e in logs
    )


@pytest.mark.asyncio
async def test_fetch_trade_summary_skips_invalid_rows() -> None:
    client = CSEClient(client=AsyncMock())
    client._request = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "reqTradeSummery": [
                {"symbol": "BAD"},  # missing price → ValidationError
                {
                    "symbol": "jkh.n0000",
                    "price": 185.5,
                    "lastTradedTime": 1_720_000_000_000,
                },
            ]
        }
    )

    with capture_logs() as logs:
        out = await client.fetch_trade_summary()

    assert len(out) == 1
    assert out[0].symbol == "JKH.N0000"
    assert out[0].price == 185.5
    assert any(e.get("event") == "cse_trade_row_skipped" for e in logs)


@pytest.mark.asyncio
async def test_fetch_company_info_success_and_schema_miss() -> None:
    client = CSEClient(client=AsyncMock())
    client._request = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "reqSymbolInfo": {
                "symbol": "comb.n0000",
                "lastTradedPrice": 95.0,
                "name": "Commercial Bank",
            }
        }
    )
    snap = await client.fetch_company_info("comb.n0000")
    assert snap is not None
    assert snap.symbol == "COMB.N0000"
    assert snap.price == 95.0

    client._request = AsyncMock(return_value={"unexpected": True})  # type: ignore[method-assign]
    with capture_logs() as logs:
        assert await client.fetch_company_info("MISSING.N0000") is None
    assert any(
        e.get("event") == "cse_schema_error" and e.get("endpoint") == "companyInfoSummery"
        for e in logs
    )


@pytest.mark.asyncio
async def test_fetch_announcements_for_symbol_with_dates_and_rows() -> None:
    client = CSEClient(client=AsyncMock())
    client._request = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "reqCompanyAnnouncement": [
                {
                    "announcementId": 99,
                    "announcementCategory": "Financial",
                    "createdDate": 1_720_000_000_000,
                    "remarks": "Q1",
                },
                {
                    # no id → skipped by announcement_to_disclosure
                    "announcementCategory": "Other",
                },
            ]
        }
    )

    out = await client.fetch_announcements_for_symbol(
        "jkh.n0000",
        from_date="2026-01-01",
        to_date="2026-07-12",
    )
    assert len(out) == 1
    assert out[0].external_id == "99"
    assert out[0].symbol == "JKH.N0000"
    assert out[0].title == "Financial: Q1"
    client._request.assert_awaited_once()
    call_kwargs = client._request.await_args.kwargs
    assert call_kwargs["data"]["fromDate"] == "2026-01-01"
    assert call_kwargs["data"]["toDate"] == "2026-07-12"


@pytest.mark.asyncio
async def test_fetch_announcements_for_symbol_schema_error() -> None:
    from pydantic import ValidationError

    client = CSEClient(client=AsyncMock())
    client._request = AsyncMock(return_value=["bad"])  # type: ignore[method-assign]

    with capture_logs() as logs, pytest.raises(ValidationError):
        await client.fetch_announcements_for_symbol("JKH.N0000")

    assert any(
        e.get("event") == "cse_schema_error"
        and e.get("endpoint") == "getAnnouncementByCompany"
        for e in logs
    )


@pytest.mark.asyncio
async def test_fetch_approved_announcements_success_and_schema_error() -> None:
    from pydantic import ValidationError

    client = CSEClient(client=AsyncMock())
    client._request = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "approvedAnnouncements": [
                {"announcementId": 1, "company": "John Keells Holdings PLC"},
            ]
        }
    )
    rows = await client.fetch_approved_announcements()
    assert len(rows) == 1
    assert rows[0].announcementId == 1

    client._request = AsyncMock(return_value=["bad"])  # type: ignore[method-assign]
    with capture_logs() as logs, pytest.raises(ValidationError):
        await client.fetch_approved_announcements()
    assert any(
        e.get("event") == "cse_schema_error" and e.get("endpoint") == "approvedAnnouncement"
        for e in logs
    )
