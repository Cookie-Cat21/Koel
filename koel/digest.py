"""End-of-day Telegram digest for users with ``digest_enabled``.

Scheduling (documented choice)
------------------------------
Digests are sent **once per Colombo trading day after market close**
(default window 14:30–16:00 Asia/Colombo, weekdays). The poller invokes
``maybe_run_eod_digest`` on off-hours ticks; ``python3 -m koel digest``
runs the same path on demand.

Quiet hours gate **live** alert delivery only. Digests intentionally fire
at EOD so they are not held overnight inside a quiet window.

Idempotency: ``users.last_digest_on`` (claimed before send). Cap message
length with ``_clamp_telegram_message``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Awaitable, Callable, Protocol
from zoneinfo import ZoneInfo

from koel.domain import _clamp_telegram_message, disclaimer
from koel.logging_setup import get_logger
from koel.notify import SendResult

log = get_logger(__name__)

_COLOMBO = ZoneInfo("Asia/Colombo")

# After MARKET_CLOSE (14:30); stop retrying the same day after this.
DIGEST_WINDOW_START = time(14, 30)
DIGEST_WINDOW_END = time(16, 0)

MAX_FIRE_LINES = 8
MAX_MOVER_LINES = 5
MAX_XD_LINES = 5


class DigestStorage(Protocol):
    async def list_digest_users(self) -> list[dict[str, Any]]: ...

    async def claim_digest_send(self, user_id: int, on_date: date) -> bool: ...

    async def list_recent_alert_fires(
        self, user_id: int, *, since: datetime, limit: int = 20
    ) -> list[dict[str, Any]]: ...

    async def list_watchlist_movers(
        self, user_id: int, *, limit: int = 5
    ) -> list[dict[str, Any]]: ...

    async def list_watchlist(self, user_id: int) -> list[str]: ...

    async def list_upcoming_dividend_events(
        self,
        *,
        symbols: list[str] | None = None,
        horizon_days: int = 14,
        limit: int = 50,
    ) -> list[Any]: ...


SendFunc = Callable[[int, str], Awaitable[SendResult | bool]]


@dataclass(frozen=True)
class DigestRunResult:
    candidates: int
    sent: int
    skipped: int
    errors: int
    outside_window: bool = False


def colombo_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(_COLOMBO)
    if now.tzinfo is None:
        return now.replace(tzinfo=_COLOMBO)
    return now.astimezone(_COLOMBO)


def in_digest_window(now: datetime | None = None) -> bool:
    """True on Colombo weekdays between DIGEST_WINDOW_START and END."""
    local = colombo_now(now)
    if local.weekday() >= 5:
        return False
    t = local.time()
    return DIGEST_WINDOW_START <= t <= DIGEST_WINDOW_END


def format_digest_message(
    *,
    on_date: date,
    fires: list[dict[str, Any]],
    movers: list[dict[str, Any]],
    xd_rows: list[Any],
) -> str:
    """Build a short factual digest body (always ends with NFA)."""
    lines: list[str] = [f"koel EOD digest — {on_date.isoformat()} (SLT)"]

    if fires:
        lines.append("")
        lines.append(f"Alerts today ({len(fires)}):")
        for row in fires[:MAX_FIRE_LINES]:
            sym = str(row.get("symbol") or "?").strip() or "?"
            trigger = str(row.get("trigger") or row.get("type") or "alert").strip()
            if len(trigger) > 80:
                trigger = trigger[:79].rstrip() + "…"
            lines.append(f"• {sym}: {trigger}")
        if len(fires) > MAX_FIRE_LINES:
            lines.append(f"… +{len(fires) - MAX_FIRE_LINES} more")
    else:
        lines.append("")
        lines.append("Alerts today: none")

    if movers:
        lines.append("")
        lines.append("Watchlist movers:")
        for m in movers[:MAX_MOVER_LINES]:
            sym = str(m.get("symbol") or "?").strip() or "?"
            pct = m.get("change_pct")
            price = m.get("price")
            try:
                pct_s = f"{float(pct):+.2f}%" if pct is not None else "n/a"
            except (TypeError, ValueError):
                pct_s = "n/a"
            try:
                price_s = f"{float(price):g}" if price is not None else "?"
            except (TypeError, ValueError):
                price_s = "?"
            lines.append(f"• {sym} {price_s} ({pct_s})")

    if xd_rows:
        lines.append("")
        lines.append("Upcoming XD on watchlist:")
        for ev in xd_rows[:MAX_XD_LINES]:
            sym = str(getattr(ev, "symbol", None) or "?").strip() or "?"
            d_xd = getattr(ev, "d_xd", None)
            dps = getattr(ev, "dps", None)
            xd_s = d_xd.isoformat() if hasattr(d_xd, "isoformat") else str(d_xd or "?")
            dps_s = f" Rs {dps:g}" if isinstance(dps, int | float) and not isinstance(dps, bool) else ""
            lines.append(f"• {sym} XD {xd_s}{dps_s}")

    lines.append("")
    lines.append(disclaimer())
    return _clamp_telegram_message("\n".join(lines))


def _normalize_send_result(raw: SendResult | bool) -> SendResult:
    if isinstance(raw, SendResult):
        return raw
    return SendResult.OK if raw is True else SendResult.FAILED


async def build_user_digest(
    storage: DigestStorage,
    *,
    user_id: int,
    on_date: date,
    since: datetime,
) -> str:
    fires = await storage.list_recent_alert_fires(user_id, since=since, limit=20)
    movers = await storage.list_watchlist_movers(user_id, limit=MAX_MOVER_LINES)
    symbols = await storage.list_watchlist(user_id)
    xd_rows: list[Any] = []
    if symbols:
        try:
            xd_rows = await storage.list_upcoming_dividend_events(
                symbols=symbols, horizon_days=14, limit=MAX_XD_LINES
            )
        except Exception:
            log.exception("digest_xd_lookup_failed", user_id=user_id)
            xd_rows = []
    return format_digest_message(
        on_date=on_date, fires=fires, movers=movers, xd_rows=xd_rows
    )


async def run_eod_digest(
    storage: DigestStorage,
    send: SendFunc,
    *,
    now: datetime | None = None,
    force: bool = False,
) -> DigestRunResult:
    """Send digests to eligible users.

    When ``force`` is False, requires the Colombo digest window and skips
    users already claimed for today. ``force`` still claims per user so a
    forced re-run does not double-send within the same day unless the claim
    column is cleared.
    """
    local = colombo_now(now)
    if not force and not in_digest_window(local):
        log.info(
            "digest_skipped_outside_window",
            local=local.isoformat(),
            start=DIGEST_WINDOW_START.isoformat(timespec="minutes"),
            end=DIGEST_WINDOW_END.isoformat(timespec="minutes"),
        )
        return DigestRunResult(
            candidates=0, sent=0, skipped=0, errors=0, outside_window=True
        )

    on_date = local.date()
    # Fires since Colombo midnight (covers "today"); last-24h if before noon
    # is unnecessary — EOD window is always after close.
    since = datetime.combine(on_date, time(0, 0), tzinfo=_COLOMBO)

    try:
        users = await storage.list_digest_users()
    except Exception:
        log.exception("digest_list_users_failed")
        return DigestRunResult(candidates=0, sent=0, skipped=0, errors=1)

    sent = 0
    skipped = 0
    errors = 0
    for u in users:
        user_id = u.get("id")
        telegram_id = u.get("telegram_id")
        if not isinstance(user_id, int) or isinstance(user_id, bool):
            skipped += 1
            continue
        if not isinstance(telegram_id, int) or isinstance(telegram_id, bool):
            skipped += 1
            continue
        if telegram_id <= 0:
            skipped += 1
            continue

        try:
            claimed = await storage.claim_digest_send(user_id, on_date)
        except Exception:
            log.exception("digest_claim_failed", user_id=user_id)
            errors += 1
            continue
        if not claimed:
            skipped += 1
            continue

        try:
            body = await build_user_digest(
                storage, user_id=user_id, on_date=on_date, since=since
            )
            result = _normalize_send_result(await send(telegram_id, body))
            if result is SendResult.OK:
                sent += 1
                log.info("digest_sent", user_id=user_id, telegram_id=telegram_id)
            else:
                # Leave last_digest_on set to avoid retry storms; ops can clear.
                errors += 1
                log.warning(
                    "digest_send_failed",
                    user_id=user_id,
                    telegram_id=telegram_id,
                    result=str(result),
                )
        except Exception:
            errors += 1
            log.exception("digest_user_failed", user_id=user_id)

    return DigestRunResult(
        candidates=len(users),
        sent=sent,
        skipped=skipped,
        errors=errors,
        outside_window=False,
    )


async def maybe_run_eod_digest(
    storage: DigestStorage,
    send: SendFunc,
    *,
    now: datetime | None = None,
) -> DigestRunResult | None:
    """Poller hook: no-op outside the window; otherwise run once."""
    if not in_digest_window(now):
        return None
    return await run_eod_digest(storage, send, now=now, force=False)
