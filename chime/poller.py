"""Market-hours polling loop (09:30–14:30 Asia/Colombo, weekdays).

Fetches price + disclosure data via adapters, stores every snapshot, evaluates
rules, claims alerts idempotently, and dispatches Telegram sends.

CORE-004: advisory lock covers fetch/store/evaluate/claim/disarm only.
Telegram sends and disclosure inter-symbol sleeps run after unlock.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import math
import os
import random
import signal
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from chime.adapters.cse import (
    CSEClient,
    announcement_to_disclosure,
    build_unique_company_name_map,
    legacy_pdf_urls_by_id,
    normalize_company_name,
    resolve_announcement_symbol,
)
from chime.briefs import briefs_enabled
from chime.briefs.worker import claim_pending_briefs
from chime.circuit import CircuitOpenError
from chime.config import Settings
from chime.domain import (
    MARKET_REGIME_ALERT_TYPES,
    MARKET_SYMBOL,
    AlertEvent,
    AlertRule,
    AlertType,
    Disclosure,
    PriceSnapshot,
    format_alert_message,
    format_dead_letter_notify,
)
from chime.health import brief_queue_health_hint
from chime.logging_setup import get_logger
from chime.macro_alerts import evaluate_market_regime_rules
from chime.notify import SendResult
from chime.rules import (
    evaluate_big_print_rules,
    evaluate_disclosure_rules,
    evaluate_xd_digest_rules,
    evaluate_xd_soon_rules,
    evaluate_notice_rules,
    evaluate_order_book_rules,
    evaluate_price_rules,
    filter_fireable,
)
from chime.storage import Storage

log = get_logger(__name__)

# bool kept for test AsyncMocks; production send returns SendResult.
SendFunc = Callable[[int, str], Awaitable[SendResult | bool]]
# Session try-lock for the CSE poll tick. Distinct from storage.BRIEF_CAP_LOCK_ID
# (4_201_339) — do not unify; see docs/factory/passes/ADVISORY_LOCK_DEADLOCK.md.
POLL_LOCK_ID = 4_201_337
# After this many failed Telegram sends, stop retrying (message_sent stays false).
MAX_SEND_ATTEMPTS = 5
# After this many deferred (RetryAfter) sends, stop retrying — same attempt_count
# column, higher ceiling so transient flood-waits are not dead-lettered early.
MAX_DEFERRED_ATTEMPTS = 30
# Persist delivery_attempted_ok this many times before abandoning to memory + DL.
MARK_DELIVERY_OK_ATTEMPTS = 3
# Cap one-at-a-time unsent claims per drain (lease starts just before each send).
RETRY_UNSENT_MAX = 50
# Fsync'd local Telegram-OK ledger. Covers restart after total post-send DB write failure.
DELIVERY_OK_LEDGER_ENV = "CHIME_DELIVERY_OK_LEDGER"
# Max time shutdown waits for an in-flight scheduled tick (CORE-005 / E2-C02).
SHUTDOWN_TICK_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class PendingSend:
    """Claimed alert awaiting Telegram delivery (outside the advisory lock)."""

    log_id: int
    telegram_id: int
    message: str
    already_claimed_new: bool
    rule_id: int | None = None
    event: AlertEvent | None = None
    symbol: str | None = None


@dataclass(frozen=True)
class PendingPdfEnrich:
    """Disclosure awaiting optional legacy PDF URL enrichment (after unlock)."""

    disclosure_id: int
    symbol: str
    external_id: str


def _normalize_send_result(result: SendResult | bool) -> SendResult:
    """Map legacy bool send callbacks onto SendResult (False → failed)."""
    if isinstance(result, bool):
        return SendResult.OK if result else SendResult.FAILED
    return result


def _symbol_from_alert_message(message: object) -> str | None:
    """Best-effort parse of ``format_alert_message`` first line (``🔔 SYMBOL``)."""
    # Fail closed — non-strings used to throw on .split mid dead-letter notify.
    if not isinstance(message, str):
        return None
    first = message.split("\n", 1)[0].strip()
    if first.startswith("🔔"):
        symbol = first.removeprefix("🔔").strip()
        return symbol or None
    return None


def _delivery_ok_token(
    *,
    log_id: int,
    rule_id: int | None,
    telegram_id: int,
    message: object,
) -> str:
    # Fail closed — non-string message used to throw on .encode mid ledger token.
    msg = message if isinstance(message, str) else ""
    digest = hashlib.sha256(msg.encode("utf-8")).hexdigest()
    rule_part = "" if rule_id is None else str(rule_id)
    return f"{log_id}:{rule_part}:{telegram_id}:{digest}"


def parse_hhmm(value: object) -> time:
    # Fail closed — non-strings used to throw on .split mid market-hours gate.
    if not isinstance(value, str):
        raise ValueError("market open/close must be HH:MM string")
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


def _positive_int_setting(value: object) -> int:
    """Return positive int settings, rejecting bool and other soft-accepted types."""
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value if value > 0 else 0


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
        self.last_tick_ok: bool = False
        self.last_error: str | None = None
        self.price_poll_ok: bool = True
        self.disclosure_poll_ok: bool = True
        self.lock_held_skip: bool = False
        # Watched symbols absent from the latest tradeSummary (E2-C06).
        self.watched_missing: list[str] = []
        # Last tradeSummary shape: empty HTTP-OK with a non-empty watchlist is
        # operationally different from a partial symbol miss.
        self.trade_summary_count: int | None = None
        self.trade_summary_empty_ok: bool = False
        # When True, _claim_and_send queues PendingSend instead of sending inline
        # (set for the locked section of run_once).
        self._queue_sends: bool = False
        self._pending_sends: list[PendingSend] = []
        # In-flight scheduled tick (APScheduler job task). Awaited on shutdown.
        self._tick_task: asyncio.Task[Any] | None = None
        # Process-lifetime: Telegram-OK alert_log ids. Survives ticks so a
        # mark_alert_sent outage cannot re-push every poll (L08-001).
        self._delivered_ok_ids: set[int] = set()
        # Restart-lifetime: Telegram-OK signatures fsync'd before DB marks.
        self._delivery_ok_ledger_path = self._delivery_ok_ledger_path_from_env()
        self._delivered_ok_tokens: set[str] = set()
        self._delivery_ok_records: dict[str, dict[str, Any]] = {}
        self._load_delivery_ok_ledger()
        # Dead-letter user notification is best-effort and one-shot per process.
        self._dead_letter_notify_attempted_ids: set[int] = set()
        # Legacy PDF enrichment queued under lock; HTTP runs after unlock.
        self._pending_pdf_enrich: list[PendingPdfEnrich] = []
        self._pdf_enrich_tasks: set[asyncio.Task[Any]] = set()
        self._pdf_enrich_lock = asyncio.Lock()
        # Cheap ops counters for loopback health (wave3 brief_queue hint).
        self._pdf_enrich_last_batch_size: int = 0
        self._pdf_enrich_batches_started: int = 0
        self._brief_drain_tasks: set[asyncio.Task[Any]] = set()
        self._brief_drain_lock = asyncio.Lock()
        # After shutdown finishes draining background work, reject new schedules
        # so a shielded late tick cannot race storage.close() (wave4).
        self._background_closed = False

    def pdf_enrich_health_snapshot(self) -> dict[str, int]:
        """In-memory PDF enrich queue counters for health details."""
        return {
            "in_flight_tasks": len(self._pdf_enrich_tasks),
            "last_batch_size": self._pdf_enrich_last_batch_size,
            "batches_started": self._pdf_enrich_batches_started,
        }

    async def await_pdf_enrichment(self) -> None:
        """Drain in-flight PDF enrich tasks (tests / shutdown)."""
        await self._await_background_tasks(
            self._pdf_enrich_tasks,
            label="pdf_enrich",
        )

    async def await_brief_drain(self) -> None:
        """Drain in-flight brief worker tasks (tests / shutdown)."""
        await self._await_background_tasks(
            self._brief_drain_tasks,
            label="brief_drain",
        )

    async def _await_background_tasks(
        self,
        tasks: set[asyncio.Task[Any]],
        *,
        label: str,
    ) -> None:
        """Await a snapshot of background tasks; log (do not raise) failures."""
        pending = list(tasks)
        if not pending:
            return
        results = await asyncio.gather(*pending, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                log.warning(
                    "poller_background_task_error",
                    kind=label,
                    error=str(result),
                )

    async def run_once(self, *, force: bool = False) -> list[AlertEvent]:
        """Single poll cycle. Returns events claimed (delivered after unlock)."""
        now = datetime.now(UTC)
        if not force and not is_market_open(now, self.settings):
            log.info("poll_skipped_outside_hours", now=now.isoformat())
            # Delivery is independent of market hours — retry unsent backlog
            # so Telegram failures overnight/weekend still drain.
            await self._retry_unsent_with_lock()
            self.last_tick_at = datetime.now(UTC)
            self._schedule_brief_drain()
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
        pending: list[PendingSend] = []
        pdf_enrich: list[PendingPdfEnrich] = []
        self._queue_sends = True
        self._pending_sends = pending
        self._pending_pdf_enrich = pdf_enrich
        # Fail-closed defaults: if the cycle aborts mid-tick, health must not
        # keep stale True from a prior success (or cold-start defaults).
        price_ok = False
        disc_ok = False
        print_ok = False
        notice_ok = False
        book_ok = False
        try:
            self.last_error = None
            price_events, price_ok = await self._poll_prices()
            disc_events, disc_ok = await self._poll_disclosures()
            print_events, print_ok = await self._poll_big_prints()
            notice_events, notice_ok = await self._poll_market_notices()
            book_events, book_ok = await self._poll_order_books()
            # Postgres-only MARKET tape/context regime (fail-soft).
            regime_events, _regime_ok = await self._poll_market_regime()
            xd_events, _xd_ok = await self._poll_dividend_xd()
            await self._poll_indexes()
            await self._poll_sectors()
            fired.extend(price_events)
            fired.extend(disc_events)
            fired.extend(print_events)
            fired.extend(notice_events)
            fired.extend(book_events)
            fired.extend(regime_events)
            fired.extend(xd_events)
            symbols = await self.storage.watched_symbols()
            rules = await self.storage.active_rules_for_symbols(symbols) if symbols else []
            # Fail closed — non-enum rule.type used to throw on .value mid tick
            # health aggregation (poisoned row / hostile model_construct).
            needs_disclosure = any(
                getattr(r.type, "value", r.type) == "disclosure" for r in rules
            )
            ok = True
            # Market-wide persist is the browse foundation: degrade on price_ok
            # False even with an empty watchlist (fetch/persist/empty board).
            if not price_ok:
                ok = False
            if needs_disclosure and not disc_ok:
                ok = False
            # Activity legs are fail-soft for tick health unless rules exist.
            needs_prints = any(
                getattr(r.type, "value", r.type) == "big_print" for r in rules
            )
            needs_notices = any(
                getattr(r.type, "value", r.type)
                in {"buy_in", "non_compliance", "halt"}
                for r in rules
            )
            if needs_prints and not print_ok:
                ok = False
            if needs_notices and not notice_ok:
                ok = False
            needs_book = any(
                getattr(r.type, "value", r.type) in {"bid_heavy", "ask_heavy"}
                for r in rules
            )
            if needs_book and not book_ok:
                ok = False
            self.last_tick_ok = ok
            if not ok:
                if self.last_error is None:
                    self.last_error = "poll_degraded"
            else:
                self.last_error = None
        except Exception as exc:
            self.last_tick_ok = False
            self.last_error = str(exc)
            log.exception("poll_cycle_failed", error=str(exc))
        finally:
            self.price_poll_ok = price_ok
            self.disclosure_poll_ok = disc_ok
            self._queue_sends = False
            self.last_tick_at = datetime.now(UTC)
            await self.storage.advisory_unlock(POLL_LOCK_ID)

        # CORE-004: Telegram I/O for this tick's new claims after unlock.
        # E2-C05: unsent drain uses row leases (SKIP LOCKED) — no advisory
        # re-hold, so RetryAfter may sleep without pinning the poll lock.
        # PDF enrichment is fail-soft and rate-limited — never blocks alerts.
        try:
            await self._deliver_pending(pending)
            await self._retry_unsent_with_lock()
        except Exception as exc:
            log.exception("poll_deliver_failed", error=str(exc))
        self._schedule_pdf_enrichment(pdf_enrich)
        self._schedule_brief_drain()
        return fired

    async def _retry_unsent_with_lock(self) -> None:
        """Drain unsent without holding the poll advisory lock (E2-C05).

        ``claim_unsent_batch`` leases rows via FOR UPDATE SKIP LOCKED so
        concurrent pollers cannot double-send; Telegram RetryAfter sleeps
        safely outside any advisory hold. Method name kept for call sites.
        """
        try:
            await self._retry_unsent()
        except Exception as exc:
            log.exception("offhours_retry_failed", error=str(exc))

    def _remember_delivered(self, log_id: int) -> None:
        self._delivered_ok_ids.add(log_id)
        # Bound memory if mark_alert_sent stays broken for a long outage.
        if len(self._delivered_ok_ids) > 10_000:
            # Drop an arbitrary half (set pop is fine — ids are opaque).
            for _ in range(5_000):
                self._delivered_ok_ids.pop()

    def _delivery_ok_ledger_path_from_env(self) -> Path | None:
        raw = os.getenv(DELIVERY_OK_LEDGER_ENV)
        # Fail closed — non-string getenv mocks used to throw on .strip mid ledger path.
        if isinstance(raw, str):
            raw = raw.strip()
            return Path(raw) if raw else None
        if raw is not None:
            return None
        # Fail closed — non-string database_url used to throw on .encode mid ledger.
        db_url = self.settings.database_url
        if not isinstance(db_url, str) or not db_url:
            return None
        digest = hashlib.sha256(db_url.encode("utf-8")).hexdigest()[:16]
        return Path("/tmp/chime") / f"delivery-ok-{digest}.jsonl"

    def _load_delivery_ok_ledger(self) -> None:
        path = self._delivery_ok_ledger_path
        if path is None:
            return
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return
        except Exception:
            log.exception("delivery_ok_ledger_load_failed", path=str(path))
            return
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                log.warning("delivery_ok_ledger_bad_line", path=str(path))
                continue
            token = record.get("token")
            if not isinstance(token, str) or not token:
                continue
            if record.get("forget") is True:
                self._delivered_ok_tokens.discard(token)
                self._delivery_ok_records.pop(token, None)
                continue
            self._delivered_ok_tokens.add(token)
            self._delivery_ok_records[token] = record

    def _delivery_ok_token_for_pending(self, pending: PendingSend) -> str:
        return _delivery_ok_token(
            log_id=pending.log_id,
            rule_id=pending.rule_id,
            telegram_id=pending.telegram_id,
            message=pending.message,
        )

    @staticmethod
    def _append_ledger_record_blocking(path: Path, record: dict[str, Any]) -> None:
        """Blocking file write + fsync — run via ``asyncio.to_thread`` only.

        Durability (fsync before returning) is the point of this call, so it
        cannot be fire-and-forget — but the syscalls themselves can block for
        a long time under disk contention, so this must never run directly on
        the event loop thread.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())

    async def _durably_remember_delivery_ok(
        self,
        pending: PendingSend,
        *,
        event_key: str | None,
    ) -> str:
        """Fsync Telegram-OK before DB marks so restart cannot re-send."""
        token = self._delivery_ok_token_for_pending(pending)
        self._delivered_ok_tokens.add(token)
        if token in self._delivery_ok_records:
            return token
        # Fail closed — non-string pending.message used to throw on .encode.
        msg = pending.message if isinstance(pending.message, str) else ""
        record: dict[str, Any] = {
            "token": token,
            "id": pending.log_id,
            "rule_id": pending.rule_id,
            "telegram_id": pending.telegram_id,
            "message_sha256": hashlib.sha256(msg.encode("utf-8")).hexdigest(),
            "event_key": event_key,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        path = self._delivery_ok_ledger_path
        if path is None:
            self._delivery_ok_records[token] = record
            return token
        try:
            await asyncio.to_thread(self._append_ledger_record_blocking, path, record)
            self._delivery_ok_records[token] = record
        except Exception:
            log.exception(
                "delivery_ok_ledger_write_failed",
                alert_log_id=pending.log_id,
                rule_id=pending.rule_id,
                event_key=event_key,
                path=str(path),
            )
        return token

    async def _forget_durable_delivery_ok(self, token: str) -> None:
        self._delivered_ok_tokens.discard(token)
        self._delivery_ok_records.pop(token, None)
        path = self._delivery_ok_ledger_path
        if path is None:
            return
        record: dict[str, Any] = {
            "token": token,
            "forget": True,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        try:
            await asyncio.to_thread(self._append_ledger_record_blocking, path, record)
        except Exception:
            log.exception("delivery_ok_ledger_forget_failed", path=str(path))

    def _delivery_ok_already_recorded(self, pending: PendingSend) -> bool:
        return (
            pending.log_id in self._delivered_ok_ids
            or self._delivery_ok_token_for_pending(pending) in self._delivered_ok_tokens
        )

    async def _reconcile_delivery_ok(self, pending: PendingSend) -> None:
        token = self._delivery_ok_token_for_pending(pending)
        self._remember_delivered(pending.log_id)
        delivery_marked = await self._mark_delivery_ok_best_effort(
            pending.log_id,
            rule_id=pending.rule_id,
            event_key=None,
        )
        marked = await self._mark_sent_best_effort(
            pending.log_id,
            rule_id=pending.rule_id,
            event_key=None,
        )
        if delivery_marked or marked:
            await self._forget_durable_delivery_ok(token)

    async def _poll_prices(self) -> tuple[list[AlertEvent], bool]:
        """Fetch full tradeSummary, persist market-wide, evaluate watchlist only.

        Empty watchlist still persists the board so the thin /market browse has
        data. Rule evaluation and watched_missing checks remain watchlist-scoped.
        """
        symbols = await self.storage.watched_symbols()
        wanted = set(symbols)

        try:
            all_snaps = await self.cse.fetch_trade_summary()
        except CircuitOpenError:
            self.trade_summary_count = None
            self.trade_summary_empty_ok = False
            # No board this tick — clear stale missing so health does not imply
            # a CSE symbol gap when the real failure is circuit/transport.
            self.watched_missing = []
            log.error("price_poll_circuit_open")
            return [], False
        except Exception as exc:
            self.trade_summary_count = None
            self.trade_summary_empty_ok = False
            self.watched_missing = []
            log.exception("price_poll_failed", error=str(exc))
            return [], False

        self.trade_summary_count = len(all_snaps)
        self.trade_summary_empty_ok = len(all_snaps) == 0
        if self.trade_summary_empty_ok:
            log.warning(
                "trade_summary_empty_ok",
                watched_count=len(symbols),
                symbols=sorted(symbols),
            )

        # Market-wide persist (Tijori/browse foundation). Fail closed on DB errors.
        try:
            stored_all = await self.storage.persist_market_snapshots(all_snaps)
        except Exception as exc:
            log.exception("market_persist_failed", error=str(exc), count=len(all_snaps))
            # Fetch succeeded — report watchlist gaps from the board we saw.
            if wanted:
                # Fail closed — non-string symbols used to throw on .strip mid
                # board gap reporting after persist failure.
                present = {
                    s.symbol.strip().upper()
                    for s in all_snaps
                    if isinstance(s.symbol, str) and s.symbol.strip()
                }
                self.watched_missing = sorted(wanted - present)
            else:
                self.watched_missing = []
            return [], False

        # Optional non-watchlist snapshot retention (fail-soft — never degrade tick).
        retention_days = _positive_int_setting(self.settings.snapshot_retention_days)
        if retention_days > 0:
            try:
                deleted = await self.storage.delete_old_non_watchlist_snapshots(retention_days)
                if deleted:
                    log.info(
                        "snapshot_retention_deleted",
                        deleted=deleted,
                        days=retention_days,
                    )
            except Exception as exc:
                log.exception(
                    "snapshot_retention_failed",
                    error=str(exc),
                    days=retention_days,
                )

        if not wanted:
            self.watched_missing = []
            # Empty HTTP-OK board is not a successful browse persist.
            price_ok = not self.trade_summary_empty_ok
            log.info(
                "poll_market_persist_no_watchlist",
                persisted=len(stored_all),
                trade_summary_count=self.trade_summary_count,
                price_ok=price_ok,
            )
            return [], price_ok

        present = {s.symbol for s in stored_all}
        missing = sorted(wanted - present)
        self.watched_missing = missing
        price_ok = not missing
        if missing:
            log.warning(
                "watched_symbols_missing",
                count=len(missing),
                symbols=missing,
            )

        snaps = [s for s in stored_all if s.symbol in wanted]
        rules = await self.storage.active_rules_for_symbols(list(wanted))
        rules_by_symbol: dict[str, list[Any]] = {}
        for rule in rules:
            rules_by_symbol.setdefault(rule.symbol, []).append(rule)

        return await self._evaluate_price_snaps(snaps, rules_by_symbol), price_ok

    async def _poll_sectors(self) -> None:
        """Optional ``SECTORS_INGEST`` board persist — fail-soft, never degrades tick."""
        if not self.settings.sectors_ingest:
            return
        try:
            sectors = await self.cse.fetch_all_sectors()
        except Exception as exc:
            log.warning("sectors_poll_failed", error=str(exc))
            return
        try:
            stored = await self.storage.persist_sectors(sectors)
            log.info("sectors_persist_ok", fetched=len(sectors), persisted=len(stored))
        except Exception as exc:
            log.exception("sectors_persist_failed", error=str(exc), count=len(sectors))

    async def _poll_indexes(self) -> None:
        """Market index board persist — fail-soft, never degrades tick."""
        indexes = []
        fetchers = (
            getattr(self.cse, "fetch_aspi_data", None),
            getattr(self.cse, "fetch_snp_data", None),
        )
        for fetch in fetchers:
            if fetch is None:
                continue
            try:
                index = await fetch()
            except Exception as exc:
                log.warning(
                    "index_poll_failed",
                    endpoint=getattr(fetch, "__name__", ""),
                    error=str(exc),
                )
                continue
            if index is not None:
                indexes.append(index)
        if not indexes:
            return
        try:
            stored = await self.storage.persist_index_snapshots(indexes)
            log.info("indexes_persist_ok", fetched=len(indexes), persisted=len(stored))
        except Exception as exc:
            log.exception("indexes_persist_failed", error=str(exc), count=len(indexes))

    async def _evaluate_price_snaps(
        self,
        snaps: list[PriceSnapshot],
        rules_by_symbol: dict[str, list[Any]],
    ) -> list[AlertEvent]:
        """Evaluate already-persisted watchlist snapshots (ids required)."""
        fired: list[AlertEvent] = []
        for stored in snaps:
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
            # Price crosses: claim+disarm in one DB transaction (E2-C03).
            # Conflict claim skips disarm. Telegram send stays outside the txn.
            for event in filter_fireable(events):
                t0 = datetime.now(UTC)
                claimed = await self._claim_and_send(
                    event,
                    disarm=event.set_armed is False,
                )
                if not claimed:
                    continue
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
        # Fail closed — non-enum rule.type used to throw on .value mid disclosure
        # poll (parity tick needs_disclosure getattr).
        disclosure_rules = [
            r for r in rules if getattr(r.type, "value", r.type) == "disclosure"
        ]
        # Only hit CSE announcements for symbols with active disclosure rules
        # (price-only watchlist symbols skip this leg — rate-limit priority).
        disclosure_symbols = sorted({r.symbol for r in disclosure_rules})
        if not disclosure_symbols:
            return [], True

        tz = ZoneInfo(self.settings.market_tz)
        today = datetime.now(tz).date()
        from_date = (today - timedelta(days=365)).isoformat()
        to_date = today.isoformat()
        any_failure = False

        # Fetch all first (no inter-symbol sleep under lock — CORE-004).
        # Sequential HTTP provides natural spacing; rate-limit sleeps belong
        # outside the advisory lock if reintroduced.
        # Optional bulk path (DISCLOSURE_BULK_FEED=1): one market-wide call +
        # stocks name→symbol map; fail-soft to per-symbol for uncovered
        # tickers or when the bulk feed errors.
        fetched: dict[str, list[Disclosure]] = {}
        remaining = list(disclosure_symbols)
        if self.settings.disclosure_bulk_feed:
            bulk_fetched, bulk_covered, bulk_ok = await self._fetch_disclosures_bulk(
                disclosure_symbols
            )
            if bulk_ok:
                fetched.update(bulk_fetched)
                remaining = [s for s in disclosure_symbols if s not in bulk_covered]
                if remaining:
                    log.info(
                        "disclosure_bulk_partial_fallback",
                        bulk_covered=sorted(bulk_covered),
                        per_symbol_fallback=remaining,
                    )
            else:
                # Fail-soft: bulk error does not poison the tick if per-symbol works.
                log.warning(
                    "disclosure_bulk_failed_fallback",
                    symbols=disclosure_symbols,
                )
                remaining = list(disclosure_symbols)

        for symbol in remaining:
            try:
                fetched[symbol] = await self.cse.fetch_announcements_for_symbol(
                    symbol, from_date=from_date, to_date=to_date
                )
            except Exception as exc:
                any_failure = True
                log.warning("disclosure_poll_failed", symbol=symbol, error=str(exc))

        fired: list[AlertEvent] = []
        for symbol, disclosures in fetched.items():
            symbol_rules = [r for r in disclosure_rules if r.symbol == symbol]
            for disc in disclosures:
                # Always upsert + evaluate. Crash between insert and claim used to
                # permanently skip (insert_if_new → None). Claim uniqueness
                # prevents duplicate Telegram sends; created_at gates history.
                try:
                    stored = await self.storage.upsert_disclosure(disc)
                except Exception as exc:
                    any_failure = True
                    self.last_error = str(exc)
                    log.exception(
                        "disclosure_persist_failed",
                        symbol=symbol,
                        external_id=getattr(disc, "external_id", None),
                        error=str(exc),
                    )
                    continue
                events = evaluate_disclosure_rules(disclosure=stored, rules=symbol_rules)
                for event in filter_fireable(events):
                    claimed = await self._claim_and_send(event)
                    if claimed:
                        fired.append(event)
                # CSE dividend calendar — parse title/category into dividend_events.
                try:
                    await self.storage.upsert_dividend_event_from_disclosure(
                        symbol=stored.symbol,
                        disclosure_id=stored.id,
                        title=stored.title,
                        category=stored.category,
                        brief=None,
                        published_at=stored.published_at,
                    )
                except Exception as exc:
                    log.warning(
                        "dividend_event_upsert_failed",
                        symbol=symbol,
                        error=str(exc),
                    )
                # Queue PDF enrichment after alerts are claimed — never blocks
                # rule eval / Telegram. Skip rows that already have pdf_url.
                if (
                    stored.id is not None
                    and stored.just_inserted
                    and not stored.pdf_url
                    and self._pending_pdf_enrich is not None
                ):
                    self._pending_pdf_enrich.append(
                        PendingPdfEnrich(
                            disclosure_id=stored.id,
                            symbol=stored.symbol,
                            external_id=stored.external_id,
                        )
                    )
        return fired, not any_failure

    async def _poll_big_prints(self) -> tuple[list[AlertEvent], bool]:
        """Poll day tape for symbols with active big_print rules."""
        symbols = await self.storage.watched_symbols()
        if not symbols:
            return [], True
        rules = await self.storage.active_rules_for_symbols(symbols)
        print_rules = [
            r for r in rules if getattr(r.type, "value", r.type) == "big_print"
        ]
        print_symbols = sorted({r.symbol for r in print_rules})
        if not print_symbols:
            return [], True

        any_failure = False
        fired: list[AlertEvent] = []
        for symbol in print_symbols:
            try:
                prints = await self.cse.fetch_days_trade(symbol)
            except Exception as exc:
                any_failure = True
                log.warning("big_print_poll_failed", symbol=symbol, error=str(exc))
                continue
            symbol_rules = [r for r in print_rules if r.symbol == symbol]
            for bp in prints:
                try:
                    stored = await self.storage.upsert_big_print(bp)
                except Exception as exc:
                    any_failure = True
                    log.exception(
                        "big_print_persist_failed",
                        symbol=symbol,
                        external_id=getattr(bp, "external_id", None),
                        error=str(exc),
                    )
                    continue
                events = evaluate_big_print_rules(print_=stored, rules=symbol_rules)
                for event in filter_fireable(events):
                    claimed = await self._claim_and_send(event)
                    if claimed:
                        fired.append(event)
        return fired, not any_failure

    async def _poll_market_notices(self) -> tuple[list[AlertEvent], bool]:
        """Poll buy-in, non-compliance, and halt/notification feeds."""
        symbols = await self.storage.watched_symbols()
        # Halt rules may only watch MARKET; still load all active notice rules.
        wanted = set(symbols) | {MARKET_SYMBOL}
        rules = await self.storage.active_rules_for_symbols(sorted(wanted))
        notice_rules = [
            r
            for r in rules
            if getattr(r.type, "value", r.type)
            in {"buy_in", "non_compliance", "halt"}
        ]
        if not notice_rules:
            return [], True

        any_failure = False
        notices: list[Any] = []
        fetchers = (
            ("buy_in", self.cse.fetch_buy_in_announcements),
            ("non_compliance", self.cse.fetch_non_compliance_announcements),
            ("halt", self.cse.fetch_market_notifications),
        )
        needed = {getattr(r.type, "value", r.type) for r in notice_rules}
        for kind, fetcher in fetchers:
            if kind not in needed:
                continue
            try:
                batch = await fetcher()
                notices.extend(batch)
            except Exception as exc:
                any_failure = True
                log.warning("market_notice_poll_failed", kind=kind, error=str(exc))

        fired: list[AlertEvent] = []
        for notice in notices:
            # Resolve company → symbol for buy-in / non-compliance when missing.
            if notice.symbol is None and notice.notice_type != "halt":
                company = None
                if isinstance(notice.body, str) and notice.body.strip():
                    # Body often starts with company name from flexible parser.
                    company = notice.body.split(" — ", 1)[0].strip()
                if isinstance(notice.title, str) and (
                    company is None or company == notice.title
                ):
                    # Try title only when body lacked a distinct company.
                    pass
                resolved = await self.storage.resolve_symbol_by_company_name(company)
                if resolved is None and isinstance(notice.title, str):
                    resolved = await self.storage.resolve_symbol_by_company_name(
                        notice.title
                    )
                if resolved is not None:
                    notice = notice.model_copy(update={"symbol": resolved})
            try:
                stored = await self.storage.upsert_market_notice(notice)
            except Exception as exc:
                any_failure = True
                log.exception(
                    "market_notice_persist_failed",
                    notice_type=getattr(notice, "notice_type", None),
                    external_id=getattr(notice, "external_id", None),
                    error=str(exc),
                )
                continue
            events = evaluate_notice_rules(notice=stored, rules=notice_rules)
            for event in filter_fireable(events):
                claimed = await self._claim_and_send(event)
                if claimed:
                    fired.append(event)
        return fired, not any_failure

    async def _poll_market_regime(self) -> tuple[list[AlertEvent], bool]:
        """Evaluate MARKET tape/context regime rules from Postgres only.

        Inputs: latest appetite score, foreign net, book imbalance %, USD/LKR
        and Brent day-over-day % when ``macro_series`` is populated. Fail-soft
        when a leg is missing — that type simply does not fire.
        """
        try:
            rules = await self.storage.active_rules_for_symbols([MARKET_SYMBOL])
        except Exception as exc:
            log.exception("market_regime_rules_load_failed", error=str(exc))
            return [], False

        # xd_digest is MARKET-scoped but evaluated in _poll_dividend_xd.
        regime_type_values = {
            t.value
            for t in (MARKET_REGIME_ALERT_TYPES - {AlertType.HALT, AlertType.XD_DIGEST})
        }
        regime_rules = [
            r
            for r in rules
            if getattr(r.type, "value", r.type) in regime_type_values
        ]
        if not regime_rules:
            return [], True

        appetite_score: float | None = None
        foreign_net: float | None = None
        book_imbalance_pct: float | None = None
        usdlkr_change_pct: float | None = None
        oil_change_pct: float | None = None
        ok = True

        try:
            appetite_rows = await self.storage.list_market_appetite_daily(
                source="cse"
            )
            if appetite_rows:
                raw = appetite_rows[-1].get("score")
                if (
                    not isinstance(raw, bool)
                    and isinstance(raw, int | float)
                    and math.isfinite(float(raw))
                ):
                    appetite_score = float(raw)
        except Exception as exc:
            ok = False
            log.warning("market_regime_appetite_load_failed", error=str(exc))

        try:
            summary = await self.storage.list_market_daily_summary()
            if summary:
                raw = summary[-1].get("foreign_net")
                if (
                    not isinstance(raw, bool)
                    and isinstance(raw, int | float)
                    and math.isfinite(float(raw))
                ):
                    foreign_net = float(raw)
        except Exception as exc:
            ok = False
            log.warning("market_regime_foreign_load_failed", error=str(exc))

        try:
            book_imbalance_pct = await self.storage.market_book_imbalance_pct()
        except Exception as exc:
            ok = False
            log.warning("market_regime_book_load_failed", error=str(exc))

        try:
            usdlkr_change_pct = await self.storage.latest_macro_change_pct(
                "USD_LKR"
            )
        except Exception as exc:
            ok = False
            log.warning("market_regime_usdlkr_load_failed", error=str(exc))

        try:
            oil_change_pct = await self.storage.latest_macro_change_pct(
                "BRENT_SPOT"
            )
        except Exception as exc:
            ok = False
            log.warning("market_regime_oil_load_failed", error=str(exc))

        try:
            fired_keys = await self.storage.market_regime_fired_keys()
        except Exception as exc:
            ok = False
            log.warning("market_regime_fired_keys_failed", error=str(exc))
            fired_keys = set()

        try:
            events = evaluate_market_regime_rules(
                rules=regime_rules,
                appetite_score=appetite_score,
                foreign_net=foreign_net,
                book_imbalance_pct=book_imbalance_pct,
                usdlkr_change_pct=usdlkr_change_pct,
                oil_change_pct=oil_change_pct,
                fired_keys=fired_keys,
            )
        except Exception as exc:
            log.exception("market_regime_evaluate_failed", error=str(exc))
            return [], False

        fired: list[AlertEvent] = []
        for event in filter_fireable(events):
            claimed = await self._claim_and_send(event)
            if claimed:
                fired.append(event)
        if fired:
            log.info(
                "market_regime_fired",
                count=len(fired),
                types=[getattr(e.type, "value", e.type) for e in fired],
            )
        return fired, ok

    async def _poll_dividend_xd(self) -> tuple[list[AlertEvent], bool]:
        """Sync dividend_events from disclosures; fire xd_soon + xd_digest."""
        ok = True
        try:
            await self.storage.sync_dividend_events_from_recent_disclosures(limit=120)
        except Exception as exc:
            ok = False
            log.warning("dividend_events_sync_failed", error=str(exc))

        fired: list[AlertEvent] = []
        try:
            watched = await self.storage.watched_symbols()
            symbols = list(watched) if watched else []
            # Include symbols that have xd_soon rules even if not watched.
            soon_rules = await self.storage.active_rules_for_symbols(
                symbols + [MARKET_SYMBOL] if symbols else [MARKET_SYMBOL]
            )
            # Also load any xd_soon via a broad MARKET+watched pull; for symbols
            # only in rules, merge from active rules query on those symbols.
            xd_soon_rules = [
                r
                for r in soon_rules
                if getattr(r.type, "value", r.type) == "xd_soon"
            ]
            digest_rules = [
                r
                for r in soon_rules
                if getattr(r.type, "value", r.type) == "xd_digest"
            ]
            # Expand rule symbols for calendar fetch.
            rule_syms = sorted({r.symbol for r in xd_soon_rules})
            fetch_syms = sorted(set(symbols) | set(rule_syms))
            upcoming = await self.storage.list_upcoming_dividend_events(
                symbols=fetch_syms or None,
                horizon_days=90,
                limit=200,
            )
            by_symbol: dict[str, list] = {}
            for ev in upcoming:
                by_symbol.setdefault(ev.symbol, []).append(ev)

            # If xd_soon rules reference symbols with no upcoming rows, still ok.
            if xd_soon_rules:
                # Reload rules for exact rule symbols (may be outside watchlist).
                if rule_syms:
                    extra = await self.storage.active_rules_for_symbols(rule_syms)
                    xd_soon_rules = [
                        r
                        for r in extra
                        if getattr(r.type, "value", r.type) == "xd_soon"
                    ]
                events = evaluate_xd_soon_rules(
                    events_by_symbol=by_symbol,
                    rules=xd_soon_rules,
                )
                for event in filter_fireable(events):
                    claimed = await self._claim_and_send(event)
                    if claimed:
                        fired.append(event)

            if digest_rules:
                for rule in digest_rules:
                    try:
                        user_watch = await self.storage.list_watchlist(rule.user_id)
                    except Exception:
                        user_watch = []
                    watch_set = {w for w in user_watch if isinstance(w, str)}
                    user_upcoming = [e for e in upcoming if e.symbol in watch_set]
                    events = evaluate_xd_digest_rules(
                        upcoming=user_upcoming,
                        rules=[rule],
                    )
                    for event in filter_fireable(events):
                        claimed = await self._claim_and_send(event)
                        if claimed:
                            fired.append(event)
        except Exception as exc:
            ok = False
            log.exception("dividend_xd_poll_failed", error=str(exc))
        if fired:
            log.info("dividend_xd_fired", count=len(fired))
        return fired, ok

    async def _poll_order_books(self) -> tuple[list[AlertEvent], bool]:
        """Poll public order-book totals for bid_heavy / ask_heavy rules."""
        symbols = await self.storage.watched_symbols()
        if not symbols:
            return [], True
        rules = await self.storage.active_rules_for_symbols(symbols)
        book_rules = [
            r
            for r in rules
            if getattr(r.type, "value", r.type) in {"bid_heavy", "ask_heavy"}
        ]
        book_symbols = sorted({r.symbol for r in book_rules})
        if not book_symbols:
            return [], True

        any_failure = False
        fired: list[AlertEvent] = []
        for symbol in book_symbols:
            try:
                book = await self.cse.fetch_order_book(symbol)
            except Exception as exc:
                any_failure = True
                log.warning("order_book_poll_failed", symbol=symbol, error=str(exc))
                continue
            if book is None:
                continue
            try:
                stored = await self.storage.persist_order_book(book)
            except Exception as exc:
                any_failure = True
                log.exception(
                    "order_book_persist_failed",
                    symbol=symbol,
                    error=str(exc),
                )
                continue
            try:
                fired_keys = await self.storage.order_book_fired_keys(symbol)
            except Exception as exc:
                any_failure = True
                log.exception(
                    "order_book_fired_keys_failed",
                    symbol=symbol,
                    error=str(exc),
                )
                fired_keys = set()
            symbol_rules = [r for r in book_rules if r.symbol == symbol]
            events = evaluate_order_book_rules(
                book=stored, rules=symbol_rules, fired_keys=fired_keys
            )
            for event in filter_fireable(events):
                claimed = await self._claim_and_send(event)
                if claimed:
                    fired.append(event)
        return fired, not any_failure

    async def _fetch_disclosures_bulk(
        self, disclosure_symbols: list[str]
    ) -> tuple[dict[str, list[Disclosure]], set[str], bool]:
        """Market-wide approvedAnnouncement + name map.

        Returns ``(fetched_by_symbol, covered_symbols, ok)``. ``covered`` are
        symbols that have a unique stocks-table name mapping (safe to skip
        per-symbol HTTP even when the feed has no rows for them). On any
        bulk/map failure, ``ok`` is False and the caller falls back fully.
        """
        # Fail closed — non-string watchlist symbols used to throw on .strip mid bulk fetch.
        allowed = {
            s.strip().upper()
            for s in disclosure_symbols
            if isinstance(s, str) and s.strip()
        }
        try:
            rows = await self.cse.fetch_approved_announcements()
            stock_pairs = await self.storage.list_stock_names()
        except Exception as exc:
            log.warning("disclosure_bulk_fetch_failed", error=str(exc))
            return {}, set(), False

        name_map = build_unique_company_name_map(stock_pairs)
        covered: set[str] = set()
        for symbol, name in stock_pairs:
            # Fail closed — non-string stock pair members used to throw on .strip.
            if not isinstance(symbol, str) or not isinstance(name, str):
                continue
            sym = symbol.strip().upper()
            if sym not in allowed or not name:
                continue
            mapped = name_map.get(normalize_company_name(name))
            if mapped == sym:
                covered.add(sym)

        seen_at = datetime.now(UTC)
        fetched: dict[str, list[Disclosure]] = {s: [] for s in covered}
        unmatched = 0
        for row in rows:
            resolved = resolve_announcement_symbol(row, name_map=name_map, allowed_symbols=allowed)
            if resolved is None:
                unmatched += 1
                continue
            covered.add(resolved)
            fetched.setdefault(resolved, [])
            disc = announcement_to_disclosure(row, symbol=resolved, seen_at=seen_at)
            if disc is not None:
                fetched[resolved].append(disc)

        log.info(
            "disclosure_bulk_ok",
            rows=len(rows),
            matched_symbols=sorted(s for s, ds in fetched.items() if ds),
            covered=sorted(covered),
            unmatched_or_out_of_watchlist=unmatched,
        )
        return fetched, covered, True

    def _schedule_pdf_enrichment(self, items: list[PendingPdfEnrich]) -> None:
        """Fire-and-forget enrich so run_once returns after alert delivery."""
        if not items:
            return
        if self._background_closed:
            log.warning(
                "pdf_enrich_skipped_shutdown",
                count=len(items),
            )
            return
        self._pdf_enrich_last_batch_size = len(items)
        self._pdf_enrich_batches_started += 1
        task = asyncio.create_task(
            self._enrich_disclosure_pdfs_safe(items),
            name="chime_pdf_enrich",
        )
        self._pdf_enrich_tasks.add(task)
        task.add_done_callback(self._pdf_enrich_tasks.discard)

    def _schedule_brief_drain(self) -> None:
        """Fire-and-forget pending brief drain when AI briefs are enabled."""
        if not briefs_enabled():
            return
        if self._background_closed:
            log.warning("brief_drain_skipped_shutdown")
            return
        # Coalesce: one in-flight drain (or waiter on the lock) is enough —
        # avoid N tasks stacking on `_brief_drain_lock` for shutdown gathers.
        if self._brief_drain_tasks or self._brief_drain_lock.locked():
            return
        task = asyncio.create_task(
            self._drain_briefs_safe(),
            name="chime_brief_drain",
        )
        self._brief_drain_tasks.add(task)
        task.add_done_callback(self._brief_drain_tasks.discard)

    async def _drain_briefs_safe(self) -> None:
        try:
            async with self._brief_drain_lock:
                n = await claim_pending_briefs(self.storage, notify=self.send)
                if n:
                    log.info("brief_drain_done", processed=n)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("brief_drain_failed", error=str(exc))

    async def _enrich_disclosure_pdfs_safe(self, items: list[PendingPdfEnrich]) -> None:
        try:
            async with self._pdf_enrich_lock:
                await self._enrich_disclosure_pdfs(items)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("pdf_enrich_batch_failed", error=str(exc))

    async def _enrich_disclosure_pdfs(self, items: list[PendingPdfEnrich]) -> None:
        """Resolve legacy filePath → CDN PDF URL. Fail-soft; polite per-symbol sleep.

        Runs outside the advisory lock and outside run_once's await path so CSE
        latency / sleeps never pin the poller or delay Telegram / next tick.
        """
        if not items:
            return
        by_symbol: dict[str, list[PendingPdfEnrich]] = {}
        for item in items:
            by_symbol.setdefault(item.symbol, []).append(item)

        sleep_s = max(0.0, float(self.settings.pdf_enrich_sleep_seconds))
        for symbol, rows in sorted(by_symbol.items()):
            if sleep_s > 0:
                await asyncio.sleep(sleep_s)
            try:
                legacy = await self.cse.fetch_legacy_announcements(symbol)
            except Exception as exc:
                log.warning(
                    "legacy_announcement_enrich_failed",
                    symbol=symbol,
                    error=str(exc),
                )
                continue
            pdf_map = legacy_pdf_urls_by_id(legacy)
            if not pdf_map:
                continue
            for item in rows:
                pdf_url = pdf_map.get(item.external_id)
                if not pdf_url:
                    continue
                try:
                    updated = await self.storage.set_disclosure_pdf_url(item.disclosure_id, pdf_url)
                    if updated:
                        log.info(
                            "disclosure_pdf_url_set",
                            disclosure_id=item.disclosure_id,
                            symbol=item.symbol,
                            external_id=item.external_id,
                        )
                        self._schedule_metrics_job(item.disclosure_id, item.symbol)
                except Exception as exc:
                    log.warning(
                        "pdf_url_set_failed",
                        disclosure_id=item.disclosure_id,
                        symbol=item.symbol,
                        error=str(exc),
                    )

    def _schedule_metrics_job(self, disclosure_id: int, symbol: str) -> None:
        """Fire-and-forget filing metrics extract after pdf_url lands."""
        from chime.metrics import metrics_enabled

        if not metrics_enabled():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(
            self._run_metrics_job_safe(disclosure_id, symbol),
            name=f"metrics-{disclosure_id}",
        )

    async def _run_metrics_job_safe(self, disclosure_id: int, symbol: str) -> None:
        try:
            await self._run_metrics_job(disclosure_id, symbol)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "metrics_job_failed",
                disclosure_id=disclosure_id,
                symbol=symbol,
                error=str(exc)[:240],
            )

    async def _run_metrics_job(self, disclosure_id: int, symbol: str) -> None:
        from chime.domain import format_alert_message
        from chime.metrics import MetricsSettings
        from chime.metrics.worker import process_disclosure_metrics

        disc = await self.storage.get_disclosure_by_id(disclosure_id)
        if disc is None or not disc.pdf_url:
            return
        rules = await self.storage.active_rules_for_symbols([symbol])
        cfg = MetricsSettings.from_env()
        result = await process_disclosure_metrics(
            storage=self.storage,
            disclosure=disc,
            rules=rules,
            settings=cfg,
        )
        if result is None:
            return
        if (
            cfg.yoy_append_to_disclosure
            and result.metrics_id is not None
            and result.compared
        ):
            await self._maybe_send_yoy_append(disc, result.metrics_id, rules)
        if not result.events:
            return
        for event in result.events:
            text = format_alert_message(event)
            shadow_only = cfg.metrics_shadow_mode and (
                (
                    event.type.value in ("eps_above", "eps_below")
                    and not cfg.eps_calc_alerts_enabled
                )
                or (
                    "yoy" in event.type.value and not cfg.yoy_compare_alerts_enabled
                )
            )
            if shadow_only:
                text = f"[shadow] {text}"
            alert_id = await self.storage.claim_alert(event, text)
            if alert_id is None:
                continue
            if shadow_only:
                await self.storage.mark_alert_sent(alert_id)
                log.info(
                    "metrics_shadow_fire",
                    alert_log_id=alert_id,
                    event_key=event.event_key,
                    symbol=symbol,
                )
                continue
            pending = PendingSend(
                log_id=alert_id,
                telegram_id=event.telegram_id,
                message=text,
                already_claimed_new=True,
                rule_id=event.rule_id,
                event=event,
                symbol=event.symbol,
            )
            await self._deliver_one(pending)

    async def _maybe_send_yoy_append(
        self, disc: Disclosure, metrics_id: int, rules: list[AlertRule]
    ) -> None:
        """Follow-up Telegram with YoY block for users watching disclosures."""
        from chime.domain import (
            AlertEvent,
            AlertType,
            format_alert_message,
            format_yoy_comparison_block,
        )

        comparison = await self.storage.get_filing_comparison_for_metrics(metrics_id)
        metrics_rows = await self.storage.list_filing_metrics_for_symbol(disc.symbol)
        metrics = next((m for m in metrics_rows if int(m["id"]) == metrics_id), None)
        if not metrics or not comparison:
            return
        block = format_yoy_comparison_block(metrics=metrics, comparison=comparison)
        if not block:
            return
        for rule in rules:
            if not rule.active or rule.type != AlertType.DISCLOSURE:
                continue
            if rule.symbol != disc.symbol:
                continue
            event = AlertEvent(
                rule_id=rule.id,
                user_id=rule.user_id,
                telegram_id=rule.telegram_id,
                symbol=rule.symbol,
                type=AlertType.DISCLOSURE,
                threshold=None,
                trigger=f"filing metrics YoY for {disc.title}",
                disclosure_url=disc.url or disc.pdf_url,
                disclosure_title=disc.title,
                disclosure_id=disc.id,
                filing_brief=block,
                event_key=f"yoy_append:{rule.id}:{disc.id}",
            )
            text = format_alert_message(event)
            alert_id = await self.storage.claim_alert(event, text)
            if alert_id is None:
                continue
            pending = PendingSend(
                log_id=alert_id,
                telegram_id=event.telegram_id,
                message=text,
                already_claimed_new=True,
                rule_id=event.rule_id,
                event=event,
                symbol=event.symbol,
            )
            await self._deliver_one(pending)

    async def _notify_dead_letter(
        self,
        *,
        telegram_id: int | None,
        symbol: str | None,
        attempts: int,
        alert_log_id: int,
        rule_id: int | None = None,
    ) -> None:
        """One Telegram notify after dead-letter. Failures are log-only (no retry loop)."""
        if telegram_id is None or not symbol:
            log.warning(
                "dead_letter_notify_skipped",
                alert_log_id=alert_log_id,
                rule_id=rule_id,
                attempts=attempts,
                has_telegram_id=telegram_id is not None,
                has_symbol=bool(symbol),
            )
            return
        if alert_log_id in self._dead_letter_notify_attempted_ids:
            log.info(
                "dead_letter_notify_already_attempted",
                alert_log_id=alert_log_id,
                rule_id=rule_id,
                symbol=symbol,
                attempts=attempts,
            )
            return
        self._dead_letter_notify_attempted_ids.add(alert_log_id)
        text = format_dead_letter_notify(symbol, attempts)
        try:
            result = _normalize_send_result(await self.send(telegram_id, text))
        except Exception:
            log.exception(
                "dead_letter_notify_failed",
                alert_log_id=alert_log_id,
                rule_id=rule_id,
                symbol=symbol,
                attempts=attempts,
            )
            return
        if result is SendResult.OK:
            log.info(
                "dead_letter_notify_sent",
                alert_log_id=alert_log_id,
                rule_id=rule_id,
                symbol=symbol,
                attempts=attempts,
            )
        else:
            # Do not bump attempt_count / dead-letter again — notify is best-effort.
            log.warning(
                "dead_letter_notify_failed",
                alert_log_id=alert_log_id,
                rule_id=rule_id,
                symbol=symbol,
                attempts=attempts,
                send_result=result.value,
            )

    async def _record_send_failure(
        self,
        alert_log_id: int,
        *,
        rule_id: int | None = None,
        telegram_id: int | None = None,
        symbol: str | None = None,
    ) -> None:
        attempts = await self.storage.mark_alert_attempt(alert_log_id)
        if attempts >= MAX_SEND_ATTEMPTS:
            await self.storage.dead_letter(alert_log_id)
            log.warning(
                "alert_dead_lettered",
                alert_log_id=alert_log_id,
                rule_id=rule_id,
                attempts=attempts,
                reason="failed",
            )
            await self._notify_dead_letter(
                telegram_id=telegram_id,
                symbol=symbol,
                attempts=attempts,
                alert_log_id=alert_log_id,
                rule_id=rule_id,
            )
        else:
            log.warning(
                "alert_send_failed",
                alert_log_id=alert_log_id,
                rule_id=rule_id,
                attempts=attempts,
            )

    async def _record_send_deferred(
        self,
        alert_log_id: int,
        *,
        rule_id: int | None = None,
        telegram_id: int | None = None,
        symbol: str | None = None,
    ) -> None:
        """Bump deferred_attempt_count on RetryAfter defer; dead-letter at MAX_DEFERRED_ATTEMPTS.

        Uses its own counter, separate from ``attempt_count``, so alternating
        ordinary failures and flood-wait defers on the same alert don't burn
        down the tighter ``MAX_SEND_ATTEMPTS`` ceiling meant only for the former.
        """
        attempts = await self.storage.mark_alert_deferred_attempt(alert_log_id)
        if attempts >= MAX_DEFERRED_ATTEMPTS:
            await self.storage.dead_letter(alert_log_id)
            log.warning(
                "alert_dead_lettered",
                alert_log_id=alert_log_id,
                rule_id=rule_id,
                attempts=attempts,
                reason="deferred",
            )
            await self._notify_dead_letter(
                telegram_id=telegram_id,
                symbol=symbol,
                attempts=attempts,
                alert_log_id=alert_log_id,
                rule_id=rule_id,
            )
        else:
            log.info(
                "alert_send_deferred",
                alert_log_id=alert_log_id,
                rule_id=rule_id,
                attempts=attempts,
            )

    async def _ready_filing_brief_for(self, event: AlertEvent) -> str | None:
        """Best-effort ready brief for a disclosure alert; never raises."""
        # Fail closed — non-enum type used to throw on .value before lookup try.
        type_val = getattr(event.type, "value", event.type)
        if type_val != "disclosure":
            return None
        external_id: str | None = None
        # event_key = disclosure:{rule_id}:{external_id}
        # Fail closed — non-string event_key used to throw on .startswith mid claim.
        key = event.event_key
        if isinstance(key, str) and key.startswith("disclosure:"):
            parts = key.split(":", 2)
            if len(parts) == 3 and parts[2].strip():
                external_id = parts[2].strip()
        try:
            brief = await self.storage.get_ready_filing_brief(
                disclosure_id=event.disclosure_id,
                external_id=external_id,
                symbol=event.symbol,
            )
        except Exception as exc:
            log.warning(
                "ready_filing_brief_lookup_failed",
                event_key=event.event_key,
                disclosure_id=event.disclosure_id,
                error=str(exc),
            )
            return None
        if isinstance(brief, str) and brief.strip():
            return brief
        return None

    async def _claim_only(
        self,
        event: AlertEvent,
        *,
        disarm: bool = False,
    ) -> PendingSend | None:
        """Claim the alert row; return a PendingSend or None on conflict.

        When ``disarm`` is True (price crosses), uses ``claim_and_disarm`` so
        claim + armed=False commit together. Conflict → no disarm.

        Disclosure claims attach a ready ``disclosure_briefs`` filing brief when
        present (fail-soft — missing/pending briefs do not block the push).
        """
        filing_brief = await self._ready_filing_brief_for(event)
        message = format_alert_message(event, filing_brief=filing_brief)
        if disarm:
            log_id = await self.storage.claim_and_disarm(event, message)
        else:
            log_id = await self.storage.claim_alert(event, message)
        if log_id is None:
            log.info("alert_already_claimed", event_key=event.event_key, rule_id=event.rule_id)
            return None
        return PendingSend(
            log_id=log_id,
            telegram_id=event.telegram_id,
            message=message,
            already_claimed_new=True,
            rule_id=event.rule_id,
            event=event,
            symbol=event.symbol,
        )

    async def _telegram_in_quiet_hours(self, telegram_id: int) -> bool:
        """True when Colombo local hour is inside the user's quiet window.

        Window may wrap midnight (e.g. 22→6). Both ends required; otherwise off.
        """
        try:
            prefs = await self.storage.get_user_quiet_hours_by_telegram(telegram_id)
        except AttributeError:
            # Older / test storage stubs without the prefs method — treat as off.
            return False
        except Exception:
            log.exception("quiet_hours_lookup_failed", telegram_id=telegram_id)
            return False
        if prefs is None:
            return False
        if not isinstance(prefs, tuple) or len(prefs) != 2:
            return False
        start, end = prefs
        if start is None or end is None:
            return False
        if not isinstance(start, int) or not isinstance(end, int):
            return False
        if isinstance(start, bool) or isinstance(end, bool):
            return False
        if start == end:
            return False
        if not (0 <= start <= 23 and 0 <= end <= 23):
            return False
        try:
            hour = datetime.now(ZoneInfo("Asia/Colombo")).hour
        except Exception:
            return False
        if start < end:
            return start <= hour < end
        # Wraps midnight: quiet from start..23 and 0..end-1
        return hour >= start or hour < end

    async def _deliver_one(self, pending: PendingSend) -> None:
        """Send one claimed alert and update alert_log (OK / FAILED / DEFERRED)."""
        # Quiet hours (user prefs) — hold the row (message_sent=false) for retry;
        # do not burn deferred/failure attempt counters.
        if await self._telegram_in_quiet_hours(pending.telegram_id):
            log.info(
                "alert_held_quiet_hours",
                rule_id=pending.rule_id,
                telegram_id=pending.telegram_id,
                log_id=pending.log_id,
            )
            return
        result = _normalize_send_result(await self.send(pending.telegram_id, pending.message))
        symbol = pending.symbol
        if symbol is None and pending.event is not None:
            symbol = pending.event.symbol
        if symbol is None:
            symbol = _symbol_from_alert_message(pending.message)
        if result is SendResult.OK:
            # Telegram already delivered. Remember across ticks (L08-001) so a
            # mark_alert_sent outage cannot re-push every poll interval.
            self._remember_delivered(pending.log_id)
            event_key = pending.event.event_key if pending.event is not None else None
            # E12-C01: write a local durable OK marker before any DB marks. If
            # all post-send DB writes fail and the process restarts, retry drain
            # will reconcile this row without re-sending Telegram.
            token = await self._durably_remember_delivery_ok(pending, event_key=event_key)
            # Durable guard before message_sent (E2-C04): survives restart when
            # mark_alert_sent fails but this lighter UPDATE succeeds.
            delivery_marked = await self._mark_delivery_ok_best_effort(
                pending.log_id,
                rule_id=pending.rule_id,
                event_key=event_key,
            )
            marked = await self._mark_sent_best_effort(
                pending.log_id,
                rule_id=pending.rule_id,
                event_key=event_key,
            )
            if marked:
                log.info(
                    "alert_sent",
                    rule_id=pending.rule_id,
                    event_key=event_key,
                )
            if delivery_marked or marked:
                await self._forget_durable_delivery_ok(token)
        elif result is SendResult.FAILED:
            await self._record_send_failure(
                pending.log_id,
                rule_id=pending.rule_id,
                telegram_id=pending.telegram_id,
                symbol=symbol,
            )
        elif result is SendResult.DEFERRED:
            await self._record_send_deferred(
                pending.log_id,
                rule_id=pending.rule_id,
                telegram_id=pending.telegram_id,
                symbol=symbol,
            )

    async def _deliver_pending(self, pending: list[PendingSend]) -> None:
        for item in pending:
            await self._deliver_one(item)

    async def _claim_and_send(self, event: AlertEvent, *, disarm: bool = False) -> bool:
        """Claim the alert, then attempt Telegram send (or queue when locked).

        Returns True when the claim succeeded (row inserted), even if Telegram
        send failed. With ``disarm=True``, claim and armed=False are one
        transaction (E2-C03); delivery continues via ``message_sent=False``
        retry / dead-letter. Returns False only on claim conflict.

        Under ``run_once`` (``_queue_sends=True``) the send is deferred until
        after advisory unlock (CORE-004). Direct callers (unit tests) still
        send inline.
        """
        pending = await self._claim_only(event, disarm=disarm)
        if pending is None:
            return False
        if self._queue_sends:
            self._pending_sends.append(pending)
            return True
        await self._deliver_one(pending)
        return True

    async def _mark_delivery_ok_best_effort(
        self,
        log_id: int,
        *,
        rule_id: int | None = None,
        event_key: str | None = None,
    ) -> bool:
        """Persist delivery_attempted_ok so restart cannot re-push (E2-C04).

        Retries before treating delivery as durably recorded. Never raises.
        Returns True if the durable flag was written. On total failure the
        caller still keeps ``log_id`` in ``_delivered_ok_ids``; we log
        critical and best-effort dead-letter as a last resort.
        """
        for attempt in range(1, MARK_DELIVERY_OK_ATTEMPTS + 1):
            try:
                await self.storage.mark_delivery_attempted_ok(log_id)
                return True
            except Exception:
                log.exception(
                    "mark_delivery_attempted_ok_failed",
                    alert_log_id=log_id,
                    rule_id=rule_id,
                    event_key=event_key,
                    attempt=attempt,
                )
        log.critical(
            "mark_delivery_attempted_ok_abandoned",
            alert_log_id=log_id,
            rule_id=rule_id,
            event_key=event_key,
            attempts=MARK_DELIVERY_OK_ATTEMPTS,
        )
        with contextlib.suppress(Exception):
            await self.storage.dead_letter(log_id)
        return False

    async def _mark_sent_best_effort(
        self,
        log_id: int,
        *,
        rule_id: int | None = None,
        event_key: str | None = None,
    ) -> bool:
        """Mark message_sent; retry once on failure. Never raises.

        Returns True if marked. If both attempts fail, dead-letters so
        ``_retry_unsent`` cannot re-deliver to Telegram.
        """
        for attempt in (1, 2):
            try:
                await self.storage.mark_alert_sent(log_id)
                return True
            except Exception:
                log.exception(
                    "mark_alert_sent_failed",
                    alert_log_id=log_id,
                    rule_id=rule_id,
                    event_key=event_key,
                    attempt=attempt,
                )
        with contextlib.suppress(Exception):
            await self.storage.dead_letter(log_id)
        log.warning(
            "mark_alert_sent_abandoned",
            alert_log_id=log_id,
            rule_id=rule_id,
            event_key=event_key,
        )
        return False

    async def _retry_unsent(self) -> None:
        """Claim+send one unsent row at a time so each lease starts at send time.

        Batch-claiming N rows then sending sequentially can let later leases
        expire mid-drain (RetryAfter). ``limit=1`` renews the lease just before
        each Telegram attempt; stop when the queue is empty or after
        ``RETRY_UNSENT_MAX`` claims.
        """
        for _ in range(RETRY_UNSENT_MAX):
            pending = await self.storage.claim_unsent_batch(limit=1)
            if not pending:
                break
            row = pending[0]
            # Fail closed — poisoned unsent rows used to throw on int() or
            # soft-accept bool→1 / non-string message_text mid retry drain.
            raw_id = row.get("id")
            raw_tg = row.get("telegram_id")
            raw_rule = row.get("rule_id")
            if (
                isinstance(raw_id, bool)
                or not isinstance(raw_id, int)
                or isinstance(raw_tg, bool)
                or not isinstance(raw_tg, int)
                or isinstance(raw_rule, bool)
                or not isinstance(raw_rule, int)
            ):
                log.warning(
                    "unsent_row_poisoned",
                    alert_log_id=raw_id,
                    telegram_id=raw_tg,
                    rule_id=raw_rule,
                )
                continue
            log_id = raw_id
            raw_text = row.get("message_text")
            text = raw_text if isinstance(raw_text, str) else ""
            item = PendingSend(
                log_id=log_id,
                telegram_id=raw_tg,
                message=text,
                already_claimed_new=False,
                rule_id=raw_rule,
                event=None,
                symbol=_symbol_from_alert_message(text),
            )
            if self._delivery_ok_already_recorded(item):
                log.warning(
                    "alert_send_skipped_already_delivered_ok",
                    alert_log_id=log_id,
                    rule_id=item.rule_id,
                )
                await self._reconcile_delivery_ok(item)
                continue
            await self._deliver_one(item)

    async def _scheduled_tick(self) -> None:
        task = asyncio.current_task()
        self._tick_task = task
        try:
            jitter = random.uniform(0, self.settings.poll_jitter_seconds)
            await asyncio.sleep(jitter)
            await self.run_once()
        finally:
            if self._tick_task is task:
                self._tick_task = None

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

    async def _drain_background_on_shutdown(self) -> None:
        """Await PDF enrich + brief drain without cancelling them on timeout.

        Re-scans task sets until empty so a late ``run_once`` (shielded tick
        still finishing) can push work and still be waited on within the
        budget. ``asyncio.shield`` mirrors CORE-005: timeout must not cancel
        mid-flight work that holds the enrich/brief locks or a pool borrow.
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + SHUTDOWN_TICK_TIMEOUT_SECONDS
        while True:
            pending = [
                t for t in (*self._pdf_enrich_tasks, *self._brief_drain_tasks) if not t.done()
            ]
            if not pending:
                return
            remaining = deadline - loop.time()
            if remaining <= 0:
                log.warning(
                    "poller_shutdown_background_timeout",
                    timeout_seconds=SHUTDOWN_TICK_TIMEOUT_SECONDS,
                    pdf_enrich=len(self._pdf_enrich_tasks),
                    brief_drain=len(self._brief_drain_tasks),
                )
                return
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(
                        *[asyncio.shield(t) for t in pending],
                        return_exceptions=True,
                    ),
                    timeout=remaining,
                )
            except TimeoutError:
                log.warning(
                    "poller_shutdown_background_timeout",
                    timeout_seconds=SHUTDOWN_TICK_TIMEOUT_SECONDS,
                    pdf_enrich=len(self._pdf_enrich_tasks),
                    brief_drain=len(self._brief_drain_tasks),
                )
                return
            for result in results:
                if isinstance(result, Exception):
                    log.warning(
                        "poller_shutdown_background_error",
                        error=str(result),
                    )

    async def shutdown(self) -> None:
        """Stop the scheduler, then await any in-flight tick (bounded).

        ``scheduler.shutdown(wait=False)`` returns immediately; CORE-005 /
        E2-C02 require waiting for the current ``_scheduled_tick`` /
        ``run_once`` so ``storage.close()`` does not race the advisory lock.

        After the tick wait, drain fire-and-forget PDF enrich / brief push
        tasks the same way (shielded, bounded) before callers ``storage.close()``.
        """
        self._stopping.set()
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
        tick = self._tick_task
        if tick is not None and not tick.done():
            try:
                # shield: timeout must not cancel mid-tick (lock / pool borrow).
                await asyncio.wait_for(
                    asyncio.shield(tick),
                    timeout=SHUTDOWN_TICK_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                log.warning(
                    "poller_shutdown_tick_timeout",
                    timeout_seconds=SHUTDOWN_TICK_TIMEOUT_SECONDS,
                )
            except Exception:
                log.exception("poller_shutdown_tick_error")
        try:
            await self._drain_background_on_shutdown()
        except Exception:
            log.exception("poller_shutdown_background_error")
        # Reject further fire-and-forget schedules (late shielded tick).
        self._background_closed = True
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
            missing = list(poller.watched_missing)
            circuits: dict[str, object] = {}
            metrics = getattr(poller.cse, "circuit_metrics", None)
            if callable(metrics):
                raw = metrics()
                if isinstance(raw, dict):
                    circuits = raw
            health.update(
                ok=db_ok and tick_ok and not missing and not poller.trade_summary_empty_ok,
                db_ok=db_ok,
                last_tick_at=poller.last_tick_at.isoformat() if poller.last_tick_at else None,
                last_tick_ok=tick_ok,
                price_poll_ok=poller.price_poll_ok,
                disclosure_poll_ok=poller.disclosure_poll_ok,
                lock_held_skip=poller.lock_held_skip,
                watched_missing=missing,
                trade_summary_empty_ok=poller.trade_summary_empty_ok,
                trade_summary_count=poller.trade_summary_count,
                tradeSummary={
                    "empty_ok": poller.trade_summary_empty_ok,
                    "count": poller.trade_summary_count,
                },
                circuits=circuits,
                last_error=poller.last_error,
            )
            brief_queue = await brief_queue_health_hint(storage=storage, poller=poller)
            if brief_queue:
                health.update(brief_queue=brief_queue)
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
