"""Legacy POST /announcements → CDN pdf_url enrichment (Phase 2 foundation)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from chime.adapters.cse import (
    CDN_BASE,
    CSEClient,
    LegacyAnnouncementRow,
    legacy_pdf_urls_by_id,
    resolve_pdf_url,
)
from chime.config import Settings
from chime.domain import AlertType, Disclosure, PreviousPriceState, PriceSnapshot
from chime.poller import Poller
from tests.conftest import make_disclosure, make_rule
from tests.test_storage_unit import _Conn, _store

_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "sample_responses"
    / "announcements_legacy.json"
)


def _legacy_fixture() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_resolve_pdf_url_from_fixture_file_paths() -> None:
    rows = _legacy_fixture()["infoAnnouncement"]
    assert resolve_pdf_url(rows[0]["filePath"]) == (
        f"{CDN_BASE}/uploadAnnounceFiles/5051552647765_508.pdf"
    )
    assert resolve_pdf_url(rows[1]["filePath"]) is None  # null filePath
    assert resolve_pdf_url(rows[2]["filePath"]) == (
        f"{CDN_BASE}/uploadAnnounceFiles/6781548416472_508.pdf"
    )


def test_resolve_pdf_url_edge_cases() -> None:
    assert resolve_pdf_url(None) is None
    assert resolve_pdf_url("") is None
    assert resolve_pdf_url("   ") is None
    assert resolve_pdf_url("/uploadAnnounceFiles/x.pdf") == (
        f"{CDN_BASE}/uploadAnnounceFiles/x.pdf"
    )
    absolute = "https://cdn.cse.lk/uploadAnnounceFiles/already.pdf"
    assert resolve_pdf_url(absolute) == absolute


def test_legacy_pdf_urls_by_id_from_fixture() -> None:
    raw = _legacy_fixture()
    rows = [LegacyAnnouncementRow.model_validate(item) for item in raw["infoAnnouncement"]]
    mapping = legacy_pdf_urls_by_id(rows)
    assert mapping == {
        "25040": f"{CDN_BASE}/uploadAnnounceFiles/5051552647765_508.pdf",
        "24562": f"{CDN_BASE}/uploadAnnounceFiles/6781548416472_508.pdf",
    }
    assert "24588" not in mapping  # null filePath


@pytest.mark.asyncio
async def test_fetch_legacy_announcements_parses_fixture() -> None:
    client = CSEClient(client=AsyncMock())
    client._request = AsyncMock(return_value=_legacy_fixture())  # type: ignore[method-assign]

    rows = await client.fetch_legacy_announcements("jkh.n0000")

    client._request.assert_awaited_once()
    call_kwargs = client._request.await_args
    assert call_kwargs.args[0] == "POST"
    assert call_kwargs.args[1] == "/announcements"
    assert call_kwargs.kwargs["data"] == {"symbol": "JKH.N0000"}
    assert len(rows) == 3
    assert rows[0].announcementId == 25040
    assert rows[0].filePath == "uploadAnnounceFiles/5051552647765_508.pdf"
    assert rows[1].filePath is None
    assert legacy_pdf_urls_by_id(rows)["25040"].startswith(CDN_BASE)


@pytest.mark.asyncio
async def test_set_disclosure_pdf_url_fills_null_only() -> None:
    conn = _Conn([{"id": 7}])
    store = _store(conn)
    assert await store.set_disclosure_pdf_url(7, f"{CDN_BASE}/uploadAnnounceFiles/a.pdf") is True
    assert "UPDATE disclosures" in conn.sql[0]
    assert "pdf_url IS NULL" in conn.sql[0]
    assert conn.params[0] == (f"{CDN_BASE}/uploadAnnounceFiles/a.pdf", 7)

    conn2 = _Conn([None])
    store2 = _store(conn2)
    assert await store2.set_disclosure_pdf_url(7, f"{CDN_BASE}/uploadAnnounceFiles/a.pdf") is False

    conn3 = _Conn([])
    store3 = _store(conn3)
    assert await store3.set_disclosure_pdf_url(7, "   ") is False
    assert conn3.sql == []


@pytest.mark.asyncio
async def test_upsert_disclosure_returns_existing_pdf_url() -> None:
    disc = Disclosure(
        external_id="ann-pdf-1",
        symbol="JKH.N0000",
        title="Filing",
        url="https://www.cse.lk/announcements#ann-pdf-1",
        published_at=datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
        seen_at=datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
    )
    existing = f"{CDN_BASE}/uploadAnnounceFiles/kept.pdf"
    conn = _Conn([None, {"id": 21, "pdf_url": existing, "inserted": False}])
    store = _store(conn)
    out = await store.upsert_disclosure(disc)
    assert out.id == 21
    assert out.pdf_url == existing
    assert "pdf_url" in conn.sql[1]


@pytest.mark.asyncio
async def test_poller_enriches_pdf_url_after_alerts_fail_soft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alerts claim/send even when legacy enrichment fails; enrichment is after unlock."""
    monkeypatch.setattr("chime.poller.asyncio.sleep", AsyncMock())

    published = datetime(2026, 7, 11, 8, 0, 0, tzinfo=UTC)
    disc_rule = make_rule(
        id=3,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=published.replace(hour=6),
    )
    stored = make_disclosure(
        external_id="25040",
        symbol="JKH.N0000",
        title="ESOS",
        published_at=published,
    ).model_copy(update={"id": 55, "pdf_url": None})

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
    storage.claim_alert = AsyncMock(return_value=9001)
    storage.mark_alert_sent = AsyncMock()
    storage.claim_unsent_batch = AsyncMock(return_value=[])
    storage.set_disclosure_pdf_url = AsyncMock(return_value=True)

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
        LegacyAnnouncementRow.model_validate(item)
        for item in _legacy_fixture()["infoAnnouncement"]
    ]
    cse.fetch_legacy_announcements = AsyncMock(return_value=legacy_rows)

    sent: list[str] = []

    async def send(chat_id: int, text: str) -> bool:
        sent.append(text)
        return True

    settings = Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
        pdf_enrich_sleep_seconds=0.5,
    )
    poller = Poller(settings, storage, cse, send)
    events = await poller.run_once(force=True)

    assert len(events) == 1
    assert sent and "ESOS" in sent[0]
    storage.advisory_unlock.assert_awaited()
    cse.fetch_legacy_announcements.assert_awaited_once_with("JKH.N0000")
    storage.set_disclosure_pdf_url.assert_awaited_once_with(
        55,
        f"{CDN_BASE}/uploadAnnounceFiles/5051552647765_508.pdf",
    )


