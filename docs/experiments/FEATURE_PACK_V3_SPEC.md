# Feature Pack v3 — cross-section / momentum append (Goal A chase)

Status: **research-only behind `--feature-pack v3`** on `cpu_exhaust` /
`distributed_worker`. **Not** applied in `live_shadow`.

Parent plan: [ML_EXHAUST_TO_CONTRACT_MASTER_PLAN.md](../factory/ML_EXHAUST_TO_CONTRACT_MASTER_PLAN.md) §W1 / Goal A.

Research only — not financial advice. No buy/sell language. No
`forecast_points` writes.

---

## Identity

| Field | Value |
|---|---|
| `matrix_id` | `feature_pack_v3` |
| Base | Feature Pack v2 (sector-relative 20 cols) |
| Delta | **+10** append-only columns (see below) |
| Target / horizon / domain | `relative` / **h1** / `cse` |
| Sector map | same as v2 (`KOEL_SECTOR_MAP` / `/tmp/koel-sector-map.json`) |

v1/v2 nested runs showed no RankIC materiality. v3 tests whether sector ranks,
liquidity z-scores, vol-scaled returns, and longer momentum unlock selective
emits or +0.005 RankIC.

---

## Append columns (`FEATURE_PACK_V3_NAMES`)

| Column | Definition (point-in-time) |
|---|---|
| `fpv3_sector_rank_ret_1d` | Percentile rank of 1d return within sector peers on `as_of` (market rank if no sector peers) |
| `fpv3_sector_rank_ret_5d` | Same for 5d return |
| `fpv3_adv_cs_z` | Cross-sectional z-score of ADV20 on `as_of` |
| `fpv3_vol20_cs_z` | Cross-sectional z-score of vol20 on `as_of` |
| `fpv3_ret1d_vol_scaled` | 1d return / vol20 |
| `fpv3_mom_20d` | 20-session total return |
| `fpv3_mom_60d` | 60-session total return |
| `fpv3_amihud_20` | Mean \|ret\|/volume over last ≤20 sessions |
| `fpv3_hl_range_20` | Mean (high−low)/price over last ≤20 sessions |
| `fpv3_volume_trend_20` | Second-half vs first-half ADV within last 20 sessions |

---

## Leakage rules

Same as v1/v2: bars `trade_date ≤ as_of` only; same-session cross-section;
sector labels from frozen map; no future fundamentals.

---

## Materiality gates (W1 exit)

Any one of vs frozen champions (`xgb_two_stage` RankIC 0.2861 / DE persist
+0.49%):

- RankIC **+0.005**
- net@112 **+0.10 pp**
- Selective emits **2×** at same calibration coverage grid

If met → unblock W5 on this matrix. Else document kill and keep champions.

---

## Policy IDs

None wired. New immutable IDs only after offline + prospective SuccessContract
and human W6 review.
