# ML exhaust → contract master plan

**Status:** Active — same-matrix h1 search exhausted; W1–W4 first passes **killed or
closed without unlock**; Goal A (selective 90%) **still unmet**; global promotion
**blocked**. Loop 0 DE-persist shadow **wired** (`shadow_policy_rank_de_persist_v1`
in `live_shadow.py`; partial canary only — **≥60 non-partial scored sessions still
needed**).  
**Authority:** [NORTH_STAR_LOOPS.md](NORTH_STAR_LOOPS.md) · [ML_DISTRIBUTED_90_MASTER_PLAN.md](ML_DISTRIBUTED_90_MASTER_PLAN.md) · [ML_CHAMPION_TABLE.md](../experiments/ML_CHAMPION_TABLE.md)  
**Run until:** selective 90% SuccessContract met **or** exhaustion checklist (§4) all true.

### Progress ledger (2026-07-23, honest)

| Workstream | State | Headline |
|---|---|---|
| **W0** Loop 0 DE-persist shadow | **Partial** | Wired + `live_shadow_report` book-policy row; partial canary **14 legs** (`DE_PERSIST_CANARY_20260723.md`); no non-partial receipts yet |
| **W0b** Loop 0 h3 weekly shadow | **Wired** | `shadow_policy_rank_de_h3_weekly_v1`; relative/h3 DE + weekly_5_sessions_top_bottom_05; no non-partial receipts yet |
| **W1** feature_pack_v1 | **Killed (no materiality)** | Nested fpv1: best RankIC Δ **−0.0007** vs frozen 0.2861; selective/cost below W1 thresholds (`FEATURE_PACK_V1_NESTED_20260723.md`) |
| **W2** liq_v1 universe filter | **Killed** | Sample collapse **−93.5%**; xgb/hgb screen fail; 0 selective emits (`UNIVERSE_FILTER_LIQ_V1_NESTED_20260723.md`) |
| **W2+W1** fp+liq combo | **Killed** | Same 32 535-row ceiling; DE partial RankIC 0.1779; retired with liq_v1 (`FEATURE_PACK_LIQ_V1_NESTED_20260723.md`) |
| **W3** relative/h5 | **Done — no unlock** | RankIC ~**0.17** (xgb 0.1735); selective **0** emits; cost still negative (`CPU_EXHAUST_REL_H5_20260723.md`) |
| **W4** CSE-only ablation | **Killed** | ~1y CSE history insufficient for nested splits (`CSE_ONLY_NESTED_20260723.md`) |
| **W5** bounded search | **Blocked** | Do not start until a new `matrix_id` shows W1/W3 materiality |
| **W2** liq_v3 flat-only universe filter | **Killed / exhausted** | 35,377 samples (<100k), best RankIC 0.2227, 0 selective emits; flat_fraction alone collapses hybrid history (`UNIVERSE_FILTER_LIQ_V3_NESTED_20260723.md`) |
| **W1b** adv20 sample-weight | **Killed (no materiality)** | Nested xgb +0.0001 RankIC; selective regresses; DE +0.45% vs +0.49% (`SAMPLE_WEIGHT_ADV20_NESTED_20260724.md`) |
| **Goal A** selective denser + disagreement (fpv2) | **Killed** | Best 0.779/0.693/77 emits; contract false (`SELECTIVE_DISAGREEMENT_20260724.md`, `SELECTIVE_DENSE_FPV2_20260724.md`) |
| **In flight** | E7 non-partial shadow after 14:35 Colombo (partial smoke attempted) |

**Champions unchanged:** RankIC `xgb_two_stage` rel/h1 **0.2861**; cost DE persist split **+0.49%** @112; selective near-miss **0.770 / 0.681 / 74 emits**.

---

## 0. Operating context (2026-07-23)

| Lane | Champion | Key metric | Contract |
|---|---|---|---:|
| RankIC (relative/h1) | `xgb_two_stage` | RankIC **0.2861** | Selective 90% **not met** |
| Cost (relative/h1, split-adjusted) | `double_ensemble_native` / `persistence_exit_10_top_bottom_05` | **+0.49%** net@112bps | Selective 90% **not met** (0 emits under grid) |
| Selective near-miss | `xgb_two_stage` | prec **0.770** / LCB **0.681** / **74** emits | All SuccessContract checks **false** |

**Exhausted on the frozen feature matrix + h1 relative/absolute targets:**

