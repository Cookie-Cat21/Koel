"""Telegram bot — the only user-facing surface for v1.

Commands: /start, /watch, /unwatch, /alert, /cancel, /myalerts, /mywatchlist.
Alert dispatch happens from the poller via notify.send_message.
"""

from __future__ import annotations

import re
from typing import Any

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from chime.adapters.cse import CSEClient
from chime.domain import AlertType, PriceSnapshot, disclaimer
from chime.logging_setup import get_logger
from chime.storage import Storage

log = get_logger(__name__)

SYMBOL_RE = re.compile(r"^[A-Za-z0-9]{1,12}(\.[A-Za-z0-9]{1,8})?$")

START_TEXT = (
    "Chime watches the Colombo Stock Exchange and pings you on Telegram "
    "when a price or daily-move alert fires — no app or browser tab required.\n\n"
    "Disclosures need an explicit /alert SYMBOL disclosure.\n\n"
    f"{disclaimer()}"
)

HELP_HINT = (
    "Commands:\n"
    "/watch SYMBOL\n"
    "/unwatch SYMBOL\n"
    "/alert SYMBOL above PRICE\n"
    "/alert SYMBOL below PRICE\n"
    "/alert SYMBOL move PERCENT\n"
    "/alert SYMBOL disclosure\n"
    "/cancel ALERT_ID\n"
    "/myalerts\n"
    "/mywatchlist"
)


def normalize_symbol(raw: str) -> str | None:
    s = raw.strip().upper()
    if not s or not SYMBOL_RE.match(s):
        return None
    # CSE common shares often use .N0000 — accept bare ticker and common forms
    return s


async def _user_id(storage: Storage, update: Update) -> int | None:
    if update.effective_user is None:
        return None
    return await storage.ensure_user(update.effective_user.id)


async def _lookup_symbol(
    cse: CSEClient, symbol: str
) -> tuple[str, PriceSnapshot | None]:
    """Return ('ok', snap) | ('not_found', None) | ('upstream', None)."""
    try:
        info = await cse.fetch_company_info(symbol)
    except Exception:
        log.warning("cse_lookup_upstream", symbol=symbol)
        return ("upstream", None)
    if info is None:
        return ("not_found", None)
    return ("ok", info)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage: Storage = context.application.bot_data["storage"]
    await _user_id(storage, update)
    if update.effective_message:
        await update.effective_message.reply_text(f"{START_TEXT}\n\n{HELP_HINT}")


async def cmd_watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage: Storage = context.application.bot_data["storage"]
    cse: CSEClient = context.application.bot_data["cse"]
    if not update.effective_message:
        return
    if not context.args:
        await update.effective_message.reply_text("Usage: /watch SYMBOL\nExample: /watch JKH.N0000")
        return
    symbol = normalize_symbol(context.args[0])
    if symbol is None:
        await update.effective_message.reply_text(
            "That doesn't look like a CSE symbol. Try e.g. JKH.N0000 or COMB.N0000."
        )
        return
    status, info = await _lookup_symbol(cse, symbol)
    if status == "upstream":
        await update.effective_message.reply_text("cse.lk unreachable, try again.")
        return
    if status == "not_found":
        await update.effective_message.reply_text(
            f"Couldn't find {symbol} on cse.lk. Check the ticker and try again."
        )
        return
    assert info is not None
    user_id = await _user_id(storage, update)
    assert user_id is not None
    await storage.upsert_stock(symbol, info.name)
    await storage.add_watch(user_id, symbol)
    await update.effective_message.reply_text(
        f"Watching {symbol}. Set an alert with /alert.\n{disclaimer()}"
    )


async def cmd_unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage: Storage = context.application.bot_data["storage"]
    if not update.effective_message:
        return
    if not context.args:
        await update.effective_message.reply_text("Usage: /unwatch SYMBOL")
        return
    symbol = normalize_symbol(context.args[0])
    if symbol is None:
        await update.effective_message.reply_text("That doesn't look like a CSE symbol.")
        return
    user_id = await _user_id(storage, update)
    assert user_id is not None
    removed = await storage.remove_watch(user_id, symbol)
    deactivated = await storage.deactivate_rules_for_symbol(user_id, symbol)
    if removed:
        msg = f"Removed {symbol} from your watchlist."
        if deactivated:
            msg += f" Deactivated {deactivated} alert(s)."
        await update.effective_message.reply_text(msg)
    elif deactivated:
        await update.effective_message.reply_text(
            f"{symbol} wasn't on your watchlist, but deactivated {deactivated} orphan alert(s)."
        )
    else:
        await update.effective_message.reply_text(f"{symbol} wasn't on your watchlist.")


