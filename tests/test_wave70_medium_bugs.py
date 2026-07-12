"""Wave70: medium+ bugs — config/poller/guardrails/browse/session guards.

1. ``Settings`` env helpers must isinstance-guard getenv returns — non-string
   mocks used to throw on ``.strip`` / ``.upper`` / ``.rstrip`` mid boot.
2. ``_symbol_from_alert_message`` / ``parse_hhmm`` must isinstance-guard
   non-strings (``.split`` used to raise mid dead-letter / market-hours).
3. Scenario ``assert_safe_scenario_output`` / ``contains_buy_sell_language``
   must isinstance-guard — non-strings used to throw on ``.replace``.
4. ``queryMarketBrowse`` must typeof-guard ``opts.q`` before ``.trim``.
5. ``requirePageSession`` must typeof-guard cookie value before verify /
   expired redirect (parity ``verifySessionToken``).
"""

from __future__ import annotations

from datetime import time
from pathlib import Path
from unittest.mock import patch

import pytest

from chime.config import Settings
from chime.poller import _symbol_from_alert_message, parse_hhmm
from chime.scenarios.guardrails import (
    GuardrailViolation,
    assert_safe_scenario_output,
    contains_buy_sell_language,
)

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_settings_env_helpers_reject_non_string_getenv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/chime")

    def _hostile(name: str, default: str | None = None) -> object:
        if name == "TELEGRAM_BOT_TOKEN":
            return "tok"
        if name == "DATABASE_URL":
            return "postgresql://localhost/chime"
        # Non-string mocks — must not throw on .strip / .upper mid Settings.
        return 123

    with patch("chime.config.os.getenv", side_effect=_hostile):
        settings = Settings.from_env(require_token=True)
    assert settings.poll_interval_seconds == 60.0
    assert settings.log_level == "INFO"
    assert settings.disclosure_bulk_feed is False
    assert settings.sectors_ingest is False
    assert settings.cse_base_url == "https://www.cse.lk/api"

    src = (ROOT / "chime" / "config.py").read_text(encoding="utf-8")
    assert "isinstance(raw, str)" in src
    assert "def _env_str" in src


def test_symbol_from_alert_message_and_parse_hhmm_reject_non_strings() -> None:
    for bad in (123, True, None, ["🔔 JKH"], b"x"):
        assert _symbol_from_alert_message(bad) is None
    assert _symbol_from_alert_message("🔔 JKH.N0000\nTrigger: x") == "JKH.N0000"

    for bad in (123, True, None, ["09:30"]):
        with pytest.raises(ValueError, match="HH:MM"):
            parse_hhmm(bad)
    assert parse_hhmm("09:30") == time(9, 30)

    src = (ROOT / "chime" / "poller.py").read_text(encoding="utf-8")
    assert "isinstance(message, str)" in src
    assert "isinstance(value, str)" in src.split("def parse_hhmm")[1].split(
        "def is_market_open"
    )[0]


def test_scenario_guardrails_reject_non_strings() -> None:
    for bad in (123, True, None, ["buy now"], b"sell"):
        assert contains_buy_sell_language(bad) is False
        with pytest.raises(GuardrailViolation):
            assert_safe_scenario_output(bad)
    assert contains_buy_sell_language("Margins steady.") is False
    assert assert_safe_scenario_output("Margins steady.") == "Margins steady."

    src = (ROOT / "chime" / "scenarios" / "guardrails.py").read_text(
        encoding="utf-8"
    )
    assert src.count("isinstance(text, str)") >= 2


def test_market_browse_q_typeof_guard() -> None:
    source = (WEB / "src" / "lib" / "api" / "market-browse.ts").read_text(
        encoding="utf-8"
    )
    chunk = source.split("export async function queryMarketBrowse")[1]
    assert 'typeof opts.q === "string"' in chunk
    assert "opts.q?.trim()" not in chunk


def test_require_page_session_cookie_typeof_guard() -> None:
    source = (WEB / "src" / "lib" / "auth" / "page-session.ts").read_text(
        encoding="utf-8"
    )
    chunk = source.split("export async function requirePageSession")[1]
    assert 'typeof raw === "string" && raw && cfg.sessionSecret' in chunk
    assert chunk.count('typeof raw === "string"') >= 2
    assert "LOGIN_EXPIRED_PATH" in chunk
    # Bare truthy cookie (no typeof) must not decide expired redirect alone.
    assert "redirect(raw ? LOGIN_EXPIRED_PATH" not in chunk
