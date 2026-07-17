"""Parse official CSE ``companyProfile`` director / top-post rows.

CSE packs role text into ``firstName`` oddly, e.g.
``"K. (Chief Executive Officer/Executive Director)"`` + ``lastName: "Balendra"``,
while ``topPosts.designationOther`` is cleaner (``"Chairman"``,
``"Executive Chairman / CEO"``).

Research only (NFA) — not personal net worth.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from chime.extractors.people_pdf import _roles_from_blob, normalize_person_name

# Role words that sometimes appear *outside* parentheses in firstName
# (e.g. "T. Finance Director (Executive Director)").
_EMBEDDED_ROLE = re.compile(
    r"(?i)\b("
    r"group\s+finance\s+director|"
    r"finance\s+director|"
    r"group\s+chief\s+executive(?:\s+officer)?|"
    r"chief\s+executive(?:\s+officer)?|"
    r"managing\s+director|"
    r"company\s+secretary|"
    r"chief\s+financial\s+officer"
    r")\b"
)

_PAREN = re.compile(r"^(?P<head>.*?)\s*\((?P<role>[^)]+)\)\s*$")
_HONORIFIC = re.compile(r"^(?:dr|mr|mrs|ms|prof)\.?\s+", re.I)
_INITIALS = re.compile(
    r"^(?P<init>(?:[A-Za-z]\.?\s*){1,6})\s*$"
)


@dataclass(frozen=True, slots=True)
class CseDirectorSeat:
    """One person at one issuer, with one or more normalized roles."""

    director_id: int | None
    display_name: str
    name_norm: str
    roles: tuple[str, ...]
    designation_raw: str
    source_bucket: str  # top_posts | directors | key_executive


def _clean_token(raw: str) -> str:
    s = re.sub(r"\s+", " ", (raw or "")).strip(" ,;·•\t")
    s = _HONORIFIC.sub("", s).strip()
    return s


def _strip_embedded_roles(head: str) -> tuple[str, list[str]]:
    roles: list[str] = []
    rest = head
    while True:
        m = _EMBEDDED_ROLE.search(rest)
        if not m:
            break
        roles.append(m.group(1))
        rest = (rest[: m.start()] + " " + rest[m.end() :]).strip()
    rest = re.sub(r"\s+", " ", rest).strip(" ,;-/")
    return rest, roles


def parse_cse_person_name(
    first_name: str | None, last_name: str | None
) -> tuple[str | None, list[str]]:
    """Return ``(display_name, role_blobs_from_name)`` or ``(None, [])``."""
    first = _clean_token(first_name or "")
    last = _clean_token(last_name or "")
    role_blobs: list[str] = []

    head = first
    m = _PAREN.match(first)
    if m:
        head = m.group("head").strip()
        role_blobs.append(m.group("role").strip())

    head, embedded = _strip_embedded_roles(head)
    role_blobs.extend(embedded)

    # Prefer initials-style head; drop leftover role-ish words.
    head = re.sub(r"\s+", " ", head).strip(" ,;-/")
    if head and not _INITIALS.match(head) and len(head) > 24:
        # Hostile long firstName without a usable initials head.
        head = ""

    if not last and not head:
        return None, role_blobs

    # Display: "K. Balendra", "M. Pandithage", "S. A. Coorey"
    if head:
        # Normalize spaced initials: "K D G" → "K. D. G."
        parts = [p for p in re.split(r"[\s.]+", head) if p]
        if parts and all(len(p) <= 2 for p in parts):
            init = " ".join(f"{p[0].upper()}." for p in parts)
            display = f"{init} {last}".strip() if last else init
        else:
            display = f"{head} {last}".strip() if last else head
    else:
        display = last

    display = re.sub(r"\s+", " ", display).strip()
    if len(display) < 2 or len(display) > 80:
        return None, role_blobs
    # Need a surname-ish token (not only a single initial).
    letters = [c for c in display if c.isalpha()]
    if len(letters) < 2:
        return None, role_blobs
    return display, role_blobs


def roles_from_cse_text(*blobs: str | None) -> list[str]:
    """Map CSE designation / parenthetical text → schema roles.

    Handles multi-role posts (``Executive Chairman / CEO`` → chairman+ceo)
    and ``non-independent`` phrasing that would otherwise match ``independent``.
    """
    out: list[str] = []
    for blob in blobs:
        if not isinstance(blob, str) or not blob.strip():
            continue
        t = re.sub(r"\s+", " ", blob).strip().lower()
        # Finance Director is common on CSE boards but not in PDF map_role.
        if "finance director" in t or "group finance" in t:
            if "cfo" not in out:
                out.append("cfo")
        # Fix false positive: "non-independent" contains substring "independent".
        t_for_map = t
        if "non-independent" in t or "non independent" in t:
            t_for_map = re.sub(r"non[- ]independent", " ", t)
        for role in _roles_from_blob(t_for_map):
            if role not in out:
                out.append(role)
        # Co-Chairman → deputy_chairman (distinct from sole Chairman).
        if "co-chairman" in t or "co chairman" in t:
            out = [r for r in out if r != "chairman"]
            if "deputy_chairman" not in out:
                out.append("deputy_chairman")
    if not out:
        out.append("director")
    return out


def parse_cse_director_row(
    row: dict[str, Any], *, source_bucket: str
) -> CseDirectorSeat | None:
    if not isinstance(row, dict):
        return None
    display, name_roles = parse_cse_person_name(
        row.get("firstName") if isinstance(row.get("firstName"), str) else None,
        row.get("lastName") if isinstance(row.get("lastName"), str) else None,
    )
    if not display:
        return None
    name_norm = normalize_person_name(display)
    if len(name_norm) < 2:
        return None

    designation = ""
    if isinstance(row.get("designationOther"), str):
        designation = row["designationOther"].strip()
    elif isinstance(row.get("description"), str) and row["description"].strip():
        designation = row["description"].strip()

    roles = roles_from_cse_text(designation, *name_roles)
    raw_id = row.get("directorId")
    director_id = raw_id if isinstance(raw_id, int) and not isinstance(raw_id, bool) else None

    return CseDirectorSeat(
        director_id=director_id,
        display_name=display[:120],
        name_norm=name_norm,
        roles=tuple(roles),
        designation_raw=(designation or "; ".join(name_roles))[:240],
        source_bucket=source_bucket,
    )


def merge_cse_board(
    *,
    top_posts: list[dict[str, Any]] | None,
    directors: list[dict[str, Any]] | None,
    key_executives: list[dict[str, Any]] | None = None,
) -> list[CseDirectorSeat]:
    """Merge topPosts + infoCompanyDirector (+ optional key execs) by directorId/name.

    Prefer topPosts designation for role when the same person appears in both.
    """
    by_key: dict[str, CseDirectorSeat] = {}

    def _key(seat: CseDirectorSeat) -> str:
        if seat.director_id is not None:
            return f"id:{seat.director_id}"
        return f"n:{seat.name_norm}"

    for bucket, rows in (
        ("top_posts", top_posts or []),
        ("directors", directors or []),
        ("key_executive", key_executives or []),
    ):
        if not isinstance(rows, list):
            continue
        for row in rows:
            seat = parse_cse_director_row(row, source_bucket=bucket)
            if seat is None:
                continue
            k = _key(seat)
            prev = by_key.get(k)
            if prev is None:
                by_key[k] = seat
                continue
            # Union roles; prefer top_posts designation / display.
            roles = list(prev.roles)
            for r in seat.roles:
                if r not in roles:
                    roles.append(r)
            prefer_top = prev.source_bucket == "top_posts" or bucket != "top_posts"
            by_key[k] = CseDirectorSeat(
                director_id=prev.director_id or seat.director_id,
                display_name=prev.display_name if prefer_top else seat.display_name,
                name_norm=prev.name_norm,
                roles=tuple(roles),
                designation_raw=prev.designation_raw
                if prefer_top and prev.designation_raw
                else seat.designation_raw or prev.designation_raw,
                source_bucket="top_posts"
                if "top_posts" in (prev.source_bucket, bucket)
                else prev.source_bucket,
            )

    return list(by_key.values())
