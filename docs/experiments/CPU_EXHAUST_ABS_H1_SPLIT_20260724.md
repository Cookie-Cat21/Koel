# Absolute h1 split nested + selective denser — 2026-07-24

Research only — not financial advice. SuccessContract **still unmet** on absolute/h1.

## Run identity

| Field | Value |
|---|---|
| Matrix | split-adjusted / absolute / h1 / CSE |
| Snapshot | `/tmp/koel-live-final-snapshot-split` (`fc4d730527d4821f…`) |
| Models | `hgb_bagged`, `xgb_two_stage`, `hgb_two_stage`, `double_ensemble_native` |
| Nested | 3 folds × seeds 0,1,2 |
| Exhaust dir | `/tmp/cpu-exhaust-abs-h1-split` |
| Post-process | `/tmp/cpu-post-abs-h1-split` |
| Denser selective | `/tmp/cpu-selective-abs-h1-dense` |
| Summary JSON | `cpu_exhaust_abs_h1_split_summary.json` |

---

## Nested RankIC vs frozen abs/h1 champion

Frozen baseline: `cpu_exhaust_abs_h1_summary.json`. Champion RankIC **0.2546**
(`hgb_bagged`).

| Model | Frozen RankIC | Split RankIC | Δ RankIC |
|---|---:|---:|---:|
| **`hgb_bagged`** | **0.2546** | 0.2500 | **−0.0046** |
| `xgb_two_stage` | 0.2457 | 0.2457 | 0.0000 |
| `hgb_two_stage` | 0.2419 | 0.2419 | 0.0000 |
| `double_ensemble_native` | 0.2258 | 0.2258 | ~0 |

Split adjustment slightly reduces abs/h1 RankIC (−0.0046 on champion) — consistent
with `ML_SPLIT_ADJUSTED_RESCORE_20260723.md` (~0.2500 on split).

---

## Selective gates (90% contract)

**NOT MET** — **0 emits** for all models under standard and denser coverage grids
(0.001–0.10 coverage sweep on `hgb_bagged`, `xgb_two_stage`, `hgb_two_stage`).

Absolute/h1 selective mining **exhausted** on split-adjusted matrix.

---

## Cost @112 bps

Best: `double_ensemble_native` / `persistence_exit_10_top_bottom_05`
**+0.28%** net@112 on split shards — thin positive but not promotion path
(relative DE persist +0.49% remains cost champion).

---

## Verdict

Shards restored on split snapshot for absolute selective research. No Goal A
unlock; champions unchanged. Lever **exhausted** for absolute selective 90%.

Next: fpv2+adv20 combo nested (relative/h1).
