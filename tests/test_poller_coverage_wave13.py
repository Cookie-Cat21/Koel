"""Wave13: unit coverage push for remaining poller.py partial branches."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from koel.adapters.cse import AnnouncementRow, LegacyAnnouncementRow
from koel.config import Settings
from koel.domain import AlertEvent, AlertType
from koel.health import HealthState
from koel.poller import PendingPdfEnrich, PendingSend, Poller, run_poller_forever


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


def _pending(**kwargs: object) -> PendingSend:
    base: dict[str, object] = dict(
        log_id=1,
        telegram_id=9,
        message="body",
        already_claimed_new=True,
        rule_id=1,
        event=None,
        symbol="JKH.N0000",
    )
    base.update(kwargs)
    return PendingSend(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_fetch_disclosures_bulk_skips_ambiguous_name_map() -> None:
    """Ambiguous company names are not pre-covered (mapped != sym)."""
    storage = AsyncMock()
    storage.list_stock_names = AsyncMock(
        return_value=[
            ("JKH.N0000", "SAME NAME PLC"),
            ("COMB.N0000", "SAME NAME PLC"),
        ]
    )
    cse = AsyncMock()
    cse.fetch_approved_announcements = AsyncMock(return_value=[])
    poller = _poller(storage=storage, cse=cse, disclosure_bulk_feed=True)
    fetched, covered, ok = await poller._fetch_disclosures_bulk(
        ["JKH.N0000", "COMB.N0000"]
    )
    assert ok is True
    assert covered == set()
    assert fetched == {}


@pytest.mark.asyncio
async def test_fetch_disclosures_bulk_skips_null_disclosure_rows() -> None:
    """Resolved rows that cannot become Disclosure are dropped (disc is None)."""
    storage = AsyncMock()
    storage.list_stock_names = AsyncMock(
        return_value=[("JKH.N0000", "JOHN KEELLS HOLDINGS PLC")]
    )
    cse = AsyncMock()
    cse.fetch_approved_announcements = AsyncMock(
        return_value=[
            AnnouncementRow(
                announcementId=None,
                id=None,
                company="JOHN KEELLS HOLDINGS PLC",
                symbol="JKH.N0000",
                createdDate=1_700_000_000_000,
            ),
        ]
    )
    poller = _poller(storage=storage, cse=cse, disclosure_bulk_feed=True)
    fetched, covered, ok = await poller._fetch_disclosures_bulk(["JKH.N0000"])
    assert ok is True
    assert "JKH.N0000" in covered
    assert fetched.get("JKH.N0000") == []


@pytest.mark.asyncio
async def test_drain_briefs_safe_silent_when_zero_processed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import koel.poller as poller_mod

    poller = _poller()
    monkeypatch.setattr(poller_mod, "claim_pending_briefs", AsyncMock(return_value=0))
    with patch.object(poller_mod.log, "info") as info:
        await poller._drain_briefs_safe()
    assert not any(c.args and c.args[0] == "brief_drain_done" for c in info.call_args_list)


@pytest.mark.asyncio
async def test_enrich_disclosure_pdfs_skips_when_set_url_returns_false() -> None:
    storage = AsyncMock()
    storage.set_disclosure_pdf_url = AsyncMock(return_value=False)
    cse = AsyncMock()
    cse.fetch_legacy_announcements = AsyncMock(
        return_value=[
            LegacyAnnouncementRow(
                announcementId=99,
                filePath="uploadAnnounceFiles/a.pdf",
            )
        ]
    )
    poller = _poller(storage=storage, cse=cse)
    import koel.poller as poller_mod

    with patch.object(poller_mod.log, "info") as info:
        await poller._enrich_disclosure_pdfs(
            [
                PendingPdfEnrich(
                    disclosure_id=55,
                    symbol="JKH.N0000",
                    external_id="99",
                )
            ]
        )
    storage.set_disclosure_pdf_url.assert_awaited_once()
    assert not any(
        c.args and c.args[0] == "disclosure_pdf_url_set" for c in info.call_args_list
    )


@pytest.mark.asyncio
async def test_ready_filing_brief_disclosure_without_disclosure_prefix() -> None:
    storage = AsyncMock()
    storage.get_ready_filing_brief = AsyncMock(return_value="brief text")
    poller = _poller(storage=storage)
    event = AlertEvent(
        rule_id=1,
        user_id=2,
        telegram_id=9,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        threshold=None,
        trigger="new disclosure",
        current_price=None,
        disclosure_title="AGM",
        disclosure_url="https://www.cse.lk/announcements#1",
        disclosure_id=55,
        event_key="odd-key:1:55",
    )
    out = await poller._ready_filing_brief_for(event)
    assert out == "brief text"
    storage.get_ready_filing_brief.assert_awaited_once_with(
        disclosure_id=55,
        external_id=None,
        symbol="JKH.N0000",
    )


@pytest.mark.asyncio
async def test_ready_filing_brief_malformed_event_key_parts() -> None:
    storage = AsyncMock()
    storage.get_ready_filing_brief = AsyncMock(return_value=None)
    poller = _poller(storage=storage)
    event = AlertEvent(
        rule_id=1,
        user_id=2,
        telegram_id=9,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        threshold=None,
        trigger="new disclosure",
        current_price=None,
        disclosure_title="AGM",
        disclosure_url="https://www.cse.lk/announcements#1",
        disclosure_id=55,
        event_key="disclosure:1:",
    )
    assert await poller._ready_filing_brief_for(event) is None
    storage.get_ready_filing_brief.assert_awaited_once_with(
        disclosure_id=55,
        external_id=None,
        symbol="JKH.N0000",
    )


@pytest.mark.asyncio
async def test_deliver_one_ignores_unknown_send_result() -> None:
    """Non-enum send results fall through OK/FAILED/DEFERRED without recording."""
    storage = AsyncMock()
    send = AsyncMock(return_value="not-a-send-result")  # type: ignore[arg-type]
    poller = _poller(storage=storage, send=send)
    await poller._deliver_one(_pending())
    storage.mark_alert_attempt.assert_not_awaited()
    storage.mark_alert_sent.assert_not_awaited()
    storage.mark_delivery_attempted_ok.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_unsent_stops_after_max_claims() -> None:
    storage = AsyncMock()
    row = {
        "id": 7,
        "telegram_id": 9,
        "message_text": "🔔 JKH.N0000\nbody",
        "rule_id": 1,
    }
    storage.claim_unsent_batch = AsyncMock(return_value=[row])
    poller = _poller(storage=storage)
    poller._deliver_one = AsyncMock()  # type: ignore[method-assign]
    with patch("koel.poller.RETRY_UNSENT_MAX", 3):
        await poller._retry_unsent()
    assert storage.claim_unsent_batch.await_count == 3
    assert poller._deliver_one.await_count == 3


@pytest.mark.asyncio
async def test_scheduled_tick_does_not_clear_replaced_tick_task() -> None:
    poller = _poller(settings=_settings(poll_jitter_seconds=0.01))
    poller.run_once = AsyncMock(return_value=[])  # type: ignore[method-assign]
    replaced = object()

    async def swap_tick(_delay: float = 0) -> None:
        poller._tick_task = replaced  # type: ignore[assignment]

    with patch("koel.poller.asyncio.sleep", swap_tick):
        await poller._scheduled_tick()
    assert poller._tick_task is replaced


@pytest.mark.asyncio
async def test_run_poller_forever_health_loop_while_exit_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover ``while not stop`` exit after one iteration (not cancel mid-wait).

    ``run_poller_forever`` cancels the health task as soon as ``stop`` is set,
    which races the while re-check. Wrap the health task so ``cancel()`` is a
    no-op and the loop can leave the while naturally after wait_for.
    """
    storage = AsyncMock()
    storage.health_check = AsyncMock(return_value=True)
    storage.count_pending_disclosure_briefs = AsyncMock(return_value=1)
    cse = AsyncMock()
    cse.circuit_metrics = MagicMock(return_value={})
    health = HealthState()
    stop_events: list[asyncio.Event] = []

    class CaptureEvent(asyncio.Event):
        def __init__(self) -> None:
            super().__init__()
            stop_events.append(self)

    real_create_task = asyncio.create_task
    wrapped: dict[str, asyncio.Task[object]] = {}

    def tracking_create(coro: object, **kwargs: object) -> object:
        real = real_create_task(coro, **kwargs)  # type: ignore[arg-type]
        wrapped["task"] = real

        class CancelProof:
            def cancel(self, *_a: object, **_k: object) -> bool:
                return False

            def __await__(self):  # noqa: ANN204
                return real.__await__()

            def __getattr__(self, name: str) -> object:
                return getattr(real, name)

        return CancelProof()

    real_wait_for = asyncio.wait_for

    async def fast_wait_for(aw: object, timeout: object = None) -> object:
        # Health loop uses timeout=10; do not swallow the test's outer wait_for.
        if timeout == 10 and stop_events:
            stop_events[-1].set()
            close = getattr(aw, "close", None)
            if callable(close):
                close()
            return None
        return await real_wait_for(aw, timeout=timeout)  # type: ignore[arg-type]

    monkeypatch.setattr("koel.poller.asyncio.Event", CaptureEvent)
    monkeypatch.setattr("koel.poller.asyncio.create_task", tracking_create)
    monkeypatch.setattr("koel.poller.asyncio.wait_for", fast_wait_for)

    with (
        patch.object(Poller, "start_scheduler", return_value=MagicMock()),
        patch.object(Poller, "shutdown", new_callable=AsyncMock) as shutdown,
    ):
        await asyncio.wait_for(
            run_poller_forever(
                _settings(),
                storage,
                cse,
                AsyncMock(),
                health=health,
            ),
            timeout=2.0,
        )
        shutdown.assert_awaited()

    assert health.details.get("db_ok") is True
    assert wrapped["task"].done()


@pytest.mark.asyncio
async def test_run_poller_forever_health_non_callable_circuits_and_empty_brief_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = AsyncMock()
    storage.health_check = AsyncMock(return_value=True)
    # No count_pending_disclosure_briefs → empty brief_queue hint when pdf
    # counters are suppressed.
    del storage.count_pending_disclosure_briefs
    cse = AsyncMock()
    cse.circuit_metrics = "not-callable"
    health = HealthState()
    started = asyncio.Event()
    orig_update = health.update

    def tracking_update(**kwargs: object) -> None:
        orig_update(**kwargs)
        if "circuits" in kwargs:
            started.set()

    health.update = tracking_update  # type: ignore[method-assign]

    async def empty_brief_queue(**_kwargs: object) -> dict[str, object]:
        return {}

    monkeypatch.setattr("koel.poller.brief_queue_health_hint", empty_brief_queue)

    with (
        patch.object(Poller, "start_scheduler", return_value=MagicMock()),
        patch.object(Poller, "shutdown", new_callable=AsyncMock),
    ):
        task = asyncio.create_task(
            run_poller_forever(_settings(), storage, cse, AsyncMock(), health=health)
        )
        await asyncio.wait_for(started.wait(), timeout=2.0)
        # Stop via the signal handler path.
        import os
        import signal

        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(task, timeout=2.0)

    assert health.details.get("circuits") == {}
    assert "brief_queue" not in health.details


@pytest.mark.asyncio
async def test_run_poller_forever_health_rejects_non_dict_circuit_metrics() -> None:
    storage = AsyncMock()
    storage.health_check = AsyncMock(return_value=True)
    storage.count_pending_disclosure_briefs = AsyncMock(return_value=1)
    cse = AsyncMock()
    cse.circuit_metrics = MagicMock(return_value=["not", "a", "dict"])
    health = HealthState()
    started = asyncio.Event()
    orig_update = health.update

    def tracking_update(**kwargs: object) -> None:
        orig_update(**kwargs)
        if "circuits" in kwargs:
            started.set()

    health.update = tracking_update  # type: ignore[method-assign]

    with (
        patch.object(Poller, "start_scheduler", return_value=MagicMock()),
        patch.object(Poller, "shutdown", new_callable=AsyncMock),
    ):
        task = asyncio.create_task(
            run_poller_forever(_settings(), storage, cse, AsyncMock(), health=health)
        )
        await asyncio.wait_for(started.wait(), timeout=2.0)
        import os
        import signal

        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(task, timeout=2.0)

    assert health.details.get("circuits") == {}
