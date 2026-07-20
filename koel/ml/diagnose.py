"""Autopsy OOS predictions: who hits high confidence, who doesn't, why."""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from koel.logging_setup import get_logger
from koel.ml import sklearn_available
from koel.ml.dataset import build_samples, load_symbol_bars
from koel.ml.features import FEATURE_NAMES
from koel.ml.harden import (
    _demean_by_day,
    _fit_predict_with_scores,
    _purge_train,
)
from koel.ml.walkforward import _unique_sorted_dates
from koel.storage import Storage

log = get_logger(__name__)

HIGH_THR = 0.20
MID_THR = 0.10


@dataclass(frozen=True, slots=True)
class PredRow:
    symbol: str
    as_of: date
    fold: int
    score: float
    y_dir: float
    y_ret: float
    hit: bool
    features: tuple[float, ...]
    sector: str | None = None


@dataclass
class DiagnoseResult:
    model_id: str
    horizon: int
    panel: bool
    n_rows: int
    pooled_hit: float | None
    mean_symbol_hit: float | None
    symbols_ge_070: int
    symbols_ge_075: int
    n_symbols: int
    bucket_counts: dict[str, int] = field(default_factory=dict)
    bucket_hits: dict[str, float | None] = field(default_factory=dict)
    feature_gaps: list[dict[str, Any]] = field(default_factory=list)
    top_symbols: list[dict[str, Any]] = field(default_factory=list)
    bottom_symbols: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    sector_slice: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _bucket(score: float) -> str:
    a = abs(score)
    if a >= HIGH_THR:
        return "HIGH"
    if a >= MID_THR:
        return "MID"
    return "LOW"


def _nanmean(xs: list[float]) -> float | None:
    vals = [x for x in xs if math.isfinite(x)]
    if not vals:
        return None
    return sum(vals) / len(vals)


def collect_oos_rows(
    series: dict,
    *,
    horizon: int = 1,
    panel: bool = True,
    model_id: str = "M1_hgb_clf",
    min_history: int = 60,
    min_train_days: int = 100,
    fold_step: int = 10,
    embargo: int = 2,
    sectors: dict[str, str] | None = None,
) -> list[PredRow]:
    samples = build_samples(series, horizon=horizon, min_history=min_history)
    if panel:
        samples = _demean_by_day(samples)
    if not samples:
        return []
    dates = _unique_sorted_dates(samples)
    if len(dates) < min_train_days + fold_step:
        return []

    rows: list[PredRow] = []
    cut = min_train_days
    fold = 0
    while cut + fold_step <= len(dates):
        test_dates = set(dates[cut : cut + fold_step])
        train = _purge_train(
            samples, dates=dates, cut=cut, horizon=horizon, embargo=embargo
        )
        test = [s for s in samples if s.as_of in test_dates]
        cut += fold_step
        if len(train) < 50 or len(test) < 10:
            continue
        try:
            y_dir, y_ret, scores, _pred, _as_ofs = _fit_predict_with_scores(
                train, test, model_id=model_id
            )
        except Exception as exc:
            log.warning("diagnose_fold_failed", fold=fold, error=str(exc))
            continue
        for s, yd, yr, sc in zip(test, y_dir, y_ret, scores, strict=True):
            if yd == 0 or sc == 0:
                continue
            pred_d = 1.0 if sc > 0 else -1.0
            hit = (yd > 0 and pred_d > 0) or (yd < 0 and pred_d < 0)
            sec = None
            if sectors:
                sec = sectors.get(s.symbol)
            rows.append(
                PredRow(
                    symbol=s.symbol,
                    as_of=s.as_of,
                    fold=fold,
                    score=float(sc),
                    y_dir=float(yd),
                    y_ret=float(yr),
                    hit=hit,
                    features=s.x,
                    sector=sec,
                )
            )
        fold += 1
    return rows


