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
    BigPrint,
    Disclosure,
    MarketNotice,
    OrderBookSnapshot,
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


def _pct_from_previous_close(price: float | None, previous_close: float | None) -> float | None:
    """Compute daily percent move from previous close when CSE omits it."""
    if not (_finite(price) and _finite(previous_close)) or previous_close == 0:
        return None
    return ((price - previous_close) / previous_close) * 100.0


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


def _event_key_day(prefix: str, rule: AlertRule, snapshot: PriceSnapshot) -> str | None:
    """One fire per Colombo calendar day for activity rules."""
    try:
        day = snapshot.ts.astimezone(_COLOMBO).date().isoformat()
    except (OverflowError, ValueError, OSError):
        return None
    return f"{prefix}:{rule.id}:{day}"


def _volume_multiple_met(
    *,
    current: float | None,
    avg: float | None,
    threshold: float,
) -> bool:
    """True when current volume is at least threshold × recent average."""
    if not (_finite(current) and _finite(avg) and _finite(threshold)):
        return False
    if avg <= 0 or threshold <= 0 or current is None or avg is None:
        return False
    return current >= threshold * avg


def _signed_change_pct(snapshot: PriceSnapshot, curr: float) -> float | None:
    pct = snapshot.change_pct
    if _finite(pct):
        return pct
    return _pct_from_previous_close(curr, snapshot.previous_close)


def _gap_pct(snapshot: PriceSnapshot) -> float | None:
    """|open − previous_close| / previous_close × 100."""
    if not (_finite(snapshot.open) and _finite(snapshot.previous_close)):
        return None
    assert snapshot.open is not None and snapshot.previous_close is not None
    if snapshot.previous_close == 0:
        return None
    return abs((snapshot.open - snapshot.previous_close) / snapshot.previous_close) * 100.0


