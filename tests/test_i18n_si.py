"""W9: Sinhala (si) alert language — i18n + format_alert_message locale."""

from __future__ import annotations

from datetime import UTC, datetime

from koel.domain import AlertEvent, AlertType, disclaimer, format_alert_message
from koel.i18n import normalize_locale, parse_language_arg, t


def _event(**kwargs: object) -> AlertEvent:
    base: dict[str, object] = {
        "rule_id": 1,
        "user_id": 1,
        "telegram_id": 1001,
        "symbol": "JKH.N0000",
        "type": AlertType.PRICE_ABOVE,
        "threshold": 100.0,
        "trigger": "price crossed above 100.00",
        "current_price": 101.5,
        "event_key": "price:1:1",
    }
    base.update(kwargs)
    return AlertEvent.model_validate(base)


def test_normalize_locale_aliases() -> None:
    assert normalize_locale("en") == "en"
    assert normalize_locale("EN") == "en"
    assert normalize_locale("english") == "en"
    assert normalize_locale("si") == "si"
    assert normalize_locale("SI") == "si"
    assert normalize_locale("sinhala") == "si"
    assert normalize_locale("සිංහල") == "si"
    assert normalize_locale("fr") == "en"
    assert normalize_locale(None) == "en"
    assert normalize_locale(1) == "en"
    assert normalize_locale("") == "en"
    assert normalize_locale("  si  ") == "si"


def test_parse_language_arg() -> None:
    assert parse_language_arg("si") == "si"
    assert parse_language_arg("සිංහල") == "si"
    assert parse_language_arg("sinhala") == "si"
    assert parse_language_arg("en") == "en"
    assert parse_language_arg("english") == "en"
    assert parse_language_arg("fr") is None
    assert parse_language_arg("") is None
    assert parse_language_arg(None) is None


def test_t_sinhala_vs_en() -> None:
    assert t("alert.trigger", "en", trigger="x") == "Trigger: x"
    assert t("alert.trigger", "si", trigger="x") == "හේතුව: x"
    assert t("alert.price", "en", price="1.00") == "Price: 1.00 LKR"
    assert t("alert.price", "si", price="1.00") == "මිල: 1.00 LKR"
    assert "මූල්‍ය" in t("alert.nfa", "si")
    assert t("alert.nfa", "en") == disclaimer()
    # Missing key → key string; unknown locale → English.
    assert t("alert.nfa", "xx") == disclaimer()
    assert t("no.such.key", "si") == "no.such.key"


def test_format_alert_message_locale_si() -> None:
    as_of = datetime(2026, 7, 21, 8, 12, tzinfo=UTC)
    msg = format_alert_message(_event(as_of=as_of), locale="si")
    assert "🔔 JKH.N0000" in msg
    assert "හේතුව: price crossed above 100.00" in msg
    assert "මිල: 101.50 LKR" in msg
    assert "වේලාව 13:42 SLT" in msg
    assert "මෙය මූල්‍ය උපදෙස් නොවේ — තොරතුරු පමණි." in msg
    assert "Trigger:" not in msg
    assert "Not financial advice" not in msg


def test_format_alert_message_locale_en_unchanged() -> None:
    msg = format_alert_message(_event(), locale="en")
    assert "Trigger: price crossed above 100.00" in msg
    assert "Price: 101.50 LKR" in msg
    assert disclaimer() in msg


def test_bot_language_templates() -> None:
    usage = t("bot.language_usage", "en", current="en")
    assert "/language" in usage
    assert "සිංහල" in usage
    set_si = t("bot.language_set", "si")
    assert "සිංහල" in set_si
    assert "මූල්‍ය" in set_si
