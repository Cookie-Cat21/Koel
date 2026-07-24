"""Prospective live shadow forecasts written only to ``forecast_outcomes``."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from koel.adapters.cse import CSEClient
from koel.domain import DailyBar, PriceSnapshot
from koel.ml.cost_engineering import (
    PERSIST_EXIT_10_TOP_BOTTOM_05,
    BookState,
    PortfolioVariant,
    book_state_from_signed_scores,
    construct_session_book,
)
from koel.ml.dataset import Sample, build_samples
from koel.ml.distributed_worker import _fit_predict_average
from koel.ml.features import path_features
from koel.ml.harden import _demean_by_day
from koel.ml.iterate import _enrich_cross_section
from koel.ml.outcomes import OutcomeEmit, emit_shadow_outcome_rows
from koel.ml.research_features import (
    build_research_bar_metadata,
    enrich_market_context,
    enrich_research_quality,
)
from koel.ml.research_fundamentals import enrich_fundamentals
from koel.ml.snapshot import (
    LoadedSnapshot,
    composite_snapshot_sha,
    load_bar_snapshot,
)
from koel.storage import Storage

COLOMBO = ZoneInfo("Asia/Colombo")
POLICY_MODELS = {
    "shadow_policy_abs_xgb2_v1": "xgb_two_stage",
    "shadow_policy_abs_hgb2_v1": "hgb_two_stage",
    "shadow_policy_abs_xgb_domain_v1": "xgb_domain",
}
POLICY_SELECTIVE = "shadow_policy_abs_xgb2_p005_v1"
POLICY_PRESSURE = "shadow_policy_abs_xgb2_pressure_v1"
POLICY_RANK_DE_PERSIST = "shadow_policy_rank_de_persist_v1"
# Point-in-time historical replay — research/cost evidence only.
# Does NOT count toward E7 (prospective non-partial sessions).
POLICY_RANK_DE_PERSIST_HIST = "shadow_policy_rank_de_persist_hist_v1"
POLICY_RANK_DE_MODEL = "double_ensemble_native"
POLICY_RANK_DE_VARIANT = PERSIST_EXIT_10_TOP_BOTTOM_05
POLICY_RANK_DE_H3_WEEKLY = "shadow_policy_rank_de_h3_weekly_v1"
POLICY_RANK_DE_H3_WEEKLY_VARIANT = PortfolioVariant(
    "weekly_5_sessions_top_bottom_05",
    fraction=0.05,
    rebalance_every=5,
)


@dataclass(frozen=True, slots=True)
class LiveShadowResult:
    issued_at: str
    partial_session: bool
    board_rows: int
    eligible_symbols: int
    policy_emits: dict[str, int]
    selective_emits: int
    pressure_emits: int
    snapshot_sha256: str
    instance_versions: dict[str, str]


@dataclass(frozen=True, slots=True)
class PressureFactors:
    book_median: float
    book_persistence: float
    book_slope: float
    signed_volume_proxy: float


@dataclass(frozen=True, slots=True)
class WeeklyBookLedgerState:
    session_index: int
    book: BookState | None
    signed_scores: dict[str, float]


def truncate_series_as_of(
    series: dict[str, list[DailyBar]],
    *,
    as_of: date,
) -> dict[str, list[DailyBar]]:
    """Keep only bars with ``trade_date <= as_of`` (point-in-time replay)."""
    out: dict[str, list[DailyBar]] = {}
    for symbol, bars in series.items():
        kept = [bar for bar in bars if bar.trade_date <= as_of]
        if kept:
            out[symbol] = kept
    return out


def append_live_board(
    series: dict[str, list[DailyBar]],
    board: list[PriceSnapshot],
    *,
    trade_date: date,
) -> dict[str, list[DailyBar]]:
    """Return a copy with one current-session CSE bar per known symbol."""
    out = {symbol: list(bars) for symbol, bars in series.items()}
    for snapshot in board:
        symbol = snapshot.symbol.strip().upper()
        if symbol not in out or snapshot.price <= 0 or not math.isfinite(snapshot.price):
            continue
        bar = DailyBar(
            symbol=symbol,
            trade_date=trade_date,
            price=float(snapshot.price),
            high=snapshot.high,
            low=snapshot.low,
            open=snapshot.open,
            volume=snapshot.volume,
            source_period=5,
            bar_ts=snapshot.ts.astimezone(UTC),
        )
        out[symbol] = [
            existing for existing in out[symbol] if existing.trade_date != trade_date
        ] + [bar]
        out[symbol].sort(key=lambda existing: existing.trade_date)
    return out


def _latest_samples(
    *,
    series: dict[str, list[DailyBar]],
    loaded: LoadedSnapshot,
    trade_date: date,
    min_history: int,
    max_flat_fraction: float,
    horizon: int = 1,
) -> list[Sample]:
    metadata = build_research_bar_metadata(series, dataset=loaded.manifest.dataset)
    base: list[Sample] = []
    for symbol, bars in series.items():
        ordered = sorted(bars, key=lambda bar: bar.trade_date)
        if (
            len(ordered) < min_history
            or ordered[-1].trade_date != trade_date
            or metadata[(symbol, trade_date)].source != "cse"
            or metadata[(symbol, trade_date)].flat_fraction_60 > max_flat_fraction
        ):
            continue
        if len(ordered) > 1:
            previous = ordered[-2].price
            if previous <= 0 or abs((ordered[-1].price / previous) - 1.0) > 0.35:
                continue
        features = path_features(ordered)
        if features is None:
            continue
        base.append(
            Sample(
                symbol=symbol,
                as_of=trade_date,
                x=features.values,
                y_ret=0.0,
                y_dir=0.0,
                horizon=horizon,
            )
        )
    enriched = enrich_research_quality(base, metadata)
    enriched = enrich_fundamentals(enriched, loaded.fundamentals)
    enriched = enrich_market_context(enriched)
    # Feature Pack v1 is intentionally NOT applied here: existing Loop-0 policy
    # IDs must keep a frozen feature matrix. New fp policies get a new ID.
    return _enrich_cross_section(enriched)


def _training_samples(loaded: LoadedSnapshot) -> list[Sample]:
    metadata = build_research_bar_metadata(
        loaded.series,
        dataset=loaded.manifest.dataset,
    )
    samples = build_samples(
        loaded.series,
        horizon=1,
        min_history=252,
        max_abs_return=0.35,
        include_flat=True,
        price_adjustment=loaded.manifest.price_adjustment,
        corporate_actions=loaded.corporate_actions,
    )
    samples = enrich_research_quality(samples, metadata)
    samples = enrich_fundamentals(samples, loaded.fundamentals)
    samples = enrich_market_context(samples)
    return _enrich_cross_section(samples)


def _relative_training_samples(
    loaded: LoadedSnapshot,
    *,
    horizon: int = 1,
) -> list[Sample]:
    """Relative panel matching offline DE book-policy training."""
    metadata = build_research_bar_metadata(
        loaded.series,
        dataset=loaded.manifest.dataset,
    )
    samples = build_samples(
        loaded.series,
        horizon=horizon,
        min_history=252,
        max_abs_return=0.35,
        include_flat=False,
        price_adjustment=loaded.manifest.price_adjustment,
        corporate_actions=loaded.corporate_actions,
    )
    samples = _demean_by_day(samples)
    samples = enrich_research_quality(samples, metadata)
    samples = enrich_fundamentals(samples, loaded.fundamentals)
    samples = enrich_market_context(samples)
    return _enrich_cross_section(samples)


def should_rebuild_weekly_book(
    session_index: int,
    *,
    rebalance_every: int = POLICY_RANK_DE_H3_WEEKLY_VARIANT.rebalance_every,
) -> bool:
    """Return true when the zero-based live issue session starts a new weekly book."""
    if session_index < 0:
        raise ValueError("session_index must be >= 0")
    if rebalance_every < 1:
        raise ValueError("rebalance_every must be >= 1")
    return session_index % rebalance_every == 0


def carry_forward_book(book: BookState) -> BookState:
    """Re-emit the prior weekly book with unchanged weights and incremented ages."""
    return BookState(
        weights=dict(book.weights),
        holding_ages={
            symbol: book.holding_ages.get(symbol, 1) + 1
            for symbol in book.weights
        },
    )


def _parse_holding_age(regime_tag: str | None) -> int:
    if not regime_tag:
        return 1
    for part in regime_tag.split("|"):
        if part.startswith("age="):
            try:
                age = int(part.removeprefix("age="))
            except ValueError:
                return 1
            return max(1, age)
    return 1


async def load_prior_persist_book(
    storage: Storage,
    *,
    policy_id: str,
    before: date,
) -> BookState | None:
    """Rebuild prior-session book state from immutable shadow ledger rows."""
    async with storage._pool.connection() as conn:
        prior_session = await (
            await conn.execute(
                """
                SELECT MAX(issued_at) AS issued_at
                FROM forecast_outcomes
                WHERE model_id = %s
                  AND issued_at < %s
                  AND gate LIKE 'shadow%%persist%%'
                  AND COALESCE(gate, '') NOT LIKE '%%partial%%'
                """,
                (policy_id, before),
            )
        ).fetchone()
        if prior_session is None or prior_session["issued_at"] is None:
            return None
        rows = await (
            await conn.execute(
                """
                SELECT symbol, y_pred, regime_tag
                FROM forecast_outcomes
                WHERE model_id = %s
                  AND issued_at = %s
                  AND gate LIKE 'shadow%%persist%%'
                ORDER BY symbol
                """,
                (policy_id, prior_session["issued_at"]),
            )
        ).fetchall()
    if not rows:
        return None
    signed = {
        str(row["symbol"]).strip().upper(): float(row["y_pred"])
        for row in rows
        if row["y_pred"] is not None and math.isfinite(float(row["y_pred"]))
    }
    ages = {
        str(row["symbol"]).strip().upper(): _parse_holding_age(
            str(row["regime_tag"]) if row["regime_tag"] is not None else None
        )
        for row in rows
    }
    if not signed:
        return None
    return book_state_from_signed_scores(signed, previous_ages=ages)


async def load_prior_weekly_book(
    storage: Storage,
    *,
    policy_id: str,
    before: date,
) -> WeeklyBookLedgerState:
    """Load the latest non-partial weekly shadow book and its cadence index."""
    final_gate = "shadow_h3_weekly_book"
    async with storage._pool.connection() as conn:
        state = await (
            await conn.execute(
                """
                SELECT COUNT(DISTINCT issued_at) AS session_count,
                       MAX(issued_at) AS issued_at
                FROM forecast_outcomes
                WHERE model_id = %s
                  AND issued_at < %s
                  AND gate = %s
                """,
                (policy_id, before, final_gate),
            )
        ).fetchone()
        session_index = (
            int(state["session_count"])
            if state is not None and state["session_count"] is not None
            else 0
        )
        if state is None or state["issued_at"] is None:
            return WeeklyBookLedgerState(
                session_index=session_index,
                book=None,
                signed_scores={},
            )
        rows = await (
            await conn.execute(
                """
                SELECT symbol, y_pred, regime_tag
                FROM forecast_outcomes
                WHERE model_id = %s
                  AND issued_at = %s
                  AND gate = %s
                ORDER BY symbol
                """,
                (policy_id, state["issued_at"], final_gate),
            )
        ).fetchall()
    signed = {
        str(row["symbol"]).strip().upper(): float(row["y_pred"])
        for row in rows
        if row["y_pred"] is not None and math.isfinite(float(row["y_pred"]))
    }
    ages = {
        str(row["symbol"]).strip().upper(): _parse_holding_age(
            str(row["regime_tag"]) if row["regime_tag"] is not None else None
        )
        for row in rows
    }
    return WeeklyBookLedgerState(
        session_index=session_index,
        book=book_state_from_signed_scores(signed, previous_ages=ages)
        if signed
        else None,
        signed_scores=signed,
    )


def summarize_pressure_factors(
    book_rows: list[dict[str, object]],
    price_rows: list[dict[str, object]],
) -> dict[str, PressureFactors]:
    """Summarize displayed book and tick-rule cumulative-volume pressure."""
    books: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
    for row in book_rows:
        symbol = str(row["symbol"]).strip().upper()
        bids = float(row["total_bids"])
        asks = float(row["total_asks"])
        ts = row["ts"]
        denominator = bids + asks
        if (
            isinstance(ts, datetime)
            and denominator > 0
            and math.isfinite(denominator)
        ):
            books[symbol].append((ts, (bids - asks) / denominator))

    prices: dict[str, list[tuple[datetime, float, float]]] = defaultdict(list)
    for row in price_rows:
        ts = row["ts"]
        price = float(row["price"])
        volume = float(row["volume"] or 0)
        if isinstance(ts, datetime) and price > 0 and math.isfinite(price):
            prices[str(row["symbol"]).strip().upper()].append((ts, price, volume))

    out: dict[str, PressureFactors] = {}
    for symbol, observations in books.items():
        ordered_books = sorted(observations)
        imbalances = [value for _ts, value in ordered_books]
        persistence = statistics.fmean(
            1.0 if value > 0 else -1.0 if value < 0 else 0.0
            for value in imbalances
        )
        slope = imbalances[-1] - imbalances[0] if len(imbalances) > 1 else 0.0

        signed_volume = 0.0
        total_volume = 0.0
        last_sign = 0.0
        ordered_prices = sorted(prices.get(symbol, []))
        for previous, current in zip(
            ordered_prices,
            ordered_prices[1:],
            strict=False,
        ):
            _prev_ts, previous_price, previous_volume = previous
            _curr_ts, current_price, current_volume = current
            delta_volume = max(0.0, current_volume - previous_volume)
            if current_price > previous_price:
                last_sign = 1.0
            elif current_price < previous_price:
                last_sign = -1.0
            signed_volume += last_sign * delta_volume
            total_volume += delta_volume
        signed_proxy = signed_volume / total_volume if total_volume > 0 else 0.0
        out[symbol] = PressureFactors(
            book_median=statistics.median(imbalances),
            book_persistence=persistence,
            book_slope=max(-1.0, min(1.0, slope)),
            signed_volume_proxy=max(-1.0, min(1.0, signed_proxy)),
        )
    return out


async def _latest_pressure_factors(
    storage: Storage,
    *,
    lookback_minutes: int = 120,
) -> dict[str, PressureFactors]:
    async with storage._pool.connection() as conn:
        book_rows = await (
            await conn.execute(
                """
                SELECT symbol, total_bids, total_asks, ts
                FROM order_book_snapshots
                WHERE ts >= now() - (%s::text || ' minutes')::interval
                ORDER BY symbol, ts
                """,
                (str(lookback_minutes),),
            )
        ).fetchall()
        price_rows = await (
            await conn.execute(
                """
                SELECT symbol, price, volume, ts
                FROM price_snapshots
                WHERE ts >= now() - (%s::text || ' minutes')::interval
                ORDER BY symbol, ts
                """,
                (str(lookback_minutes),),
            )
        ).fetchall()
    return summarize_pressure_factors(
        [dict(row) for row in book_rows],
        [dict(row) for row in price_rows],
    )


def _confidence(score: float) -> float:
    return max(0.0, min(1.0, abs(score) * 2.0))


def policy_instance_version(
    *,
    policy_id: str,
    snapshot_sha256: str,
    issue_session: date,
    revision: str,
    live_input_sha256: str = "",
    partial: bool = False,
) -> str:
    """Immutable fitted-instance identity for one prequential issue."""
    payload = {
        "policy_id": policy_id,
        "snapshot_sha256": snapshot_sha256,
        "issue_session": issue_session.isoformat(),
        "revision": revision,
        "live_input_sha256": live_input_sha256,
        "partial": partial,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    partial_tag = "_partial" if partial else ""
    return f"{policy_id}__{issue_session.isoformat()}__{digest}{partial_tag}"


async def run_live_shadow(
    *,
    storage: Storage,
    cse: CSEClient,
    snapshot_dir: Path,
    allow_partial: bool = False,
    min_history: int = 60,
    max_flat_fraction: float = 0.40,
) -> LiveShadowResult:
    """Fit the frozen challenger and append prospective ledger rows."""
    now = datetime.now(COLOMBO)
    partial = now.time() < time(14, 35)
    if partial and not allow_partial:
        raise RuntimeError("market session is still active; refusing final shadow emit")

    loaded = load_bar_snapshot(snapshot_dir)
    board = await cse.fetch_trade_summary()
    live_series = append_live_board(loaded.series, board, trade_date=now.date())
    train = _training_samples(loaded)
    latest = _latest_samples(
        series=live_series,
        loaded=loaded,
        trade_date=now.date(),
        min_history=min_history,
        max_flat_fraction=max_flat_fraction,
    )
    if len(train) < 100 or not latest:
        raise RuntimeError("insufficient training or live feature rows")
    snapshot_sha = composite_snapshot_sha(loaded.manifest)
    revision = (
        os.environ.get("GITHUB_SHA")
        or os.environ.get("KOEL_MODEL_REVISION")
        or "local"
    )
    policy_emits: dict[str, int] = {}
    instance_versions: dict[str, str] = {}
    scores_by_policy: dict[str, dict[str, float]] = {}
    for policy_id, model in POLICY_MODELS.items():
        scores = _fit_predict_average(
            model=model,
            train=train,
            test=latest,
            seeds=(0,),
        )
        score_by_symbol = {
            sample.symbol: score
            for sample, score in zip(latest, scores, strict=True)
            if score != 0 and math.isfinite(score)
        }
        scores_by_policy[policy_id] = score_by_symbol
        instance_version = policy_instance_version(
            policy_id=policy_id,
            snapshot_sha256=snapshot_sha,
            issue_session=now.date(),
            revision=revision,
            partial=partial,
        )
        instance_versions[policy_id] = instance_version
        rows = [
            OutcomeEmit(
                model_id=policy_id,
                model_version=instance_version,
                symbol=symbol,
                issued_at=now.date(),
                horizon_days=1,
                y_pred=score,
                confidence=_confidence(score),
                gate="shadow_partial" if partial else "shadow_all",
                regime_tag=(
                    f"live_shadow|policy={policy_id}|partial={int(partial)}"
                    f"|snapshot={snapshot_sha[:12]}"
                ),
            )
            for symbol, score in sorted(score_by_symbol.items())
        ]
        policy_emits[policy_id] = await emit_shadow_outcome_rows(storage, rows)

    xgb_scores = scores_by_policy["shadow_policy_abs_xgb2_v1"]
    ranked = sorted(xgb_scores.items(), key=lambda item: abs(item[1]), reverse=True)
    selective_n = max(1, math.ceil(len(ranked) * 0.005))
    selective_version = policy_instance_version(
        policy_id=POLICY_SELECTIVE,
        snapshot_sha256=snapshot_sha,
        issue_session=now.date(),
        revision=revision,
        partial=partial,
    )
    instance_versions[POLICY_SELECTIVE] = selective_version
    selective_rows = [
        OutcomeEmit(
            model_id=POLICY_SELECTIVE,
            model_version=selective_version,
            symbol=symbol,
            issued_at=now.date(),
            horizon_days=1,
            y_pred=score,
            confidence=_confidence(score),
            gate="shadow_partial_p005" if partial else "shadow_p005",
            regime_tag=f"live_shadow|partial={int(partial)}|coverage=0.005",
        )
        for symbol, score in ranked[:selective_n]
    ]
    selective_count = await emit_shadow_outcome_rows(storage, selective_rows)

    pressure = await _latest_pressure_factors(storage)
    pressure_payload = {
        symbol: asdict(factors) for symbol, factors in sorted(pressure.items())
    }
    pressure_sha = hashlib.sha256(
        json.dumps(
            pressure_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    pressure_version = policy_instance_version(
        policy_id=POLICY_PRESSURE,
        snapshot_sha256=snapshot_sha,
        issue_session=now.date(),
        revision=revision,
        live_input_sha256=pressure_sha,
        partial=partial,
    )
    instance_versions[POLICY_PRESSURE] = pressure_version
    pressure_rows = []
    for symbol, score in sorted(xgb_scores.items()):
        factors = pressure.get(symbol)
        if factors is None:
            continue
        pressure_score = (
            score
            + 0.03 * factors.book_median
            + 0.02 * factors.book_persistence
            + 0.01 * factors.book_slope
            + 0.03 * factors.signed_volume_proxy
        )
        pressure_rows.append(
            OutcomeEmit(
                model_id=POLICY_PRESSURE,
                model_version=pressure_version,
                symbol=symbol,
                issued_at=now.date(),
                horizon_days=1,
                y_pred=pressure_score,
                confidence=_confidence(pressure_score),
                gate="shadow_partial_book" if partial else "shadow_book",
                regime_tag=(
                    f"live_shadow|partial={int(partial)}"
                    f"|book={factors.book_median:.4f}"
                    f"|persist={factors.book_persistence:.4f}"
                    f"|slope={factors.book_slope:.4f}"
                    f"|signed_vol={factors.signed_volume_proxy:.4f}"
                ),
            )
        )
    pressure_count = await emit_shadow_outcome_rows(storage, pressure_rows)

    # Loop-0 relative DE + persistence book (ledger only; never forecast_points).
    relative_train = _relative_training_samples(loaded)
    de_persist_count = 0
    if len(relative_train) >= 100:
        relative_scores = _fit_predict_average(
            model=POLICY_RANK_DE_MODEL,
            train=relative_train,
            test=latest,
            seeds=(0,),
        )
        relative_by_symbol = {
            sample.symbol: score
            for sample, score in zip(latest, relative_scores, strict=True)
            if score != 0 and math.isfinite(score)
        }
        previous_book = await load_prior_persist_book(
            storage,
            policy_id=POLICY_RANK_DE_PERSIST,
            before=now.date(),
        )
        book = construct_session_book(
            relative_by_symbol,
            variant=POLICY_RANK_DE_VARIANT,
            previous=previous_book,
        )
        de_version = policy_instance_version(
            policy_id=POLICY_RANK_DE_PERSIST,
            snapshot_sha256=snapshot_sha,
            issue_session=now.date(),
            revision=revision,
            partial=partial,
        )
        instance_versions[POLICY_RANK_DE_PERSIST] = de_version
        if book is not None and book.weights:
            de_rows: list[OutcomeEmit] = []
            for symbol, weight in sorted(book.weights.items()):
                if symbol not in relative_by_symbol:
                    continue
                raw_score = relative_by_symbol[symbol]
                # Sign follows book side (persistence may keep a name after score flips).
                y_pred = math.copysign(
                    abs(raw_score) if raw_score != 0 else abs(weight),
                    weight,
                )
                de_rows.append(
                    OutcomeEmit(
                        model_id=POLICY_RANK_DE_PERSIST,
                        model_version=de_version,
                        symbol=symbol,
                        issued_at=now.date(),
                        horizon_days=1,
                        y_pred=y_pred,
                        confidence=_confidence(raw_score),
                        gate=(
                            "shadow_partial_persist_book"
                            if partial
                            else "shadow_persist_book"
                        ),
                        regime_tag=(
                            f"live_shadow|policy={POLICY_RANK_DE_PERSIST}"
                            f"|variant={POLICY_RANK_DE_VARIANT.name}"
                            f"|side={'long' if weight > 0 else 'short'}"
                            f"|age={book.holding_ages.get(symbol, 1)}"
                            f"|w={weight:.6f}"
                            f"|raw={raw_score:.6f}"
                            f"|partial={int(partial)}"
                            f"|snapshot={snapshot_sha[:12]}"
                        ),
                    )
                )
            de_persist_count = await emit_shadow_outcome_rows(storage, de_rows)
        policy_emits[POLICY_RANK_DE_PERSIST] = de_persist_count

    # Loop-0 relative/h3 DE + weekly 5-session book (ledger only).
    weekly_prior = await load_prior_weekly_book(
        storage,
        policy_id=POLICY_RANK_DE_H3_WEEKLY,
        before=now.date(),
    )
    weekly_rebuild = (
        should_rebuild_weekly_book(weekly_prior.session_index)
        or weekly_prior.book is None
    )
    h3_weekly_count = 0
    h3_scores_by_symbol: dict[str, float] = {}
    h3_book: BookState | None = None
    if weekly_rebuild:
        h3_train = _relative_training_samples(loaded, horizon=3)
        if len(h3_train) >= 100:
            h3_latest = _latest_samples(
                series=live_series,
                loaded=loaded,
                trade_date=now.date(),
                min_history=min_history,
                max_flat_fraction=max_flat_fraction,
                horizon=3,
            )
            h3_scores = _fit_predict_average(
                model=POLICY_RANK_DE_MODEL,
                train=h3_train,
                test=h3_latest,
                seeds=(0,),
            )
            h3_scores_by_symbol = {
                sample.symbol: score
                for sample, score in zip(h3_latest, h3_scores, strict=True)
                if score != 0 and math.isfinite(score)
            }
            h3_book = construct_session_book(
                h3_scores_by_symbol,
                variant=POLICY_RANK_DE_H3_WEEKLY_VARIANT,
            )
    elif weekly_prior.book is not None:
        h3_book = carry_forward_book(weekly_prior.book)
        h3_scores_by_symbol = dict(weekly_prior.signed_scores)

    h3_version = policy_instance_version(
        policy_id=POLICY_RANK_DE_H3_WEEKLY,
        snapshot_sha256=snapshot_sha,
        issue_session=now.date(),
        revision=revision,
        partial=partial,
    )
    instance_versions[POLICY_RANK_DE_H3_WEEKLY] = h3_version
    if h3_book is not None and h3_book.weights:
        h3_rows: list[OutcomeEmit] = []
        for symbol, weight in sorted(h3_book.weights.items()):
            raw_score = h3_scores_by_symbol.get(symbol)
            if raw_score is None or not math.isfinite(raw_score):
                raw_score = weight
            y_pred = math.copysign(
                abs(raw_score) if raw_score != 0 else abs(weight),
                weight,
            )
            h3_rows.append(
                OutcomeEmit(
                    model_id=POLICY_RANK_DE_H3_WEEKLY,
                    model_version=h3_version,
                    symbol=symbol,
                    issued_at=now.date(),
                    horizon_days=3,
                    y_pred=y_pred,
                    confidence=_confidence(raw_score),
                    gate=(
                        "shadow_partial_h3_weekly_book"
                        if partial
                        else "shadow_h3_weekly_book"
                    ),
                    regime_tag=(
                        f"live_shadow|policy={POLICY_RANK_DE_H3_WEEKLY}"
                        f"|variant={POLICY_RANK_DE_H3_WEEKLY_VARIANT.name}"
                        f"|side={'long' if weight > 0 else 'short'}"
                        f"|age={h3_book.holding_ages.get(symbol, 1)}"
                        f"|w={weight:.6f}"
                        f"|raw={raw_score:.6f}"
                        f"|rebuilt={int(weekly_rebuild)}"
                        f"|session_index={weekly_prior.session_index}"
                        f"|partial={int(partial)}"
                        f"|snapshot={snapshot_sha[:12]}"
                    ),
                )
            )
        h3_weekly_count = await emit_shadow_outcome_rows(storage, h3_rows)
    policy_emits[POLICY_RANK_DE_H3_WEEKLY] = h3_weekly_count

    return LiveShadowResult(
        issued_at=now.date().isoformat(),
        partial_session=partial,
        board_rows=len(board),
        eligible_symbols=len(latest),
        policy_emits=policy_emits,
        selective_emits=selective_count,
        pressure_emits=pressure_count,
        snapshot_sha256=snapshot_sha,
        instance_versions=instance_versions,
    )


async def run_historical_de_persist_shadow(
    *,
    storage: Storage,
    snapshot_dir: Path,
    as_of: date,
    min_history: int = 60,
    max_flat_fraction: float = 0.40,
) -> LiveShadowResult:
    """Point-in-time DE-persist book emit for research (not E7 prospective).

    Uses only bars ``<= as_of`` from the snapshot (no live CSE board). Writes
    under ``POLICY_RANK_DE_PERSIST_HIST`` with gate ``shadow_hist_persist_book``.
    Never writes ``forecast_points`` / Telegram.
    """
    loaded = load_bar_snapshot(snapshot_dir)
    truncated_series = truncate_series_as_of(loaded.series, as_of=as_of)
    if not truncated_series:
        raise RuntimeError(f"no bars on/before {as_of.isoformat()}")
    # Rebuild a shallow LoadedSnapshot-compatible view for sample builders.
    loaded_as_of = LoadedSnapshot(
        manifest=loaded.manifest,
        series=truncated_series,
        fundamentals=loaded.fundamentals,
        corporate_actions=loaded.corporate_actions,
    )
    train = _relative_training_samples(loaded_as_of, horizon=1)
    latest = _latest_samples(
        series=truncated_series,
        loaded=loaded_as_of,
        trade_date=as_of,
        min_history=min_history,
        max_flat_fraction=max_flat_fraction,
        horizon=1,
    )
    if len(train) < 100 or not latest:
        raise RuntimeError(
            f"insufficient PIT rows for {as_of.isoformat()}: "
            f"train={len(train)} latest={len(latest)}"
        )
    snapshot_sha = composite_snapshot_sha(loaded.manifest)
    revision = (
        os.environ.get("GITHUB_SHA")
        or os.environ.get("KOEL_MODEL_REVISION")
        or "local"
    )
    relative_scores = _fit_predict_average(
        model=POLICY_RANK_DE_MODEL,
        train=train,
        test=latest,
        seeds=(0,),
    )
    relative_by_symbol = {
        sample.symbol: score
        for sample, score in zip(latest, relative_scores, strict=True)
        if score != 0 and math.isfinite(score)
    }
    previous_book = await load_prior_persist_book(
        storage,
        policy_id=POLICY_RANK_DE_PERSIST_HIST,
        before=as_of,
    )
    book = construct_session_book(
        relative_by_symbol,
        variant=POLICY_RANK_DE_VARIANT,
        previous=previous_book,
    )
    de_version = policy_instance_version(
        policy_id=POLICY_RANK_DE_PERSIST_HIST,
        snapshot_sha256=snapshot_sha,
        issue_session=as_of,
        revision=f"{revision}|hist",
        partial=False,
    )
    de_persist_count = 0
    if book is not None and book.weights:
        de_rows: list[OutcomeEmit] = []
        for symbol, weight in sorted(book.weights.items()):
            if symbol not in relative_by_symbol:
                continue
            raw_score = relative_by_symbol[symbol]
            y_pred = math.copysign(
                abs(raw_score) if raw_score != 0 else abs(weight),
                weight,
            )
            de_rows.append(
                OutcomeEmit(
                    model_id=POLICY_RANK_DE_PERSIST_HIST,
                    model_version=de_version,
                    symbol=symbol,
                    issued_at=as_of,
                    horizon_days=1,
                    y_pred=y_pred,
                    confidence=_confidence(raw_score),
                    gate="shadow_hist_persist_book",
                    regime_tag=(
                        f"historical_shadow|policy={POLICY_RANK_DE_PERSIST_HIST}"
                        f"|variant={POLICY_RANK_DE_VARIANT.name}"
                        f"|side={'long' if weight > 0 else 'short'}"
                        f"|age={book.holding_ages.get(symbol, 1)}"
                        f"|w={weight:.6f}"
                        f"|raw={raw_score:.6f}"
                        f"|as_of={as_of.isoformat()}"
                        f"|snapshot={snapshot_sha[:12]}"
                        f"|e7_eligible=0"
                    ),
                )
            )
        de_persist_count = await emit_shadow_outcome_rows(storage, de_rows)
    return LiveShadowResult(
        issued_at=as_of.isoformat(),
        partial_session=False,
        board_rows=0,
        eligible_symbols=len(latest),
        policy_emits={POLICY_RANK_DE_PERSIST_HIST: de_persist_count},
        selective_emits=0,
        pressure_emits=0,
        snapshot_sha256=snapshot_sha,
        instance_versions={POLICY_RANK_DE_PERSIST_HIST: de_version},
    )


async def _run(args: argparse.Namespace) -> None:
    database_url = os.environ.get("ML_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("ML_DATABASE_URL (or DATABASE_URL) is required")
    storage = Storage(database_url)
    await storage.open()
    try:
        if args.as_of is not None:
            result = await run_historical_de_persist_shadow(
                storage=storage,
                snapshot_dir=args.snapshot,
                as_of=args.as_of,
                min_history=args.min_history,
                max_flat_fraction=args.max_flat_fraction,
            )
        else:
            async with CSEClient(min_interval_seconds=0.25) as cse:
                result = await run_live_shadow(
                    storage=storage,
                    cse=cse,
                    snapshot_dir=args.snapshot,
                    allow_partial=args.allow_partial,
                    min_history=args.min_history,
                    max_flat_fraction=args.max_flat_fraction,
                )
    finally:
        await storage.close()
    print(json.dumps(asdict(result), sort_keys=True))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Emit prospective CSE shadow rows")
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--min-history", type=int, default=60)
    parser.add_argument("--max-flat-fraction", type=float, default=0.40)
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=None,
        help=(
            "Research-only point-in-time DE-persist replay for YYYY-MM-DD. "
            "Writes shadow_policy_rank_de_persist_hist_v1 (NOT E7-eligible)."
        ),
    )
    args = parser.parse_args(argv)
    if args.as_of is not None and args.allow_partial:
        parser.error("--as-of cannot be combined with --allow-partial")
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