- Model-family screen (nested survivors + 10k LGB)
- 6×1000 improve loop (`CPU_IMPROVE_6K_20260723.md`)
- Ensemble stack (`ENSEMBLE_STACK_20260723.md`)
- Selective gate grids (`SELECTIVE_GATES_20260723.md`)
- Cost variants on existing scores (persistence flip verified on split bars)

**First-pass killed (not global exhaustion — see §4):**

- W1 `feature_pack_v1` nested — no materiality (RankIC Δ −0.0007)
- W2 `liq_v1` + fp+liq combo — 93% sample collapse; 0 selective emits
- W3 relative/h5 — RankIC ~0.17; selective 0; cost negative
- W4 CSE-only ablation — insufficient history (~1y CSE)

**Still open (not exhausted):**

- W0 prospective shadow — h1 DE-persist and h3 weekly wired; need **≥60 non-partial scored sessions**
- W1 feature revisions beyond fpv1 if a new matrix lands
- W5 bounded search — **only** after a new `matrix_id` clears materiality
- Goal A selective-90% chase on any improving matrix

**Cross-cutting rules (non-negotiable):**

1. Every model, feature, horizon, filter, or gate change → **new immutable policy ID**; prior IDs stay append-only.
2. Report trading-like spreads at **112 bps** unless a written justification uses another cost assumption.
3. **Never weaken** the SuccessContract to claim progress (precision/LCB ≥0.90, emits ≥500, symbols ≥80, coverage ≥0.01, fold stability, concentration caps — see §1.A).
4. No writes to `forecast_points`, Telegram, or Signal Board until **all** global hard gates in [NORTH_STAR_LOOPS.md](NORTH_STAR_LOOPS.md) pass human review.
5. Calibration-only selection; test scored once per declared winner; official-CSE outcomes only for qualification.
6. NFA framing on every user-facing or summary artifact.

---

## 1. Goal hierarchy

Workstreams prioritize in this order. Lower tiers never override higher-tier kill criteria.

### A — Selective 90% SuccessContract (primary)

**Definition:** offline nested evaluation (or prospective shadow aggregate, once sufficient) where `contract_met=true` on the declared target/horizon/domain.

| Check | Gate |
|---|---:|
| Test selective precision | ≥ 0.90 |
| One-sided 95% Wilson LCB | ≥ 0.90 |
| Held-out emits | ≥ 500 |
| Distinct symbols | ≥ 80 |
| Eligible-row coverage | ≥ 0.01 |
| Outer folds with precision ≥ 0.85 | ≥ 2/3 |
| Max symbol share of emits | ≤ 0.05 |
| Distinct emit sessions | ≥ 60 |
| Max session share of emits | ≤ 0.05 |

**Win condition:** any policy ID passes all rows on official-CSE nested test **and** survives prospective shadow standards (Loop 0 receipts) without contradiction.

**Anti-patterns (instant fail):** reporting fold-0 only, pooling calibration+test, lowering coverage floor, ex-post threshold tuning, flat-price concentration pockets.

### B — Cost + ranking shadow (secondary, parallel track)

**Definition:** prospective evidence for the split-adjusted cost champion operating slice.

- Policy ID: `shadow_policy_rank_de_persist_v1` (**wired** in `live_shadow.py`; partial canary only).
- Model: `double_ensemble_native` with `persistence_exit_10_top_bottom_05` book on **relative/h1** scores.
- Offline reference: **+0.49%** net@112bps on split-adjusted bars (`ML_SPLIT_ADJUSTED_RESCORE_20260723.md`).
- Secondary policy ID: `shadow_policy_rank_de_h3_weekly_v1` (**wired** in
  `live_shadow.py`; no receipts yet).
- Secondary model/book: `double_ensemble_native` with
  `weekly_5_sessions_top_bottom_05` on **relative/h3** scores; rebuild when
  `session_index % 5 == 0`, otherwise re-emit prior sides with incremented ages.
- Secondary offline reference: **+0.27%** net@112bps on split-adjusted h3 bars
  (`ML_H3_WEEKLY_COST_20260723.md`).
- Purpose: accumulate **honest forward receipts** while feature/horizon work continues; cost shadow does **not** substitute for selective 90%.

**Win condition:** ≥60 scored sessions, positive net@112 on shadow aggregate, concentration within contract caps, no partial-session contamination in standards.

### C — Honesty kill (tertiary guardrail)

