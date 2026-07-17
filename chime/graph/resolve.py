"""Fail-closed company-name → listed symbol resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import get_close_matches

from chime.adapters.cse import normalize_company_name

_LEGAL_SUFFIX = re.compile(
    r"\b(PLC|LIMITED|LTD\.?|COMPANY|CORPORATION|CORP\.?|INC\.?|HOLDINGS)\s*$",
    re.I,
)


@dataclass(frozen=True, slots=True)
class ResolveResult:
    status: str  # resolved | unresolved | ambiguous
    symbol: str | None = None
    name_norm: str = ""
    method: str = ""  # exact | suffix | fuzzy


def strip_legal_suffix(name_norm: str) -> str:
    if not isinstance(name_norm, str) or not name_norm:
        return ""
    out = name_norm.strip()
    # Strip repeatedly for "X HOLDINGS PLC"
    for _ in range(3):
        nxt = _LEGAL_SUFFIX.sub("", out).strip()
        if nxt == out:
            break
        out = nxt
    return out


def build_suffix_map(exact_map: dict[str, str]) -> dict[str, str]:
    """Unique suffix-stripped keys only (drop collisions)."""
    buckets: dict[str, set[str]] = {}
    for name, symbol in exact_map.items():
        key = strip_legal_suffix(name)
        if not key or len(key) < 3:
            continue
        buckets.setdefault(key, set()).add(symbol)
    return {k: next(iter(v)) for k, v in buckets.items() if len(v) == 1}


def resolve_company_name(
    raw: str,
    *,
    exact_map: dict[str, str],
    suffix_map: dict[str, str],
    fuzzy_cutoff: float = 0.92,
) -> ResolveResult:
    if not isinstance(raw, str) or not raw.strip():
        return ResolveResult(status="unresolved")
    name_norm = normalize_company_name(raw)
    if not name_norm:
        return ResolveResult(status="unresolved")

    if name_norm in exact_map:
        return ResolveResult(
            status="resolved",
            symbol=exact_map[name_norm],
            name_norm=name_norm,
            method="exact",
        )

    suffix = strip_legal_suffix(name_norm)
    if suffix and suffix in suffix_map:
        return ResolveResult(
            status="resolved",
            symbol=suffix_map[suffix],
            name_norm=name_norm,
            method="suffix",
        )

    if suffix and len(suffix) >= 5 and suffix_map:
        keys = list(suffix_map.keys())
        matches = get_close_matches(suffix, keys, n=2, cutoff=fuzzy_cutoff)
        if not matches:
            return ResolveResult(status="unresolved", name_norm=name_norm)
        best = matches[0]
        if len(matches) > 1:
            # Require clear winner
            from difflib import SequenceMatcher

            s0 = SequenceMatcher(None, suffix, matches[0]).ratio()
            s1 = SequenceMatcher(None, suffix, matches[1]).ratio()
            if s0 - s1 < 0.03:
                return ResolveResult(status="ambiguous", name_norm=name_norm)
        return ResolveResult(
            status="resolved",
            symbol=suffix_map[best],
            name_norm=name_norm,
            method="fuzzy",
        )

    return ResolveResult(status="unresolved", name_norm=name_norm)


def _prefer_voting_share(symbols: set[str]) -> str | None:
    """When N/X dual-listed, prefer ``*.N0000`` voting share."""
    if not symbols:
        return None
    if len(symbols) == 1:
        return next(iter(symbols))
    voting = sorted(s for s in symbols if s.endswith(".N0000"))
    if len(voting) == 1:
        return voting[0]
    return None


def maps_from_stock_pairs(
    pairs: list[tuple[str, str | None]],
) -> tuple[dict[str, str], dict[str, str]]:
    """Build exact + suffix maps; prefer voting share on N/X dual listings."""
    from chime.adapters.cse import normalize_company_name as _norm

    buckets: dict[str, set[str]] = {}
    for symbol, name in pairs:
        if not isinstance(symbol, str) or not isinstance(name, str):
            continue
        sym = symbol.strip().upper()
        if not sym or not name.strip():
            continue
        key = _norm(name)
        if not key:
            continue
        buckets.setdefault(key, set()).add(sym)

    exact: dict[str, str] = {}
    for key, symbols in buckets.items():
        if len(symbols) == 1:
            exact[key] = next(iter(symbols))
            continue
        preferred = _prefer_voting_share(symbols)
        if preferred:
            exact[key] = preferred
    return exact, build_suffix_map(exact)
