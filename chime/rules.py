"""Alert rule engine: pure functions over (previous_state, new_snapshot) → events.

Crossing semantics: fire on state transition vs previous snapshot, not level checks.
No I/O inside evaluation.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import TypeGuard
from zoneinfo import ZoneInfo

from chime.domain import (
    AlertEvent,
    AlertRule,
    AlertType,
    Disclosure,
    PreviousPriceState,
    PriceSnapshot,
)

_COLOMBO = ZoneInfo("Asia/Colombo")


def _as_utc_aware(dt: datetime) -> datetime:
    """Normalize naive or aware datetimes to UTC-aware for safe comparison."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _finite(value: float | None) -> TypeGuard[float]:
    """True when value is a real finite float (not None / NaN / ±Inf)."""
    return value is not None and math.isfinite(value)


def crossed_above(prev: float | None, curr: float, threshold: float) -> bool:
    """True iff price transitioned from below threshold to at/above threshold."""
    if prev is None or not (_finite(prev) and _finite(curr) and _finite(threshold)):
        return False
    return prev < threshold <= curr


def crossed_below(prev: float | None, curr: float, threshold: float) -> bool:
    """True iff price transitioned from above threshold to at/below threshold."""
    if prev is None or not (_finite(prev) and _finite(curr) and _finite(threshold)):
        return False
    return prev > threshold >= curr


def _event_key_price(rule: AlertRule, snapshot: PriceSnapshot) -> str:
    """Idempotency key for a claimed price crossing.

    Preferred form includes snapshot.id so a same-minute re-cross after re-arm
    (new snapshot row) can fire. Dual-poller duplicate ticks are prevented by
    the session advisory lock, not by collapsing keys across snap ids.

    When snapshot.id is None (pre-persist / synthetic), fall back to a
    minute+price fingerprint so dual evaluation of the same tick still
    collides on alert_log UNIQUE(rule_id, event_key).
    """
    side = "above" if rule.type == AlertType.PRICE_ABOVE else "below"
    thr = rule.threshold if rule.threshold is not None else 0.0
    if snapshot.id is not None:
        return f"price:{rule.id}:{side}:{thr:g}:s{snapshot.id}"
    minute = snapshot.ts.strftime("%Y%m%d%H%M")
    return f"price:{rule.id}:{side}:{thr:g}:{minute}:{snapshot.price:g}"


def _event_key_move(rule: AlertRule, snapshot: PriceSnapshot) -> str | None:
    """One daily-move fire per Colombo calendar day (not UTC midnight).

    Returns None when the snapshot timestamp cannot be converted (extreme /
    overflow offsets) so callers fail closed instead of raising.
    """
    try:
        day = snapshot.ts.astimezone(_COLOMBO).date().isoformat()
    except (OverflowError, ValueError, OSError):
        return None
    return f"move:{rule.id}:{day}"


def _event_key_disclosure(rule: AlertRule, disclosure: Disclosure) -> str:
    return f"disclosure:{rule.id}:{disclosure.external_id}"


