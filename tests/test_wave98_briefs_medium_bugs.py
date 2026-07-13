"""Wave98 briefs worker medium bug pins."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from chime.briefs import BriefSettings
from chime.briefs.worker import claim_pending_briefs


def _enabled_settings(**kwargs: Any) -> BriefSettings:
    base = dict(
        enabled=True,
        api_key="test-key",
        provider="gemini",
        model="gemini-2.0-flash",
        max_briefs_per_day=50,
        max_input_chars=12_000,
        sleep_seconds=0,
    )
    base.update(kwargs)
    return BriefSettings(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_claim_pending_briefs_skips_poisoned_non_dict_row() -> None:
    """A malformed claimed row must not abort later valid leased brief rows."""
    storage = MagicMock()
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=0)
    storage.count_briefs_today = AsyncMock(return_value=0)
    storage.claim_pending_briefs = AsyncMock(
        return_value=[
            "not-a-row",
            {"disclosure_id": 98, "symbol": "JKH.N0000", "title": "AGM Notice"},
        ]
    )
    storage.mark_brief_ready = AsyncMock(return_value=True)
    storage.mark_brief_failed = AsyncMock(return_value=True)

    provider = AsyncMock()
    provider.summarize = AsyncMock(return_value="AGM scheduled.")

    n = await claim_pending_briefs(
        storage,
        settings=_enabled_settings(),
        provider=provider,
        http_client=AsyncMock(),
    )

    assert n == 1
    provider.summarize.assert_awaited_once()
    storage.mark_brief_ready.assert_awaited_once()
    assert storage.mark_brief_ready.await_args.args[0] == 98
    storage.mark_brief_failed.assert_not_awaited()
