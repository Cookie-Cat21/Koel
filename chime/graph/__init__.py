"""Company relationship + equity graph (feature-flagged)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GraphSettings:
    company_graph_enabled: bool = False
    keep_low_confidence: bool = False
    pdf_max_bytes: int = 20_971_520  # 20 MiB — annual reports run large
    max_pages: int = 140

    @classmethod
    def from_env(cls) -> GraphSettings:
        def _on(name: str, default: str = "0") -> bool:
            raw = os.getenv(name, default)
            if not isinstance(raw, str):
                return default == "1"
            return raw.strip() == "1"

        raw_bytes = os.getenv("COMPANY_GRAPH_PDF_MAX_BYTES", "")
        pdf_max = 20_971_520
        if isinstance(raw_bytes, str) and raw_bytes.strip().isdigit():
            pdf_max = max(1_048_576, min(int(raw_bytes.strip()), 20_971_520))

        raw_pages = os.getenv("COMPANY_GRAPH_MAX_PAGES", "")
        max_pages = 140
        if isinstance(raw_pages, str) and raw_pages.strip().isdigit():
            max_pages = max(20, min(int(raw_pages.strip()), 250))

        return cls(
            company_graph_enabled=_on("COMPANY_GRAPH_ENABLED"),
            keep_low_confidence=_on("COMPANY_GRAPH_KEEP_LOW"),
            pdf_max_bytes=pdf_max,
            max_pages=max_pages,
        )


def graph_enabled(settings: GraphSettings | None = None) -> bool:
    cfg = settings or GraphSettings.from_env()
    return bool(cfg.company_graph_enabled)