@pytest.mark.asyncio
async def test_poller_pdf_enrich_failure_does_not_block_alerts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("chime.poller.asyncio.sleep", AsyncMock())

    published = datetime(2026, 7, 11, 8, 0, 0, tzinfo=UTC)
    disc_rule = make_rule(
        id=4,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=published.replace(hour=6),
    )
    stored = make_disclosure(
        external_id="25040",
        symbol="JKH.N0000",
        published_at=published,
    ).model_copy(update={"id": 56, "pdf_url": None})

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
    storage.claim_alert = AsyncMock(return_value=9002)
    storage.mark_alert_sent = AsyncMock()
    storage.claim_unsent_batch = AsyncMock(return_value=[])
    storage.set_disclosure_pdf_url = AsyncMock()

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(
        return_value=[PriceSnapshot(symbol="JKH.N0000", price=100.0, ts=datetime.now(UTC))]
    )
    cse.fetch_announcements_for_symbol = AsyncMock(
        return_value=[
            make_disclosure(external_id="25040", symbol="JKH.N0000", published_at=published)
        ]
    )
    cse.fetch_legacy_announcements = AsyncMock(side_effect=RuntimeError("cdn down"))

    sent: list[str] = []

    async def send(chat_id: int, text: str) -> bool:
        sent.append(text)
        return True

    settings = Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )
    poller = Poller(settings, storage, cse, send)
    events = await poller.run_once(force=True)

    assert len(events) == 1
    assert sent
    storage.set_disclosure_pdf_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_poller_skips_enrich_when_pdf_url_already_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("chime.poller.asyncio.sleep", AsyncMock())

    published = datetime(2026, 7, 11, 8, 0, 0, tzinfo=UTC)
    disc_rule = make_rule(
        id=5,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=published.replace(hour=6),
    )
    stored = make_disclosure(
        external_id="25040",
        symbol="JKH.N0000",
        published_at=published,
    ).model_copy(
        update={"id": 57, "pdf_url": f"{CDN_BASE}/uploadAnnounceFiles/already.pdf"}
    )

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
    storage.claim_alert = AsyncMock(return_value=None)  # already claimed
    storage.claim_unsent_batch = AsyncMock(return_value=[])
    storage.set_disclosure_pdf_url = AsyncMock()

    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(
        return_value=[PriceSnapshot(symbol="JKH.N0000", price=100.0, ts=datetime.now(UTC))]
    )
    cse.fetch_announcements_for_symbol = AsyncMock(
        return_value=[
            make_disclosure(external_id="25040", symbol="JKH.N0000", published_at=published)
        ]
    )
    cse.fetch_legacy_announcements = AsyncMock()

    settings = Settings(
        telegram_bot_token="x",
        database_url="postgresql://x",
        poll_jitter_seconds=0,
    )
    poller = Poller(settings, storage, cse, AsyncMock(return_value=True))
    await poller.run_once(force=True)

    cse.fetch_legacy_announcements.assert_not_awaited()
    storage.set_disclosure_pdf_url.assert_not_awaited()
