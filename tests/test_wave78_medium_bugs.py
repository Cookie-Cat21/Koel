"""Wave78: medium+ bugs — persist/disclosure id + just_inserted + promote.

1. ``persist_market_snapshots`` must isinstance-guard RETURNING ids (no
   ``int(True)==1`` / list abort mid board persist).
2. ``upsert_disclosure`` must isinstance-guard id and require ``inserted is True``
   (no ``bool(1)`` soft-accept → duplicate disclosure alerts).
3. ``_promote_skipped_if_needed`` must reject bool promote counts
   (``isinstance(True, int)`` soft-accept).
4. Keep prior isinstance source pins (claim/ready/CSE/BriefSettings).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from koel.briefs import BriefSettings
from koel.briefs.worker import _promote_skipped_if_needed
from koel.domain import Disclosure, PriceSnapshot
from koel.storage import Storage

ROOT = Path(__file__).resolve().parents[1]


class _Cursor:
    def __init__(self, *, one: Any = None, many: list[Any] | None = None) -> None:
        self._one = one
        self._many = many or []

    async def fetchone(self) -> Any:
        return self._one

    async def fetchall(self) -> list[Any]:
        return list(self._many)


class _Conn:
    def __init__(self, results: list[Any] | None = None) -> None:
        self._results = list(results or [])
        self.sql: list[str] = []

    async def execute(self, sql: str, params: Any = None) -> _Cursor:
        self.sql.append(sql)
        if not self._results:
            return _Cursor()
        nxt = self._results.pop(0)
        if isinstance(nxt, list):
            return _Cursor(many=nxt)
        return _Cursor(one=nxt)

    @asynccontextmanager
    async def transaction(self) -> Any:
        yield


class _Pool:
    def __init__(self, conn: _Conn) -> None:
        self._conn = conn

    @asynccontextmanager
    async def connection(self) -> Any:
        yield self._conn


def _store(conn: _Conn) -> Storage:
    store = Storage("postgresql://unused", min_size=1, max_size=2)
    store._pool = _Pool(conn)  # type: ignore[assignment]
    return store


def _snap(**kwargs: object) -> PriceSnapshot:
    base: dict[str, object] = dict(
        symbol="JKH.N0000",
        price=100.0,
        ts=datetime(2024, 6, 1, tzinfo=UTC),
        name="John Keells",
    )
    base.update(kwargs)
    return PriceSnapshot.model_construct(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_persist_market_snapshots_skips_poisoned_returning_ids() -> None:
    conn = _Conn([None, [{"id": True}, {"id": 9}, {"id": ["x"]}]])
    store = _store(conn)
    out = await store.persist_market_snapshots(
        [
            _snap(symbol="AAA.N0000"),
            _snap(symbol="BBB.N0000"),
            _snap(symbol="CCC.N0000"),
        ]
    )
    assert len(out) == 1 and out[0].id == 9 and out[0].symbol == "BBB.N0000"


@pytest.mark.asyncio
async def test_upsert_disclosure_rejects_poisoned_id_and_soft_inserted() -> None:
    disc = Disclosure(
        external_id="ann-w78",
        symbol="JKH.N0000",
        title="Results",
        url="https://www.cse.lk/a/1",
        published_at=datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
        seen_at=datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
    )

    store = _store(_Conn([None, {"id": True, "pdf_url": None, "inserted": True}]))
    with pytest.raises(ValueError, match="disclosure row id failed validation"):
        await store.upsert_disclosure(disc)

    conn = _Conn([None, {"id": 44, "pdf_url": None, "inserted": 1}])
    store2 = _store(conn)
    out = await store2.upsert_disclosure(disc)
    assert out.id == 44
    assert out.just_inserted is False
    assert not any("disclosure_briefs" in s for s in conn.sql)

    ok_conn = _Conn([None, {"id": 45, "pdf_url": None, "inserted": True}, None])
    store3 = _store(ok_conn)
    ok = await store3.upsert_disclosure(disc)
    assert ok.just_inserted is True
    assert any("disclosure_briefs" in s for s in ok_conn.sql)


@pytest.mark.asyncio
async def test_promote_skipped_rejects_bool_count() -> None:
    storage = MagicMock()
    storage.promote_recent_skipped_briefs = AsyncMock(return_value=True)
    settings = BriefSettings(
        enabled=True,
        api_key="k",
        provider="gemini",
        model="gemini-2.0-flash",
        skipped_promote_hours=24,
    )
    with patch("koel.briefs.worker.log") as log:
        await _promote_skipped_if_needed(storage, cfg=settings)
        log.info.assert_not_called()

    storage.promote_recent_skipped_briefs = AsyncMock(return_value=3)
    with patch("koel.briefs.worker.log") as log:
        await _promote_skipped_if_needed(storage, cfg=settings)
        log.info.assert_called_once()
        assert log.info.call_args.kwargs["count"] == 3


def test_storage_brief_claim_lookup_isinstance_pins() -> None:
    src = (ROOT / "koel" / "storage.py").read_text(encoding="utf-8")
    claim = src.split("async def claim_brief_followups")[1].split(
        "async def mark_brief_ready"
    )[0]
    assert "isinstance(external_id, str)" in claim
    assert "isinstance(symbol, str)" in claim
    assert "isinstance(brief, str)" in claim
    assert "isinstance(message_text, str)" in claim
    assert '(external_id or "").strip()' not in claim

    ready = src.split("async def get_ready_filing_brief")[1].split(
        "async def get_latest_ready_brief"
    )[0]
    assert "isinstance(external_id, str)" in ready
    assert "isinstance(symbol, str)" in ready
    assert "isinstance(brief, str)" in ready


def test_get_latest_ready_brief_field_isinstance_pins() -> None:
    src = (ROOT / "koel" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("async def get_latest_ready_brief")[1].split(
        "async def insert_disclosure_if_new"
    )[0]
    assert "isinstance(brief, str)" in chunk
    assert "isinstance(raw_sym, str)" in chunk
    assert "isinstance(raw_title, str)" in chunk
    assert "isinstance(raw_url, str)" in chunk
    assert "isinstance(raw_ext, str)" in chunk
    assert 'str(data.get("symbol")' not in chunk
    assert 'str(data.get("title")' not in chunk
    assert 'str(data.get("url")' not in chunk
    assert 'str(data.get("external_id")' not in chunk


def test_row_to_rule_and_snapshot_isinstance_pins() -> None:
    src = (ROOT / "koel" / "storage.py").read_text(encoding="utf-8")
    rule = src.split("def _row_to_rule")[1]
    assert "isinstance(raw_type, str)" in rule
    assert "isinstance(raw_sym, str)" in rule
    assert "isinstance(raw_cat, str)" in rule
    assert "AlertType(str(row" not in rule

    snap = src.split("def _row_to_snapshot")[1].split("def _row_to_rule")[0]
    assert "isinstance(raw_sym, str)" in snap
    assert "isinstance(ts, datetime)" in snap


def test_cse_sector_and_symbol_info_isinstance_pins() -> None:
    src = (ROOT / "koel" / "adapters" / "cse.py").read_text(encoding="utf-8")
    sector = src.split("def sector_row_to_snapshot")[1].split(
        "def symbol_info_to_snapshot"
    )[0]
    assert "isinstance(row.symbol, str)" in sector
    assert "isinstance(row.name, str)" in sector

    info = src.split("def symbol_info_to_snapshot")[1].split(
        "def announcement_to_disclosure"
    )[0]
    assert "isinstance(info.symbol, str)" in info


def test_brief_settings_model_raw_isinstance_pin() -> None:
    src = (ROOT / "koel" / "briefs" / "__init__.py").read_text(encoding="utf-8")
    chunk = src.split("def from_env")[1].split("def briefs_enabled")[0]
    assert "isinstance(model_raw, str)" in chunk
    assert "isinstance(provider_raw, str)" in chunk
    assert "isinstance(enabled_raw, str)" in chunk
    assert "isinstance(api_key_raw, str)" in chunk
