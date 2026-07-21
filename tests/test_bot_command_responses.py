"""Catalog bot replies for every command + alert form (mocked; no Telegram/CSE net).

Run:
  python3 -m pytest tests/test_bot_command_responses.py -q --no-cov -s
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from koel.bot import (
    cmd_alert,
    cmd_brief,
    cmd_cancel,
    cmd_help,
    cmd_myalerts,
    cmd_mywatchlist,
    cmd_start,
    cmd_unwatch,
    cmd_watch,
    reset_cmd_rate_limits,
)
from koel.domain import AlertRule, AlertType, PriceSnapshot, disclaimer


@pytest.fixture(autouse=True)
def _clear_rate_limits() -> None:
    reset_cmd_rate_limits()
    yield
    reset_cmd_rate_limits()


def _make_update_context(
    *,
    args: list[str] | None = None,
    storage: AsyncMock,
    cse: AsyncMock | None = None,
    telegram_id: int = 4242,
) -> tuple[MagicMock, MagicMock]:
    message = AsyncMock()
    message.reply_text = AsyncMock()
    user = MagicMock()
    user.id = telegram_id
    update = MagicMock()
    update.effective_message = message
    update.effective_user = user
    application = MagicMock()
    bot_data: dict = {"storage": storage, "cmd_rate_per_minute": 100}
    if cse is not None:
        bot_data["cse"] = cse
    application.bot_data = bot_data
    context = MagicMock()
    context.args = args or []
    context.application = application
    return update, context


def _snap(symbol: str = "JKH.N0000") -> PriceSnapshot:
    return PriceSnapshot(
        symbol=symbol,
        price=20.0,
        name="John Keells Holdings PLC",
        ts=datetime(2026, 7, 13, 5, 0, tzinfo=UTC),
    )


def _rule(
    *,
    rule_id: int,
    alert_type: AlertType,
    threshold: float | None,
    symbol: str = "JKH.N0000",
) -> AlertRule:
    return AlertRule(
        id=rule_id,
        user_id=1,
        telegram_id=4242,
        symbol=symbol,
        type=alert_type,
        threshold=threshold,
        active=True,
        armed=True,
        created_at=datetime(2026, 7, 1, tzinfo=UTC),
    )


async def _reply(
    handler,
    *,
    args: list[str],
    storage: AsyncMock,
    cse: AsyncMock | None = None,
) -> str:
    update, context = _make_update_context(args=args, storage=storage, cse=cse)
    await handler(update, context)
    assert update.effective_message.reply_text.await_count >= 1
    return str(update.effective_message.reply_text.await_args.args[0])


ALERT_CASES: list[tuple[str, list[str], AlertType, float | None]] = [
    ("above", ["JKH.N0000", "above", "100"], AlertType.PRICE_ABOVE, 100.0),
    ("below", ["JKH.N0000", "below", "90"], AlertType.PRICE_BELOW, 90.0),
    ("move", ["JKH.N0000", "move", "5"], AlertType.DAILY_MOVE, 5.0),
    ("disclosure", ["JKH.N0000", "disclosure"], AlertType.DISCLOSURE, None),
    (
        "disclosure category",
        ["JKH.N0000", "disclosure", "Financial"],
        AlertType.DISCLOSURE,
        None,
    ),
    ("volume", ["JKH.N0000", "volume", "5"], AlertType.VOLUME_SPIKE, 5.0),
    ("volup", ["JKH.N0000", "volup", "3"], AlertType.VOLUME_UP, 3.0),
    ("voldown", ["JKH.N0000", "voldown", "3"], AlertType.VOLUME_DOWN, 3.0),
    ("crossing", ["JKH.N0000", "crossing", "4"], AlertType.CROSSING_VOLUME, 4.0),
    ("print", ["JKH.N0000", "print", "10000"], AlertType.BIG_PRINT, 10000.0),
    ("gap", ["JKH.N0000", "gap", "2"], AlertType.GAP, 2.0),
    ("buyin", ["JKH.N0000", "buyin"], AlertType.BUY_IN, None),
    ("noncompliance", ["JKH.N0000", "noncompliance"], AlertType.NON_COMPLIANCE, None),
    ("halt", ["MARKET", "halt"], AlertType.HALT, None),
    ("bidheavy", ["JKH.N0000", "bidheavy", "2"], AlertType.BID_HEAVY, 2.0),
    ("askheavy", ["JKH.N0000", "askheavy", "1.5"], AlertType.ASK_HEAVY, 1.5),
]


@pytest.mark.asyncio
async def test_catalog_all_bot_command_responses(capsys: pytest.CaptureFixture[str]) -> None:
    """Exercise every bot command / alert form and print the Telegram reply body."""
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=1)
    storage.upsert_stock = AsyncMock()
    storage.add_watch = AsyncMock()
    storage.create_alert_rule = AsyncMock(
        side_effect=lambda user_id, symbol, alert_type, threshold, category=None, ref_price=None: _rule(
            rule_id=7,
            alert_type=alert_type,
            threshold=threshold,
            symbol=symbol,
        )
    )
    storage.unwatch_symbol = AsyncMock(return_value=(True, 1))
    storage.deactivate_alert = AsyncMock(return_value=True)
    storage.list_alerts = AsyncMock(
        return_value=[
            _rule(rule_id=1, alert_type=AlertType.PRICE_ABOVE, threshold=100.0),
            _rule(rule_id=2, alert_type=AlertType.VOLUME_SPIKE, threshold=5.0),
            _rule(rule_id=3, alert_type=AlertType.ASK_HEAVY, threshold=1.5),
            _rule(
                rule_id=4,
                alert_type=AlertType.HALT,
                threshold=None,
                symbol="MARKET",
            ),
        ]
    )
    storage.list_watchlist = AsyncMock(return_value=["JKH.N0000", "COMB.N0000"])
    storage.get_latest_ready_brief = AsyncMock(return_value=None)

    cse = AsyncMock()
    cse.fetch_company_info = AsyncMock(return_value=_snap())

    catalog: list[tuple[str, str]] = []

    catalog.append(("/start", await _reply(cmd_start, args=[], storage=storage)))
    catalog.append(("/help", await _reply(cmd_help, args=[], storage=storage)))
    catalog.append(
        (
            "/watch JKH.N0000",
            await _reply(cmd_watch, args=["JKH.N0000"], storage=storage, cse=cse),
        )
    )
    catalog.append(
        (
            "/unwatch JKH.N0000",
            await _reply(cmd_unwatch, args=["JKH.N0000"], storage=storage),
        )
    )

    for _label, args, alert_type, threshold in ALERT_CASES:
        category = None
        if alert_type == AlertType.DISCLOSURE and len(args) > 2:
            category = " ".join(args[2:])
        storage.create_alert_rule = AsyncMock(
            return_value=_rule(
                rule_id=7,
                alert_type=alert_type,
                threshold=threshold,
                symbol=args[0].upper(),
            ).model_copy(update={"category": category})
        )
        cmd = "/alert " + " ".join(args)
        reply = await _reply(cmd_alert, args=args, storage=storage, cse=cse)
        catalog.append((cmd, reply))
        assert "Alert #7 set" in reply or "Alert #7 set:" in reply
        assert disclaimer() in reply
        if category:
            assert category in reply

    catalog.append(
        ("/cancel 7", await _reply(cmd_cancel, args=["7"], storage=storage))
    )
    catalog.append(("/myalerts", await _reply(cmd_myalerts, args=[], storage=storage)))
    catalog.append(
        ("/mywatchlist", await _reply(cmd_mywatchlist, args=[], storage=storage))
    )
    catalog.append(
        (
            "/brief JKH.N0000",
            await _reply(cmd_brief, args=["JKH.N0000"], storage=storage),
        )
    )

    # Usage / empty-arg replies
    catalog.append(
        ("/alert (no args)", await _reply(cmd_alert, args=[], storage=storage, cse=cse))
    )
    catalog.append(
        ("/watch (no args)", await _reply(cmd_watch, args=[], storage=storage, cse=cse))
    )
    catalog.append(
        ("/cancel (no args)", await _reply(cmd_cancel, args=[], storage=storage))
    )

    # Print catalog for humans when run with -s
    print("\n===== KOEL BOT COMMAND RESPONSE CATALOG =====\n")
    for cmd, reply in catalog:
        print(f">>> {cmd}")
        print(reply)
        print("-" * 60)

    # Sanity: every reply is non-empty; core commands carry NFA where expected
    assert len(catalog) >= 20
    for cmd, reply in catalog:
        assert reply.strip(), cmd
    for cmd, reply in catalog:
        if cmd.startswith(("/start", "/help", "/alert")):
            assert disclaimer() in reply or "Not financial advice" in reply


@pytest.mark.asyncio
@pytest.mark.parametrize("label,args,alert_type,threshold", ALERT_CASES)
async def test_each_alert_form_confirm_reply(
    label: str,
    args: list[str],
    alert_type: AlertType,
    threshold: float | None,
) -> None:
    storage = AsyncMock()
    storage.ensure_user = AsyncMock(return_value=1)
    storage.upsert_stock = AsyncMock()
    storage.create_alert_rule = AsyncMock(
        return_value=_rule(
            rule_id=11,
            alert_type=alert_type,
            threshold=threshold,
            symbol=args[0].upper(),
        )
    )
    cse = AsyncMock()
    cse.fetch_company_info = AsyncMock(return_value=_snap(args[0].upper()))
    reply = await _reply(cmd_alert, args=args, storage=storage, cse=cse)
    assert "Alert #11 set" in reply
    assert disclaimer() in reply
