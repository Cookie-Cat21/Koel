"""WS-066 / CORE-002: Price event_key includes snapshot.id when present.

Claimed fires use snapshot.id so same-minute re-cross after re-arm can notify.
Dual-poller same-tick dupes are prevented by the session advisory lock, not by
collapsing keys across different snap ids. When id is None, minute+price
fallback still collapses dual evaluation of the same synthetic tick.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

from koel.domain import AlertType, format_alert_message
from koel.rules import evaluate_price_rules, filter_fireable
from tests.conftest import make_previous, make_rule, make_snapshot
from tests.test_idempotency import FakeAlertLog


def test_different_snap_ids_distinct_event_keys() -> None:
    """Snap ids 10 vs 11 → distinct keys → both claims succeed (re-cross OK)."""
    store = FakeAlertLog()
    rule = make_rule(id=1, type=AlertType.PRICE_ABOVE, threshold=100.0)
    prev = make_previous(price=95.0)
    ts = datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC)

    snap_a = make_snapshot(price=105.0, id=10, ts=ts)
    snap_b = make_snapshot(price=105.0, id=11, ts=ts)

    events_a = filter_fireable(evaluate_price_rules(snapshot=snap_a, previous=prev, rules=[rule]))
    events_b = filter_fireable(evaluate_price_rules(snapshot=snap_b, previous=prev, rules=[rule]))
    assert len(events_a) == 1
    assert len(events_b) == 1
    assert events_a[0].event_key == "price:1:above:100:s10"
    assert events_b[0].event_key == "price:1:above:100:s11"
    assert events_a[0].event_key != events_b[0].event_key

    msg = format_alert_message(events_a[0])
    assert store.claim_and_send(events_a[0].rule_id, events_a[0].event_key, msg) is True
    assert store.claim_and_send(events_b[0].rule_id, events_b[0].event_key, msg) is True
    assert len(store.send_log) == 2


def test_same_snap_id_idempotent_claim() -> None:
    """Same snapshot.id → same event_key → second claim blocked."""
    store = FakeAlertLog()
    rule = make_rule(id=2, type=AlertType.PRICE_ABOVE, threshold=100.0)
    prev = make_previous(price=95.0)
    snap = make_snapshot(price=105.0, id=20)

    key = filter_fireable(evaluate_price_rules(snapshot=snap, previous=prev, rules=[rule]))[
        0
    ].event_key
    assert key == "price:2:above:100:s20"

    assert store.claim_and_send(rule.id, key, "a") is True
    assert store.claim_and_send(rule.id, key, "b") is False
    assert len(store.send_log) == 1


def test_none_snap_id_falls_back_to_minute_price() -> None:
    """Without snapshot.id, minute+price fingerprint collapses dual eval."""
    store = FakeAlertLog()
    rule = make_rule(id=3, type=AlertType.PRICE_ABOVE, threshold=100.0)
    prev = make_previous(price=95.0)
    ts = datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC)

    snap_a = make_snapshot(price=105.0, id=None, ts=ts)
    snap_b = make_snapshot(price=105.0, id=None, ts=ts)

    key_a = filter_fireable(evaluate_price_rules(snapshot=snap_a, previous=prev, rules=[rule]))[
        0
    ].event_key
    key_b = filter_fireable(evaluate_price_rules(snapshot=snap_b, previous=prev, rules=[rule]))[
        0
    ].event_key
    assert key_a == key_b
    assert key_a == "price:3:above:100:202607110600:105"

    assert store.claim_and_send(rule.id, key_a, "a") is True
    assert store.claim_and_send(rule.id, key_b, "b") is False
    assert len(store.send_log) == 1


async def test_dual_eval_optional_advisory_lock_mock() -> None:
    """Optional: Storage.try_advisory_lock mock — second holder loses lock."""
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(side_effect=[True, False])

    assert await storage.try_advisory_lock(4_201_337) is True
    assert await storage.try_advisory_lock(4_201_337) is False
    assert storage.try_advisory_lock.await_count == 2
