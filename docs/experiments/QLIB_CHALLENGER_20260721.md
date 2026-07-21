# Qlib challenger report — 2026-07-21

**Status:** ranking signal found; prospective policy blocked  
**Target:** one-session CSE-relative return ranking  
**Qualification domain:** official CSE development folds only

## Data parity

The deterministic Qlib-compatible export completed from the post-close snapshot:

| Item | Value |
|---|---:|
| Ordinary instruments | 196 |
| Rows | 916,443 |
| Sessions | 6,678 |
| First / last | 2000-01-03 / 2026-07-21 |
| Source composite SHA | `5da05d2f65714ed75d0dea58903eb03dac02f2d310312871a8013af1a8d60b32` |

Pinned `pyqlib==0.9.7` was installed in an isolated Python 3.12 environment.
The release converter SHA was verified, all 196 instruments were converted to
native binary storage, and Qlib successfully read JKH close/volume/source
features through 2026-07-21.

The export uses raw `factor=1` bars and is therefore marked
`qualification_allowed=false` until corporate-action adjustment is complete.

## Native parity challengers

Three chronological official-CSE development folds, 122 test sessions:

| Challenger | Rows | RankIC | Balanced accuracy | MCC | Gross top-bottom mean | Net mean @112 bps | Break-even cost |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qlib-parameter LightGBM | 16,779 | 0.2213 | 0.5778 | 0.1541 | 2.24% | -1.32% | 70.4 bps |
| Native DoubleEnsemble approximation | 16,779 | **0.2526** | 0.5763 | 0.1509 | **2.90%** | **-0.69%** | **90.5 bps** |

These are development results, not untouched or prospective evidence.

## Decision

Both challengers clear the research RankIC, balanced-accuracy and MCC point
gates. Neither clears the current cost stress. Neither receives a live policy
ID yet.

Next:

1. run exact Qlib LightGBM and DoubleEnsemble through the pinned isolated
   workflow;
2. complete corporate-action factors;
3. test lower-turnover five-session ranking and score smoothing;
4. require positive post-cost lower-bound evidence before prospective policy
   registration.

## Exact pinned-Qlib smoke

`pyqlib==0.9.7` exact adapters and the isolated three-fold workflow are now
implemented. Fold 0 completed successfully:

| Exact challenger | RankIC | Balanced accuracy | MCC | Net mean @112 bps | Break-even cost |
|---|---:|---:|---:|---:|---:|
| Qlib `LGBModel` | 0.2046 | 0.5805 | 0.1591 | -1.47% | 64.3 bps |
| Qlib `DEnsembleModel` | 0.1933 | 0.5703 | 0.1387 | -1.57% | 59.1 bps |

This validates data/model interoperability, not promotion. The scheduled manual
Qlib workflow will produce the complete exact three-fold report.

Research only — not financial advice.
