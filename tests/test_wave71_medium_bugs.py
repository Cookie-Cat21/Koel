"""Wave71: medium+ bugs — reject str() soft-accept on brief follow-up paths.

1. ``format_brief_followup`` must isinstance-guard ``url`` (no ``str(url)``
   soft-accept before allowlist).
2. Brief worker title/symbol/external_id/url paths must isinstance-guard
   (``_title_only_input_text`` / ``_input_text_for_row`` /
   ``_notify_brief_followups``) — no ``str()`` soft-accept of hostile PG
   shapes mid drain / follow-up.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from koel.adapters.cse import CDN_BASE
from koel.briefs.worker import _notify_brief_followups, _title_only_input_text
from koel.domain import format_brief_followup

ROOT = Path(__file__).resolve().parents[1]


def test_format_brief_followup_rejects_non_string_url() -> None:
    follow = format_brief_followup(
        symbol="JKH.N0000",
        brief="Margins steady.",
        url=123,  # type: ignore[arg-type]
    )
    assert "Margins steady." in follow
    assert "cdn.cse.lk" not in follow
    assert "123" not in follow

    ok_url = f"{CDN_BASE}/uploadAnnounceFiles/x.pdf"
    ok = format_brief_followup(symbol="JKH.N0000", brief="Ready.", url=ok_url)
    assert ok_url in ok

    src = (ROOT / "koel" / "domain.py").read_text(encoding="utf-8")
    bf = src.split("def format_brief_followup")[1].split("def as_dict")[0]
    assert "isinstance(url, str)" in bf
    assert "if isinstance(url, str) and url.strip():" in bf
    assert "if url and str(url).strip():" not in bf


def test_title_only_input_rejects_non_string_fields() -> None:
    assert _title_only_input_text({"symbol": 123, "title": "Solo"}) == "Solo"
    assert _title_only_input_text({"symbol": "JKH.N0000", "title": 9}) == "JKH.N0000"
    assert _title_only_input_text({"symbol": None, "title": None}) == ""
    assert (
        _title_only_input_text({"symbol": "JKH.N0000", "title": "AGM"})
        == "JKH.N0000: AGM"
    )

    src = (ROOT / "koel" / "briefs" / "worker.py").read_text(encoding="utf-8")
    title = src.split("def _title_only_input_text")[1].split(
        "async def _input_text_for_row"
    )[0]
    assert "isinstance(raw_sym, str)" in title
    assert 'str(row.get("symbol")' not in title
    inp = src.split("async def _input_text_for_row")[1].split(
        "async def _notify_brief_followups"
    )[0]
    assert "isinstance(raw_sym, str)" in inp
    assert 'str(row.get("symbol")' not in inp


@pytest.mark.asyncio
async def test_notify_brief_followups_rejects_non_string_row_fields() -> None:
    storage = MagicMock()
    storage.claim_brief_followups = AsyncMock(return_value=[])
    await _notify_brief_followups(
        storage,
        notify=AsyncMock(),
        row={
            "disclosure_id": 1,
            "symbol": 123,
            "external_id": "9",
            "title": True,
            "url": {"x": 1},
        },
        brief="Ready",
    )
    storage.claim_brief_followups.assert_not_awaited()

    await _notify_brief_followups(
        storage,
        notify=AsyncMock(),
        row={
            "disclosure_id": 1,
            "symbol": "JKH.N0000",
            "external_id": 9,
            "title": "AGM",
            "url": f"{CDN_BASE}/uploadAnnounceFiles/x.pdf",
        },
        brief="Ready",
    )
    storage.claim_brief_followups.assert_not_awaited()

    src = (ROOT / "koel" / "briefs" / "worker.py").read_text(encoding="utf-8")
    chunk = src.split("async def _notify_brief_followups")[1].split(
        "async def _promote_skipped_if_needed"
    )[0]
    assert "isinstance(raw_sym, str)" in chunk
    assert "isinstance(raw_ext, str)" in chunk
    assert "isinstance(raw_title, str)" in chunk
    assert "isinstance(raw_url, str)" in chunk
    assert 'str(row.get("symbol")' not in chunk
    assert 'str(row.get("title")' not in chunk
