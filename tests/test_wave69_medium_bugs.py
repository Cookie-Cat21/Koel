"""Wave69: medium+ bugs — isinstance / typeof fail-closed + price/log guards.

1. ``format_price_lkr`` must reject non-numeric / bool (``math.isfinite`` used
   to throw mid Telegram alert price line).
2. ``configure_logging`` must isinstance-guard ``level`` before ``.upper``.
3. ``format_alert_message`` / brief formatters must isinstance-guard
   symbol/trigger/title (parity dead-letter notify).
4. ``normalize_symbol`` / ``parse_cancel_alert_id`` / ``normalize_company_name``
   / ``_is_loopback_host`` / name-map pairs must isinstance-guard non-strings.
5. ``resolveInternalOrigin`` / ``healthProxyTimeoutMs`` / HEALTH_URL /
   ``getPool`` must typeof-guard env values before ``.trim``.
"""

from __future__ import annotations

from pathlib import Path

from koel.adapters.cse import (
    build_unique_company_name_map,
    normalize_company_name,
)
from koel.bot import (
    format_brief_lookup_reply,
    normalize_symbol,
    parse_cancel_alert_id,
)
from koel.domain import (
    AlertEvent,
    AlertType,
    format_alert_message,
    format_brief_followup,
    format_price_lkr,
)
from koel.health import _is_loopback_host
from koel.logging_setup import configure_logging

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_format_price_lkr_rejects_non_numeric() -> None:
    for bad in ("12.3", None, True, False, "1e2", [1.0], {"p": 1}):
        assert format_price_lkr(bad) == "n/a"  # type: ignore[arg-type]
    assert format_price_lkr(float("nan")) == "n/a"
    assert format_price_lkr(12.5) == "12.50"

    src = (ROOT / "koel" / "domain.py").read_text(encoding="utf-8")
    chunk = src.split("def format_price_lkr")[1].split(
        "def brief_budget_for_prefix"
    )[0]
    assert "isinstance(price, bool)" in chunk
    assert "isinstance(price, (int, float))" in chunk


def test_configure_logging_rejects_non_string_level() -> None:
    configure_logging(level=123)  # type: ignore[arg-type]
    configure_logging(level=None)  # type: ignore[arg-type]
    configure_logging(level="WARNING")

    src = (ROOT / "koel" / "logging_setup.py").read_text(encoding="utf-8")
    chunk = src.split("def configure_logging")[1].split("def get_logger")[0]
    assert "isinstance(level, str)" in chunk
    assert "level_name" in chunk


def test_format_alert_and_brief_isinstance_guards() -> None:
    event = AlertEvent.model_construct(
        rule_id=1,
        user_id=1,
        telegram_id=1,
        symbol=123,  # type: ignore[arg-type]
        type=AlertType.PRICE_ABOVE,
        trigger=456,  # type: ignore[arg-type]
        current_price=10.0,
        event_key="k",
    )
    msg = format_alert_message(event)
    assert "🔔 ?" in msg
    assert "Trigger: alert" in msg

    follow = format_brief_followup(
        symbol="JKH.N0000",
        brief="Ready",
        title=99,  # type: ignore[arg-type]
    )
    assert "Filing brief ready" in follow
    assert "Disclosure:" not in follow

    lookup = format_brief_lookup_reply(
        symbol=None,  # type: ignore[arg-type]
        brief="Body",
        title=True,  # type: ignore[arg-type]
    )
    assert "Body" in lookup
    assert "Disclosure:" not in lookup

    domain = (ROOT / "koel" / "domain.py").read_text(encoding="utf-8")
    alert = domain.split("def format_alert_message")[1].split(
        "def format_dead_letter_notify"
    )[0]
    assert "isinstance(event.symbol, str)" in alert
    assert "isinstance(event.trigger, str)" in alert
    bf = domain.split("def format_brief_followup")[1].split("def as_dict")[0]
    assert "isinstance(title, str)" in bf

    bot = (ROOT / "koel" / "bot.py").read_text(encoding="utf-8")
    br = bot.split("def format_brief_lookup_reply")[1].split("async def cmd_brief")[
        0
    ]
    assert "isinstance(symbol, str)" in br
    assert "isinstance(title, str)" in br


def test_normalize_helpers_and_loopback_isinstance() -> None:
    assert normalize_symbol(123) is None  # type: ignore[arg-type]
    assert parse_cancel_alert_id(42) is None  # type: ignore[arg-type]
    assert normalize_company_name(None) == ""  # type: ignore[arg-type]
    assert _is_loopback_host(123) is False
    assert _is_loopback_host("127.0.0.1") is True
    assert _is_loopback_host("[::1]") is True

    mapping = build_unique_company_name_map(
        [
            ("JKH.N0000", "John Keells"),
            (123, "Bad"),  # type: ignore[list-item]
            ("BAD.N0000", 99),  # type: ignore[list-item]
        ]
    )
    assert mapping == {"JOHN KEELLS": "JKH.N0000"}

    bot = (ROOT / "koel" / "bot.py").read_text(encoding="utf-8")
    assert "isinstance(raw, str)" in bot.split("def normalize_symbol")[1].split(
        "def _parse_threshold_token"
    )[0]
    assert "isinstance(raw, str)" in bot.split("def parse_cancel_alert_id")[
        1
    ].split("async def cmd_cancel")[0]

    cse = (ROOT / "koel" / "adapters" / "cse.py").read_text(encoding="utf-8")
    assert "isinstance(name, str)" in cse.split("def normalize_company_name")[
        1
    ].split("def build_unique_company_name_map")[0]
    assert "isinstance(symbol, str)" in cse.split(
        "def build_unique_company_name_map"
    )[1].split("def resolve_announcement_symbol")[0]

    health = (ROOT / "koel" / "health.py").read_text(encoding="utf-8")
    assert "isinstance(host, str)" in health.split("def _is_loopback_host")[
        1
    ].split("def _nonneg_int")[0]


def test_web_env_typeof_guards_before_trim() -> None:
    origin = (WEB / "src" / "lib" / "api" / "server-fetch.ts").read_text(
        encoding="utf-8"
    )
    chunk = origin.split("export function resolveInternalOrigin")[1].split(
        "export const MAX_SERVER_API_PATH_LENGTH"
    )[0]
    assert 'typeof fromEnvRaw === "string"' in chunk
    assert 'typeof portEnv === "string"' in chunk

    health = (
        WEB / "src" / "app" / "api" / "v1" / "health" / "route.ts"
    ).read_text(encoding="utf-8")
    timeout = health.split("export function healthProxyTimeoutMs")[1].split(
        "type BriefQueueHint"
    )[0]
    assert 'typeof rawEnv === "string"' in timeout
    assert 'typeof healthUrlEnv === "string"' in health

    db = (WEB / "src" / "lib" / "db.ts").read_text(encoding="utf-8")
    pool = db.split("export function getPool")[1].split(
        "export async function ensureUser"
    )[0]
    assert 'typeof urlEnv === "string"' in pool
