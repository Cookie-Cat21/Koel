"""WS-066: Dual-eval dedupe via crossing-stable event_key (no Postgres).

Two evaluate+claim cycles with different snapshot ids but the same
minute+price fingerprint must collapse to one notify. Does not prove
real pg_try_advisory_lock — only UNIQUE(rule_id, event_key) semantics.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from chime.domain import AlertType, format_alert_message
from chime.rules import evaluate_price_rules, filter_fireable
from tests.conftest import make_previous, make_rule, make_snapshot
from tests.test_idempotency import FakeAlertLog


def test_dual_eval_different_snap_ids_same_event_key_sends_once() -> None:
    """Snap ids 10 vs 11, same minute+price → one claim, one send."""
    store = FakeAlertLog()
    rule = make_rule(id=1, type=AlertType.PRICE_ABOVE, threshold=100.0)
    prev = make_previous(price=95.0)
    ts = datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC)

    snap_a = make_snapshot(price=105.0, id=10, ts=ts)
    snap_b = make_snapshot(price=105.0, id=11, ts=ts)

    events_a = filter_fireable(
        evaluate_price_rules(snapshot=snap_a, previous=prev, rules=[rule])
    )
    events_b = filter_fireable(
        evaluate_price_rules(snapshot=snap_b, previous=prev, rules=[rule])
    )
    assert len(events_a) == 1
    assert len(events_b) == 1
    assert events_a[0].event_key == events_b[0].event_key
    assert events_a[0].snapshot_id == 10
    assert events_b[0].snapshot_id == 11

    msg = format_alert_message(events_a[0])
    assert store.claim_and_send(events_a[0].rule_id, events_a[0].event_key, msg) is True
    assert store.claim_and_send(events_b[0].rule_id, events_b[0].event_key, msg) is False
    assert len(store.send_log) == 1


def test_dual_eval_different_minute_allows_two_keys() -> None:
    """Contrast: different UTC minute → distinct event_keys → two claims."""
    store = FakeAlertLog()
    rule = make_rule(id=2, type=AlertType.PRICE_ABOVE, threshold=100.0)
    prev = make_previous(price=95.0)
    ts0 = datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC)
    ts1 = ts0 + timedelta(minutes=1)

    snap_a = make_snapshot(price=105.0, id=20, ts=ts0)
    snap_b = make_snapshot(price=105.0, id=21, ts=ts1)

    key_a = filter_fireable(
        evaluate_price_rules(snapshot=snap_a, previous=prev, rules=[rule])
    )[0].event_key
    key_b = filter_fireable(
        evaluate_price_rules(snapshot=snap_b, previous=prev, rules=[rule])
    )[0].event_key
    assert key_a != key_b

    assert store.claim_and_send(rule.id, key_a, "a") is True
    assert store.claim_and_send(rule.id, key_b, "b") is True
    assert len(store.send_log) == 2


async def test_dual_eval_optional_advisory_lock_mock() -> None:
    """Optional: Storage.try_advisory_lock mock — second holder loses lock."""
    storage = AsyncMock()
    storage.try_advisory_lock = AsyncMock(side_effect=[True, False])

    assert await storage.try_advisory_lock(4_201_337) is True
    assert await storage.try_advisory_lock(4_201_337) is False
    assert storage.try_advisory_lock.await_count == 2