def _symbol_stats(rows: list[PredRow]) -> list[dict[str, Any]]:
    by: dict[str, list[PredRow]] = defaultdict(list)
    for r in rows:
        by[r.symbol].append(r)
    out: list[dict[str, Any]] = []
    for sym, rs in by.items():
        hits = sum(1 for r in rs if r.hit)
        n = len(rs)
        high = [r for r in rs if abs(r.score) >= HIGH_THR]
        high_hits = sum(1 for r in high if r.hit)
        out.append(
            {
                "symbol": sym,
                "n": n,
                "hit_rate": hits / n if n else None,
                "high_n": len(high),
                "high_hit_rate": high_hits / len(high) if high else None,
                "mean_abs_score": _nanmean([abs(r.score) for r in rs]),
                "mean_liquidity": _nanmean(
                    [r.features[FEATURE_NAMES.index("liquidity_20d")] for r in rs]
                ),
                "mean_vol": _nanmean(
                    [r.features[FEATURE_NAMES.index("vol_20d")] for r in rs]
                ),
                "sector": next((r.sector for r in rs if r.sector), None),
            }
        )
    out.sort(key=lambda d: (d["hit_rate"] is not None, d["hit_rate"] or 0), reverse=True)
    return out


def _feature_gap_table(rows: list[PredRow]) -> list[dict[str, Any]]:
    high_hit = [r for r in rows if abs(r.score) >= HIGH_THR and r.hit]
    high_miss = [r for r in rows if abs(r.score) >= HIGH_THR and not r.hit]
    low = [r for r in rows if abs(r.score) < MID_THR]
    gaps: list[dict[str, Any]] = []
    for i, name in enumerate(FEATURE_NAMES):
        mh = _nanmean([r.features[i] for r in high_hit])
        mm = _nanmean([r.features[i] for r in high_miss])
        ml = _nanmean([r.features[i] for r in low])
        # standardized gap high_hit vs low
        pool = [r.features[i] for r in high_hit + low if math.isfinite(r.features[i])]
        sd = statistics.pstdev(pool) if len(pool) >= 3 else None
        gap = None
        if mh is not None and ml is not None and sd and sd > 0:
            gap = (mh - ml) / sd
        gaps.append(
            {
                "feature": name,
                "high_hit_mean": mh,
                "high_miss_mean": mm,
                "low_mean": ml,
                "std_gap_hit_vs_low": gap,
                "n_high_hit": len(high_hit),
                "n_high_miss": len(high_miss),
                "n_low": len(low),
            }
        )
    gaps.sort(
        key=lambda d: abs(d["std_gap_hit_vs_low"] or 0),
        reverse=True,
    )
    return gaps


