"""Wave90: medium+ bugs — CSE HTTP status / CT / pace soft-accepts.

1. ``CSEClient._request`` must reject bool ``status_code`` (``True >= 400`` is
   False, so a poisoned status used to soft-accept as HTTP success).
2. ``CSEClient._request`` must typeof-guard ``content-type`` before
   ``\"json\" not in …`` (non-string CT mocks used to throw mid classify).
3. ``_retryable`` must reject bool / non-int status (no poisoned retry classify).
4. ``CSEClient`` must reject bool ``min_interval_seconds`` (``float(True)==1.0``
   used to enable a fake 1s pace).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from chime.adapters.cse import CSEClient, _retryable

ROOT = Path(__file__).resolve().parents[1]


def test_retryable_rejects_bool_status_soft_accept() -> None:
    req = httpx.Request("POST", "https://www.cse.lk/api/tradeSummary")
    poisoned = httpx.Response(500, request=req)
    poisoned.status_code = True  # type: ignore[assignment]
    err = httpx.HTTPStatusError("boom", request=req, response=poisoned)
    assert not _retryable(err)

    ok = httpx.HTTPStatusError(
        "503", request=req, response=httpx.Response(503, request=req)
    )
    assert _retryable(ok)

    src = (ROOT / "chime" / "adapters" / "cse.py").read_text(encoding="utf-8")
    chunk = src.split("def _retryable")[1].split("def _try_ms_to_dt")[0]
    assert "isinstance(raw_status, bool)" in chunk
    assert "exc.response.status_code in {429" not in chunk


def test_cse_client_rejects_bool_min_interval_soft_accept() -> None:
    client = CSEClient(min_interval_seconds=True)  # type: ignore[arg-type]
    assert client._min_interval == 0.0
    client2 = CSEClient(min_interval_seconds=float("nan"))
    assert client2._min_interval == 0.0
    client3 = CSEClient(min_interval_seconds=0.5)
    assert client3._min_interval == 0.5

    src = (ROOT / "chime" / "adapters" / "cse.py").read_text(encoding="utf-8")
    ctor = src.split("class CSEClient")[1].split("async def _pace")[0]
    assert "isinstance(min_interval_seconds, bool)" in ctor


@pytest.mark.asyncio
async def test_request_rejects_bool_status_and_non_str_content_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("asyncio.sleep", AsyncMock())
    req = httpx.Request("POST", "https://www.cse.lk/api/tradeSummary")

    # Bool status must fail closed (not soft-accept as success) and not retry.
    poisoned = httpx.Response(
        200,
        json={"ok": True},
        headers={"content-type": "application/json"},
        request=req,
    )
    poisoned.status_code = True  # type: ignore[assignment]
    http = AsyncMock()
    http.request = AsyncMock(return_value=poisoned)
    client = CSEClient(fail_max=99, reset_timeout=60.0, client=http)
    with pytest.raises(httpx.HTTPStatusError, match="invalid CSE status_code"):
        await client._request("POST", "/tradeSummary", json_body={})
    assert http.request.await_count == 1

    # Non-string content-type must not throw on membership; JSON body still ok.
    class _Hdr(dict):
        def get(self, key: str, default: object = None) -> object:  # type: ignore[override]
            if key.lower() == "content-type":
                return True
            return dict.get(self, key, default)

    class _Resp:
        status_code = 200
        text = '{"ok": true}'
        request = req
        headers = _Hdr()

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, bool]:
            return {"ok": True}

    http.request = AsyncMock(return_value=_Resp())
    client2 = CSEClient(client=http)
    assert await client2._request("POST", "/tradeSummary", json_body={}) == {"ok": True}

    src = (ROOT / "chime" / "adapters" / "cse.py").read_text(encoding="utf-8")
    chunk = src.split("async def _request")[1].split("async def _guarded")[0]
    assert "isinstance(raw_status, int)" in chunk
    assert "isinstance(raw_ct, str)" in chunk
    assert "response.status_code >= 400" not in chunk
