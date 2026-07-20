"""Always-on accuracy scoreboard (purged mean per-symbol hit)."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from koel.logging_setup import get_logger
from koel.ml import sklearn_available
from koel.ml.dataset import Sample, build_samples, load_symbol_bars
from koel.ml.diagnose import PredRow, analyze_rows
from koel.ml.harden import _demean_by_day, _purge_train
from koel.ml.iterate import (
    _enrich_cross_section,
    _predict_lmt_bagged,
    _rows_from_scores,
)
from koel.ml.walkforward import _unique_sorted_dates
from koel.storage import Storage

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
    async with storage._pool.connection() as conn, conn.cursor() as cur:
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
    async with storage._pool.connection() as conn, conn.cursor() as cur:
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
    """Append disc/notice intensity features (leakage-safe, as_of ≤ published)."""
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
        d1 = d7 = d30 = fin30 = 0.0
        days_since = 120.0  # cap
        start1 = s.as_of - timedelta(days=1)
        start7 = s.as_of - timedelta(days=7)
        start30 = s.as_of - timedelta(days=30)
        last_before: date | None = None
        for d, cat in disc:
            if d > s.as_of:
                break
            last_before = d
            if d >= start30:
                d30 += 1.0
                if _is_financial_category(cat):
                    fin30 += 1.0
            if d >= start7:
                d7 += 1.0
            if d >= start1:
                d1 += 1.0
        if last_before is not None:
            days_since = float(min(120, (s.as_of - last_before).days))
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
                x=tuple(s.x) + (d1, d7, d30, fin30, n30, days_since),
                y_ret=s.y_ret,
                y_dir=s.y_dir,
                horizon=s.horizon,
            )
        )
    return out


def enrich_samples_with_sector_rs(
    samples: list[Sample],
    sector_by_symbol: dict[str, str],
) -> list[Sample]:
    """Append sector_rs_5d / sector_rs_20d from within-day peer means."""
    from koel.ml.features import FEATURE_NAMES

    i5 = FEATURE_NAMES.index("ret_5d")
    i20 = FEATURE_NAMES.index("ret_20d")

    by_day: dict[date, list[Sample]] = {}
    for s in samples:
        by_day.setdefault(s.as_of, []).append(s)

    out: list[Sample] = []
    for day_samples in by_day.values():
        sec_rets: dict[str, list[tuple[float, float]]] = {}
        for s in day_samples:
            sec = sector_by_symbol.get(s.symbol)
            if not sec:
                continue
            r5, r20 = s.x[i5], s.x[i20]
            if math.isfinite(r5) and math.isfinite(r20):
                sec_rets.setdefault(sec, []).append((r5, r20))
        sec_mean: dict[str, tuple[float, float]] = {}
        for sec, pairs in sec_rets.items():
            if len(pairs) < 2:
                continue
            m5 = sum(p[0] for p in pairs) / len(pairs)
            m20 = sum(p[1] for p in pairs) / len(pairs)
            sec_mean[sec] = (m5, m20)
        for s in day_samples:
            rs5 = rs20 = float("nan")
            sec = sector_by_symbol.get(s.symbol)
            if sec and sec in sec_mean:
                m5, m20 = sec_mean[sec]
                r5, r20 = s.x[i5], s.x[i20]
                if math.isfinite(r5) and math.isfinite(r20):
                    rs5 = r5 - m5
                    rs20 = r20 - m20
            out.append(
                Sample(
                    symbol=s.symbol,
                    as_of=s.as_of,
                    x=tuple(s.x) + (rs5, rs20),
                    y_ret=s.y_ret,
                    y_dir=s.y_dir,
                    horizon=s.horizon,
                )
            )
    return out


def _walk_lmt_bagged(
    samples: list[Sample],
    *,
    train_window_days: int | None = None,
) -> list[PredRow]:
    """Purged walk-forward. If ``train_window_days`` set, use rolling train."""
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
        if train_window_days is not None and train_window_days > 0:
            # Keep only the last N unique train session dates
            train_dates = sorted({s.as_of for s in train})
            if len(train_dates) > train_window_days:
                keep = set(train_dates[-train_window_days:])
                train = [s for s in train if s.as_of in keep]
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


def enrich_samples_with_market_summary(
    samples: list[Sample],
    rows: list[dict[str, Any]],
) -> list[Sample]:
    """Append market turnover / foreign-flow regime features (B-002).

    Features (as-of leakage-safe using same-day or prior session):
    - log1p(market_turnover)
    - foreign_net / turnover
    - foreign_buy_share
    - turnover_z_20 (vs trailing 20 sessions)
    - foreign_net_z_20
    """
    by_date: dict[date, dict[str, Any]] = {}
    for r in rows:
        d = r.get("trade_date")
        if isinstance(d, date):
            by_date[d] = r
    ordered = sorted(by_date)
    if not ordered:
        return samples

    turnovers: list[float] = []
    nets: list[float] = []
    feat_by_date: dict[date, tuple[float, float, float, float, float]] = {}
    for d in ordered:
        r = by_date[d]
        to = r.get("market_turnover")
        fn = r.get("foreign_net")
        fp = r.get("equity_foreign_purchase")
        fs = r.get("equity_foreign_sales")
        to_f = (
            float(to)
            if isinstance(to, int | float) and math.isfinite(float(to))
            else float("nan")
        )
        fn_f = (
            float(fn)
            if isinstance(fn, int | float) and math.isfinite(float(fn))
            else float("nan")
        )
        turnovers.append(to_f if math.isfinite(to_f) else float("nan"))
        nets.append(fn_f if math.isfinite(fn_f) else float("nan"))

        log_to = math.log1p(to_f) if math.isfinite(to_f) and to_f >= 0 else float("nan")
        ratio = (
            fn_f / to_f
            if math.isfinite(fn_f) and math.isfinite(to_f) and to_f > 0
            else float("nan")
        )
        buy_share = float("nan")
        if (
            isinstance(fp, int | float)
            and isinstance(fs, int | float)
            and math.isfinite(float(fp))
            and math.isfinite(float(fs))
        ):
            denom = float(fp) + float(fs)
            if denom > 0:
                buy_share = float(fp) / denom

        def _z(series: list[float]) -> float:
            window = [x for x in series[-20:] if math.isfinite(x)]
            if len(window) < 5:
                return float("nan")
            mu = sum(window) / len(window)
            var = sum((x - mu) ** 2 for x in window) / len(window)
            if var <= 0:
                return 0.0
            last = series[-1]
            if not math.isfinite(last):
                return float("nan")
            return (last - mu) / math.sqrt(var)

        feat_by_date[d] = (log_to, ratio, buy_share, _z(turnovers), _z(nets))

    out: list[Sample] = []
    for s in samples:
        # use as_of session if present else prior
        d = s.as_of if s.as_of in feat_by_date else None
        if d is None:
            prior = [x for x in ordered if x <= s.as_of]
            d = prior[-1] if prior else None
        extras = feat_by_date.get(d, (float("nan"),) * 5) if d else (float("nan"),) * 5
        out.append(
            Sample(
                symbol=s.symbol,
                as_of=s.as_of,
                x=tuple(s.x) + extras,
                y_ret=s.y_ret,
                y_dir=s.y_dir,
                horizon=s.horizon,
            )
        )
    return out


def enrich_samples_with_interactions(samples: list[Sample]) -> list[Sample]:
    """Append filing_recent × range_20d and ret_5d × vol_20d (B-007).

    Expects financial-filing enrichment already appended so the last feature
    before extras is ``q_recent`` when rich filings are present; falls back to
    using days_since proxies from the trailing extras when layout is unknown.
    Always uses base ``FEATURE_NAMES`` indices for path features.
    """
    from koel.ml.features import FEATURE_NAMES

    i_range = FEATURE_NAMES.index("range_20d")
    i_ret5 = FEATURE_NAMES.index("ret_5d")
    i_vol = FEATURE_NAMES.index("vol_20d")
    out: list[Sample] = []
    for s in samples:
        x = list(s.x)
        r20 = x[i_range] if i_range < len(x) else float("nan")
        ret5 = x[i_ret5] if i_ret5 < len(x) else float("nan")
        vol = x[i_vol] if i_vol < len(x) else float("nan")
        # Heuristic: q_recent flag often sits near end of financial extras.
        # Prefer explicit 0/1 flag in trailing features; else use 0.
        q_recent = 0.0
        for v in reversed(x[len(FEATURE_NAMES) :]):
            if v in (0.0, 1.0):
                q_recent = float(v)
                break
        inter_fr = (
            q_recent * r20
            if math.isfinite(r20)
            else float("nan")
        )
        inter_rv = (
            ret5 * vol
            if math.isfinite(ret5) and math.isfinite(vol)
            else float("nan")
        )
        out.append(
            Sample(
                symbol=s.symbol,
                as_of=s.as_of,
                x=tuple(x) + (inter_fr, inter_rv),
                y_ret=s.y_ret,
                y_dir=s.y_dir,
                horizon=s.horizon,
            )
        )
    return out


def _window_ret(values: list[float], n: int) -> float:
    if len(values) <= n:
        return float("nan")
    a, b = values[-(n + 1)], values[-1]
    if a == 0 or not math.isfinite(a) or not math.isfinite(b):
        return float("nan")
    return (b / a) - 1.0


def enrich_samples_with_aspi(
    samples: list[Sample],
    aspi: list[tuple[date, float, float | None]],
) -> list[Sample]:
    """Append aspi_ret_1/5/20, aspi_vol_20, stock_minus_aspi_5 (using ret_5d)."""
    from koel.ml.features import FEATURE_NAMES

    i5 = FEATURE_NAMES.index("ret_5d")
    by_date = {d: v for d, v, _pc in aspi}
    ordered_dates = sorted(by_date)
    # prefix closes for each as_of
    out: list[Sample] = []
    for s in samples:
        # closes up to as_of
        closes = [by_date[d] for d in ordered_dates if d <= s.as_of]
        if len(closes) < 5:
            extras = (float("nan"),) * 5
        else:
            r1 = _window_ret(closes, 1)
            r5 = _window_ret(closes, 5)
            r20 = _window_ret(closes, 20)
            rets = []
            for i in range(1, min(21, len(closes))):
                prev, cur = closes[-i - 1], closes[-i]
                if prev and math.isfinite(prev) and math.isfinite(cur) and prev != 0:
                    rets.append((cur / prev) - 1.0)
            vol = float("nan")
            if len(rets) >= 5:
                mean = sum(rets) / len(rets)
                var = sum((x - mean) ** 2 for x in rets) / len(rets)
                vol = math.sqrt(var)
            stock_r5 = s.x[i5] if i5 < len(s.x) else float("nan")
            gap = (
                stock_r5 - r5
                if math.isfinite(stock_r5) and math.isfinite(r5)
                else float("nan")
            )
            extras = (r1, r5, r20, vol, gap)
        out.append(
            Sample(
                symbol=s.symbol,
                as_of=s.as_of,
                x=tuple(s.x) + extras,
                y_ret=s.y_ret,
                y_dir=s.y_dir,
                horizon=s.horizon,
            )
        )
    return out


def enrich_samples_with_financial_filings(
    samples: list[Sample],
    filings: list[tuple[str, date, str]],
    *,
    rich: bool = True,
) -> list[Sample]:
    """Append quarterly/annual filing-date features (leakage-safe).

    ``filings`` rows: (symbol, filing_date, kind) kind in annual/quarterly/other.
    Rich mode (default): q90/q365/a365, days since Q/A, q_recent≤45d flag.
    """
    by_sym: dict[str, list[tuple[date, str]]] = {}
    for sym, d, kind in filings:
        by_sym.setdefault(sym, []).append((d, kind))
    for sym in by_sym:
        by_sym[sym].sort(key=lambda t: t[0])

    out: list[Sample] = []
    for s in samples:
        rows = by_sym.get(s.symbol, [])
        start90 = s.as_of - timedelta(days=90)
        start365 = s.as_of - timedelta(days=365)
        q90 = q365 = a365 = 0.0
        last_q: date | None = None
        last_a: date | None = None
        for d, kind in rows:
            if d > s.as_of:
                break
            if kind == "quarterly":
                last_q = d
                if d >= start90:
                    q90 += 1.0
                if d >= start365:
                    q365 += 1.0
            elif kind == "annual":
                last_a = d
                if d >= start365:
                    a365 += 1.0
        days_q = (
            float(min(400, (s.as_of - last_q).days)) if last_q is not None else 400.0
        )
        if rich:
            days_a = (
                float(min(800, (s.as_of - last_a).days))
                if last_a is not None
                else 800.0
            )
            q_recent = 1.0 if days_q <= 45 else 0.0
            extras = (q90, q365, a365, days_q, days_a, q_recent)
        else:
            extras = (q365, a365, days_q)
        out.append(
            Sample(
                symbol=s.symbol,
                as_of=s.as_of,
                x=tuple(s.x) + extras,
                y_ret=s.y_ret,
                y_dir=s.y_dir,
                horizon=s.horizon,
            )
        )
    return out


async def load_aspi_series(cse: Any) -> list[tuple[date, float, float | None]]:
    return await cse.fetch_index_chart(period=5)


async def load_yoy_events(
    storage: Storage,
) -> list[tuple[str, date, float | None, float | None, float | None]]:
    """(symbol, fiscal_period_end, eps_yoy, rev_yoy, profit_yoy) ascending."""
    out: list[tuple[str, date, float | None, float | None, float | None]] = []
    async with storage._pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT
                    fm.symbol,
                    fm.fiscal_period_end,
                    fc.eps_delta_pct,
                    fc.revenue_delta_pct,
                    fc.profit_delta_pct
                FROM filing_metrics fm
                JOIN filing_comparisons fc
                  ON fc.filing_metrics_id = fm.id
                WHERE fm.extract_ok = TRUE
                  AND fm.fiscal_period_end IS NOT NULL
                  AND fc.match_quality IN ('exact_yoy', 'approx_yoy')
                ORDER BY fm.symbol, fm.fiscal_period_end
                """
        )
        for row in await cur.fetchall():
            d = dict(row)
            sym = str(d["symbol"]).strip().upper()
            period = d["fiscal_period_end"]
            if hasattr(period, "isoformat") and not isinstance(period, date):
                # date already
                pass
            if not isinstance(period, date):
                continue

            row = d

            def _f(key: str, src: dict[str, Any] = row) -> float | None:
                val = src.get(key)
                if isinstance(val, bool) or not isinstance(val, int | float):
                    return None
                if not math.isfinite(float(val)):
                    return None
                return float(val)

            out.append(
                (
                    sym,
                    period,
                    _f("eps_delta_pct"),
                    _f("revenue_delta_pct"),
                    _f("profit_delta_pct"),
                )
            )
    return out


