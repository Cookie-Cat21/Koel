# Absolute / h3 nested — 2026-07-24

Research only — not financial advice. SuccessContract **still unmet** — no
selective 90% unlock; no promotion.

## Run identity

| Field | Value |
|---|---|
| Matrix | absolute / h3 / CSE (no feature pack) |
| Snapshot | split-adjusted (`fc4d730527d4821f…`) — same as 2026-07-24 queue export |
| Models | `hgb_bagged`, `hgb_two_stage`, `xgb_two_stage`, `double_ensemble_native` |
| Nested | 3 folds × seeds 0,1,2 |
| Exhaust dir | `/tmp/cpu-exhaust-abs-h3` |
| Post-process | `/tmp/cpu-post-abs-h3` |
| Summary JSON | `cpu_exhaust_abs_h3_summary.json` |

Queue step 3 of serial run (`koel-safe-queue.sh`). Step 2 (fpv2 rel/h1) failed
on missing deps and was scheduled for recovery after step 4.

---

## Nested RankIC vs frozen champions

| Model | abs/h3 RankIC | abs/h1 frozen | Δ | Sessions | net@112 daily L/S |
|---|---:|---:|---:|---:|---:|
| **`hgb_bagged`** | **0.2061** | 0.2546 | −0.0485 | 111 | −1.21% |
| `xgb_two_stage` | 0.2014 | — | — | 111 | −1.06% |
| `hgb_two_stage` | 0.1912 | — | — | 111 | −1.02% |
| `double_ensemble_native` | 0.1790 | — | — | 111 | −0.18% |

Frozen abs/h1 champion remains `hgb_bagged` **0.2546** — abs/h3 does not beat it.

vs relative/h3 (2026-07-23): rel/h3 xgb **0.2285** > abs/h3 hgb **0.2061**.

---

## Selective gates (90% contract)

**NOT MET** — 0 emits for all four models on the predeclared coverage grid.

| Model | Contract | Emits |
|---|:---:|---:|
| `hgb_bagged` | false | 0 |
| `xgb_two_stage` | false | 0 |
| `hgb_two_stage` | false | 0 |
| `double_ensemble_native` | false | 0 |

Absolute/h3 scores are too sparse for the 500-emit / 0.90 LCB floors.

---

## Cost engineering @112 bps

| Model | Best variant | Net | Gross | Turnover | Sessions |
|---|---|---:|---:|---:|---:|
| **`double_ensemble_native`** | `weekly_5_sessions_top_bottom_05` | **+0.69%** | 1.44% | 0.336 | 111 |
| `xgb_two_stage` | `weekly_5_sessions_top_bottom_05` | +0.04% | — | — | 111 |
| `hgb_bagged` | `weekly_5_sessions_top_bottom_05` | −0.12% | — | — | 111 |

DE weekly book on abs/h3 **+0.69%** net@112 exceeds rel/h3 DE weekly +0.27%
(2026-07-23) but RankIC remains below h1 champions. Review-only; contract
unchanged.

---

## Verdict

- **No RankIC challenger** for abs/h1 or rel/h1.
- Selective 90% **unmet**.
- Cost-positive weekly DE construction on abs/h3 scores is interesting but does
  not clear promotion gates.
- Champions retained. SuccessContract **still unmet**.
