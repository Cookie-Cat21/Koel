# koel Edge vs CSEPal — Master Plan + 30-Loop Agentic Strategy

**Status:** Active planning (2026-07-19)  
**Live:** https://koel-cse.vercel.app  
**Authority:** [CLAUDE.md](../../CLAUDE.md) · [DASH_CAKE_CHERRY.md](DASH_CAKE_CHERRY.md) · [CHIME_MASTER_PLAN.md](CHIME_MASTER_PLAN.md) · [ARDENO_UI_MASTER_PLAN.md](ARDENO_UI_MASTER_PLAN.md) · [UI_PATTERN_MINING_2026-07-19.md](UI_PATTERN_MINING_2026-07-19.md)  
**Competitor reference:** CSEPal dense screener (observed UI only — **do not scrape**)

---

## 0. North star (how we win)

**Do not become CSEPal.** Beat them where they are weak.

| Dimension | CSEPal | koel edge |
|---|---|---|
| Density | 20-column fundamentals + TA screener | **Decision density** — fewer columns, inline viz, progressive disclosure |
| Alerts | Browser / in-app style | **Telegram push when the tab is closed** (cherry) |
| Research | Raw ratios | **Explainable scores + ownership map + people influence** (NFA) |
| Trust | Opaque freshness | **Poller age chips, health beam, fire audit (“Telegram sent ✓”)** |
| Speed | Page-heavy grids | **Sub-200ms browse → drawer → alert** |

**One-liner:** koel = daily CSE dash + research overlays + Telegram cherry. CSEPal = desk screener. Different jobs; we steal their *feel of completeness* without their terminal.

---

## 1. Hard fence (cannot wish away)

Copied from constitution — loops that violate these are **auto-fail**:

1. No portfolio / tax / broker sync (until explicit P2+ unlock)  
2. No heavy multi-filter quant screener / trading terminal  
3. No full TA chart suite (MACD/BB *as a column farm* banned; optional thin labels later)  
4. `web/` = Postgres only — no cse.lk from dash  
5. License: MIT/Apache only — **REJECT** React Bits (Commons Clause), DaisyUI plugin, Cult Pro, 21st Financial Dashboard packs, AGPL forks  
6. Compliance: NFA everywhere; no competitor scrape  
7. Brand: no purple glow, cream+terracotta, broadsheet density porn  

---

## 2. Data reality (what we can compute today)

Neon snapshot (2026-07-19) — plan from truth, not wishlist:

| Metric family | Raw readiness | Board coverage | Plan phase |
|---|---|---|---|
| Last / change / sector / mcap | `price_snapshots` | ~full | **Now** (densify UI) |
| 1W / 1M / 3M / ~1Y returns | `daily_bars` | ~268 `.N0000` | **Phase A** |
| ATR / 52W / SMA / MACD / BB labels | OHLC in `daily_bars` | ~268 | **Phase B** (labels, not column farm) |
| EPS / EPS YoY / rough P/E | `filing_metrics.eps_basic` | ~289 | **Phase A** |
| NAV / P/B / ROE / DY | Weak (equity ~32 nodes; no DY store) | sparse | **Phase C** (extract first) |
| Ownership / people | Graph + CSE boards | 278 nodes / 271 boards | **Shipped — polish** |
| Telegram fire audit | `alert_log` | users with rules | **Phase A** (UI proof) |

**Implication:** Catch-up is **not** “build CSEPal grid.” It is (1) densify cake with data we already have, (2) close NAV/ROE gaps via extract, (3) keep cherry + research as the moat.

---

## 3. UI pattern inventory (from Ardeno bookmark crawl)

Subagents visited Tremor, HyperUI, Watermelon, shadcnblocks, shadcn, 21st, Cult, DaisyUI, Magic UI (2026-07-19). Details: [UI_PATTERN_MINING_2026-07-19.md](UI_PATTERN_MINING_2026-07-19.md) + [ARDENO_UI_MASTER_PLAN.md](ARDENO_UI_MASTER_PLAN.md).

### KEEP / ADAPT (fence-legal)

