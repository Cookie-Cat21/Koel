# fpv2 + adv20 combo nested — relative/h1 (2026-07-24)

Research only — not financial advice. SuccessContract **still unmet**.

## Run identity

| Field | Value |
|---|---|
| Matrix | `feature_pack_v2` + `--sample-weight adv20` / relative / h1 / CSE |
| Snapshot | split-adjusted (`fc4d730527d4821f…`) |
| Sector map | `/tmp/koel-sector-map.json` |
| Models | `xgb_two_stage`, `hgb_two_stage`, `double_ensemble_native` |
| Nested | 3 folds × seeds 0,1,2 |
| Exhaust dir | `/tmp/cpu-exhaust-rel-h1-fpv2-advw` |
| Post-process | `/tmp/cpu-post-rel-h1-fpv2-advw` |
| Summary JSON | `cpu_exhaust_rel_h1_fpv2_advw_summary.json` |

---

## Nested RankIC vs frozen + component levers

| Model | Frozen RankIC | fpv2 only | adv20 only | fpv2+adv20 | Δ vs frozen |
|---|---:|---:|---:|---:|---:|
| **`xgb_two_stage`** | **0.2861** | 0.2865 | 0.2862 | **0.2867** | **+0.0006** |
| `hgb_two_stage` | 0.2816 | 0.2836 | 0.2824 | 0.2841 | +0.0025 |
| `double_ensemble_native` | 0.2566 | 0.2553 | 0.2502 | 0.2539 | −0.0027 |

### Headline

- **No RankIC challenger.** Best xgb 0.2867 is **+0.0006** above frozen — under
  W1 +0.005 threshold. Combo marginally beats fpv2-only (+0.0002) and adv20-only
  (+0.0005) but within noise.
- DE persist **+0.59%** net@112 vs frozen **+0.49%** (+0.10 pp) — at W1 net
  threshold borderline but selective contract **still false**; not promotion path.

---

## Selective gates (90% contract)

**NOT MET.**

| Model | Contract | Precision | LCB | Emits | fpv2-only |
|---|:---:|---:|---:|---:|---|
| `xgb_two_stage` | false | 0.760 | 0.685 | 104 | 105 / 0.688 |
| `hgb_two_stage` | false | 0.714 | 0.628 | 84 | 73 / 0.662 |
| `double_ensemble_native` | false | — | — | 0 | 0 |

Combo does not improve selective LCB vs fpv2-only; contract **still false**.

---

## Verdict

**EXHAUSTED** — fpv2+adv20 combo does not clear W1 RankIC (+0.005) or selective
90%. Frozen RankIC champion retained. Cost uptick on DE persist noted but
insufficient without Goal A.

Serial queue steps a–c **complete**. E7 non-partial shadow blocked until ≥14:35
Asia/Colombo.
