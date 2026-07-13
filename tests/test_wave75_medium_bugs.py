"""Wave75: medium+ bugs — rate limit / row mappers / brief egress / ledger URL.

1. ``_cmd_rate_limit`` must isinstance-guard ``bot_data`` rate (``int(list)`` /
   ``int(True)`` used to throw or soft-accept mid ``/watch``).
2. ``format_brief_lookup_reply`` must isinstance-guard ``url`` before allowlist.
3. ``_delivery_ok_ledger_path_from_env`` must isinstance-guard
   ``settings.database_url`` before ``.encode``.
4. ``get_latest_ready_brief`` must isinstance-guard PG symbol/title/url/
   external_id (no ``str()`` soft-accept of ints/None).
5. ``_row_to_rule`` / ``_row_to_snapshot`` must fail closed on poisoned type /
   symbol / price so ``list_alerts`` / ``active_rules_for_symbols`` cannot
   abort the tick.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from chime.bot import _cmd_rate_limit, format_brief_lookup_reply
from chime.domain import AlertType
from chime.poller import Poller
from chime.storage import Storage, _row_to_rule, _row_to_snapshot

ROOT = Path(__file__).resolve().parents[1]


def test_cmd_rate_limit_rejects_non_int_bot_data() -> None:
    context = MagicMock()
    for bad in ("20", 12.5, True, False, None, [20], {"n": 20}):
        context.application.bot_data = {"cmd_rate_per_minute": bad}
        assert _cmd_rate_limit(context) == 20
    context.application.bot_data = {"cmd_rate_per_minute": 7}
    assert _cmd_rate_limit(context) == 7
    context.application.bot_data = {"cmd_rate_per_minute": -3}
    assert _cmd_rate_limit(context) == 20

    src = (ROOT / "chime" / "bot.py").read_text(encoding="utf-8")
    chunk = src.split("def _cmd_rate_limit")[1].split("async def _rate_limited")[0]
    assert "isinstance(raw, bool)" in chunk
    assert "isinstance(raw, int)" in chunk
    assert "int(raw)" not in chunk


def test_format_brief_lookup_rejects_non_string_url() -> None:
    msg = format_brief_lookup_reply(
        symbol="JKH.N0000",
        brief="Margins steady.",
        title="Results",
        url=123,  # type: ignore[arg-type]
    )
    assert "Margins steady." in msg
    assert "cdn.cse.lk" not in msg

    src = (ROOT / "chime" / "bot.py").read_text(encoding="utf-8")
    chunk = src.split("def format_brief_lookup_reply")[1].split("async def cmd_brief")[0]
    assert "isinstance(url, str)" in chunk


def test_delivery_ok_ledger_rejects_non_string_database_url() -> None:
    poller = object.__new__(Poller)
    poller.settings = SimpleNamespace(database_url=123)
    assert poller._delivery_ok_ledger_path_from_env() is None
    poller.settings = SimpleNamespace(database_url="")
    assert poller._delivery_ok_ledger_path_from_env() is None
    poller.settings = SimpleNamespace(database_url="postgresql://localhost/chime")
    path = poller._delivery_ok_ledger_path_from_env()
    assert path is not None and path.name.startswith("delivery-ok-")

    src = (ROOT / "chime" / "poller.py").read_text(encoding="utf-8")
    chunk = src.split("def _delivery_ok_ledger_path_from_env")[1].split(
        "def _load_delivery_ok_ledger"
    )[0]
    assert "isinstance(db_url, str)" in chunk


@pytest.mark.asyncio
async def test_get_latest_ready_brief_rejects_non_string_pg_fields() -> None:
    class _Conn:
        async def execute(self, *_a: object, **_k: object) -> SimpleNamespace:
            return SimpleNamespace(
                fetchone=AsyncMock(
                    return_value={
                        "brief": "Ready brief",
                        "symbol": 99,
                        "title": True,
                        "url": {"u": 1},
                        "external_id": None,
                        "disclosure_id": 7,
                    }
                )
            )

        async def __aenter__(self) -> _Conn:
            return self

        async def __aexit__(self, *_a: object) -> None:
            return None

    class _Pool:
        def connection(self) -> _Conn:
            return _Conn()

    store = Storage.__new__(Storage)
    store._pool = _Pool()  # type: ignore[attr-defined]
    out = await store.get_latest_ready_brief("JKH.N0000")
    assert out is not None
    assert out["brief"] == "Ready brief"
    assert out["symbol"] == "JKH.N0000"
    assert out["title"] is None
    assert out["url"] is None
    assert out["external_id"] is None

    src = (ROOT / "chime" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("async def get_latest_ready_brief")[1].split(
        "async def insert_disclosure_if_new"
    )[0]
    assert "isinstance(raw_sym, str)" in chunk
    assert "str(data.get(\"symbol\")" not in chunk


def test_row_to_rule_and_snapshot_fail_closed() -> None:
    base = {
        "id": 1,
        "user_id": 2,
        "telegram_id": 3,
        "symbol": "JKH.N0000",
        "type": "price_above",
        "threshold": 10.0,
        "category": None,
        "active": True,
        "armed": True,
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
    }
    assert _row_to_rule({**base, "type": 123}) is None
    assert _row_to_rule({**base, "type": "not_a_rule"}) is None
    assert _row_to_rule({**base, "symbol": 99}) is None
    assert _row_to_rule({**base, "symbol": "  "}) is None
    assert _row_to_rule({**base, "id": "x"}) is None
    ok = _row_to_rule(base)
    assert ok is not None and ok.type == AlertType.PRICE_ABOVE
    poisoned_created = _row_to_rule({**base, "created_at": object()})
    assert poisoned_created is not None and poisoned_created.created_at is None

    assert _row_to_snapshot({"id": 1, "symbol": 123, "price": 1.0, "ts": datetime.now(UTC)}) is None
    assert _row_to_snapshot({"id": 1, "symbol": "  ", "price": 1.0, "ts": datetime.now(UTC)}) is None
    assert _row_to_snapshot({"id": 1, "symbol": "JKH.N0000", "price": "x", "ts": datetime.now(UTC)}) is None
    assert _row_to_snapshot(
        {"id": 1, "symbol": "JKH.N0000", "price": float("nan"), "ts": datetime.now(UTC)}
    ) is None
    assert _row_to_snapshot({"id": 1, "symbol": "JKH.N0000", "price": 1.0, "ts": object()}) is None
    snap = _row_to_snapshot(
        {
            "id": 1,
            "symbol": "jkh.n0000",
            "price": 12.5,
            "ts": datetime(2024, 6, 1, tzinfo=UTC),
        }
    )
    assert snap is not None and snap.symbol == "JKH.N0000"

    src = (ROOT / "chime" / "storage.py").read_text(encoding="utf-8")
    assert "-> AlertRule | None" in src
    assert "isinstance(raw_type, str)" in src.split("def _row_to_rule")[1]
    assert "isinstance(raw_sym, str)" in src.split("def _row_to_snapshot")[1]


@pytest.mark.asyncio
async def test_list_alerts_skips_poisoned_rows() -> None:
    class _Conn:
        async def execute(self, *_a: object, **_k: object) -> SimpleNamespace:
            return SimpleNamespace(
                fetchall=AsyncMock(
                    return_value=[
                        {
                            "id": 1,
                            "user_id": 9,
                            "telegram_id": 100,
                            "symbol": "JKH.N0000",
                            "type": "bogus",
                            "threshold": 1.0,
                            "category": None,
                            "active": True,
                            "armed": True,
                            "created_at": datetime(2024, 1, 1, tzinfo=UTC),
                        },
                        {
                            "id": 2,
                            "user_id": 9,
                            "telegram_id": 100,
                            "symbol": "JKH.N0000",
                            "type": "price_above",
                            "threshold": 5.0,
                            "category": None,
                            "active": True,
                            "armed": True,
                            "created_at": datetime(2024, 1, 1, tzinfo=UTC),
                        },
                    ]
                )
            )

        async def __aenter__(self) -> _Conn:
            return self

        async def __aexit__(self, *_a: object) -> None:
            return None

    class _Pool:
        def connection(self) -> _Conn:
            return _Conn()

    store = Storage.__new__(Storage)
    store._pool = _Pool()  # type: ignore[attr-defined]
    rules = await store.list_alerts(9)
    assert len(rules) == 1
    assert rules[0].id == 2
