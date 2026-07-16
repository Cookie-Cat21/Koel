"""Always-on accuracy scoreboard (purged mean per-symbol hit)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from chime.logging_setup import get_logger
from chime.ml import sklearn_available
from chime.ml.dataset import Sample, build_samples, load_symbol_bars
from chime.ml.diagnose import PredRow, analyze_rows
from chime.ml.harden import _demean_by_day, _purge_train
from chime.ml.iterate import (
    _enrich_cross_section,
    _predict_lmt_bagged,
    _rows_from_scores,
)
from chime.ml.walkforward import _unique_sorted_dates
from chime.storage import Storage

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class EventFeat:
    symbol: str
    as_of: date
    disc_7d: float
    disc_30d: float
    disc_fin_30d: float
    notice_30d: float


@dataclass
class AlwaysOnResult:
    lever: str
    mean_symbol_hit: float | None
    pooled_hit: float | None
    symbols_ge_070: int
    n_symbols: int
    n_rows: int
    high_bucket_hit: float | None
    delta_vs_baseline: float | None = None
    keep: bool | None = None
    notes: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_FIN_CAT_HINTS = (
    "FINANCIAL",
    "ANNUAL",
    "INTERIM",
    "QUARTER",
    "DIVIDEND",
    "EARNINGS",
    "AUDITED",
)


def _is_financial_category(cat: str | None) -> bool:
    if not cat:
        return False
    u = cat.upper()
    return any(h in u for h in _FIN_CAT_HINTS)


async def load_disclosure_events(
    storage: Storage,
) -> list[tuple[str, date, str | None]]:
    """Return (symbol, published_date, category) ascending by date."""
    out: list[tuple[str, date, str | None]] = []
    async with storage._pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT symbol, published_at, category
                FROM disclosures
                WHERE symbol IS NOT NULL AND published_at IS NOT NULL
                ORDER BY symbol, published_at
                """
            )
            for row in await cur.fetchall():
                d = dict(row)
                sym = str(d["symbol"]).strip().upper()
                pub = d["published_at"]
                if hasattr(pub, "date"):
                    pub_d = pub.date()
                elif isinstance(pub, date):
                    pub_d = pub
                else:
                    continue
                cat = d.get("category")
                cat_s = str(cat) if cat is not None else None
                out.append((sym, pub_d, cat_s))
    return out


