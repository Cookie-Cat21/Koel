"""Bot parse helpers — normalize_symbol, parse_alert_args, START/HELP budgets."""

from __future__ import annotations

import pytest

from chime.bot import (
    ALERT_USAGE,
    HELP_TEXT,
    START_TEXT,
    normalize_symbol,
    parse_alert_args,
)
from chime.domain import AlertType, disclaimer


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("JKH.N0000", "JKH.N0000"),
        ("  jkh.n0000  ", "JKH.N0000"),
        ("COMB", "COMB.N0000"),
        ("samp.N0000", "SAMP.N0000"),
    ],
)
def test_normalize_symbol_accepts(raw: str, expected: str) -> None:
    assert normalize_symbol(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "!!!", "this-is-not-a-symbol", "A" * 20],
)
def test_normalize_symbol_rejects(raw: str) -> None:
    assert normalize_symbol(raw) is None


@pytest.mark.parametrize(
    "args,alert_type,threshold",
    [
        (["JKH.N0000", "above", "100"], AlertType.PRICE_ABOVE, 100.0),
        (["JKH.N0000", "below", "50.5"], AlertType.PRICE_BELOW, 50.5),
        (["COMB.N0000", "move", "5"], AlertType.DAILY_MOVE, 5.0),
        (["SAMP.N0000", "move", "1,000"], AlertType.DAILY_MOVE, 1000.0),
        (["HNB.N0000", "disclosure"], AlertType.DISCLOSURE, None),
        (["JKH.N0000", "announcement"], AlertType.DISCLOSURE, None),
    ],
)
def test_parse_alert_args_variants(
    args: list[str],
    alert_type: AlertType,
    threshold: float | None,
) -> None:
    parsed, err = parse_alert_args(args)
    assert err is None
    assert parsed is not None
    assert parsed.alert_type == alert_type
    assert parsed.threshold == threshold


@pytest.mark.parametrize(
    "args,needle",
    [
        ([], "couldn't parse"),
        (["JKH.N0000"], "couldn't parse"),
        (["JKH.N0000", "above"], "need a number"),
        (["JKH.N0000", "above", "nope"], "positive finite number"),
        (["JKH.N0000", "below", "-1"], "positive finite number"),
        (["JKH.N0000", "sideways", "1"], "didn't catch that alert type"),
    ],
)
def test_parse_alert_args_kind_errors(args: list[str], needle: str) -> None:
    parsed, err = parse_alert_args(args)
    assert parsed is None
    assert err is not None
    assert needle.lower() in err.lower()


def test_alert_usage_lists_four_forms_and_nfa() -> None:
    """E17-B01: /alert usage errors show every supported kind plus NFA."""
    assert "/alert SYMBOL above PRICE" in ALERT_USAGE
    assert "/alert SYMBOL below PRICE" in ALERT_USAGE
    assert "/alert SYMBOL move PERCENT" in ALERT_USAGE
    assert "/alert SYMBOL disclosure" in ALERT_USAGE
    assert disclaimer() in ALERT_USAGE


def test_alert_unknown_kind_error_includes_full_usage_and_nfa() -> None:
    parsed, err = parse_alert_args(["JKH.N0000", "sideways", "1"])
    assert parsed is None
    assert err is not None
    for needle in (
        "/alert SYMBOL above PRICE",
        "/alert SYMBOL below PRICE",
        "/alert SYMBOL move PERCENT",
        "/alert SYMBOL disclosure",
        disclaimer(),
    ):
        assert needle in err


def test_start_text_is_short_and_mentions_colombo_disclaimer() -> None:
    lines = [ln for ln in START_TEXT.strip().splitlines() if ln.strip()]
    assert len(lines) <= 3
    assert "Colombo" in START_TEXT
    assert "/help" in START_TEXT
    assert "Browse dash" in START_TEXT
    assert "push stays here" in START_TEXT
    assert "[CATEGORY]" in START_TEXT
    assert "optional AI brief" in START_TEXT
    assert disclaimer() in START_TEXT
    assert "Not financial advice" in START_TEXT


def test_help_text_lists_alert_syntax_and_nfa() -> None:
    """E11-B01: /help lists alert forms + NFA one-liner (≤12 lines)."""
    lines = [ln for ln in HELP_TEXT.strip().splitlines() if ln.strip()]
    assert len(lines) <= 12
    assert "/watch SYMBOL" in HELP_TEXT
    assert "/alert SYMBOL above PRICE" in HELP_TEXT
    assert "/alert SYMBOL below PRICE" in HELP_TEXT
    assert "/alert SYMBOL move PERCENT" in HELP_TEXT
    assert "/alert SYMBOL disclosure" in HELP_TEXT
    assert "[CATEGORY]" in HELP_TEXT
    assert "/cancel ALERT_ID" in HELP_TEXT
    assert "/myalerts — active only" in HELP_TEXT
    assert "/brief SYMBOL" in HELP_TEXT
    assert "Browse dash" in HELP_TEXT
    assert "scenarios disabled" in HELP_TEXT
    assert "optional AI brief" in HELP_TEXT
    assert "Disclosure alerts:" in HELP_TEXT
    assert disclaimer() in HELP_TEXT
    assert "Not financial advice" in HELP_TEXT


