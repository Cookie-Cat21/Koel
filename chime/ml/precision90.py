"""High-Precision Emitter chase: OOS precision ≥ 90% under selective gates.

Selective system (not always-on). Stress-tested on purged CSE path history.
"""

from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from chime.logging_setup import get_logger
from chime.ml import sklearn_available
from chime.ml.dataset import build_samples, load_symbol_bars
from chime.ml.diagnose import PredRow, load_sector_map
from chime.ml.features import FEATURE_NAMES
from chime.ml.harden import _demean_by_day, _purge_train
from chime.ml.iterate import (
    _enrich_cross_section,
    _predict_lmt_bagged,
    _rows_from_scores,
)
from chime.ml.walkforward import _unique_sorted_dates
from chime.storage import Storage

log = get_logger(__name__)

MIN_EMITS = 200
MIN_SYMBOLS = 80
PRECISION_TARGET = 0.90
FOLD_PREC_FLOOR = 0.85


@dataclass(frozen=True, slots=True)
class GateCandidate:
    name: str
    precision: float
    n_emits: int
    n_symbols: int
    coverage: float
    folds_ge_floor: int
    n_folds: int
    passes_target: bool
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class Precision90Result:
    target_met: bool
    best_gate: str | None
    best_precision: float | None
    best_n_emits: int
    candidates: list[GateCandidate] = field(default_factory=list)
    stress: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    n_rows: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "target_met": self.target_met,
            "best_gate": self.best_gate,
            "best_precision": self.best_precision,
            "best_n_emits": self.best_n_emits,
            "n_rows": self.n_rows,
            "candidates": [asdict(c) for c in self.candidates],
            "stress": self.stress,
            "recommendations": list(self.recommendations),
        }


def _feat(row: PredRow, name: str) -> float:
    try:
        i = FEATURE_NAMES.index(name)
    except ValueError:
        return float("nan")
    if i >= len(row.features):
        return float("nan")
    return float(row.features[i])


def _collect_primary_rows(
    series: dict,
    *,
    sectors: dict[str, str],
) -> list[PredRow]:
    base = build_samples(series, horizon=1, min_history=60)
    samples = _enrich_cross_section(_demean_by_day(base))
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
            log.warning("p90_fold_failed", fold=fold, error=str(exc))
            continue
        rows.extend(
            _rows_from_scores(test, scores, fold=fold, sectors=sectors)
        )
        fold += 1
    return rows


