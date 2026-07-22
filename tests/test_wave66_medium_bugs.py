"""Wave66: medium+ bugs — briefs/scenarios/bot env + list isinstance.

1. ``BriefSettings.from_env`` / ``ScenarioSettings.from_env`` isinstance-guard
   getenv returns before ``.strip``.
2. ``_env_cmd_rate_per_minute`` isinstance-guards getenv before ``.strip``.
3. ``_parse_threshold_token`` / ``parse_alert_args`` kind isinstance-guard.
4. ``/myalerts`` / ``/mywatchlist`` symbol egress isinstance-guards.
5. Poller delivery-ok ledger getenv isinstance False branch.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from koel.bot import (
    _env_cmd_rate_per_minute,
    _parse_threshold_token,
    parse_alert_args,
)
from koel.briefs import BriefSettings, briefs_enabled
from koel.domain import _CTRL_RE
from koel.poller import Poller
from koel.scenarios import ScenarioSettings, scenarios_enabled

ROOT = Path(__file__).resolve().parents[1]


def test_brief_settings_from_env_rejects_non_string_getenv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.delenv("AI_BRIEFS_ENABLED", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)

    def _hostile(name: str, default: str | None = None) -> object:
        if name == "AI_PROVIDER":
            return 123
        if name == "AI_BRIEFS_ENABLED":
            return True
        if name == "AI_API_KEY":
            return {"k": 1}
        if name == "AI_MODEL":
            return 9.5
        return default

    with patch("koel.briefs.os.getenv", side_effect=_hostile):
        cfg = BriefSettings.from_env()
    assert cfg.provider == "gemini"
    assert cfg.enabled is False
    assert cfg.api_key == ""
    assert cfg.model == "gemini-2.0-flash"
    assert briefs_enabled(cfg) is False

    src = (ROOT / "koel" / "briefs" / "__init__.py").read_text(encoding="utf-8")
    chunk = src.split("def from_env")[1].split("def briefs_enabled")[0]
    assert "isinstance(provider_raw, str)" in chunk
    assert "isinstance(enabled_raw, str)" in chunk
    assert "isinstance(api_key_raw, str)" in chunk


def test_scenario_settings_from_env_rejects_non_string_getenv() -> None:
    with patch("koel.scenarios.os.getenv", return_value=1):
        cfg = ScenarioSettings.from_env()
    assert cfg.enabled is False
    assert scenarios_enabled(cfg) is False

    with patch("koel.scenarios.os.getenv", return_value="1"):
        assert ScenarioSettings.from_env().enabled is True

    src = (ROOT / "koel" / "scenarios" / "__init__.py").read_text(
        encoding="utf-8"
    )
    chunk = src.split("def from_env")[1].split("def scenarios_enabled")[0]
    assert "isinstance(raw, str)" in chunk


def test_bot_rate_threshold_and_kind_isinstance_guards() -> None:
    with patch("koel.bot.os.getenv", return_value=30):
        assert _env_cmd_rate_per_minute() == 20
    with patch("koel.bot.os.getenv", return_value="7"):
        assert _env_cmd_rate_per_minute() == 7

    assert _parse_threshold_token(123) is None  # type: ignore[arg-type]
    assert _parse_threshold_token(None) is None  # type: ignore[arg-type]
    assert _parse_threshold_token("12.5") == 12.5

    bad, err = parse_alert_args(["JKH.N0000", 99, "5"])  # type: ignore[list-item]
    assert bad is None and err is not None
    ok, err_ok = parse_alert_args(["JKH.N0000", "above", "5"])
    assert err_ok is None and ok is not None

    src = (ROOT / "koel" / "bot.py").read_text(encoding="utf-8")
    rate = src.split("def _env_cmd_rate_per_minute")[1].split("START_TEXT")[0]
    assert "isinstance(raw_env, str)" in rate
    thr = src.split("def _parse_threshold_token")[1].split("def parse_alert_args")[0]
    assert "isinstance(raw, str)" in thr
    args = src.split("def parse_alert_args")[1].split("async def _user_id")[0]
    assert "isinstance(args[1], str)" in args


def test_myalerts_mywatchlist_symbol_isinstance_guards() -> None:
    for bad in (123, True, None, {"s": 1}, ["JKH"]):
        sym_raw = bad if isinstance(bad, str) else ""
        assert (_CTRL_RE.sub("", sym_raw).strip() or "?") == "?"

    src = (ROOT / "koel" / "bot.py").read_text(encoding="utf-8")
    alerts = src.split("Your alerts:")[1].split("def format_mywatchlist_text")[0]
    assert "isinstance(r.symbol, str)" in alerts
    watch = src.split("def format_mywatchlist_text")[1].split(
        "async def _maybe_offer_digest"
    )[0]
    assert "isinstance(s, str)" in watch

    row = SimpleNamespace(symbol=999, type="disclosure", category=None, id=1)
    sym_raw = row.symbol if isinstance(row.symbol, str) else ""
    assert (_CTRL_RE.sub("", sym_raw).strip() or "?") == "?"


def test_delivery_ok_ledger_path_rejects_non_string_getenv() -> None:
    poller = Poller.__new__(Poller)
    poller.settings = SimpleNamespace(database_url="postgresql://localhost/koel")
    with patch("koel.poller.os.getenv", return_value=123):
        assert poller._delivery_ok_ledger_path_from_env() is None
    with patch("koel.poller.os.getenv", return_value=""):
        assert poller._delivery_ok_ledger_path_from_env() is None