**Definition:** stop a branch when evidence shows the lever cannot reach A or B without violating cross-cutting rules.

Kill immediately when:

- RankIC improves but post-cost @112 bps stays negative on the declared operating slice.
- Selective precision rises only via symbol/session concentration above contract caps.
- Results depend on partition leakage, test retuning, or unresolved price cliffs.
- Prospective shadow diverges materially from nested offline claims (>10pp precision gap with matched coverage).
- Engineering would require weakening gates, inventing metrics, or promoting without artifacts.

**Win condition (exhaustion path):** §4 checklist all true → publish exhaustion dossier (W6) and keep Loop 0 running on best-known shadow policies only.

---

## 2. Workstreams W0–W6

Each workstream produces a dated cycle note under `docs/experiments/` plus JSON artifacts. Loop 0 refreshes the champion table after every completion.

### W0 — Loop 0 DE-persist shadow wiring + daily receipts

**Intent:** Wire the split-adjusted cost champion into prospective capture so forward performance is measurable while offline search continues.

**Scope:**

1. Register `shadow_policy_rank_de_persist_v1` in `koel/ml/live_shadow.py` (or sibling module) with:
   - target: `relative`, horizon: `1`
   - model: `double_ensemble_native`
   - post-score book: `persistence_exit_10_top_bottom_05` (top/bottom 5% names, 10% persistence exit)
   - immutable `model_version` = f(policy_id, snapshot_sha, issue_session, code_rev, book_params_sha)
2. Emit ranked long/short legs (or signed score + book metadata) to `forecast_outcomes` only — same safety boundary as existing abs policies (`docs/runbooks/ML_LIVE_SHADOW.md`).
3. Extend `live_shadow_report` to tabulate:
   - net@112bps on shadow emits
   - RankIC / hit-rate on matured relative outcomes
   - emit counts, symbol/session concentration
4. Update `.github/workflows/ml-live-shadow.yml` to include the new policy in the daily matrix.
5. Loop 0 cycle note template: champion delta, shadow receipts path, contract state unchanged/met, next lever.

**Exit criteria:**

- [ ] At least one non-partial shadow emit stored under `shadow_policy_rank_de_persist_v1`.
- [x] `live_shadow_report` includes DE-persist row with net@112 and concentration columns.
- [x] Runbook + champion table reference the wired policy ID (not "proposed").
- [x] Loop 0 daily note cites artifact paths for shadow receipts (`DE_PERSIST_CANARY_20260723.md`; partial only).

**Kill criteria:**

- Shadow emits require features or labels unavailable at issue time (lookahead).
- Implementation would write `forecast_points` or touch Telegram paths.
- DE-persist book cannot be reproduced deterministically from stored row metadata.
- After 60 scored sessions, net@112 is negative **and** offline split-adjusted +0.49% is not reproducible on the same snapshot protocol → freeze policy, open data-quality incident (W4), do not silently retune.

**Dependencies:** none (start immediately).  
**Does not satisfy:** Goal A alone.

---

### W1 — Feature pack v1 (liquidity / regime / sector-relative / event hygiene)

**Intent:** Change the feature matrix so model search is no longer on exhausted terrain.

**Candidate features (implement as named, versioned pack `feature_pack_v1`):**

| Block | Examples | Rationale |
|---|---|---|
| Liquidity | 20d ADV rank, zero-volume streak, bid-ask proxy from range×volume, no-trade flags | Reduce flat/illiquid false emits |
| Regime | ASPI 5/20d return, cross-section dispersion, VIX-proxy absent → breadth-only | Context for selective gates |
| Sector-relative | symbol return minus sector median; sector RankIC residual | Align with relative/h1 target |
| Event hygiene | days since disclosure; pre/post filing window flags; cliff quarantine carry | Stop label noise from events |

**Protocol:**

- Bump snapshot manifest with `feature_schema_version=feature_pack_v1`.
- Re-run **baseline trio only** first: `xgb_two_stage`, `hgb_two_stage`, `double_ensemble_native` on relative/h1 nested folds — no wide search.
- Compare to frozen champions using same split-adjusted bars SHA.
- Document ablation table: pack off vs on vs each block off.

**Exit criteria:**

