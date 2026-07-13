"""Wave77: medium+ bugs — health ok / dead-letter attempts / ensure_user id.

1. ``HealthState.update`` must isinstance-guard ``ok`` (no ``bool(1)/"false"``).
2. ``format_dead_letter_notify`` must isinstance-guard ``attempts`` (no
   ``int(True)==1`` soft-accept).
3. ``ensure_user`` must isinstance-guard RETURNING ``id`` (no ``int(True)==1``).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

from chime.domain import format_dead_letter_notify
from chime.health import HealthState
from chime.storage import Storage

ROOT = Path(__file__).resolve().parents[1]


class _Cursor:
    def __init__(self, *, one: Any = None) -> None:
        self._one = one

    async def fetchone(self) -> Any:
        return self._one


def test_health_state_update_rejects_non_bool_ok() -> None:
    state = HealthState()
    assert state.ok is True
    state.update(ok=False)
    assert state.ok is False
    state.update(ok=1)  # type: ignore[arg-type]
    assert state.ok is False
    state.update(ok="false")  # type: ignore[arg-type]
    assert state.ok is False
    state.update(ok=True)
    assert state.ok is True

    src = (ROOT / "chime" / "health.py").read_text(encoding="utf-8")
    chunk = src.split("def update")[1].split("def start_health_server")[0]
    assert "isinstance(raw_ok, bool)" in chunk
    assert 'bool(kwargs["ok"])' not in chunk


def test_format_dead_letter_rejects_bool_and_non_int_attempts() -> None:
    assert "after 0 tries" in format_dead_letter_notify("JKH.N0000", True)  # type: ignore[arg-type]
    assert "after 0 tries" in format_dead_letter_notify("JKH.N0000", False)  # type: ignore[arg-type]
    assert "after 0 tries" in format_dead_letter_notify("JKH.N0000", "5")  # type: ignore[arg-type]
    assert "after 0 tries" in format_dead_letter_notify("JKH.N0000", 5.5)  # type: ignore[arg-type]
    assert "after 5 tries" in format_dead_letter_notify("JKH.N0000", 5)
    assert "after 0 tries" in format_dead_letter_notify("JKH.N0000", -1)
    assert "after 1000000 tries" in format_dead_letter_notify("JKH.N0000", 10**100)

    src = (ROOT / "chime" / "domain.py").read_text(encoding="utf-8")
    chunk = src.split("def format_dead_letter_notify")[1].split(
        "def format_brief_followup"
    )[0]
    assert "isinstance(attempts, bool)" in chunk
    assert "int(attempts)" not in chunk


@pytest.mark.asyncio
async def test_ensure_user_rejects_poisoned_returning_id() -> None:
    class _Conn:
        def __init__(self, one: Any) -> None:
            self._one = one

        async def execute(self, *_a: object, **_k: object) -> _Cursor:
            return _Cursor(one=self._one)

        @asynccontextmanager
        async def connection(self) -> Any:
            yield self

    class _Pool:
        def __init__(self, one: Any) -> None:
            self._conn = _Conn(one)

        @asynccontextmanager
        async def connection(self) -> Any:
            yield self._conn

    store = Storage.__new__(Storage)
    store._pool = _Pool({"id": True})  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="failed validation"):
        await store.ensure_user(1001)

    store2 = Storage.__new__(Storage)
    store2._pool = _Pool({"id": 42})  # type: ignore[attr-defined]
    assert await store2.ensure_user(1001) == 42

    src = (ROOT / "chime" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("async def ensure_user")[1].split("async def add_watch")[0]
    assert "isinstance(raw_id, bool)" in chunk
    assert 'int(_as_row(row)["id"])' not in chunk