| Pattern | Source | koel target |
|---|---|---|
| Spark / inline data bar | Tremor | `/market` cards & table cells |
| Bar list (movers / sectors) | Tremor | `/overview` |
| Category bar (appetite) | Tremor | `/overview` (already have gauge — densify) |
| Tracker strip (session / fires) | Tremor | `/alerts/history`, `/health` |
| Stats / badges / empty states | HyperUI | all cake routes |
| Details list + timeline | HyperUI | `/symbols/[symbol]` |
| Filter chips (sector, leadership) | HyperUI | `/market`, `/people` |
| Bento overview | shadcnblocks free | `/overview` |
| Data-table (optional dense mode) | shadcn | `/market` toggle — **≤6 columns default** |
| Drawer detail (mail-dashboard layout) | Watermelon pattern | `/market` → symbol drawer |
| Shift-card hover disclosure | Cult free | symbol cards |
| Animated beam | Magic UI MIT | `/health` only |
| Semantic status colors | DaisyUI *patterns* | alerts pending/fired |

### REJECT

React Bits · DaisyUI npm · Cult Pro / shaders · 21st Financial Dashboard packs · Tremor Planner / chart walls · Apple Cards on signed-in dash · Watermelon Premium · CSEPal column clones · purple/indigo defaults

---

## 4. Capability roadmap (catch-up without becoming them)

### Phase A — Feel complete with data we have (loops 1–12)

**Cake densify**

| ID | Deliverable | Acceptance |
|---|---|---|
| A1 | `/market` card grid + optional table (≤6 cols): symbol, last, Δ%, spark, sector, actions | Not a screener; sector chip filter only |
| A2 | Symbol drawer (chart + disclosures + Watch/Alert) | No full page reload |
| A3 | Overview bento: indexes · appetite · top movers bar-list · sector chips · last Telegram fire | Above-fold pulse |
| A4 | Returns chips on symbol detail: 1W / 1M / 3M / 1Y from `daily_bars` | Null-safe; NFA |
| A5 | Filing strip on symbol: latest EPS + YoY when `filing_metrics` exists | No fake NAV |
| A6 | Alert history “Telegram sent ✓” proof + test-fire affordance | Cherry visible in cake |

**Cherry harden**

| ID | Deliverable |
|---|---|
| A7 | Bot ↔ dash parity checklist green |
| A8 | Quiet hours / mute (if not shipped) |
| A9 | Fire latency SLO chip on `/health` |

### Phase B — Thin “intel labels” (loops 13–20)

Computable from bars — **badges on symbol detail / optional market column**, not CSEPal’s TA farm.

| ID | Label | Source |
|---|---|---|
| B1 | 52W position % | `daily_bars` |
| B2 | vs SMA50 % | `daily_bars` |
| B3 | ATR% (14) | OHLC |
| B4 | MACD bias BULL/BEAR | close series |
| B5 | BB pos / squeeze | OHLC |

UI: one “Tech” popover on symbol — **never** 6 sticky screener columns.

### Phase C — Fundamentals catch-up (loops 21–26)

| ID | Work |
|---|---|
| C1 | Extract / persist NAV (or equity) from annual PDFs → board coverage |
| C2 | Derive P/B where NAV+price exist |
| C3 | ROE when profit + equity exist |
| C4 | Dividend yield only from honest CSE/filing fields (no invent) |
| C5 | Light Browse filters: sector + Δ% + “has EPS” (constitution **P1** amend) |

Still banned: 20-filter builder, Best P/E top-10 casino boards as product core.

### Phase D — Moat deepen (loops 27–30)

| ID | Work |
|---|---|
| D1 | Signal Board explainability polish (reasons always visible) |
| D2 | Ownership + people cross-links from symbol drawer |
| D3 | Cmd+K → watch → alert ≤30s path |
| D4 | Marketing proof: Telegram cherry vs “browser-only alerts” |
| D5 | Adversarial pass: “trading terminal?” → strip |

---

## 5. Agentic loop protocol (30 loops)

### Loop template (every iteration)

```
1. SCORE   — run rubric (§5.1), write loop-N score to SCORECARD
2. HYPOTHESIS — one improvement that raises the lowest rubric axis
3. MINE    — optional: 1 Ardeno source (Tremor/HyperUI/shadcn/…) for pattern
4. IMPLEMENT — smallest fence-legal diff (one concern)
5. VERIFY  — typecheck + lint + route smoke + live/demo screenshot if UI
6. ADVERSARIAL — terminal? advice? license? brand anti-pattern?
7. COMMIT  — descriptive message; update SCORECARD + THIRD_PARTY if needed
8. STOP RULE — if score Δ < 0.5 for 3 loops OR fence violate → pivot theme
```

