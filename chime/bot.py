"""Telegram bot — the only user-facing surface for v1.

Commands: /start, /help, /watch, /unwatch, /alert, /cancel, /myalerts,
/mywatchlist, /brief. Alert dispatch happens from the poller via notify.send_message.
"""

from __future__ import annotations

import math
import os
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from chime.adapters.cse import CSEClient, allowed_filing_url
from chime.briefs import briefs_enabled
from chime.domain import (
    BRIEF_BODY_MAX,
    AlertType,
    PriceSnapshot,
    brief_budget_for_prefix,
    disclaimer,
    sanitize_brief_body,
    truncate_disclosure_title,
)
from chime.logging_setup import get_logger
from chime.storage import Storage

log = get_logger(__name__)

SYMBOL_RE = re.compile(r"^[A-Za-z0-9]{1,12}(\.[A-Za-z0-9]{1,8})?$")

# Per telegram_id sliding-window timestamps (monotonic seconds). No DB.
_cmd_timestamps: dict[int, deque[float]] = defaultdict(deque)
_RATE_WINDOW_SECONDS = 60.0
RATE_LIMIT_REPLY = (
    f"Slow down — you've hit the command rate limit. Try again in a minute.\n{disclaimer()}"
)

BAD_SYMBOL_HINT = "That doesn't look like a CSE symbol. Try something like JKH.N0000 or COMB.N0000."
ALERT_USAGE = (
    "I couldn't parse that alert. Try one of:\n"
    "/alert SYMBOL above PRICE\n"
    "/alert SYMBOL below PRICE\n"
    "/alert SYMBOL move PERCENT\n"
    "/alert SYMBOL disclosure [CATEGORY]\n"
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
    """Parse bot rate env; invalid / negative → 20 (0 = unlimited)."""
    raw = os.getenv("BOT_CMD_RATE_PER_MINUTE", "").strip()
    if not raw:
        return 20
    try:
        value = int(raw)
    except ValueError:
        return 20
    return 20 if value < 0 else value


# ≤3 lines including NFA; command dump lives on /help only (WS-014 / E7-B02).
# Wave5: mention Browse dash, disclosure CATEGORY, optional AI brief.
START_TEXT = (
    "Chime watches the Colombo Stock Exchange and pings Telegram on price, "
    "move, or disclosure alerts — Browse dash mirrors watchlists.\n"
    "Disclosures: /alert SYMBOL disclosure [CATEGORY]; "
    "optional AI brief when enabled. See /help.\n"
    f"{disclaimer()}"
)

# ≤12 lines (E7-B01). /myalerts lists active rules only (E9-B01).
# E11-B01: alert syntax + NFA one-liner on /help.
# E11-A01: disclosure alerts skip filings at/before rule create (fail-closed).
# Wave5: Browse dash + CATEGORY + optional AI brief.
# Wave9: /brief SYMBOL — read-only latest ready brief (or none yet / AI off).
# Wave12: scenarios disabled note (Phase 3 stub fence).
HELP_TEXT = (
    "Commands:\n"
    "/watch SYMBOL\n"
    "/unwatch SYMBOL\n"
    "/alert SYMBOL above PRICE\n"
    "/alert SYMBOL below PRICE\n"
    "/alert SYMBOL move PERCENT\n"
    "/alert SYMBOL disclosure [CATEGORY]\n"
    "/cancel ALERT_ID\n"
    "/myalerts — active only · /mywatchlist · /brief SYMBOL\n"
    "Browse dash thin UI; scenarios disabled (Phase 3 stub).\n"
    "Disclosure alerts: new filings after the rule only "
    "(missing publish time → no fire; CATEGORY = title substring; "
    "optional AI brief when enabled).\n"
    f"{disclaimer()}"
)

BRIEF_USAGE = (
    "Usage: /brief SYMBOL\n"
    "Example: /brief JKH.N0000\n"
    f"{disclaimer()}"
)
BRIEF_NONE_YET = "none yet"
BRIEF_AI_OFF = "AI briefs are off"


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


def _parse_threshold_token(raw: str) -> float | None:
    """Parse a threshold token; None if not a positive finite number.

    Accepts plain decimals and US-style thousands (``1,000`` / ``1,000.5``).
    Rejects European decimal commas (``100,50`` / ``1.000,50``), non-finite
    floats (``nan`` / ``inf``), and zero/negative values.
    """
    s = raw.strip()
    if not s:
        return None
    if "," in s:
        if not re.fullmatch(r"[-+]?\d{1,3}(,\d{3})+(\.\d+)?", s):
            return None
        s = s.replace(",", "")
    try:
        threshold = float(s)
    except ValueError:
        return None
    if not math.isfinite(threshold) or threshold <= 0:
        return None
    return threshold


def parse_alert_args(args: list[str]) -> tuple[ParsedAlert | None, str | None]:
    """Parse /alert args after the command. Returns (parsed, kind_error).

    Caller validates/normalizes ``args[0]`` as the symbol. On error, parsed is
    None and kind_error is a user-facing message.

    Disclosure form: ``/alert SYMBOL disclosure [CATEGORY...]`` — remaining
    tokens join into one optional category substring filter.
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
        if len(args) > 3:
            return None, (
                f"Unexpected extra text after the {kind} threshold. "
                f"Example: /alert JKH.N0000 {kind} 5\n{ALERT_USAGE}"
            )
        threshold = _parse_threshold_token(args[2])
        if threshold is None:
            return None, (
                "Threshold must be a positive finite number "
                "(use 1000 or 1,000 — not nan/inf). "
                f"Example: /alert JKH.N0000 {kind} 100\n{ALERT_USAGE}"
            )
        if kind == "above":
            return ParsedAlert(AlertType.PRICE_ABOVE, threshold), None
        if kind == "below":
            return ParsedAlert(AlertType.PRICE_BELOW, threshold), None
        return ParsedAlert(AlertType.DAILY_MOVE, threshold), None
    if kind in ("disclosure", "announcement"):
        category = " ".join(args[2:]).strip() or None
        return ParsedAlert(AlertType.DISCLOSURE, None, category), None
    return None, (f"I didn't catch that alert type.\n{ALERT_USAGE}")


async def _user_id(storage: Storage, update: Update) -> int | None:
    if update.effective_user is None:
        return None
    return await storage.ensure_user(update.effective_user.id)


async def _lookup_symbol(cse: CSEClient, symbol: str) -> tuple[str, PriceSnapshot | None]:
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
        await update.effective_message.reply_text("Usage: /watch SYMBOL\nExample: /watch JKH.N0000")
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
            f"{symbol} wasn't on your watchlist. Check /mywatchlist or add it with /watch {symbol}."
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
            desc = f"new disclosure for {symbol} matching category '{rule.category}'"
        else:
            desc = f"new disclosure for {symbol}"
    elif alert_type == AlertType.DAILY_MOVE:
        desc = f"{symbol} daily move ≥ {threshold:g}%"
    elif alert_type == AlertType.PRICE_ABOVE:
        desc = f"{symbol} crosses above {threshold:g}"
    else:
        desc = f"{symbol} crosses below {threshold:g}"

    await update.effective_message.reply_text(f"Alert #{rule.id} set: {desc}.\n{disclaimer()}")


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
            "Watchlist empty. Add a CSE symbol with /watch SYMBOL.\nExample: /watch JKH.N0000"
        )
        return
    await update.effective_message.reply_text("Watchlist:\n" + "\n".join(symbols))


def format_brief_lookup_reply(
    *,
    symbol: str,
    brief: str | None,
    title: str | None = None,
    url: str | None = None,
    ai_enabled: bool | None = None,
) -> str:
    """Read-only /brief reply body. Always ends with NFA.

    Egress-hardens filing URLs (CDN / www.cse.lk only), strips control chars,
    and caps brief body length so Telegram's 4096 limit is not exceeded.
    Distinguishes AI-off from none-yet when ``ai_enabled`` is provided.
    """
    lines = [f"{symbol} filing brief"]
    if title and title.strip():
        clean_title = truncate_disclosure_title(title)
        if clean_title:
            lines.append(f"Disclosure: {clean_title}")
    safe_url = allowed_filing_url(url) if url else None
    if safe_url:
        lines.append(safe_url)
    budget = min(BRIEF_BODY_MAX, brief_budget_for_prefix(lines))
    body = sanitize_brief_body(brief, max_len=budget) if budget > 0 else None
    if body is None:
        if ai_enabled is False:
            return f"{symbol}: {BRIEF_AI_OFF}\n{disclaimer()}"
        return f"{symbol}: {BRIEF_NONE_YET}\n{disclaimer()}"
    lines.append("")
    lines.append(body)
    lines.append("")
    lines.append(disclaimer())
    return "\n".join(lines)


async def cmd_brief(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Read-only latest ready brief from DB — never calls an LLM."""
    if await _rate_limited(update, context):
        return
    storage: Storage = context.application.bot_data["storage"]
    if not update.effective_message:
        return
    if not context.args:
        await update.effective_message.reply_text(BRIEF_USAGE)
        return
    symbol = normalize_symbol(context.args[0])
    if symbol is None:
        await update.effective_message.reply_text(BAD_SYMBOL_HINT)
        return
    row = await storage.get_latest_ready_brief(symbol)
    ai_on = briefs_enabled()
    if row is None:
        await update.effective_message.reply_text(
            format_brief_lookup_reply(symbol=symbol, brief=None, ai_enabled=ai_on)
        )
        return
    await update.effective_message.reply_text(
        format_brief_lookup_reply(
            symbol=str(row.get("symbol") or symbol),
            brief=str(row.get("brief") or ""),
            title=row.get("title") if isinstance(row.get("title"), str) else None,
            url=row.get("url") if isinstance(row.get("url"), str) else None,
            ai_enabled=ai_on,
        )
    )


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
    app.add_handler(CommandHandler("brief", cmd_brief))
    app.add_error_handler(on_error)
    return app
