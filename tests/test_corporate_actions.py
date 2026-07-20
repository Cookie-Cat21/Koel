"""Unit tests for share-split detect, parse, rules, and bot parse."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from koel.bot import parse_alert_args
from koel.corporate_actions import (
    CorporateAction,
    adjust_factor,
    cumulative_adjust_factor,
    detect_share_split_ratio,
    detect_splits_from_closes,
    is_split_disclosure,
    parse_split_hints,
)
from koel.domain import AlertRule, AlertType, Disclosure, PreviousPriceState, PriceSnapshot
from koel.rules import evaluate_price_rules, evaluate_share_split_disclosure_rules


def test_is_split_disclosure() -> None:
    assert is_split_disclosure("Share Sub-Division", "Notice")
    assert is_split_disclosure(None, "Subdivision of Shares 1:3")
    assert is_split_disclosure("Other", "Share Split of ABC")
    assert is_split_disclosure(None, "Consolidation of Shares")
    assert not is_split_disclosure("CASH DIVIDEND", "Interim Dividend")


def test_parse_split_hints_ratio() -> None:
    h = parse_split_hints("Share Sub-Division — 1:3")
    assert h.kind == "split"
    assert h.ratio_from == 1
    assert h.ratio_to == 3

    h2 = parse_split_hints("Consolidation of Shares 3 for 1")
    assert h2.kind == "consolidation"
    assert h2.ratio_from == 3
    assert h2.ratio_to == 1


def test_detect_jins_style_forward_split() -> None:
    hit = detect_share_split_ratio(127.75, 46.30)
    assert hit is not None
    assert hit.kind == "split"
    assert hit.n == 3
    assert hit.ratio_from == 1
    assert hit.ratio_to == 3


def test_detect_rejects_ordinary_crash() -> None:
    # ~20% drop — below min move and not a ratio cliff.
    assert detect_share_split_ratio(100.0, 80.0) is None
    # Large drop but far from ×2/×3 (100→58 ≈ 1.72×).
    assert detect_share_split_ratio(100.0, 58.0) is None


def test_detect_consolidation() -> None:
    hit = detect_share_split_ratio(50.0, 150.0)
    assert hit is not None
    assert hit.kind == "consolidation"
    assert hit.n == 3


def test_detect_from_closes() -> None:
    points = [
        (date(2026, 4, 8), 127.75),
        (date(2026, 4, 9), 46.30),
        (date(2026, 4, 10), 47.00),
    ]
    hits = detect_splits_from_closes(points)
    assert len(hits) == 1
    assert hits[0][0] == date(2026, 4, 9)
    assert hits[0][1].n == 3


def test_adjust_factor_and_cumulative() -> None:
    assert abs(adjust_factor(1, 3) - (1 / 3)) < 1e-12
    actions = [
        CorporateAction(
            symbol="JINS.N0000",
            effective_date=date(2026, 4, 9),
            kind="split",
            ratio_from=1,
            ratio_to=3,
        )
    ]
    # Before effective → scale by 1/3
    assert abs(cumulative_adjust_factor(actions, as_of=date(2026, 4, 8)) - (1 / 3)) < 1e-12
    # On/after → no scale
    assert cumulative_adjust_factor(actions, as_of=date(2026, 4, 9)) == 1.0


def test_parse_alert_split() -> None:
    parsed, err = parse_alert_args(["JINS.N0000", "split"])
    assert err is None
    assert parsed is not None
    assert parsed.alert_type == AlertType.SHARE_SPLIT
    assert parsed.threshold is None


def test_evaluate_price_share_split_rule() -> None:
    rule = AlertRule(
        id=1,
        user_id=1,
        telegram_id=9,
        symbol="JINS.N0000",
        type=AlertType.SHARE_SPLIT,
        threshold=None,
        active=True,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    snap = PriceSnapshot(
        symbol="JINS.N0000",
        price=46.30,
        previous_close=46.30,  # CSE often resets — must not block detect
        ts=datetime(2026, 4, 9, 5, 0, tzinfo=UTC),
        id=10,
    )
    prev = PreviousPriceState(price=127.75, activity_fired_keys=set())
    events = evaluate_price_rules(snapshot=snap, previous=prev, rules=[rule])
    assert len(events) == 1
    assert events[0].type == AlertType.SHARE_SPLIT
    assert "1:3" in events[0].trigger


def test_evaluate_share_split_disclosure_rule() -> None:
    rule = AlertRule(
        id=2,
        user_id=1,
        telegram_id=9,
        symbol="JINS.N0000",
        type=AlertType.SHARE_SPLIT,
        threshold=None,
        active=True,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    disc = Disclosure(
        symbol="JINS.N0000",
        external_id="ann-split-1",
        title="Share Sub-Division 1:3",
        category="Share Sub-Division",
        published_at=datetime(2026, 3, 15, tzinfo=UTC),
        seen_at=datetime(2026, 3, 15, tzinfo=UTC),
        url="https://www.cse.lk/announcements#split-1",
        id=99,
    )
    events = evaluate_share_split_disclosure_rules(disclosure=disc, rules=[rule])
    assert len(events) == 1
    assert "1:3" in events[0].trigger


def test_share_split_disclosure_ignores_old_published() -> None:
    rule = AlertRule(
        id=2,
        user_id=1,
        telegram_id=9,
        symbol="JINS.N0000",
        type=AlertType.SHARE_SPLIT,
        threshold=None,
        active=True,
        created_at=datetime(2026, 4, 1, tzinfo=UTC),
    )
    disc = Disclosure(
        symbol="JINS.N0000",
        external_id="ann-old",
        title="Share Sub-Division 1:3",
        category="Share Sub-Division",
        published_at=datetime(2026, 3, 15, tzinfo=UTC),
        seen_at=datetime(2026, 3, 15, tzinfo=UTC),
        url="https://www.cse.lk/announcements#old",
        id=98,
    )
    assert evaluate_share_split_disclosure_rules(disclosure=disc, rules=[rule]) == []


@pytest.mark.parametrize(
    "prev,curr",
    [
        (100.0, 50.0),  # exact 2:1
        (100.0, 25.0),  # 4:1
        (100.0, 10.0),  # 10:1
    ],
)
def test_common_forward_ratios(prev: float, curr: float) -> None:
    hit = detect_share_split_ratio(prev, curr)
    assert hit is not None
    assert hit.kind == "split"
