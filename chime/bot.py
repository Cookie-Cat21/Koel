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
    _CTRL_RE,
    BRIEF_BODY_MAX,
    MAX_ALERT_THRESHOLD,
    AlertType,
    PriceSnapshot,
    _clamp_telegram_message,
    brief_budget_for_prefix,
    disclaimer,
    sanitize_brief_body,
    sanitize_disclosure_category,
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
    # Fail closed — non-int / bool bot_data used to throw on int() mid /watch.
    if isinstance(raw, bool) or not isinstance(raw, int):
        return 20
    return raw if raw >= 0 else 20


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
    # Fail closed — non-string getenv mocks used to throw on .strip mid boot.
    raw_env = os.getenv("BOT_CMD_RATE_PER_MINUTE", "")
    raw = raw_env.strip() if isinstance(raw_env, str) else ""
    if not raw:
        return 20
    try:
        value = int(raw)
    except ValueError:
        return 20
    return 20 if value < 0 else value


# ≤3 lines including NFA; command dump lives on /help only (WS-014 / E7-B02).
# Wave5/w20: Browse dash note + disclosure CATEGORY + optional AI brief.
START_TEXT = (
    "Chime watches the Colombo Stock Exchange and pings Telegram on price, "
    "move, or disclosure alerts — Browse dash mirrors watchlists; "
    "push stays here.\n"
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
    "(missing publish time → no fire; CATEGORY = category substring; "
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
    # Fail closed — non-strings used to throw on .strip mid /watch|/alert|/brief.
    if not isinstance(raw, str):
        return None
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
    # Fail closed — non-strings used to throw on .strip mid /alert parse.
    if not isinstance(raw, str):
        return None
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
    if threshold > MAX_ALERT_THRESHOLD:
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
    # Fail closed — non-string kind used to throw on .lower mid /alert parse.
    if not isinstance(args[1], str):
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
                f"at most {MAX_ALERT_THRESHOLD:g} "
                "(use 1000 or 1,000 — not nan/inf or huge values). "
                f"Example: /alert JKH.N0000 {kind} 100\n{ALERT_USAGE}"
            )
        if kind == "above":
            return ParsedAlert(AlertType.PRICE_ABOVE, threshold), None
        if kind == "below":
            return ParsedAlert(AlertType.PRICE_BELOW, threshold), None
        return ParsedAlert(AlertType.DAILY_MOVE, threshold), None
    if kind in ("disclosure", "announcement"):
        # Fail closed — non-string category tokens used to throw on " ".join
        # mid /alert disclosure parse (TypeError aborts the handler).
        cat_parts = [a for a in args[2:] if isinstance(a, str)]
        raw_cat = " ".join(cat_parts).strip() or None
        category = sanitize_disclosure_category(raw_cat)
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
        # Parallel /watch tone: outcome first, then that pushes stop.
        if deactivated:
            msg = (
                f"Stopped watching {symbol}. "
                f"Deactivated {deactivated} alert(s) — no more pushes for it."
            )
        else:
            msg = f"Stopped watching {symbol}. Alerts for it won't fire."
        await update.effective_message.reply_text(msg)
    elif deactivated:
        await update.effective_message.reply_text(
            f"{symbol} wasn't on your watchlist, but deactivated "
            f"{deactivated} orphan alert(s) — they won't fire."
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
        cat = sanitize_disclosure_category(rule.category)
        if cat:
            desc = f"new disclosure for {symbol} matching category '{cat}'"
        else:
            desc = f"new disclosure for {symbol}"
    elif alert_type == AlertType.DAILY_MOVE:
        thr_s = f"{threshold:g}" if threshold is not None and math.isfinite(threshold) else "?"
        desc = f"{symbol} daily move ≥ {thr_s}%"
    elif alert_type == AlertType.PRICE_ABOVE:
        thr_s = f"{threshold:g}" if threshold is not None and math.isfinite(threshold) else "?"
        desc = f"{symbol} crosses above {thr_s}"
    else:
        thr_s = f"{threshold:g}" if threshold is not None and math.isfinite(threshold) else "?"
        desc = f"{symbol} crosses below {thr_s}"

    # Clamp: hostile/huge category (or pathological rule id) must not blow past 4096
    # — an oversize confirm would fail while the rule is already persisted.
    await update.effective_message.reply_text(
        _clamp_telegram_message(f"Alert #{rule.id} set: {desc}.\n{disclaimer()}")
    )


def parse_cancel_alert_id(raw: str) -> int | None:
    """Parse ``/cancel`` alert id; reject non-digits and oversize ints.

    Hostile input like ``9``×10k used to become a multi-KB Telegram body and a
    pathological DB param. Digits-only + ≤18 digits stays under bigint range and
    keeps confirm/error replies well under Telegram's 4096 limit.
    """
    # Fail closed — non-strings used to throw on .lstrip mid /cancel.
    if not isinstance(raw, str):
        return None
    cleaned = raw.lstrip("#").strip()
    if not cleaned.isdigit() or len(cleaned) > 18:
        return None
    rule_id = int(cleaned)
    if rule_id <= 0:
        return None
    return rule_id


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _rate_limited(update, context):
        return
    storage: Storage = context.application.bot_data["storage"]
    if not update.effective_message:
        return
    if not context.args:
        await update.effective_message.reply_text(CANCEL_USAGE)
        return
    raw_arg = context.args[0]
    rule_id = parse_cancel_alert_id(raw_arg)
    if rule_id is None:
        # Distinguish empty/zero from garbage for actionable copy.
        # Fail closed — non-string args used to throw on .lstrip after parse None.
        cleaned = raw_arg.lstrip("#").strip() if isinstance(raw_arg, str) else ""
        if (
            cleaned.isdigit()
            and len(cleaned) <= 18
            and int(cleaned) <= 0
        ):
            await update.effective_message.reply_text(
                "Alert id must be a positive number. Usage: /cancel ALERT_ID"
            )
        else:
            await update.effective_message.reply_text(
                "Alert id must be a number. Usage: /cancel ALERT_ID"
            )
        return
    user_id = await _user_id(storage, update)
    assert user_id is not None
    ok = await storage.deactivate_alert(user_id, rule_id)
    if ok:
        await update.effective_message.reply_text(
            _clamp_telegram_message(f"Cancelled alert #{rule_id}.")
        )
    else:
        await update.effective_message.reply_text(
            _clamp_telegram_message(
                f"No active alert #{rule_id} found. Check /myalerts."
            )
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
            "/alert JKH.N0000 disclosure Financial\n"
            f"{disclaimer()}"
        )
        return
    lines = ["Your alerts:"]
    for r in rules:
        # Fail closed — non-string DB symbols used to throw on re.sub mid /myalerts.
        sym_raw = r.symbol if isinstance(r.symbol, str) else ""
        sym = _CTRL_RE.sub("", sym_raw).strip() or "?"
        if r.type == AlertType.DISCLOSURE:
            cat = sanitize_disclosure_category(r.category)
            if cat:
                lines.append(f"#{r.id} {sym} disclosure {cat}")
            else:
                lines.append(f"#{r.id} {sym} disclosure")
        else:
            # Null / non-finite threshold must not TypeError the whole handler
            # (corrupt DB row / legacy insert); show "?" and keep listing.
            thr = r.threshold
            thr_s = f"{thr:g}" if thr is not None and math.isfinite(thr) else "?"
            if r.type == AlertType.DAILY_MOVE:
                lines.append(f"#{r.id} {sym} move {thr_s}%")
            elif r.type == AlertType.PRICE_ABOVE:
                lines.append(f"#{r.id} {sym} above {thr_s}")
            else:
                lines.append(f"#{r.id} {sym} below {thr_s}")
    # Category disclosure rules share a symbol with any-disclosure rules; the
    # numeric id from this list is the only way to cancel one filter.
    lines.append("")
    lines.append("Cancel with /cancel ALERT_ID")
    lines.append("")
    lines.append(disclaimer())
    await update.effective_message.reply_text(_clamp_telegram_message("\n".join(lines)))


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
    clean = [
        # Fail closed — non-string watchlist rows used to throw on re.sub.
        _CTRL_RE.sub("", s if isinstance(s, str) else "").strip() or "?"
        for s in symbols
    ]
    await update.effective_message.reply_text(
        _clamp_telegram_message("Watchlist:\n" + "\n".join(clean))
    )


def format_brief_lookup_reply(
    *,
    symbol: str,
    brief: str | None,
    title: str | None = None,
    url: str | None = None,
    ai_enabled: bool | None = None,
) -> str:
    """Read-only /brief reply body. Always ends with NFA.

    Egress-hardens filing URLs (CDN / www.cse.lk only), strips control chars
    from symbol/title/brief, and hard-clamps under Telegram's 4096 limit
    (matching ``format_alert_message`` / ``format_brief_followup``). A hostile
    DB symbol must not inject nulls or blow past the cap. Distinguishes AI-off
    from none-yet when ``ai_enabled`` is provided.
    """
    # Fail closed — non-strings used to throw on re.sub mid /brief reply
    # (parity format_brief_followup / format_dead_letter_notify).
    if not isinstance(symbol, str):
        symbol = ""
    clean_symbol = _CTRL_RE.sub("", symbol).strip() or "?"
    # CSE tickers are short; cap so a hostile DB row cannot starve the brief budget.
    if len(clean_symbol) > 32:
        clean_symbol = clean_symbol[:31].rstrip() + "…"
    lines = [f"{clean_symbol} filing brief"]
    # Fail closed — non-string truthy title used to throw on .strip mid /brief.
    if isinstance(title, str) and title.strip():
        clean_title = truncate_disclosure_title(title)
        if clean_title:
            lines.append(f"Disclosure: {clean_title}")
    # Fail closed — truthy non-string url must not reach allowlist gate.
    safe_url = allowed_filing_url(url) if isinstance(url, str) and url else None
    if safe_url:
        lines.append(safe_url)
    budget = min(BRIEF_BODY_MAX, brief_budget_for_prefix(lines))
    body = sanitize_brief_body(brief, max_len=budget) if budget > 0 else None
    if body is None:
        if ai_enabled is False:
            return _clamp_telegram_message(
                f"{clean_symbol}: {BRIEF_AI_OFF}\n{disclaimer()}"
            )
        return _clamp_telegram_message(
            f"{clean_symbol}: {BRIEF_NONE_YET}\n{disclaimer()}"
        )
    lines.append("")
    lines.append(body)
    lines.append("")
    lines.append(disclaimer())
    return _clamp_telegram_message("\n".join(lines))


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
