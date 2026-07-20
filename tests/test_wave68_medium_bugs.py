"""Wave68: medium+ bugs — brief prompt / resolve / alert parse / storage symbols.

1. ``build_brief_prompt`` must isinstance-guard ``symbol`` / ``title`` /
   ``extracted_text`` — non-strings used to throw on ``.replace`` / ``.strip``.
2. ``resolve_announcement_symbol`` must isinstance-guard ``allowed_symbols``
   members and ``row.symbol`` / ``row.company``.
3. ``_parse_threshold_token`` / ``parse_alert_args`` must isinstance-guard
   threshold tokens and alert kind (``.strip`` / ``.lower`` used to raise).
4. Storage symbol mutators/lookups must isinstance-guard ``symbol`` before
   ``.strip`` (and empty-after-strip fail-closed).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from koel.adapters.cse import resolve_announcement_symbol
from koel.bot import parse_alert_args
from koel.briefs import build_brief_prompt
from koel.domain import AlertType
from koel.storage import Storage

ROOT = Path(__file__).resolve().parents[1]


def test_build_brief_prompt_rejects_non_string_fields() -> None:
    msg = build_brief_prompt(
        symbol=123,  # type: ignore[arg-type]
        title=True,  # type: ignore[arg-type]
        extracted_text={"t": 1},  # type: ignore[arg-type]
    )
    assert "Symbol: UNKNOWN" in msg
    assert "Title: (untitled)" in msg
    assert "<<<FILING>>>" in msg

    ok = build_brief_prompt(
        symbol="JKH.N0000", title="Results", extracted_text="Filing body"
    )
    assert "Symbol: JKH.N0000" in ok and "Filing body" in ok

    src = (ROOT / "koel" / "briefs" / "__init__.py").read_text(encoding="utf-8")
    chunk = src.split("def build_brief_prompt")[1]
    assert "isinstance(extracted_text, str)" in chunk
    assert "isinstance(symbol, str)" in chunk
    assert "isinstance(title, str)" in chunk


def test_resolve_announcement_symbol_isinstance_guards() -> None:
    name_map = {"ACME PLC": "ACM.N0000"}
    assert (
        resolve_announcement_symbol(
            SimpleNamespace(symbol="ACM.N0000", company=None),
            name_map=name_map,
            allowed_symbols={"ACM.N0000", 123, None},  # type: ignore[arg-type]
        )
        == "ACM.N0000"
    )
    assert (
        resolve_announcement_symbol(
            SimpleNamespace(symbol=99, company="Acme PLC"),  # type: ignore[arg-type]
            name_map=name_map,
            allowed_symbols={"ACM.N0000"},
        )
        == "ACM.N0000"
    )
    assert (
        resolve_announcement_symbol(
            SimpleNamespace(symbol=None, company=123),
            name_map=name_map,
            allowed_symbols={"ACM.N0000"},
        )
        is None
    )
    src = (ROOT / "koel" / "adapters" / "cse.py").read_text(encoding="utf-8")
    chunk = src.split("def resolve_announcement_symbol")[1].split("class CSEClient")[0]
    assert "isinstance(s, str)" in chunk
    assert "isinstance(row.symbol, str)" in chunk
    assert "isinstance(row.company, str)" in chunk


def test_parse_alert_args_rejects_non_string_kind_and_threshold() -> None:
    parsed, err = parse_alert_args(["JKH.N0000", 123, "5"])  # type: ignore[list-item]
    assert parsed is None and err is not None
    parsed2, err2 = parse_alert_args(["JKH.N0000", "above", 5])  # type: ignore[list-item]
    assert parsed2 is None and err2 is not None
    ok, err_ok = parse_alert_args(["JKH.N0000", "above", "5"])
    assert err_ok is None and ok is not None and ok.threshold == 5.0

    src = (ROOT / "koel" / "bot.py").read_text(encoding="utf-8")
    thr = src.split("def _parse_threshold_token")[1].split("def parse_alert_args")[0]
    assert "isinstance(raw, str)" in thr
    args = src.split("def parse_alert_args")[1].split("async def _user_id")[0]
    assert "isinstance(args[1], str)" in args


@pytest.mark.asyncio
async def test_storage_symbol_isinstance_guards() -> None:
    storage = Storage.__new__(Storage)
    await storage.upsert_stock(123)  # type: ignore[arg-type]
    await storage.upsert_stock("   ")
    await storage.add_watch(1, None)  # type: ignore[arg-type]
    await storage.add_watch(1, "  ")
    assert await storage.remove_watch(1, 99) is False  # type: ignore[arg-type]
    assert await storage.remove_watch(1, "") is False
    assert await storage.unwatch_symbol(1, True) == (False, 0)  # type: ignore[arg-type]
    assert await storage.unwatch_symbol(1, "\t") == (False, 0)
    assert await storage.latest_snapshot(1.5) is None  # type: ignore[arg-type]
    assert await storage.latest_snapshot("") is None
    assert await storage.previous_snapshot(["x"], before_id=1) is None  # type: ignore[arg-type]
    assert await storage.previous_snapshot("  ", before_id=1) is None
    assert await storage.deactivate_rules_for_symbol(1, {"s": 1}) == 0  # type: ignore[arg-type]
    assert await storage.deactivate_rules_for_symbol(1, "") == 0
    with pytest.raises(ValueError, match="symbol"):
        await storage.create_alert_rule(1, 123, AlertType.PRICE_ABOVE, 10.0)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="symbol"):
        await storage.create_alert_rule(1, "  ", AlertType.PRICE_ABOVE, 10.0)

    src = (ROOT / "koel" / "storage.py").read_text(encoding="utf-8")
    for fn in (
        "async def upsert_stock",
        "async def latest_snapshot",
        "async def previous_snapshot",
        "async def add_watch",
        "async def remove_watch",
        "async def unwatch_symbol",
        "async def create_alert_rule",
        "async def deactivate_rules_for_symbol",
    ):
        chunk = src.split(fn)[1].split("async def ")[0]
        assert "isinstance(symbol, str)" in chunk, fn
