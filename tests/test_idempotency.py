"""Pure claim-logic simulation — insert-first idempotency without Postgres."""

from __future__ import annotations

from dataclasses import dataclass, field

from chime.domain import AlertType, format_alert_message
from chime.rules import evaluate_price_rules, filter_fireable
from tests.conftest import make_previous, make_rule, make_snapshot


@dataclass
class ClaimRecord:
    id: int
    rule_id: int
    event_key: str
    message_text: str
    message_sent: bool = False


@dataclass
class FakeAlertLog:
    """In-memory stand-in for alert_log UNIQUE (rule_id, event_key)."""

    _rows: dict[tuple[int, str], ClaimRecord] = field(default_factory=dict)
    _next_id: int = 1
    send_log: list[str] = field(default_factory=list)

    def claim(self, rule_id: int, event_key: str, message_text: str) -> int | None:
        key = (rule_id, event_key)
        if key in self._rows:
            return None  # already claimed
        rec = ClaimRecord(
            id=self._next_id,
            rule_id=rule_id,
            event_key=event_key,
            message_text=message_text,
            message_sent=False,
        )
        self._next_id += 1
        self._rows[key] = rec
        return rec.id

    def mark_sent(self, log_id: int) -> None:
        for rec in self._rows.values():
            if rec.id == log_id:
                rec.message_sent = True
                return

    def unsent(self) -> list[ClaimRecord]:
        return [r for r in self._rows.values() if not r.message_sent]

    def claim_and_send(
        self,
        rule_id: int,
        event_key: str,
        message_text: str,
        *,
        send_ok: bool = True,
    ) -> bool:
        log_id = self.claim(rule_id, event_key, message_text)
        if log_id is None:
            return False
        if send_ok:
            self.send_log.append(message_text)
            self.mark_sent(log_id)
            return True
        return False

    def retry_unsent(self, *, send_ok: bool = True) -> int:
        sent = 0
        for rec in self.unsent():
            if send_ok:
                self.send_log.append(rec.message_text)
                self.mark_sent(rec.id)
                sent += 1
        return sent


def test_evaluate_claim_twice_sends_once() -> None:
    store = FakeAlertLog()
    rule = make_rule(id=1, type=AlertType.PRICE_ABOVE, threshold=100.0)
    snap = make_snapshot(price=105.0, id=50)
    prev = make_previous(price=95.0)

    events = filter_fireable(evaluate_price_rules(snapshot=snap, previous=prev, rules=[rule]))
    assert len(events) == 1
    event = events[0]
    msg = format_alert_message(event)

    assert store.claim_and_send(event.rule_id, event.event_key, msg) is True
    # Same snapshot / event_key again — insert-first claim returns None → no second send
    assert store.claim_and_send(event.rule_id, event.event_key, msg) is False
    assert len(store.send_log) == 1


def test_kill_and_restart_pending_send_once() -> None:
    """Claim succeeds, send fails → restart retries pending → third pass no dup."""
    store = FakeAlertLog()
    rule = make_rule(id=2, type=AlertType.PRICE_ABOVE, threshold=100.0)
    snap = make_snapshot(price=105.0, id=77)
    events = filter_fireable(
        evaluate_price_rules(
            snapshot=snap,
            previous=make_previous(price=95.0),
            rules=[rule],
        )
    )
    assert len(events) == 1
    event = events[0]
    msg = format_alert_message(event)

    # Run 1: claim but Telegram send fails
    assert store.claim_and_send(event.rule_id, event.event_key, msg, send_ok=False) is False
    assert len(store.unsent()) == 1
    assert store.send_log == []

    # Re-evaluate same condition (would produce same event_key) — claim blocked
    events2 = filter_fireable(
        evaluate_price_rules(
            snapshot=snap,
            previous=make_previous(price=95.0),
            rules=[rule],
        )
    )
    assert events2[0].event_key == event.event_key
    assert store.claim(event.rule_id, event.event_key, msg) is None

    # Run 2 (restart): drain pending unsent → sends once
    assert store.retry_unsent(send_ok=True) == 1
    assert len(store.send_log) == 1
    assert store.unsent() == []

    # Run 3: nothing pending, claim still blocked
    assert store.retry_unsent(send_ok=True) == 0
    assert store.claim(event.rule_id, event.event_key, msg) is None
    assert len(store.send_log) == 1
