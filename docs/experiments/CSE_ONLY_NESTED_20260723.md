# CSE-only snapshot — nested relative/h1 baseline trio (2026-07-23)

Research only — not financial advice. No buy/sell language. SuccessContract
**not evaluated** — nested protocol could not run.

## Run identity

| Field | Value |
|---|---|
| Matrix | CSE-only bars export / relative / h1 |
| Snapshot | `/tmp/koel-cse-snapshot-split` (`dataset=cse`, split-adjusted) |
| SHA | `99b7e0f45ec8798a5c8fc225a92892dfbb7cb5f92ff447a8a3013c251e434a2a` |
| Date span | 2025-07-17 → 2026-07-22 (~248 calendar days) |
| Rows / symbols | 70 089 bars / 297 symbols |
| Models | `xgb_two_stage`, `hgb_two_stage`, `double_ensemble_native` |
| Nested | 3 folds × seeds 0,1,2 (requested) |
| Exhaust dir | `/tmp/cpu-exhaust-rel-h1-cse` |
| Summary JSON | `cpu_exhaust_rel_h1_cse_summary.json` |

Export log: `/tmp/koel-cse-export.log`. Manifest: `/tmp/koel-cse-snapshot-split/manifest.json`.

---

## Outcome: **KILLED — insufficient history**

All three baseline models failed at family screen with:

```text
ValueError: not enough history for requested nested split
```

- `nested_per_model`: **null**
- `nested_contract_met`: **null**
- `any_beats_baseline`: **false**
- Nested prediction shards: **0** (post-process selective/cost skipped)

The CSE-only Postgres export retains official CSE source rows only. That window
is too short for the standard h1 nested split protocol (6678-date full matrix
used by frozen champions). This is a **data-span kill**, not a model regression.

---

## Comparison vs frozen champions

| Metric | Frozen (full matrix) | CSE-only |
|---|---|---|
| RankIC `xgb_two_stage` | **0.2861** | n/a (no nested) |
| Selective best (xgb) | 74 emits / 0.770 prec / LCB 0.681 | n/a |
| DE persist net@112 | **+0.49%** | n/a |
| SuccessContract | **false** | **not evaluated** |

Frozen references: `cpu_exhaust_rel_h1_summary.json`, `SELECTIVE_GATES_20260723.md`,
`ML_SPLIT_COST_COMPARE_20260723.md`.

---

## Verdict

CSE-only nested baseline trio **does not unlock Goal A or Goal B** on this
export. Do not treat CSE-only bars as a substitute matrix for champion
comparison until history depth matches the nested protocol minimum (or protocol
is explicitly relaxed with a new matrix ID and frozen thresholds).

**Next:** retain full split-adjusted matrix for W1/W2 work; CSE-only export
remains useful for poller QA / bar-quality checks only.

## Promotion contract

**Contract: NOT MET** (unchanged). No `forecast_points`. Frozen RankIC champion
(`xgb_two_stage` 0.2861) and split-adjusted cost champion (DE persist +0.49%)
**retained**.