def enrich_samples_with_yoy(
    samples: list[Sample],
    yoy_events: list[tuple[str, date, float | None, float | None, float | None]],
) -> list[Sample]:
    """Append latest YoY eps/rev/profit as of sample date + days since period end."""
    by_sym: dict[
        str, list[tuple[date, float | None, float | None, float | None]]
    ] = {}
    for sym, period, eps, rev, profit in yoy_events:
        by_sym.setdefault(sym, []).append((period, eps, rev, profit))

    out: list[Sample] = []
    for s in samples:
        rows = by_sym.get(s.symbol, [])
        eps = rev = profit = float("nan")
        days = 400.0
        # last row with period <= as_of
        chosen = None
        for period, e, r, p in rows:
            if period <= s.as_of:
                chosen = (period, e, r, p)
            else:
                break
        if chosen is not None:
            period, e, r, p = chosen
            days = float(min(800, (s.as_of - period).days))
            eps = float(e) if e is not None else float("nan")
            rev = float(r) if r is not None else float("nan")
            profit = float(p) if p is not None else float("nan")
        out.append(
            Sample(
                symbol=s.symbol,
                as_of=s.as_of,
                x=tuple(s.x) + (eps, rev, profit, days),
                y_ret=s.y_ret,
                y_dir=s.y_dir,
                horizon=s.horizon,
            )
        )
    return out


