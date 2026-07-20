# Finance dashboard inspiration → Koel

**Date:** 2026-07-14  
**Method:** Parallel survey (OSS repos + Ardeno bookmark kits). Factory concurrency
cap is **8 preferred / 16 hard** — we did **not** spawn 50 scrape agents or
dump Pro marketplaces (see `DASH_COMPONENT_FILTER.md`).

**Product fence:** Dash cake + Telegram cherry (`DASH_CAKE_CHERRY.md`). Steal
**patterns**, not whole Tracker-Pro clones. `web/` stays Postgres-only.

---

## 1. Best open-source stock / finance dashboards (repos)

| Repo | License | Stack | Steal for Koel | Verdict |
|---|---|---|---|---|
| [tremorlabs/tremor](https://github.com/tremorlabs/tremor) | Apache-2.0 | React + Tailwind | KPI chips, delta badges, spark header layout | **ACCEPT_PATTERN** |
| [tremorlabs/tremor-blocks](https://github.com/tremorlabs/tremor-blocks) | MIT | TSX blocks | status strip, bar-list movers, form layouts, banners | **ACCEPT_PATTERN** (cherry-pick) |
| [tradingview/lightweight-charts](https://github.com/tradingview/lightweight-charts) | Apache-2.0 | Canvas lib | Optional later price series on `/symbols` | **MAYBE** (keep SVG spark first) |
| [arhamkhnz/next-shadcn-admin-dashboard](https://github.com/arhamkhnz/next-shadcn-admin-dashboard) | MIT | Next 16 + shadcn | App shell density, tables, notification list | **ACCEPT_PATTERN** |
| [tristcoil/zero-sum-public](https://github.com/tristcoil/zero-sum-public) | MIT | Next + charts | Index strip, movers, sector strip | **ACCEPT_PATTERN** |
| [Gzeu/CryptoTraderPro](https://github.com/Gzeu/CryptoTraderPro) | MIT | Next + shadcn | Watchlist + alert rules UI, Cmd+K search | **ACCEPT_PATTERN** |
| [adrianhajdin/signalist_stock-tracker-app](https://github.com/adrianhajdin/signalist_stock-tracker-app) | Unclear | Next + Finnhub | Closest product cousin (watch + alerts) | **MAYBE** (UX only until SPDX) |
| [Open-Dev-Society/OpenStock](https://github.com/Open-Dev-Society/OpenStock) | **AGPL-3.0** | Next + shadcn + TV widgets | Watchlist / search UX screenshots | **REJECT code** (look-don’t-fork) |
| [TailAdmin/free-nextjs-admin-dashboard](https://github.com/TailAdmin/free-nextjs-admin-dashboard) | MIT free / Pro stocks | Next | Free KPI/table shell only | **MAYBE** (skip Pro Stocks) |
| [Weebapp003/shadcn-fintech-template](https://github.com/Weebapp003/shadcn-fintech-template) | MIT | Next + shadcn | Ticker + sparklist | **MAYBE** (reject banking walls) |

### Explicit reject (repos)

- OpenStock / AGPL trees — do not fork into Koel  
- Quant / TA terminals, order-book clones  
- Any portfolio + tax + screener “full app” as a drop-in  

---

## 2. Ardeno bookmark folder → Koel

| Bookmark | License | Action |
|---|---|---|
| HyperUI | MIT | **Keep mining** — tables, empties, stats, timeline, pagination |
| DaisyUI | MIT core | Patterns only — **no plugin** beside shadcn |
| Tremor Charts / Blocks | Apache / MIT | Cherry-pick status, bar-list, badges — **no chart walls** |
| shadcn/ui | MIT | **Extend first** — Alert, AlertDialog, Separator, Table |
| Watermelon UI | MIT registry | Thin alerts/tables only — skip full dashboard blocks |
| Cult UI | Free MIT / Pro paid | Free popovers only — **skip Pro heroes** |
| 21st.dev | Per-item (often MIT) | Ops/empty only — **reject** finance-dashboard category wholesale |
| Magic UI | MIT | Animated Beam optional later for health diagram |
| React Bits | MIT + **Commons Clause** | **REJECT** |
| Aceternity (cards/footers/FAQ) | Free comps / Pro blocks | Skip marketing chrome |
| Icons | lucide (already in) | Keep |
| Better Design Tips / WebDev | Tips | Inspiration only |

---

## 3. Ranked components to port next (Koel routes)

Already shipped: StatCard, AlertBanner, ChatBubble, Steps, Faq, Badge, Select,
Armed/Delivery badges, PageHeader, PriceRefresh, EmptyState, sparkline.

| # | Pattern | Source | Route | Effort |
|---|---|---|---|---|
| 1 | **ChangeBadge** (↑↓ %) | Tremor badge-03 / HyperUI | overview, market, watchlist | small |
| 2 | **shadcn Alert** | ui.shadcn | health, symbol stale | small |
| 3 | **AlertDialog** confirm | ui.shadcn | unwatch / cancel alert | medium |
| 4 | **Market table (sm+)** | HyperUI striped table | `/market` | medium |
| 5 | **Movers bar-list** | Tremor bar-list-01 | overview, market | medium |
| 6 | **Disclosure timeline** | HyperUI / Daisy pattern | `/symbols/[symbol]` | medium |
| 7 | **History page X/Y** | HyperUI pagination | `/alerts/history` | small |
| 8 | **Alert form sections** | Tremor form-layout-01 | `/alerts` | small |
| 9 | **Health circuit dots** | Tremor tracker-03 (short) | `/health` | medium |
| 10 | **Search-miss empty** | HyperUI / 21st empty | market, alerts | small |
| 11 | **Cmd+K symbol search** | CryptoTraderPro / OpenStock UX | global | medium |
| 12 | **Dismissible cake/cherry banner** | Tremor banner-04 | overview, alerts | small |
| 13 | **Symbol spark header** | Tremor spark-chart-01 layout | symbol | medium |
| 14 | **shadcn Separator** | ui.shadcn | symbol, health | small |
| 15 | **Lightweight Charts** (optional) | TradingView LWC Apache | symbol later | large |

---

## 4. What we will not do

- Spawn 50–100 agents to scrape Pro packs  
- Vendor Tremor Planner / full SaaS dashboards  
- Import 21st “Financial Dashboard” / stock carousels wholesale  
- Install DaisyUI or React Bits  
- Copy AGPL OpenStock code  
- Replace Telegram push with in-browser-only alerts  

---

## 5. Suggested next build wave

**Wave A (this week shape):** ChangeBadge → shadcn Alert → market table → movers bar-list → AlertDialog  
**Wave B:** disclosure timeline · history pagination · Cmd+K  
**Wave C:** optional LWC on symbol · Magic beam health diagram  

Each port: adapt to Koel tokens → log `THIRD_PARTY.md` → `npm run typecheck && lint` → route regressions → “trading terminal?” adversarial check.
