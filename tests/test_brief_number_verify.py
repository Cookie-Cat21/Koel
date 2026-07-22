"""W1: AI brief number-verification gate."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from koel.briefs import BriefSettings
from koel.briefs.verify import (
    brief_numbers_verified,
    extract_numbers,
    normalize_number_token,
)
from koel.briefs.worker import claim_pending_briefs


def _enabled_settings(**kwargs: Any) -> BriefSettings:
    base = dict(
        enabled=True,
        api_key="test-key",
        provider="gemini",
        model="gemini-2.0-flash",
        max_briefs_per_day=50,
        max_input_chars=12_000,
        sleep_seconds=0,
        skipped_promote_hours=0,
    )
    base.update(kwargs)
    return BriefSettings(**base)  # type: ignore[arg-type]


def test_extract_numbers_integers_decimals_percent() -> None:
    assert extract_numbers("Revenue rose 12.5% to 1,250.50") == [
        "12.5%",
        "1,250.50",
    ]
    assert extract_numbers("No figures here.") == []
    assert extract_numbers("") == []
    assert extract_numbers(None) == []  # type: ignore[arg-type]


def test_normalize_number_token_strips_commas_and_percent() -> None:
    assert normalize_number_token("1,250.50") == "1250.50"
    assert normalize_number_token("12.5%") == "12.5"
    assert normalize_number_token("5%") == "5"
    assert normalize_number_token(None) == ""  # type: ignore[arg-type]


def test_brief_numbers_verified_matching() -> None:
    source = "Net profit was Rs. 1,250.50, up 12.5% year on year."
    summary = "Net profit rose to 1250.50, a 12.5% increase."
    assert brief_numbers_verified(summary, source) is True


def test_brief_numbers_verified_hallucinated_number() -> None:
    source = "Dividend of Rs. 2.50 per share declared."
    summary = "Company declared a dividend of 5.00 per share."
    assert brief_numbers_verified(summary, source) is False


def test_brief_numbers_verified_percent_forms() -> None:
    # Summary has %; source has bare number — accept.
    assert brief_numbers_verified("Margins improved by 5%.", "Margins were 5 last year.") is True
    # Matching percent in both.
    assert brief_numbers_verified("EPS grew 8.2%.", "EPS growth of 8.2% reported.") is True
    # Hallucinated percent.
    assert brief_numbers_verified("EPS grew 9%.", "EPS growth of 8.2% reported.") is False


def test_brief_numbers_verified_commas_in_source() -> None:
    source = "Turnover reached 1,500,000 this quarter."
    summary = "Turnover reached 1500000 this quarter."
    assert brief_numbers_verified(summary, source) is True
    # Malformed comma grouping: extract splits tokens, comma-strip still matches.
    assert brief_numbers_verified("1250 units", "approx 1,,250 units") is True


def test_brief_numbers_verified_empty_and_non_str() -> None:
    assert brief_numbers_verified("", "source with 1 number") is False
    assert brief_numbers_verified(None, "source") is False  # type: ignore[arg-type]
    assert brief_numbers_verified("has 1", None) is False  # type: ignore[arg-type]
    assert brief_numbers_verified(12, "12") is False  # type: ignore[arg-type]


def test_brief_numbers_verified_summary_with_no_numbers() -> None:
    assert brief_numbers_verified("Board met; no dividend.", "AGM Notice") is True
    assert brief_numbers_verified("Title only ok.", "") is True


@pytest.mark.asyncio
async def test_claim_pending_briefs_number_verify_fails_marks_failed() -> None:
    """Hallucinated brief → mark_brief_failed; mark_brief_ready never called."""
    storage = MagicMock()
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(
        return_value=[
            {
                "disclosure_id": 7,
                "symbol": "JKH.N0000",
                "title": "Dividend of Rs. 2.50 declared",
                "pdf_url": None,
            }
        ]
    )
    storage.mark_brief_ready = AsyncMock(return_value=True)
    storage.mark_brief_failed = AsyncMock(return_value=True)
    storage.list_ready_briefs_for_followup_sweep = AsyncMock(return_value=[])

    provider = AsyncMock()
    # 99.9 is not in the title-only source text.
    provider.summarize = AsyncMock(
        return_value="Dividend hiked to 99.9 per share."
    )

    notify = AsyncMock(return_value=True)

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(),
        provider=provider,
        notify=notify,
    )
    assert n == 1
    provider.summarize.assert_awaited_once()
    storage.mark_brief_failed.assert_awaited_once()
    assert (
        storage.mark_brief_failed.await_args.kwargs["error"]
        == "number_verification_failed"
    )
    assert storage.mark_brief_failed.await_args.kwargs["model"] == "gemini-2.0-flash"
    storage.mark_brief_ready.assert_not_awaited()
    notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_pending_briefs_number_verify_passes_marks_ready() -> None:
    storage = MagicMock()
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(
        return_value=[
            {
                "disclosure_id": 8,
                "symbol": "COMB.N0000",
                "title": "Interim dividend of Rs. 2.50 per share",
                "pdf_url": None,
            }
        ]
    )
    storage.mark_brief_ready = AsyncMock(return_value=True)
    storage.mark_brief_failed = AsyncMock(return_value=True)
    storage.list_ready_briefs_for_followup_sweep = AsyncMock(return_value=[])

    provider = AsyncMock()
    provider.summarize = AsyncMock(
        return_value="Interim dividend of 2.50 per share declared."
    )

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(),
        provider=provider,
    )
    assert n == 1
    storage.mark_brief_ready.assert_awaited_once()
    assert (
        storage.mark_brief_ready.await_args.kwargs["brief"]
        == "Interim dividend of 2.50 per share declared."
    )
    storage.mark_brief_failed.assert_not_awaited()
