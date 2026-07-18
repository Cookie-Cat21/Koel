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
from datetime import UTC, datetime, timedelta
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from chime.adapters.cse import CSEClient, allowed_filing_url
from chime.briefs import briefs_enabled
from chime.domain import (
    _CTRL_RE,
    BRIEF_BODY_MAX,
    MARKET_SYMBOL,
    MAX_ALERT_THRESHOLD,
    NOTICE_ALERT_TYPES,
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
    "/alert SYMBOL eps above|below X\n"
    "/alert SYMBOL eps yoy above|below PCT\n"
    "/alert SYMBOL rev yoy above|below PCT\n"
    "/alert SYMBOL profit yoy above|below PCT\n"
    "/alert SYMBOL volume MULTIPLIER\n"
    "/alert SYMBOL volup MULTIPLIER\n"
    "/alert SYMBOL voldown MULTIPLIER\n"
    "/alert SYMBOL crossing MULTIPLIER\n"
    "/alert SYMBOL print QTY\n"
    "/alert SYMBOL gap PERCENT\n"
    "/alert SYMBOL buyin\n"
    "/alert SYMBOL noncompliance\n"
    "/alert MARKET halt\n"
    "/alert SYMBOL bidheavy MULTIPLIER\n"
    "/alert SYMBOL askheavy MULTIPLIER\n"
    "Example: /alert JKH.N0000 volume 5\n"
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
# Phase A: guided chips; Browse dash + CATEGORY + optional AI brief stay on /help.
START_TEXT = (
    "Quiverly watches the Colombo Stock Exchange and pings Telegram when "
    "your rule hits — price, daily %, or a new disclosure. "
    "Tap a symbol below to arm a watch + alert (or /help for commands).\n"
    "Browse dash manages rules; push stays here. "
    "Disclosure [CATEGORY] + optional AI brief when enabled.\n"
    f"{disclaimer()}"
)

# Guided /start chips — liquid names retail users already know (labels, not tips).
_START_SYMBOL_CHIPS: tuple[tuple[str, str], ...] = (
    ("JKH.N0000", "JKH"),
    ("COMB.N0000", "COMB"),
    ("DIAL.N0000", "DIAL"),
    ("SAMP.N0000", "SAMP"),
    ("HNB.N0000", "HNB"),
)


def _start_symbol_keyboard() -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(label, callback_data=f"onboard:sym:{symbol}")
        for symbol, label in _START_SYMBOL_CHIPS
    ]
    return InlineKeyboardMarkup(
        [
            row[:3],
            row[3:],
            [InlineKeyboardButton("Type a ticker instead", callback_data="onboard:manual")],
        ]
    )


def _start_rule_keyboard(symbol: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Price above", callback_data=f"onboard:rule:{symbol}:above"
                ),
                InlineKeyboardButton(
                    "Price below", callback_data=f"onboard:rule:{symbol}:below"
                ),
            ],
            [
                InlineKeyboardButton(
                    "Daily move %", callback_data=f"onboard:rule:{symbol}:move"
                ),
                InlineKeyboardButton(
                    "New disclosure",
                    callback_data=f"onboard:rule:{symbol}:disclosure",
                ),
            ],
            [InlineKeyboardButton("← Pick another symbol", callback_data="onboard:restart")],
        ]
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
    "optional AI brief when enabled). Also volume/gap/print/buyin/halt — see /alert.\n"
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


def _env_positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not isinstance(raw, str) or not raw.strip():
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        return default
    return value if value >= 1 else default


def free_alert_cap() -> int:
    """Match dash ``DASH_FREE_ALERT_QUOTA`` / FREE_ALERT_CAP=3."""
    return _env_positive_int("DASH_FREE_ALERT_QUOTA", 3)


def free_watch_cap() -> int:
    """Match dash ``DASH_FREE_WATCH_QUOTA`` / FREE_WATCH_CAP=5."""
    return _env_positive_int("DASH_FREE_WATCH_QUOTA", 5)


def normalize_symbol(raw: str) -> str | None:
    # Fail closed — non-strings used to throw on .strip mid /watch|/alert|/brief.
    if not isinstance(raw, str):
        return None
    s = raw.strip().upper()
    if not s:
        return None
    # Bare tickers (JKH) → common-share form JKH.N0000 for CSE lookups.
    if "." not in s and re.fullmatch(r"[A-Z0-9]{1,12}", s):
        s = f"{s}.N0000"
    if not SYMBOL_RE.match(s):
        return None
    return s


