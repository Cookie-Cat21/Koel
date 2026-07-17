# ML self-improving loop — operator guide

Implementation of the closed-loop plan: outcomes → nightly adapt → weekly
promote → research agent backlog. Dashboard surfaces Spoke/Silent forecasts
and a Model section on `/health` (research metrics only).

## Enable

```bash
# .env
ML_LOOP_ENABLED=1
ML_FORECAST_ENABLED=0   # keep user-facing off until you opt in
```

## Serve modes (recommended)

| Mode | When to use | Approx. selective hit |
|---|---|---|
| `gated_p90` | Sparse high-precision path (ops default for “speak rarely”) | ~90% holdout (sym×conf) |
| `gated` | Denser selective coverage | ~73% @ ~11% cov |
| `hpe_with_fallback` | Board fill / research overlay for most symbols | HPE sparse + always-on ~60% |
| `always_on` | Research only — not ops default | ~59–60% |

```bash
python3 -m chime ml-forecast-unified --mode gated_p90
python3 -m chime ml-forecast-unified --mode gated
```

Silence is expected. Selective ≠ always right.

## Commands

| Command | Loop | Purpose |
|---|---|---|
| `python3 -m chime ml-forecast-unified --mode …` | serve | Emit forecasts (+ outcomes rows) |
| `python3 -m chime ml-score-outcomes` | A | Grade due horizons |
| `python3 -m chime ml-loop-nightly --force` | A | Accrue market summary + OB, scoreboard, allowlist, drift |
| `python3 -m chime ml-loop-retrain --force` | B | Train challenger; promote if gates pass |
| `python3 -m chime ml-loop-research --force` | C | Run open backlog experiments |
| `python3 -m chime market-summary-backfill` | data | Upsert CSE dailyMarketSummery (~2 days/call) |
| Loop C agent | C | See `LOOP_C_PROMPT.md` + `EXPERIMENT_BACKLOG.md` |

## Accrual unlock thresholds

| Track | Source | Unlock |
|---|---|---|
| B-011 / B-002 | `market_daily_summary` | Re-run market-summary features when **≥ 60** days |
| B-001 | `order_book_snapshots` | Nightly top-25 poll; empty off-hours is OK — need multi-day depth |

## Tables

- `forecast_outcomes` — ground truth ledger (migration 019)
- `model_registry` — champion/challenger (migration 020)
- `forecast_points` — serve path + confidence (017/018)
- `market_daily_summary` — foreign flow / turnover (021)

## Artifacts

- `docs/experiments/LIVE_SCOREBOARD.md`
- `docs/experiments/MODEL_REGISTRY.md`
- `docs/experiments/GATE_HOLDOUT_STRESS.md`
- `data/ml_artifacts/gate_calibration.json`
- `data/ml_artifacts/reliable_symbols.json`

## Dash

- `/signals` — Spoke / Silent chips + gate labels
- `/symbols/{sym}` — sparkline auto-shows selective gates
- `/health` — Model / forecast section (champion, gated hit, accrual)

## Kill switch

`ML_LOOP_ENABLED=0` stops nightly/retrain/research CLIs (unless `--force`).
Champion artifacts remain; dash forecasts still require `ML_FORECAST_ENABLED`
for some older paths; unified CLI does not require that flag.

Research only — not financial advice.
