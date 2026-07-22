"""Filing category tags for Tijori-style disclosure prefs.

Maps CSE ``announcementCategory`` / title text → coarse tags used in
``users.disclosure_category_prefs``. Research-only; never buy/sell language.
"""

from __future__ import annotations

import re

from koel.domain import DISCLOSURE_CATEGORY_MAX

# Canonical tags (settings checkboxes + prefs storage).
FILING_CATEGORY_TAGS: tuple[str, ...] = (
    "results",
    "board",
    "corporate_action",
    "shareholding",
    "other",
)

_TAG_SET = frozenset(FILING_CATEGORY_TAGS)

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "results",
        re.compile(
            r"\b(interim|annual|quarter|q[1-4]|financial\s+statement|"
            r"earnings|results?|profit|eps)\b",
            re.I,
        ),
    ),
    (
        "board",
        re.compile(
            r"\b(board\s+meeting|directors?|appointment|resignation|"
            r"outcome\s+of\s+board)\b",
            re.I,
        ),
    ),
    (
        "corporate_action",
        re.compile(
            r"\b(dividend|bonus|split|rights?|subdivision|consolidation|"
            r"capital\s+reduction|buy[\s-]?back)\b",
            re.I,
        ),
    ),
    (
        "shareholding",
        re.compile(
            r"\b(shareholding|substantial\s+share|director.?s?\s+deal|"
            r"insider|promoter|pledge)\b",
            re.I,
        ),
    ),
)


def normalize_filing_tags(raw: object) -> list[str]:
    """Sanitize a prefs list → unique canonical tags (stable order)."""
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.split(",")]
    elif isinstance(raw, (list, tuple, set)):
        parts = []
        for item in raw:
            if isinstance(item, str):
                parts.append(item.strip())
    else:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        tag = p.casefold().replace(" ", "_").replace("-", "_")
        if tag not in _TAG_SET or tag in seen:
            continue
        seen.add(tag)
        out.append(tag)
    return out


def classify_filing(*, category: str | None, title: str | None) -> str:
    """Return one canonical tag for a disclosure row."""
    hay = " ".join(
        x.strip()
        for x in (category or "", title or "")
        if isinstance(x, str) and x.strip()
    )
    if not hay:
        return "other"
    if len(hay) > DISCLOSURE_CATEGORY_MAX * 4:
        hay = hay[: DISCLOSURE_CATEGORY_MAX * 4]
    for tag, pat in _PATTERNS:
        if pat.search(hay):
            return tag
    return "other"


def filing_tag_allowed(tag: str, prefs: list[str] | tuple[str, ...] | None) -> bool:
    """Empty prefs → all tags allowed (unrestricted)."""
    if not prefs:
        return True
    allowed = normalize_filing_tags(prefs)
    if not allowed:
        return True
    return tag in allowed
