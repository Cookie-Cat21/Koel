"""Disclosure / announcement rule evaluation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from chime.domain import AlertType
from chime.rules import evaluate_disclosure_rules
from tests.conftest import make_disclosure, make_rule

# Default rule created_at before default disclosure published_at (2026-07-11 06:00 UTC)
_RULE_CREATED = datetime(2026, 7, 11, 5, 0, 0, tzinfo=UTC)


def test_new_disclosure_matching_symbol_fires() -> None:
    rule = make_rule(
        id=3,
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=_RULE_CREATED,
    )
    disc = make_disclosure(external_id="ext-42", symbol="JKH.N0000", title="AGM Notice")
    events = evaluate_disclosure_rules(disclosure=disc, rules=[rule])
    assert len(events) == 1
    assert events[0].trigger == "new disclosure: AGM Notice"
    assert events[0].disclosure_url == disc.url
    assert events[0].disclosure_title == "AGM Notice"


def test_wrong_symbol_ignored() -> None:
    rule = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        symbol="COMB.N0000",
        created_at=_RULE_CREATED,
    )
    disc = make_disclosure(symbol="JKH.N0000")
    events = evaluate_disclosure_rules(disclosure=disc, rules=[rule])
    assert events == []


def test_inactive_disclosure_rule_ignored() -> None:
    rule = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        active=False,
        created_at=_RULE_CREATED,
    )
    disc = make_disclosure()
    assert evaluate_disclosure_rules(disclosure=disc, rules=[rule]) == []


def test_event_key_includes_external_id() -> None:
    rule = make_rule(
        id=7,
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=_RULE_CREATED,
    )
    disc = make_disclosure(external_id="ann-12345")
    events = evaluate_disclosure_rules(disclosure=disc, rules=[rule])
    assert len(events) == 1
    assert events[0].event_key == "disclosure:7:ann-12345"


def test_non_disclosure_rule_type_ignored() -> None:
    rule = make_rule(type=AlertType.PRICE_ABOVE, threshold=100.0, created_at=_RULE_CREATED)
    disc = make_disclosure()
    assert evaluate_disclosure_rules(disclosure=disc, rules=[rule]) == []


def test_disclosure_before_rule_created_at_no_fire() -> None:
    created = datetime(2026, 7, 11, 12, 0, 0, tzinfo=UTC)
    rule = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=created,
    )
    disc = make_disclosure(published_at=created - timedelta(hours=1))
    assert evaluate_disclosure_rules(disclosure=disc, rules=[rule]) == []


def test_disclosure_after_rule_created_at_fires() -> None:
    created = datetime(2026, 7, 11, 12, 0, 0, tzinfo=UTC)
    rule = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=created,
    )
    disc = make_disclosure(published_at=created + timedelta(minutes=5))
    events = evaluate_disclosure_rules(disclosure=disc, rules=[rule])
    assert len(events) == 1


def test_disclosure_equal_created_at_no_fire() -> None:
    created = datetime(2026, 7, 11, 12, 0, 0, tzinfo=UTC)
    rule = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=created,
    )
    disc = make_disclosure(published_at=created)
    assert evaluate_disclosure_rules(disclosure=disc, rules=[rule]) == []


def test_missing_rule_created_at_fail_closed() -> None:
    """WS-002: created_at=None must not fire (cannot safely gate backfill)."""
    rule = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=None,
    )
    disc = make_disclosure(published_at=datetime(2026, 7, 12, 6, 0, 0, tzinfo=UTC))
    assert evaluate_disclosure_rules(disclosure=disc, rules=[rule]) == []


def test_naive_vs_aware_created_at_compares_without_typeerror() -> None:
    """Naive rule.created_at and aware published_at must not raise TypeError."""
    rule = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=datetime(2026, 7, 11, 5, 0, 0),  # naive
    )
    disc = make_disclosure(
        published_at=datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
    )
    events = evaluate_disclosure_rules(disclosure=disc, rules=[rule])
    assert len(events) == 1


def test_naive_published_at_before_aware_created_at_no_fire() -> None:
    rule = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=datetime(2026, 7, 11, 12, 0, 0, tzinfo=UTC),
    )
    disc = make_disclosure(published_at=datetime(2026, 7, 11, 11, 0, 0))  # naive
    assert evaluate_disclosure_rules(disclosure=disc, rules=[rule]) == []


def test_disclosure_category_filter_match_fires() -> None:
    rule = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        category="Financial",
        created_at=_RULE_CREATED,
    )
    disc = make_disclosure(category="Financial Report", title="Q1 Results")
    events = evaluate_disclosure_rules(disclosure=disc, rules=[rule])
    assert len(events) == 1


def test_disclosure_category_filter_case_insensitive() -> None:
    rule = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        category="financial",
        created_at=_RULE_CREATED,
    )
    disc = make_disclosure(category="FINANCIAL REPORT")
    events = evaluate_disclosure_rules(disclosure=disc, rules=[rule])
    assert len(events) == 1


def test_disclosure_category_filter_mismatch_no_fire() -> None:
    rule = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        category="Dividend",
        created_at=_RULE_CREATED,
    )
    disc = make_disclosure(category="Financial Report")
    assert evaluate_disclosure_rules(disclosure=disc, rules=[rule]) == []


def test_disclosure_category_filter_missing_disclosure_category_no_fire() -> None:
    rule = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        category="Financial",
        created_at=_RULE_CREATED,
    )
    disc = make_disclosure(category=None)
    assert evaluate_disclosure_rules(disclosure=disc, rules=[rule]) == []


def test_disclosure_no_category_filter_matches_any() -> None:
    rule = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        category=None,
        created_at=_RULE_CREATED,
    )
    disc = make_disclosure(category="Anything")
    events = evaluate_disclosure_rules(disclosure=disc, rules=[rule])
    assert len(events) == 1


def test_disclosure_blank_category_filter_treated_as_any() -> None:
    rule = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        category="   ",
        created_at=_RULE_CREATED,
    )
    disc = make_disclosure(category=None)
    events = evaluate_disclosure_rules(disclosure=disc, rules=[rule])
    assert len(events) == 1
