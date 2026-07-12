"""PDF text extraction for filing briefs (optional ``pypdf``).

``extract_pdf_text`` is soft-fail: missing ``pypdf`` or corrupt bytes yield
``""`` and a log line — briefs still fall back to title-only input.
CDN fetch is size-capped via ``PDF_MAX_BYTES`` / ``BriefSettings.pdf_max_bytes``.
"""

from __future__ import annotations

from io import BytesIO

import httpx
import structlog

from chime.adapters.cse import allowed_cdn_pdf_url

log = structlog.get_logger("chime.briefs.extract")

# Soft caps so a hostile/huge CDN PDF cannot pin the brief worker on CPU/RAM.
_MAX_PDF_PAGES = 40
_MAX_EXTRACT_CHARS = 50_000


def extract_pdf_text(data: bytes) -> str:
    """Extract plain text from PDF bytes.

    Uses ``pypdf`` when installed (``pip install 'chime[briefs]'``). Without
    it, returns ``""`` and logs once per call so the worker can fall back.
    Caps pages (``_MAX_PDF_PAGES``) and total chars (``_MAX_EXTRACT_CHARS``).
    """
    if not data:
        return ""
    try:
        from pypdf import PdfReader
    except ImportError:
        log.warning(
            "pypdf_unavailable",
            hint="pip install 'chime[briefs]' for PDF text extraction",
        )
        return ""

    try:
        reader = PdfReader(BytesIO(data))
        chunks: list[str] = []
        total_chars = 0
        for index, page in enumerate(reader.pages):
            if index >= _MAX_PDF_PAGES:
                log.info(
                    "pdf_extract_page_cap",
                    pages=_MAX_PDF_PAGES,
                    total_pages=len(reader.pages),
                )
                break
            piece = page.extract_text()
            if piece and piece.strip():
                text = piece.strip()
                remaining = _MAX_EXTRACT_CHARS - total_chars
                if remaining <= 0:
                    break
                if len(text) > remaining:
                    chunks.append(text[:remaining])
                    total_chars += remaining
                    log.info(
                        "pdf_extract_char_cap",
                        max_chars=_MAX_EXTRACT_CHARS,
                    )
                    break
                chunks.append(text)
                total_chars += len(text)
        return "\n".join(chunks).strip()
    except Exception as exc:
        log.warning("pdf_extract_failed", error=str(exc))
        return ""


async def fetch_cdn_pdf(
    pdf_url: str,
    *,
    max_bytes: int,
    client: httpx.AsyncClient,
) -> bytes | None:
    """GET a CSE CDN PDF with host allowlist + byte cap.

    Returns ``None`` when the URL fails the CDN SSRF check, the response is
    oversized (Content-Length or streamed body), redirects away from the
    allowlisted host, or the request errors. Redirects are never followed.
    """
    allowed = allowed_cdn_pdf_url(pdf_url)
    if allowed is None:
        log.warning("pdf_fetch_rejected_host", pdf_url=pdf_url)
        return None

    cap = max(1, int(max_bytes))
    try:
        # follow_redirects=False: open redirects on the CDN must not SSRF.
        async with client.stream(
            "GET",
            allowed,
            follow_redirects=False,
        ) as response:
            status = int(getattr(response, "status_code", 0) or 0)
            headers = getattr(response, "headers", {}) or {}
            if status in {301, 302, 303, 307, 308} or bool(
                getattr(response, "is_redirect", False)
            ):
                log.warning(
                    "pdf_fetch_redirect_rejected",
                    pdf_url=allowed,
                    status_code=status,
                    location=headers.get("location"),
                )
                return None
            if status != 200:
                log.warning(
                    "pdf_fetch_bad_status",
                    pdf_url=allowed,
                    status_code=status,
                )
                return None
            content_length = response.headers.get("content-length")
            if content_length is not None:
                try:
                    if int(content_length) > cap:
                        log.warning(
                            "pdf_fetch_too_large",
                            pdf_url=allowed,
                            content_length=int(content_length),
                            max_bytes=cap,
                        )
                        return None
                except ValueError:
                    pass

            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                if not chunk:
                    continue
                total += len(chunk)
                if total > cap:
                    log.warning(
                        "pdf_fetch_too_large",
                        pdf_url=allowed,
                        bytes_read=total,
                        max_bytes=cap,
                    )
                    return None
                chunks.append(chunk)
            return b"".join(chunks)
    except Exception as exc:
        log.warning("pdf_fetch_failed", pdf_url=allowed, error=str(exc))
        return None
