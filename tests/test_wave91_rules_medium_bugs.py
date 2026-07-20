"""Wave91: medium+ rules/domain alert correctness bugs.

1. ``AlertRule.threshold`` must reject bool-as-float coercion
   (``True`` used to become ``1.0`` and fire bogus price alerts).
2. Price-state booleans must fail closed instead of becoming ``1.0`` baselines.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from koel.domain import AlertType, PreviousPriceState, PriceSnapshot
from koel.rules import evaluate_price_rules, filter_fireable
from tests.conftest import make_previous, make_rule, make_snapshot

ROOT = Path(__file__).resolve().parents[1]


def test_bool_threshold_does_not_soft_accept_as_one_lkr_crossing() -> None:
    poisoned = make_rule(
        id=91,
        type=AlertType.PRICE_ABOVE,
        threshold=True,  # type: ignore[arg-type]
        armed=True,
    )
    assert poisoned.threshold is None

    events = filter_fireable(
        evaluate_price_rules(
            snapshot=make_snapshot(price=1.5, id=9100),
            previous=make_previous(price=0.5),
            rules=[poisoned],
        )
    )
    assert events == []

    valid = make_rule(id=92, type=AlertType.PRICE_ABOVE, threshold=100.0, armed=True)
    valid_events = filter_fireable(
        evaluate_price_rules(
            snapshot=make_snapshot(price=100.5, id=9200),
            previous=make_previous(price=99.0),
            rules=[valid],
        )
    )
    assert len(valid_events) == 1
    assert valid_events[0].event_key == "price:92:above:100:s9200"


def test_bool_price_state_fails_closed_not_one_point_baseline() -> None:
    with pytest.raises(ValidationError, match="boolean is not a valid numeric value"):
        PriceSnapshot(
            symbol="JKH.N0000",
            price=True,  # type: ignore[arg-type]
            ts=datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
        )

    previous = PreviousPriceState(
        price=True,  # type: ignore[arg-type]
        change_pct=True,  # type: ignore[arg-type]
    )
    assert previous.price is None
    assert previous.change_pct is None

    rule = make_rule(id=93, type=AlertType.DAILY_MOVE, threshold=3.0)
    events = filter_fireable(
        evaluate_price_rules(
            snapshot=make_snapshot(price=105.0, change_pct=5.0, id=9300),
            previous=previous,
            rules=[rule],
        )
    )
    assert events == []

    src = (ROOT / "koel" / "domain.py").read_text(encoding="utf-8")
    assert "isinstance(value, bool)" in src
