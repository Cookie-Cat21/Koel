"""Wave70: medium+ bugs — config/poller/guardrails/browse/session + disclosure.

1. ``Settings`` env helpers must isinstance-guard getenv returns — non-string
   mocks used to throw on ``.strip`` / ``.upper`` / ``.rstrip`` mid boot.
2. ``_symbol_from_alert_message`` / ``parse_hhmm`` must isinstance-guard
   non-strings (``.split`` used to raise mid dead-letter / market-hours).
3. Scenario ``assert_safe_scenario_output`` / ``contains_buy_sell_language``
   must isinstance-guard — non-strings used to throw on ``.replace``.
4. ``queryMarketBrowse`` must typeof-guard ``opts.q`` before ``.trim``.
5. ``requirePageSession`` must typeof-guard cookie value before verify /
   expired redirect (parity ``verifySessionToken``).
6. Disclosure eval / brief sanitize / DoA parse must isinstance-guard before
   ``.strip`` / ``.replace`` (non-strings used to raise mid rule fire / brief).
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from pathlib import Path
from unittest.mock import patch

import pytest

from koel.adapters.cse import _parse_date_of_announcement
from koel.briefs import BriefSettings
from koel.briefs.provider import GeminiBriefProvider
from koel.config import Settings
from koel.domain import AlertRule, AlertType, Disclosure
from koel.poller import _symbol_from_alert_message, parse_hhmm
from koel.rules import _disclosure_category_matches, evaluate_disclosure_rules
from koel.scenarios.guardrails import (
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
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/koel")

    def _hostile(name: str, default: str | None = None) -> object:
        if name == "TELEGRAM_BOT_TOKEN":
            return "tok"
        if name == "DATABASE_URL":
            return "postgresql://localhost/koel"
        # Non-string mocks — must not throw on .strip / .upper mid Settings.
        return 123

    with patch("koel.config.os.getenv", side_effect=_hostile):
        settings = Settings.from_env(require_token=True)
    assert settings.poll_interval_seconds == 15.0
    assert settings.log_level == "INFO"
    assert settings.disclosure_bulk_feed is False
    assert settings.sectors_ingest is False
    assert settings.cse_base_url == "https://www.cse.lk/api"

    src = (ROOT / "koel" / "config.py").read_text(encoding="utf-8")
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

    src = (ROOT / "koel" / "poller.py").read_text(encoding="utf-8")
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

    src = (ROOT / "koel" / "scenarios" / "guardrails.py").read_text(
        encoding="utf-8"
    )
    assert src.count("isinstance(text, str)") >= 2


def test_market_browse_q_typeof_guard() -> None:
    source = (WEB / "src" / "lib" / "api" / "market-browse.ts").read_text(
        encoding="utf-8"
    )
    # Guard lives in shared browseFromWhere (list + count).
    chunk = source.split("function browseFromWhere")[1]
    assert 'typeof opts.q === "string"' in chunk
    assert "opts.q?.trim()" not in source
    assert "browseFromWhere(opts)" in source.split(
        "export async function queryMarketBrowse"
    )[1]


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


def _rule(**kwargs: object) -> AlertRule:
    base = dict(
        id=1,
        user_id=1,
        telegram_id=1,
        symbol="JKH.N0000",
        type=AlertType.DISCLOSURE,
        threshold=None,
        category=None,
        active=True,
        armed=True,
        created_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    base.update(kwargs)
    return AlertRule.model_construct(**base)  # type: ignore[arg-type]


def _disclosure(**kwargs: object) -> Disclosure:
    base = dict(
        external_id="ext-1",
        symbol="JKH.N0000",
        title="t",
        url="https://www.cse.lk/announcements",
        published_at=datetime(2024, 6, 1, tzinfo=UTC),
        seen_at=datetime(2024, 6, 1, tzinfo=UTC),
        category="Financial",
    )
    base.update(kwargs)
    return Disclosure.model_construct(**base)  # type: ignore[arg-type]


def test_disclosure_category_and_external_id_isinstance_guards() -> None:
    rule = _rule(category=123)
    disc = _disclosure()
    # Non-string category → treat as unrestricted match
    assert _disclosure_category_matches(rule, disc) is True

    bad = _disclosure(external_id=999)
    assert evaluate_disclosure_rules(disclosure=bad, rules=[_rule()]) == []

    src = (ROOT / "koel" / "rules.py").read_text(encoding="utf-8")
    assert "isinstance(rule.category, str)" in src
    assert "isinstance(disclosure.external_id, str)" in src


def test_brief_sanitize_user_text_rejects_non_strings() -> None:
    provider = GeminiBriefProvider(BriefSettings(enabled=True, api_key="k"))
    with pytest.raises(ValueError, match="non-empty"):
        provider._sanitize_user_text(123)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-empty"):
        provider._sanitize_user_text(None)  # type: ignore[arg-type]
    out = provider._sanitize_user_text("hello filing")
    assert "<<<FILING>>>" in out and "hello filing" in out

    src = (ROOT / "koel" / "briefs" / "provider.py").read_text(encoding="utf-8")
    chunk = src.split("def _sanitize_user_text")[1].split("class GeminiBriefProvider")[0]
    assert "isinstance(text, str)" in chunk


def test_parse_date_of_announcement_rejects_non_strings() -> None:
    assert _parse_date_of_announcement(123) is None  # type: ignore[arg-type]
    assert _parse_date_of_announcement(True) is None  # type: ignore[arg-type]
    assert _parse_date_of_announcement(None) is None
    assert _parse_date_of_announcement("30 Jun 2026") is not None

    src = (ROOT / "koel" / "adapters" / "cse.py").read_text(encoding="utf-8")
    body = src.split("def _parse_date_of_announcement")[1].split("\ndef ")[0]
    assert "isinstance(value, str)" in body
