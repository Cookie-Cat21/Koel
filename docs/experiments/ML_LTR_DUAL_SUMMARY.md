# ML LTR + dual-target summary

Latest run: `ml_ltr_dual_20260717T091324Z.md` (200 symbols · 46,892 bars · purged panel)

**Decision:** `GO_LTR+VOL`

## What cleared

| Probe | Best | Metric | vs baseline |
|---|---|---|---|
| Learn-to-rank | `xgb_pairwise` | RankIC **0.269** · spread **+2.08%** | HGB reg 0.231 (**Δ +0.038**); HGB clf 0.266 (near-tie) |
| Volatility target | `hgb_vol` abs next-day ret | RankIC **0.378** · big-move P@25% **0.46** | Far above direction models |
| Large-move labels | HGB reg on \|y\|≥day median | RankIC **0.304** · hit **0.619** | Full-panel RankIC 0.234 |
| Liq × turnover regime | LGB on **low_turnover** | RankIC **0.316** | High-turnover only 0.180 |

## What did not

| Probe | Status | Note |
|---|---|---|
| Multi-day proxy labels (h=2/5/10) | Weaker | Full RankIC falls 0.23 → 0.05 as horizon grows |
| `xgb_ndcg` | Underperformed | RankIC 0.199 < HGB reg |
| Market summary (B-002) | **BLOCKED_ACCRUING** | 2 rows only — keep nightly upsert |
| Order book (B-001) | **OPEN_ACCRUING** | Seeded 5 symbols; need multi-day history via poller |
| Buy-in notice→symbol | **BLOCKED** | API company field is always "TRADING AND MARKET SURVEILLANCE" |
| Filing YoY features | **UNDERPOWERED** | 0 `filing_comparisons` in this DB |
| Macros / news sentiment | **DEFERRED** | `docs/THIRD_PARTY_DATA.md` |

## Product takeaway

1. **Ship ranking + vol sizing**, not always-on direction. Vol is the strongest short-horizon target.
2. **Prefer `xgb_pairwise` (or keep HGB clf)** for cross-section scores; judge RankIC/spread, not hit rate.
3. **Lean into low-turnover / large-move selective emits** — matches gated/p90 path already in Loop C.
4. **Accrue microstructure**; do not re-grind path-only trees until B-001/B-002 deepen.

Promote gate used: LTR RankIC ≥ 0.03 and Δ vs HGB reg ≥ +0.01 → `GO_LTR`; vol RankIC ≥ 0.05 → `+VOL`.

CLI: `python3 -m koel ml-ltr-dual` (optional `--limit N`).

**Shipped:** see `ML_LTR_SHIP.md` — `ml-ltr-ship` promoted LTR+vol champion;
serve via `--mode gated_ltr` / `hpe_with_ltr_fallback` (`ML_LTR_SERVE=1`).

Research only — not financial advice.
