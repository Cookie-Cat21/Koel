"""Wave91: medium storage bugs pinned in owned storage paths."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from chime.domain import AlertRule, AlertType, Disclosure
from chime.rules import evaluate_disclosure_rules
from tests.test_storage_unit import _Conn, _store


def _disc(**kwargs: object) -> Disclosure:
    base = {
        "external_id": "ann-91",
        "symbol": "JKH.N0000",
        "company_name": "Incoming Co",
        "title": "Incoming Title",
        "category": "Incoming Category",
        "url": "https://www.cse.lk/pages/company-profile/company-profile.component.html",
        "published_at": datetime(2026, 7, 13, 8, 0, tzinfo=UTC),
        "seen_at": datetime(2026, 7, 13, 8, 1, tzinfo=UTC),
    }
    base.update(kwargs)
    return Disclosure(**base)


@pytest.mark.asyncio
async def test_upsert_disclosure_conflict_returns_stored_watermark() -> None:
    """Duplicate announcement payloads must not refresh DB publish watermarks."""
    stored_published = datetime(2026, 7, 10, 8, 0, tzinfo=UTC)
    stored_seen = datetime(2026, 7, 10, 8, 1, tzinfo=UTC)
    incoming = _disc(
        published_at=datetime(2026, 7, 13, 8, 0, tzinfo=UTC),
        seen_at=datetime(2026, 7, 13, 8, 1, tzinfo=UTC),
    )
    conn = _Conn(
        [
            None,
            {
                "id": 91,
                "title": "Stored Title",
                "category": "Stored Category",
                "url": "https://www.cse.lk/announcements/stored",
                "company_name": "Stored Co",
                "published_at": stored_published,
                "seen_at": stored_seen,
                "pdf_url": None,
                "inserted": False,
            },
        ]
    )
    store = _store(conn)

    stored = await store.upsert_disclosure(incoming)

    assert stored.id == 91
    assert stored.just_inserted is False
    assert stored.published_at == stored_published
    assert stored.seen_at == stored_seen
    assert stored.title == "Stored Title"
    assert stored.category == "Stored Category"
    assert stored.url == "https://www.cse.lk/announcements/stored"
    assert stored.company_name == "Stored Co"
    assert "published_at" in conn.sql[1]
    assert "seen_at" in conn.sql[1]

    rule = AlertRule(
        id=1,
        user_id=1,
        telegram_id=1001,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        created_at=datetime(2026, 7, 12, 8, 0, tzinfo=UTC),
    )
    assert evaluate_disclosure_rules(disclosure=stored, rules=[rule]) == []


@pytest.mark.asyncio
async def test_upsert_disclosure_conflict_rejects_poisoned_stored_strings() -> None:
    """Non-str RETURNING title/category/url/company_name fall back to incoming."""
    incoming = _disc()
    conn = _Conn(
        [
            None,
            {
                "id": 92,
                "title": True,
                "category": 1,
                "url": {"u": 1},
                "company_name": ["Co"],
                "published_at": "not-a-datetime",
                "seen_at": None,
                "pdf_url": True,
                "inserted": False,
            },
        ]
    )
    store = _store(conn)

    stored = await store.upsert_disclosure(incoming)

    assert stored.id == 92
    assert stored.title == incoming.title
    assert stored.category == incoming.category
    assert stored.url == incoming.url
    assert stored.company_name == incoming.company_name
    assert stored.published_at == incoming.published_at
    assert stored.seen_at == incoming.seen_at
    assert stored.pdf_url == incoming.pdf_url
