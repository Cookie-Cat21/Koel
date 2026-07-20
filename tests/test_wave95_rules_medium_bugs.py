"""Wave95: medium+ rules/domain/health correctness bugs.

Daily-move fallback must use previous price + previous close when CSE omits
``change_pct`` on both adjacent snapshots; otherwise a real crossing is missed.
"""

from __future__ import annotations

from koel.domain import AlertType
from koel.rules import evaluate_price_rules, filter_fireable
from tests.conftest import make_previous, make_rule, make_snapshot


def test_daily_move_fallback_computes_previous_pct_from_previous_price() -> None:
    rule = make_rule(id=95, type=AlertType.DAILY_MOVE, threshold=3.0)
    snapshot = make_snapshot(price=104.0, previous_close=100.0, change_pct=None, id=9500)

    events = filter_fireable(
        evaluate_price_rules(
            snapshot=snapshot,
            previous=make_previous(price=101.0, change_pct=None),
            rules=[rule],
        )
    )

    assert len(events) == 1
    assert events[0].trigger == "daily move up 4.00% (threshold 3.00%)"
    assert events[0].event_key == "move:95:2026-07-11"
