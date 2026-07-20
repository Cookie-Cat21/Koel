"""Loop C helper — run next open backlog experiments and ledger results."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from koel.logging_setup import get_logger
from koel.ml.always_on import (
    _walk_lmt_bagged,
    enrich_samples_with_financial_filings,
    enrich_samples_with_interactions,
    enrich_samples_with_market_summary,
    enrich_samples_with_sector_rs,
    enrich_samples_with_yoy,
    load_yoy_events,
)
from koel.ml.dataset import build_samples, load_symbol_bars
from koel.ml.diagnose import analyze_rows, load_sector_map
from koel.ml.harden import _demean_by_day
from koel.ml.iterate import _enrich_cross_section
from koel.storage import Storage

log = get_logger(__name__)
OUT_DIR = Path("docs/experiments")


@dataclass(frozen=True, slots=True)
class ResearchResult:
    experiment_id: str
    status: str  # KEEP | DEAD | OPEN
    mean_symbol_hit: float | None
    gated_hit_055: float | None
    gated_cov_055: float | None
    delta_vs_baseline: float | None
    notes: str


def _gated_stats(rows, thr: float = 0.55) -> tuple[float | None, float | None]:
    if not rows:
        return None, None
    # PredRow.score → conf ≈ min(1, abs(score)*2) matching serve mapping roughly
    confs = [min(1.0, abs(r.score) * 2.0) for r in rows]
    gated = [r for r, c in zip(rows, confs, strict=True) if c >= thr]
    if not gated:
        return None, 0.0
    hit = sum(1 for r in gated if r.hit) / len(gated)
    return hit, len(gated) / len(rows)


async def _base_samples(storage: Storage):
    from datetime import date
    from pathlib import Path as P

    series = await load_symbol_bars(storage)
    base = _enrich_cross_section(
        _demean_by_day(build_samples(series, horizon=1, min_history=60))
    )
    sectors = await load_sector_map(storage)
    samples = enrich_samples_with_sector_rs(base, sectors)
    cache = P("data/financial_filings_cache.json")
    if cache.is_file():
        raw = json.loads(cache.read_text(encoding="utf-8"))
        filings = [(str(a), date.fromisoformat(str(b)), str(c)) for a, b, c in raw]
        samples = enrich_samples_with_financial_filings(samples, filings)
    yoy = await load_yoy_events(storage)
    if yoy:
        samples = enrich_samples_with_yoy(samples, yoy)
    return samples


async def run_b006_rolling(storage: Storage, baseline_hit: float | None) -> ResearchResult:
    samples = await _base_samples(storage)
    rows = _walk_lmt_bagged(samples, train_window_days=120)
    diag = analyze_rows(rows, model_id="b006_roll120", horizon=1, panel=True)
    g_hit, g_cov = _gated_stats(rows)
    delta = None
    if baseline_hit is not None and diag.mean_symbol_hit is not None:
        delta = diag.mean_symbol_hit - baseline_hit
    keep = delta is not None and delta >= 0.005
    # Also keep if gated improves materially vs ~0.727 champion
    if g_hit is not None and g_hit >= 0.74 and (g_cov or 0) >= 0.08:
        keep = True
    status = "KEEP" if keep else "DEAD"
    notes = f"rolling 120d train; gated@0.55 hit={g_hit} cov={g_cov}"
    return ResearchResult(
        "B-006",
        status,
        diag.mean_symbol_hit,
        g_hit,
        g_cov,
        delta,
        notes,
    )


async def run_b002_market_summary(
    storage: Storage, baseline_hit: float | None
) -> ResearchResult:
    samples = await _base_samples(storage)
    mkt = await storage.list_market_daily_summary()
    if len(mkt) < 30:
        return ResearchResult(
            "B-002",
            "OPEN",
            None,
            None,
            None,
            None,
            f"insufficient market_daily_summary rows ({len(mkt)})",
        )
    samples = enrich_samples_with_market_summary(samples, mkt)
    rows = _walk_lmt_bagged(samples)
    diag = analyze_rows(rows, model_id="b002_mkt", horizon=1, panel=True)
    g_hit, g_cov = _gated_stats(rows)
    delta = None
    if baseline_hit is not None and diag.mean_symbol_hit is not None:
        delta = diag.mean_symbol_hit - baseline_hit
    keep = delta is not None and delta >= 0.005
    if g_hit is not None and g_hit >= 0.74 and (g_cov or 0) >= 0.08:
        keep = True
    status = "KEEP" if keep else "DEAD"
    return ResearchResult(
        "B-002",
        status,
        diag.mean_symbol_hit,
        g_hit,
        g_cov,
        delta,
        f"market summary features n_days={len(mkt)}; gated@0.55 hit={g_hit}",
    )


async def run_b007_interactions(
    storage: Storage, baseline_hit: float | None
) -> ResearchResult:
    samples = await _base_samples(storage)
    samples = enrich_samples_with_interactions(samples)
    rows = _walk_lmt_bagged(samples)
    diag = analyze_rows(rows, model_id="b007_inter", horizon=1, panel=True)
    g_hit, g_cov = _gated_stats(rows)
    delta = None
    if baseline_hit is not None and diag.mean_symbol_hit is not None:
        delta = diag.mean_symbol_hit - baseline_hit
    keep = delta is not None and delta >= 0.005
    if g_hit is not None and g_hit >= 0.74 and (g_cov or 0) >= 0.08:
        keep = True
    status = "KEEP" if keep else "DEAD"
    notes = f"filing×range + ret×vol; gated@0.55 hit={g_hit} cov={g_cov}"
    return ResearchResult(
        "B-007",
        status,
        diag.mean_symbol_hit,
        g_hit,
        g_cov,
        delta,
        notes,
    )


async def run_loop_research(storage: Storage) -> list[ResearchResult]:
    """Run B-006 then B-007 against expanding fin+sector baseline."""
    samples = await _base_samples(storage)
    base_rows = _walk_lmt_bagged(samples)
    base_diag = analyze_rows(base_rows, model_id="baseline_fin_sector", horizon=1, panel=True)
    baseline = base_diag.mean_symbol_hit
    results = [
        await run_b002_market_summary(storage, baseline),
        await run_b006_rolling(storage, baseline),
        await run_b007_interactions(storage, baseline),
    ]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"loop_research_{stamp}.md"
    lines = [
        f"# Loop C research — {stamp}",
        "",
        f"Baseline fin+sector mean_symbol_hit={baseline}",
        "",
        "| id | status | mean_hit | gated_hit@0.55 | cov | delta | notes |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.experiment_id} | {r.status} | {r.mean_symbol_hit} | "
            f"{r.gated_hit_055} | {r.gated_cov_055} | {r.delta_vs_baseline} | "
            f"{r.notes} |"
        )
    lines.append("")
    lines.append("Research only — not financial advice.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT_DIR / f"loop_research_{stamp}.json").write_text(
        json.dumps([asdict(r) for r in results], indent=2, default=str),
        encoding="utf-8",
    )
    log.info("loop_research_done", path=str(path), n=len(results))
    return results
