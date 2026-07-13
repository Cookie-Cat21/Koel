"""Wave87 (WS-087): clock skew — claim eligibility invariant.

Disclosure / price rules must key off snapshot & disclosure timestamps, not
host wall-clock windows. ±5m / ±1h host skew must not drop or double-fire
claims when data timestamps are fixed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from chime.domain import AlertType
from chime.rules import evaluate_disclosure_rules, evaluate_price_rules, filter_fireable
from tests.conftest import make_disclosure, make_previous, make_rule, make_snapshot

ROOT = Path(__file__).resolve().parents[1]
RULES_SRC = (ROOT / "chime" / "rules.py").read_text(encoding="utf-8")

_CREATED = datetime(2026, 7, 11, 12, 0, 0, tzinfo=UTC)
_TRADE_TS = datetime(2026, 7, 11, 5, 0, 0, tzinfo=UTC)  # ~10:30 SLT


def test_rules_module_has_no_wall_clock_now() -> None:
    """Claim eval must not call datetime.now (host skew cannot gate fires)."""
    assert "datetime.now" not in RULES_SRC


def test_disclosure_claim_uses_published_vs_created_not_wall_clock() -> None:
    """±5m / ±1h offsets on data stamps still gate correctly; wall clock unused."""
    rule = make_rule(
        id=87,
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=_CREATED,
    )
    for delta in (
        timedelta(minutes=5),
        timedelta(hours=1),
        -timedelta(minutes=5),
        -timedelta(hours=1),
    ):
        disc = make_disclosure(
            external_id=f"skew-{int(delta.total_seconds())}",
            published_at=_CREATED + delta,
        )
        events = evaluate_disclosure_rules(disclosure=disc, rules=[rule])
        if delta > timedelta(0):
            assert len(events) == 1
            assert events[0].event_key == f"disclosure:87:{disc.external_id}"
        else:
            assert events == []


def test_price_cross_claim_stable_under_snapshot_ts_skew() -> None:
    """Price above fire keys off prev/curr levels; ±1h snap.ts skew still fires."""
    rule = make_rule(id=87, type=AlertType.PRICE_ABOVE, threshold=100.0, armed=True)
    prev = make_previous(price=99.0)
    for delta in (timedelta(0), timedelta(minutes=5), timedelta(hours=1), -timedelta(hours=1)):
        snap = make_snapshot(id=8700, price=100.5, ts=_TRADE_TS + delta)
        events = filter_fireable(
            evaluate_price_rules(snapshot=snap, previous=prev, rules=[rule])
        )
        assert len(events) == 1
        assert events[0].event_key == "price:87:above:100:s8700"


def test_daily_move_day_key_uses_snapshot_ts_not_host_now() -> None:
    """Daily-move idempotency day is snapshot.ts in Colombo — fixed trade ts.

    Host wall clock is irrelevant; ±1h trade-time skew within the same Colombo
    calendar day must keep the same event_key (no double-fire under skew).
    """
    rule = make_rule(id=87, type=AlertType.DAILY_MOVE, threshold=3.0)
    prev = make_previous(price=100.0, change_pct=2.0)
    keys: set[str] = set()
    for delta in (timedelta(0), timedelta(minutes=5), timedelta(hours=1), -timedelta(hours=1)):
        snap = make_snapshot(id=8701, price=104.0, change_pct=4.0, ts=_TRADE_TS + delta)
        events = filter_fireable(
            evaluate_price_rules(snapshot=snap, previous=prev, rules=[rule])
        )
        assert len(events) == 1
        keys.add(events[0].event_key)
    assert keys == {"move:87:2026-07-11"}
