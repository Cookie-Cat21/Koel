# Edge loop scorecard — koel vs CSEPal strategy

**Plan:** [KOEL_EDGE_VS_CSEPal_MASTER_PLAN.md](../KOEL_EDGE_VS_CSEPal_MASTER_PLAN.md)  
**Live:** https://chime-cse.vercel.app  

Scores 0–10 per axis. Target composite ≥ 8.0 by loop 30.

| Loop | Date | Cake | Cherry | Research | Speed | Honesty | License | Diff | Composite | Hypothesis / result |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 2026-07-19 | 6.5 | 7.0 | 7.5 | 6.0 | 7.0 | 9.0 | 7.5 | **7.2** | Baseline: full graph/people shipped; market still thin (price/Δ only); Telegram proof weak in cake UI |
| 1–3 | 2026-07-19 | 7.5 | 8.5 | 7.5 | 6.5 | 8.0 | 9.0 | 8.0 | **7.9** | Overview: Last Telegram fire + snapshot age StatCards; DeliveryBadge on recent fires |
| 4–8 | 2026-07-19 | 8.0 | 8.5 | 7.5 | 7.0 | 8.0 | 9.0 | 8.0 | **8.0** | Market light filters: sector chips + Has EPS (P1, not screener) |
| 9–12 | 2026-07-19 | 8.0 | 8.5 | 7.5 | 7.0 | 8.0 | 9.0 | 8.0 | **8.0** | Cherry proof visible on overview (same as 1–3); history already had badges |
| 13–16 | 2026-07-19 | 8.5 | 8.5 | 8.0 | 7.0 | 8.5 | 9.0 | 8.5 | **8.3** | Symbol: 1W/1M/3M/1Y returns + EPS/YoY strip from daily_bars / filing_metrics |
| 17–20 | 2026-07-19 | 8.5 | 8.5 | 8.0 | 7.0 | 8.5 | 9.0 | 8.5 | **8.3** | Symbol Tech strip: SMA50 / ATR% / MACD bias / BB / 52W (labels only) |
| 21–24 | 2026-07-19 | 8.5 | 8.5 | 8.0 | 7.0 | 9.0 | 9.0 | 8.5 | **8.4** | Honest Book strip: NAV/P/B/ROE only when equity confidence medium/high |
| 25–27 | 2026-07-19 | 8.5 | 8.5 | 8.0 | 7.5 | 9.0 | 9.0 | 8.5 | **8.4** | Light Browse filters live; Signal Board left as shipped |
| 28–30 | 2026-07-19 | 8.5 | 8.5 | 8.5 | 7.5 | 9.0 | 9.0 | 8.5 | **8.5** | Symbol already cross-links Ownership map + People; adversarial: no TA column farm |

### Baseline notes (loop 0)

- **Cake:** Overview + indexes + appetite exist; `/market` lacks sparks/drawer/returns.  
- **Cherry:** Bot+rules work; dash under-shows “Telegram sent” audit.  
- **Research:** Ownership 281 / 107 linked; people ~1471 — strong moat.  
- **Speed:** Demo login OK; card→alert path not optimized.  
- **Honesty:** Filing EPS available ~289; NAV sparse (~32) — must not fake.  
- **License/Diff:** Fence intact; not a CSEPal clone.

### Ship notes (loops 1–30 batch)

- Helpers: `period-returns.ts`, `tech-labels.ts`, `fundamentals.ts` + unit harness.
- Fence held: no 20-column screener; nulls stay null; NAV only with honest equity confidence.
- Deferred (explicit): symbol drawer without reload, spark column on market cards, quiet hours UI, NAV extract densification beyond existing graph equity.
