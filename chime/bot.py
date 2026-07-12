"""Telegram bot — the only user-facing surface for v1.

Commands: /start, /help, /watch, /unwatch, /alert, /cancel, /myalerts, /mywatchlist.
Alert dispatch happens from the poller via notify.send_message.
"""

from __future__ import annotations

import os
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from chime.adapters.cse import CSEClient
from chime.domain import AlertType, PriceSnapshot, disclaimer
from chime.logging_setup import get_logger
from chime.storage import Storage

log = get_logger(__name__)

SYMBOL_RE = re.compile(r"^[A-Za-z0-9]{1,12}(\.[A-Za-z0-9]{1,8})?$")

# Per telegram_id sliding-window timestamps (monotonic seconds). No DB.
_cmd_timestamps: dict[int, deque[float]] = defaultdict(deque)
_RATE_WINDOW_SECONDS = 60.0
RATE_LIMIT_REPLY = (
    "Slow down — you've hit the command rate limit. Try again in a minute.\n"
    f"{disclaimer()}"
)

BAD_SYMBOL_HINT = (
    "That doesn't look like a CSE symbol. Try something like JKH.N0000 or COMB.N0000."
)
ALERT_USAGE = (
    "I couldn't parse that alert. Try one of:\n"
    "/alert SYMBOL above PRICE\n"
    "/alert SYMBOL below PRICE\n"
    "/alert SYMBOL move PERCENT\n"
    "/alert SYMBOL disclosure\n"
    "Example: /alert JKH.N0000 above 100\n"
    f"{disclaimer()}"
)
CANCEL_USAGE = (
    "To cancel an alert, send its id from /myalerts.\n"
    "Usage: /cancel ALERT_ID\n"
    "Example: /cancel 7\n"
    f"{disclaimer()}"
)


def watch_upstream_error(symbol: str) -> str:
    return (
        f"I couldn't verify {symbol} because cse.lk is unreachable right now. "
        f"Nothing was added; try /watch {symbol} again in a minute.\n"
        f"{disclaimer()}"
    )


def reset_cmd_rate_limits() -> None:
    """Clear in-memory rate-limit state (tests)."""
    _cmd_timestamps.clear()


def allow_command(
    telegram_id: int,
    limit: int,
    *,
    now: float | None = None,
    window: float = _RATE_WINDOW_SECONDS,
) -> bool:
    """Return True if this command is within the per-user sliding window budget."""
    if limit <= 0:
        return True
    t = time.monotonic() if now is None else now
    q = _cmd_timestamps[telegram_id]
    while q and t - q[0] >= window:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(t)
    return True


