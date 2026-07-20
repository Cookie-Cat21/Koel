# Hardened ML summary (purge · RankIC · confidence)

**Report:** `ml_hardened_20260716T145857Z.md`  
**Universe:** 273 symbols · 64 400 daily bars (~1y CSE path)  
**Decision:** **GO** (under honesty checks)

## What changed vs the earlier walk-forward

| Check | Old `ml-experiment` | New `ml-harden` |
|---|---|---|
| Train/test split | Expanding, no purge | Purge `max(horizon, embargo)` sessions before test |
| Fold step | 20 (~2–3 folds) | 10 (**7–8 folds**) |
| Ranking metric | Pooled Spearman IC | **Mean daily RankIC** |
| Panel | Absolute return | Cross-section demeaned return |
| Confidence | None | Sweep on \|P(up)−0.5\| / \|ŷ\| |

## Headline numbers

| Model | Mode | H | Hit | RankIC | Best gated hit | Coverage |
|---|---|---:|---:|---:|---:|---:|
| B1_logistic | purged | 1 | **0.569** | **0.211** | (see report sweeps) | — |
| M1_hgb_clf | purged | 1 | **0.562** | **0.211** | (see report sweeps) | — |
| M1_hgb_clf | **panel** | 1 | **0.564** | **0.239** | **0.659 @0.15** | **0.22** |
| M2_hgb_reg | panel | 1 | **0.561** | **0.212** | (low-cov at high thr) | — |
| M1_hgb_clf | panel | 5 | **0.556** | 0.154 | 0.630 @0.15 | 0.27 |
| B0_naive | — | 5 | 0.443 | — | — | — |

Fold hit rates stay ≥0.52 on **7–8/8** folds for the 1d classifiers (not a one-fold fluke).

## Interpretation (honest)

- **Purged hit ~56–57%** on 1d — still “right a bit more than half the time,” but **did not collapse to chance** under purge. Earlier ~58% was not pure leakage.
- **RankIC ~0.21–0.24** (1d) is the stronger story: the model ranks names vs peers usefully, not just absolute direction.
- **Confidence gate:** panel HGB classifier reaches **~65% hit on ~21% of samples** at \|P−0.5\|≥0.15 — near the soft “speak when sharp” target. Not 90%, and not every day.
- 5d is weaker on hit rate but RankIC remains positive (~0.14–0.16).

## Product implication

- Keep Signal Board research scores; keep ML forecast **flag-gated**.
- Prefer **panel + confidence gate** for any future “only show when confident” UI, not raw always-on arrows.
- Next optional wave (not auto-wired): filing/notice features in the ML matrix (W4), then serve upgrade (W5) if you want the gate in production.

## How to re-run

```bash
python3 -m koel path-backfill --force --limit 0   # if daily_bars empty
python3 -m koel ml-harden --horizons 1,5
```

Research only — not financial advice.
