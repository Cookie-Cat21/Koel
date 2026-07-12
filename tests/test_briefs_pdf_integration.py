"""Briefs enqueue + legacy PDF enrich interaction (unit).

Phase 2 foundation: a new disclosure always lands a ``disclosure_briefs``
ledger row (``skipped`` while AI briefs are off). PDF URL enrichment is a
separate fail-soft step that fills ``disclosures.pdf_url`` without touching
the briefs ledger or re-enqueueing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from chime.adapters.cse import CDN_BASE, LegacyAnnouncementRow, legacy_pdf_urls_by_id
from chime.briefs import BriefStatus
from chime.config import Settings
from chime.domain import AlertType, Disclosure, PreviousPriceState, PriceSnapshot
from chime.poller import PendingPdfEnrich, Poller
from tests.conftest import make_disclosure, make_rule
from tests.test_legacy_pdf_enrich import _legacy_fixture
from tests.test_storage_unit import _Conn, _store


def _disc(**kwargs: object) -> Disclosure:
    base = dict(
        external_id="25040",
        symbol="JKH.N0000",
        title="ESOS",
        url="https://www.cse.lk/announcements#25040",
        published_at=datetime(2026, 7, 11, 8, 0, 0, tzinfo=UTC),
        seen_at=datetime(2026, 7, 11, 8, 0, 0, tzinfo=UTC),
        company_name="John Keells",
        pdf_url=None,
    )
    base.update(kwargs)
    return Disclosure(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_new_disclosure_enqueues_skipped_then_pdf_enrich_sets_url() -> None:
    """Insert path: briefs ledger gets skipped; enrich later fills pdf_url only."""
    pdf = f"{CDN_BASE}/uploadAnnounceFiles/5051552647765_508.pdf"
    # upsert_stock + insert disclosure (inserted) + briefs INSERT + pdf UPDATE
    conn = _Conn(
        [
            None,
            {"id": 55, "pdf_url": None, "inserted": True},
            None,
            {"id": 55},
        ]
    )
    store = _store(conn)

    with patch("chime.briefs.briefs_enabled", return_value=False):
        stored = await store.upsert_disclosure(_disc())

    assert stored.id == 55
    assert stored.pdf_url is None
    brief_sql = [s for s in conn.sql if "disclosure_briefs" in s]
    assert len(brief_sql) == 1
    assert "ON CONFLICT" in brief_sql[0]
    assert conn.params[2] == (55, BriefStatus.SKIPPED.value)

    assert await store.set_disclosure_pdf_url(55, pdf) is True
    assert "UPDATE disclosures" in conn.sql[-1]
    assert "NULLIF(btrim(pdf_url), '') IS NULL" in conn.sql[-1]
    assert conn.params[-1] == (pdf, 55)
    # Enrich must not touch disclosure_briefs again
    assert sum(1 for s in conn.sql if "disclosure_briefs" in s) == 1


@pytest.mark.asyncio
async def test_pdf_enrich_preserves_skipped_brief_and_existing_row_idempotent() -> None:
    """Re-upsert after enrich: keep pdf_url, never enqueue a second brief."""
    pdf = f"{CDN_BASE}/uploadAnnounceFiles/5051552647765_508.pdf"
    conn = _Conn(
        [
            None,
            {"id": 55, "pdf_url": None, "inserted": True},
            None,  # briefs skipped insert
            {"id": 55},  # set pdf_url
            None,  # upsert_stock on re-upsert
            {"id": 55, "pdf_url": pdf, "inserted": False},
        ]
    )
    store = _store(conn)

    with patch("chime.briefs.briefs_enabled", return_value=False):
        first = await store.upsert_disclosure(_disc())
    assert first.pdf_url is None
    assert await store.set_disclosure_pdf_url(55, pdf) is True

    with patch("chime.briefs.briefs_enabled", return_value=False):
        again = await store.upsert_disclosure(_disc(title="ESOS (updated)"))

    assert again.id == 55
    assert again.pdf_url == pdf
    assert sum(1 for s in conn.sql if "disclosure_briefs" in s) == 1
    assert sum(1 for s in conn.sql if "UPDATE disclosures" in s and "pdf_url" in s) == 1


@pytest.mark.asyncio
async def test_poller_enrich_sets_pdf_url_without_brief_reenqueue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Poller path: new disclosure (no pdf_url) → enrich sets CDN url; no brief API."""
    monkeypatch.setattr("chime.poller.asyncio.sleep", AsyncMock())

    published = datetime(2026, 7, 11, 8, 0, 0, tzinfo=UTC)
    disc_rule = make_rule(
        id=9,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=published.replace(hour=6),
    )
    # Simulate upsert already having enqueued skipped brief (storage side).
    stored = make_disclosure(
        external_id="25040",
        symbol="JKH.N0000",
        title="ESOS",
        published_at=published,
    ).model_copy(update={"id": 55, "pdf_url": None, "just_inserted": True})

    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000"])
    storage.active_rules_for_symbols = AsyncMock(return_value=[disc_rule])
    storage.persist_market_snapshots = AsyncMock(
        side_effect=lambda snaps: [
            s.model_copy(update={"id": i}) for i, s in enumerate(snaps, start=1)
        ]
    )
    storage.get_previous_state = AsyncMock(return_value=PreviousPriceState(price=None))
    storage.upsert_disclosure = AsyncMock(return_value=stored)
    storage.claim_alert = AsyncMock(return_value=9100)
    storage.mark_alert_sent = AsyncMock()
    storage.claim_unsent_batch = AsyncMock(return_value=[])
    storage.set_disclosure_pdf_url = AsyncMock(return_value=True)
    storage.enqueue_disclosure_brief = AsyncMock(return_value=True)

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(
        return_value=[PriceSnapshot(symbol="JKH.N0000", price=100.0, ts=datetime.now(UTC))]
    )
    cse.fetch_announcements_for_symbol = AsyncMock(
        return_value=[
            make_disclosure(
                external_id="25040",
                symbol="JKH.N0000",
                title="ESOS",
                published_at=published,
            )
        ]
    )
    legacy_rows = [
        LegacyAnnouncementRow.model_validate(item) for item in _legacy_fixture()["infoAnnouncement"]
    ]
    cse.fetch_legacy_announcements = AsyncMock(return_value=legacy_rows)

    settings = Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
        pdf_enrich_sleep_seconds=0,
    )
    poller = Poller(settings, storage, cse, AsyncMock(return_value=True))
    events = await poller.run_once(force=True)
    await poller.await_pdf_enrichment()

    assert len(events) == 1
    expected_pdf = legacy_pdf_urls_by_id(legacy_rows)["25040"]
    storage.set_disclosure_pdf_url.assert_awaited_once_with(55, expected_pdf)
    # PDF enrich path must not call the briefs enqueuer (upsert owns that).
    storage.enqueue_disclosure_brief.assert_not_awaited()


@pytest.mark.asyncio
async def test_enrich_disclosure_pdfs_sets_url_for_pending_items() -> None:
    """Direct enrich helper: maps legacy filePath → set_disclosure_pdf_url."""
    pdf = f"{CDN_BASE}/uploadAnnounceFiles/5051552647765_508.pdf"
    storage = AsyncMock()
    storage.set_disclosure_pdf_url = AsyncMock(return_value=True)
    storage.enqueue_disclosure_brief = AsyncMock()

    cse = AsyncMock()
    legacy_rows = [
        LegacyAnnouncementRow.model_validate(item) for item in _legacy_fixture()["infoAnnouncement"]
    ]
    cse.fetch_legacy_announcements = AsyncMock(return_value=legacy_rows)

    settings = Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
        pdf_enrich_sleep_seconds=0,
    )
    poller = Poller(settings, storage, cse, AsyncMock(return_value=True))
    await poller._enrich_disclosure_pdfs(
        [
            PendingPdfEnrich(
                disclosure_id=55,
                symbol="JKH.N0000",
                external_id="25040",
            )
        ]
    )

    storage.set_disclosure_pdf_url.assert_awaited_once_with(55, pdf)
    storage.enqueue_disclosure_brief.assert_not_awaited()
