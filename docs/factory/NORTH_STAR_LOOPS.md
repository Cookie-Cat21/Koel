# ML north-star loops

Purpose: keep koel ML work moving toward useful CSE research scores without
turning experiments into advice or prematurely promoting models into product
surfaces. Agents should use this as the operating runbook before starting any
ML, Signal Board, or model-promotion task.

## Cross-cutting contract

- Evidence first: every claim must point to a checked-in experiment doc or JSON
  artifact under `docs/experiments/`.
- Official-CSE qualification only: promotion decisions use official CSE outcome
  rows, not Yahoo/hybrid rows or hand-picked examples.
- Keep targets separate: relative outperformance and absolute direction are
  different products and must keep separate metrics, champions, and gates.
- No fake precision: do not round an unmet selective gate into a success story.
- Cost matters: report post-cost spread at 112 bps whenever a trading-like
  top/bottom spread is discussed.
- Calibration discipline: select hyperparameters, thresholds, blends, and gates
  on calibration data only; score test data once for declared winners.
- Promotion freeze: no candidate may write `forecast_points`, Telegram pushes,
  Signal Board recommendations, or live policy IDs until the hard gates below
  are met and reviewed.
- Compliance: keep all user-facing wording as research/NFA; never use
  buy/sell/"best to invest" language.
- Reproducibility: preserve snapshot hashes, target, horizon, evaluation
  domain, row/session counts, and source artifact paths in each cycle note.

## Global hard gates

These gates come from the current nested evaluation contract artifacts. Passing
RankIC alone is not enough.

- `contract_met` must be `true`.
- Point precision must meet 0.90.
- 95% precision LCB must meet 0.90.
- Emits must be at least 500.
- Symbols must be at least 80.
- Coverage must be at least 0.01.
- Fold precision must be at least 0.85 on at least 2/3 of folds.
- Max symbol share must be at most 0.05.
- Emit days must be at least 60.
- Max session share must be at most 0.05.
- Post-cost spread at 112 bps must be positive for the promoted operating
  slice.

Current state: **not met** for user promotion. Daily 10% post-cost @112 bps
is negative for nested survivors without persistence construction. Split-adjusted
persistence confirms +net for `double_ensemble_native`
(`persistence_exit_10_top_bottom_05`, +0.49% @112bps —
`ML_SPLIT_ADJUSTED_RESCORE_20260723.md`) but selective 90% contract still
fails (`SELECTIVE_GATES_20260723.md`); ensemble blends and improve-loop
6×1000 also exhausted (`ENSEMBLE_STACK_20260723.md`, `CPU_IMPROVE_6K_20260723.md`).

## Loop 0 - Evidence daily automated

Cadence: daily when data changes; immediately after any experiment lands.

Agent actions:

1. Refresh the champion table from checked-in experiment artifacts.
2. Confirm whether any active run changed the current champion, contract state,
   or cost state.
3. Add a dated cycle note with artifact paths, verdict, and next lever.
4. Flag stale, pending, or contradictory docs before new modeling work starts.

Hard gates:

- Every metric in a summary must be traceable to `CPU_EXHAUST_20260722.md` or
  related `cpu_exhaust_*` JSON files unless a newer checked-in artifact exists.
- Current champion status must distinguish nested results from one-fold screens.
- Promotion stays blocked while contract or post-cost gates fail.

**Loop 0 shadow (2026-07-23):** includes DE-persist policy
`shadow_policy_rank_de_persist_v1` — wired in `live_shadow.py` for prospective
ledger emits (book legs only; not user-facing). SuccessContract still unmet.
See `docs/factory/ML_EXHAUST_TO_CONTRACT_MASTER_PLAN.md` §W0 and
`docs/runbooks/ML_LIVE_SHADOW.md`.

Kill criteria:

- Stop the cycle if source artifacts are missing, ambiguous, or still in
  progress.
- Stop the cycle if an agent would need to invent a metric or infer a missing
  result.

## Loop 1 - Research

Cadence: one declared lever at a time; write up each completed cycle before
starting the next lever.

Priority order:

1. Corporate-action adjustment.
2. Cost/turnover reduction.
3. Selective gates.
4. Ensembles.
5. Features.
6. Horizons.

