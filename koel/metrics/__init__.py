"""Filing metrics extract + YoY compare (feature-flagged)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MetricsSettings:
    financial_metrics_enabled: bool = False
    filing_compare_enabled: bool = False
    eps_calc_alerts_enabled: bool = False
    yoy_compare_alerts_enabled: bool = False
    metrics_shadow_mode: bool = True
    yoy_append_to_disclosure: bool = False

    @classmethod
    def from_env(cls) -> MetricsSettings:
        def _on(name: str, default: str = "0") -> bool:
            raw = os.getenv(name, default)
            if not isinstance(raw, str):
                return default == "1"
            return raw.strip() == "1"

        return cls(
            financial_metrics_enabled=_on("FINANCIAL_METRICS_ENABLED"),
            filing_compare_enabled=_on("FILING_COMPARE_ENABLED"),
            eps_calc_alerts_enabled=_on("EPS_CALC_ALERTS_ENABLED"),
            yoy_compare_alerts_enabled=_on("YOY_COMPARE_ALERTS_ENABLED"),
            metrics_shadow_mode=_on("METRICS_SHADOW_MODE", "1"),
            yoy_append_to_disclosure=_on("YOY_APPEND_TO_DISCLOSURE"),
        )


def metrics_enabled(settings: MetricsSettings | None = None) -> bool:
    cfg = settings or MetricsSettings.from_env()
    return bool(cfg.financial_metrics_enabled)


def compare_enabled(settings: MetricsSettings | None = None) -> bool:
    cfg = settings or MetricsSettings.from_env()
    return bool(cfg.financial_metrics_enabled and cfg.filing_compare_enabled)
