"""Wave10: unit coverage push for koel.poller missing / fail-soft branches."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from koel.adapters.cse import AnnouncementRow
from koel.config import Settings
from koel.domain import AlertEvent, AlertType, PreviousPriceState, PriceSnapshot
from koel.health import HealthState
from koel.notify import SendResult
from koel.poller import (
    DELIVERY_OK_LEDGER_ENV,
    PendingSend,
    Poller,
    run_poller_forever,
)
from tests.conftest import make_rule


def _settings(**kwargs: object) -> Settings:
    base: dict[str, object] = dict(
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
    settings: Settings | None = None,
    **settings_kw: object,
) -> Poller:
    return Poller(
        settings or _settings(**settings_kw),
        storage or AsyncMock(),
        cse or AsyncMock(),
        send or AsyncMock(return_value=True),
    )


def _pending(
    *,
    log_id: int = 1,
    telegram_id: int = 9,
    message: str = "body",
    rule_id: int | None = 1,
    event: AlertEvent | None = None,
    symbol: str | None = None,
) -> PendingSend:
    return PendingSend(
        log_id=log_id,
        telegram_id=telegram_id,
        message=message,
        already_claimed_new=True,
        rule_id=rule_id,
        event=event,
        symbol=symbol,
    )


@pytest.mark.asyncio
async def test_await_background_tasks_logs_exceptions() -> None:
    import koel.poller as poller_mod

    poller = _poller()

    async def boom() -> None:
        raise RuntimeError("bg boom")

    task = asyncio.create_task(boom())
    poller._pdf_enrich_tasks.add(task)
    with patch.object(poller_mod.log, "warning") as warning:
        await poller.await_pdf_enrichment()
    warning.assert_any_call(
        "poller_background_task_error",
        kind="pdf_enrich",
        error="bg boom",
    )


@pytest.mark.asyncio
async def test_run_once_logs_poll_deliver_failed() -> None:
    import koel.poller as poller_mod

    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(return_value=True)
    storage.advisory_unlock = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=[])
    storage.claim_unsent_batch = AsyncMock(return_value=[])
    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(return_value=[])
    poller = _poller(storage=storage, cse=cse)
    poller._deliver_pending = AsyncMock(side_effect=RuntimeError("deliver boom"))  # type: ignore[method-assign]
    with patch.object(poller_mod.log, "exception") as exc_log:
        await poller.run_once(force=True)
    exc_log.assert_any_call("poll_deliver_failed", error="deliver boom")


@pytest.mark.asyncio
async def test_retry_unsent_with_lock_logs_offhours_failure() -> None:
    import koel.poller as poller_mod

    poller = _poller()
    poller._retry_unsent = AsyncMock(side_effect=RuntimeError("retry boom"))  # type: ignore[method-assign]
    with patch.object(poller_mod.log, "exception") as exc_log:
        await poller._retry_unsent_with_lock()
    exc_log.assert_any_call("offhours_retry_failed", error="retry boom")


def test_remember_delivered_bounds_memory() -> None:
    poller = _poller()
    poller._delivered_ok_ids = set(range(10_001))
    poller._remember_delivered(99_999)
    # 10001 → +1 → 10002, then pop 5000 → 5002
    assert len(poller._delivered_ok_ids) == 5_002
    assert 99_999 in poller._delivered_ok_ids


def test_load_delivery_ok_ledger_noop_when_path_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(DELIVERY_OK_LEDGER_ENV, "")
    poller = _poller()
    assert poller._delivery_ok_ledger_path is None
    poller._load_delivery_ok_ledger()  # early return


def test_load_delivery_ok_ledger_handles_read_errors_and_bad_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import koel.poller as poller_mod

    ledger = tmp_path / "ok.jsonl"
    ledger.write_text(
        "\n"
        "not-json\n"
        + json.dumps({"token": ""})
        + "\n"
        + json.dumps({"token": 12})
        + "\n"
        + json.dumps({"token": "keep-me", "id": 1})
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(DELIVERY_OK_LEDGER_ENV, str(ledger))
    with patch.object(poller_mod.log, "warning") as warning:
        poller = _poller()
    assert "keep-me" in poller._delivered_ok_tokens
    warning.assert_any_call("delivery_ok_ledger_bad_line", path=str(ledger))

    # Non-FileNotFoundError on read → exception path.
    bad = tmp_path / "unreadable.jsonl"
    bad.write_text("{}", encoding="utf-8")
    monkeypatch.setenv(DELIVERY_OK_LEDGER_ENV, str(bad))
    with (
        patch.object(Path, "read_text", side_effect=PermissionError("denied")),
        patch.object(poller_mod.log, "exception") as exc_log,
    ):
        _poller()
    exc_log.assert_any_call("delivery_ok_ledger_load_failed", path=str(bad))


@pytest.mark.asyncio
async def test_durably_remember_skips_rewrite_when_token_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = tmp_path / "ok.jsonl"
    monkeypatch.setenv(DELIVERY_OK_LEDGER_ENV, str(ledger))
    poller = _poller()
    pending = _pending(log_id=7, message="hello")
    t1 = await poller._durably_remember_delivery_ok(pending, event_key="k")
    size_after_first = ledger.stat().st_size
    t2 = await poller._durably_remember_delivery_ok(pending, event_key="k")
    assert t1 == t2
    assert ledger.stat().st_size == size_after_first


@pytest.mark.asyncio
async def test_durably_remember_and_forget_without_ledger_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(DELIVERY_OK_LEDGER_ENV, "")
    poller = _poller()
    pending = _pending(log_id=8, message="no-path")
    token = await poller._durably_remember_delivery_ok(pending, event_key=None)
    assert token in poller._delivery_ok_records
    await poller._forget_durable_delivery_ok(token)
    assert token not in poller._delivery_ok_records


@pytest.mark.asyncio
async def test_durably_remember_and_forget_log_write_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import koel.poller as poller_mod

    # Point ledger at a directory so open("a") fails.
    blocked = tmp_path / "blocked_dir"
    blocked.mkdir()
    monkeypatch.setenv(DELIVERY_OK_LEDGER_ENV, str(blocked))
    poller = _poller()
    pending = _pending(log_id=9, message="write-fail")
    with patch.object(poller_mod.log, "exception") as exc_log:
        await poller._durably_remember_delivery_ok(pending, event_key="ek")
    exc_log.assert_any_call(
        "delivery_ok_ledger_write_failed",
        alert_log_id=9,
        rule_id=1,
        event_key="ek",
        path=str(blocked),
    )

    poller._delivered_ok_tokens.add("tok-x")
    with patch.object(poller_mod.log, "exception") as exc_log:
        await poller._forget_durable_delivery_ok("tok-x")
    exc_log.assert_any_call("delivery_ok_ledger_forget_failed", path=str(blocked))


@pytest.mark.asyncio
async def test_poll_prices_general_exception_clears_missing() -> None:
    import koel.poller as poller_mod

    storage = AsyncMock()
    storage.watched_symbols = AsyncMock(return_value=["JKH.N0000"])
    cse = AsyncMock()
    cse.fetch_trade_summary = AsyncMock(side_effect=RuntimeError("html error page"))
    poller = _poller(storage=storage, cse=cse)
    poller.watched_missing = ["STALE"]
    with patch.object(poller_mod.log, "exception") as exc_log:
        events, ok = await poller._poll_prices()
    assert events == []
    assert ok is False
    assert poller.watched_missing == []
    assert poller.trade_summary_count is None
    assert poller.trade_summary_empty_ok is False
    exc_log.assert_any_call("price_poll_failed", error="html error page")


@pytest.mark.asyncio
async def test_evaluate_price_snaps_rearm_and_claim_conflict() -> None:
    """Rearm calls set_rule_armed; claim conflict skips fire list."""
    rule_rearm = make_rule(type=AlertType.PRICE_ABOVE, threshold=100.0, armed=False)
    snap_rearm = PriceSnapshot(
        symbol="JKH.N0000",
        price=95.0,
        previous_close=98.0,
        ts=datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
        id=10,
    )
    storage = AsyncMock()
    storage.get_previous_state = AsyncMock(return_value=PreviousPriceState(price=105.0))
    storage.set_rule_armed = AsyncMock()
    storage.claim_and_disarm = AsyncMock(return_value=None)
    storage.claim_alert = AsyncMock(return_value=None)
    poller = _poller(storage=storage)

    fired = await poller._evaluate_price_snaps(
        [snap_rearm],
        rules_by_symbol={"JKH.N0000": [rule_rearm]},
    )
    assert fired == []
    storage.set_rule_armed.assert_awaited_once_with(rule_rearm.id, True)

    # Armed cross + claim conflict → continue (no fire).
    rule_fire = make_rule(id=2, type=AlertType.PRICE_ABOVE, threshold=100.0, armed=True)
    snap_fire = snap_rearm.model_copy(update={"price": 105.0, "id": 11})
    storage.get_previous_state = AsyncMock(return_value=PreviousPriceState(price=95.0))
    storage.claim_and_disarm = AsyncMock(return_value=None)
    fired2 = await poller._evaluate_price_snaps(
        [snap_fire],
        rules_by_symbol={"JKH.N0000": [rule_fire]},
    )
    assert fired2 == []
    storage.claim_and_disarm.assert_awaited()


@pytest.mark.asyncio
async def test_fetch_disclosures_bulk_skips_empty_names_and_unmatched() -> None:
    storage = AsyncMock()
    storage.list_stock_names = AsyncMock(
        return_value=[
            ("JKH.N0000", "JOHN KEELLS HOLDINGS PLC"),
            ("OUT.N0000", "OUT OF WATCHLIST PLC"),
            ("EMPTY.N0000", ""),
            ("JKH.N0000", None),
        ]
    )
    cse = AsyncMock()
    cse.fetch_approved_announcements = AsyncMock(
        return_value=[
            AnnouncementRow(
                announcementId=1,
                company="UNKNOWN CO PLC",
                symbol=None,
                createdDate=1_700_000_000_000,
            ),
            AnnouncementRow(
                announcementId=2,
                company="JOHN KEELLS HOLDINGS PLC",
                symbol=None,
                announcementCategory="CORPORATE DISCLOSURE",
                remarks="Board",
                createdDate=1_700_000_000_000,
            ),
        ]
    )
    poller = _poller(storage=storage, cse=cse, disclosure_bulk_feed=True)
    fetched, covered, ok = await poller._fetch_disclosures_bulk(["JKH.N0000", "EMPTY.N0000"])
    assert ok is True
    assert "JKH.N0000" in covered
    assert "OUT.N0000" not in covered
    assert any(d.external_id == "2" for d in fetched.get("JKH.N0000", []))


@pytest.mark.asyncio
async def test_deliver_one_uses_event_symbol_when_pending_symbol_missing() -> None:
    storage = AsyncMock()
    storage.mark_delivery_attempted_ok = AsyncMock()
    storage.mark_alert_sent = AsyncMock()
    send = AsyncMock(return_value=SendResult.FAILED)
    storage.mark_alert_attempt = AsyncMock(return_value=1)
    event = AlertEvent(
        rule_id=1,
        user_id=2,
        telegram_id=9,
        symbol="COMB.N0000",
        type=AlertType.PRICE_ABOVE,
        threshold=10.0,
        trigger="cross",
        current_price=11.0,
        event_key="k",
    )
    poller = _poller(storage=storage, send=send)
    await poller._deliver_one(
        _pending(
            log_id=55,
            message="no bell line",
            symbol=None,
            event=event,
        )
    )
    storage.mark_alert_attempt.assert_awaited_once_with(55)


@pytest.mark.asyncio
async def test_start_scheduler_registers_job() -> None:
    poller = _poller()
    scheduler = poller.start_scheduler()
    try:
        assert poller._scheduler is scheduler
        assert scheduler.get_job("cse_poll") is not None
    finally:
        scheduler.shutdown(wait=False)
        poller._scheduler = None


@pytest.mark.asyncio
async def test_shutdown_background_timeout_when_budget_already_spent() -> None:
    import koel.poller as poller_mod

    poller = _poller()

    async def never() -> None:
        await asyncio.sleep(60)

    task = asyncio.create_task(never())
    poller._pdf_enrich_tasks.add(task)
    with (
        patch("koel.poller.SHUTDOWN_TICK_TIMEOUT_SECONDS", 0),
        patch.object(poller_mod.log, "warning") as warning,
    ):
        await poller._drain_background_on_shutdown()
    warning.assert_any_call(
        "poller_shutdown_background_timeout",
        timeout_seconds=0,
        pdf_enrich=1,
        brief_drain=0,
    )
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_shutdown_logs_tick_and_background_errors() -> None:
    import koel.poller as poller_mod

    poller = _poller()

    async def boom_tick() -> None:
        await asyncio.sleep(0.01)
        raise RuntimeError("tick boom")

    poller._tick_task = asyncio.create_task(boom_tick())
    poller._drain_background_on_shutdown = AsyncMock(  # type: ignore[method-assign]
        side_effect=RuntimeError("bg drain boom")
    )
    with patch.object(poller_mod.log, "exception") as exc_log:
        await poller.shutdown()
    names = [c.args[0] for c in exc_log.call_args_list]
    assert "poller_shutdown_tick_error" in names
    assert "poller_shutdown_background_error" in names
    assert poller._background_closed is True


@pytest.mark.asyncio
async def test_run_poller_forever_health_loop_and_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Covers run_poller_forever + health update paths, then clean stop."""
    storage = AsyncMock()
    storage.health_check = AsyncMock(side_effect=[RuntimeError("db"), True])
    storage.count_pending_disclosure_briefs = AsyncMock(return_value=2)
    cse = AsyncMock()
    cse.circuit_metrics = MagicMock(return_value={"tradeSummary": {"state": "closed"}})
    send = AsyncMock()
    health = HealthState()

    started = asyncio.Event()
    orig_update = health.update

    def tracking_update(**kwargs: object) -> None:
        orig_update(**kwargs)
        started.set()

    health.update = tracking_update  # type: ignore[method-assign]

    monkeypatch.setenv(DELIVERY_OK_LEDGER_ENV, "")
    with (
        patch.object(Poller, "start_scheduler", return_value=MagicMock()),
        patch.object(Poller, "shutdown", new_callable=AsyncMock) as shutdown,
    ):
        task = asyncio.create_task(
            run_poller_forever(
                _settings(),
                storage,
                cse,
                send,
                health=health,
            )
        )
        await asyncio.wait_for(started.wait(), timeout=2.0)
        # Signal stop via SIGTERM handler registered by run_poller_forever.
        os.kill(os.getpid(), __import__("signal").SIGTERM)
        await asyncio.wait_for(task, timeout=2.0)
        shutdown.assert_awaited()

    assert "db_ok" in health.details
    assert "circuits" in health.details


@pytest.mark.asyncio
async def test_run_poller_forever_without_health_exits_on_stop() -> None:
    # Poller.__init__ creates `_stopping` first; `stop` is the second Event.
    events: list[asyncio.Event] = []

    class CaptureEvent(asyncio.Event):
        def __init__(self) -> None:
            super().__init__()
            events.append(self)

    with (
        patch("koel.poller.asyncio.Event", CaptureEvent),
        patch.object(Poller, "start_scheduler", return_value=MagicMock()),
        patch.object(Poller, "shutdown", new_callable=AsyncMock) as shutdown,
    ):
        task = asyncio.create_task(
            run_poller_forever(_settings(), AsyncMock(), AsyncMock(), AsyncMock(), health=None)
        )
        for _ in range(50):
            if len(events) >= 2:
                break
            await asyncio.sleep(0.01)
        assert len(events) >= 2
        events[1].set()  # run_poller_forever's `stop`
        await asyncio.wait_for(task, timeout=2.0)
        shutdown.assert_awaited()
