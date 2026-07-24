# Universe filter liq_v3 — nested relative/h1 (2026-07-23)

Research only — not financial advice. No buy/sell language. SuccessContract
**still unmet** — `nested_contract_met: false`; no promotion.

## Run identity

| Field | Value |
|---|---|
| Matrix | `liq_v3` / relative / h1 / CSE |
| Snapshot | split-adjusted (`c135679786b5602…`) |
| Filter | `--universe-filter liq_v3` (ADV gate off, flat60 <=0.40, CSE sessions >=5) |
| Models | `xgb_two_stage`, `hgb_two_stage`, `double_ensemble_native` |
| Nested | 3 folds x seeds 0,1,2 |
| Exhaust dir | `/tmp/cpu-exhaust-rel-h1-liqv3` |
| Summary JSON | `cpu_exhaust_rel_h1_liqv3_summary.json` |
| Nested JSON | `cpu_exhaust_rel_h1_liqv3_nested.json` |

Spec: `UNIVERSE_FILTER_LIQ_V3_SPEC.md`. Parent plan:
`ML_EXHAUST_TO_CONTRACT_MASTER_PLAN.md` §W2.

Sample impact: **636,455 -> 35,377** rows after the flat-only filter. This is
still **<100k**, so the W2 continuation floor fails. Nested test rows: **18,215**
over 117 sessions.

**Kill signal:** `liq_v3` removed ADV but remained collapsed at the same order as
`liq_v1`/`liq_v2`; flat-fraction alone collapses hybrid history for this snapshot.

---

## Nested RankIC vs frozen h1 champions

| Model | Frozen RankIC | liq_v3 RankIC | Delta | net@112 |
|---|---:|---:|---:|---:|
| **`xgb_two_stage`** | **0.2861** | 0.2227 | **-0.0634** | -1.49% |
| `hgb_two_stage` | 0.2816 | 0.2138 | -0.0678 | -1.76% |
| `double_ensemble_native` | 0.2566 | 0.1785 | -0.0781 | -1.88% |

### Headline

- **W2 killed/exhausted for this snapshot:** `liq_v3` retains only ~5.6% of the
  h1 matrix; sample count is far below the 100k stability floor.
- **No RankIC challenger:** best RankIC is xgb 0.2227, still far below the frozen
  xgb h1 champion 0.2861.
- **No selective progress:** nested selective emits are **0**.
- **No cost flip:** all daily net@112 values are negative; best is xgb **-1.49%**.

---

## W2 exit / kill criteria

| Criterion | Fired? | Evidence |
|---|---|---|
| Sample count >=100k post-filter | **No** | 35,377 rows |
| Selective emits >=2x frozen xgb | **No** | 0 vs frozen 74 |
| RankIC within 0.005 of frozen | **No** | best delta -0.0634 |
| net@112 improvement >=0.10 pp | **No** | best -1.49% |

**Verdict:** W2 universe-filter lever is **exhausted/killed** for the current
split-adjusted snapshot. Champions unchanged; SuccessContract **still unmet**.
