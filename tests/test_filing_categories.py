"""Filing category tags + disclosure prefs gating."""

from __future__ import annotations

from datetime import UTC, datetime

from koel.domain import AlertType
from koel.filing_categories import (
    classify_filing,
    filing_tag_allowed,
    normalize_filing_tags,
)
from koel.rules import evaluate_disclosure_rules
from tests.conftest import make_disclosure, make_rule

_RULE_CREATED = datetime(2026, 7, 11, 5, 0, 0, tzinfo=UTC)


def test_classify_results_and_board() -> None:
    assert classify_filing(category="Financial", title="Interim Financial Statement") == "results"
    assert classify_filing(category=None, title="Board Meeting Outcome") == "board"
    assert classify_filing(category="Dividend", title="Final Dividend") == "corporate_action"
    assert classify_filing(category=None, title="Routine notice") == "other"


def test_normalize_and_allow() -> None:
    assert normalize_filing_tags(["Results", "board", "bogus"]) == ["results", "board"]
    assert filing_tag_allowed("results", []) is True
    assert filing_tag_allowed("results", ["board"]) is False
    assert filing_tag_allowed("board", ["board", "results"]) is True


def test_evaluate_disclosure_respects_user_prefs() -> None:
    disc = make_disclosure(
        symbol="COMB.N0000",
        external_id="ext-results-1",
        title="Interim Financial Statement Q1",
        category="Financial",
    )
    rule = make_rule(
        user_id=9,
        telegram_id=9001001,
        symbol="COMB.N0000",
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=_RULE_CREATED,
    )
    # Prefs exclude results → no fire.
    assert (
        evaluate_disclosure_rules(
            disclosure=disc,
            rules=[rule],
            category_prefs_by_user={9: ["board"]},
        )
        == []
    )
    # Prefs allow results → fire with results-day trigger.
    events = evaluate_disclosure_rules(
        disclosure=disc,
        rules=[rule],
        category_prefs_by_user={9: ["results"]},
    )
    assert len(events) == 1
    assert events[0].trigger.startswith("results-day filing:")
    # Unrestricted prefs (empty) still fire.
    assert evaluate_disclosure_rules(
        disclosure=disc,
        rules=[rule],
        category_prefs_by_user={9: []},
    )
