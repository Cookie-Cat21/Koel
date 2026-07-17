# Experiment backlog (Loop C)

Priority order — research agent picks the **top open** item each cycle.
Initial seed from force-find ledger + factor expansion waves.

| id | priority | status | hypothesis | protocol | kill if |
|---|---:|---|---|---|---|
| B-001 | 10 | OPEN | Persist order-book imbalance history → liquidity shock features | purged panel | RankIC lift &lt; 0.005 |
| B-002 | 20 | OPEN | Daily market summary (turnover / foreign) as regime features | purged panel | no keep vs fin_rich |
| B-003 | 30 | DEAD | Denser YoY (finish PDF drain) → always-on mean ≥ 0.62 | ml-always-on | &lt; +0.005 after full drain — hit 0.595 vs baseline 0.593 (no-keep) |
| B-004 | 40 | KEEP-PARTIAL | Per-regime HPE gate thresholds (up/down/flat) | ml-precision90 | regimes alone ~equal; conf×regime lifts up_low to ~0.77 @ thr=0.6 |
| B-005 | 50 | KEEP | Meta-label / conf gate: emit when conf≥0.55 | purged + gate | **KEEP** gated hit 0.7268 @ cov 0.11 — promoted champion `challenger_gated_c55_20260717` |
| B-006 | 60 | OPEN | Rolling 120d train window vs expanding | Loop B challenger | worse fold robustness |
| B-007 | 70 | OPEN | Interaction: filing_recent × range_20d | feature add | importance &lt; 1% × 3 cycles |
| B-008 | 80 | OPEN | Target: next-day vol-scaled return | label change | RankIC not ≥ hit-only stack |
| B-009 | 90 | DEAD | Announcement count features alone | — | already no-keep in ledger |
| B-010 | 100 | KEEP | Protocol audit: shuffle labels → hit≈0.5 | audit | **PASS** mean_hit=0.524 across 8 folds |

**Anti-plateau:** after 3 consecutive no-keeps, next cycle must be data acquisition (B-001/B-002), target engineering (B-008), or protocol audit (B-010).

**Current champion (serve):** `challenger_gated_c55_20260717` — gated always-on, thr from `data/ml_artifacts/gate_calibration.json` (≈0.45–0.55). Mode: `ml-forecast-unified --mode gated`.

Research only — not financial advice.