def test_start_text_includes_nfa_framing() -> None:
    """E11-B02: /start carries not-financial-advice framing."""
    assert disclaimer() in START_TEXT
    assert "Not financial advice" in START_TEXT
    assert "informational only" in START_TEXT.lower() or "Not financial advice" in START_TEXT


@pytest.mark.parametrize(
    "args,category",
    [
        (["HNB.N0000", "disclosure"], None),
        (["JKH.N0000", "disclosure", "Financial"], "Financial"),
        (["JKH.N0000", "disclosure", "Financial", "Report"], "Financial Report"),
        (["COMB.N0000", "announcement", "Dividend"], "Dividend"),
        # Wave3 edges: kind case, whitespace-only → None, multi-token join, alias.
        (["JKH.N0000", "DISCLOSURE", "Board"], "Board"),
        (["JKH.N0000", "Disclosure", "  "], None),
        (["JKH.N0000", "disclosure", " ", "\t"], None),
        (["SAMP.N0000", "announcement", "Corporate", "Disclosure"], "Corporate Disclosure"),
        (["HNB.N0000", "ANNOUNCEMENT", "Circular"], "Circular"),
        (["JKH.N0000", "disclosure", "Q1", "Interim", "Financial"], "Q1 Interim Financial"),
    ],
)
def test_parse_disclosure_category_args(args: list[str], category: str | None) -> None:
    """Wave3: /alert SYMBOL disclosure [CATEGORY...] joins remaining tokens."""
    parsed, err = parse_alert_args(args)
    assert err is None
    assert parsed is not None
    assert parsed.alert_type == AlertType.DISCLOSURE
    assert parsed.threshold is None
    assert parsed.category == category


@pytest.mark.parametrize(
    "args",
    [
        ["JKH.N0000", "above", "nan"],
        ["JKH.N0000", "above", "NaN"],
        ["JKH.N0000", "above", "NAN"],
        ["JKH.N0000", "below", "inf"],
        ["JKH.N0000", "below", "-inf"],
        ["JKH.N0000", "below", "+inf"],
        ["JKH.N0000", "move", "Infinity"],
        ["JKH.N0000", "move", "-Infinity"],
        ["JKH.N0000", "above", "1e309"],
        ["COMB.N0000", "move", "1e400"],
    ],
)
def test_parse_alert_args_rejects_nan_inf(args: list[str]) -> None:
    """Wave3: nan/inf (any case/sign) and overflow must not create rules."""
    parsed, err = parse_alert_args(args)
    assert parsed is None
    assert err is not None
    assert "positive finite number" in err.lower()
    assert "nan/inf" in err.lower()


@pytest.mark.parametrize(
    "args",
    [
        ["JKH.N0000", "above", "100,50"],
        ["JKH.N0000", "above", "1.000,50"],
        ["JKH.N0000", "below", "12,5"],
        ["JKH.N0000", "move", "1.234,56"],
        ["COMB.N0000", "above", "1.000.000,99"],
        ["SAMP.N0000", "below", "0,5"],
    ],
)
def test_parse_alert_args_rejects_eu_decimal_comma(args: list[str]) -> None:
    """Wave3: European decimal commas are rejected (US thousands 1,000 still ok)."""
    parsed, err = parse_alert_args(args)
    assert parsed is None
    assert err is not None
    assert "positive finite number" in err.lower()


@pytest.mark.parametrize(
    "args",
    [
        ["JKH.N0000", "above", "100", "extra"],
        ["JKH.N0000", "below", "50", "more", "junk"],
        ["JKH.N0000", "move", "5", "pct"],
    ],
)
def test_parse_alert_args_rejects_trailing_junk(args: list[str]) -> None:
    """Trailing tokens after a price/move threshold are not allowed."""
    parsed, err = parse_alert_args(args)
    assert parsed is None
    assert err is not None
    assert "unexpected extra text" in err.lower()


