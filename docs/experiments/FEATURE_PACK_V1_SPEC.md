# Feature Pack v1 — workstream spec (W1)

Status: **research-only behind `--feature-pack v1`** on `cpu_exhaust` /
`distributed_worker`. **Not** applied in `live_shadow` (frozen Loop-0
policy matrices). Market-relative only (`fp_use_sector=0.0`; sector deferred).
New policy IDs required before any fp live emit.

Parent plan: [ML_EXHAUST_TO_CONTRACT_MASTER_PLAN.md](../factory/ML_EXHAUST_TO_CONTRACT_MASTER_PLAN.md) §W1.

Research only — not financial advice. No buy/sell language. No
`forecast_points` writes.

---

## Identity

| Field | Value |
|---|---|
| `matrix_id` | `feature_pack_v1` |
| `feature_schema_version` | `feature_pack_v1` |
| Target / horizon / domain (v1 eval) | `relative` / **h1** / `cse` |
| Bars protocol | Same split-adjusted `daily_bars` SHA as 2026-07-23 exhaust champions |
| Baseline comparison | Frozen trio: `xgb_two_stage`, `hgb_two_stage`, `double_ensemble_native` |

`matrix_id` for W5 search is the hash of `(feature_schema_version, horizon, filter_manifest, bars_sha)` per master plan; until W2 combines filters, `filter_manifest=none`.

---

## Intent

Move model search off exhausted terrain by adding **liquidity**, **realized-vol regime**, **sector- or market-relative return**, and **disclosure-proximity hygiene** columns — all computed point-in-time from public CSE bars + Postgres fundamentals/disclosures already in the snapshot pipeline.

---

## Column manifest (deterministic order)

Append after existing path + research + fundamental blocks when integrated. Names are stable; SHA recorded in snapshot manifest on integration.

### Block A — Liquidity / ADV proxy (volume-based)

| Column | Definition | Notes |
|---|---|---|
| `fp_adv20` | Mean `volume` over last 20 sessions with finite volume | ADV proxy; LKR notional optional later via `volume × price` |
| `fp_adv20_log` | `log1p(fp_adv20)` when ADV > 0 else NaN | Scale for tree models |
| `fp_zero_volume_streak` | Consecutive trailing sessions with `volume == 0` or missing | Illiquidity flag |
| `fp_no_trade_flag` | 1.0 if `fp_zero_volume_streak >= 3` else 0.0 | Hard illiquid marker |
| `fp_volume_spike` | Last session volume / `fp_adv20` when ADV > 0 | Same spirit as `vol_spike` in path features |

### Block B — Realized vol regime

| Column | Definition | Notes |
|---|---|---|
| `fp_vol20` | Population stdev of daily returns over last 20 sessions | Realized vol; see `koel/ml/feature_pack_v1.py` |
| `fp_vol60` | Same over 60 sessions when history allows | Longer baseline |
| `fp_vol_regime` | Mean abs return last 5d / mean abs return prior 15d in 20d window | >1 = rising vol regime; breadth-only when no VIX proxy |
| `fp_vol_regime_z` | Cross-section z-score of `fp_vol_regime` within session | Optional at enrich time |

### Block C — Sector-relative return (market fallback)

| Column | Definition | Notes |
|---|---|---|
| `fp_ret_1d` | Symbol 1d return ending `as_of` | Building block |
| `fp_rel_ret_1d` | `fp_ret_1d − sector_median_ret_1d` when `stocks.sector` present | Preferred |
| `fp_rel_ret_5d` | 5d symbol return minus sector median 5d return | Aligns with relative/h1 target |
| `fp_rel_ret_1d_market` | `fp_ret_1d − market_median_ret_1d` | **Fallback** when sector missing |
| `fp_rel_ret_5d_market` | 5d symbol minus market median 5d | Fallback pair |
| `fp_use_sector` | 1.0 if sector label resolved else 0.0 | Auditable fallback indicator |

Sector medians use only symbols with the same sector label **as of** `as_of` (no future sector remaps). Market medians reuse `MARKET_CONTEXT_NAMES` cross-section logic from `koel/ml/research_features.py`.

### Block D — Disclosure / fundamentals proximity

| Column | Definition | Notes |
|---|---|---|
| `fp_days_since_filing` | Days since latest `FundamentalEvent` with `published_at.date() < as_of` | Mirrors fundamental hygiene |
| `fp_disclosure_proximity` | 1.0 if any fundamentals event within **±5** sessions of `as_of` else 0.0 | “Nearby event” flag |
| `fp_pre_filing_window` | 1.0 if filing published in `(as_of, as_of+5]` calendar days | Pre-announce drift guard (label-side awareness) |
| `fp_post_filing_window` | 1.0 if filing published in `[as_of−5, as_of)` | Post-event noise |
| `fp_cliff_quarantine` | Carry existing cliff quarantine bit from sample construction | No new lookahead |

Fundamentals source: snapshot `FundamentalEvent` rows (public filings), same publication-time filter as `koel/ml/research_fundamentals.py`.

---

## Point-in-time / leakage rules (must not leak)

1. **Bars:** For decision date `as_of`, use only bars with `trade_date ≤ as_of`. Helpers accept ascending history ending at `as_of`; never pass future bars.
2. **Cross-section:** Session medians/ranks use symbols observable on that session only (same fold panel as nested eval).
3. **Fundamentals / disclosures:** Event visible only if `published_at.date() < as_of` (strict inequality matches existing enricher).
4. **Sector map:** Use sector label stored on `stocks` at snapshot time; do not backfill sector history from future corporate actions.
5. **No future volume/price:** ADV and vol windows are backward-looking only.
6. **Ablation poison test:** Mutating bars with `trade_date > as_of` must not change features at `as_of` (unit tests required before integration).

