"""Transfer-learning experiment: pretrain on foreign daily OHLCV → test on CSE.

Loads a long CSV panel (Yahoo/Kaggle-style) with columns:
``symbol,trade_date,open,high,low,close,volume``.

Compares under the same CSE walk-forward folds:
- ``cse_only``: train on CSE past only
- ``zero_shot``: train on foreign panel only
- ``transfer``: train on foreign + CSE past (joint fine-tune)

Does not write production ``forecast_points``.
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from koel.domain import DailyBar
from koel.logging_setup import get_logger
from koel.ml.dataset import Sample, build_samples, load_symbol_bars
from koel.ml.walkforward import (
    ModelMetrics,
    _fit_predict_sklearn,
    _spearman_ic,
    _unique_sorted_dates,
)
from koel.storage import Storage

log = get_logger(__name__)


def load_panel_csv(path: Path) -> dict[str, list[DailyBar]]:
    """Load external OHLCV panel into DailyBar series keyed by symbol."""
    by: dict[str, list[DailyBar]] = defaultdict(list)
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sym = (row.get("symbol") or "").strip().upper()
            if not sym:
                continue
            try:
                td = date.fromisoformat((row.get("trade_date") or "").strip())
            except ValueError:
                continue
            try:
                price = float(row["close"])
            except (KeyError, TypeError, ValueError):
                continue
            if not math.isfinite(price) or price <= 0:
                continue

            def _opt_num(raw: str | None) -> float | None:
                if raw is None or raw == "":
                    return None
                try:
                    v = float(raw)
                except (TypeError, ValueError):
                    return None
                return v if math.isfinite(v) else None

            by[sym].append(
                DailyBar(
                    symbol=sym,
                    trade_date=td,
                    price=price,
                    high=_opt_num(row.get("high")),
                    low=_opt_num(row.get("low")),
                    open=_opt_num(row.get("open")),
                    volume=_opt_num(row.get("volume")),
                    source_period=5,
                    bar_ts=datetime(td.year, td.month, td.day, 18, 30, tzinfo=UTC),
                )
            )
    out: dict[str, list[DailyBar]] = {}
    for sym, bars in by.items():
        out[sym] = sorted(bars, key=lambda b: b.trade_date)
    return out


@dataclass
class TransferCompareResult:
    metrics: list[ModelMetrics] = field(default_factory=list)
    decision: str = "UNCLEAR"
    reasons: list[str] = field(default_factory=list)
    panel_symbols: int = 0
    panel_bars: int = 0
    cse_symbols: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reasons": list(self.reasons),
            "panel_symbols": self.panel_symbols,
            "panel_bars": self.panel_bars,
            "cse_symbols": self.cse_symbols,
            "metrics": [asdict(m) for m in self.metrics],
        }


def _run_protocol(
    *,
    protocol: str,
    horizon: int,
    model_id: str,
    cse_samples: list[Sample],
    foreign_samples: list[Sample],
    min_train_days: int = 120,
    fold_step: int = 20,
) -> ModelMetrics:
    dates = _unique_sorted_dates(cse_samples)
    hits = 0
    total = 0
    origins = 0
    abs_err: list[float] = []
    preds_ret: list[float] = []
    acts_ret: list[float] = []
    folds = 0
    cut = min_train_days
    task = "dir" if "logistic" in model_id or "clf" in model_id else "ret"

    while cut + fold_step <= len(dates):
        train_dates = set(dates[:cut])
        test_dates = set(dates[cut : cut + fold_step])
        cse_train = [s for s in cse_samples if s.as_of in train_dates]
        cse_test = [s for s in cse_samples if s.as_of in test_dates]
        cut += fold_step
        if len(cse_test) < 10:
            continue

        if protocol == "cse_only":
            train = cse_train
        elif protocol == "zero_shot":
            train = foreign_samples
        elif protocol == "transfer":
            train = list(foreign_samples) + cse_train
        else:
            raise ValueError(protocol)

        if len(train) < 50:
            continue
        try:
            y_dir, y_ret, pred = _fit_predict_sklearn(
                train, cse_test, task=task, model_id=model_id
            )
        except Exception as exc:
            log.warning(
                "transfer_fold_failed",
                protocol=protocol,
                model_id=model_id,
                horizon=horizon,
                error=str(exc),
            )
            continue
        folds += 1
        origins += len(cse_test)
        if task == "dir":
            for yd, yp in zip(y_dir, pred, strict=True):
                if yd == 0 or yp == 0:
                    continue
                total += 1
                if (yd > 0 and yp > 0) or (yd < 0 and yp < 0):
                    hits += 1
            preds_ret.extend(pred)
            acts_ret.extend(y_ret)
        else:
            for yr, yp in zip(y_ret, pred, strict=True):
                abs_err.append(abs(yp - yr))
                if yr != 0 and yp != 0:
                    total += 1
                    if (yr > 0 and yp > 0) or (yr < 0 and yp < 0):
                        hits += 1
            preds_ret.extend(pred)
            acts_ret.extend(y_ret)

    hit_rate = hits / total if total else None
    mae = sum(abs_err) / len(abs_err) if abs_err else None
    ic = _spearman_ic(preds_ret, acts_ret)
    return ModelMetrics(
        model_id=f"{protocol}::{model_id}",
        horizon=horizon,
        origins=origins,
        direction_hits=hits,
        direction_total=total,
        hit_rate=hit_rate,
        ic=ic,
        mae=mae,
        folds=folds,
    )


async def run_transfer_experiment(
    *,
    storage: Storage,
    panel_csv: Path,
    horizons: tuple[int, ...] = (1, 5),
    model_ids: tuple[str, ...] = ("B1_logistic", "M1_hgb_clf", "M2_hgb_reg"),
    limit_cse_symbols: int | None = None,
    min_history: int = 60,
) -> TransferCompareResult:
    from koel.ml import sklearn_available

    if not sklearn_available():
        return TransferCompareResult(
            decision="UNCLEAR",
            reasons=["sklearn not installed — pip install -e '.[ml]'"],
        )

    foreign = load_panel_csv(panel_csv)
    cse = await load_symbol_bars(storage, limit_symbols=limit_cse_symbols)
    panel_bars = sum(len(v) for v in foreign.values())
    log.info(
        "transfer_loaded",
        panel_symbols=len(foreign),
        panel_bars=panel_bars,
        cse_symbols=len(cse),
    )

    metrics: list[ModelMetrics] = []
    for horizon in horizons:
        foreign_samples = build_samples(
            foreign, horizon=horizon, min_history=min_history
        )
        cse_samples = build_samples(cse, horizon=horizon, min_history=min_history)
        log.info(
            "transfer_samples",
            horizon=horizon,
            foreign=len(foreign_samples),
            cse=len(cse_samples),
        )
        for model_id in model_ids:
            for protocol in ("cse_only", "zero_shot", "transfer"):
                m = _run_protocol(
                    protocol=protocol,
                    horizon=horizon,
                    model_id=model_id,
                    cse_samples=cse_samples,
                    foreign_samples=foreign_samples,
                    min_train_days=120,
                    fold_step=20,
                )
                metrics.append(m)
                log.info(
                    "transfer_metric",
                    protocol=protocol,
                    model_id=model_id,
                    horizon=horizon,
                    hit_rate=m.hit_rate,
                    ic=m.ic,
                    origins=m.origins,
                )

    # Decision: does best transfer beat best cse_only on hit_rate or IC?
    def _best(prefix: str, horizon: int) -> ModelMetrics | None:
        cands = [
            m
            for m in metrics
            if m.model_id.startswith(prefix) and m.horizon == horizon and m.origins >= 200
        ]
        if not cands:
            return None
        return max(
            cands,
            key=lambda m: (
                m.hit_rate or 0.0,
                m.ic or -1.0,
            ),
        )

    reasons: list[str] = []
    wins = 0
    for h in horizons:
        base = _best("cse_only::", h)
        tr = _best("transfer::", h)
        zs = _best("zero_shot::", h)
        if base and tr and (tr.hit_rate or 0) > (base.hit_rate or 0) + 0.005:
            wins += 1
            reasons.append(
                f"h={h} transfer hit {(tr.hit_rate or 0):.3f} > "
                f"cse_only {(base.hit_rate or 0):.3f} ({tr.model_id})"
            )
        elif base and tr:
            reasons.append(
                f"h={h} transfer hit {(tr.hit_rate or 0):.3f} ≤ "
                f"cse_only {(base.hit_rate or 0):.3f} ({base.model_id})"
            )
        if zs and base:
            reasons.append(
                f"h={h} zero_shot hit {(zs.hit_rate or 0):.3f} "
                f"vs cse_only {(base.hit_rate or 0):.3f}"
            )

    if wins >= 1:
        decision = "GO_TRANSFER"
    elif any("≤" in r or "zero_shot" in r for r in reasons):
        decision = "NO_GAIN"
    else:
        decision = "UNCLEAR"

    return TransferCompareResult(
        metrics=metrics,
        decision=decision,
        reasons=reasons,
        panel_symbols=len(foreign),
        panel_bars=panel_bars,
        cse_symbols=len(cse),
    )


def render_transfer_markdown(result: TransferCompareResult) -> str:
    lines = [
        "# Transfer-learning experiment (foreign panel → CSE)",
        "",
        f"**Panel:** {result.panel_symbols} symbols · {result.panel_bars} bars "
        "(Yahoo India+US daily, 2018→2026)",
        f"**CSE test universe:** {result.cse_symbols} symbols",
        f"**Decision:** **{result.decision}**",
        "",
        "## Verdict reasons",
        "",
    ]
    for r in result.reasons:
        lines.append(f"- {r}")
    lines.extend(
        [
            "",
            "## Metrics",
            "",
            "| Protocol::Model | Horizon | Origins | Hit rate | IC | MAE | Folds |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for m in sorted(result.metrics, key=lambda x: (x.horizon, x.model_id)):
        hr = f"{m.hit_rate:.3f}" if m.hit_rate is not None else "—"
        ic = f"{m.ic:.3f}" if m.ic is not None else "—"
        mae = f"{m.mae:.4f}" if m.mae is not None else "—"
        lines.append(
            f"| {m.model_id} | {m.horizon} | {m.origins} | {hr} | {ic} | {mae} | "
            f"{m.folds} |"
        )
    lines.extend(
        [
            "",
            "## Protocols",
            "",
            "- **cse_only** — train on CSE past folds only (baseline)",
            "- **zero_shot** — train on foreign panel only; test CSE folds",
            "- **transfer** — train on foreign + CSE past; test CSE folds",
            "",
            "## Interpretation",
            "",
            "- **GO_TRANSFER** — joint training beat CSE-only enough to keep exploring",
            "- **NO_GAIN** — foreign pretrain did not help CSE; stick to CSE-only",
            "- Domain shift (US/India ≠ Colombo) often kills zero-shot; fine-tune may still help",
            "",
            "## NFA",
            "",
            "Research only — not financial advice.",
            "",
        ]
    )
    return "\n".join(lines)
