"""Market-hours polling loop (09:30–14:30 Asia/Colombo, weekdays).

Fetches price + disclosure data via adapters, stores every snapshot, evaluates
rules, claims alerts idempotently, and dispatches Telegram sends.
"""

from __future__ import annotations

import asyncio
import contextlib
import random
import signal
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from chime.adapters.cse import CSEClient
from chime.circuit import CircuitOpenError
from chime.config import Settings
from chime.domain import AlertEvent, PriceSnapshot, format_alert_message
from chime.logging_setup import get_logger
from chime.rules import evaluate_disclosure_rules, evaluate_price_rules, filter_fireable
from chime.storage import Storage

log = get_logger(__name__)

SendFunc = Callable[[int, str], Awaitable[bool]]
POLL_LOCK_ID = 4_201_337
# After this many failed Telegram sends, stop retrying (message_sent stays false).
MAX_SEND_ATTEMPTS = 5


def parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def is_market_open(now: datetime, settings: Settings) -> bool:
    tz = ZoneInfo(settings.market_tz)
    local = now.astimezone(tz)
    if local.weekday() >= 5:
        return False
    open_t = parse_hhmm(settings.market_open)
    close_t = parse_hhmm(settings.market_close)
    return open_t <= local.time() <= close_t


class Poller:
    def __init__(
        self,
        settings: Settings,
        storage: Storage,
        cse: CSEClient,
        send: SendFunc,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.cse = cse
        self.send = send
        self._scheduler: AsyncIOScheduler | None = None
        self._stopping = asyncio.Event()
        self.last_tick_at: datetime | None = None
        self.last_tick_ok: bool = True
        self.last_error: str | None = None
        self.price_poll_ok: bool = True
        self.disclosure_poll_ok: bool = True
        self.lock_held_skip: bool = False

    async def run_once(self, *, force: bool = False) -> list[AlertEvent]:
        """Single poll cycle. Returns fireable events that were claimed+sent."""
        now = datetime.now(UTC)
        if not force and not is_market_open(now, self.settings):
            log.info("poll_skipped_outside_hours", now=now.isoformat())
            return []

        locked = await self.storage.try_advisory_lock(POLL_LOCK_ID)
        if not locked:
            log.info("poll_skipped_lock_held")
            self.lock_held_skip = True
            self.last_tick_ok = False
            self.last_error = "poll_lock_held"
            self.last_tick_at = datetime.now(UTC)
            return []

        self.lock_held_skip = False
        fired: list[AlertEvent] = []
        try:
            price_events, price_ok = await self._poll_prices()
            disc_events, disc_ok = await self._poll_disclosures()
            fired.extend(price_events)
            fired.extend(disc_events)
            await self._retry_unsent()
            self.price_poll_ok = price_ok
            self.disclosure_poll_ok = disc_ok
            symbols = await self.storage.watched_symbols()
            rules = await self.storage.active_rules_for_symbols(symbols) if symbols else []
            needs_disclosure = any(r.type.value == "disclosure" for r in rules)
            ok = True
            if symbols and not price_ok:
                ok = False
            if needs_disclosure and not disc_ok:
                ok = False
            self.last_tick_ok = ok
            if not ok:
                self.last_error = "poll_degraded"
            else:
                self.last_error = None
        except Exception as exc:
            self.last_tick_ok = False
            self.last_error = str(exc)
            log.exception("poll_cycle_failed", error=str(exc))
        finally:
            self.last_tick_at = datetime.now(UTC)
            await self.storage.advisory_unlock(POLL_LOCK_ID)
        return fired

    async def _poll_prices(self) -> tuple[list[AlertEvent], bool]:
        symbols = await self.storage.watched_symbols()
        if not symbols:
            log.info("poll_no_watchlist")
            return [], True

        try:
            all_snaps = await self.cse.fetch_trade_summary()
        except CircuitOpenError:
            log.error("price_poll_circuit_open")
            return [], False
        except Exception as exc:
            log.exception("price_poll_failed", error=str(exc))
            return [], False

        wanted = set(symbols)
        snaps = [s for s in all_snaps if s.symbol in wanted]
        rules = await self.storage.active_rules_for_symbols(list(wanted))
        rules_by_symbol: dict[str, list[Any]] = {}
        for rule in rules:
            rules_by_symbol.setdefault(rule.symbol, []).append(rule)

        return await self._evaluate_price_snaps(snaps, rules_by_symbol), True

    async def _evaluate_price_snaps(
        self,
        snaps: list[PriceSnapshot],
        rules_by_symbol: dict[str, list[Any]],
    ) -> list[AlertEvent]:
        fired: list[AlertEvent] = []
        for snap in snaps:
            stored = await self.storage.insert_snapshot(snap)
            assert stored.id is not None
            previous = await self.storage.get_previous_state(stored.symbol, before_id=stored.id)
            symbol_rules = rules_by_symbol.get(stored.symbol, [])
            events = evaluate_price_rules(
                snapshot=stored,
                previous=previous,
                rules=symbol_rules,
            )
            for event in events:
                if event.trigger == "rearm" and event.set_armed is True:
                    await self.storage.set_rule_armed(event.rule_id, True)
            # Claim BEFORE disarm so a crash cannot lose the alert forever
            for event in filter_fireable(events):
                t0 = datetime.now(UTC)
                claimed = await self._claim_and_send(event)
                if not claimed:
                    continue
                # Disarm after successful claim (even if Telegram send failed /
                # left message_sent=False). Crossing is consumed; unsent retry
                # delivers. Keeps armed state aligned with claim semantics.
                if event.set_armed is False:
                    await self.storage.set_rule_armed(event.rule_id, False)
                latency_ms = (datetime.now(UTC) - t0).total_seconds() * 1000
                log.info(
                    "alert_latency_ms",
                    rule_id=event.rule_id,
                    latency_ms=round(latency_ms, 1),
                    event_key=event.event_key,
                )
                fired.append(event)
        return fired

    async def _poll_disclosures(self) -> tuple[list[AlertEvent], bool]:
        symbols = await self.storage.watched_symbols()
        if not symbols:
            return [], True
        rules = await self.storage.active_rules_for_symbols(symbols)
        disclosure_rules = [r for r in rules if r.type.value == "disclosure"]
        # Only hit CSE announcements for symbols with active disclosure rules
        # (price-only watchlist symbols skip this leg — rate-limit priority).
        disclosure_symbols = sorted({r.symbol for r in disclosure_rules})
        if not disclosure_symbols:
            return [], True

        tz = ZoneInfo(self.settings.market_tz)
        today = datetime.now(tz).date()
        from_date = (today - timedelta(days=365)).isoformat()
        to_date = today.isoformat()
        fired: list[AlertEvent] = []
        any_failure = False

        for symbol in disclosure_symbols:
            try:
                disclosures = await self.cse.fetch_announcements_for_symbol(
                    symbol, from_date=from_date, to_date=to_date
                )
            except Exception as exc:
                any_failure = True
                log.warning("disclosure_poll_failed", symbol=symbol, error=str(exc))
                continue

            symbol_rules = [r for r in disclosure_rules if r.symbol == symbol]
            for disc in disclosures:
                inserted = await self.storage.insert_disclosure_if_new(disc)
                if inserted is None:
                    continue
                # Historical rows are filtered by rule.created_at in the engine
                events = evaluate_disclosure_rules(disclosure=inserted, rules=symbol_rules)
                for event in filter_fireable(events):
                    claimed = await self._claim_and_send(event)
                    if claimed:
                        fired.append(event)
            await asyncio.sleep(0.15 + random.random() * 0.2)
        return fired, not any_failure

    async def _record_send_failure(self, alert_log_id: int, *, rule_id: int | None = None) -> None:
        attempts = await self.storage.mark_alert_attempt(alert_log_id)
        if attempts >= MAX_SEND_ATTEMPTS:
            await self.storage.dead_letter(alert_log_id)
            log.warning(
                "alert_dead_lettered",
                alert_log_id=alert_log_id,
                rule_id=rule_id,
                attempts=attempts,
            )
        else:
            log.warning(
                "alert_send_failed",
                alert_log_id=alert_log_id,
                rule_id=rule_id,
                attempts=attempts,
            )

    async def _claim_and_send(self, event: AlertEvent) -> bool:
        message = format_alert_message(event)
        log_id = await self.storage.claim_alert(event, message)
        if log_id is None:
            log.info("alert_already_claimed", event_key=event.event_key, rule_id=event.rule_id)
            return False
        ok = await self.send(event.telegram_id, message)
        if ok:
            await self.storage.mark_alert_sent(log_id)
            log.info("alert_sent", rule_id=event.rule_id, event_key=event.event_key)
            return True
        await self._record_send_failure(log_id, rule_id=event.rule_id)
        return False

    async def _retry_unsent(self) -> None:
        pending = await self.storage.unsent_alerts()
        for row in pending:
            text = row["message_text"] or ""
            log_id = int(row["id"])
            ok = await self.send(int(row["telegram_id"]), text)
            if ok:
                await self.storage.mark_alert_sent(log_id)
            else:
                await self._record_send_failure(log_id, rule_id=int(row["rule_id"]))

    async def _scheduled_tick(self) -> None:
        jitter = random.uniform(0, self.settings.poll_jitter_seconds)
        await asyncio.sleep(jitter)
        await self.run_once()

    def start_scheduler(self) -> AsyncIOScheduler:
        tz = ZoneInfo(self.settings.market_tz)
        scheduler = AsyncIOScheduler(timezone=tz)
        scheduler.add_job(
            self._scheduled_tick,
            IntervalTrigger(seconds=self.settings.poll_interval_seconds, timezone=tz),
            id="cse_poll",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=30,
        )
        scheduler.start()
        self._scheduler = scheduler
        log.info(
            "poller_started",
            interval=self.settings.poll_interval_seconds,
            tz=self.settings.market_tz,
        )
        return scheduler

    async def shutdown(self) -> None:
        self._stopping.set()
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
        log.info("poller_stopped")


async def run_poller_forever(
    settings: Settings,
    storage: Storage,
    cse: CSEClient,
    send: SendFunc,
    *,
    health: Any | None = None,
) -> None:
    poller = Poller(settings, storage, cse, send)
    poller.start_scheduler()

    stop = asyncio.Event()

    def _handle_sig(*_: object) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _handle_sig)

    async def _health_loop() -> None:
        if health is None:
            return
        while not stop.is_set():
            db_ok = False
            try:
                db_ok = await storage.health_check()
            except Exception as exc:
                log.warning("health_db_failed", error=str(exc))
            tick_ok = poller.last_tick_ok
            health.update(
                ok=db_ok and tick_ok,
                db_ok=db_ok,
                last_tick_at=poller.last_tick_at.isoformat() if poller.last_tick_at else None,
                last_tick_ok=tick_ok,
                price_poll_ok=poller.price_poll_ok,
                disclosure_poll_ok=poller.disclosure_poll_ok,
                lock_held_skip=poller.lock_held_skip,
                last_error=poller.last_error,
            )
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=10)

    health_task = asyncio.create_task(_health_loop())
    try:
        await stop.wait()
    finally:
        health_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await health_task
        await poller.shutdown()
