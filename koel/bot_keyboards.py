"""Inline keyboards shared by the Telegram bot and (optionally) poller fires."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from koel.domain import disclaimer

WATCH_HELP_TEXT = (
    "Watch a CSE symbol so koel can poll it and fire alerts.\n"
    "Usage: /watch SYMBOL\n"
    "Example: /watch JKH.N0000\n"
    f"{disclaimer()}"
)


def start_menu_keyboard() -> InlineKeyboardMarkup:
    """Primary /start action buttons."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📈 Watch a symbol", callback_data="menu:watch_help"
                )
            ],
            [
                InlineKeyboardButton("🔔 My alerts", callback_data="menu:myalerts"),
                InlineKeyboardButton("📋 Watchlist", callback_data="menu:mywatchlist"),
            ],
            [InlineKeyboardButton("❓ How it works", callback_data="menu:help")],
        ]
    )


DIGEST_OFFER_TEXT = (
    "Want a daily close summary for your watchlist after the market closes "
    "(~14:45 SLT)? One tap — you can turn it off anytime in settings.\n"
    f"{disclaimer()}"
)

DIGEST_ENABLED_CONFIRM = (
    "Daily close summary on. You'll get one Telegram digest after market close "
    "on trading days (watchlist movers, disclosures, alerts fired).\n"
    f"{disclaimer()}"
)


def digest_offer_keyboard() -> InlineKeyboardMarkup:
    """Opt-in button for EOD digest (W8) — never force-enable without consent."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📬 Daily close summary", callback_data="prefs:digest_on"
                )
            ]
        ]
    )


def watch_confirm_keyboard(symbol: str) -> InlineKeyboardMarkup:
    """Deep-link confirm button to add a symbol to the watchlist."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"✅ Watch {symbol}", callback_data=f"watch:{symbol}")]]
    )


def fire_pause_keyboard(rule_id: int) -> InlineKeyboardMarkup | None:
    """Pause button for alert fires — only when mute storage exists.

    Returns None for now (no Python mute API); callers treat None as no markup.
    """
    # Fail closed — non-int / bool must not become callback data.
    if isinstance(rule_id, bool) or not isinstance(rule_id, int) or rule_id <= 0:
        return None
    # Mute is dashboard-only today (alert_rules.muted_until via web PATCH).
    # Skip fire pause until Storage exposes mute/unmute.
    _ = rule_id
    return None


def nl_confirm_keyboard(confirm_payload: str) -> InlineKeyboardMarkup | None:
    """Confirm / cancel buttons for natural-language alert parse."""
    if not isinstance(confirm_payload, str) or not confirm_payload.startswith("nlok:"):
        return None
    if len(confirm_payload) > 64:
        return None
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirm", callback_data=confirm_payload),
                InlineKeyboardButton("❌ Cancel", callback_data="nlcancel"),
            ]
        ]
    )
