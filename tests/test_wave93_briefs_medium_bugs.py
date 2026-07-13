"""Wave93 briefs: CDN PDF type/header hardening."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from chime.briefs.extract import CdnPdfPermanentError, fetch_cdn_pdf

CDN_PDF = "https://cdn.cse.lk/uploadAnnounceFiles/x.pdf"


@pytest.mark.asyncio
async def test_fetch_cdn_pdf_rejects_non_pdf_content_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"%PDF-1.7\n",
            headers={"Content-Type": "text/html; charset=utf-8"},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(CdnPdfPermanentError, match="content-type rejected"):
            await fetch_cdn_pdf(CDN_PDF, max_bytes=1024, client=client)


@pytest.mark.asyncio
async def test_fetch_cdn_pdf_rejects_non_pdf_body_without_type_header() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, content=b"<html>login</html>")
    )

    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(CdnPdfPermanentError, match="body was not a PDF"):
            await fetch_cdn_pdf(CDN_PDF, max_bytes=1024, client=client)


@pytest.mark.asyncio
async def test_fetch_cdn_pdf_malformed_headers_do_not_soft_accept_redirect() -> None:
    class _Stream:
        async def __aenter__(self) -> Any:
            return SimpleNamespace(
                status_code=302,
                headers=True,
                is_redirect=False,
                aiter_bytes=lambda: _aiter([]),
            )

        async def __aexit__(self, *_args: object) -> None:
            return None

    class _Client:
        def stream(self, *_args: object, **_kwargs: object) -> _Stream:
            return _Stream()

    async def _aiter(chunks: list[bytes]) -> Any:
        for chunk in chunks:
            yield chunk

    with pytest.raises(CdnPdfPermanentError, match="redirect rejected"):
        await fetch_cdn_pdf(CDN_PDF, max_bytes=1024, client=_Client())  # type: ignore[arg-type]
