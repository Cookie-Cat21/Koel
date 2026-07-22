"""Unit tests for CSE dividend parse helpers (no DB)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from koel.bot import cmd_alert, parse_alert_args, reset_cmd_rate_limits
from koel.dividends import (
    colombo_today,
    is_dividend_disclosure,
    merge_dividend_hints,
    parse_cse_date,
    parse_dividend_hints,
    xd_within_horizon,
)
from koel.domain import MARKET_SYMBOL, AlertRule, AlertType, PriceSnapshot, disclaimer
from koel.rules import evaluate_xd_digest_rules, evaluate_xd_soon_rules

LEGACY = (
    "Date of Announcement: - 31.Jan.2019 \r<br>"
    "Rate of Dividend: - Rs. 2.00 per share / Second Interim\r<br>"
    "Financial Year: - 2018/2019 \r<br>"
    "XD: - 12.Feb.2019 \r<br>"
    "Payment: - 22.Feb.2019"
)


def test_is_dividend_disclosure() -> None:
    assert is_dividend_disclosure("CASH DIVIDEND", "Notice")
    assert is_dividend_disclosure(None, "Interim Dividend")
    assert not is_dividend_disclosure("AGM", "Notice of meeting")


def test_parse_legacy_body() -> None:
    h = parse_dividend_hints(LEGACY)
    assert h.dps == 2.0
    assert h.d_xd == date(2019, 2, 12)
    assert h.d_pay == date(2019, 2, 22)
    assert h.kind == "second interim"
    assert h.fy == "2018/2019"


def test_parse_cse_date_variants() -> None:
    assert parse_cse_date("12.Feb.2019") == date(2019, 2, 12)
    assert parse_cse_date("2026-07-24") == date(2026, 7, 24)
    assert parse_cse_date("24/07/2026") == date(2026, 7, 24)


def test_dates_tbd() -> None:
    h = parse_dividend_hints("CASH DIVIDEND (DATES TO BE NOTIFIED)")
    assert h.dates_tbd is True


def test_merge_prefers_first_non_null() -> None:
    h = merge_dividend_hints("Rs 1.5 per share", "XD: - 01.Aug.2026")
    assert h.dps == 1.5
    assert h.d_xd == date(2026, 8, 1)


def test_xd_within_horizon() -> None:
    today = date(2026, 7, 20)
    assert xd_within_horizon(date(2026, 7, 24), horizon_days=7, today=today)
    assert not xd_within_horizon(date(2026, 8, 20), horizon_days=7, today=today)
    assert not xd_within_horizon(None, horizon_days=7, today=today)


def test_parse_alert_xd() -> None:
    parsed, err = parse_alert_args(["JKH.N0000", "xd", "7"])
    assert err is None
    assert parsed is not None
    assert parsed.alert_type == AlertType.XD_SOON
    assert parsed.threshold == 7.0

    parsed, err = parse_alert_args(["MARKET", "xd_digest", "7"])
    assert err is None
    assert parsed is not None
    assert parsed.alert_type == AlertType.XD_DIGEST


@pytest.mark.asyncio
async def test_cmd_alert_xd_confirm_and_digest_normalizes_market() -> None:
    """XD confirm copy + xd_digest always stores MARKET (even if ticker given)."""
    reset_cmd_rate_limits()
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=1)
    storage.upsert_stock = AsyncMock()
    storage.create_alert_rule = AsyncMock(
        side_effect=lambda uid, sym, atype, thr, category=None, ref_price=None: AlertRule(
            id=11,
            user_id=uid,
            telegram_id=9,
            symbol=sym,
            type=atype,
            threshold=thr,
            active=True,
            category=category,
            ref_price=ref_price,
        )
    )
    cse = AsyncMock()
    cse.fetch_company_info = AsyncMock(
        return_value=PriceSnapshot(
            symbol="JKH.N0000",
            price=20.0,
            name="John Keells",
            ts=datetime(2026, 7, 20, tzinfo=UTC),
        )
    )
    message = AsyncMock()
    update = MagicMock()
    update.effective_message = message
    update.effective_user = MagicMock(id=9)
    context = MagicMock()
    context.application = MagicMock(
        bot_data={"storage": storage, "cse": cse, "cmd_rate_per_minute": 100}
    )

    # Per-symbol xd_soon confirm
    context.args = ["JKH.N0000", "xd", "7"]
    await cmd_alert(update, context)
    reply = message.reply_text.await_args.args[0]
    assert "ex-dividend" in reply.lower() or "XD" in reply
    assert "7" in reply
    assert disclaimer() in reply
    assert cse.fetch_company_info.await_count == 1

    # xd_digest with non-MARKET symbol → normalized to MARKET (no CSE lookup)
    message.reply_text.reset_mock()
    storage.create_alert_rule.reset_mock()
    context.args = ["JKH.N0000", "xd_digest", "7"]
    await cmd_alert(update, context)
    create_args = storage.create_alert_rule.await_args.args
    assert create_args[1] == MARKET_SYMBOL
    reply = message.reply_text.await_args.args[0]
    assert "XD digest" in reply or "xd digest" in reply.lower()
    assert "MARKET" in reply
    assert disclaimer() in reply
    assert cse.fetch_company_info.await_count == 1


def test_evaluate_xd_soon_once_per_xd() -> None:
    from types import SimpleNamespace

    today = colombo_today()
    d_xd = today + timedelta(days=3)
    rule = AlertRule(
        id=1,
        user_id=1,
        telegram_id=9,
        symbol="JKH.N0000",
        type=AlertType.XD_SOON,
        threshold=7,
        active=True,
    )
    row = SimpleNamespace(
        d_xd=d_xd,
        dps=2.0,
        title="Interim",
        disclosure_id=55,
    )
    events = evaluate_xd_soon_rules(
        events_by_symbol={"JKH.N0000": [row]},
        rules=[rule],
        today=today,
    )
    assert len(events) == 1
    assert events[0].event_key == f"xd:1:{d_xd.isoformat()}"
    # Second pass with claimed key → no fire
    events2 = evaluate_xd_soon_rules(
        events_by_symbol={"JKH.N0000": [row]},
        rules=[rule],
        today=today,
        fired_keys={events[0].event_key},
    )
    assert events2 == []


def test_evaluate_xd_digest_week_key() -> None:
    from types import SimpleNamespace

    today = colombo_today()
    rule = AlertRule(
        id=2,
        user_id=1,
        telegram_id=9,
        symbol="MARKET",
        type=AlertType.XD_DIGEST,
        threshold=7,
        active=True,
    )
    upcoming = [
        SimpleNamespace(symbol="AAF.N0000", d_xd=today + timedelta(days=2), dps=0.5),
        SimpleNamespace(symbol="JKH.N0000", d_xd=today + timedelta(days=5), dps=1.0),
    ]
    events = evaluate_xd_digest_rules(
        upcoming=upcoming,
        rules=[rule],
        today=today,
    )
    assert len(events) == 1
    assert "XD this week" in events[0].trigger
    assert events[0].event_key.startswith("xddigest:2:")


def test_hints_hash_and_iso_week() -> None:
    from koel.dividends import DividendHints, hints_raw_hash, iso_week_key

    h = DividendHints(dps=1.0, d_xd=date(2026, 7, 22), dates_tbd=False)
    digest = hints_raw_hash("JKH.N0000", "Final", h)
    assert len(digest) == 32
    assert iso_week_key(date(2026, 7, 20)).startswith("2026-W")


def test_parse_alert_xd_rejects_huge_horizon() -> None:
    parsed, err = parse_alert_args(["JKH.N0000", "xd", "120"])
    assert parsed is None
    assert err is not None
    assert "1–90" in err or "1-90" in err


def test_parse_numeric_dmy_and_iso() -> None:
    assert parse_cse_date("01.08.2026") == date(2026, 8, 1)
    assert parse_cse_date("") is None
    assert parse_cse_date(None) is None  # type: ignore[arg-type]
