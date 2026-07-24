# DE blend models — nested relative/h1 fpv2 (2026-07-24)

Research only — not financial advice. SuccessContract **still unmet**.

## Run identity

| Field | Value |
|---|---|
| Matrix | `feature_pack_v2` / relative / h1 / CSE |
| Models | `blend_de_lgb`, `blend_de_ridge` |
| Exhaust dir | `/tmp/cpu-exhaust-rel-h1-blends` |
| Summary JSON | `cpu_exhaust_rel_h1_blends_summary.json` |

---

## Nested RankIC vs frozen champion

Frozen: `xgb_two_stage` **0.2861**.

| Model | RankIC | Δ vs frozen | Beats baseline |
|---|---:|---:|:---:|
| `blend_de_lgb` | **0.2557** | −0.0304 | yes |
| `blend_de_ridge` | 0.2485 | −0.0376 | no |
| `double_ensemble_native` | 0.2553 | — | yes |

**Verdict:** DE+LGB/Ridge blends **do not challenge** RankIC champion. Lever
**exhausted**.

---

## Selective gates

**NOT MET** — all models **0 emits**.

---

## Cost @112 bps

Best net: `blend_de_lgb` **+0.58%** (slightly above frozen DE persist +0.49%)
but selective contract still false — no Goal A unlock.

---

## Decision

- **Exhausted** — blend models killed on fpv2 matrix.
- Frozen champions retained.
- All serial offline levers for this session **complete**; awaiting E7
  non-partial shadow after 14:35 SLT.