def _tercile_mix(rows: list[PredRow], feat_idx: int) -> dict[str, dict[str, float]]:
    """Share of HIGH_HIT / HIGH_MISS / LOW in each feature tercile."""
    vals = [(r, r.features[feat_idx]) for r in rows if math.isfinite(r.features[feat_idx])]
    if len(vals) < 30:
        return {}
    sorted_vals = sorted(v for _, v in vals)
    t1 = sorted_vals[len(sorted_vals) // 3]
    t2 = sorted_vals[(2 * len(sorted_vals)) // 3]

    def terc(v: float) -> str:
        if v <= t1:
            return "low"
        if v <= t2:
            return "mid"
        return "high"

    buckets = {
        "HIGH_HIT": [r for r, _ in vals if abs(r.score) >= HIGH_THR and r.hit],
        "HIGH_MISS": [r for r, _ in vals if abs(r.score) >= HIGH_THR and not r.hit],
        "LOW": [r for r, _ in vals if abs(r.score) < MID_THR],
    }
    out: dict[str, dict[str, float]] = {}
    for bname, rs in buckets.items():
        if not rs:
            continue
        counts = {"low": 0, "mid": 0, "high": 0}
        for r in rs:
            counts[terc(r.features[feat_idx])] += 1
        n = len(rs)
        out[bname] = {k: v / n for k, v in counts.items()}
    return out


def build_recommendations(
    *,
    gaps: list[dict[str, Any]],
    sym_stats: list[dict[str, Any]],
    pooled_hit: float | None,
    mean_symbol_hit: float | None,
    liq_mix: dict[str, dict[str, float]],
    vol_mix: dict[str, dict[str, float]],
) -> list[str]:
    recs: list[str] = []
    if mean_symbol_hit is not None and mean_symbol_hit < 0.70:
        recs.append(
            f"Board mean per-symbol hit={mean_symbol_hit:.3f} "
            f"(pooled={pooled_hit}) — below 0.70–0.75 target; iterate levers."
        )
    # Liquidity story
    if liq_mix.get("HIGH_HIT") and liq_mix.get("LOW"):
        hh = liq_mix["HIGH_HIT"].get("high", 0)
        ll = liq_mix["LOW"].get("high", 0)
        if hh - ll >= 0.08:
            recs.append(
                "HIGH_HIT skews to high-liquidity tercile vs LOW — "
                "try liquid-universe filter / liquidity-weighted gate."
            )
        elif ll - hh >= 0.08:
            recs.append(
                "LOW has more high-liquidity than HIGH_HIT — "
                "liquidity alone won't lift the board; look at vol/momentum."
            )
    if vol_mix.get("HIGH_MISS") and vol_mix.get("HIGH_HIT"):
        hm = vol_mix["HIGH_MISS"].get("high", 0)
        hh = vol_mix["HIGH_HIT"].get("high", 0)
        if hm - hh >= 0.08:
            recs.append(
                "HIGH_MISS richer in high-vol tercile — add vol/spike veto "
                "before trusting confident calls."
            )
    # Top feature gaps
    for g in gaps[:3]:
        if g["std_gap_hit_vs_low"] is None:
            continue
        direction = "higher" if g["std_gap_hit_vs_low"] > 0 else "lower"
        recs.append(
            f"Feature `{g['feature']}`: HIGH_HIT has {direction} values than LOW "
            f"(std gap={g['std_gap_hit_vs_low']:.2f}) — use in filter or meta-label."
        )
    # Symbol dispersion
    rates = [s["hit_rate"] for s in sym_stats if s["hit_rate"] is not None]
    if rates:
        ge70 = sum(1 for r in rates if r >= 0.70)
        recs.append(
            f"{ge70}/{len(rates)} symbols already ≥70% hit — "
            "study their trait overlap; apply that filter board-wide."
        )
        if statistics.pstdev(rates) >= 0.08:
            recs.append(
                "Large per-symbol hit dispersion — consider per-sector or "
                "liquidity-bucket models instead of one global clf."
            )
    if not recs:
        recs.append("No strong automatic lever; inspect top/bottom symbol tables manually.")
    return recs


def analyze_rows(
    rows: list[PredRow],
    *,
    model_id: str,
    horizon: int,
    panel: bool,
) -> DiagnoseResult:
    if not rows:
        return DiagnoseResult(
            model_id=model_id,
            horizon=horizon,
            panel=panel,
            n_rows=0,
            pooled_hit=None,
            mean_symbol_hit=None,
            symbols_ge_070=0,
            symbols_ge_075=0,
            n_symbols=0,
            recommendations=["No OOS rows — check daily_bars / train window."],
        )

    pooled = sum(1 for r in rows if r.hit) / len(rows)
    # Buckets
    bucket_rows: dict[str, list[PredRow]] = defaultdict(list)
    for r in rows:
        b = _bucket(r.score)
        key = f"{b}_{'HIT' if r.hit else 'MISS'}"
        bucket_rows[key].append(r)
        bucket_rows[b].append(r)

    bucket_counts = {k: len(v) for k, v in sorted(bucket_rows.items())}
    bucket_hits: dict[str, float | None] = {}
    for name in ("HIGH", "MID", "LOW"):
        rs = bucket_rows.get(name, [])
        bucket_hits[name] = (
            sum(1 for r in rs if r.hit) / len(rs) if rs else None
        )

    gaps = _feature_gap_table(rows)
    sym_stats = _symbol_stats(rows)
    rates = [s["hit_rate"] for s in sym_stats if s["hit_rate"] is not None and s["n"] >= 20]
    mean_sym = sum(rates) / len(rates) if rates else None
    ge70 = sum(1 for r in rates if r is not None and r >= 0.70)
    ge75 = sum(1 for r in rates if r is not None and r >= 0.75)

    liq_i = FEATURE_NAMES.index("liquidity_20d")
    vol_i = FEATURE_NAMES.index("vol_20d")
    liq_mix = _tercile_mix(rows, liq_i)
    vol_mix = _tercile_mix(rows, vol_i)

    # Sector slice
    sector_slice: list[dict[str, Any]] = []
    by_sec: dict[str, list[PredRow]] = defaultdict(list)
    for r in rows:
        if r.sector:
            by_sec[r.sector].append(r)
    for sec, rs in sorted(by_sec.items(), key=lambda kv: -len(kv[1])):
        sector_slice.append(
            {
                "sector": sec,
                "n": len(rs),
                "hit_rate": sum(1 for r in rs if r.hit) / len(rs),
                "mean_abs_score": _nanmean([abs(r.score) for r in rs]),
            }
        )

    recs = build_recommendations(
        gaps=gaps,
        sym_stats=[s for s in sym_stats if (s["n"] or 0) >= 20],
        pooled_hit=pooled,
        mean_symbol_hit=mean_sym,
        liq_mix=liq_mix,
        vol_mix=vol_mix,
    )
    # Attach mix summaries into recommendations context via feature_gaps note
    if liq_mix:
        recs.append(f"Liquidity tercile mix: {json.dumps(liq_mix)}")
    if vol_mix:
        recs.append(f"Vol tercile mix: {json.dumps(vol_mix)}")

    return DiagnoseResult(
        model_id=model_id,
        horizon=horizon,
        panel=panel,
        n_rows=len(rows),
        pooled_hit=pooled,
        mean_symbol_hit=mean_sym,
        symbols_ge_070=ge70,
        symbols_ge_075=ge75,
        n_symbols=len(rates),
        bucket_counts=bucket_counts,
        bucket_hits=bucket_hits,
        feature_gaps=gaps,
        top_symbols=sym_stats[:25],
        bottom_symbols=list(reversed(sym_stats[-25:])),
        recommendations=recs,
        sector_slice=sector_slice,
    )


def render_diagnose_markdown(result: DiagnoseResult) -> str:
    lines = [
        "# ML diagnose — who hits ~70% and why",
        "",
        f"**Generated (UTC):** {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"**Model:** `{result.model_id}` · horizon={result.horizon} · "
        f"panel={result.panel}",
        f"**Rows:** {result.n_rows}",
        f"**Pooled hit:** {result.pooled_hit}",
        f"**Mean per-symbol hit (n≥20):** {result.mean_symbol_hit}",
        f"**Symbols ≥70% / ≥75%:** {result.symbols_ge_070} / "
        f"{result.symbols_ge_075} of {result.n_symbols}",
        "",
        "## Target",
        "",
        "Board-wide average **70–75%** direction hit across companies "
        "(research metric; NFA).",
        "",
        "## Confidence buckets",
        "",
        "| Bucket | Hit rate |",
        "|---|---:|",
    ]
    for name in ("HIGH", "MID", "LOW"):
        hr = result.bucket_hits.get(name)
        lines.append(
            f"| {name} (|score| "
            f"{'≥0.20' if name == 'HIGH' else '0.10–0.20' if name == 'MID' else '<0.10'}) | "
            f"{hr if hr is not None else '—'} |"
        )
    lines.extend(
        ["", "### Counts", "", "```", json.dumps(result.bucket_counts, indent=2), "```", ""]
    )

    lines.extend(
        [
            "## Feature gaps (HIGH_HIT vs LOW)",
            "",
            "| Feature | HIGH_HIT | HIGH_MISS | LOW | Std gap |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for g in result.feature_gaps:
        def fmt(v: float | None) -> str:
            if v is None:
                return "—"
            if abs(v) >= 1000:
                return f"{v:.2e}"
            return f"{v:.4g}"

        gap = g["std_gap_hit_vs_low"]
        lines.append(
            f"| {g['feature']} | {fmt(g['high_hit_mean'])} | "
            f"{fmt(g['high_miss_mean'])} | {fmt(g['low_mean'])} | "
            f"{fmt(gap)} |"
        )

    if result.sector_slice:
        lines.extend(
            [
                "",
                "## Sector slice",
                "",
                "| Sector | N | Hit | Mean |score| |",
                "|---|---:|---:|---:|",
            ]
        )
        for s in result.sector_slice[:20]:
            lines.append(
                f"| {s['sector']} | {s['n']} | {s['hit_rate']:.3f} | "
                f"{s['mean_abs_score'] if s['mean_abs_score'] is not None else '—'} |"
            )

    lines.extend(
        [
            "",
            "## Top symbols by hit rate (n≥20 in full table filter)",
            "",
            "| Symbol | N | Hit | High-N | High-hit | Liq | Vol | Sector |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for s in result.top_symbols:
        if (s["n"] or 0) < 20:
            continue
        lines.append(
            f"| {s['symbol']} | {s['n']} | {s['hit_rate']:.3f} | "
            f"{s['high_n']} | "
            f"{s['high_hit_rate'] if s['high_hit_rate'] is not None else '—'} | "
            f"{s['mean_liquidity'] if s['mean_liquidity'] is not None else '—'} | "
            f"{s['mean_vol'] if s['mean_vol'] is not None else '—'} | "
            f"{s['sector'] or '—'} |"
        )

    lines.extend(
        [
            "",
            "## Bottom symbols",
            "",
            "| Symbol | N | Hit | High-N | Liq | Vol | Sector |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for s in result.bottom_symbols:
        if (s["n"] or 0) < 20:
            continue
        lines.append(
            f"| {s['symbol']} | {s['n']} | {s['hit_rate']:.3f} | "
            f"{s['high_n']} | "
            f"{s['mean_liquidity'] if s['mean_liquidity'] is not None else '—'} | "
            f"{s['mean_vol'] if s['mean_vol'] is not None else '—'} | "
            f"{s['sector'] or '—'} |"
        )

    lines.extend(["", "## Recommendations", ""])
    for r in result.recommendations:
        lines.append(f"- {r}")
    lines.extend(
        [
            "",
            "Research autopsy only — not financial advice.",
            "",
        ]
    )
    return "\n".join(lines)


async def load_sector_map(storage: Storage) -> dict[str, str]:
    out: dict[str, str] = {}
    async with storage._pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT symbol, sector FROM stocks
                WHERE sector IS NOT NULL AND btrim(sector) <> ''
                """
        )
        for row in await cur.fetchall():
            d = dict(row)
            sym = str(d["symbol"]).strip().upper()
            sec = str(d["sector"]).strip()
            if sym and sec:
                out[sym] = sec
    return out


async def run_diagnose(
    *,
    storage: Storage,
    horizon: int = 1,
    panel: bool = True,
    model_id: str = "M1_hgb_clf",
    limit_symbols: int | None = None,
    out_dir: Path = Path("docs/experiments"),
) -> DiagnoseResult:
    if not sklearn_available():
        return DiagnoseResult(
            model_id=model_id,
            horizon=horizon,
            panel=panel,
            n_rows=0,
            pooled_hit=None,
            mean_symbol_hit=None,
            symbols_ge_070=0,
            symbols_ge_075=0,
            n_symbols=0,
            recommendations=["sklearn not installed"],
        )
    series = await load_symbol_bars(storage, limit_symbols=limit_symbols)
    sectors = await load_sector_map(storage)
    log.info(
        "diagnose_loaded",
        symbols=len(series),
        sectors=len(sectors),
        model_id=model_id,
        horizon=horizon,
    )
    rows = collect_oos_rows(
        series,
        horizon=horizon,
        panel=panel,
        model_id=model_id,
        sectors=sectors,
    )
    result = analyze_rows(rows, model_id=model_id, horizon=horizon, panel=panel)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_md = out_dir / f"ml_diagnose_{stamp}.md"
    out_json = out_md.with_suffix(".json")
    out_md.write_text(render_diagnose_markdown(result), encoding="utf-8")
    out_json.write_text(json.dumps(result.as_dict(), indent=2, default=str) + "\n")
    log.info("diagnose_done", report=str(out_md), n_rows=result.n_rows)
    return result
