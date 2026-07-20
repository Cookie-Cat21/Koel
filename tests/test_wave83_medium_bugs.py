"""Wave83: medium+ bugs — CDN fetch soft-accepts.

1. ``fetch_cdn_pdf`` must reject bool ``status_code`` (no ``int(True)==1``).
2. ``fetch_cdn_pdf`` must require ``is_redirect is True`` (no ``bool("yes")``).
3. ``fetch_cdn_pdf`` must reject bool / non-digit ``content-length``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from koel.briefs.extract import CdnPdfPermanentError, fetch_cdn_pdf

ROOT = Path(__file__).resolve().parents[1]
CDN_PDF = "https://cdn.cse.lk/uploadAnnounceFiles/x.pdf"


@pytest.mark.asyncio
async def test_fetch_cdn_pdf_rejects_bool_status_redirect_and_length() -> None:
    class _Stream:
        def __init__(self, response: Any) -> None:
            self._response = response

        async def __aenter__(self) -> Any:
            return self._response

        async def __aexit__(self, *_a: object) -> None:
            return None

    class _Client:
        def __init__(self, response: Any) -> None:
            self._response = response

        def stream(self, *_a: object, **_k: object) -> _Stream:
            return _Stream(self._response)

    async def _aiter(chunks: list[bytes]) -> Any:
        for c in chunks:
            yield c

    def client_for(response: Any) -> _Client:
        return _Client(response)

    assert (
        await fetch_cdn_pdf(
            CDN_PDF,
            max_bytes=1024,
            client=client_for(
                SimpleNamespace(
                    status_code=True,
                    headers={},
                    is_redirect=False,
                    aiter_bytes=lambda: _aiter([]),
                )
            ),
        )
        is None
    )
    assert (
        await fetch_cdn_pdf(
            CDN_PDF,
            max_bytes=1024,
            client=client_for(
                SimpleNamespace(
                    status_code=200,
                    headers={},
                    is_redirect="yes",
                    aiter_bytes=lambda: _aiter([b"%PDF"]),
                )
            ),
        )
        == b"%PDF"
    )
    assert (
        await fetch_cdn_pdf(
            CDN_PDF,
            max_bytes=1024,
            client=client_for(
                SimpleNamespace(
                    status_code=200,
                    headers={"content-length": True},
                    is_redirect=False,
                    aiter_bytes=lambda: _aiter([b"%PDF"]),
                )
            ),
        )
        == b"%PDF"
    )
    assert (
        await fetch_cdn_pdf(
            CDN_PDF,
            max_bytes=1024,
            client=client_for(
                SimpleNamespace(
                    status_code=200,
                    headers={"content-length": 4},
                    is_redirect=False,
                    aiter_bytes=lambda: _aiter([b"%PDF"]),
                )
            ),
        )
        == b"%PDF"
    )
    with pytest.raises(CdnPdfPermanentError, match="too large"):
        await fetch_cdn_pdf(
            CDN_PDF,
            max_bytes=1024,
            client=client_for(
                SimpleNamespace(
                    status_code=200,
                    headers={"content-length": "99999"},
                    is_redirect=False,
                    aiter_bytes=lambda: _aiter([]),
                )
            ),
        )
    transport = httpx.MockTransport(
        lambda _r: httpx.Response(200, content=b"%PDF", headers={"content-length": "4"})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        assert await fetch_cdn_pdf(CDN_PDF, max_bytes=1024, client=client) == b"%PDF"


def test_fetch_cdn_pdf_source_guards() -> None:
    src = (ROOT / "koel" / "briefs" / "extract.py").read_text(encoding="utf-8")
    chunk = src.split("async def fetch_cdn_pdf")[1].split("chunks: list[bytes]")[0]
    assert "isinstance(raw_status, int)" in chunk
    assert "isinstance(raw_status, bool)" in chunk
    assert "is True" in chunk
    assert 'int(getattr(response, "status_code"' not in chunk
