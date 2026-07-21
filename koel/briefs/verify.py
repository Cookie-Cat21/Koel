"""Number-verification gate for AI filing briefs.

After the LLM summarizes a filing, every numeric token in the summary must
appear in the source PDF/title text (normalized). Fail closed: a wrong number
never ships as a ready brief.
"""

from __future__ import annotations

import re

# Integers / decimals with optional thousand-separators and optional trailing %.
_NUMBER_RE = re.compile(
    r"\d{1,3}(?:,\d{3})+(?:\.\d+)?%?"
    r"|"
    r"\d+(?:\.\d+)?%?"
)


def extract_numbers(text: str) -> list[str]:
    """Extract numeric tokens from text (integers, decimals, optional trailing %)."""
    if not isinstance(text, str) or not text:
        return []
    return _NUMBER_RE.findall(text)


def normalize_number_token(token: str) -> str:
    """Strip commas and trailing % for membership compare."""
    if not isinstance(token, str):
        return ""
    normalized = token.replace(",", "").strip()
    if normalized.endswith("%"):
        normalized = normalized[:-1]
    return normalized


def brief_numbers_verified(summary: str, source_text: str) -> bool:
    """True iff every number in summary appears in source (after normalize).

    Empty summary → False. Non-str → False.
    Summaries with no numbers → True (titles-only ok).
    """
    if not isinstance(summary, str) or not isinstance(source_text, str):
        return False
    if not summary:
        return False
    summary_nums = extract_numbers(summary)
    if not summary_nums:
        return True

    source_nums = {
        normalize_number_token(token) for token in extract_numbers(source_text)
    }
    source_nums.discard("")
    # Comma-stripped source so "1250" matches source "1,250" even when the
    # token boundary did not capture the comma form as a single number.
    source_no_commas = source_text.replace(",", "")

    for token in summary_nums:
        norm = normalize_number_token(token)
        if not norm:
            continue
        if norm in source_nums:
            continue
        # Accept summary "5%" when source has bare "5" (or "5%") as substring
        # of the comma-stripped source text.
        if norm in source_no_commas:
            continue
        return False
    return True