Agent actions:

- Start from the current champion table, not from memory.
- Declare target, horizon, snapshot, selection metric, and winner test policy.
- Prefer levers that can plausibly improve post-cost @112 bps before adding
  more model families.
- Keep relative/h1 and absolute/h1 results side by side but not blended into a
  single claim.

Hard gates:

- Calibration-only selection.
- Official-CSE test scoring.
- No test-set tuning after a failed result.
- No promotion unless all global gates pass.

Kill criteria:

- Retire a branch of research when it improves RankIC but leaves post-cost
  @112 bps negative.
- Retire an approach that depends on a known artifact such as flat-price
  concentration, partition leakage, or test-time retuning.

**Loop 1 status (2026-07-23): levers 1–4 resolved.** (1) split adjustment
**done + verified** — snapshot + nested re-score complete; (2) cost/turnover
**+net@112 verified on split-adjusted bars** (DE persist +0.49%); (3) selective
gates **exhausted**; (4) ensembles **exhausted**; improve-loop 6×1000
**exhausted** (best RankIC 0.2746). Loop 0 DE-persist shadow
`shadow_policy_rank_de_persist_v1` **wired** (`live_shadow.py`; book legs
only; not user-facing). Next levers: W1 feature pack, W3 h5 nested (in flight).
Loop 0 (evidence refresh + shadow receipts) continues daily. See
`docs/experiments/ML_CHAMPION_TABLE.md`,
`docs/factory/ML_EXHAUST_TO_CONTRACT_MASTER_PLAN.md`.

## Loop 2 - Promotion

Cadence: only after Loop 0 shows a candidate passed all global hard gates.

Agent actions:

- Open a promotion packet rather than editing runtime policy code directly.
- Include champion deltas, contract checks, cost checks, concentration checks,
  and compliance wording.
- Require an explicit human review step before any live policy registration.

Hard gates:

- `contract_met=true`.
- Positive post-cost @112 bps on the declared operating slice.
- No failed contract check in the nested artifact.
- No product copy that can be read as investment advice.

Kill criteria:

- Kill promotion immediately if any hard gate is false or missing.
- Kill promotion if the candidate is only a screen winner and not a completed
  nested winner.

## Loop 3 - Product

Cadence: after a promotion packet exists; otherwise product surfaces stay in
research/demo mode.

Agent actions:

- Show research scores with reasons, uncertainty, timestamps, and NFA framing.
- Keep price alerts, disclosures, watchlists, and health as the primary shipped
  product until ML gates pass.
- Make "no model is live-promoted" visible when relevant.

Hard gates:

- Product must not imply a model passed gates that are currently unmet.
- Product must not expose buy/sell instructions.
- Any displayed ML score must identify source model/version and freshness.

Kill criteria:

- Remove or hide copy that turns research into advice.
- Stop work if the product request depends on fake historical performance.

## Loop 4 - Platform

Cadence: whenever an experiment fails for infrastructure reasons or reproducible
evidence is blocked.

Agent actions:

- Improve repeatability, artifact capture, data snapshots, and cost accounting.
- Fix data pipeline issues before expanding model search.
- Keep runtime product code separate from research experiments unless the task
  explicitly asks for a production integration and gates allow it.

Hard gates:

- Platform changes must preserve append-only experiment evidence.
- Any data adapter change must log source, timestamp, and failure context.
- No production writes from research jobs.

Kill criteria:

- Stop platform work that mainly enables more blind hyperparameter grinding.
- Stop if the change risks contaminating live dashboard, Telegram, or
  `forecast_points` state.

## Loop 5 - Expansion

Cadence: only after core relative/absolute loops have a stable, documented
contract path.

Agent actions:

- Consider new data sources, horizons, or market regimes only as declared
  challengers.
- Preserve the current CSE/public-data compliance boundary.
- Require a new evidence doc for any new domain before comparing it to the CSE
  champions.

Hard gates:

- Publicly available data only.
- No competitor scraping.
- New horizons and domains need separate baselines, contracts, and champion
  rows.

Kill criteria:

- Kill expansion if it weakens compliance, reproducibility, or current product
  focus.
- Kill expansion if it tries to bypass unmet core promotion gates.

