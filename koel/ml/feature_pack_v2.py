"""Feature Pack v2 — v1 columns with true sector-relative returns.

Same column manifest as v1; ``--feature-pack v2`` loads a sector map and
passes it to ``enrich_feature_pack_v1``. See
``docs/experiments/FEATURE_PACK_V2_SPEC.md``.
"""

from __future__ import annotations

import os
from pathlib import Path

from koel.ml.feature_pack_v1 import (
    FEATURE_PACK_V1_NAMES,
    enrich_feature_pack_v1,
    load_sector_map_from_json,
)

FEATURE_PACK_V2_NAMES: tuple[str, ...] = FEATURE_PACK_V1_NAMES

DEFAULT_SECTOR_MAP_PATH = Path("/tmp/koel-sector-map.json")


def resolve_sector_map_path() -> Path | None:
    """Return sector-map path from ``KOEL_SECTOR_MAP`` or the default if present."""
    env_path = os.environ.get("KOEL_SECTOR_MAP", "").strip()
    if env_path:
        path = Path(env_path)
        return path if path.is_file() else None
    return DEFAULT_SECTOR_MAP_PATH if DEFAULT_SECTOR_MAP_PATH.is_file() else None


def load_sector_map_for_v2() -> dict[str, str] | None:
    """Load sector map for v2 enrichment, or ``None`` when no file is available."""
    path = resolve_sector_map_path()
    if path is None:
        return None
    return load_sector_map_from_json(path)


__all__ = [
    "FEATURE_PACK_V2_NAMES",
    "DEFAULT_SECTOR_MAP_PATH",
    "enrich_feature_pack_v1",
    "load_sector_map_for_v2",
    "load_sector_map_from_json",
    "resolve_sector_map_path",
]