def evaluate_price_rules(
    *,
    snapshot: PriceSnapshot,
    previous: PreviousPriceState,
    rules: list[AlertRule],
) -> list[AlertEvent]:
    """Evaluate price / move / volume / crossing / gap rules for one snapshot.

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
            pct_from_close = pct is None
            if pct_from_close:
                pct = _pct_from_previous_close(curr, snapshot.previous_close)
            if not _finite(pct):
                continue
            key = _event_key_move(rule, snapshot)
            if key is None:
                continue
            if key in previous.move_fired_keys:
                continue
            # Crossing semantics on |pct|: require previous |pct| below threshold
            prev_pct = previous.change_pct
            if not _finite(prev_pct) and pct_from_close:
                prev_pct = _pct_from_previous_close(previous.price, snapshot.previous_close)
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

        elif rule.type in (
            AlertType.VOLUME_SPIKE,
            AlertType.VOLUME_UP,
            AlertType.VOLUME_DOWN,
        ):
            if rule.threshold is None or not math.isfinite(rule.threshold):
                continue
            thr = abs(rule.threshold)
            prefix = {
                AlertType.VOLUME_SPIKE: "volspike",
                AlertType.VOLUME_UP: "volup",
                AlertType.VOLUME_DOWN: "voldown",
            }[rule.type]
            key = _event_key_day(prefix, rule, snapshot)
            if key is None or key in previous.activity_fired_keys:
                continue
            if not _volume_multiple_met(
                current=snapshot.volume,
                avg=previous.avg_volume,
                threshold=thr,
            ):
                continue
            signed = _signed_change_pct(snapshot, curr)
            if rule.type == AlertType.VOLUME_UP:
                if not _finite(signed) or signed is None or signed <= 0:
                    continue
                direction = "up"
            elif rule.type == AlertType.VOLUME_DOWN:
                if not _finite(signed) or signed is None or signed >= 0:
                    continue
                direction = "down"
            else:
                direction = None
            vol = snapshot.volume if _finite(snapshot.volume) else 0.0
            avg = previous.avg_volume if _finite(previous.avg_volume) else 0.0
            mult = (vol / avg) if avg > 0 else 0.0
            if direction is None:
                trigger = (
                    f"unusual volume {mult:.1f}× recent avg "
                    f"({vol:,.0f} vs {avg:,.0f}; threshold {thr:g}×)"
                )
            else:
                trigger = (
                    f"heavy volume {direction} {mult:.1f}× avg "
                    f"({vol:,.0f}; price {signed:+.2f}%; threshold {thr:g}×)"
                )
            events.append(
                AlertEvent(
                    rule_id=rule.id,
                    user_id=rule.user_id,
                    telegram_id=rule.telegram_id,
                    symbol=rule.symbol,
                    type=rule.type,
                    threshold=thr,
                    trigger=trigger,
                    current_price=curr,
                    snapshot_id=snapshot.id,
                    event_key=key,
                )
            )

        elif rule.type == AlertType.CROSSING_VOLUME:
            if rule.threshold is None or not math.isfinite(rule.threshold):
                continue
            thr = abs(rule.threshold)
            key = _event_key_day("xvol", rule, snapshot)
            if key is None or key in previous.activity_fired_keys:
                continue
            if not _volume_multiple_met(
                current=snapshot.crossing_volume,
                avg=previous.avg_crossing_volume,
                threshold=thr,
            ):
                continue
            xvol = snapshot.crossing_volume if _finite(snapshot.crossing_volume) else 0.0
            xavg = (
                previous.avg_crossing_volume
                if _finite(previous.avg_crossing_volume)
                else 0.0
            )
            mult = (xvol / xavg) if xavg > 0 else 0.0
            events.append(
                AlertEvent(
                    rule_id=rule.id,
                    user_id=rule.user_id,
                    telegram_id=rule.telegram_id,
                    symbol=rule.symbol,
                    type=rule.type,
                    threshold=thr,
                    trigger=(
                        f"crossing volume {mult:.1f}× recent avg "
                        f"({xvol:,.0f} vs {xavg:,.0f}; threshold {thr:g}×)"
                    ),
                    current_price=curr,
                    snapshot_id=snapshot.id,
                    event_key=key,
                )
            )

        elif rule.type == AlertType.GAP:
            if rule.threshold is None or not math.isfinite(rule.threshold):
                continue
            thr = abs(rule.threshold)
            key = _event_key_day("gap", rule, snapshot)
            if key is None or key in previous.activity_fired_keys:
                continue
            gap = _gap_pct(snapshot)
            if not _finite(gap) or gap is None:
                continue
            # First observation of the day can fire once gap already exceeds thr
            # (open is set early); still day-bucketed via event_key.
            if gap < thr:
                continue
            assert snapshot.open is not None and snapshot.previous_close is not None
            direction = "up" if snapshot.open >= snapshot.previous_close else "down"
            events.append(
                AlertEvent(
                    rule_id=rule.id,
                    user_id=rule.user_id,
                    telegram_id=rule.telegram_id,
                    symbol=rule.symbol,
                    type=rule.type,
                    threshold=thr,
                    trigger=(
                        f"gap {direction} {gap:.2f}% "
                        f"(open {snapshot.open:.2f} vs prev close "
                        f"{snapshot.previous_close:.2f}; threshold {thr:.2f}%)"
                    ),
                    current_price=curr,
                    snapshot_id=snapshot.id,
                    event_key=key,
                )
            )

    return events


def evaluate_big_print_rules(
    *,
    print_: BigPrint,
    rules: list[AlertRule],
) -> list[AlertEvent]:
    """Fire when a day-tape print quantity meets/exceeds the rule threshold."""
    events: list[AlertEvent] = []
    if not isinstance(print_.external_id, str) or not print_.external_id.strip():
        return events
    if not _finite(print_.quantity) or print_.quantity <= 0:
        return events
    for rule in rules:
        if not rule.active or rule.type != AlertType.BIG_PRINT:
            continue
        if rule.symbol != print_.symbol:
            continue
        if rule.threshold is None or not math.isfinite(rule.threshold):
            continue
        thr = abs(rule.threshold)
        if print_.quantity < thr:
            continue
        # Fail-closed backfill gate: only prints seen after rule creation.
        if rule.created_at is None:
            continue
        created = _safe_utc_aware(rule.created_at)
        seen = _safe_utc_aware(print_.seen_at) if print_.seen_at is not None else None
        traded = _safe_utc_aware(print_.traded_at) if print_.traded_at is not None else None
        if created is None:
            continue
        gate_ts = traded or seen
        if gate_ts is not None and gate_ts <= created:
            continue
        px = print_.price if _finite(print_.price) else None
        events.append(
            AlertEvent(
                rule_id=rule.id,
                user_id=rule.user_id,
                telegram_id=rule.telegram_id,
                symbol=rule.symbol,
                type=rule.type,
                threshold=thr,
                trigger=(
                    f"big print {print_.quantity:,.0f} shares"
                    + (f" @ {px:.2f}" if px is not None else "")
                    + f" (threshold {thr:,.0f})"
                ),
                current_price=px,
                snapshot_id=None,
                event_key=f"bigprint:{rule.id}:{print_.external_id}",
            )
        )
    return events


_NOTICE_TYPE_TO_ALERT = {
    "buy_in": AlertType.BUY_IN,
    "non_compliance": AlertType.NON_COMPLIANCE,
    "halt": AlertType.HALT,
}


def evaluate_notice_rules(
    *,
    notice: MarketNotice,
    rules: list[AlertRule],
) -> list[AlertEvent]:
    """Fire buy-in / non-compliance / halt rules for a newly seen market notice."""
    events: list[AlertEvent] = []
    if not isinstance(notice.external_id, str) or not notice.external_id.strip():
        return events
    alert_type = _NOTICE_TYPE_TO_ALERT.get(notice.notice_type)
    if alert_type is None:
        return events
    published = _safe_utc_aware(notice.published_at)
    if published is None or published <= datetime(1970, 1, 1, tzinfo=UTC):
        return events
    for rule in rules:
        if not rule.active or rule.type != alert_type:
            continue
        # Halt notices are market-wide; buy-in / non-compliance need symbol match.
        if alert_type == AlertType.HALT:
            pass
        else:
            if notice.symbol is None or rule.symbol != notice.symbol:
                continue
        if rule.created_at is None:
            continue
        created = _safe_utc_aware(rule.created_at)
        if created is None or published <= created:
            continue
        title = notice.title if isinstance(notice.title, str) else "notice"
        prefix = {
            AlertType.BUY_IN: "buy-in board",
            AlertType.NON_COMPLIANCE: "non-compliance",
            AlertType.HALT: "market notice",
        }[alert_type]
        events.append(
            AlertEvent(
                rule_id=rule.id,
                user_id=rule.user_id,
                telegram_id=rule.telegram_id,
                symbol=rule.symbol,
                type=rule.type,
                threshold=None,
                trigger=f"{prefix}: {title}",
                current_price=None,
                disclosure_url=notice.url,
                disclosure_title=title,
                snapshot_id=None,
                event_key=f"{notice.notice_type}:{rule.id}:{notice.external_id}",
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
    # Fail closed — non-string category used to soft-accept via str()
    # (ints/objects became "123"/"<...>" and could false-match filters).
    if not isinstance(haystack, str):
        return False
    hay = haystack
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


def evaluate_order_book_rules(
    *,
    book: OrderBookSnapshot,
    rules: list[AlertRule],
    fired_keys: set[str] | None = None,
) -> list[AlertEvent]:
    """Fire when public order-book bid/ask totals are imbalanced.

    ``bid_heavy``: total_bids / total_asks >= threshold
    ``ask_heavy``: total_asks / total_bids >= threshold

    Day-bucketed like volume alerts. Requires both sides > 0.
    """
    events: list[AlertEvent] = []
    claimed = fired_keys or set()
    if not (_finite(book.total_bids) and _finite(book.total_asks)):
        return events
    if book.total_bids <= 0 or book.total_asks <= 0:
        return events
    try:
        day = book.ts.astimezone(_COLOMBO).date().isoformat()
    except (OverflowError, ValueError, OSError):
        return events

    for rule in rules:
        if not rule.active or rule.symbol != book.symbol:
            continue
        if rule.type not in (AlertType.BID_HEAVY, AlertType.ASK_HEAVY):
            continue
        if rule.threshold is None or not math.isfinite(rule.threshold):
            continue
        thr = abs(rule.threshold)
        if thr <= 0:
            continue
        if rule.type == AlertType.BID_HEAVY:
            ratio = book.total_bids / book.total_asks
            prefix = "bidheavy"
            label = "bid-heavy book"
        else:
            ratio = book.total_asks / book.total_bids
            prefix = "askheavy"
            label = "ask-heavy book"
        key = f"{prefix}:{rule.id}:{day}"
        if key in claimed:
            continue
        if ratio < thr:
            continue
        events.append(
            AlertEvent(
                rule_id=rule.id,
                user_id=rule.user_id,
                telegram_id=rule.telegram_id,
                symbol=rule.symbol,
                type=rule.type,
                threshold=thr,
                trigger=(
                    f"{label} {ratio:.2f}× "
                    f"(bids {book.total_bids:,.0f} / asks {book.total_asks:,.0f}; "
                    f"threshold {thr:g}×)"
                ),
                current_price=book.best_bid,
                snapshot_id=None,
                event_key=key,
            )
        )
    return events


def filter_fireable(events: list[AlertEvent]) -> list[AlertEvent]:
    """Drop rearm-only events from the notify path (arming updates still apply)."""
    return [e for e in events if e.trigger != "rearm"]
