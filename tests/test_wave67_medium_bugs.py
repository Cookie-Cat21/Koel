"""Wave67: medium+ bugs — brief provider factory + bulk symbols + PDF extract.

1. ``make_brief_provider`` must isinstance-guard ``BriefSettings.provider``
   before ``.strip`` / ``.lower`` (hostile dataclass mocks used to throw).
2. ``_fetch_disclosures_bulk`` must isinstance-guard watchlist symbols and
   stock-name pairs before ``.strip``.
3. PDF ``page.extract_text()`` pieces must isinstance-guard before ``.strip``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chime.briefs import BriefSettings
from chime.briefs.provider import GeminiBriefProvider, make_brief_provider

ROOT = Path(__file__).resolve().parents[1]


def test_make_brief_provider_rejects_non_string_provider() -> None:
    cfg = object.__new__(BriefSettings)
    for key, value in {
        "enabled": True,
        "provider": 123,
        "api_key": "k",
        "model": "gemini-2.0-flash",
        "max_briefs_per_day": 1,
        "max_input_chars": 100,
        "pdf_max_bytes": 1000,
        "http_timeout_seconds": 1.0,
        "sleep_seconds": 0.0,
        "pdf_grace_seconds": 0,
        "cdn_backoff_seconds": 0,
        "skipped_promote_hours": 0,
    }.items():
        object.__setattr__(cfg, key, value)
    provider = make_brief_provider(cfg)
    assert isinstance(provider, GeminiBriefProvider)

    src = (ROOT / "chime" / "briefs" / "provider.py").read_text(encoding="utf-8")
    chunk = src.split("def make_brief_provider")[1]
    assert "isinstance(cfg.provider, str)" in chunk


def test_fetch_disclosures_bulk_symbol_isinstance_guards() -> None:
    src = (ROOT / "chime" / "poller.py").read_text(encoding="utf-8")
    chunk = src.split("async def _fetch_disclosures_bulk")[1].split("async def ")[0]
    assert "isinstance(s, str)" in chunk
    assert "isinstance(symbol, str)" in chunk
    assert "isinstance(name, str)" in chunk
    assert "{s.strip().upper() for s in disclosure_symbols}" not in chunk


def test_pdf_extract_piece_isinstance_guard() -> None:
    src = (ROOT / "chime" / "briefs" / "extract.py").read_text(encoding="utf-8")
    # First extract_text call site in extract_pdf_text
    chunk = src.split("piece = page.extract_text()", 1)[1].split("remaining =", 1)[0]
    assert "isinstance(piece, str)" in chunk
    assert "if piece and piece.strip():" not in chunk


@pytest.mark.asyncio
async def test_fetch_disclosures_bulk_skips_non_string_symbols() -> None:
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from chime.poller import Poller

    poller = object.__new__(Poller)
    poller.cse = SimpleNamespace(
        fetch_approved_announcements=AsyncMock(return_value=[]),
    )
    poller.storage = SimpleNamespace(
        list_stock_names=AsyncMock(
            return_value=[
                (123, "Acme"),
                ("JKH.N0000", None),
                ("JKH.N0000", "John Keells"),
            ]
        ),
    )
    fetched, covered, ok = await poller._fetch_disclosures_bulk(
        [123, "JKH.N0000", None]  # type: ignore[list-item]
    )
    assert ok is True
    assert "JKH.N0000" in covered
    assert 123 not in covered
    assert set(fetched).issubset({"JKH.N0000"})
