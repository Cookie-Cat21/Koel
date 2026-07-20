"""Wave73: medium+ bugs — previous_state / base_url / cancel / env / web.

1. ``get_previous_state`` must isinstance-guard ``symbol`` before ``.strip``
   (``previous_snapshot`` already failed closed, but the move-key query still
   threw on non-string symbols mid rule eval).
2. ``CSEClient.__init__`` must isinstance-guard ``base_url`` before ``.rstrip``.
3. ``cmd_cancel`` must isinstance-guard ``args[0]`` on the parse-None path.
4. ``_notify_brief_followups`` / ``_delivery_ok_token`` / ``_ready_filing_brief_for``
   must isinstance-guard brief / message / event_key.
5. Brief ``_env_int`` / ``_env_float`` must isinstance-guard getenv (no
   ``str(raw)`` soft-accept).
6. CSE fetch + board normalize must isinstance-guard symbols.
7. Persist paths must skip non-string symbols; dash searchParams / CL /
   ``active`` must typeof-guard before ``.trim`` / soft-match.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from koel.adapters.cse import (
    CSEClient,
    TradeSummaryRow,
    announcement_to_disclosure,
    symbol_info_to_snapshot,
    trade_row_to_snapshot,
)
from koel.bot import cmd_cancel
from koel.briefs import BriefSettings, _env_float, _env_int
from koel.briefs.worker import _notify_brief_followups
from koel.domain import (
    AlertEvent,
    AlertType,
    PreviousPriceState,
    PriceSnapshot,
    SectorSnapshot,
)
from koel.notify import SendResult
from koel.poller import Poller, _delivery_ok_token
from koel.storage import Storage

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def _snap(**kwargs: object) -> PriceSnapshot:
    base: dict[str, object] = dict(
        symbol="JKH.N0000",
        price=100.0,
        ts=datetime(2024, 6, 1, tzinfo=UTC),
    )
    base.update(kwargs)
    return PriceSnapshot.model_construct(**base)  # type: ignore[arg-type]


def _sector(**kwargs: object) -> SectorSnapshot:
    base: dict[str, object] = dict(
        sector_id=1,
        symbol="EGY",
        name="Energy",
        ts=datetime(2024, 6, 1, tzinfo=UTC),
    )
    base.update(kwargs)
    return SectorSnapshot.model_construct(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_get_previous_state_rejects_non_string_symbol() -> None:
    store = Storage.__new__(Storage)
    store._pool = MagicMock()  # type: ignore[attr-defined]

    for bad in (123, True, None, ["JKH"]):
        out = await store.get_previous_state(bad, before_id=1)  # type: ignore[arg-type]
        assert isinstance(out, PreviousPriceState)
        assert out.price is None
        assert out.change_pct is None
        assert out.move_fired_keys == set()

    out_blank = await store.get_previous_state("  ", before_id=1)
    assert out_blank.price is None and out_blank.move_fired_keys == set()

    src = (ROOT / "koel" / "storage.py").read_text(encoding="utf-8")
    chunk = src.split("async def get_previous_state")[1].split("async def ")[0]
    assert "isinstance(symbol, str)" in chunk
    assert "symbol.strip().upper()," not in chunk


def test_cse_client_base_url_isinstance_guard() -> None:
    client = CSEClient(base_url=123, timeout=1.0)  # type: ignore[arg-type]
    assert client.base_url == "https://www.cse.lk/api"
    client2 = CSEClient(base_url="  ", timeout=1.0)
    assert client2.base_url == "https://www.cse.lk/api"
    client3 = CSEClient(base_url="https://www.cse.lk/api/", timeout=1.0)
    assert client3.base_url == "https://www.cse.lk/api"

    src = (ROOT / "koel" / "adapters" / "cse.py").read_text(encoding="utf-8")
    chunk = src.split("class CSEClient")[1].split("def _breaker")[0]
    assert "isinstance(base_url, str)" in chunk


@pytest.mark.asyncio
async def test_cmd_cancel_non_string_arg_fail_closed() -> None:
    update = MagicMock()
    update.effective_message = MagicMock()
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = [123]
    context.application.bot_data = {"storage": MagicMock()}

    with patch("koel.bot._rate_limited", AsyncMock(return_value=False)):
        await cmd_cancel(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    text = update.effective_message.reply_text.await_args.args[0]
    assert "Alert id must be a number" in text

    src = (ROOT / "koel" / "bot.py").read_text(encoding="utf-8")
    chunk = src.split("async def cmd_cancel")[1].split("async def cmd_myalerts")[0]
    assert "isinstance(raw_arg, str)" in chunk


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

    src = (ROOT / "koel" / "briefs" / "worker.py").read_text(encoding="utf-8")
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
        trigger=None,
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

    src = (ROOT / "koel" / "poller.py").read_text(encoding="utf-8")
    chunk = src.split("async def _ready_filing_brief_for")[1].split(
        "async def _claim_only"
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

    src = (ROOT / "koel" / "poller.py").read_text(encoding="utf-8")
    tok = src.split("def _delivery_ok_token")[1].split("def parse_hhmm")[0]
    assert "isinstance(message, str)" in tok
    durable = src.split("def _durably_remember_delivery_ok")[1].split(
        "def _delivery_ok_already_recorded"
    )[0]
    assert "isinstance(pending.message, str)" in durable


def test_briefs_env_int_float_reject_non_string_getenv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_BRIEFS_ENABLED", "0")
    monkeypatch.setenv("AI_API_KEY", "")

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

    with patch("koel.briefs.os.getenv", side_effect=_hostile):
        cfg = BriefSettings.from_env()
    assert cfg.max_briefs_per_day == 50
    assert cfg.max_input_chars == 12_000
    assert cfg.pdf_max_bytes == 5_242_880
    assert cfg.http_timeout_seconds == 30.0
    assert cfg.sleep_seconds == 0.5

    with patch("koel.briefs.os.getenv", return_value=99):
        assert _env_int("X", 3) == 3
        assert _env_float("Y", 1.5) == 1.5

    src = (ROOT / "koel" / "briefs" / "__init__.py").read_text(encoding="utf-8")
    env_int = src.split("def _env_int")[1].split("def _env_float")[0]
    env_float = src.split("def _env_float")[1].split("@dataclass")[0]
    assert "isinstance(raw, str)" in env_int
    assert "isinstance(raw, str)" in env_float
    assert "str(raw)" not in env_int
    assert "str(raw)" not in env_float


@pytest.mark.asyncio
async def test_cse_fetch_and_normalize_reject_non_string_symbol() -> None:
    client = CSEClient(base_url="https://www.cse.lk/api", timeout=1.0)
    assert await client.fetch_company_info(123) is None  # type: ignore[arg-type]
    assert await client.fetch_announcements_for_symbol(True) == []  # type: ignore[arg-type]
    assert await client.fetch_legacy_announcements(None) == []  # type: ignore[arg-type]

    row = TradeSummaryRow.model_construct(
        symbol=123,  # type: ignore[arg-type]
        price=10.0,
        lastTradedTime=None,
        previousClose=None,
        change=None,
        percentageChange=None,
        sharevolume=None,
        tradevolume=None,
        turnover=None,
        high=None,
        low=None,
        open=None,
        marketCap=None,
        name="X",
    )
    assert trade_row_to_snapshot(row) is None

    info = SimpleNamespace(
        symbol=True,
        lastTradedPrice=10.0,
        previousClose=None,
        change=None,
        changePercentage=None,
        tdyShareVolume=None,
        tdyTradeVolume=None,
        tdyTurnover=None,
        hiTrade=None,
        lowTrade=None,
        marketCap=None,
        name="X",
    )
    assert symbol_info_to_snapshot(info) is None  # type: ignore[arg-type]
    ann = SimpleNamespace(
        announcementId="1",
        id=None,
        createdDate=1_700_000_000_000,
        dateOfAnnouncement=None,
        announcementCategory="Fin",
        remarks=None,
        company="Acme",
        url=None,
    )
    assert announcement_to_disclosure(ann, symbol=123) is None  # type: ignore[arg-type]

    src = (ROOT / "koel" / "adapters" / "cse.py").read_text(encoding="utf-8")
    assert "isinstance(row.symbol, str)" in src.split("def trade_row_to_snapshot")[1].split(
        "def sector_row_to_snapshot"
    )[0]
    assert "isinstance(symbol, str)" in src.split("async def fetch_company_info")[1].split(
        "async def "
    )[0]


@pytest.mark.asyncio
async def test_persist_market_and_sectors_skip_non_string_symbols() -> None:
    class _Conn:
        async def execute(self, *_a: object, **_k: object) -> SimpleNamespace:
            return SimpleNamespace(
                fetchall=AsyncMock(return_value=[]),
                fetchone=AsyncMock(return_value=None),
            )

        def transaction(self) -> SimpleNamespace:
            return SimpleNamespace(
                __aenter__=AsyncMock(return_value=None),
                __aexit__=AsyncMock(return_value=None),
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

    assert (
        await store.persist_market_snapshots(
            [_snap(symbol=123), _snap(symbol=True)]  # type: ignore[arg-type]
        )
        == []
    )
    assert (
        await store.persist_sectors(
            [_sector(symbol=99), _sector(symbol=None)]  # type: ignore[arg-type]
        )
        == []
    )

    src = (ROOT / "koel" / "storage.py").read_text(encoding="utf-8")
    assert "isinstance(snap.symbol, str)" in src.split("async def persist_market_snapshots")[
        1
    ].split("async def ")[0]
    assert "isinstance(sector.symbol, str)" in src.split("async def persist_sectors")[1].split(
        "async def "
    )[0]


def test_web_searchparams_active_and_content_length_typeof_pins() -> None:
    alerts = (WEB / "src" / "app" / "api" / "v1" / "alerts" / "route.ts").read_text(
        encoding="utf-8"
    )
    assert 'typeof symbolRaw === "string"' in alerts
    assert 'typeof activeParam !== "string"' in alerts

    history = (
        WEB / "src" / "app" / "api" / "v1" / "alerts" / "history" / "route.ts"
    ).read_text(encoding="utf-8")
    assert 'typeof symbolRaw === "string"' in history

    movers = (WEB / "src" / "app" / "api" / "v1" / "market" / "movers" / "route.ts").read_text(
        encoding="utf-8"
    )
    assert 'typeof directionParam === "string"' in movers

    symbols = (WEB / "src" / "app" / "api" / "v1" / "symbols" / "route.ts").read_text(
        encoding="utf-8"
    )
    assert 'typeof sortParam === "string"' in symbols

    bounded = (WEB / "src" / "lib" / "api" / "read-bounded-text.ts").read_text(encoding="utf-8")
    assert 'typeof lenHeader === "string"' in bounded

    json_body = (WEB / "src" / "lib" / "api" / "read-json-body.ts").read_text(encoding="utf-8")
    assert 'typeof lenHeader === "string"' in json_body
