# Diagnose + iterate summary — path to 70–75% board-wide

**Date:** 2026-07-16  
**Target (user):** mean per-symbol direction hit **70–75% for all companies** (always-on).  
**Status:** **Not met** on always-on board. Closest honest hits documented below.

## Autopsy (`ml-diagnose`)

| Slice | Hit rate | Notes |
|---|---:|---|
| Board pooled | ~0.56 | Global HGB panel |
| Mean per-symbol (n≥20) | ~0.57 | 15/264 symbols ≥70% |
| **HIGH** `\|P−0.5\|≥0.20` | **~0.71** | Already in 70–75% band |
| MID | ~0.60 | |
| LOW | ~0.52 | Drag on the average |

**Who wins (HIGH_HIT vs LOW):**

- Higher `range_20d` / `vol_20d` (more “alive” names)
- Lower `log_price` (cheaper names)
- Recent positive short-horizon returns (`ret_1d` / `ret_5d`)
- Liquidity terciles **do not** cleanly separate winners

**Who loses:** many quiet Food & Beverage / low-vol names (e.g. CTC, DIST, SUN) with almost no HIGH-confidence calls.

Sectors backfilled (271/272); notices mostly unresolved to symbols (3/264) — weak event signal today. Filings empty.

## Levers tried (`ml-iterate` + focused probes)

| Lever | Mean symbol hit | ≥70% syms | Notes |
|---|---:|---:|---|
| baseline panel HGB | ~0.57 | ~12–14 | |
| + cross-section percentiles | ~0.58 | ~12–15 | Best simple lift |
| sector models / vol buckets | ≤ baseline | — | Overfit / no help |
| large-move train (LMT) | ~0.59 | ~14–18 | Best single family |
| LMT + bagged HGB | ~0.59 | ~11 | |
| transfer (80 foreign) + LMT bag | ~0.59 | 13 | HIGH≈0.71 |
| dual-horizon vote | ~0.59 | 12 | |
| **+ dist to 20d high/low** | **~0.593** | **19** | Best always-on so far |
| symbol-adaptive flip | ~0.57 | — | Little help |

Typical lift vs baseline: **+1–2.5pp**, not +13pp.

## Where ~70% *does* appear

1. **Confidence gate (product path):** HIGH bucket **~69–71%** hit (coverage ~8–22% depending on thr).  
2. **Magnitude-conditional:** only score days with `|y_ret| ≥ day-median` → mean symbol **~0.62–0.63**, ~60–67 symbols ≥70% — better, still &lt;0.70 board mean.  
3. **Per-symbol:** ~15–19 names already clear 70% always-on; they look like higher-range / dual-listed / “alive” tickers.

## Honest ceiling (path-only, ~1y CSE)

Always-on direction for **every name every day** is stuck in the **high-50s**.  
Getting **all companies** to a **70–75% average** on that metric needs **new information content**, not another tree depth:

1. **Dense filings / fundamentals** (YoY EPS/rev) joined as-of — currently 0 rows  
2. **Better notice→symbol resolution** (264 notices, 3 resolved)  
3. **Longer history** (still unavailable from public CSE)  
4. Or **change the metric** to confidence-gated / large-move (where 70% is already real)

## Recommendation

| Goal | Do this |
|---|---|
| Show ~70–75% when we speak | Ship **confidence gate** (HIGH band); NFA copy |
| Lift always-on board mean | Prioritize **filing drain + features**, then re-run `ml-iterate` |
| Keep researching path-only | Keep `panel_cs` + LMT (+ high/low distance) as best stack — expect ~59%, not 70% |

## Commands

```bash
python3 -m koel ml-diagnose
python3 -m koel ml-iterate
```

Research only — not financial advice.