Violations → kill workstream per W1 master plan; do not promote.

---

## Evaluation protocol

Same nested **relative/h1** protocol as 2026-07-23 exhaust unless noted.

### Phase 1 — Baseline trio only (no wide search)

1. Export snapshot with `feature_schema_version=feature_pack_v1` and manifest column SHA.
2. Run nested folds (3 outer, official-CSE domain, split-adjusted bars) for:
   - `xgb_two_stage`
   - `hgb_two_stage`
   - `double_ensemble_native`
3. Compare to frozen champions in `docs/experiments/cpu_exhaust_rel_h1_summary.md` on:
   - Pooled RankIC
   - BA / MCC (secondary)
   - Ablation: pack off vs on vs each block off (A/B/C/D)

**Do not** start 10k/6k improve loops or W5 capped search until Phase 1 completes.

### Phase 2 — Selective gates (survivors only)

On nested `*.predictions.jsonl.gz` shards from Phase 1 survivors:

- Tool: `python3 -m koel.ml.selective_gates`
- Same coverage grid and `SuccessContract` as `docs/experiments/SELECTIVE_GATES_20260723.md`
- Calibration-only threshold search per outer fold

### Phase 3 — Cost engineering (survivors only)

On the same shards:

- Tool: `python3 -m koel.ml.cost_engineering`
- Cost: **112 bps** on traded notional
- Book grid: include at minimum `persistence_exit_10_top_bottom_05` (2026-07-23 cost winner)
- Report gross, net@112, turnover, sessions

### Materiality gates (W1 exit)

Improvement vs 2026-07-23 champions requires **any one** of:

- RankIC **+0.005**
- net@112 **+0.10 pp**
- Selective emits **2×** at same calibration coverage grid

If met → unblock W5 bounded search on this `matrix_id`. If full trio regresses on RankIC **and** net@112 with no selective gain → revert pack, document failure, consider W1-b hypothesis.

---

## Policy IDs (reserved — promotion later only)

No policies are wired until W6 promotion review. If offline + prospective gates pass, register **new** immutable IDs (do not overwrite existing exhaust policies):

| Policy ID | Model | Gate / book | Notes |
|---|---|---|---|
| `shadow_policy_rank_xgb2_fp_v1` | `xgb_two_stage` | raw rank emit | Phase 1 survivor |
| `shadow_policy_rank_hgb2_fp_v1` | `hgb_two_stage` | raw rank emit | Phase 1 survivor |
| `shadow_policy_rank_de_fp_v1` | `double_ensemble_native` | raw rank emit | Phase 1 survivor |
| `shadow_policy_rank_xgb2_fp_persist_v1` | `xgb_two_stage` | `persistence_exit_10_top_bottom_05` | Cost-engine survivor |
| `shadow_policy_rank_de_fp_persist_v1` | `double_ensemble_native` | `persistence_exit_10_top_bottom_05` | Cost-engine survivor |
| `shadow_policy_rank_xgb2_fp_selective_v1` | `xgb_two_stage` | calibration selective gate | Only if selective contract met |

Human review required before any shadow wiring. **Never** auto-write `forecast_points` or Telegram paths.

---

## Implementation map (not started except stub)

| Component | Path | Status |
|---|---|---|
| Pure bar helpers (`fp_adv20`, `fp_vol20`) | `koel/ml/feature_pack_v1.py` | Stub + unit tests |
| Column enricher / manifest SHA | `koel/ml/features.py` or `research_features.py` | Not wired |
| Snapshot `feature_schema_version` | `koel/ml/snapshot.py` | Not wired |
| Dataset / distributed worker | `koel/ml/dataset.py`, `distributed_worker.py` | Not wired |
| Live shadow | `koel/ml/live_shadow.py` | **Forbidden** until W6 |

---

## Compliance / NFA

- Research scores only; no investment advice, no ranked “best stocks,” no buy/sell copy.
- Public data only (CSE bars, filings already ingested). No competitor scrape.
- Signal Board ML scores stay hidden; no `forecast_points` integration in this workstream.
- Every cycle note carries: *Research only — not financial advice.*

---

## Required artifacts (W1 exit checklist)

- [ ] This spec checked in
- [ ] `feature_pack_v1` deterministic column list + SHA in snapshot manifest
- [ ] Nested baseline trio complete on new matrix
- [ ] Cycle note: ΔRankIC, Δnet@112, Δselective emits vs 2026-07-23 champions
- [ ] Ablation table: pack off / on / per-block off
- [ ] Selective + cost sidecars for survivors

Kill artifacts: failure note with revert commit hash if pack regresses.

---

## References

- Frozen h1 champions: `docs/experiments/cpu_exhaust_rel_h1_summary.md`
- Selective protocol: `docs/experiments/SELECTIVE_GATES_20260723.md`
- Cost protocol: `docs/experiments/ML_COST_ENGINEERING_LOOP1_20260723.md`
- Split-adjusted bars: `docs/experiments/ML_SPLIT_ADJUSTED_RESCORE_20260723.md`
- Fundamental enricher (PII-safe): `koel/ml/research_fundamentals.py`
