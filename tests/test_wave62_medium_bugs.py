"""Wave62: medium+ bugs — bot threshold abs-cap + HEALTH_URL typeof.

1. Bot ``_parse_threshold_token`` must reject magnitudes above
   ``MAX_ALERT_THRESHOLD`` (parity dash POST ``/alerts``).
2. ``isAllowedHealthProxyUrl`` must typeof-guard non-strings.
"""

from __future__ import annotations

from pathlib import Path

from koel.bot import parse_alert_args
from koel.domain import MAX_ALERT_THRESHOLD

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_bot_threshold_caps_at_max_alert_threshold() -> None:
    assert MAX_ALERT_THRESHOLD == 1_000_000_000
    src = (ROOT / "koel" / "bot.py").read_text(encoding="utf-8")
    assert "MAX_ALERT_THRESHOLD" in src
    assert "threshold > MAX_ALERT_THRESHOLD" in src
    parsed_huge, err_huge = parse_alert_args(["JKH.N0000", "above", "1e20"])
    assert parsed_huge is None and err_huge is not None
    parsed_max, err_max = parse_alert_args(
        ["JKH.N0000", "above", str(MAX_ALERT_THRESHOLD)]
    )
    assert err_max is None and parsed_max is not None
    assert parsed_max.threshold == float(MAX_ALERT_THRESHOLD)
    parsed_over, err_over = parse_alert_args(
        ["JKH.N0000", "move", str(MAX_ALERT_THRESHOLD + 1)]
    )
    assert parsed_over is None and err_over is not None


def test_health_proxy_url_typeof_guard() -> None:
    source = (
        WEB / "src" / "app" / "api" / "v1" / "health" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "export function isAllowedHealthProxyUrl(raw: unknown)" in source
    chunk = source.split("export function isAllowedHealthProxyUrl")[1].split(
        "export function parseBriefQueue"
    )[0]
    assert 'typeof raw !== "string"' in chunk