# Wave7: fuzz / weird-string corpus — parse_alert_args must never raise.
_WEIRD_TOKENS = [
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
    "above\u200b",  # zero-width space
    "below\ufeff",  # BOM
    "move\u00a0",  # nbsp
    "a" * 10_000,
    "1" * 5000,
    "0" * 100,
    "-0",
    "+0",
    "0",
    "0.0",
    "-0.0",
    "--1",
    "++1",
    "1..2",
    "..5",
    "1.2.3",
    "1e",
    "e10",
    "1e-",
    "1e+",
    "0x10",
    "0b10",
    "0o10",
    "1_000",
    "1 000",
    "$100",
    "100%",
    "100Rs",
    "₹100",
    "(100)",
    "[100]",
    "{100}",
    "100;",
    "100--",
    "';100",
    "null",
    "None",
    "undefined",
    "true",
    "false",
    "NaN%",
    "inf.",
    ".inf",
    "∞",
    "１",  # fullwidth digit
    "١٠",  # Arabic-Indic digits
    "' OR 1=1 --",
    '"; DROP TABLE alert_rules;--',
    "<script>alert(1)</script>",
    "${IFS}",
    "$(whoami)",
    "`id`",
    "../../../etc/passwd",
    "%s%s%s%s",
    "%n",
    "{{7*7}}",
    "\u202eabove",  # RTL override
    "above\u202c",
    "\u0000above",
    "a\tb\tc",
    "👍" * 100,
]

_WEIRD_KINDS = [
    "",
    " ",
    "above",
    "below",
    "move",
    "disclosure",
    "announcement",
    "ABOVE",
    "BeLoW",
    "sideways",
    "price",
    "alert",
    "🔥",
    "a" * 256,
    "above\nbelow",
    "disclos ure",
]


@pytest.mark.parametrize(
    "args",
    [
        # Sparse / malformed shapes
        [],
        [""],
        [" "],
        ["\x00"],
        ["JKH.N0000"],
        ["", ""],
        ["JKH.N0000", ""],
        ["JKH.N0000", " ", "100"],
        ["JKH.N0000", "above", ""],
        ["JKH.N0000", "above", " "],
        ["JKH.N0000", "above", "\t\n"],
        ["JKH.N0000", "below", "\x00"],
        ["JKH.N0000", "move", "🚀"],
        ["JKH.N0000", "disclosure", "\x00"],
        ["JKH.N0000", "announcement", "<script>"],
        # Extra / odd arity
        ["JKH.N0000", "above", "100", ""],
        ["JKH.N0000", "above", "100", "\x00"],
        ["JKH.N0000", "move", "5", "💥", "more"],
        ["", "above", "100"],
        ["\ufffd", "below", "1"],
        # Long / unicode symbol slot still must not throw
        ["🚀" * 50, "above", "1"],
        ["A" * 10_000, "move", "1"],
        *[
            ["JKH.N0000", kind, token]
            for kind in ("above", "below", "move")
            for token in _WEIRD_TOKENS
        ],
        *[["JKH.N0000", kind] for kind in _WEIRD_KINDS],
        *[["JKH.N0000", kind, "Financial", "💣"] for kind in ("disclosure", "announcement")],
    ],
    ids=lambda a: repr(a)[:80],
)
def test_parse_alert_args_fuzz_never_raises(args: list[str]) -> None:
    """Wave7: weird / adversarial arg lists must not throw — only return errors."""
    try:
        parsed, err = parse_alert_args(args)
    except Exception as exc:  # pragma: no cover - failure path for the invariant
        pytest.fail(f"parse_alert_args raised {type(exc).__name__}: {exc!r} for {args!r}")
    # Contract: success → (ParsedAlert, None); failure → (None, str). Never both/neither.
    if err is None:
        assert parsed is not None
        assert parsed.alert_type in AlertType
        if parsed.alert_type == AlertType.DISCLOSURE:
            assert parsed.threshold is None
        else:
            assert parsed.threshold is not None
            assert parsed.threshold > 0
            assert parsed.threshold == parsed.threshold  # not NaN
    else:
        assert parsed is None
        assert isinstance(err, str)
        assert err.strip() != ""


def test_parse_alert_args_fuzz_cartesian_kinds_thresholds() -> None:
    """Wave7 property-ish: every weird kind×threshold pair returns without raising."""
    thresholds = _WEIRD_TOKENS + ["100", "50.5", "1,000", "0.01"]
    for kind in _WEIRD_KINDS + ["above", "below", "move", "disclosure", "announcement"]:
        for thr in thresholds:
            args = ["JKH.N0000", kind, thr]
            try:
                parsed, err = parse_alert_args(args)
            except Exception as exc:  # pragma: no cover
                pytest.fail(f"parse_alert_args raised {type(exc).__name__}: {exc!r} for {args!r}")
            assert (parsed is None) ^ (err is None)
            if err is not None:
                assert isinstance(err, str) and err
            else:
                assert parsed is not None
