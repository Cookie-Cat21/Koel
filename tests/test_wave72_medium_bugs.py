"""Wave72: medium+ bugs — cancel/brief/env/CSE/persist + searchParams typeof.

1. ``cmd_cancel`` must isinstance-guard ``args[0]`` on the parse-None error
   path — non-strings used to throw on ``.lstrip`` after ``parse_cancel_alert_id``.
2. ``parse_alert_args`` disclosure category must skip non-string tokens before
   ``" ".join``.
3. ``_notify_brief_followups`` must isinstance-guard ``brief`` before ``.strip``.
4. ``_ready_filing_brief_for`` must isinstance-guard ``event_key`` before
   ``.startswith`` / ``.split``.
5. ``_delivery_ok_token`` / durable ledger must isinstance-guard ``message``
   before ``.encode``.
6. Briefs ``_env_int`` / ``_env_float`` must isinstance-guard getenv (no
   ``str(raw)`` soft-accept of int mocks).
7. CSE normalize + fetch helpers must fail closed on non-string symbols;
   ``CSEClient.__init__`` must isinstance-guard ``base_url``.
8. Persist / previous_state / board gap reporting must skip non-string symbols.
9. Dash searchParams / Content-Length / ``active`` must typeof-guard before
   ``.trim`` / soft-match.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chime.adapters.cse import (
    AnnouncementRow,
    CSEClient,
    SectorRow,
    SymbolInfo,
    TradeSummaryRow,
    announcement_to_disclosure,
    sector_row_to_snapshot,
    symbol_info_to_snapshot,
    trade_row_to_snapshot,
)
from chime.bot import cmd_cancel, parse_alert_args
from chime.briefs import BriefSettings
from chime.briefs.worker import _notify_brief_followups
from chime.domain import (
    AlertEvent,
    AlertType,
    PreviousPriceState,
    PriceSnapshot,
    SectorSnapshot,
)
from chime.notify import SendResult
from chime.poller import Poller, _delivery_ok_token
from chime.storage import Storage

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


@pytest.mark.asyncio
async def test_cmd_cancel_non_string_arg_fail_closed() -> None:
    storage = AsyncMock()
    update = MagicMock()
    update.effective_user.id = 1001
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    context.application.bot_data = {"storage": storage}
    context.args = [123]

    with patch("chime.bot._rate_limited", AsyncMock(return_value=False)):
        await cmd_cancel(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    text = update.effective_message.reply_text.await_args.args[0]
    assert "Alert id must be a number" in text
    storage.deactivate_alert.assert_not_awaited()

    src = (ROOT / "chime" / "bot.py").read_text(encoding="utf-8")
    chunk = src.split("async def cmd_cancel")[1].split("async def cmd_myalerts")[0]
    assert "isinstance(raw_arg, str)" in chunk


def test_parse_alert_disclosure_skips_non_string_category_tokens() -> None:
    parsed, err = parse_alert_args(
        ["JKH.N0000", "disclosure", 123, "Results", None, "Q1"]  # type: ignore[list-item]
    )
    assert err is None and parsed is not None
    assert parsed.alert_type == AlertType.DISCLOSURE
    assert parsed.category == "Results Q1"

    parsed2, err2 = parse_alert_args(
        ["JKH.N0000", "disclosure", True, {"c": 1}]  # type: ignore[list-item]
    )
    assert err2 is None and parsed2 is not None
    assert parsed2.category is None

    src = (ROOT / "chime" / "bot.py").read_text(encoding="utf-8")
    chunk = src.split("def parse_alert_args")[1].split("async def _user_id")[0]
    assert "isinstance(a, str)" in chunk
    assert '" ".join(args[2:])' not in chunk


@pytest.mark.asyncio
async def test_notify_brief_followups_rejects_non_string_brief() -> None:
    storage = MagicMock()
    storage.claim_brief_followups = AsyncMock(return_value=[])

    async def notify(_chat_id: int, _text: str) -> SendResult:
        raise AssertionError("notify must not run")

    await _notify_brief_followups(
        storage,
        notify=notify,
        row={
            "disclosure_id": 1,
            "symbol": "JKH.N0000",
            "external_id": "ext-1",
            "title": "Results",
        },
        brief=123,  # type: ignore[arg-type]
    )
    storage.claim_brief_followups.assert_not_awaited()

    src = (ROOT / "chime" / "briefs" / "worker.py").read_text(encoding="utf-8")
    chunk = src.split("async def _notify_brief_followups")[1].split(
        "async def _promote_skipped_if_needed"
    )[0]
    assert "isinstance(brief, str)" in chunk


@pytest.mark.asyncio
async def test_ready_filing_brief_rejects_non_string_event_key() -> None:
    poller = object.__new__(Poller)
    poller.storage = SimpleNamespace(
        get_ready_filing_brief=AsyncMock(return_value="brief body"),
    )
    event = AlertEvent.model_construct(
        rule_id=1,
        user_id=1,
        telegram_id=1,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        trigger="new disclosure",
        current_price=None,
        event_key=99,  # type: ignore[arg-type]
        disclosure_id=7,
    )
    out = await poller._ready_filing_brief_for(event)
    assert out == "brief body"
    poller.storage.get_ready_filing_brief.assert_awaited_once_with(
        disclosure_id=7,
        external_id=None,
        symbol="JKH.N0000",
    )

    src = (ROOT / "chime" / "poller.py").read_text(encoding="utf-8")
    chunk = src.split("async def _ready_filing_brief_for")[1].split(
        "async def _claim_and_send"
    )[0]
    assert "isinstance(key, str)" in chunk


def test_delivery_ok_token_rejects_non_string_message() -> None:
    token = _delivery_ok_token(
        log_id=1,
        rule_id=2,
        telegram_id=3,
        message=123,  # type: ignore[arg-type]
    )
    assert token == _delivery_ok_token(
        log_id=1, rule_id=2, telegram_id=3, message=""
    )

    src = (ROOT / "chime" / "poller.py").read_text(encoding="utf-8")
    tok = src.split("def _delivery_ok_token")[1].split("def parse_hhmm")[0]
    assert "isinstance(message, str)" in tok
    durable = src.split("def _durably_remember_delivery_ok")[1].split(
        "def _delivery_ok_already_recorded"
    )[0]
    assert "isinstance(pending.message, str)" in durable


def test_briefs_env_int_float_reject_non_string_getenv() -> None:
    def _hostile(name: str, default: str | None = None) -> object:
        if name in {
            "AI_MAX_BRIEFS_PER_DAY",
            "AI_MAX_INPUT_CHARS",
            "PDF_MAX_BYTES",
            "BRIEF_PDF_GRACE_SECONDS",
            "BRIEF_CDN_BACKOFF_SECONDS",
            "BRIEF_SKIPPED_PROMOTE_HOURS",
        }:
            return 999
        if name in {"AI_HTTP_TIMEOUT_SECONDS", "AI_BRIEF_SLEEP_SECONDS"}:
            return 12.5
        if default is not None:
            return default
        return None

    with patch("chime.briefs.os.getenv", side_effect=_hostile):
        cfg = BriefSettings.from_env()
    assert cfg.max_briefs_per_day == 50
    assert cfg.max_input_chars == 12_000
    assert cfg.pdf_max_bytes == 5_242_880
    assert cfg.http_timeout_seconds == 30.0
    assert cfg.sleep_seconds == 0.5
    assert cfg.pdf_grace_seconds == 120
    assert cfg.cdn_backoff_seconds == 300
    assert cfg.skipped_promote_hours == 24

    src = (ROOT / "chime" / "briefs" / "__init__.py").read_text(encoding="utf-8")
    env_int = src.split("def _env_int")[1].split("def _env_float")[0]
    env_float = src.split("def _env_float")[1].split("@dataclass")[0]
    assert "isinstance(raw, str)" in env_int
    assert "isinstance(raw, str)" in env_float
    assert "str(raw).strip()" not in env_int
    assert "str(raw).strip()" not in env_float


@pytest.mark.asyncio
async def test_cse_fetch_and_normalize_reject_non_string_symbols() -> None:
    client = CSEClient(base_url=123, timeout=1.0)  # type: ignore[arg-type]
    assert client.base_url == "https://www.cse.lk/api"
    assert await client.fetch_company_info(123) is None  # type: ignore[arg-type]
    assert await client.fetch_company_info("") is None
    assert await client.fetch_announcements_for_symbol(True) == []  # type: ignore[arg-type]
    assert await client.fetch_announcements_for_symbol("  ") == []
    assert await client.fetch_legacy_announcements(None) == []  # type: ignore[arg-type]
    assert await client.fetch_legacy_announcements("") == []

    assert trade_row_to_snapshot(
        TradeSummaryRow.model_construct(symbol=123, price=10.0, name="X")
    ) is None
    assert symbol_info_to_snapshot(
        SymbolInfo.model_construct(symbol=None, lastTradedPrice=10.0)
    ) is None
    assert sector_row_to_snapshot(
        SectorRow.model_construct(sectorId=1, symbol=5, name="Energy")
    ) is None
    assert sector_row_to_snapshot(
        SectorRow.model_construct(sectorId=1, symbol="egy", name=9)
    ) is None
    assert (
        announcement_to_disclosure(
            AnnouncementRow(announcementId=1, createdDate=1_720_000_000_000),
            symbol=123,  # type: ignore[arg-type]
        )
        is None
    )

    src = (ROOT / "chime" / "adapters" / "cse.py").read_text(encoding="utf-8")
    assert "isinstance(base_url, str)" in src.split("def __init__")[1].split(
        "self._owns_client"
    )[0]
    for fn in (
        "async def fetch_company_info",
        "async def fetch_announcements_for_symbol",
        "async def fetch_legacy_announcements",
    ):
        chunk = src.split(fn)[1].split("async def ")[0]
        assert "isinstance(symbol, str)" in chunk, fn


@pytest.mark.asyncio
async def test_persist_and_previous_state_skip_non_string_symbols() -> None:
    store = Storage.__new__(Storage)
    store._pool = MagicMock()  # type: ignore[attr-defined]

    snaps = [
        PriceSnapshot.model_construct(
            symbol=123,  # type: ignore[arg-type]
            price=10.0,
            ts=datetime.now(UTC),
        ),
    ]
    assert await store.persist_market_snapshots(snaps) == []

    sectors = [
        SectorSnapshot.model_construct(
            sector_id=1,
            symbol=99,  # type: ignore[arg-type]
            name="Energy",
            ts=datetime.now(UTC),
        ),
    ]
    assert await store.persist_sectors(sectors) == []

    for bad in (123, True, None, ["JKH"]):
        out = await store.get_previous_state(bad, before_id=1)  # type: ignore[arg-type]
        assert isinstance(out, PreviousPriceState)
        assert out.price is None

    src = (ROOT / "chime" / "storage.py").read_text(encoding="utf-8")
    assert "isinstance(snap.symbol, str)" in src.split(
        "async def persist_market_snapshots"
    )[1].split("async def delete_old_non_watchlist_snapshots")[0]
    assert "isinstance(sector.symbol, str)" in src.split("async def persist_sectors")[
        1
    ].split("async def latest_snapshot")[0]
    prev = src.split("async def get_previous_state")[1].split("async def ")[0]
    assert "isinstance(symbol, str)" in prev


@pytest.mark.asyncio
async def test_list_stock_names_skips_non_string_pg_values() -> None:
    class _Conn:
        async def execute(self, *_a: object, **_k: object) -> SimpleNamespace:
            return SimpleNamespace(
                fetchall=AsyncMock(
                    return_value=[
                        {"symbol": 123, "name": "Acme"},
                        {"symbol": "JKH.N0000", "name": None},
                        {"symbol": "JKH.N0000", "name": "John Keells"},
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
    assert await store.list_stock_names() == [("JKH.N0000", "John Keells")]


@pytest.mark.asyncio
async def test_get_previous_state_rejects_blank_symbol() -> None:
    store = Storage.__new__(Storage)
    store._pool = MagicMock()  # type: ignore[attr-defined]
    out = await store.get_previous_state("  ", before_id=1)
    assert isinstance(out, PreviousPriceState)
    assert out.price is None
    store._pool.connection.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_all_sectors_skips_when_normalize_returns_none() -> None:
    client = CSEClient(client=AsyncMock())
    raw = [
        {"sectorId": 1, "symbol": "egy", "name": "Energy", "indexValue": 10.0}
    ]
    with patch.object(client, "_request", AsyncMock(return_value=raw)):
        with patch(
            "chime.adapters.cse.sector_row_to_snapshot",
            return_value=None,
        ):
            out = await client.fetch_all_sectors()
    assert out == []


def test_web_searchparams_and_header_typeof_guards() -> None:
    alerts = (WEB / "src" / "app" / "api" / "v1" / "alerts" / "route.ts").read_text(
        encoding="utf-8"
    )
    history = (
        WEB / "src" / "app" / "api" / "v1" / "alerts" / "history" / "route.ts"
    ).read_text(encoding="utf-8")
    movers = (
        WEB / "src" / "app" / "api" / "v1" / "market" / "movers" / "route.ts"
    ).read_text(encoding="utf-8")
    symbols = (WEB / "src" / "app" / "api" / "v1" / "symbols" / "route.ts").read_text(
        encoding="utf-8"
    )
    bounded = (WEB / "src" / "lib" / "api" / "read-bounded-text.ts").read_text(
        encoding="utf-8"
    )
    json_body = (WEB / "src" / "lib" / "api" / "read-json-body.ts").read_text(
        encoding="utf-8"
    )

    assert 'typeof symbolRaw === "string"' in alerts
    assert 'typeof activeParam !== "string"' in alerts
    assert 'typeof symbolRaw === "string"' in history
    assert 'typeof directionParam === "string"' in movers
    assert 'typeof sortParam === "string"' in symbols
    assert 'typeof lenHeader === "string"' in bounded
    assert 'typeof lenHeader === "string"' in json_body


def test_poller_gap_reporting_isinstance_guard() -> None:
    src = (ROOT / "chime" / "poller.py").read_text(encoding="utf-8")
    assert "isinstance(s.symbol, str)" in src
