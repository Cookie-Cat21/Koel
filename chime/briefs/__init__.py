"""Filing brief helpers (Tijori-style AI summaries).

Phase 1: schema + disabled-by-default stub. Phase 2 wires PDF fetch + LLM.
Never call cse.lk from web/ — briefs are produced by the Python worker only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "BriefSettings",
    "BriefStatus",
    "briefs_enabled",
    "build_brief_prompt",
    "nfa_suffix",
]


class BriefStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class BriefSettings:
    """Env knobs (see root ``.env.example``):

    - ``AI_BRIEFS_ENABLED`` — ``1`` to opt in (default ``0``)
    - ``AI_PROVIDER`` — only ``gemini`` for now (default ``gemini``)
    - ``AI_API_KEY`` — required with enabled for ``briefs_enabled()``
    - ``AI_MODEL`` — default ``gemini-2.0-flash``
    - ``AI_MAX_BRIEFS_PER_DAY`` — default ``50``
    - ``AI_MAX_INPUT_CHARS`` — default ``12000``
    - ``PDF_MAX_BYTES`` — max PDF download size (default ``5242880``)
    """

    enabled: bool = False
    provider: str = "gemini"
    api_key: str = ""
    model: str = "gemini-2.0-flash"
    max_briefs_per_day: int = 50
    max_input_chars: int = 12_000
    pdf_max_bytes: int = 5_242_880

    @classmethod
    def from_env(cls) -> BriefSettings:
        return cls(
            enabled=os.getenv("AI_BRIEFS_ENABLED", "0").strip() == "1",
            provider=os.getenv("AI_PROVIDER", "gemini").strip() or "gemini",
            api_key=os.getenv("AI_API_KEY", "").strip(),
            model=os.getenv("AI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash",
            max_briefs_per_day=int(os.getenv("AI_MAX_BRIEFS_PER_DAY", "50") or "50"),
            max_input_chars=int(os.getenv("AI_MAX_INPUT_CHARS", "12000") or "12000"),
            pdf_max_bytes=int(os.getenv("PDF_MAX_BYTES", "5242880") or "5242880"),
        )


def briefs_enabled(settings: BriefSettings | None = None) -> bool:
    """True only when explicitly opted in and a key is present."""
    cfg = settings or BriefSettings.from_env()
    return cfg.enabled and bool(cfg.api_key)


def nfa_suffix() -> str:
    return "Not financial advice — informational only."


def build_brief_prompt(*, symbol: str, title: str, extracted_text: str) -> str:
    """System-ish user prompt for a neutral filing brief (Phase 2 LLM call)."""
    body = extracted_text.strip()
    if len(body) > 12_000:
        body = body[:12_000]
    return (
        f"Summarize this official CSE company filing for {symbol} in 3-5 short "
        "sentences. Stick to facts in the text. Do not give buy/sell/hold advice "
        "or price targets.\n\n"
        f"Title: {title}\n\n"
        f"Filing text:\n{body}\n\n"
        f"{nfa_suffix()}"
    )