async def load_financial_filing_dates(
    cse: Any,
    symbols: list[str],
    *,
    sleep_seconds: float = 0.2,
    limit: int | None = None,
) -> list[tuple[str, date, str]]:
    import asyncio

    syms = symbols
    if limit is not None and limit > 0:
        syms = symbols[:limit]
    out: list[tuple[str, date, str]] = []
    for i, sym in enumerate(syms):
        try:
            docs = await cse.fetch_company_financial_docs(sym)
        except Exception as exc:
            log.warning("financials_fetch_failed", symbol=sym, error=str(exc))
            continue
        for kind, d, _pdf in docs:
            out.append((sym, d, kind))
        if sleep_seconds > 0 and i + 1 < len(syms):
            await asyncio.sleep(sleep_seconds)
    return out


async def run_always_on(
    *,
    storage: Storage,
    lever: str = "baseline_cs_lmt_bag",
    use_events: bool = False,
    use_sector_rs: bool = False,
    use_aspi: bool = False,
    use_financials: bool = False,
    use_yoy: bool = False,
    cse: Any | None = None,
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
        "sector_rs": use_sector_rs,
        "aspi": use_aspi,
        "financials": use_financials,
        "yoy": use_yoy,
    }
    if use_sector_rs:
        from koel.ml.diagnose import load_sector_map

        sectors = await load_sector_map(storage)
        extras["sectors_mapped"] = len(sectors)
        samples = enrich_samples_with_sector_rs(samples, sectors)
    if use_aspi:
        aspi: list[tuple[date, float, float | None]] = []
        # Prefer persisted ASPI daily_bars (aspi-backfill); else live chartData.
        stored = await storage.list_daily_bars("ASPI")
        if stored:
            aspi = [(b.trade_date, b.price, None) for b in stored]
            extras["aspi_source"] = "daily_bars"
        elif cse is not None:
            aspi = await load_aspi_series(cse)
            extras["aspi_source"] = "chartData"
        else:
            raise ValueError("use_aspi requires cse client or ASPI daily_bars")
        extras["aspi_points"] = len(aspi)
        samples = enrich_samples_with_aspi(samples, aspi)
    if use_financials:
        cache = Path("data/financial_filings_cache.json")
        filings: list[tuple[str, date, str]]
        if cache.is_file():
            import json as _json

            raw = _json.loads(cache.read_text(encoding="utf-8"))
            filings = [
                (str(a), date.fromisoformat(str(b)), str(c)) for a, b, c in raw
            ]
            extras["financial_filings_source"] = "cache"
        else:
            if cse is None:
                raise ValueError("use_financials requires cse client or cache")
            filings = await load_financial_filing_dates(
                cse, sorted(series.keys()), sleep_seconds=0.2
            )
            extras["financial_filings_source"] = "api"
        extras["financial_filing_rows"] = len(filings)
        samples = enrich_samples_with_financial_filings(samples, filings)
    if use_yoy:
        yoy_events = await load_yoy_events(storage)
        extras["yoy_events"] = len(yoy_events)
        samples = enrich_samples_with_yoy(samples, yoy_events)
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
            "+".join(
                p
                for p, on in (
                    ("path+CS", True),
                    ("sector_rs", use_sector_rs),
                    ("aspi", use_aspi),
                    ("financials", use_financials),
                    ("yoy", use_yoy),
                    ("events", use_events),
                )
                if on
            )
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
