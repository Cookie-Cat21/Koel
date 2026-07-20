"""CSE adapter circuit-open / timeout / transport errors must propagate."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest
from structlog.testing import capture_logs

from koel.adapters.cse import CSEClient
from koel.circuit import CircuitOpenError


@pytest.mark.asyncio
async def test_fetch_announcements_for_symbol_reraises_circuit_open() -> None:
    """WS-017: CircuitOpenError must not become [] (poller treats [] as success)."""
    client = CSEClient(fail_max=1, reset_timeout=60.0, client=AsyncMock())
    breaker = client._breaker("getAnnouncementByCompany")
    breaker.record_failure()  # open the circuit (fail_max=1)

    with pytest.raises(CircuitOpenError, match="circuit open"):
        await client.fetch_announcements_for_symbol("JKH.N0000")


@pytest.mark.asyncio
async def test_fetch_approved_announcements_reraises_circuit_open() -> None:
    """WS-017: CircuitOpenError must not become [] on approvedAnnouncement."""
    client = CSEClient(fail_max=1, reset_timeout=60.0, client=AsyncMock())
    breaker = client._breaker("approvedAnnouncement")
    breaker.record_failure()

    with pytest.raises(CircuitOpenError, match="circuit open"):
        await client.fetch_approved_announcements()


@pytest.mark.asyncio
async def test_fetch_company_info_propagates_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E9-C02: httpx timeout after retries must surface (not None / soft-miss)."""
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    http = AsyncMock()
    http.request = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
    client = CSEClient(fail_max=99, reset_timeout=60.0, client=http)

    with pytest.raises(httpx.TimeoutException):
        await client.fetch_company_info("JKH.N0000")
    assert http.request.await_count == 3  # tenacity stop_after_attempt(3)


@pytest.mark.asyncio
async def test_fetch_company_info_logs_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E16-C01: symbol-specific timeout logs include path and normalized symbol."""
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    http = AsyncMock()
    http.request = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
    client = CSEClient(fail_max=99, reset_timeout=60.0, client=http)

    with capture_logs() as caps, pytest.raises(httpx.TimeoutException):
        await client.fetch_company_info("JKH.N0000")

    timeout_events = [e for e in caps if e.get("event") == "cse_timeout"]
    assert timeout_events, f"expected cse_timeout in {caps!r}"
    assert any("/companyInfoSummery" in str(e.get("path", "")) for e in timeout_events)
    assert any(e.get("symbol") == "JKH.N0000" for e in timeout_events)


@pytest.mark.asyncio
async def test_fetch_trade_summary_propagates_connect_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E9-C02: transport errors propagate after retries (poller must not treat as [])."""
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    http = AsyncMock()
    http.request = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
    client = CSEClient(fail_max=99, reset_timeout=60.0, client=http)

    with pytest.raises(httpx.TransportError):
        await client.fetch_trade_summary()
    assert http.request.await_count == 3