async def _watch_quota_blocked(storage: Storage, user_id: int, symbol: str) -> str | None:
    """Return an error reply when free watch cap would be exceeded."""
    watchlist = await storage.list_watchlist(user_id)
    if symbol in watchlist:
        return None
    cap = free_watch_cap()
    if len(watchlist) >= cap:
        return (
            f"Free tier allows up to {cap} watches. "
            f"Remove one with /unwatch, or see Pro on the dash pricing page.\n"
            f"{disclaimer()}"
        )
    return None


async def _alert_quota_blocked(
    storage: Storage,
    user_id: int,
    *,
    symbol: str,
    alert_type: AlertType,
    threshold: float | None,
) -> str | None:
    """Return an error reply when free alert cap would block a *new* rule."""
    rules = await storage.list_alerts(user_id)
    for rule in rules:
        if (
            rule.symbol == symbol
            and rule.type == alert_type
            and rule.threshold == threshold
        ):
            return None  # idempotent create — not a new slot
    cap = free_alert_cap()
    if len(rules) >= cap:
        return (
            f"Free tier allows up to {cap} active alerts. "
            f"Cancel one with /cancel ALERT_ID, or see Pro on the dash pricing page.\n"
            f"{disclaimer()}"
        )
    return None


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

    # Financial PDF calc / YoY: /alert SYMBOL eps above X
    # /alert SYMBOL eps yoy above PCT | rev yoy … | profit yoy …
    if kind in ("eps", "rev", "revenue", "profit", "pat"):
        rest = [a.lower() if isinstance(a, str) else "" for a in args[2:]]
        metric = "eps" if kind == "eps" else ("rev" if kind in ("rev", "revenue") else "profit")
        direction: str | None = None
        threshold_token: str | None = None
        if rest and rest[0] in ("above", "below") and len(rest) >= 2:
            # absolute EPS only
            if metric != "eps":
                return None, (
                    "Absolute thresholds are only for EPS. "
                    f"Try: /alert SYMBOL eps above X\n{ALERT_USAGE}"
                )
            direction = rest[0]
            threshold_token = args[3] if len(args) > 3 else None
            if len(args) > 4:
                return None, (
                    f"Unexpected extra text after eps {direction}. "
                    f"Example: /alert JKH.N0000 eps {direction} 5\n{ALERT_USAGE}"
                )
            abs_map = {
                "above": AlertType.EPS_ABOVE,
                "below": AlertType.EPS_BELOW,
            }
            threshold = _parse_threshold_token(str(threshold_token or ""))
            if threshold is None:
                return None, (
                    "EPS threshold must be a positive finite number. "
                    f"Example: /alert JKH.N0000 eps {direction} 5\n{ALERT_USAGE}"
                )
            return ParsedAlert(abs_map[direction], threshold), None
        if rest and rest[0] == "yoy" and len(rest) >= 3 and rest[1] in ("above", "below"):
            direction = rest[1]
            threshold_token = args[4] if len(args) > 4 else None
            if len(args) > 5:
                return None, (
                    f"Unexpected extra text after yoy {direction}. "
                    f"Example: /alert JKH.N0000 {kind} yoy {direction} 10\n{ALERT_USAGE}"
                )
            yoy_map: dict[tuple[str, str], AlertType] = {
                ("eps", "above"): AlertType.EPS_YOY_ABOVE,
                ("eps", "below"): AlertType.EPS_YOY_BELOW,
                ("rev", "above"): AlertType.REV_YOY_ABOVE,
                ("rev", "below"): AlertType.REV_YOY_BELOW,
                ("profit", "above"): AlertType.PROFIT_YOY_ABOVE,
                ("profit", "below"): AlertType.PROFIT_YOY_BELOW,
            }
            key = (metric, direction)
            if key not in yoy_map:
                return None, ALERT_USAGE
            threshold = _parse_threshold_token(str(threshold_token or ""))
            if threshold is None:
                return None, (
                    "YoY threshold must be a positive percent "
                    f"(e.g. 10 for +10% / decline of 10%).\n{ALERT_USAGE}"
                )
            return ParsedAlert(yoy_map[key], threshold), None
        return None, (
            "Try: /alert SYMBOL eps above X\n"
            "Or: /alert SYMBOL eps yoy above PCT\n"
            f"{ALERT_USAGE}"
        )

    # Activity / notice kinds (peers: Tijori volume, Stock Alarm gap/volume).
    activity_kinds = {
        "volume": AlertType.VOLUME_SPIKE,
        "volspike": AlertType.VOLUME_SPIKE,
        "volup": AlertType.VOLUME_UP,
        "voldown": AlertType.VOLUME_DOWN,
        "crossing": AlertType.CROSSING_VOLUME,
        "xvol": AlertType.CROSSING_VOLUME,
        "print": AlertType.BIG_PRINT,
        "bigprint": AlertType.BIG_PRINT,
        "gap": AlertType.GAP,
        "bidheavy": AlertType.BID_HEAVY,
        "bid_heavy": AlertType.BID_HEAVY,
        "askheavy": AlertType.ASK_HEAVY,
        "ask_heavy": AlertType.ASK_HEAVY,
    }
    if kind in activity_kinds:
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
                f"Example: /alert JKH.N0000 {kind} 5\n{ALERT_USAGE}"
            )
        return ParsedAlert(activity_kinds[kind], threshold), None
    notice_kinds = {
        "buyin": AlertType.BUY_IN,
        "buy_in": AlertType.BUY_IN,
        "noncompliance": AlertType.NON_COMPLIANCE,
        "non_compliance": AlertType.NON_COMPLIANCE,
        "halt": AlertType.HALT,
        "notice": AlertType.HALT,
    }
    if kind in notice_kinds:
        if len(args) > 2:
            return None, (
                f"Unexpected extra text after {kind}. "
                f"Example: /alert JKH.N0000 {kind}\n{ALERT_USAGE}"
            )
        return ParsedAlert(notice_kinds[kind], None), None
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
        await update.effective_message.reply_text(
            START_TEXT,
            reply_markup=_start_symbol_keyboard(),
        )


