# Distributed ML iteration ledger — 2026-07-21

**Status:** strict 90% contract not met  
**Qualification domain:** official CSE outcomes only  
**Final/prospective qualification data consumed:** none

## Protocol corrections

The original distributed baseline was not absolute price direction. It used
cross-sectionally demeaned returns and was vulnerable to flat-price names
becoming predictable relative underperformers.

The corrected protocol now:

- records target dates and rejects partition-boundary crossings;
- keeps flat outcomes in absolute-direction evaluation;
- evaluates official CSE source rows only;
- joins fundamentals strictly after publication;
- adds source, missingness, lag, market-breadth and calendar context;
- uses fixed calibration coverage levels and a calibration LCB floor;
- selects model subsets on calibration only;
- rejects symbols with trailing 60-session flat-return fraction over 40%;
- reports symbol/session concentration and support.

## Frozen data

| Item | Value |
|---|---:|
| Bar snapshot SHA | `69071c0689be1a338e90c95755e28f063aed69552cb75ee6f120d3fb3ea1a24d` |
| Bars | 916,804 |
| Symbols | 200 |
| Filing snapshot SHA | `ce153d84cac292ad124478c18dc83467ddaeee2e9842dc12c276386ac06621a2` |
| Publication-safe filing rows | 3,675 |

## Experiment ledger

| Iteration | Target / change | Result | Decision |
|---|---|---|---|
| v1 one-seed | Relative, old pooled protocol | 89.44%, 322 emits, 0.90% coverage | Reject: wrong target + concentration |
| v1 three-seed | Relative, old pooled protocol | 87.65%, 340 emits, 0.95% coverage | Reject |
| v2 | Absolute, target-date safe, CSE-only | No calibration gate reached 90% | Reject |
| v3 | + filings, LightGBM, two-stage direction/magnitude | No calibration gate reached 90% | Reject |
| v3-domain | + CSE/recency weighting | No calibration gate reached 90% | Reject |
| v4 | + 20 return lags, volume/range lags, market breadth | Only earliest fold reached 90.2% at 41 rows; later folds ≤81.6% / 69.2% | Reject instability |
| v5 | Five-session absolute direction | Best fold calibration pockets ~73% / 83% / 85% | Reject |
| v6 | Corrected CSE relative outperformance | 89.33%, 253 emits, 1.45% coverage, LCB 85.71%, 58 symbols | Reject |
| v6 thin diagnostic | Fixed 0.5% gate, inspected development folds | 95.95%, 148 emits, LCB 92.35%, 28 symbols, max symbol 27.0% | Reject concentration/artifact |
| v7 | v6 plus ex-ante flat-history ≤40% | 77.18%, 149 emits, 53 symbols, no stable folds | Reject; confirms artifact |

## Why the thin relative result is invalid

The v6 diagnostic was dominated by names with very high flat-close rates:

| Symbol | Share of 148 emits | Recent flat-close rate |
|---|---:|---:|
| `ASPH.N0000` | 27.0% | 61.7% |
| `CITW.N0000` | 16.9% | 64.6% |
| `MULL.N0000` | 16.2% | 48.3% |
| `BERU.N0000` | 9.5% | 46.7% |

For a flat stock, a positive market day mechanically creates a negative
cross-sectional label. The model learned stale relative underperformance,
not broad predictive skill. Once this behavior was excluded ex ante, precision
collapsed to 77.18%.

## Current conclusion

The honest result is not “almost 90% absolute direction.” With current
price/fundamental information:

- absolute direction peaks well below 90% in later regimes;
- the only >90% relative pocket is sparse and illiquidity-concentrated;
- the 500-emission qualification requirement cannot be supported by the
  available official-CSE history at a conservative gate;
- further threshold/tree grinding on these exposed development folds would be
  overfitting, not improvement.

## Next valid work

1. Accumulate append-only prospective CSE shadow outcomes.
2. Accrue order-book, foreign-flow and market-summary history.
3. Add a GPU temporal model as a predeclared challenger, not as a guaranteed fix.
4. Evaluate new candidates on fresh prospective periods; do not consume the
   delayed-development buffer to rescue a failed model.
5. Keep absolute direction and relative outperformance as separate products and
   metrics.

Research only — not financial advice.
