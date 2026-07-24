# Ranking models — nested relative/h1 fpv2 (2026-07-24)

Research only — not financial advice. SuccessContract **still unmet**.

## Run identity

| Field | Value |
|---|---|
| Matrix | `feature_pack_v2` / relative / h1 / CSE |
| Models | `xgb_rank_ndcg`, `xgb_rank_pairwise`, `lgb_lambdarank` |
| Exhaust dir | `/tmp/cpu-exhaust-rel-h1-rankers` |
| Summary JSON | `cpu_exhaust_rel_h1_rankers_summary.json` |

---

## Nested RankIC vs frozen champion

Frozen: `xgb_two_stage` **0.2861**.

| Model | RankIC | Δ vs frozen | Beats baseline |
|---|---:|---:|:---:|
| `lgb_lambdarank` | **0.2647** | −0.0214 | yes |
| `xgb_rank_pairwise` | 0.2474 | −0.0387 | no |
| `xgb_rank_ndcg` | 0.1723 | −0.1138 | no |

**Verdict:** Ranking objective models **do not challenge** frozen champion.
Best `lgb_lambdarank` at 0.2647 is **−0.0214** below 0.2861. Lever **exhausted**.

---

## Selective gates

**NOT MET** — all models **0 emits** under 90% contract grid.

---

## Decision

- **Exhausted** — LTR/ranking models killed on fpv2 matrix.
- Frozen champions retained.
- Next serial: DE blends (`blend_de_lgb`, `blend_de_ridge`).
