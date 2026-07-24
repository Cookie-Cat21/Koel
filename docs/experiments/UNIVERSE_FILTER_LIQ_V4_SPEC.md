# Universe filter liq_v4 — soft ADV-only (Goal A / W2 revision)

Status: **research-only behind `--universe-filter liq_v4`**. Not wired to
`live_shadow`.

Parent: [ML_EXHAUST_TO_CONTRACT_MASTER_PLAN.md](../factory/ML_EXHAUST_TO_CONTRACT_MASTER_PLAN.md) §W2.

Research only — not financial advice.

---

## Why v4

`liq_v1`–`liq_v3` collapsed hybrid history to ~35k samples (−94%) because
flat-fraction and/or CSE-session floors exclude Yahoo pretrain depth.

Hypothesis: an **ADV-only** floor preserves sample depth while still dropping
illiquid names that poison selective concentration.

## Manifest

| Field | Value |
|---|---|
| name | `liq_v4` |
| min_adv20 | **500** |
| max_flat_fraction_60 | **1.0** (disabled) |
| min_cse_sessions_60 | **0** (disabled) |

Order: base → research enrich → optional feature pack → universe filter →
relative demean.

## Kill / continue

- Post-filter samples **<100 000** → kill (same floor as v2/v3).
- Else nested baseline trio; W1-style materiality vs frozen champions
  (RankIC +0.005 / net@112 +0.10pp / selective emits 2×).
