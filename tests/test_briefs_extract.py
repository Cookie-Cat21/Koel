"""PDF extract + CDN fetch for filing briefs (wave4)."""

from __future__ import annotations

import builtins
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from chime.briefs import BriefSettings, build_brief_prompt
from chime.briefs.extract import CdnPdfPermanentError, extract_pdf_text, fetch_cdn_pdf
from chime.briefs.worker import claim_pending_briefs


def _tiny_pdf_bytes(text: str = "Hello Brief") -> bytes:
    """Build a minimal PDF with extractable text (correct xref offsets)."""
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        ),
    ]
    stream = f"BT /F1 12 Tf 50 100 Td ({text}) Tj ET\n".encode()
    objects.append(
        f"4 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"endstream\nendobj\n"
    )
    objects.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
        ).encode()
    )
    return bytes(out)


def _enabled_settings(**kwargs: object) -> BriefSettings:
    base: dict[str, object] = dict(
        enabled=True,
        api_key="test-key",
        provider="gemini",
        model="gemini-2.0-flash",
        max_briefs_per_day=50,
        max_input_chars=12_000,
        pdf_max_bytes=5_242_880,
    )
    base.update(kwargs)
    return BriefSettings(**base)  # type: ignore[arg-type]


def test_extract_pdf_text_empty_bytes() -> None:
    assert extract_pdf_text(b"") == ""


def test_extract_pdf_text_stub_without_pypdf(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "pypdf", raising=False)
    real_import = builtins.__import__

    def _block_pypdf(name: str, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        if name == "pypdf" or name.startswith("pypdf."):
            raise ImportError("blocked for test")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", _block_pypdf)
    assert extract_pdf_text(b"%PDF-1.4 fake") == ""


def test_extract_pdf_text_with_tiny_pdf_or_skip() -> None:
    pytest.importorskip("pypdf")
    text = extract_pdf_text(_tiny_pdf_bytes("Hello Brief"))
    assert "Hello Brief" in text


def test_extract_pdf_text_corrupt_returns_empty() -> None:
    pytest.importorskip("pypdf")
    assert extract_pdf_text(b"not-a-pdf") == ""


@pytest.mark.asyncio
async def test_fetch_cdn_pdf_rejects_non_cdn() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(200, content=b"%PDF"))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(CdnPdfPermanentError, match="not allowlisted"):
            await fetch_cdn_pdf(
                "https://evil.example/x.pdf",
                max_bytes=1024,
                client=client,
            )


@pytest.mark.asyncio
async def test_fetch_cdn_pdf_ok() -> None:
    body = _tiny_pdf_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "cdn.cse.lk"
        return httpx.Response(200, content=body)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        out = await fetch_cdn_pdf(
            "https://cdn.cse.lk/uploadAnnounceFiles/x.pdf",
            max_bytes=10_000,
            client=client,
        )
    assert out == body


@pytest.mark.asyncio
async def test_fetch_cdn_pdf_respects_content_length_cap() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"x" * 100,
            headers={"content-length": "100"},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(CdnPdfPermanentError, match="too large"):
            await fetch_cdn_pdf(
                "https://cdn.cse.lk/big.pdf",
                max_bytes=50,
                client=client,
            )


@pytest.mark.asyncio
async def test_fetch_cdn_pdf_respects_streamed_byte_cap() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # Invalid Content-Length skips the header check so the streamed
        # byte counter (not Content-Length) enforces the cap.
        return httpx.Response(
            200,
            content=b"y" * 200,
            headers={"content-length": "not-a-number"},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(CdnPdfPermanentError, match="too large"):
            await fetch_cdn_pdf(
                "https://cdn.cse.lk/big.pdf",
                max_bytes=50,
                client=client,
            )


@pytest.mark.asyncio
async def test_fetch_cdn_pdf_skips_empty_stream_chunks() -> None:
    body = b"%PDF-ok"

    class _Resp:
        status_code = 200
        headers: dict[str, str] = {}

        def raise_for_status(self) -> None:
            return None

        async def aiter_bytes(self):  # type: ignore[no-untyped-def]
            yield b""
            yield body

        async def __aenter__(self) -> _Resp:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

    client = MagicMock()
    client.stream = MagicMock(return_value=_Resp())
    out = await fetch_cdn_pdf(
        "https://cdn.cse.lk/empty-chunk.pdf",
        max_bytes=1024,
        client=client,
    )
    assert out == body


@pytest.mark.asyncio
async def test_fetch_cdn_pdf_http_error_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="cdn down")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        out = await fetch_cdn_pdf(
            "https://cdn.cse.lk/missing.pdf",
            max_bytes=1024,
            client=client,
        )
    assert out is None