- [x] `feature_pack_v1` checked in with deterministic column list + SHA in snapshot manifest.
- [x] Nested baseline trio complete with new matrix; cycle note shows ΔRankIC, Δnet@112, Δselective best emit count vs 2026-07-23 champions (`FEATURE_PACK_V1_NESTED_20260723.md`).
- [ ] At least one metric (RankIC, net@112, or selective emits at fixed coverage) improves ≥ agreed materiality: RankIC +0.005, or net@112 +0.10pp, or selective emits 2× at same calibration coverage grid. **Not met** — best RankIC Δ **−0.0007**; fpv1 **killed** on materiality.
- [ ] If material improvement → unblock W5 for this matrix version. **Blocked** — no W5 on fpv1 matrix.

**Kill criteria:**

- Full trio regression on both RankIC **and** net@112 with no selective emit gain → revert pack; document failure; try next feature hypothesis (W1-b) before W5.
- Improvement traceable only to flat-price names or single symbol → reject block ex ante.
- Feature computation requires non-public data or competitor scrape.

**Dependencies:** W4 cliff/corp-action fixes recommended in parallel but not blocking for pack v1 if quarantine flags already exist.

---

### W2 — Universe / liquidity filters in training

**Intent:** Train and emit on an eligible universe so selective gates are not dominated by untradeable rows.

**Candidate filters (calibration-selected, predeclared grid):**

- Minimum 20d median turnover (LKR or share volume).
- Exclude top decile flat-history fraction (extend existing `max_flat_fraction`).
- Minimum official-CSE session count in trailing 60d.
- Optional: exclude symbols with unresolved cliff in label window.

**Protocol:**

- Filters apply at **sample construction** (`build_samples` / distributed worker), not post-hoc on scores.
- New policy IDs per filter preset (e.g. `_liq_v1` suffix).
- Nested evaluation on relative/h1 with baseline trio before any search.

**Exit criteria:**

- [x] Filter manifest checked in with thresholds frozen before nested run (`liq_v1`; preset **retired**).
- [x] Eligible row count, symbol count, and session count reported per fold (`UNIVERSE_FILTER_LIQ_V1_NESTED_20260723.md`: 502 908 → 32 535 rows, −93.5%).
- [ ] Selective gate best-point improves emits ≥2× **or** precision LCB ≥0.75 at ≥100 emits **or** net@112 improves ≥0.10pp vs unfiltered champion at same model. **Not met** — **0** selective emits; **killed**.
- [ ] Concentration caps satisfied at best selective point. **N/A** — no qualifying selective point.

**Next:** `liq_v2` softer filter manifest before re-nesting.

**Kill criteria:**

- Filter removes >50% of official-CSE sessions without selective contract progress.
- Improvement is coverage collapse (emits <30) with precision noise.
- Filter uses future liquidity (lookahead in median turnover).

**Dependencies:** can parallel W1 after schema freeze; combine as `feature_pack_v1 + liq_filter_v1` → single new matrix ID for W5.

---

### W3 — Horizon h5 (+ optional h3) nested + selective + cost

**Intent:** Exhaust horizon lever before declaring global exhaustion.

**Protocol:**

- Primary: **relative/h5** nested (three outer folds, official-CSE domain, split-adjusted bars).
- Optional parallel: relative/h3 if compute budget allows (lower priority than h5).
- Run baseline trio + selective grid + `persistence_exit_10_top_bottom_05` cost book on each horizon.
- Separate champion rows in `ML_CHAMPION_TABLE.md` — do not blend h1 and h5 metrics.

**Exit criteria:**

- [x] `cpu_exhaust_rel_h5_summary.json` (and markdown) checked in with same schema as h1 exhaust (`CPU_EXHAUST_REL_H5_20260723.md`).
- [x] Selective + cost reports parallel to `SELECTIVE_GATES_20260723.md` and split cost compare.
- [ ] If h5 beats h1 on selective LCB or net@112 at matched coverage → declare h5 challenger; new shadow policy IDs per horizon. **Not met** — RankIC ~0.17 vs h1 0.2861; selective **0**; cost negative.
- [ ] Prospective shadow stub documented if h5 wins offline (do not wire until W0 pattern replicated). **N/A** — h5 did not win.

