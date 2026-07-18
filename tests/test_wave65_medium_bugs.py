"""Wave65: medium+ bugs — filing URL isinstance + notify symbol + mint secret.

1. ``allowed_cdn_pdf_url`` / ``allowed_filing_url`` / ``resolve_pdf_url`` must
   isinstance-guard non-strings (``.strip`` used to throw mid Telegram /
   enrich egress).
2. ``format_dead_letter_notify`` / ``format_brief_followup`` must isinstance-
   guard ``symbol`` (``re.sub`` used to throw on hostile / wrong-shape callers).
3. ``mintSessionToken`` must typeof-guard ``secret`` — non-string / empty
   secrets used to throw deep in HMAC instead of a clean mint reject.
"""

from __future__ import annotations

from pathlib import Path

from chime.adapters.cse import (
    allowed_cdn_pdf_url,
    allowed_filing_url,
    resolve_pdf_url,
)
from chime.domain import format_brief_followup, format_dead_letter_notify

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_filing_url_helpers_reject_non_strings() -> None:
    for bad in (123, True, 1.5, {"u": 1}, ["https://cdn.cse.lk/x.pdf"], b"x"):
        assert allowed_cdn_pdf_url(bad) is None  # type: ignore[arg-type]
        assert allowed_filing_url(bad) is None  # type: ignore[arg-type]
        assert resolve_pdf_url(bad) is None  # type: ignore[arg-type]
    ok_cdn = "https://cdn.cse.lk/ok.pdf"
    assert allowed_cdn_pdf_url(ok_cdn) == ok_cdn
    assert allowed_filing_url(ok_cdn) == ok_cdn
    assert resolve_pdf_url("uploadAnnounceFiles/ok.pdf") == (
        "https://cdn.cse.lk/uploadAnnounceFiles/ok.pdf"
    )
    ok_ann = "https://www.cse.lk/announcements#1"
    assert allowed_filing_url(ok_ann) == ok_ann

    src = (ROOT / "chime" / "adapters" / "cse.py").read_text(encoding="utf-8")
    assert src.count("if not isinstance(url, str):") >= 2
    assert "if not isinstance(file_path, str):" in src


def test_notify_formatters_reject_non_string_symbol() -> None:
    msg = format_dead_letter_notify(123, 5)  # type: ignore[arg-type]
    assert "after 5 tries" in msg
    assert "koel could not deliver" in msg

    follow = format_brief_followup(symbol=None, brief="Ready")  # type: ignore[arg-type]
    assert "Filing brief ready" in follow
    assert "Ready" in follow

    src = (ROOT / "chime" / "domain.py").read_text(encoding="utf-8")
    dl = src.split("def format_dead_letter_notify")[1].split(
        "def format_brief_followup"
    )[0]
    bf = src.split("def format_brief_followup")[1].split("def as_dict")[0]
    assert "isinstance(symbol, str)" in dl
    assert "isinstance(symbol, str)" in bf


def test_mint_session_token_secret_typeof_guard() -> None:
    source = (WEB / "src" / "lib" / "auth" / "session.ts").read_text(
        encoding="utf-8"
    )
    chunk = source.split("export function mintSessionToken")[1].split(
        "export function verifySessionToken"
    )[0]
    assert "secret: unknown" in chunk
    assert 'typeof secret !== "string"' in chunk
    assert "secret must be a non-empty string" in chunk
