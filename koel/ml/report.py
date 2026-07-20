"""Markdown / JSON report writers for ML walk-forward experiments."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from koel.ml.walkforward import WalkForwardResult


def render_markdown(
    result: WalkForwardResult,
    *,
    symbols: int,
    bars_hint: str,
) -> str:
    lines = [
        "# ML walk-forward experiment report",
        "",
        f"**Generated (UTC):** {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"**Universe:** {symbols} symbols · {bars_hint}",
        f"**Decision:** **{result.decision}**",
        f"**Leakage checklist:** {'PASS' if result.leakage_ok else 'FAIL'}",
        "",
        "## Reasons",
        "",
    ]
    for r in result.reasons:
        lines.append(f"- {r}")
    if not result.reasons:
        lines.append("- (none)")
    lines.extend(
        [
            "",
            "## Metrics",
            "",
            "| Model | Horizon | Origins | Dir hits | Hit rate | IC | MAE | Folds |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for m in result.metrics:
        hr = f"{m.hit_rate:.3f}" if m.hit_rate is not None else "—"
        ic = f"{m.ic:.3f}" if m.ic is not None else "—"
        mae = f"{m.mae:.4f}" if m.mae is not None else "—"
        lines.append(
            f"| {m.model_id} | {m.horizon} | {m.origins} | "
            f"{m.direction_hits}/{m.direction_total} | {hr} | {ic} | {mae} | "
            f"{m.folds} |"
        )
    lines.extend(
        [
            "",
            "## Gates",
            "",
            "- Promote (GO) if hit rate ≥ **0.55** or Spearman IC ≥ **0.03**",
            "  with enough origins and leakage checklist green.",
            "- NO-GO: keep naive opt-in forecast; do not wire ML into dash.",
            "- UNCLEAR: marginal band — one more experiment pass before hard kill.",
            "",
            "## Leakage checklist",
            "",
            "1. Features from bars with `trade_date ≤ as_of` only",
            "2. Labels from future closes only",
            "3. Expanding-window folds by calendar `as_of`",
            "4. No fit on evaluation fold",
            "5. No random shuffle across time",
            "",
            "## NFA",
            "",
            "Even on GO, any product surface must stay research / estimate — "
            "not financial advice.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(
    result: WalkForwardResult,
    *,
    out_md: Path,
    symbols: int,
    bars_hint: str,
) -> dict[str, Any]:
    out_md.parent.mkdir(parents=True, exist_ok=True)
    md = render_markdown(result, symbols=symbols, bars_hint=bars_hint)
    out_md.write_text(md, encoding="utf-8")
    payload = result.as_dict()
    payload["symbols"] = symbols
    payload["bars_hint"] = bars_hint
    payload["report_md"] = str(out_md)
    out_json = out_md.with_suffix(".json")
    out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload
