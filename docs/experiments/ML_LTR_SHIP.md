# LTR + vol ship

**Status:** SHIPPED · champion promoted `challenger_ltr_gated_20260717T092730Z`

## Ops

```bash
# Evaluate OOS, promote if GO_LTR+VOL gates pass, write forecast_points
python3 -m koel ml-ltr-ship

# Serve (default when ML_LTR_SERVE=1)
export ML_LTR_SERVE=1
python3 -m koel ml-forecast-unified --mode hpe_with_ltr_fallback
# or selective LTR-only:
python3 -m koel ml-forecast-unified --mode gated_ltr
```

## OOS (purged panel, this ship)

| Metric | Value |
|---|---|
| Ranker | `xgb_pairwise` |
| Mean RankIC | **0.264** |
| Vol RankIC | **0.376** |
| Gated hit @ 0.55 | **0.621** (cov ~selective) |
| Live emits | **101** symbols · 404 `forecast_points` |

Promote used the product gate: RankIC ≥ 0.25 + vol RankIC ≥ 0.05 + gated hit ≥ 0.55 (legacy direction champion was 0.727 — ranking/vol is the new primary).

## Product surface

- Gate label: `gated_ltr` → dash Spoke badge **“LTR rank + vol”**
- Forecast magnitude sized by predicted \|next-day return\|
- Low-turnover names get a slightly looser conf threshold (0.50)
- Explainable `path_v5` Signal Board scores unchanged

Research only — not financial advice.
