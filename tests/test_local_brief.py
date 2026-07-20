"""Local metric-based brief text."""

from datetime import date

from koel.briefs.local_fill import build_local_brief


def test_local_brief_includes_nfa_and_metrics() -> None:
    text = build_local_brief(
        symbol="SAMP.N0000",
        title="Interim Financial Statements",
        kind="quarterly",
        period_end=date(2026, 3, 31),
        revenue=1_500_000_000,
        profit=120_000_000,
        eps=2.5,
        extract_ok=True,
        eps_yoy=12.5,
        rev_yoy=-3.0,
        profit_yoy=8.0,
    )
    assert "SAMP.N0000" in text
    assert "Not financial advice" in text
    assert "EPS YoY" in text or "basic EPS" in text
