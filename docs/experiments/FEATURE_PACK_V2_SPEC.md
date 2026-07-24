# Feature Pack v2 — sector-relative (Goal A chase)

Status: **research-only behind `--feature-pack v2`** on `cpu_exhaust` /
`distributed_worker`. **Not** applied in `live_shadow`. Same 20-column manifest
as v1; v2 activates true sector-relative returns via an external sector map.

Parent plan: [ML_EXHAUST_TO_CONTRACT_MASTER_PLAN.md](../factory/ML_EXHAUST_TO_CONTRACT_MASTER_PLAN.md) §W1 / Goal A.

Research only — not financial advice. No buy/sell language. No
`forecast_points` writes.

---

## Identity

| Field | Value |
|---|---|
| `matrix_id` | `feature_pack_v2` |
| `feature_schema_version` | `feature_pack_v2` |
| Column manifest | Same as `feature_pack_v1` (20 columns) |
| Delta vs v1 | `fp_rel_ret_1d` / `fp_rel_ret_5d` use **sector** medians; `fp_use_sector=1.0` when label resolved |
| Target / horizon / domain | `relative` / **h1** / `cse` |
| Sector map | `KOEL_SECTOR_MAP` env or `/tmp/koel-sector-map.json` |

v1 nested run showed no materiality with market-only relative columns
(`fp_use_sector=0.0`). v2 is the sector chase: same trees, richer cross-section
signal within sector buckets.

---

## Sector map source

Exported once from Neon `stocks.sector`:

```sql
SELECT symbol, sector FROM stocks WHERE sector IS NOT NULL;
```

Artifacts:

| Path | Purpose |
|---|---|
| `/tmp/koel-sector-map.json` | Default runtime path for `cpu_exhaust --feature-pack v2` |
| `docs/experiments/sector_map_20260723.json` | Checked-in snapshot (296 symbols as of 2026-07-23) |

Loader: `koel.ml.feature_pack_v1.load_sector_map_from_json` /
`koel.ml.feature_pack_v2.load_sector_map_for_v2`.

Symbols are normalized to uppercase. Missing symbols fall back to market-relative
columns for `fp_rel_ret_*` and set `fp_use_sector=0.0`.

---

## Column behavior (delta from v1)

| Column | v1 | v2 |
|---|---|---|
| `fp_rel_ret_1d` | market median fallback | `fp_ret_1d − sector_median_1d` when sector resolved |
| `fp_rel_ret_5d` | market median fallback | `fp_ret_5d − sector_median_5d` when sector resolved |
| `fp_rel_ret_1d_market` | same as `fp_rel_ret_1d` | always market median (unchanged) |
| `fp_rel_ret_5d_market` | same as `fp_rel_ret_5d` | always market median (unchanged) |
| `fp_use_sector` | always `0.0` | `1.0` when symbol has sector label in map |

Sector medians use only symbols with the same sector label **on the same
`as_of` session** (same cross-section panel as nested eval). No future bars,
no future sector remaps.

Implementation: `enrich_feature_pack_v1(..., sector_map=...)` in
`koel/ml/feature_pack_v1.py`; v2 CLI loads map via `koel/ml/feature_pack_v2.py`.

---

## Point-in-time / leakage rules

Same as [FEATURE_PACK_V1_SPEC.md](./FEATURE_PACK_V1_SPEC.md) with sector map
frozen at export time:

1. Bars: `trade_date ≤ as_of` only.
2. Sector medians: peers on **same session** only.
3. Sector labels: static map from snapshot export; no backfill from future data.
4. Poison test: mutating bars with `trade_date > as_of` must not change features
   at `as_of` (covered in `tests/test_ml_feature_pack_v2.py`).

---

## CLI usage

```bash
export KOEL_SECTOR_MAP=/tmp/koel-sector-map.json

python3 -m koel.ml.cpu_exhaust \
  --snapshot /tmp/koel-live-final-snapshot-split \
  --output /tmp/cpu-exhaust-rel-h1-fpv2 \
  --target relative --horizon 1 --evaluation-domain cse \
  --max-flat-fraction 0.40 --screen-top-k 3 \
  --nested-folds 3 --nested-seeds 0,1,2 \
  --skip-hyper --feature-pack v2 \
  --models xgb_two_stage,double_ensemble_native,hgb_two_stage
```

If no sector map file is found, v2 raises at matrix build time (fail loud).

---

## Evaluation protocol

Nested **relative/h1** on split-adjusted snapshot, baseline trio only (no 10k
hyper until materiality gate clears):

- Compare pooled RankIC vs v1 nested (`FEATURE_PACK_V1_NESTED_20260723.md`)
- Secondary: BA / MCC, selective gates on survivors
- Materiality bar: same as master plan W1 (RankIC Δ meaningful vs frozen 0.2861)

---

## Files

| File | Role |
|---|---|
| `koel/ml/feature_pack_v1.py` | Shared enricher + `load_sector_map_from_json` |
| `koel/ml/feature_pack_v2.py` | v2 resolve/load helpers |
| `koel/ml/cpu_exhaust.py` | `--feature-pack v2` wiring |
| `tests/test_ml_feature_pack_v2.py` | Sector PIT + loader tests |
| `docs/experiments/sector_map_20260723.json` | Frozen sector labels |
