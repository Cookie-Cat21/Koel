# TradingView chart audit → koel port (user-approved)

**Status:** Approved for Layer A implementation (2026-07-21)  
**Constraint:** Reimplement UX patterns on **koel Postgres + Lightweight Charts**. Do **not** vendor TradingView proprietary code, assets, Pine, or branding. Layer B embed stays for full TV.

Sources audited (public docs):
- [UI elements](https://www.tradingview.com/charting-library-docs/latest/ui_elements/)
- [Toolbars](https://www.tradingview.com/charting-library-docs/latest/ui_elements/Toolbars/)
- [Layouts / drawings / indicators](https://www.tradingview.com/support/solutions/43000692404-layouts-charts-drawings-indicators-and-their-interaction/)
- Live koel Layer B embed (`CSELK:`) for side-by-side compare

---

## 1. How TradingView shows charts (anatomy)

| Zone | What TV puts there | Notes |
|---|---|---|
| **Top toolbar** | Symbol search, resolution (1m/5m/D/W…), chart style (candle/bar/line/area/Heikin), Indicators, Indicator templates, Layout save, Undo, Settings, Fullscreen | Primary chrome |
| **Left drawing toolbar** | Cursor, trend, h-line, v-line, fib, shapes, text, measure, eraser, hide | Analysis tools |
| **Main pane** | Price series + overlay indicators (MA, BB, VWAP…) + drawings | Crosshair + legend |
| **Secondary panes** | Volume, RSI, MACD, Stochastic… | Stacked under price |
| **Bottom timeframes** | 1D / 5D / 1M / 3M / 6M / YTD / 1Y / 5Y / All | Quick range |
| **Right widget bar** | Watchlist, Details, News, Object tree *(Trading Platform)* | Out of koel fence |
| **Account / orders** | Broker panel | **Never** in koel |

Data: TV’s own exchange feeds (CSE often delayed without paid realtime).  
koel data spine stays poller → Postgres.

---

## 2. Port matrix (approved)

### Ship in koel Layer A (this pass)

| TV capability | koel implementation | Data |
|---|---|---|
| Chart styles candle / line / area | Style toggle on expand workbench | `daily_bars` |
| Resolution / ranges | Existing 1D–1Y (keep) | ticks / daily |
| Overlay MAs | SMA(20), SMA(50), EMA(12) | closes |
| Bollinger | BB(20, 2) mid + bands | closes |
| RSI pane | RSI(14) in extra pane | closes |
| Volume pane | Already shipped | volume |
| Legend / OHLC readout | Enhance hover + active indicator legend | — |
| H-line drawing | Click → `createPriceLine` (session drawings) | user local |
| Trend line | Two-click line series | user local |
| Eraser / clear drawings | Clear session drawings | — |
| Marks / events | Disclosure + Telegram fire pins (already) | koel DB |
| Alert lines | Armed `price_above`/`below` (already) | koel DB |
| Crosshair, pan, zoom | LWC (already) | — |

### Keep as Layer B (TradingView embed) — do not rebuild

Pine Script, full fib/gann suite, multi-layout sync, cloud layout save, replay, DOM, broker, object tree, 100+ studies, paid realtime CSE.

### Explicit non-copy

- TradingView logo, fonts, color tokens as brand, widget JS, or Charting Library license
- Using TV quotes for Telegram alert evaluation

---

## 3. Architecture

```
Expand dialog
├── [ koel workbench ]  [ TradingView ]
│        │
│        ├── Left: draw tools (cursor / H-line / trend / clear)
│        ├── Top: style + indicators + koel event toggles
│        ├── LwcPriceChart (series + panes + drawings + markers)
│        └── Footer: NFA + koel legend
└── TV embed (unchanged)
```

Indicators computed client-side from the loaded bar window (`koel-indicators.ts`).  
Drawings are **session-local** (not persisted yet — future: `chart_drawings` table).

---

## 4. Success criteria

1. Expand koel tab exposes style + indicators + draw tools.  
2. SMA/EMA/BB/RSI render on COMB with seeded bars.  
3. H-line and trend drawings place without crashing.  
4. koel event overlays still work alongside indicators.  
5. TV tab still loads for A/B compare.  
6. `scripts/tv_port_improve_loop.py` → 50/50 PASS.  
7. NFA footer unchanged; no TV as alert spine.

---

## 5. Improve loop

`scripts/tv_port_improve_loop.py` — 50 verify cycles (typecheck, source contracts, HTTP expand path, unit helpers). Failures fixed until green; no empty commit farming.