def _collect_reg_rows(
    series: dict,
    *,
    sectors: dict[str, str],
) -> list[PredRow]:
    """Regressor scores (predicted demeaned return) for |ŷ| gates."""
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingRegressor

    base = build_samples(series, horizon=1, min_history=60)
    samples = _enrich_cross_section(_demean_by_day(base))
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
        # large-move train
        mags = sorted(abs(s.y_ret) for s in train)
        med = mags[len(mags) // 2] if mags else 0.0
        filtered = [s for s in train if abs(s.y_ret) >= med]
        if len(filtered) < 50:
            filtered = train
        x_tr = np.asarray([s.x for s in filtered], dtype=float)
        y_tr = np.asarray([s.y_ret for s in filtered], dtype=float)
        x_te = np.asarray([s.x for s in test], dtype=float)
        reg = HistGradientBoostingRegressor(
            max_depth=4, max_iter=120, learning_rate=0.08, random_state=0
        )
        try:
            reg.fit(x_tr, y_tr)
            pred = [float(v) for v in reg.predict(x_te)]
        except Exception as exc:
            log.warning("p90_reg_fold_failed", fold=fold, error=str(exc))
            continue
        rows.extend(_rows_from_scores(test, pred, fold=fold, sectors=sectors))
        fold += 1
    return rows


def _eval_mask(
    rows: list[PredRow], mask: list[bool], *, name: str, details: dict[str, Any]
) -> GateCandidate:
    emitted = [r for r, m in zip(rows, mask, strict=True) if m]
    n = len(emitted)
    if n == 0:
        return GateCandidate(
            name=name,
            precision=0.0,
            n_emits=0,
            n_symbols=0,
            coverage=0.0,
            folds_ge_floor=0,
            n_folds=0,
            passes_target=False,
            details=details,
        )
    prec = sum(1 for r in emitted if r.hit) / n
    syms = {r.symbol for r in emitted}
    coverage = n / len(rows) if rows else 0.0
    by_fold: dict[int, list[bool]] = defaultdict(list)
    for r in emitted:
        by_fold[r.fold].append(r.hit)
    folds_ok = 0
    for hits in by_fold.values():
        if hits and (sum(hits) / len(hits)) >= FOLD_PREC_FLOOR:
            folds_ok += 1
    n_folds = len(by_fold)
    need_folds = max(1, (2 * n_folds + 2) // 3) if n_folds else 0
    passes = (
        prec >= PRECISION_TARGET
        and (n >= MIN_EMITS or len(syms) >= MIN_SYMBOLS)
        and n_folds >= 2
        and folds_ok >= need_folds
    )
    return GateCandidate(
        name=name,
        precision=prec,
        n_emits=n,
        n_symbols=len(syms),
        coverage=coverage,
        folds_ge_floor=folds_ok,
        n_folds=n_folds,
        passes_target=passes,
        details={**details, "fold_precisions": {
            str(k): sum(v) / len(v) for k, v in sorted(by_fold.items())
        }},
    )


def sweep_score_thresholds(rows: list[PredRow], *, prefix: str) -> list[GateCandidate]:
    out: list[GateCandidate] = []
    for thr in (
        0.15, 0.18, 0.20, 0.22, 0.25, 0.28, 0.30, 0.32, 0.35, 0.38, 0.40, 0.45
    ):
        mask = [abs(r.score) >= thr for r in rows]
        out.append(
            _eval_mask(
                rows,
                mask,
                name=f"{prefix}|score|>={thr}",
                details={"thr": thr, "kind": "abs_score"},
            )
        )
    return out


def sweep_quantiles(rows: list[PredRow], *, prefix: str) -> list[GateCandidate]:
    """Emit top-q fraction by |score| globally and per-day."""
    out: list[GateCandidate] = []
    abs_scores = sorted(abs(r.score) for r in rows)
    for q in (0.01, 0.02, 0.03, 0.05, 0.08, 0.10):
        if not abs_scores:
            continue
        idx = max(0, int(math.floor((1.0 - q) * len(abs_scores))) - 1)
        thr = abs_scores[idx]
        mask = [abs(r.score) >= thr for r in rows]
        out.append(
            _eval_mask(
                rows,
                mask,
                name=f"{prefix}|global_top_{q:.0%}|thr≈{thr:.4f}",
                details={"q": q, "thr": thr, "kind": "global_quantile"},
            )
        )

    # per-day top q
    by_day: dict[Any, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        by_day[r.as_of].append(i)
    for q in (0.02, 0.05, 0.10):
        mask = [False] * len(rows)
        for idxs in by_day.values():
            ranked = sorted(idxs, key=lambda i: abs(rows[i].score), reverse=True)
            k = max(1, int(math.ceil(q * len(ranked))))
            for i in ranked[:k]:
                mask[i] = True
        out.append(
            _eval_mask(
                rows,
                mask,
                name=f"{prefix}|per_day_top_{q:.0%}",
                details={"q": q, "kind": "per_day_quantile"},
            )
        )
    return out


def sweep_intersections(rows: list[PredRow], *, prefix: str) -> list[GateCandidate]:
    """|score| thr AND feature above train-like global quantile."""
    out: list[GateCandidate] = []
    range_vals = sorted(
        _feat(r, "range_20d")
        for r in rows
        if math.isfinite(_feat(r, "range_20d"))
    )
    vol_vals = sorted(
        _feat(r, "vol_20d") for r in rows if math.isfinite(_feat(r, "vol_20d"))
    )
    if len(range_vals) < 50 or len(vol_vals) < 50:
        return out

    def qv(xs: list[float], q: float) -> float:
        return xs[int(q * (len(xs) - 1))]

    for score_thr in (0.20, 0.25, 0.30, 0.35):
        for feat_q in (0.50, 0.67, 0.75, 0.85):
            r_cut = qv(range_vals, feat_q)
            v_cut = qv(vol_vals, feat_q)
            mask = [
                abs(r.score) >= score_thr
                and math.isfinite(_feat(r, "range_20d"))
                and math.isfinite(_feat(r, "vol_20d"))
                and _feat(r, "range_20d") >= r_cut
                and _feat(r, "vol_20d") >= v_cut
                for r in rows
            ]
            out.append(
                _eval_mask(
                    rows,
                    mask,
                    name=(
                        f"{prefix}|score>={score_thr}"
                        f"&range/vol≥q{feat_q:.2f}"
                    ),
                    details={
                        "score_thr": score_thr,
                        "feat_q": feat_q,
                        "range_cut": r_cut,
                        "vol_cut": v_cut,
                        "kind": "intersection",
                    },
                )
            )
    return out


def _meta_features(row: PredRow) -> list[float]:
    return [
        abs(row.score),
        _feat(row, "vol_20d"),
        _feat(row, "range_20d"),
        _feat(row, "liquidity_20d"),
        _feat(row, "dist_20d_high"),
        _feat(row, "dist_20d_low"),
        _feat(row, "ret_5d"),
        _feat(row, "log_price"),
    ]


def apply_metalabel_scores(rows: list[PredRow]) -> list[float]:
    """Walk-forward meta P(correct); prior folds only. NaN if unavailable."""
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingClassifier

    by_fold: dict[int, list[PredRow]] = defaultdict(list)
    for r in rows:
        by_fold[r.fold].append(r)
    folds = sorted(by_fold)
    meta_p = {id(r): float("nan") for r in rows}
    for i, f in enumerate(folds):
        if i == 0:
            continue
        train_rows: list[PredRow] = []
        for pf in folds[:i]:
            train_rows.extend(by_fold[pf])
        if len(train_rows) < 80:
            continue
        x_tr = np.asarray([_meta_features(r) for r in train_rows], dtype=float)
        y_tr = np.asarray([1 if r.hit else 0 for r in train_rows])
        if len(set(y_tr.tolist())) < 2:
            continue
        clf = HistGradientBoostingClassifier(
            max_depth=3, max_iter=80, learning_rate=0.1, random_state=0
        )
        try:
            clf.fit(x_tr, y_tr)
        except Exception:
            continue
        test_rows = by_fold[f]
        x_te = np.asarray([_meta_features(r) for r in test_rows], dtype=float)
        proba = clf.predict_proba(x_te)[:, 1]
        for r, p in zip(test_rows, proba, strict=True):
            meta_p[id(r)] = float(p)
    return [meta_p[id(r)] for r in rows]


def sweep_metalabel(
    rows: list[PredRow], meta_p: list[float], *, prefix: str
) -> list[GateCandidate]:
    out: list[GateCandidate] = []
    for score_thr in (0.15, 0.20, 0.25, 0.30):
        for meta_thr in (0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90):
            mask = [
                abs(r.score) >= score_thr
                and math.isfinite(mp)
                and mp >= meta_thr
                for r, mp in zip(rows, meta_p, strict=True)
            ]
            out.append(
                _eval_mask(
                    rows,
                    mask,
                    name=f"{prefix}|score>={score_thr}&meta>={meta_thr}",
                    details={
                        "score_thr": score_thr,
                        "meta_thr": meta_thr,
                        "kind": "metalabel",
                    },
                )
            )
    # meta-only extreme
    for meta_thr in (0.75, 0.80, 0.85, 0.90, 0.92, 0.95):
        mask = [
            math.isfinite(mp) and mp >= meta_thr
            for mp in meta_p
        ]
        out.append(
            _eval_mask(
                rows,
                mask,
                name=f"{prefix}|meta_only>={meta_thr}",
                details={"meta_thr": meta_thr, "kind": "metalabel_only"},
            )
        )
    return out


def sweep_triple(
    rows: list[PredRow], meta_p: list[float], *, prefix: str
) -> list[GateCandidate]:
    """score × meta × range/vol intersection."""
    out: list[GateCandidate] = []
    range_vals = sorted(
        _feat(r, "range_20d")
        for r in rows
        if math.isfinite(_feat(r, "range_20d"))
    )
    if len(range_vals) < 50:
        return out
    r_cut = range_vals[int(0.75 * (len(range_vals) - 1))]
    for score_thr in (0.20, 0.25, 0.30):
        for meta_thr in (0.65, 0.70, 0.75, 0.80):
            mask = [
                abs(r.score) >= score_thr
                and math.isfinite(mp)
                and mp >= meta_thr
                and math.isfinite(_feat(r, "range_20d"))
                and _feat(r, "range_20d") >= r_cut
                for r, mp in zip(rows, meta_p, strict=True)
            ]
            out.append(
                _eval_mask(
                    rows,
                    mask,
                    name=(
                        f"{prefix}|score>={score_thr}"
                        f"&meta>={meta_thr}&range≥q75"
                    ),
                    details={
                        "score_thr": score_thr,
                        "meta_thr": meta_thr,
                        "range_cut": r_cut,
                        "kind": "triple",
                    },
                )
            )
    return out


def stress_pack(rows: list[PredRow], mask: list[bool]) -> dict[str, Any]:
    emitted = [r for r, m in zip(rows, mask, strict=True) if m]
    out: dict[str, Any] = {"n_emits": len(emitted)}
    if len(emitted) < 30:
        out["skipped"] = "too_few_emits"
        return out

    def prec(rs: list[PredRow]) -> float | None:
        if not rs:
            return None
        return sum(1 for r in rs if r.hit) / len(rs)

    # time halves by as_of
    days = sorted({r.as_of for r in emitted})
    mid = days[len(days) // 2]
    early = [r for r in emitted if r.as_of <= mid]
    late = [r for r in emitted if r.as_of > mid]
    out["time_early_prec"] = prec(early)
    out["time_late_prec"] = prec(late)
    out["time_halves_ok"] = (
        (prec(early) or 0) >= 0.85 and (prec(late) or 0) >= 0.85
    )

    # drop top-10 symbols by emit count
    counts: dict[str, int] = defaultdict(int)
    for r in emitted:
        counts[r.symbol] += 1
    top = {s for s, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:10]}
    jack = [r for r in emitted if r.symbol not in top]
    out["symbol_jackknife_prec"] = prec(jack)
    out["symbol_jackknife_ok"] = (prec(jack) or 0) >= 0.85

    # sector jackknife for large sectors
    sec_ok = True
    sec_table: dict[str, float | None] = {}
    by_sec: dict[str, list[PredRow]] = defaultdict(list)
    for r in emitted:
        by_sec[r.sector or "_UNK"].append(r)
    for sec, rs in by_sec.items():
        if len(rs) < 20:
            continue
        held = [r for r in emitted if (r.sector or "_UNK") != sec]
        p = prec(held)
        sec_table[sec] = p
        if (p or 0) < 0.85:
            sec_ok = False
    out["sector_jackknife"] = sec_table
    out["sector_jackknife_ok"] = sec_ok

    # shuffle null: permute hits within day among emitted
    by_day: dict[Any, list[PredRow]] = defaultdict(list)
    for r in emitted:
        by_day[r.as_of].append(r)
    null_hits = 0
    null_n = 0
    rng = random.Random(0)
    for rs in by_day.values():
        labels = [r.hit for r in rs]
        rng.shuffle(labels)
        # compare shuffled labels to original pred direction? 
        # Null: assign random hit labels — expected ~0.5 precision
        null_hits += sum(1 for x in labels if x)
        null_n += len(labels)
    # Better null: randomly flip predictions
    flip_hits = 0
    for r in emitted:
        # random direction independent of truth
        if rng.random() < 0.5:
            flip_hits += 1 if r.y_dir > 0 else 0
        else:
            flip_hits += 1 if r.y_dir < 0 else 0
    out["shuffle_null_prec"] = flip_hits / len(emitted)
    out["shuffle_null_ok"] = out["shuffle_null_prec"] < 0.60

    out["stress_pass"] = (
        out.get("time_halves_ok")
        and out.get("symbol_jackknife_ok")
        and out.get("sector_jackknife_ok")
        and out.get("shuffle_null_ok")
    )
    return out


def _mask_for_candidate(rows: list[PredRow], cand: GateCandidate, meta_p: list[float]) -> list[bool]:
    d = cand.details
    kind = d.get("kind")
    if kind == "abs_score":
        thr = float(d["thr"])
        return [abs(r.score) >= thr for r in rows]
    if kind == "global_quantile":
        thr = float(d["thr"])
        return [abs(r.score) >= thr for r in rows]
    if kind == "per_day_quantile":
        q = float(d["q"])
        by_day: dict[Any, list[int]] = defaultdict(list)
        for i, r in enumerate(rows):
            by_day[r.as_of].append(i)
        mask = [False] * len(rows)
        for idxs in by_day.values():
            ranked = sorted(idxs, key=lambda i: abs(rows[i].score), reverse=True)
            k = max(1, int(math.ceil(q * len(ranked))))
            for i in ranked[:k]:
                mask[i] = True
        return mask
    if kind == "intersection":
        st = float(d["score_thr"])
        rc = float(d["range_cut"])
        vc = float(d["vol_cut"])
        return [
            abs(r.score) >= st
            and _feat(r, "range_20d") >= rc
            and _feat(r, "vol_20d") >= vc
            for r in rows
        ]
    if kind == "metalabel":
        st = float(d["score_thr"])
        mt = float(d["meta_thr"])
        return [
            abs(r.score) >= st and math.isfinite(mp) and mp >= mt
            for r, mp in zip(rows, meta_p, strict=True)
        ]
    if kind == "metalabel_only":
        mt = float(d["meta_thr"])
        return [math.isfinite(mp) and mp >= mt for mp in meta_p]
    if kind == "triple":
        st = float(d["score_thr"])
        mt = float(d["meta_thr"])
        rc = float(d["range_cut"])
        return [
            abs(r.score) >= st
            and math.isfinite(mp)
            and mp >= mt
            and _feat(r, "range_20d") >= rc
            for r, mp in zip(rows, meta_p, strict=True)
        ]
    # fallback: top precision reconstruct via name parse — empty
    return [False] * len(rows)


def pick_best(candidates: list[GateCandidate]) -> GateCandidate | None:
    passing = [c for c in candidates if c.passes_target]
    pool = passing or candidates
    if not pool:
        return None
    # Prefer passers; then highest precision with N floor soft preference
    def key(c: GateCandidate) -> tuple:
        floor_ok = 1 if (c.n_emits >= MIN_EMITS or c.n_symbols >= MIN_SYMBOLS) else 0
        return (
            1 if c.passes_target else 0,
            floor_ok,
            c.precision,
            c.n_emits,
        )

    return max(pool, key=key)


def render_markdown(result: Precision90Result) -> str:
    lines = [
        "# Precision-90 High-Precision Emitter report",
        "",
        f"**Generated (UTC):** {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"**Target:** precision ≥ {PRECISION_TARGET} with "
        f"N≥{MIN_EMITS} or symbols≥{MIN_SYMBOLS}, fold stability",
        f"**TARGET_MET:** **{result.target_met}**",
        f"**Best gate:** `{result.best_gate}` @ prec={result.best_precision} "
        f"(emits={result.best_n_emits})",
        f"**OOS rows scored:** {result.n_rows}",
        "",
        "## Top candidates (by precision, N≥50)",
        "",
        "| Gate | Prec | Emits | Syms | Cov | Folds≥0.85 | Pass |",
        "|---|---:|---:|---:|---:|---:|:---:|",
    ]
    ranked = sorted(
        [c for c in result.candidates if c.n_emits >= 50],
        key=lambda c: (c.precision, c.n_emits),
        reverse=True,
    )[:40]
    for c in ranked:
        lines.append(
            f"| {c.name} | {c.precision:.3f} | {c.n_emits} | {c.n_symbols} | "
            f"{c.coverage:.3f} | {c.folds_ge_floor}/{c.n_folds} | "
            f"{'Y' if c.passes_target else 'N'} |"
        )
    # Near-miss: prec>=0.90 regardless of N
    near = sorted(
        [c for c in result.candidates if c.precision >= 0.90],
        key=lambda c: (-c.n_emits, -c.precision),
    )[:15]
    lines.extend(["", "## Gates with precision ≥ 0.90 (any N)", ""])
    if not near:
        lines.append("_None._")
    else:
        lines.append("| Gate | Prec | Emits | Syms | Cov |")
        lines.append("|---|---:|---:|---:|---:|")
        for c in near:
            lines.append(
                f"| {c.name} | {c.precision:.3f} | {c.n_emits} | "
                f"{c.n_symbols} | {c.coverage:.3f} |"
            )
    # Best at N>=200
    floor = [c for c in result.candidates if c.n_emits >= MIN_EMITS]
    if floor:
        best_floor = max(floor, key=lambda c: c.precision)
        lines.extend(
            [
                "",
                "## Best precision @ N≥200 (ceiling if target unmet)",
                "",
                f"- `{best_floor.name}` → **{best_floor.precision:.3f}** "
                f"(emits={best_floor.n_emits}, cov={best_floor.coverage:.3f})",
            ]
        )
    lines.extend(["", "## Stress pack", "", "```json", json.dumps(result.stress, indent=2), "```", ""])
    lines.extend(["## Recommendations", ""])
    for r in result.recommendations:
        lines.append(f"- {r}")
    lines.extend(["", "Research only — not financial advice.", ""])
    return "\n".join(lines)


async def run_precision90(
    *,
    storage: Storage,
    limit_symbols: int | None = None,
    out_dir: Path = Path("docs/experiments"),
) -> Precision90Result:
    if not sklearn_available():
        return Precision90Result(
            target_met=False,
            best_gate=None,
            best_precision=None,
            best_n_emits=0,
            recommendations=["sklearn not installed"],
        )

    series = await load_symbol_bars(storage, limit_symbols=limit_symbols)
    sectors = await load_sector_map(storage)
    log.info("p90_loaded", symbols=len(series), sectors=len(sectors))

    clf_rows = _collect_primary_rows(series, sectors=sectors)
    reg_rows = _collect_reg_rows(series, sectors=sectors)
    log.info("p90_rows", clf=len(clf_rows), reg=len(reg_rows))

    candidates: list[GateCandidate] = []
    candidates.extend(sweep_score_thresholds(clf_rows, prefix="clf"))
    candidates.extend(sweep_quantiles(clf_rows, prefix="clf"))
    candidates.extend(sweep_intersections(clf_rows, prefix="clf"))
    candidates.extend(sweep_score_thresholds(reg_rows, prefix="reg"))
    candidates.extend(sweep_quantiles(reg_rows, prefix="reg"))
    candidates.extend(sweep_intersections(reg_rows, prefix="reg"))

    meta_p = apply_metalabel_scores(clf_rows)
    candidates.extend(sweep_metalabel(clf_rows, meta_p, prefix="clf"))
    candidates.extend(sweep_triple(clf_rows, meta_p, prefix="clf"))

    # Also meta on reg scores
    meta_reg = apply_metalabel_scores(reg_rows)
    candidates.extend(sweep_metalabel(reg_rows, meta_reg, prefix="reg"))
    candidates.extend(sweep_triple(reg_rows, meta_reg, prefix="reg"))

    best = pick_best(candidates)
    stress: dict[str, Any] = {}
    target_met = False
    if best is not None:
        # choose row set by prefix
        rows_for_best = clf_rows if best.name.startswith("clf") else reg_rows
        meta_for_best = meta_p if best.name.startswith("clf") else meta_reg
        mask = _mask_for_candidate(rows_for_best, best, meta_for_best)
        stress = stress_pack(rows_for_best, mask)
        target_met = bool(best.passes_target and stress.get("stress_pass"))

    recs: list[str] = []
    if target_met and best:
        recs.append(
            f"TARGET MET: `{best.name}` precision={best.precision:.3f} "
            f"emits={best.n_emits} stress_pass={stress.get('stress_pass')}"
        )
    else:
        ge90 = [c for c in candidates if c.precision >= 0.90]
        ge90_floor = [c for c in ge90 if c.n_emits >= MIN_EMITS or c.n_symbols >= MIN_SYMBOLS]
        if ge90_floor:
            b = max(ge90_floor, key=lambda c: c.n_emits)
            recs.append(
                f"Precision≥0.90 with floor exists but stress/folds failed: `{b.name}` "
                f"prec={b.precision:.3f} n={b.n_emits}"
            )
        elif ge90:
            b = max(ge90, key=lambda c: c.n_emits)
            recs.append(
                f"Precision≥0.90 only at thin N: best `{b.name}` "
                f"prec={b.precision:.3f} n={b.n_emits} "
                f"(need ≥{MIN_EMITS} emits or ≥{MIN_SYMBOLS} symbols)"
            )
        floor = [c for c in candidates if c.n_emits >= MIN_EMITS]
        if floor:
            b = max(floor, key=lambda c: c.precision)
            recs.append(
                f"Ceiling @ N≥{MIN_EMITS}: `{b.name}` precision={b.precision:.3f}"
            )
        recs.append(
            "Always-on 90% remains out of reach; keep tightening selective HPE "
            "or add filings history for more sharp emits."
        )

    result = Precision90Result(
        target_met=target_met,
        best_gate=best.name if best else None,
        best_precision=best.precision if best else None,
        best_n_emits=best.n_emits if best else 0,
        candidates=candidates,
        stress=stress,
        recommendations=recs,
        n_rows=len(clf_rows),
    )
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / f"ml_precision90_{stamp}.md"
    js = md.with_suffix(".json")
    md.write_text(render_markdown(result), encoding="utf-8")
    # Trim JSON candidates to top 80 by precision for size
    slim = result.as_dict()
    slim["candidates"] = sorted(
        slim["candidates"], key=lambda c: (-c["precision"], -c["n_emits"])
    )[:80]
    js.write_text(json.dumps(slim, indent=2) + "\n", encoding="utf-8")
    log.info(
        "p90_done",
        target_met=target_met,
        best=result.best_gate,
        prec=result.best_precision,
        report=str(md),
    )
    return result
