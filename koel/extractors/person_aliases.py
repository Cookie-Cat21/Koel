"""Merge keys for CSE directors listed under split initials spellings.

Display stays as CSE initials (``K. A. D. D. Perera``), not common/public
first names. Soft-merge only collapses known spelling variants so one person
is not split across boards (e.g. ``M. Pandithage`` vs ``A. M. Pandithage``).
"""

from __future__ import annotations

# name_norm → canonical_merge_key (display is never rewritten)
PERSON_MERGE_KEYS: dict[str, str] = {
    "K A D D PERERA": "kadd_perera",
    "M PANDITHAGE": "m_pandithage",
    "A M PANDITHAGE": "m_pandithage",
    "K BALENDRA": "k_balendra",
    "K N J BALENDRA": "k_balendra",
    "J G A COORAY": "jga_cooray",
    "D S T JAYAWARDENA": "dst_jayawardena",
    "DON S T JAYAWARDENA": "dst_jayawardena",
    "D HASITHA S JAYAWARDENA": "hasitha_jayawardena",
    "D HASITHA STASSEN JAYAWARDENA": "hasitha_jayawardena",
    "I C NANAYAKKARA": "ic_nanayakkara",
    "W D K JAYAWARDENA": "wdk_jayawardena",
    "H A S MADANAYAKE": "has_madanayake",
    "U G MADANAYAKE": "ug_madanayake",
    "S K SHAH": "sk_shah",
    "S H AMARASEKERA": "sh_amarasekera",
    "D A CABRAAL": "da_cabraal",
}


def preferred_display_name(display_name: str, name_norm: str) -> str:
    """Keep CSE initials / as-provided display (no common-name rewrite)."""
    del name_norm  # merge identity only; do not alter label
    return display_name


def alias_merge_key(name_norm: str) -> str | None:
    key = (name_norm or "").strip().upper()
    return PERSON_MERGE_KEYS.get(key)
