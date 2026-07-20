"""Wave96: pin cov gaps from w93/w94 harden paths."""

from __future__ import annotations

from types import MappingProxyType

from koel.adapters.cse import allowed_cdn_pdf_url, allowed_filing_url
from koel.briefs.extract import _header_media_type, _header_value


def test_path_segment_decode_rejects_invalid_utf8_percent() -> None:
    assert allowed_cdn_pdf_url("https://cdn.cse.lk/uploadAnnounceFiles/%80.pdf") is None
    assert allowed_filing_url("https://www.cse.lk/announcements/%ff#1") is None


def test_path_segment_decode_rejects_excessive_nested_encoding() -> None:
    # Five nested %25 layers exceeds the decode cap → fail closed.
    nested = "%2525252525252e"  # peels toward "." but never settles in 5 rounds
    assert allowed_cdn_pdf_url(f"https://cdn.cse.lk/uploadAnnounceFiles/{nested}/x.pdf") is None


def test_header_value_matches_case_insensitive_keys() -> None:
    headers = MappingProxyType({True: "skip", "Content-TYPE": "application/pdf"})
    assert _header_value(headers, "content-type") == "application/pdf"


def test_header_media_type_rejects_non_string() -> None:
    assert _header_media_type(None) is None
    assert _header_media_type(True) == ""
    assert _header_media_type(["application/pdf"]) == ""