async def cmd_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage: Storage = context.application.bot_data["storage"]
    cse: CSEClient = context.application.bot_data["cse"]
    if not update.effective_message:
        return
    args = context.args or []
    if len(args) < 2:
        await update.effective_message.reply_text(
            "Usage:\n"
            "/alert SYMBOL above PRICE\n"
            "/alert SYMBOL below PRICE\n"
            "/alert SYMBOL move PERCENT\n"
            "/alert SYMBOL disclosure"
        )
        return
    symbol = normalize_symbol(args[0])
    if symbol is None:
        await update.effective_message.reply_text("That doesn't look like a CSE symbol.")
        return
    kind = args[1].lower()
    threshold: float | None = None
    alert_type: AlertType

    if kind in ("above", "below", "move"):
        if len(args) < 3:
            await update.effective_message.reply_text(f"Usage: /alert SYMBOL {kind} NUMBER")
            return
        try:
            threshold = float(args[2].replace(",", ""))
        except ValueError:
            await update.effective_message.reply_text("The threshold must be a number.")
            return
        if threshold <= 0:
            await update.effective_message.reply_text("Threshold must be positive.")
            return
        if kind == "above":
            alert_type = AlertType.PRICE_ABOVE
        elif kind == "below":
            alert_type = AlertType.PRICE_BELOW
        else:
            alert_type = AlertType.DAILY_MOVE
    elif kind in ("disclosure", "announcement"):
        alert_type = AlertType.DISCLOSURE
    else:
        await update.effective_message.reply_text(
            "Unknown alert kind. Use above, below, move, or disclosure."
        )
        return

    status, info = await _lookup_symbol(cse, symbol)
    if status == "upstream":
        await update.effective_message.reply_text("cse.lk unreachable, try again.")
        return
    if status == "not_found":
        await update.effective_message.reply_text(
            f"Couldn't find {symbol} on cse.lk. Check the ticker and try again."
        )
        return
    assert info is not None

    user_id = await _user_id(storage, update)
    assert user_id is not None
    await storage.upsert_stock(symbol, info.name)
    rule = await storage.create_alert_rule(user_id, symbol, alert_type, threshold)

    if alert_type == AlertType.DISCLOSURE:
        desc = f"new disclosure for {symbol}"
    elif alert_type == AlertType.DAILY_MOVE:
        desc = f"{symbol} daily move ≥ {threshold:g}%"
    elif alert_type == AlertType.PRICE_ABOVE:
        desc = f"{symbol} crosses above {threshold:g}"
    else:
        desc = f"{symbol} crosses below {threshold:g}"

    await update.effective_message.reply_text(
        f"Alert #{rule.id} set: {desc}.\n{disclaimer()}"
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage: Storage = context.application.bot_data["storage"]
    if not update.effective_message:
        return
    if not context.args:
        await update.effective_message.reply_text("Usage: /cancel ALERT_ID")
        return
    raw = context.args[0].lstrip("#")
    try:
        rule_id = int(raw)
    except ValueError:
        await update.effective_message.reply_text(
            "Alert id must be a number. Usage: /cancel ALERT_ID"
        )
        return
    if rule_id <= 0:
        await update.effective_message.reply_text(
            "Alert id must be a positive number. Usage: /cancel ALERT_ID"
        )
        return
    user_id = await _user_id(storage, update)
    assert user_id is not None
    ok = await storage.deactivate_alert(user_id, rule_id)
    if ok:
        await update.effective_message.reply_text(f"Cancelled alert #{rule_id}.")
    else:
        await update.effective_message.reply_text(
            f"No active alert #{rule_id} found. Check /myalerts."
        )


async def cmd_myalerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage: Storage = context.application.bot_data["storage"]
    if not update.effective_message:
        return
    user_id = await _user_id(storage, update)
    assert user_id is not None
    rules = await storage.list_alerts(user_id)
    if not rules:
        await update.effective_message.reply_text("No active alerts. Set one with /alert.")
        return
    lines = ["Your alerts:"]
    for r in rules:
        if r.type == AlertType.DISCLOSURE:
            lines.append(f"#{r.id} {r.symbol} disclosure")
        elif r.type == AlertType.DAILY_MOVE:
            lines.append(f"#{r.id} {r.symbol} move {r.threshold:g}%")
        elif r.type == AlertType.PRICE_ABOVE:
            lines.append(f"#{r.id} {r.symbol} above {r.threshold:g}")
        else:
            lines.append(f"#{r.id} {r.symbol} below {r.threshold:g}")
    lines.append("")
    lines.append(disclaimer())
    await update.effective_message.reply_text("\n".join(lines))


async def cmd_mywatchlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage: Storage = context.application.bot_data["storage"]
    if not update.effective_message:
        return
    user_id = await _user_id(storage, update)
    assert user_id is not None
    symbols = await storage.list_watchlist(user_id)
    if not symbols:
        await update.effective_message.reply_text("Watchlist empty. Add with /watch SYMBOL.")
        return
    await update.effective_message.reply_text("Watchlist:\n" + "\n".join(symbols))


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("bot_handler_error", error=str(context.error), update=str(update)[:200])


def build_application(
    token: str, storage: Storage, cse: CSEClient
) -> Application[Any, Any, Any, Any, Any, Any]:
    app = (
        Application.builder()
        .token(token)
        .connect_timeout(10.0)
        .read_timeout(20.0)
        .write_timeout(20.0)
        .pool_timeout(5.0)
        .build()
    )
    app.bot_data["storage"] = storage
    app.bot_data["cse"] = cse
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("watch", cmd_watch))
    app.add_handler(CommandHandler("unwatch", cmd_unwatch))
    app.add_handler(CommandHandler("alert", cmd_alert))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("myalerts", cmd_myalerts))
    app.add_handler(CommandHandler("mywatchlist", cmd_mywatchlist))
    app.add_error_handler(on_error)
    return app