**Concurrency:** ≤4 agents; disjoint files.  
**Budget:** 30 loops total across Phases A→D (not 30 clones of the same table).

### 5.1 Rubric (0–10 each; target ≥8 average by loop 30)

| Axis | What “10” looks like |
|---|---|
| **Cake density** | Overview answers “what matters today?” in one viewport |
| **Cherry proof** | User sees Telegram delivery without leaving dash |
| **Research trust** | Scores/ownership/people always explained + NFA |
| **Speed** | Browse → alert path ≤30s; no dead empty states |
| **Honesty** | No fake NAV/ROE; nulls labeled; poller age visible |
| **License/brand** | Zero rejected kits; koel tokens only |
| **Differentiation** | Could not be mistaken for CSEPal/Tracker Pro |

**Composite** = mean(axes). Log each loop in `docs/factory/passes/EDGE_LOOP_SCORECARD.md`.

### 5.2 Loop theme schedule

| Loops | Theme | Primary routes |
|---|---|---|
| 1–3 | Baseline score + empty/stale honesty | `/overview`, `/health` |
| 4–8 | Market densify (cards, sparks, drawer) | `/market` |
| 9–12 | Cherry proof + alert UX | `/alerts`, history |
| 13–16 | Returns + EPS strip on symbol | `/symbols/[id]` |
| 17–20 | Tech labels popover (B1–B5) | symbol |
| 21–24 | NAV/ROE extract + P/B where honest | engine + symbol |
| 25–27 | Light P1 filters + Signal Board polish | `/market`, `/signals` |
| 28–30 | Cross-link graph/people + adversarial strip + marketing proof | graph, people, landing |

### 5.3 Per-loop agent roles

| Role | Job |
|---|---|
| **Scout** | Visit 1 bookmark site; propose ≤3 patterns with license |
| **Builder** | Implement one hypothesis |
| **Critic** | Rubric + adversarial; may force revert |
| **Verifier** | CI + live koel-cse.vercel.app smoke |

Orchestrator keeps a running “lowest axis” pointer so loops do not over-optimize vanity UI.

---

## 6. Success metrics (product)

| Metric | Target by end of 30 loops |
|---|---|
| Rubric composite | ≥ 8.0 |
| `/market` default columns | ≤ 6 (+ spark) |
| Symbols with returns chips | ≥ 250 |
| Symbols with EPS strip | ≥ 250 |
| Symbols with honest NAV | ≥ 150 (stretch) |
| Telegram proof visible | Yes on overview + history |
| Time watch→alert | ≤ 30s |
| License incidents | 0 |
| “Looks like CSEPal?” blind test | No |

---

## 7. Explicit never (even if loops ask)

- CSEPal clone grid (EPS+NAV+ROE+DY+MACD+ATR+SMA+BB as sticky columns)  
- Scrape CSEPal / Tracker Pro  
- Portfolio / tax / payments (until P2+ constitution amend)  
- Buy/sell language on Signal Board  
- React Bits / Cult Pro / DaisyUI plugin / 21st finance packs  

---

## 8. Relation to older plans

| Doc | Role |
|---|---|
| `CHIME_MASTER_PLAN.md` | Fence-max cake/cherry waves — still authoritative |
| `ARDENO_UI_MASTER_PLAN.md` | Kit reject list + prior 10 UI loops |
| `UI_PATTERN_MINING_2026-07-19.md` | Raw bookmark crawl notes |
| **This doc** | Competitive strategy vs CSEPal + **30-loop execution program** |

Phased Tracker unlocks in CHIME_MASTER_PLAN §G still apply: light screener only after cake+cherry green.

---

## 9. Immediate next action (loop 1)

1. Create `docs/factory/passes/EDGE_LOOP_SCORECARD.md` with baseline rubric scores from live koel.  
2. Loop 1 hypothesis: Overview “Last Telegram fire” + poller age honesty (cherry proof).  
3. Do **not** start NAV extract or TA labels until loops 1–12 raise Cake + Cherry axes.

---

*Information tool, not investment advice. Competitive analysis is product strategy — not a solicitation to deal in securities.*
