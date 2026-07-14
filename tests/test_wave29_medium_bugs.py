"""Wave29: medium+ bugs — demo auth telegram_id SafeInteger harden.

1. ``POST /api/v1/auth/demo`` must parse ``telegram_id`` via digits-only
   ``toSafePositiveInt`` (not bare ``typeof === "number"`` + ``isSafeInteger``)
   so string / oversized / float / sci-notation bodies cannot precision-lose
   into an allowlisted session mint.
2. ``getDashAuthConfig`` allowlist + default must use the same helper —
   ``Number("9…093")`` must not silently alias ``MAX_SAFE_INTEGER`` into the
   demo allowlist from env.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_demo_auth_route_uses_to_safe_positive_int() -> None:
    route = WEB / "src" / "app" / "api" / "v1" / "auth" / "demo" / "route.ts"
    source = route.read_text(encoding="utf-8")
    assert "toSafePositiveInt" in source
    assert "toSafePositiveInt(parsed.telegramId)" in source
    assert 'typeof rawId !== "number"' not in source
    assert "Number.isSafeInteger(rawId)" not in source


def test_auth_config_allowlist_uses_to_safe_positive_int() -> None:
    config = WEB / "src" / "lib" / "auth" / "config.ts"
    source = config.read_text(encoding="utf-8")
    assert "toSafePositiveInt" in source
    assert "toSafePositiveInt(part.trim())" in source
    assert "toSafePositiveInt(" in source
    assert r"/^-?\d+$/" not in source
    assert "Number(trimmed)" not in source
    assert "Number(defaultRaw)" not in source