@pytest.mark.asyncio
async def test_fetch_cdn_pdf_transport_error_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        out = await fetch_cdn_pdf(
            "https://cdn.cse.lk/x.pdf",
            max_bytes=1024,
            client=client,
        )
    assert out is None


@pytest.mark.asyncio
async def test_fetch_cdn_pdf_clamps_max_bytes_to_at_least_one() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"ab")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(CdnPdfPermanentError, match="too large"):
            await fetch_cdn_pdf(
                "https://cdn.cse.lk/tiny.pdf",
                max_bytes=0,
                client=client,
            )


@pytest.mark.asyncio
async def test_fetch_cdn_pdf_rejects_redirect() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"location": "https://evil.example/steal"},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(CdnPdfPermanentError, match="redirect"):
            await fetch_cdn_pdf(
                "https://cdn.cse.lk/uploadAnnounceFiles/x.pdf",
                max_bytes=1024,
                client=client,
            )


@pytest.mark.asyncio
async def test_fetch_cdn_pdf_rejects_non_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="missing")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        out = await fetch_cdn_pdf(
            "https://cdn.cse.lk/missing.pdf",
            max_bytes=1024,
            client=client,
        )
    assert out is None


@pytest.mark.asyncio
async def test_fetch_cdn_pdf_permanent_http_status() -> None:
    """403/410 must not soft-requeue forever — permanent fail."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(CdnPdfPermanentError, match="permanent HTTP 403"):
            await fetch_cdn_pdf(
                "https://cdn.cse.lk/forbidden.pdf",
                max_bytes=1024,
                client=client,
            )


def test_extract_pdf_text_caps_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("pypdf")
    from chime.briefs import extract as extract_mod

    class _Page:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class _Reader:
        def __init__(self, *_a: object, **_k: object) -> None:
            self.pages = [_Page(f"page-{i}") for i in range(60)]

    monkeypatch.setattr(extract_mod, "_MAX_PDF_PAGES", 3)
    with patch("pypdf.PdfReader", _Reader):
        text = extract_pdf_text(b"%PDF")
    assert text == "page-0" + chr(10) + "page-1" + chr(10) + "page-2"


def test_extract_pdf_text_skips_blank_pages() -> None:
    pytest.importorskip("pypdf")

    class _Page:
        def __init__(self, text: str | None) -> None:
            self._text = text

        def extract_text(self) -> str | None:
            return self._text

    class _Reader:
        def __init__(self, *_a: object, **_k: object) -> None:
            self.pages = [_Page(None), _Page("   "), _Page("Keep me")]

    with patch("pypdf.PdfReader", _Reader):
        assert extract_pdf_text(b"%PDF") == "Keep me"


@pytest.mark.asyncio
async def test_claim_pending_briefs_skips_pdf_fetch_without_url() -> None:
    storage = MagicMock()
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(
        return_value=[
            {
                "disclosure_id": 7,
                "symbol": "JKH.N0000",
                "title": "AGM Notice",
                "pdf_url": None,
            }
        ]
    )
    storage.mark_brief_ready = AsyncMock(return_value=True)
    storage.mark_brief_failed = AsyncMock(return_value=True)

    provider = AsyncMock()
    provider.summarize = AsyncMock(return_value="AGM set for August.")

    fetch = AsyncMock()
    with patch("chime.briefs.worker.fetch_cdn_pdf", fetch):
        n = await claim_pending_briefs(
            storage,
            settings=_enabled_settings(),
            provider=provider,
        )
    assert n == 1
    fetch.assert_not_awaited()
    called = provider.summarize.await_args.args[0]
    assert "<<<FILING>>>" in called
    assert "JKH.N0000: AGM Notice" in called


@pytest.mark.asyncio
async def test_claim_pending_briefs_fetches_pdf_when_url_set() -> None:
    pytest.importorskip("pypdf")
    pdf_bytes = _tiny_pdf_bytes("Board met Tuesday")
    storage = MagicMock()
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(
        return_value=[
            {
                "disclosure_id": 9,
                "symbol": "JKH.N0000",
                "title": "Board Meeting",
                "pdf_url": "https://cdn.cse.lk/uploadAnnounceFiles/x.pdf",
            }
        ]
    )
    storage.mark_brief_ready = AsyncMock(return_value=True)
    storage.mark_brief_failed = AsyncMock(return_value=True)

    provider = AsyncMock()
    provider.summarize = AsyncMock(return_value="Board met; no dividend.")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=pdf_bytes)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        n = await claim_pending_briefs(
            storage,
            settings=_enabled_settings(),
            provider=provider,
            http_client=client,
        )

    assert n == 1
    called = provider.summarize.await_args.args[0]
    expected = build_brief_prompt(
        symbol="JKH.N0000",
        title="Board Meeting",
        extracted_text="Board met Tuesday",
    )
    assert called == expected
    storage.mark_brief_ready.assert_awaited_once()