async def onboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guided /start: pick symbol → pick rule → create alert (or prompt for threshold)."""
    query = update.callback_query
    if query is None or not query.data:
        return
    await query.answer()
    data = query.data
    if not data.startswith("onboard:"):
        return

    storage: Storage = context.application.bot_data["storage"]
    cse: CSEClient = context.application.bot_data["cse"]
    user_id = await _user_id(storage, update)
    if user_id is None:
        return

    if data == "onboard:manual":
        await query.edit_message_text(
            _clamp_telegram_message(
                "Type a ticker with /watch SYMBOL, then /alert …\n"
                f"Example: /watch JKH.N0000\n{disclaimer()}"
            )
        )
        return

    if data == "onboard:restart":
        await query.edit_message_text(
            START_TEXT,
            reply_markup=_start_symbol_keyboard(),
        )
        return

    if data.startswith("onboard:sym:"):
        symbol = data.removeprefix("onboard:sym:").strip().upper()
        status, info = await _lookup_symbol(cse, symbol)
        if status == "upstream":
            await query.edit_message_text(
                f"cse.lk unreachable, try again.\n{disclaimer()}"
            )
            return
        if status == "not_found" or info is None:
            await query.edit_message_text(
                f"Couldn't find {symbol} on cse.lk.\n{disclaimer()}"
            )
            return
        watch_block = await _watch_quota_blocked(storage, user_id, symbol)
        if watch_block is not None:
            await query.edit_message_text(watch_block)
            return
        await storage.upsert_stock(symbol, info.name)
        await storage.add_watch(user_id, symbol)
        name = info.name or symbol
        price_s = f"{info.price:g}" if info.price is not None else "?"
        await query.edit_message_text(
            _clamp_telegram_message(
                f"Watching {symbol} ({name}) — last {price_s}.\n"
                f"Pick a rule type:\n{disclaimer()}"
            ),
            reply_markup=_start_rule_keyboard(symbol),
        )
        return

    if data.startswith("onboard:rule:"):
        parts = data.split(":")
        # onboard:rule:SYMBOL:kind
        if len(parts) < 4:
            return
        symbol = parts[2].strip().upper()
        kind = parts[3].strip().lower()
        status, info = await _lookup_symbol(cse, symbol)
        if status != "ok" or info is None:
            await query.edit_message_text(
                f"Couldn't refresh {symbol}. Try /watch {symbol}.\n{disclaimer()}"
            )
            return
        watch_block = await _watch_quota_blocked(storage, user_id, symbol)
        if watch_block is not None:
            await query.edit_message_text(watch_block)
            return
        await storage.upsert_stock(symbol, info.name)
        await storage.add_watch(user_id, symbol)
        price = info.price

        if kind == "disclosure":
            alert_block = await _alert_quota_blocked(
                storage,
                user_id,
                symbol=symbol,
                alert_type=AlertType.DISCLOSURE,
                threshold=None,
            )
            if alert_block is not None:
                await query.edit_message_text(alert_block)
                return
            rule = await storage.create_alert_rule(
                user_id, symbol, AlertType.DISCLOSURE, None
            )
            await query.edit_message_text(
                _clamp_telegram_message(
                    f"Alert #{rule.id} set: new disclosure for {symbol}.\n"
                    f"You'll get a Telegram ping when a filing lands.\n{disclaimer()}"
                )
            )
            return

        if kind == "move":
            thr = 3.0
            alert_block = await _alert_quota_blocked(
                storage,
                user_id,
                symbol=symbol,
                alert_type=AlertType.DAILY_MOVE,
                threshold=thr,
            )
            if alert_block is not None:
                await query.edit_message_text(alert_block)
                return
            rule = await storage.create_alert_rule(
                user_id, symbol, AlertType.DAILY_MOVE, thr
            )
            await query.edit_message_text(
                _clamp_telegram_message(
                    f"Alert #{rule.id} set: {symbol} daily move ≥ {thr:g}%.\n"
                    f"Change with /alert {symbol} move PERCENT\n{disclaimer()}"
                )
            )
            return

        if kind in ("above", "below") and price is not None and math.isfinite(price):
            # Sensible default: ±2% from last trade (not a tip — just a starter threshold).
            if kind == "above":
                thr = round(price * 1.02, 2)
                alert_type = AlertType.PRICE_ABOVE
                side = "above"
            else:
                thr = round(price * 0.98, 2)
                alert_type = AlertType.PRICE_BELOW
                side = "below"
            alert_block = await _alert_quota_blocked(
                storage,
                user_id,
                symbol=symbol,
                alert_type=alert_type,
                threshold=thr,
            )
            if alert_block is not None:
                await query.edit_message_text(alert_block)
                return
            rule = await storage.create_alert_rule(
                user_id, symbol, alert_type, thr
            )
            await query.edit_message_text(
                _clamp_telegram_message(
                    f"Alert #{rule.id} set: {symbol} {side} {thr:g} "
                    f"(last {price:g}).\n"
                    f"Tweak: /alert {symbol} {side} PRICE\n{disclaimer()}"
                )
            )
            return

        await query.edit_message_text(
            _clamp_telegram_message(
                f"Set a threshold manually:\n"
                f"/alert {symbol} above PRICE\n"
                f"/alert {symbol} below PRICE\n{disclaimer()}"
            )
        )
        return


async def mute_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tap-to-mute on fire cards: ``mute:{rule_id}:24h``."""
    query = update.callback_query
    if query is None or not query.data:
        return
    await query.answer()
    data = query.data
    if not data.startswith("mute:"):
        return
    parts = data.split(":")
    if len(parts) != 3 or parts[2] != "24h":
        return
    try:
        rule_id = int(parts[1])
    except ValueError:
        return
    if rule_id < 1:
        return
    storage: Storage = context.application.bot_data["storage"]
    user_id = await _user_id(storage, update)
    if user_id is None:
        return
    muted_until = datetime.now(UTC) + timedelta(hours=24)
    ok = await storage.mute_alert(user_id, rule_id, muted_until)
    if ok:
        await query.edit_message_reply_markup(reply_markup=None)
        # Prefer a short confirmation reply; keep original fire text intact.
        if query.message is not None:
            await query.message.reply_text(
                _clamp_telegram_message(
                    f"Muted alert #{rule_id} for 24 hours.\n{disclaimer()}"
                )
            )
    else:
        if query.message is not None:
            await query.message.reply_text(
                _clamp_telegram_message(
                    f"Couldn't mute #{rule_id} — check /myalerts.\n{disclaimer()}"
                )
            )


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
    blocked = await _watch_quota_blocked(storage, user_id, symbol)
    if blocked is not None:
        await update.effective_message.reply_text(blocked)
        return
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

    # Market-wide halt notices use synthetic MARKET stock (seeded in migrations).
    if alert_type == AlertType.HALT and symbol == MARKET_SYMBOL:
        user_id = await _user_id(storage, update)
        assert user_id is not None
        alert_block = await _alert_quota_blocked(
            storage,
            user_id,
            symbol=symbol,
            alert_type=alert_type,
            threshold=threshold,
        )
        if alert_block is not None:
            await update.effective_message.reply_text(alert_block)
            return
        await storage.upsert_stock(
            MARKET_SYMBOL, "Colombo Stock Exchange (market-wide)"
        )
        rule = await storage.create_alert_rule(
            user_id, symbol, alert_type, threshold, category=category
        )
        await update.effective_message.reply_text(
            _clamp_telegram_message(
                f"Alert #{rule.id} set: market halt/notice alerts.\n{disclaimer()}"
            )
        )
        return

    status, info = await _lookup_symbol(cse, symbol)
    if status == "upstream":
        await update.effective_message.reply_text(
            f"cse.lk unreachable, try again.\n{disclaimer()}"
        )
        return
    if status == "not_found":
        await update.effective_message.reply_text(
            f"Couldn't find {symbol} on cse.lk. Check the ticker and try again.\n"
            f"{disclaimer()}"
        )
        return
    assert info is not None

    user_id = await _user_id(storage, update)
    assert user_id is not None
    watch_block = await _watch_quota_blocked(storage, user_id, symbol)
    if watch_block is not None:
        await update.effective_message.reply_text(watch_block)
        return
    alert_block = await _alert_quota_blocked(
        storage,
        user_id,
        symbol=symbol,
        alert_type=alert_type,
        threshold=threshold,
    )
    if alert_block is not None:
        await update.effective_message.reply_text(alert_block)
        return
    await storage.upsert_stock(symbol, info.name)
    rule = await storage.create_alert_rule(
        user_id, symbol, alert_type, threshold, category=category
    )

    thr_s = f"{threshold:g}" if threshold is not None and math.isfinite(threshold) else "?"
    if alert_type == AlertType.DISCLOSURE:
        cat = sanitize_disclosure_category(rule.category)
        if cat:
            desc = f"new disclosure for {symbol} matching category '{cat}'"
        else:
            desc = f"new disclosure for {symbol}"
    elif alert_type == AlertType.DAILY_MOVE:
        desc = f"{symbol} daily move ≥ {thr_s}%"
    elif alert_type == AlertType.PRICE_ABOVE:
        desc = f"{symbol} crosses above {thr_s}"
    elif alert_type == AlertType.PRICE_BELOW:
        desc = f"{symbol} crosses below {thr_s}"
    elif alert_type == AlertType.VOLUME_SPIKE:
        desc = f"{symbol} volume ≥ {thr_s}× recent average"
    elif alert_type == AlertType.VOLUME_UP:
        desc = f"{symbol} heavy volume while price up (≥ {thr_s}× avg)"
    elif alert_type == AlertType.VOLUME_DOWN:
        desc = f"{symbol} heavy volume while price down (≥ {thr_s}× avg)"
    elif alert_type == AlertType.CROSSING_VOLUME:
        desc = f"{symbol} crossing volume ≥ {thr_s}× recent average"
    elif alert_type == AlertType.BIG_PRINT:
        desc = f"{symbol} single print ≥ {thr_s} shares"
    elif alert_type == AlertType.GAP:
        desc = f"{symbol} open gap ≥ {thr_s}%"
    elif alert_type == AlertType.BUY_IN:
        desc = f"{symbol} buy-in board notice"
    elif alert_type == AlertType.NON_COMPLIANCE:
        desc = f"{symbol} non-compliance notice"
    elif alert_type == AlertType.HALT:
        desc = f"{symbol} market halt/notice"
    elif alert_type == AlertType.BID_HEAVY:
        desc = f"{symbol} bid-heavy order book ≥ {thr_s}× (bids/asks)"
    elif alert_type == AlertType.ASK_HEAVY:
        desc = f"{symbol} ask-heavy order book ≥ {thr_s}× (asks/bids)"
    elif alert_type == AlertType.EPS_ABOVE:
        desc = (
            f"{symbol} next financial filing basic EPS above {thr_s} "
            "(not live price)"
        )
    elif alert_type == AlertType.EPS_BELOW:
        desc = (
            f"{symbol} next financial filing basic EPS below {thr_s} "
            "(not live price)"
        )
    elif alert_type == AlertType.EPS_YOY_ABOVE:
        desc = f"{symbol} filing EPS YoY above +{thr_s}%"
    elif alert_type == AlertType.EPS_YOY_BELOW:
        desc = f"{symbol} filing EPS YoY below -{thr_s}%"
    elif alert_type == AlertType.REV_YOY_ABOVE:
        desc = f"{symbol} filing revenue YoY above +{thr_s}%"
    elif alert_type == AlertType.REV_YOY_BELOW:
        desc = f"{symbol} filing revenue YoY below -{thr_s}%"
    elif alert_type == AlertType.PROFIT_YOY_ABOVE:
        desc = f"{symbol} filing profit YoY above +{thr_s}%"
    elif alert_type == AlertType.PROFIT_YOY_BELOW:
        desc = f"{symbol} filing profit YoY below -{thr_s}%"
    else:
        desc = f"{symbol} alert"

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
    if len(context.args) > 1:
        await update.effective_message.reply_text(
            f"Unexpected extra text after alert id.\n{CANCEL_USAGE}"
        )
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
            "/alert JKH.N0000 volume 5\n"
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
        elif r.type in NOTICE_ALERT_TYPES:
            label = {
                AlertType.BUY_IN: "buyin",
                AlertType.NON_COMPLIANCE: "noncompliance",
                AlertType.HALT: "halt",
            }.get(r.type, r.type.value)
            lines.append(f"#{r.id} {sym} {label}")
        else:
            # Null / non-finite threshold must not TypeError the whole handler
            # (corrupt DB row / legacy insert); show "?" and keep listing.
            thr = r.threshold
            thr_s = f"{thr:g}" if thr is not None and math.isfinite(thr) else "?"
            if r.type == AlertType.DAILY_MOVE:
                lines.append(f"#{r.id} {sym} move {thr_s}%")
            elif r.type == AlertType.PRICE_ABOVE:
                lines.append(f"#{r.id} {sym} above {thr_s}")
            elif r.type == AlertType.PRICE_BELOW:
                lines.append(f"#{r.id} {sym} below {thr_s}")
            elif r.type == AlertType.VOLUME_SPIKE:
                lines.append(f"#{r.id} {sym} volume {thr_s}x")
            elif r.type == AlertType.VOLUME_UP:
                lines.append(f"#{r.id} {sym} volup {thr_s}x")
            elif r.type == AlertType.VOLUME_DOWN:
                lines.append(f"#{r.id} {sym} voldown {thr_s}x")
            elif r.type == AlertType.CROSSING_VOLUME:
                lines.append(f"#{r.id} {sym} crossing {thr_s}x")
            elif r.type == AlertType.BIG_PRINT:
                lines.append(f"#{r.id} {sym} print {thr_s}")
            elif r.type == AlertType.GAP:
                lines.append(f"#{r.id} {sym} gap {thr_s}%")
            elif r.type == AlertType.BID_HEAVY:
                lines.append(f"#{r.id} {sym} bidheavy {thr_s}x")
            elif r.type == AlertType.ASK_HEAVY:
                lines.append(f"#{r.id} {sym} askheavy {thr_s}x")
            else:
                lines.append(f"#{r.id} {sym} {r.type.value} {thr_s}")
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
    # Fail closed — non-string PG fields used to soft-accept via str()
    # (ints/None became "123"/"None" in /brief Telegram egress).
    raw_sym = row.get("symbol")
    sym_out = (
        raw_sym.strip().upper()
        if isinstance(raw_sym, str) and raw_sym.strip()
        else symbol
    )
    raw_brief = row.get("brief")
    brief_out = raw_brief if isinstance(raw_brief, str) else ""
    await update.effective_message.reply_text(
        format_brief_lookup_reply(
            symbol=sym_out,
            brief=brief_out,
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
    app.add_handler(CallbackQueryHandler(onboard_callback, pattern=r"^onboard:"))
    app.add_handler(CallbackQueryHandler(mute_callback, pattern=r"^mute:"))
    app.add_error_handler(on_error)
    return app
