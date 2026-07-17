# Ardeno UI → Chime master plan

**Date:** 2026-07-17  
**Goal:** Integrate useful patterns from the Ardeno bookmark folder into Chime’s
thin CSE dash + Telegram cherry — **adapt patterns**, never vendor whole kits.

## Fence (non-negotiable)

| Source | License / action |
|---|---|
| HyperUI | MIT — **keep mining** |
| Tremor Charts / Blocks | Apache / MIT — cherry-pick bar-list, badge, tracker; **no** Planner/Overview |
| shadcn/ui (+ free shadcnblocks) | MIT — **extend first** |
| DaisyUI | Patterns only — **no plugin** |
| Watermelon UI | Thin Alert/Table only — skip Premium dashboards |
| Cult UI | Free structure only — **skip Pro / shader heroes** |
| 21st.dev | Per-item MIT after SPDX — **reject** Financial Dashboard wholesale |
| Magic UI Animated Beam | MIT — optional `/health` only |
| React Bits | **REJECT** (Commons Clause) |
| Apple Cards Carousel | **REJECT** for Chime (marketing chrome) |

Product non-goals stay: no portfolio/tax/screener terminal, no purple-glow SaaS,
no AGPL forks, `web/` stays Postgres-only.

## Already shipped (do not re-vendor)

ChangeBadge, StatCard, EmptyState, MoversBarList, DisclosureTimeline, BrowseTable,
FaqSection, NfaFooter / marketing footer, AlertBanner, CakeCherryBanner,
AnnouncementBar, ChatBubble, Steps, shadcn Badge/Select/Alert/AlertDialog,
People dossier + ownership React Flow (hand-rolled).

## Integration waves

### Wave A — People / Ownership (this branch)

| # | Pattern | Source | Target | Status |
|---|---|---|---|---|
| A1 | Generic **RankBarList** | Tremor bar-list | `/people/[id]` peers + seat share | done |
| A2 | **EventTimeline** kit | HyperUI timeline | dossier Across years | done |
| A3 | Wire **StatCard** / **EmptyState** | in-tree kit | dossier KPIs + empties | done |
| A4 | Ownership **KpiStrip** | HyperUI / IndexStrip density | `/graph` | done |
| A5 | Ops **AlertBanner** callout | Tremor/Watermelon thin alert | `/people` refresh honesty | done |
| A6 | **FilterChip** density | HyperUI filters | people All / Leadership | done |
| A7 | Soft-merge / NFA microcopy | brand tokens | dossier + people row | done |

### Wave B — Overview / Market / Alerts

| # | Pattern | Route |
|---|---|---|
| B1 | Health circuit tracker dots | `/health` |
| B2 | Stale poller Alert on overview | `/overview` |
| B3 | History pagination polish | `/alerts/history` |
| B4 | Optional Magic Beam (CSE→Telegram) | `/health` only |

### Wave C — deferred

Lightweight Charts on symbol · full shadcn `Table` extract · announcement category
filters for board events · `marketStatus` poller gating (backend, not UI kit).

## Explicit REJECT backlog

- React Bits (any)
- DaisyUI npm plugin
- 21st Financial Dashboard packs
- Cult Hero Color Panels / Pro
- Tremor Planner / KPI card walls
- Watermelon Premium dashboards
- Apple Cards Carousel on signed-in dash
- Chart walls / portfolio UIs

## Port checklist (each item)

1. Adapt to Chime CSS tokens (no indigo/purple defaults)  
2. Log in `docs/THIRD_PARTY.md`  
3. `npm run typecheck`  
4. Adversarial: “trading terminal / Tracker Pro?” → revert if yes  

## Agentic improvement loops (execution)

Ten loops completed (2026-07-17):

1. `RankBarList` + `FilterChip` kit (Tremor bar-list pattern)
2. `EventTimeline` kit (HyperUI timeline)
3. Dossier `StatCard` KPIs + `EmptyState` empties
4. Ownership `KpiStrip` (companies / links / PDF source)
5. `/people` `AlertBanner` — boards not auto-updated
6. People filter chips (All roles / Leadership) + NFA hint
7. Soft-merge + Across-years honesty microcopy
8. Dossier peers + seat influence via `RankBarList`
9. Across years → `EventTimeline`
10. a11y (focus rings, `aria-pressed`, banner `role=status`) + KPI density

Wave B/C stay planned unless a later pass picks them up.