def evaluate_price_rules(
    *,
    snapshot: PriceSnapshot,
    previous: PreviousPriceState,
    rules: list[AlertRule],
) -> list[AlertEvent]:
    """Evaluate price_above / price_below / daily_move rules for one snapshot.

    Non-finite prices / thresholds / pcts and unconvertible timestamps fail
    closed (skip the rule, never raise).
    """
    events: list[AlertEvent] = []
    prev_price = previous.price
    curr = snapshot.price
    if not _finite(curr):
        return events

    for rule in rules:
        if not rule.active or rule.symbol != snapshot.symbol:
            continue

        if rule.type == AlertType.PRICE_ABOVE:
            if rule.threshold is None or not math.isfinite(rule.threshold):
                continue
            thr = rule.threshold
            if rule.armed and crossed_above(prev_price, curr, thr):
                events.append(
                    AlertEvent(
                        rule_id=rule.id,
                        user_id=rule.user_id,
                        telegram_id=rule.telegram_id,
                        symbol=rule.symbol,
                        type=rule.type,
                        threshold=thr,
                        trigger=f"price crossed above {thr:.2f}",
                        current_price=curr,
                        snapshot_id=snapshot.id,
                        event_key=_event_key_price(rule, snapshot),
                        set_armed=False,
                    )
                )
            elif not rule.armed and curr < thr:
                events.append(
                    AlertEvent(
                        rule_id=rule.id,
                        user_id=rule.user_id,
                        telegram_id=rule.telegram_id,
                        symbol=rule.symbol,
                        type=rule.type,
                        threshold=thr,
                        trigger="rearm",
                        current_price=curr,
                        snapshot_id=snapshot.id,
                        event_key=f"rearm:{rule.id}:{snapshot.id}",
                        set_armed=True,
                    )
                )

        elif rule.type == AlertType.PRICE_BELOW:
            if rule.threshold is None or not math.isfinite(rule.threshold):
                continue
            thr = rule.threshold
            if rule.armed and crossed_below(prev_price, curr, thr):
                events.append(
                    AlertEvent(
                        rule_id=rule.id,
                        user_id=rule.user_id,
                        telegram_id=rule.telegram_id,
                        symbol=rule.symbol,
                        type=rule.type,
                        threshold=thr,
                        trigger=f"price crossed below {thr:.2f}",
                        current_price=curr,
                        snapshot_id=snapshot.id,
                        event_key=_event_key_price(rule, snapshot),
                        set_armed=False,
                    )
                )
            elif not rule.armed and curr > thr:
                events.append(
                    AlertEvent(
                        rule_id=rule.id,
                        user_id=rule.user_id,
                        telegram_id=rule.telegram_id,
                        symbol=rule.symbol,
                        type=rule.type,
                        threshold=thr,
                        trigger="rearm",
                        current_price=curr,
                        snapshot_id=snapshot.id,
                        event_key=f"rearm:{rule.id}:{snapshot.id}",
                        set_armed=True,
                    )
                )

        elif rule.type == AlertType.DAILY_MOVE:
            if rule.threshold is None or not math.isfinite(rule.threshold):
                continue
            thr = abs(rule.threshold)
            pct = snapshot.change_pct
            if pct is None and snapshot.previous_close not in (None, 0):
                pc = snapshot.previous_close
                if _finite(pc) and pc != 0:
                    pct = ((curr - pc) / pc) * 100.0
            if not _finite(pct):
                continue
            key = _event_key_move(rule, snapshot)
            if key is None:
                continue
            if key in previous.move_fired_keys:
                continue
            # Crossing semantics on |pct|: require previous |pct| below threshold
            prev_pct = previous.change_pct
            if not _finite(prev_pct):
                # Baseline only — do not fire on first observation / already-exceeded
                continue
            if abs(prev_pct) < thr <= abs(pct):
                direction = "up" if pct >= 0 else "down"
                events.append(
                    AlertEvent(
                        rule_id=rule.id,
                        user_id=rule.user_id,
                        telegram_id=rule.telegram_id,
                        symbol=rule.symbol,
                        type=rule.type,
                        threshold=thr,
                        trigger=f"daily move {direction} {pct:.2f}% (threshold {thr:.2f}%)",
                        current_price=curr,
                        snapshot_id=snapshot.id,
                        event_key=key,
                    )
                )

    return events


def _disclosure_category_matches(rule: AlertRule, disclosure: Disclosure) -> bool:
    """If rule.category is set, require disclosure.category contains it (case-insensitive)."""
    # Non-string category → treat as unrestricted (filter only; never throw).
    if not isinstance(rule.category, str):
        return True
    needle = rule.category.strip()
    if not needle:
        return True
    haystack = disclosure.category
    if haystack is None:
        return False
    hay = str(haystack)
    if not hay.strip():
        return False
    return needle.casefold() in hay.casefold()


def _safe_utc_aware(dt: datetime) -> datetime | None:
    """UTC-normalize; return None on out-of-range / unconvertible timestamps."""
    try:
        return _as_utc_aware(dt)
    except (OverflowError, ValueError, OSError):
        return None


def evaluate_disclosure_rules(
    *,
    disclosure: Disclosure,
    rules: list[AlertRule],
) -> list[AlertEvent]:
    """Fire disclosure rules for newly seen announcements on watched symbols.

    Skips announcements published at or before the rule's created_at so historical
    backfill never floods Telegram. Missing rule.created_at fails closed (no fire).
    Undated CSE rows (Unix-epoch published_at) and empty external_id never fire.
    Optional rule.category filters by case-insensitive substring on disclosure.category.
    Weird / unconvertible timestamps fail closed (never raise).
    """
    events: list[AlertEvent] = []
    if not isinstance(disclosure.external_id, str) or not disclosure.external_id.strip():
        return events
    published = _safe_utc_aware(disclosure.published_at)
    if published is None:
        return events
    # Adapter stamps missing/non-positive createdDate as Unix epoch — never fire.
    if published <= datetime(1970, 1, 1, tzinfo=UTC):
        return events
    for rule in rules:
        if not rule.active:
            continue
        if rule.type != AlertType.DISCLOSURE:
            continue
        if rule.symbol != disclosure.symbol:
            continue
        # Fail-closed: without created_at we cannot gate backfill safely.
        if rule.created_at is None:
            continue
        created = _safe_utc_aware(rule.created_at)
        if created is None:
            continue
        if published <= created:
            continue
        if not _disclosure_category_matches(rule, disclosure):
            continue
        events.append(
            AlertEvent(
                rule_id=rule.id,
                user_id=rule.user_id,
                telegram_id=rule.telegram_id,
                symbol=rule.symbol,
                type=rule.type,
                threshold=None,
                trigger=f"new disclosure: {disclosure.title}",
                current_price=None,
                disclosure_url=disclosure.url,
                disclosure_title=disclosure.title,
                disclosure_id=disclosure.id,
                snapshot_id=None,
                event_key=_event_key_disclosure(rule, disclosure),
            )
        )
    return events


def filter_fireable(events: list[AlertEvent]) -> list[AlertEvent]:
    """Drop rearm-only events from the notify path (arming updates still apply)."""
    return [e for e in events if e.trigger != "rearm"]
