"""Wave8: unit coverage for poller brief-drain / PDF-enrich fail-soft branches."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from chime.adapters.cse import LegacyAnnouncementRow
from chime.config import Settings
from chime.poller import PendingPdfEnrich, Poller


def _settings(**kwargs: object) -> Settings:
    base = dict(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
        pdf_enrich_sleep_seconds=0,
    )
    base.update(kwargs)
    return Settings(**base)  # type: ignore[arg-type]


def _poller(
    *,
    storage: AsyncMock | None = None,
    cse: AsyncMock | None = None,
    send: AsyncMock | None = None,
    **settings_kw: object,
) -> Poller:
    return Poller(
        _settings(**settings_kw),
        storage or AsyncMock(),
        cse or AsyncMock(),
        send or AsyncMock(return_value=True),
    )


@pytest.mark.asyncio
async def test_drain_briefs_safe_logs_when_processed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import chime.poller as poller_mod

    poller = _poller()
    monkeypatch.setattr(
        poller_mod, "claim_pending_briefs", AsyncMock(return_value=3)
    )
    with patch.object(poller_mod.log, "info") as info:
        await poller._drain_briefs_safe()
    info.assert_any_call("brief_drain_done", processed=3)


@pytest.mark.asyncio
async def test_drain_briefs_safe_fail_soft_on_worker_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import chime.poller as poller_mod

    poller = _poller()
    monkeypatch.setattr(
        poller_mod,
        "claim_pending_briefs",
        AsyncMock(side_effect=RuntimeError("worker boom")),
    )
    with patch.object(poller_mod.log, "warning") as warning:
        await poller._drain_briefs_safe()
    warning.assert_any_call("brief_drain_failed", error="worker boom")


@pytest.mark.asyncio
async def test_drain_briefs_safe_rethrows_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import chime.poller as poller_mod

    poller = _poller()

    async def boom(storage: object, *, notify: object) -> int:
        raise asyncio.CancelledError()

    monkeypatch.setattr(poller_mod, "claim_pending_briefs", boom)
    with pytest.raises(asyncio.CancelledError):
        await poller._drain_briefs_safe()


@pytest.mark.asyncio
async def test_enrich_disclosure_pdfs_safe_fail_soft_on_batch_error() -> None:
    import chime.poller as poller_mod

    poller = _poller()
    poller._enrich_disclosure_pdfs = AsyncMock(  # type: ignore[method-assign]
        side_effect=RuntimeError("batch boom")
    )
    items = [PendingPdfEnrich(disclosure_id=1, symbol="JKH.N0000", external_id="1")]
    with patch.object(poller_mod.log, "warning") as warning:
        await poller._enrich_disclosure_pdfs_safe(items)
    warning.assert_any_call("pdf_enrich_batch_failed", error="batch boom")


@pytest.mark.asyncio
async def test_enrich_disclosure_pdfs_safe_rethrows_cancelled() -> None:
    poller = _poller()
    poller._enrich_disclosure_pdfs = AsyncMock(  # type: ignore[method-assign]
        side_effect=asyncio.CancelledError()
    )
    with pytest.raises(asyncio.CancelledError):
        await poller._enrich_disclosure_pdfs_safe(
            [PendingPdfEnrich(disclosure_id=1, symbol="JKH.N0000", external_id="1")]
        )


@pytest.mark.asyncio
async def test_enrich_disclosure_pdfs_empty_items_is_noop() -> None:
    cse = AsyncMock()
    poller = _poller(cse=cse)
    await poller._enrich_disclosure_pdfs([])
    cse.fetch_legacy_announcements.assert_not_awaited()


@pytest.mark.asyncio
async def test_enrich_skips_when_legacy_returns_no_pdf_map() -> None:
    """Legacy rows with null filePath → empty pdf_map → continue."""
    storage = AsyncMock()
    storage.set_disclosure_pdf_url = AsyncMock(return_value=True)
    cse = AsyncMock()
    cse.fetch_legacy_announcements = AsyncMock(
        return_value=[
            LegacyAnnouncementRow(announcementId=25040, filePath=None),
        ]
    )
    poller = _poller(storage=storage, cse=cse)
    await poller._enrich_disclosure_pdfs(
        [
            PendingPdfEnrich(
                disclosure_id=55,
                symbol="JKH.N0000",
                external_id="25040",
            )
        ]
    )
    storage.set_disclosure_pdf_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_enrich_skips_when_external_id_missing_from_pdf_map() -> None:
    """Legacy returns PDFs for other ids; watched external_id has no match."""
    storage = AsyncMock()
    storage.set_disclosure_pdf_url = AsyncMock(return_value=True)
    cse = AsyncMock()
    cse.fetch_legacy_announcements = AsyncMock(
        return_value=[
            LegacyAnnouncementRow(
                announcementId=99999,
                filePath="uploadAnnounceFiles/other.pdf",
            )
        ]
    )
    poller = _poller(storage=storage, cse=cse)
    await poller._enrich_disclosure_pdfs(
        [
            PendingPdfEnrich(
                disclosure_id=55,
                symbol="JKH.N0000",
                external_id="25040",
            )
        ]
    )
    storage.set_disclosure_pdf_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_enrich_fail_soft_when_set_pdf_url_raises() -> None:
    import chime.poller as poller_mod

    storage = AsyncMock()
    storage.set_disclosure_pdf_url = AsyncMock(side_effect=RuntimeError("db down"))
    cse = AsyncMock()
    cse.fetch_legacy_announcements = AsyncMock(
        return_value=[
            LegacyAnnouncementRow(
                announcementId=25040,
                filePath="uploadAnnounceFiles/ok.pdf",
            )
        ]
    )
    poller = _poller(storage=storage, cse=cse)
    with patch.object(poller_mod.log, "warning") as warning:
        await poller._enrich_disclosure_pdfs(
            [
                PendingPdfEnrich(
                    disclosure_id=55,
                    symbol="JKH.N0000",
                    external_id="25040",
                )
            ]
        )
    warning.assert_any_call(
        "pdf_url_set_failed",
        disclosure_id=55,
        symbol="JKH.N0000",
        error="db down",
    )


@pytest.mark.asyncio
async def test_schedule_pdf_enrichment_empty_is_noop() -> None:
    poller = _poller()
    poller._schedule_pdf_enrichment([])
    assert not poller._pdf_enrich_tasks
    assert poller.pdf_enrich_health_snapshot()["batches_started"] == 0


@pytest.mark.asyncio
async def test_pdf_enrich_health_snapshot_tracks_schedule() -> None:
    poller = _poller()
    poller._enrich_disclosure_pdfs_safe = AsyncMock()  # type: ignore[method-assign]
    items = [PendingPdfEnrich(disclosure_id=1, symbol="AAA.N0000", external_id="1")]
    poller._schedule_pdf_enrichment(items)
    snap = poller.pdf_enrich_health_snapshot()
    assert snap["last_batch_size"] == 1
    assert snap["batches_started"] == 1
    assert snap["in_flight_tasks"] == 1
    await poller.await_pdf_enrichment()
    assert poller.pdf_enrich_health_snapshot()["in_flight_tasks"] == 0
