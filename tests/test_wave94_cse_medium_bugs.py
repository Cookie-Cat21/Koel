"""Wave94: CSE filing URL guards must reject encoded path traversal.

Literal ``.`` / ``..`` segments were rejected, but percent-encoded dot segments
and encoded slashes could still pass through CDN/filing URL normalization. Those
URLs are later stored or echoed to Telegram as allowlisted links.
"""

from __future__ import annotations

from koel.adapters.cse import (
    CDN_BASE,
    allowed_cdn_pdf_url,
    allowed_filing_url,
    resolve_pdf_url,
)


def test_filing_url_helpers_reject_percent_encoded_traversal_segments() -> None:
    assert allowed_cdn_pdf_url(
        "https://cdn.cse.lk/uploadAnnounceFiles/%2e%2e/secret.pdf"
    ) is None
    assert allowed_cdn_pdf_url(
        "https://cdn.cse.lk/uploadAnnounceFiles/%252e%252e/secret.pdf"
    ) is None
    assert allowed_filing_url(
        "https://www.cse.lk/announcements/%2E%2E/login#25040"
    ) is None
    assert resolve_pdf_url("uploadAnnounceFiles/%2e%2e/secret.pdf") is None


def test_filing_url_helpers_reject_encoded_separators_and_bad_escapes() -> None:
    assert allowed_cdn_pdf_url(
        "https://cdn.cse.lk/uploadAnnounceFiles/%2fsecret.pdf"
    ) is None
    assert allowed_cdn_pdf_url(
        "https://cdn.cse.lk/uploadAnnounceFiles/%5csecret.pdf"
    ) is None
    assert allowed_filing_url("https://www.cse.lk/announcements/%00x") is None
    assert resolve_pdf_url("uploadAnnounceFiles/%zz.pdf") is None


def test_filing_url_helpers_keep_benign_encoded_path_segments() -> None:
    cdn = "https://cdn.cse.lk/uploadAnnounceFiles/annual%20report.pdf"
    ann = "https://www.cse.lk/announcements/annual%20report#25040"

    assert allowed_cdn_pdf_url(cdn) == cdn
    assert allowed_filing_url(ann) == ann
    assert resolve_pdf_url("uploadAnnounceFiles/annual%20report.pdf") == (
        f"{CDN_BASE}/uploadAnnounceFiles/annual%20report.pdf"
    )