def _cmd_rate_limit(context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = context.application.bot_data.get("cmd_rate_per_minute")
    if raw is not None:
        return int(raw)
    return 20


async def _rate_limited(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """If over limit, reply and return True (caller should return)."""
    user = update.effective_user
    if user is None:
        return False
    if allow_command(user.id, _cmd_rate_limit(context)):
        return False
    if update.effective_message:
        await update.effective_message.reply_text(RATE_LIMIT_REPLY)
    return True


def _env_cmd_rate_per_minute() -> int:
    raw = os.getenv("BOT_CMD_RATE_PER_MINUTE", "").strip()
    if not raw:
        return 20
    return int(raw)


# ≤3 lines including NFA; command dump lives on /help only (WS-014 / E7-B02).
START_TEXT = (
    "Chime watches the Colombo Stock Exchange and pings you on Telegram "
    "when a price or daily-move alert fires — no app or browser tab required.\n"
    "Disclosures need an explicit /alert SYMBOL disclosure. See /help for commands.\n"
    f"{disclaimer()}"
)

# ≤12 lines (E7-B01). /myalerts lists active rules only (E9-B01).
# E11-B01: alert syntax + NFA one-liner on /help.
# E11-A01: disclosure alerts skip filings at/before rule create (fail-closed).
HELP_TEXT = (
    "Commands:\n"
    "/watch SYMBOL\n"
    "/unwatch SYMBOL\n"
    "/alert SYMBOL above PRICE\n"
    "/alert SYMBOL below PRICE\n"
    "/alert SYMBOL move PERCENT\n"
    "/alert SYMBOL disclosure\n"
    "/cancel ALERT_ID\n"
    "/myalerts — active only\n"
    "/mywatchlist\n"
    "Disclosure alerts: new filings after you set the rule only "
    "(missing publish time → no fire).\n"
    f"{disclaimer()}"
)

# Back-compat alias for older imports / docs.
HELP_HINT = HELP_TEXT


@dataclass(frozen=True)
class ParsedAlert:
    alert_type: AlertType
    threshold: float | None
    category: str | None = None


def normalize_symbol(raw: str) -> str | None:
    s = raw.strip().upper()
    if not s or not SYMBOL_RE.match(s):
        return None
    # CSE common shares often use .N0000 — accept bare ticker and common forms
    return s


def parse_alert_args(args: list[str]) -> tuple[ParsedAlert | None, str | None]:
    """Parse /alert args after the command. Returns (parsed, kind_error).

    Caller validates/normalizes ``args[0]`` as the symbol. On error, parsed is
    None and kind_error is a user-facing message.
    """
    if len(args) < 2:
        return None, ALERT_USAGE
    kind = args[1].lower()
    if kind in ("above", "below", "move"):
        if len(args) < 3:
            return None, (
                f"Almost — need a number after {kind}. "
                f"Example: /alert JKH.N0000 {kind} 5\n{ALERT_USAGE}"
            )
        try:
            threshold = float(args[2].replace(",", ""))
        except ValueError:
            return None, (
                "The threshold must be a number. "
                f"Example: /alert JKH.N0000 {kind} 100\n{ALERT_USAGE}"
            )
        if threshold <= 0:
            return None, (
                "Threshold must be a positive number. "
                f"Example: /alert JKH.N0000 {kind} 5\n{ALERT_USAGE}"
            )
        if kind == "above":
            return ParsedAlert(AlertType.PRICE_ABOVE, threshold), None
        if kind == "below":
            return ParsedAlert(AlertType.PRICE_BELOW, threshold), None
        return ParsedAlert(AlertType.DAILY_MOVE, threshold), None
    if kind in ("disclosure", "announcement"):
        category = " ".join(args[2:]).strip() or None
        return ParsedAlert(AlertType.DISCLOSURE, None, category), None
    return None, (
        "I didn't catch that alert type.\n"
        f"{ALERT_USAGE}"
    )


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
    if await _rate_limited(update, context):
        return
    storage: Storage = context.application.bot_data["storage"]
    await _user_id(storage, update)
    if update.effective_message:
        await update.effective_message.reply_text(START_TEXT)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _rate_limited(update, context):
        return
    if update.effective_message:
        await update.effective_message.reply_text(HELP_TEXT)


async def cmd_watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _rate_limited(update, context):
        return
    storage: Storage = context.application.bot_data["storage"]
    cse: CSEClient = context.application.bot_data["cse"]
    if not update.effective_message:
        return
    if not context.args:
        await update.effective_message.reply_text(
            "Usage: /watch SYMBOL\nExample: /watch JKH.N0000"
        )
        return
    symbol = normalize_symbol(context.args[0])
    if symbol is None:
        await update.effective_message.reply_text(BAD_SYMBOL_HINT)
        return
    status, info = await _lookup_symbol(cse, symbol)
    if status == "upstream":
        await update.effective_message.reply_text(watch_upstream_error(symbol))
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
    if await _rate_limited(update, context):
        return
    storage: Storage = context.application.bot_data["storage"]
    if not update.effective_message:
        return
    if not context.args:
        await update.effective_message.reply_text(
            "Usage: /unwatch SYMBOL\nExample: /unwatch JKH.N0000"
        )
        return
    symbol = normalize_symbol(context.args[0])
    if symbol is None:
        await update.effective_message.reply_text(BAD_SYMBOL_HINT)
        return
    user_id = await _user_id(storage, update)
    assert user_id is not None
    removed, deactivated = await storage.unwatch_symbol(user_id, symbol)
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
        await update.effective_message.reply_text(
            f"{symbol} wasn't on your watchlist. Check /mywatchlist or add it with "
            f"/watch {symbol}."
        )


async def cmd_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _rate_limited(update, context):
        return
    storage: Storage = context.application.bot_data["storage"]
    cse: CSEClient = context.application.bot_data["cse"]
    if not update.effective_message:
        return
    args = context.args or []
    if not args:
        await update.effective_message.reply_text(ALERT_USAGE)
        return
    symbol = normalize_symbol(args[0])
    if symbol is None:
        await update.effective_message.reply_text(BAD_SYMBOL_HINT)
        return
    parsed, err = parse_alert_args(args)
    if err is not None or parsed is None:
        await update.effective_message.reply_text(err or ALERT_USAGE)
        return
    alert_type = parsed.alert_type
    threshold = parsed.threshold
    category = parsed.category

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
    rule = await storage.create_alert_rule(
        user_id, symbol, alert_type, threshold, category=category
    )

    if alert_type == AlertType.DISCLOSURE:
        if rule.category:
            desc = (
                f"new disclosure for {symbol} matching category '{rule.category}'"
            )
        else:
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
    if await _rate_limited(update, context):
        return
    storage: Storage = context.application.bot_data["storage"]
    if not update.effective_message:
        return
    if not context.args:
        await update.effective_message.reply_text(CANCEL_USAGE)
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
    if await _rate_limited(update, context):
        return
    storage: Storage = context.application.bot_data["storage"]
    if not update.effective_message:
        return
    user_id = await _user_id(storage, update)
    assert user_id is not None
    rules = await storage.list_alerts(user_id)
    if not rules:
        await update.effective_message.reply_text(
            "No active alerts yet. Try:\n"
            "/alert JKH.N0000 above 100\n"
            "/alert JKH.N0000 below 90\n"
            "/alert JKH.N0000 move 5\n"
            "/alert JKH.N0000 disclosure\n"
            f"{disclaimer()}"
        )
        return
    lines = ["Your alerts:"]
    for r in rules:
        if r.type == AlertType.DISCLOSURE:
            if r.category:
                lines.append(f"#{r.id} {r.symbol} disclosure {r.category}")
            else:
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
    if await _rate_limited(update, context):
        return
    storage: Storage = context.application.bot_data["storage"]
    if not update.effective_message:
        return
    user_id = await _user_id(storage, update)
    assert user_id is not None
    symbols = await storage.list_watchlist(user_id)
    if not symbols:
        await update.effective_message.reply_text(
            "Watchlist empty. Add a CSE symbol with /watch SYMBOL.\n"
            "Example: /watch JKH.N0000"
        )
        return
    await update.effective_message.reply_text("Watchlist:\n" + "\n".join(symbols))


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("bot_handler_error", error=str(context.error), update=str(update)[:200])


def build_application(
    token: str,
    storage: Storage,
    cse: CSEClient,
    *,
    cmd_rate_per_minute: int | None = None,
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
    app.bot_data["cmd_rate_per_minute"] = (
        cmd_rate_per_minute if cmd_rate_per_minute is not None else _env_cmd_rate_per_minute()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("watch", cmd_watch))
    app.add_handler(CommandHandler("unwatch", cmd_unwatch))
    app.add_handler(CommandHandler("alert", cmd_alert))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("myalerts", cmd_myalerts))
    app.add_handler(CommandHandler("mywatchlist", cmd_mywatchlist))
    app.add_error_handler(on_error)
    return app
