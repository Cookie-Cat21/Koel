"""Per-user alert / bot string templates (W9: English + Sinhala).

Fail closed to English for unknown locales or missing keys.
Trigger *content* (rule descriptions) stays English for v1 — only labels wrap.
"""

from __future__ import annotations

from typing import Any

SUPPORTED = ("en", "si")

_NFA_EN = "Not financial advice — informational only."
_NFA_SI = "මෙය මූල්‍ය උපදෙස් නොවේ — තොරතුරු පමණි."

_STRINGS: dict[str, dict[str, str]] = {
    "alert.header": {
        "en": "🔔 {symbol}",
        "si": "🔔 {symbol}",
    },
    "alert.trigger": {
        "en": "Trigger: {trigger}",
        "si": "හේතුව: {trigger}",
    },
    "alert.price": {
        "en": "Price: {price} LKR",
        "si": "මිල: {price} LKR",
    },
    "alert.as_of": {
        "en": "As of {time} SLT",
        "si": "වේලාව {time} SLT",
    },
    "alert.nfa": {
        "en": _NFA_EN,
        "si": _NFA_SI,
    },
    "bot.language_set": {
        "en": f"Language set to English.\n\n{_NFA_EN}",
        "si": f"භාෂාව සිංහල ලෙස සකසන ලදී.\n\n{_NFA_SI}",
    },
    "bot.language_usage": {
        "en": (
            "Alert language: {current}\n"
            "Usage: /language en | si | සිංහල | english | sinhala\n"
            f"{_NFA_EN}"
        ),
        "si": (
            "ඇඟවීම් භාෂාව: {current}\n"
            "භාවිතය: /language en | si | සිංහල | english | sinhala\n"
            f"{_NFA_SI}"
        ),
    },
}

# Aliases accepted by /language (normalized → en|si).
_LOCALE_ALIASES: dict[str, str] = {
    "en": "en",
    "english": "en",
    "si": "si",
    "sinhala": "si",
    "සිංහල": "si",
}


def normalize_locale(raw: object) -> str:
    """Return ``en`` or ``si``. Unknown / non-string → ``en`` (fail closed)."""
    if not isinstance(raw, str):
        return "en"
    stripped = raw.strip()
    if not stripped:
        return "en"
    if stripped in _LOCALE_ALIASES:
        return _LOCALE_ALIASES[stripped]
    key = stripped.lower()
    if key in _LOCALE_ALIASES:
        return _LOCALE_ALIASES[key]
    return "en"


def parse_language_arg(raw: object) -> str | None:
    """Parse a /language argument into ``en``/``si``, or None if unrecognized."""
    if not isinstance(raw, str):
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    if stripped in _LOCALE_ALIASES:
        return _LOCALE_ALIASES[stripped]
    key = stripped.lower()
    if key in _LOCALE_ALIASES:
        return _LOCALE_ALIASES[key]
    return None


def t(key: str, locale: str = "en", **kwargs: Any) -> str:
    """Format template ``key`` for ``locale``; English fallback if missing."""
    loc = normalize_locale(locale)
    table = _STRINGS.get(key)
    if table is None:
        return key
    template = table.get(loc) or table.get("en")
    if template is None:
        return key
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError):
        # Fail soft — return unformatted English/template rather than raise.
        return table.get("en") or template
