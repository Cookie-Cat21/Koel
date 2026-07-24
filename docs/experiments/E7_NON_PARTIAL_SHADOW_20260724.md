# E7 non-partial live shadow — 2026-07-24 post-close

Research only — not financial advice. **E7 still open** (need ≥60 non-partial
scored sessions; have **1**).

## Run

| Field | Value |
|---|---|
| Trigger | tmux `koel-shadow-final` sleep until ~14:35 Asia/Colombo |
| Command | `python3 -m koel.ml.live_shadow --snapshot /tmp/koel-live-final-snapshot-split` |
| Log | `/tmp/shadow-final.log` |
| Export log | `/tmp/shadow-final-export.log` |
| `partial_session` | **false** |

## Emit summary (2026-07-24 issue date)

| Policy | Emits | Gate |
|---|---:|---|
| `shadow_policy_rank_de_persist_v1` | **16** | `shadow_persist_book` |
| `shadow_policy_rank_de_h3_weekly_v1` | **16** | `shadow_h3_weekly_book` |

Also emitted (non-E7): abs policies 173 legs each; selective 1; pressure 11.

Snapshot SHA: `abac62fdb734440c5d503ac9e2a160115a5d16815588f5631ae4f393939887cc`

---

## Neon `forecast_outcomes` counts (post-run)

| model_id | gate | legs | sessions | scored |
|---|---|---:|---:|---:|
| `shadow_policy_rank_de_persist_v1` | `shadow_persist_book` | **16** | **1** | 0 |
| `shadow_policy_rank_de_persist_v1` | `shadow_partial_persist_book` | 38 | 2 | 0 |
| `shadow_policy_rank_de_h3_weekly_v1` | `shadow_h3_weekly_book` | **16** | **1** | 0 |
| `shadow_policy_rank_de_h3_weekly_v1` | `shadow_partial_h3_weekly_book` | 32 | 2 | 0 |

**Non-partial E7 qualification:** 1 session / 16 legs per policy — first
receipt after post-close run. Target ≥60 sessions — **not met**.

Partial canaries from morning smoke (~11:15 SLT) remain excluded from E7/E8
qualification counts.

---

## Verdict

- **W0 wiring confirmed** — non-partial emit path works post-close.
- **E7 incomplete** — accumulate daily non-partial sessions until ≥60.
- **E8 incomplete** — scored_legs still 0 (realized returns pending).
- SuccessContract **still unmet**.
