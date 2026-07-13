"""Wave89: medium+ bugs — CSE HTTP status/CT + pace soft-accepts.

1. ``CSEClient._request`` must isinstance-guard ``status_code`` (no
   ``True >= 400`` soft-accept as HTTP success mid poll).
2. ``CSEClient._request`` must isinstance-guard ``content-type`` (no
   ``"json" not in`` TypeError / membership soft-accept on non-str CT).
3. ``CSEClient`` ctor must reject bool / non-finite ``min_interval_seconds``
   (no ``float(True)==1.0`` soft-accept mid pace).
4. ``_retryable`` must isinstance-guard status (no bool/non-int classify).
"""

from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from chime.adapters.cse import CSEClient, _retryable

ROOT = Path(__file__).resolve().parents[1]


def _mock_response(
    *,
    status_code: Any = 200,
    content_type: Any = "application/json",
    text: str = '{"ok": true}',
    json_body: Any = None,
) -> SimpleNamespace:
    headers = SimpleNamespace(
        get=lambda key, default="": (
            content_type if key.lower() == "content-type" else default
        )
    )
    req = httpx.Request("POST", "https://www.cse.lk/api/tradeSummary")

    def raise_for_status() -> None:
        if (
            isinstance(status_code, int)
            and not isinstance(status_code, bool)
            and status_code >= 400
        ):
            raise httpx.HTTPStatusError(
                f"HTTP {status_code}",
                request=req,
                response=httpx.Response(status_code, request=req),
            )

    return SimpleNamespace(
        status_code=status_code,
        headers=headers,
        text=text,
        request=req,
        raise_for_status=raise_for_status,
        json=lambda: json_body if json_body is not None else {"ok": True},
    )


@pytest.mark.asyncio
async def test_request_rejects_bool_status_and_non_str_content_type() -> None:
    client = CSEClient(client=httpx.AsyncClient())
    try:
        client._client.request = AsyncMock(  # type: ignore[method-assign]
            return_value=_mock_response(status_code=True)
        )
        with pytest.raises(httpx.HTTPStatusError, match="invalid CSE status_code"):
            await client._request("POST", "/tradeSummary", json_body={})

        client._client.request = AsyncMock(  # type: ignore[method-assign]
            return_value=_mock_response(
                status_code=200,
                content_type=True,
                text="not-json",
            )
        )
        with pytest.raises(httpx.HTTPStatusError, match="non-json"):
            await client._request("POST", "/tradeSummary", json_body={})

        client._client.request = AsyncMock(  # type: ignore[method-assign]
            return_value=_mock_response(
                status_code=200,
                content_type="application/json",
                text='{"reqTradeSummery": []}',
                json_body={"reqTradeSummery": []},
            )
        )
        assert await client._request("POST", "/tradeSummary", json_body={}) == {
            "reqTradeSummery": []
        }
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_request_still_raises_on_http_error_status() -> None:
    client = CSEClient(client=httpx.AsyncClient())
    try:
        client._client.request = AsyncMock(  # type: ignore[method-assign]
            return_value=_mock_response(status_code=503, text="unavailable")
        )
        with pytest.raises(httpx.HTTPStatusError):
            await client._request("POST", "/tradeSummary", json_body={})
    finally:
        await client.aclose()


def test_min_interval_rejects_bool_and_non_finite() -> None:
    cases: list[tuple[Any, float]] = [
        (True, 0.0),
        (False, 0.0),
        (math.nan, 0.0),
        (math.inf, 0.0),
        ("0.5", 0.0),
        (0.25, 0.25),
    ]
    for raw, expected in cases:
        client = CSEClient(
            min_interval_seconds=raw,  # type: ignore[arg-type]
            client=httpx.AsyncClient(),
        )
        assert client._min_interval == expected


def test_retryable_rejects_bool_status() -> None:
    req = httpx.Request("POST", "https://www.cse.lk/api/tradeSummary")
    resp = httpx.Response(500, request=req)
    object.__setattr__(resp, "status_code", True)
    exc = httpx.HTTPStatusError("boom", request=req, response=resp)
    assert _retryable(exc) is False

    resp500 = httpx.Response(500, request=req)
    assert _retryable(httpx.HTTPStatusError("x", request=req, response=resp500)) is True

    resp429 = httpx.Response(429, request=req)
    assert _retryable(httpx.HTTPStatusError("x", request=req, response=resp429)) is True


def test_cse_request_source_guards() -> None:
    src = (ROOT / "chime" / "adapters" / "cse.py").read_text(encoding="utf-8")
    chunk = src.split("async def _request")[1].split("async def _guarded")[0]
    assert "isinstance(raw_status, int)" in chunk
    assert "isinstance(raw_status, bool)" in chunk
    assert "isinstance(raw_ct, str)" in chunk
    assert "response.status_code >= 400" not in chunk

    ctor = src.split("def __init__")[1].split("def _breaker")[0]
    assert "isinstance(min_interval_seconds, bool)" in ctor
    assert "math.isfinite" in ctor

    retry = src.split("def _retryable")[1].split("_UNIX_EPOCH")[0]
    assert "isinstance(raw_status, int)" in retry
    assert "isinstance(raw_status, bool)" in retry
