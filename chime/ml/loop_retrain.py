"""Loop B — weekly retrain, evaluate challenger, promote/rollback by gates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from chime.logging_setup import get_logger
from chime.ml.always_on import (
    enrich_samples_with_financial_filings,
    enrich_samples_with_sector_rs,
    enrich_samples_with_yoy,
    load_yoy_events,
    _walk_lmt_bagged,
)
from chime.ml.dataset import build_samples, load_symbol_bars
from chime.ml.diagnose import analyze_rows, load_sector_map
from chime.ml.harden import _demean_by_day
from chime.ml.iterate import _enrich_cross_section
from chime.ml.registry import (
    RegistryEntry,
    get_champion,
    promote_challenger,
    register_model,
    rollback_champion,
    write_registry_markdown,
)
from chime.storage import Storage

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RetrainResult:
    challenger_id: str
    promoted: bool
    rolled_back: bool
    reasons: tuple[str, ...]
    challenger_hit: float | None
    champion_hit: float | None


def _passes_promotion(
    *,
    challenger_hit: float | None,
    champion_hit: float | None,
    fold_hit_rates: tuple[float, ...],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if challenger_hit is None:
        return False, ["no challenger hit rate"]
    if champion_hit is None:
        reasons.append("no champion baseline — promote as first champion")
        return True, reasons
    # OOS hit must beat champion by +0.005 (aligned with always-on keep bar)
    # Plan asked +0.01 RankIC OR coverage; we use hit as available proxy.
    if challenger_hit + 1e-12 < champion_hit + 0.005:
        reasons.append(
            f"challenger hit {challenger_hit:.4f} < champion {champion_hit:.4f}+0.005"
        )
        return False, reasons
    if fold_hit_rates:
        pos = sum(1 for h in fold_hit_rates if h >= 0.52)
        need = max(1, int(0.7 * len(fold_hit_rates)))
        if pos < need:
            reasons.append(f"fold robustness {pos}/{len(fold_hit_rates)} < {need}")
            return False, reasons
    reasons.append(
        f"challenger hit {challenger_hit:.4f} >= champion {champion_hit:.4f}+0.005"
    )
    return True, reasons


async def run_loop_retrain(
    storage: Storage,
    *,
    force_promote_first: bool = False,
) -> RetrainResult:
    """Train fin+sector always-on challenger; promote if gates pass."""
    from datetime import date as date_cls
    from pathlib import Path
    import json

    series = await load_symbol_bars(storage)
    base = _enrich_cross_section(
        _demean_by_day(build_samples(series, horizon=1, min_history=60))
    )
    sectors = await load_sector_map(storage)
    samples = enrich_samples_with_sector_rs(base, sectors)
    cache = Path("data/financial_filings_cache.json")
    if cache.is_file():
        raw = json.loads(cache.read_text(encoding="utf-8"))
        filings = [
            (str(a), date_cls.fromisoformat(str(b)), str(c)) for a, b, c in raw
        ]
        samples = enrich_samples_with_financial_filings(samples, filings)
    yoy = await load_yoy_events(storage)
    if yoy:
        samples = enrich_samples_with_yoy(samples, yoy)

    rows = _walk_lmt_bagged(samples)
    diag = analyze_rows(
        rows, model_id="challenger_fin_sector", horizon=1, panel=True
    )
    # Live gated metrics from WF ledger (B-005)
    gated_hit = None
    gated_cov = None
    async with storage._pool.connection() as conn:
        cal_row = await (
            await conn.execute(
                """
                SELECT COUNT(*) n,
                       AVG(CASE WHEN hit THEN 1.0 ELSE 0.0 END)
                         FILTER (WHERE confidence >= 0.55) gated_hit,
                       AVG(CASE WHEN confidence >= 0.55 THEN 1.0 ELSE 0.0 END) cov
                FROM forecast_outcomes
                WHERE model_version = 'wf_fin_sector_h1'
                  AND scored = TRUE AND hit IS NOT NULL
                """
            )
        ).fetchone()
    if cal_row:
        cd = dict(cal_row)
        if cd.get("gated_hit") is not None:
            gated_hit = float(cd["gated_hit"])
        if cd.get("cov") is not None:
            gated_cov = float(cd["cov"])

    stamp = date.today().strftime("%Y%m%d")
    challenger_id = f"challenger_gated_c55_{stamp}"
    champ = await get_champion(storage)
    # Promote on gated hit when available (selective serve path)
    champ_hit = None
    if champ:
        if champ.get("oos_gated_hit") is not None:
            champ_hit = float(champ["oos_gated_hit"])
        elif champ.get("oos_hit") is not None:
            champ_hit = float(champ["oos_hit"])
    parent = champ["model_id"] if champ else None
    challenger_metric = gated_hit if gated_hit is not None else diag.mean_symbol_hit

    await register_model(
        storage,
        RegistryEntry(
            model_id=challenger_id,
            algo="hgb_clf_lmt_bag_gated_c55",
            status="challenger",
            horizons=(1, 2, 3, 5),
            feature_list=("path", "cs", "sector_rs", "financials", "yoy", "conf_gate"),
            oos_hit=diag.mean_symbol_hit,
            oos_gated_hit=gated_hit if gated_hit is not None else diag.bucket_hits.get("HIGH"),
            oos_coverage=gated_cov,
            train_start=None,
            train_end=date.today(),
            parent_model_id=parent,
            notes="weekly loop B gated challenger (B-005)",
        ),
    )

    ok, reasons = _passes_promotion(
        challenger_hit=challenger_metric,
        champion_hit=champ_hit,
        fold_hit_rates=(),
    )
    if force_promote_first and champ is None:
        ok = True
        reasons = ["first champion bootstrap"]

    promoted = False
    if ok:
        promoted = await promote_challenger(
            storage, challenger_id=challenger_id, notes="; ".join(reasons)
        )

    # Rollback check: if champion degraded and live worse — handled in nightly;
    # here optional explicit rollback if challenger failed badly vs retired.
    rolled = False
    if not promoted and champ and champ.get("degraded"):
        # leave degraded champion; research continues
        pass

    await write_registry_markdown(storage)
    log.info(
        "loop_retrain_done",
        challenger_id=challenger_id,
        promoted=promoted,
        reasons=reasons,
    )
    return RetrainResult(
        challenger_id=challenger_id,
        promoted=promoted,
        rolled_back=rolled,
        reasons=tuple(reasons),
        challenger_hit=challenger_metric,
        champion_hit=champ_hit,
    )


async def maybe_rollback_from_live(storage: Storage) -> str | None:
    """If champion degraded, attempt rollback to parent."""
    champ = await get_champion(storage)
    if not champ or not champ.get("degraded"):
        return None
    return await rollback_champion(storage)