**In progress:** relative/**h3** nested (optional challenger; lower priority than h5 was).

**Kill criteria:**

- h5 nested RankIC and selective best both strictly worse than h1 champions **and** net@112 worse → mark horizon exhausted for relative target; record in W6 dossier.
- Label leakage via overlapping h5 windows across folds (verify embargo ≥5 sessions).
- h5 emits concentrate in <10 symbols → reject unless ex-ante filter fixes it (loop W2).

**Dependencies:** independent of W1/W2 (can run in parallel on current matrix) but **must complete before W5** on old matrix is allowed to continue. After W1/W2 land, re-run h5 on new matrix.

---

### W4 — Data enrichment (dividends / rights if public; CSE-only ablation)

**Intent:** Remove label noise and quantify domain purity before final exhaustion sign-off.

**Tracks:**

1. **Corporate actions (public CSE only):** ingest splits, rights, scrip dividends when available from official endpoints or filings; extend split-adjusted bar builder; version bars SHA.
2. **CSE-only ablation:** train/eval excluding Yahoo pretrain rows from qualification folds (Yahoo may remain for pretrain experiments but cannot qualify SuccessContract).
3. **Data-quality report:** per-snapshot counts of unresolved cliffs, flat spans, symbol lineage breaks.

**Exit criteria:**

- [x] New bars SHA documented; nested re-score of h1 baseline trio on adjusted bars (`ML_SPLIT_ADJUSTED_RESCORE_20260723.md`).
- [x] CSE-only ablation table in cycle note (RankIC, selective, net@112 vs hybrid). **Killed** — insufficient history for nested splits (`CSE_ONLY_NESTED_20260723.md`; metrics n/a).
- [x] If DE-persist +0.49% was fragile: confirm sign and magnitude after enrichment delta documented (split re-score **+0.49%** retained).

**Kill criteria:**

- Enrichment source is not publicly available or violates compliance fence.
- Re-score reverses cost champion sign without fixing a documented bug → halt promotion paths; fix adapter first.
- CSE-only rows <60 sessions → defer qualification claim; continue shadow only.

**Dependencies:** parallel with W0–W3; **blocks W6 exhaustion claim** until cliff/corp-action backlog is either resolved or explicitly waived with evidence.

---

### W5 — Bounded model search (only after W1 or W3 changes the matrix)

**Intent:** Limited re-open of model search **only** on a declared new feature/horizon/filter SHA — never repeat 10k/6k grind on unchanged matrix.

**Cap:** ≤ **2,000** configs total per matrix version (e.g. 1,500 LGB + 500 XGB/HGB/neighborhood), selected on calibration net@112 then RankIC.

**Protocol:**

1. Declare `matrix_id` = hash(feature_schema, horizon, filter_manifest, bars_sha).
2. Run `cpu_exhaust` or `cpu_improve_loop` with `--max-configs 2000` and hard stop.
3. Top-5 calibration winners → one test score each → selective grid → cost book.
4. Compare to W1/W3 baseline trio uplift; if no beat → matrix marked exhausted for search.

**Exit criteria:**

- [ ] `matrix_id` recorded in summary JSON.
- [ ] Config count ≤2,000 with artifact proof.
- [ ] Any new champion updates `ML_CHAMPION_TABLE.md` with source path.
- [ ] If SuccessContract met → trigger W6 promotion packet branch.

**Kill criteria:**

- Matrix unchanged from 2026-07-23 h1 exhaust → **do not start W5** (instant stop).
- 2,000 configs complete with no beat on primary metric (selective LCB, else net@112, else RankIC) → mark matrix search exhausted.
- Operator requests open-ended improve loops → refuse; point to this cap.

**Dependencies:** W1 and/or W3 (and optionally W2) must land first.

---

### W6 — Final exhaustion dossier OR promotion packet

**Intent:** Single closing artifact set — either honest stop or gated promotion.

**Branch 6a — Promotion packet (Goal A met):**

- Policy ID, matrix_id, snapshot SHA, horizon, target, model, gate, book params.
- Nested `contract_met=true` JSON + prospective shadow report meeting same thresholds.
- Cost table @112bps; concentration proof; compliance/NFA wording.
- Explicit human review checklist; still **no** auto-write to `forecast_points`.

**Branch 6b — Exhaustion dossier (§4 all true, Goal A not met):**

- Table of every lever tried, matrix_id, best metric, kill reason.
- Statement: same-matrix model search exhausted; horizons/features/filters/data tried or waived with evidence.
- Forward plan: Loop 0 continues shadow receipts; product stays research/demo; Signal Board ML scores stay hidden.

**Exit criteria:**

- [ ] Single markdown doc `docs/experiments/ML_EXHAUSTION_OR_PROMOTION_YYYYMMDD.md` checked in.
- [ ] Champion table status row: `EXHAUSTED` or `PROMOTION_REVIEW`.
- [ ] NORTH_STAR_LOOPS Loop 1 section updated with pointer.

**Kill criteria:**

- Missing artifact for any claimed workstream → do not sign exhaustion.
- Promotion packet requested while any hard gate false → refuse (Goal C).

**Dependencies:** all other workstreams complete or explicitly killed with docs.

---

## 3. SuccessContract reference (unchanged)

Do not edit gates in this plan. Full contract lives in [ML_DISTRIBUTED_90_MASTER_PLAN.md](ML_DISTRIBUTED_90_MASTER_PLAN.md) §1 and [NORTH_STAR_LOOPS.md](NORTH_STAR_LOOPS.md) global hard gates.

Prospective shadow uses the same numeric thresholds for **standards reporting**; offline nested remains the primary selector for model changes until prospective rows ≥500 emits.

---

## 4. Definition of “truly exhausted”

Exhaustion is claimed **only** when **every** item below is true. Otherwise keep running W0–W5.

**Checklist status (2026-07-24):** 7/10 evidenced — **not truly exhausted** (E7–E8 open: need ≥60 non-partial shadow sessions; E10 dossier pending). adv20 + selective denser/disagreement + fpv2 extra **killed**; rankers + blends + E7 non-partial in flight.

| # | Done | Condition | Evidence artifact |
|---|:---:|---|---|
| E1 | [x] | Same-matrix h1 model search capped and failed | `CPU_EXHAUST_20260722.md`, `CPU_IMPROVE_6K_20260723.md`; W5 not started (no new matrix) |
| E2 | [x] | Ensemble + selective grids failed on best nested scores | `ENSEMBLE_STACK_20260723.md`, `SELECTIVE_GATES_20260723.md`, `CPU_EXHAUST_REL_H5_20260723.md` (h5 selective 0) |
| E3 | [x] | Feature pack v1 (and one revision if v1 killed) tested with baseline trio | `FEATURE_PACK_V1_NESTED_20260723.md` — **killed, no materiality**; revision optional via liq_v2 / fp combo |
| E4 | [x] | Universe/liquidity filters tested | `UNIVERSE_FILTER_LIQ_V1_NESTED_20260723.md`, `FEATURE_PACK_LIQ_V1_NESTED_20260723.md` — **liq_v1 killed**; liq_v1–v3 **killed** (flat collapse) |
| E5 | [ ] | Relative **h5** nested complete (h3 optional) | [x] h5: `cpu_exhaust_rel_h5_summary.json`; [x] h3 nested complete (`CPU_EXHAUST_REL_H3_*`) |
| E6 | [x] | Data enrichment re-score complete or backlog waived in writing | Split re-score done; CSE-only ablation **killed** (`CSE_ONLY_NESTED_20260723.md`) |
| E7 | [ ] | DE-persist shadow wired with ≥60 scored prospective sessions | Wired + partial canary 14 legs; **non-partial receipts pending** |
| E8 | [ ] | No candidate meets SuccessContract offline **and** prospective precision/LCB within 10pp of offline at matched coverage | Offline: no contract met; prospective aggregate **insufficient** |
| E9 | [x] | No policy ID approved for `forecast_points` / Telegram / Signal Board | Loop 2 kill criteria satisfied |
| E10 | [ ] | Human-readable dossier checked in | W6 branch 6b **not started** |

**Not required for exhaustion:** beating RankIC 0.2861; positive net@112 alone; absolute/h1 dominance.

---

## 5. Parallelization map

```text
                    ┌─────────────────────────────────────┐
                    │  W0 DE-persist shadow (daily)      │  ← start now; runs continuously
                    └─────────────────────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
   ┌─────────────┐            ┌─────────────┐            ┌─────────────┐
   │ W4 data     │            │ W3 h5 nested│            │ Loop 0      │
   │ enrichment  │            │ (curr matrix)│            │ daily notes │
   └──────┬──────┘            └──────┬──────┘            └─────────────┘
          │                          │
          │         ┌────────────────┴────────────────┐
          │         ▼                                 ▼
          │  ┌─────────────┐                   ┌─────────────┐
          └─►│ W1 feature  │                   │ W2 universe │
             │ pack v1     │                   │ filters     │
             └──────┬──────┘                   └──────┬──────┘
                    │                                  │
                    └──────────────┬───────────────────┘
                                   ▼
                            ┌─────────────┐
                            │ W5 bounded  │  ← only after new matrix_id
                            │ ≤2k configs │
                            └──────┬──────┘
                                   ▼
                            ┌─────────────┐
                            │ W6 dossier  │
                            │ or promote  │
                            └─────────────┘
```

| Parallel safe | Sequential gate |
|---|---|
| W0 + W3 + W4 | W5 after W1 and/or W3 new matrix |
| W1 + W2 (coordinate combined matrix_id) | W6 after W0–W5 each exited or killed |
| W3 on current matrix while W1 in flight | Re-run W3 after W1/W2 merge |
| Loop 0 daily alongside all | Promotion (W6a) after E1–E10 |

**Resource notes:**

- W3 nested + W5 search: CPU/GHA matrix jobs — stagger to avoid factory concurrency >16.
- W0: single daily workflow slot post-close; no overlap requirement.
- W1/W2: local or CI reproducible builds; one declared lever per cycle note.

---

## 6. Non-goals / compliance fence

| Non-goal | Reason |
|---|---|
| Writing `forecast_points` or Telegram/alert integration | Global promotion freeze |
| Signal Board ranked recommendations | Same freeze; research/demo only |
| Weakening SuccessContract thresholds | Goal C honesty kill |
| Open-ended 10k/6k improve loops on same matrix | Proven exhausted |
| Third-party macro / competitor data | [CLAUDE.md](../../CLAUDE.md) compliance |
| Yahoo rows qualifying CSE contract | Domain separation |
| Buy/sell / “best stock” copy | SEC/NFA framing |
| GPU foundation-model scale-up without nested beat | [ML_DISTRIBUTED_90_MASTER_PLAN.md](ML_DISTRIBUTED_90_MASTER_PLAN.md) Phase D bar |
| Portfolio P&L, tax, screener terminal | Product non-goals in CLAUDE.md |
| Auto-promotion from shadow | Human review required (Loop 2) |

---

## 7. Immediate next 5 engineering tasks

Concrete, ordered, actionable — no estimates.

1. **W0 — Non-partial shadow receipts:** run post-close `live_shadow` on full sessions until `shadow_policy_rank_de_persist_v1` has **≥60 scored non-partial** rows; tabulate in `live_shadow_report` (net@112, RankIC, concentration).

2. **W3 — Complete relative/h3 nested baseline trio:** mirror h5 protocol on current matrix; output `cpu_exhaust_rel_h3_summary.json` + selective/cost sidecars before declaring horizon lever closed.

3. **W2 — liq_v2 softer filter manifest + nested trio:** relax ADV/flat/session thresholds to avoid >50% session loss; freeze manifest; nested relative/h1 baseline trio only (no W5 until materiality).

4. **Goal A — Selective 90% chase:** on any new matrix (liq_v2, h3, or fp revision) that improves RankIC, net@112, or emit count, re-run selective grid at fixed coverage before bounded search.

5. **W5 — Hold:** do **not** start bounded ≤2k search until a declared new `matrix_id` clears W1/W3 materiality thresholds; fpv1, liq_v1, fp+liq, h5, and CSE-only paths are **killed**.

---

## 8. Artifact checklist (agent quick reference)

| Workstream | Required outputs |
|---|---|
| W0 | shadow rows, report JSON, cycle note, runbook diff |
| W1 | feature manifest SHA, trio nested summary, ablation md |
| W2 | filter manifest, eligible-universe stats, trio nested summary |
| W3 | h5 summary json/md, selective + cost sidecars |
| W4 | bars SHA delta, CSE-only ablation, data-quality report |
| W5 | matrix_id, capped config log, champion table update |
| W6 | exhaustion or promotion markdown, Loop 1 pointer update |

---

## 9. Current champion pointers (do not hand-edit metrics)

- RankIC: `xgb_two_stage` rel/h1 **0.2861** — `docs/experiments/cpu_exhaust_rel_h1_summary.json`
- Cost: `double_ensemble_native` / `persistence_exit_10_top_bottom_05` **+0.49%** @112 split — `docs/experiments/ML_SPLIT_ADJUSTED_RESCORE_20260723.md`
- Selective: best **0.770 / 0.681 / 74 emits** — `docs/experiments/SELECTIVE_GATES_20260723.md`

Research only — not financial advice.
