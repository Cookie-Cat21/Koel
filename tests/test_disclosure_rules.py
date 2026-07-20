"""Disclosure / announcement rule evaluation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from koel.domain import AlertType
from koel.rules import evaluate_disclosure_rules
from tests.conftest import make_disclosure, make_rule

# Default rule created_at before default disclosure published_at (2026-07-11 06:00 UTC)
_RULE_CREATED = datetime(2026, 7, 11, 5, 0, 0, tzinfo=UTC)

# Wave10: weird category / timestamp corpus — evaluate_disclosure_rules must never raise.
_WEIRD_CATEGORIES: list[str | None] = [
    None,
    "",
    " ",
    "\t",
    "\n",
    "\r\n",
    "\x00",
    "\x01\x02",
    "\ufffd",
    "🚀",
    "ราคา",
    "مبلغ",
    "Financial\u200b",  # zero-width space
    "Dividend\ufeff",  # BOM
    "AGM\u00a0",  # nbsp
    "a" * 10_000,
    "FINANCIAL",
    "financial",
    "FiNaNcIaL",
    "İstanbul",  # dotted I
    "ß",
    "ﬆ",
    "ﬁ",
    "\u202eFinancial",  # RTL override
    "Financial\u202c",
    "\u0000Financial",
    "A\u0308",  # combining diaeresis
    "Ä",
    "℃",
    "Ⅷ",
    "' OR 1=1 --",
    '"; DROP TABLE alert_rules;--',
    "<script>alert(1)</script>",
    "{{7*7}}",
    "%s%s%s%s",
    "👍" * 100,
    "Financial Report",
    "Dividend",
    "   Financial   ",
]

_WEIRD_TIMESTAMPS: list[datetime] = [
    datetime(2026, 7, 11, 6, 0, 0, tzinfo=UTC),
    datetime(2026, 7, 11, 6, 0, 0),  # naive
    datetime(2026, 7, 11, 5, 0, 0, tzinfo=UTC),
    datetime(2026, 7, 11, 5, 0, 0),  # naive created-ish
    datetime(1970, 1, 1, tzinfo=UTC),
    datetime(1970, 1, 1),
    datetime(1969, 12, 31, 23, 59, 59, tzinfo=UTC),
    datetime(1, 1, 1),
    datetime(9999, 12, 31, 23, 59, 59, 999999),
    datetime(1, 1, 1, tzinfo=UTC),
    datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=UTC),
    # Extreme offsets — astimezone(UTC) can OverflowError without fail-closed.
    datetime(1, 1, 1, 0, 0, 0, tzinfo=timezone(timedelta(hours=14))),
    datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=timezone(timedelta(hours=-14))),
    datetime(2026, 7, 11, 6, 0, 0, tzinfo=timezone(timedelta(hours=14))),
    datetime(2026, 7, 11, 6, 0, 0, tzinfo=timezone(timedelta(hours=-12))),
    datetime(2026, 7, 11, 6, 0, 0, tzinfo=timezone(timedelta(hours=23, minutes=59))),
    datetime(2026, 7, 11, 6, 0, 0, tzinfo=ZoneInfo("Asia/Colombo")),
    datetime(2026, 7, 11, 6, 0, 0, tzinfo=ZoneInfo("Pacific/Kiritimati")),
    datetime(2026, 7, 11, 6, 0, 0, tzinfo=ZoneInfo("America/Adak")),
    datetime(2026, 7, 11, 0, 0, 0, tzinfo=ZoneInfo("Asia/Colombo")),
    datetime(2026, 7, 12, 23, 59, 59, 999999, tzinfo=UTC),
]


def test_new_disclosure_matching_symbol_fires() -> None:
    rule = make_rule(
        id=3,
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=_RULE_CREATED,
    )
    disc = make_disclosure(external_id="ext-42", symbol="JKH.N0000", title="AGM Notice")
    disc = disc.model_copy(update={"id": 77})
    events = evaluate_disclosure_rules(disclosure=disc, rules=[rule])
    assert len(events) == 1
    assert events[0].trigger == "new disclosure: AGM Notice"
    assert events[0].disclosure_url == disc.url
    assert events[0].disclosure_title == "AGM Notice"
    assert events[0].disclosure_id == 77


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


def test_new_rule_baseline_skips_historical_batch_fires_only_newer() -> None:
    """PASS1 / wave7: new disclosure rule must not flood ≥5 historical filings.

    Mirrors create_alert_rule's returned created_at watermark: every filing at or
    before that instant is baseline; only a strictly newer publish fires.
    """
    created = datetime(2026, 7, 11, 12, 0, 0, tzinfo=UTC)
    rule = make_rule(
        id=42,
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=created,
    )
    historical = [
        make_disclosure(
            external_id=f"hist-{i}",
            title=f"Old filing {i}",
            published_at=created - timedelta(days=i + 1),
        )
        for i in range(5)
    ]
    for disc in historical:
        assert evaluate_disclosure_rules(disclosure=disc, rules=[rule]) == []

    # Same-day filing still before the rule watermark → no fire.
    same_day_before = make_disclosure(
        external_id="hist-same-day",
        published_at=created - timedelta(minutes=1),
    )
    assert evaluate_disclosure_rules(disclosure=same_day_before, rules=[rule]) == []

    newer = make_disclosure(
        external_id="fresh-1",
        title="Post-baseline AGM",
        published_at=created + timedelta(minutes=1),
    )
    events = evaluate_disclosure_rules(disclosure=newer, rules=[rule])
    assert len(events) == 1
    assert events[0].event_key == "disclosure:42:fresh-1"
    assert events[0].disclosure_title == "Post-baseline AGM"


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


def test_epoch_published_at_never_fires() -> None:
    """Undated CSE rows stamped as Unix epoch must not alert."""
    rule = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC),
    )
    disc = make_disclosure(published_at=datetime(1970, 1, 1, tzinfo=UTC))
    assert evaluate_disclosure_rules(disclosure=disc, rules=[rule]) == []


def test_empty_external_id_never_fires() -> None:
    rule = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=_RULE_CREATED,
    )
    disc = make_disclosure(
        external_id="  ",
        published_at=datetime(2026, 7, 12, 6, 0, 0, tzinfo=UTC),
    )
    assert evaluate_disclosure_rules(disclosure=disc, rules=[rule]) == []


def test_disclosure_category_blank_haystack_no_fire() -> None:
    rule = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        category="Financial",
        created_at=_RULE_CREATED,
    )
    disc = make_disclosure(category="   ")
    assert evaluate_disclosure_rules(disclosure=disc, rules=[rule]) == []


@pytest.mark.parametrize("disc_category", _WEIRD_CATEGORIES, ids=lambda c: repr(c)[:60])
@pytest.mark.parametrize("rule_category", _WEIRD_CATEGORIES, ids=lambda c: repr(c)[:60])
def test_evaluate_disclosure_rules_fuzz_categories_never_raises(
    disc_category: str | None,
    rule_category: str | None,
) -> None:
    """Wave10: weird category pairs must not throw — only return a list."""
    rule = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        category=rule_category,
        created_at=_RULE_CREATED,
    )
    disc = make_disclosure(category=disc_category)
    try:
        events = evaluate_disclosure_rules(disclosure=disc, rules=[rule])
    except Exception as exc:  # pragma: no cover - failure path for the invariant
        pytest.fail(
            f"evaluate_disclosure_rules raised {type(exc).__name__}: {exc!r} "
            f"for disc_category={disc_category!r} rule_category={rule_category!r}"
        )
    assert isinstance(events, list)


@pytest.mark.parametrize("published_at", _WEIRD_TIMESTAMPS, ids=lambda t: repr(t)[:80])
@pytest.mark.parametrize("created_at", _WEIRD_TIMESTAMPS, ids=lambda t: repr(t)[:80])
def test_evaluate_disclosure_rules_fuzz_timestamps_never_raises(
    published_at: datetime,
    created_at: datetime,
) -> None:
    """Wave10: weird published_at × created_at pairs must not throw."""
    rule = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=created_at,
    )
    disc = make_disclosure(published_at=published_at)
    try:
        events = evaluate_disclosure_rules(disclosure=disc, rules=[rule])
    except Exception as exc:  # pragma: no cover
        pytest.fail(
            f"evaluate_disclosure_rules raised {type(exc).__name__}: {exc!r} "
            f"for published_at={published_at!r} created_at={created_at!r}"
        )
    assert isinstance(events, list)


def test_evaluate_disclosure_rules_fuzz_cartesian_categories_timestamps() -> None:
    """Wave10 property-ish: category × timestamp grid returns without raising."""
    # Sample a slice so CI stays fast while still mixing both axes.
    cats = _WEIRD_CATEGORIES[::3]
    stamps = _WEIRD_TIMESTAMPS[::2]
    for rule_cat in cats:
        for disc_cat in (None, "Financial Report", rule_cat):
            for published in stamps:
                for created in (_RULE_CREATED, stamps[0], stamps[-1]):
                    rule = make_rule(
                        type=AlertType.DISCLOSURE,
                        threshold=None,
                        category=rule_cat,
                        created_at=created,
                    )
                    disc = make_disclosure(
                        category=disc_cat,
                        published_at=published,
                    )
                    try:
                        events = evaluate_disclosure_rules(disclosure=disc, rules=[rule])
                    except Exception as exc:  # pragma: no cover
                        pytest.fail(
                            f"evaluate_disclosure_rules raised {type(exc).__name__}: {exc!r} "
                            f"rule_cat={rule_cat!r} disc_cat={disc_cat!r} "
                            f"published={published!r} created={created!r}"
                        )
                    assert isinstance(events, list)


def test_overflow_timestamp_fail_closed_no_fire() -> None:
    """Unconvertible extreme-offset timestamps must not raise and must not fire."""
    overflow_pub = datetime(1, 1, 1, 0, 0, 0, tzinfo=timezone(timedelta(hours=14)))
    rule = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=_RULE_CREATED,
    )
    disc = make_disclosure(published_at=overflow_pub)
    assert evaluate_disclosure_rules(disclosure=disc, rules=[rule]) == []

    overflow_created = datetime(
        9999, 12, 31, 23, 59, 59, 999999, tzinfo=timezone(timedelta(hours=-14))
    )
    rule2 = make_rule(
        type=AlertType.DISCLOSURE,
        threshold=None,
        created_at=overflow_created,
    )
    disc2 = make_disclosure(published_at=datetime(2026, 7, 12, 6, 0, 0, tzinfo=UTC))
    assert evaluate_disclosure_rules(disclosure=disc2, rules=[rule2]) == []
