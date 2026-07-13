"""PDF text extraction for filing briefs (optional ``pypdf``).

``extract_pdf_text`` is soft-fail: missing ``pypdf`` or corrupt bytes yield
``""`` and a log line — briefs still fall back to title-only input.
CDN fetch is size-capped via ``PDF_MAX_BYTES`` / ``BriefSettings.pdf_max_bytes``.
"""

from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO
from typing import Any

import httpx
import structlog

from chime.adapters.cse import allowed_cdn_pdf_url
from chime.domain import resolve_positive_int_cap

log = structlog.get_logger("chime.briefs.extract")

# Soft caps so a hostile/huge CDN PDF cannot pin the brief worker on CPU/RAM.
_MAX_PDF_PAGES = 40
_MAX_EXTRACT_CHARS = 50_000
# Absolute ceiling for PDF fetch byte caps (env / caller misconfig).
_PDF_MAX_BYTES_ABS = 20_971_520  # 20 MiB


# Client errors that will not heal on retry — fail the brief permanently.
_CDN_PERMANENT_STATUS = frozenset({401, 403, 410, 451})
_PDF_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "application/x-pdf",
        "application/octet-stream",
    }
)


class CdnPdfPermanentError(RuntimeError):
    """Non-retryable CDN PDF failure.

    Covers oversized/non-PDF bodies, redirects, host allowlist rejects, and
    permanent HTTP statuses (401/403/410/451). Distinct from soft ``None`` returns
    (transport / 5xx / 404) so the brief worker can mark ``failed`` instead of
    requeue-hammering the CDN forever.
    """


def _response_headers(response: Any) -> Mapping[str, Any]:
    raw = getattr(response, "headers", {})
    return raw if isinstance(raw, Mapping) else {}


def _header_value(headers: Mapping[str, Any], name: str) -> Any:
    value = headers.get(name)
    if value is not None:
        return value
    lower_name = name.lower()
    for key, candidate in headers.items():
        if isinstance(key, str) and key.lower() == lower_name:
            return candidate
    return None


def _header_media_type(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return ""
    return value.split(";", 1)[0].strip().lower()


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
            # Fail closed — non-string extract_text used to throw on .strip mid PDF parse.
            if isinstance(piece, str) and piece.strip():
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

    Returns ``None`` for transient misses (transport error, 404/5xx) so the
    worker can requeue with backoff. Raises ``CdnPdfPermanentError`` for
    oversized/non-PDF bodies, redirects (never followed — SSRF / poison loops),
    host allowlist rejects, and permanent HTTP statuses.
    """
    allowed = allowed_cdn_pdf_url(pdf_url)
    if allowed is None:
        log.warning("pdf_fetch_rejected_host", pdf_url=pdf_url)
        raise CdnPdfPermanentError(
            f"CDN PDF URL rejected (not allowlisted): {pdf_url!r}"
        )

    # Fail closed — int(NaN)/None/inf used to raise mid CDN fetch;
    # max_bytes=0 still clamps to 1 (oversized body → permanent error).
    cap = resolve_positive_int_cap(
        max_bytes, default=1, absolute_max=_PDF_MAX_BYTES_ABS
    )
    try:
        # follow_redirects=False: open redirects on the CDN must not SSRF.
        async with client.stream(
            "GET",
            allowed,
            follow_redirects=False,
        ) as response:
            raw_status = getattr(response, "status_code", 0)
            # Fail closed — bool soft-accepts via int(True)==1 mid CDN classify.
            status = (
                raw_status
                if isinstance(raw_status, int) and not isinstance(raw_status, bool)
                else 0
            )
            headers = _response_headers(response)
            # Fail closed — bool("yes") used to soft-accept redirects.
            if status in {301, 302, 303, 307, 308} or getattr(
                response, "is_redirect", False
            ) is True:
                log.warning(
                    "pdf_fetch_redirect_rejected",
                    pdf_url=allowed,
                    status_code=status,
                    location=_header_value(headers, "location"),
                )
                raise CdnPdfPermanentError(
                    f"CDN PDF redirect rejected for {allowed!r} (status={status})"
                )
            if status in _CDN_PERMANENT_STATUS:
                log.warning(
                    "pdf_fetch_permanent_status",
                    pdf_url=allowed,
                    status_code=status,
                )
                raise CdnPdfPermanentError(
                    f"CDN PDF permanent HTTP {status} for {allowed!r}"
                )
            if status != 200:
                log.warning(
                    "pdf_fetch_bad_status",
                    pdf_url=allowed,
                    status_code=status,
                )
                return None
            content_type = _header_media_type(_header_value(headers, "content-type"))
            if content_type is not None and content_type not in _PDF_CONTENT_TYPES:
                log.warning(
                    "pdf_fetch_bad_content_type",
                    pdf_url=allowed,
                    content_type=content_type,
                )
                raise CdnPdfPermanentError(
                    f"CDN PDF content-type rejected for {allowed!r}: {content_type!r}"
                )
            content_length = _header_value(headers, "content-length")
            if content_length is not None:
                # Fail closed — bool soft-accepts via int(True)==1; non-digit
                # headers must not coerce into a fake length gate.
                length: int | None = None
                if isinstance(content_length, bool):
                    length = None
                elif isinstance(content_length, int):
                    length = content_length
                elif isinstance(content_length, str):
                    try:
                        length = int(content_length)
                    except ValueError:
                        length = None
                if length is not None and length > cap:
                    log.warning(
                        "pdf_fetch_too_large",
                        pdf_url=allowed,
                        content_length=length,
                        max_bytes=cap,
                    )
                    raise CdnPdfPermanentError(
                        f"CDN PDF too large for {allowed!r} "
                        f"(content-length={length} > {cap})"
                    )

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
                    raise CdnPdfPermanentError(
                        f"CDN PDF too large for {allowed!r} "
                        f"(bytes_read={total} > {cap})"
                    )
                chunks.append(chunk)
            data = b"".join(chunks)
            if not data.lstrip().startswith(b"%PDF"):
                log.warning(
                    "pdf_fetch_bad_body_type",
                    pdf_url=allowed,
                    bytes_read=total,
                )
                raise CdnPdfPermanentError(f"CDN PDF body was not a PDF for {allowed!r}")
            return data
    except CdnPdfPermanentError:
        raise
    except Exception as exc:
        log.warning("pdf_fetch_failed", pdf_url=allowed, error=str(exc))
        return None
