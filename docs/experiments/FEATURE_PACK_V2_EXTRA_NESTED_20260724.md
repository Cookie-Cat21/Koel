# Feature pack v2 extra challengers — nested relative/h1 (2026-07-24)

Research only — not financial advice. SuccessContract **still unmet** — no
promotion.

## Run identity

| Field | Value |
|---|---|
| Matrix | `feature_pack_v2` / relative / h1 / CSE |
| Snapshot | split-adjusted (`fc4d730527d4821f…`) |
| Models | `hgb_bagged`, `xgb_lmt`, `hgb_lmt`, `hgb_deep` (+ DE survivor) |
| Nested | 3 folds × seeds 0,1,2 |
| Exhaust dir | `/tmp/cpu-exhaust-rel-h1-fpv2-extra` |
| Post-process | `/tmp/cpu-post-rel-h1-fpv2-extra` |
| Summary JSON | `cpu_exhaust_rel_h1_fpv2_extra_summary.json` |

---

## Nested RankIC vs frozen champion

Frozen baseline: `cpu_exhaust_rel_h1_summary.json` — `xgb_two_stage` RankIC
**0.2861**.

| Model | fpv2-extra RankIC | Δ vs frozen | Notes |
|---|---:|---:|---|
| `xgb_lmt` | **0.2835** | −0.0026 | Best extra challenger; below champion |
| `hgb_lmt` | 0.2816 | −0.0045 | |
| `hgb_bagged` | 0.2742 | −0.0119 | |
| `hgb_deep` | 0.2709 | −0.0152 | |
| `double_ensemble_native` | 0.2553 | — | screen survivor only |

**Verdict:** No RankIC challenger. Best extra model `xgb_lmt` at **0.2835** is
**−0.0026** below frozen `xgb_two_stage` 0.2861 — well under W1 +0.005
materiality. Lever **exhausted**.

---

## Selective gates (90% contract)

**NOT MET** for any model (emits floor ≥500 unmet).

| Model | Contract | Precision | LCB | Emits |
|---|:---:|---:|---:|---:|
| `xgb_lmt` | false | 0.891 | 0.793 | 46 |
| `hgb_lmt` | false | 0.852 | 0.776 | 81 |
| `hgb_bagged` | false | 0.780 | 0.701 | 91 |
| `hgb_deep` | false | 0.788 | 0.707 | 85 |
| `double_ensemble_native` | false | — | — | 0 |

`xgb_lmt` shows high point precision (0.891) but only **46 emits** — far below
500 floor; LCB 0.793 still below 0.90. No Goal A unlock.

---

## Cost engineering @112 bps

Best net: DE `persistence_exit_10_top_bottom_05` **+0.41%** (same as fpv2
baseline trio). Extra challengers did not beat frozen DE persist +0.49% on split
matrix.

---

## Decision

- **Exhausted** — fpv2 extra model families (bagged/LMT/deep) do not clear W1
  RankIC or selective contract.
- Frozen champions retained (`xgb_two_stage` RankIC 0.2861).
- Next serial: ranking models (`xgb_rank_ndcg`, `xgb_rank_pairwise`,
  `lgb_lambdarank`).
