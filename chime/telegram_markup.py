"""Inline keyboards for Telegram alerts (fire cards, guided onboard helpers)."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def fire_mute_keyboard(rule_id: int) -> InlineKeyboardMarkup:
    """Tap-to-mute on a fire card — Mute 24h only (cancel stays on /cancel)."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Mute 24h",
                    callback_data=f"mute:{rule_id}:24h",
                ),
            ]
        ]
    )