async def load_notice_events(
    storage: Storage,
) -> list[tuple[str, date]]:
    out: list[tuple[str, date]] = []
    async with storage._pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT symbol, published_at
                FROM market_notices
                WHERE symbol IS NOT NULL AND published_at IS NOT NULL
                ORDER BY symbol, published_at
                """
            )
            for row in await cur.fetchall():
                d = dict(row)
                sym = str(d["symbol"]).strip().upper()
                pub = d["published_at"]
                if hasattr(pub, "date"):
                    pub_d = pub.date()
                elif isinstance(pub, date):
                    pub_d = pub
                else:
                    continue
                out.append((sym, pub_d))
    return out


def enrich_samples_with_events(
    samples: list[Sample],
    disclosures: list[tuple[str, date, str | None]],
    notices: list[tuple[str, date]],
) -> list[Sample]:
    """Append disc_7d, disc_30d, disc_fin_30d, notice_30d (leakage-safe)."""
    by_sym_disc: dict[str, list[tuple[date, str | None]]] = {}
    for sym, d, cat in disclosures:
        by_sym_disc.setdefault(sym, []).append((d, cat))
    by_sym_notice: dict[str, list[date]] = {}
    for sym, d in notices:
        by_sym_notice.setdefault(sym, []).append(d)

    out: list[Sample] = []
    for s in samples:
        disc = by_sym_disc.get(s.symbol, [])
        notes = by_sym_notice.get(s.symbol, [])
        d7 = d30 = fin30 = 0.0
        start7 = s.as_of - timedelta(days=7)
        start30 = s.as_of - timedelta(days=30)
        for d, cat in disc:
            if d > s.as_of:
                break
            if d >= start30:
                d30 += 1.0
                if _is_financial_category(cat):
                    fin30 += 1.0
            if d >= start7:
                d7 += 1.0
        n30 = 0.0
        for d in notes:
            if d > s.as_of:
                break
            if d >= start30:
                n30 += 1.0
        out.append(
            Sample(
                symbol=s.symbol,
                as_of=s.as_of,
                x=tuple(s.x) + (d7, d30, fin30, n30),
                y_ret=s.y_ret,
                y_dir=s.y_dir,
                horizon=s.horizon,
            )
        )
    return out


def _walk_lmt_bagged(samples: list[Sample]) -> list[PredRow]:
    dates = _unique_sorted_dates(samples)
    min_train_days, fold_step, embargo = 100, 10, 2
    rows: list[PredRow] = []
    cut = min_train_days
    fold = 0
    while cut + fold_step <= len(dates):
        test_dates = set(dates[cut : cut + fold_step])
        train = _purge_train(
            samples, dates=dates, cut=cut, horizon=1, embargo=embargo
        )
        test = [s for s in samples if s.as_of in test_dates]
        cut += fold_step
        if len(train) < 50 or len(test) < 10:
            continue
        try:
            scores = _predict_lmt_bagged(train, test)
        except Exception as exc:
            log.warning("always_on_fold_failed", fold=fold, error=str(exc))
            continue
        rows.extend(_rows_from_scores(test, scores, fold=fold, sectors=None))
        fold += 1
    return rows


async def run_always_on(
    *,
    storage: Storage,
    lever: str = "baseline_cs_lmt_bag",
    use_events: bool = False,
    baseline_mean: float | None = None,
    limit_symbols: int | None = None,
    out_dir: Path = Path("docs/experiments"),
) -> AlwaysOnResult:
    if not sklearn_available():
        return AlwaysOnResult(
            lever=lever,
            mean_symbol_hit=None,
            pooled_hit=None,
            symbols_ge_070=0,
            n_symbols=0,
            n_rows=0,
            high_bucket_hit=None,
            notes="sklearn missing",
        )

    series = await load_symbol_bars(storage, limit_symbols=limit_symbols)
    base = build_samples(series, horizon=1, min_history=60)
    samples = _enrich_cross_section(_demean_by_day(base))
    extras: dict[str, Any] = {
        "symbols": len(series),
        "disclosures": 0,
        "notices": 0,
    }
    if use_events:
        discs = await load_disclosure_events(storage)
        notices = await load_notice_events(storage)
        extras["disclosures"] = len(discs)
        extras["notices"] = len(notices)
        samples = enrich_samples_with_events(samples, discs, notices)

    rows = _walk_lmt_bagged(samples)
    diag = analyze_rows(rows, model_id=lever, horizon=1, panel=True)
    delta = None
    keep = None
    if baseline_mean is not None and diag.mean_symbol_hit is not None:
        delta = diag.mean_symbol_hit - baseline_mean
        keep = delta >= 0.005

    result = AlwaysOnResult(
        lever=lever,
        mean_symbol_hit=diag.mean_symbol_hit,
        pooled_hit=diag.pooled_hit,
        symbols_ge_070=diag.symbols_ge_070,
        n_symbols=diag.n_symbols,
        n_rows=diag.n_rows,
        high_bucket_hit=diag.bucket_hits.get("HIGH"),
        delta_vs_baseline=delta,
        keep=keep,
        notes=(
            "events+" if use_events else "path+CS only"
        ),
        extras=extras,
    )

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / f"ml_always_on_{stamp}.md"
    lines = [
        "# Always-on accuracy scoreboard",
        "",
        f"**Generated (UTC):** {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"**Lever:** `{result.lever}`",
        f"**Mean symbol hit:** **{result.mean_symbol_hit}**",
        f"**Pooled hit:** {result.pooled_hit}",
        f"**Symbols ≥70%:** {result.symbols_ge_070}/{result.n_symbols}",
        f"**HIGH bucket hit:** {result.high_bucket_hit}",
        f"**Rows:** {result.n_rows}",
        f"**Delta vs baseline:** {result.delta_vs_baseline}",
        f"**Keep (≥+0.005):** {result.keep}",
        f"**Notes:** {result.notes}",
        f"**Extras:** `{json.dumps(result.extras)}`",
        "",
        "Research only — not financial advice.",
        "",
    ]
    md.write_text("\n".join(lines), encoding="utf-8")
    md.with_suffix(".json").write_text(
        json.dumps(result.as_dict(), indent=2) + "\n", encoding="utf-8"
    )
    log.info(
        "always_on_done",
        lever=lever,
        mean_symbol_hit=result.mean_symbol_hit,
        keep=keep,
        report=str(md),
    )
    return result
