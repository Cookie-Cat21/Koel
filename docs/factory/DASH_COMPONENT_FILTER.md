# Dash component filter — Tremor + bookmark kits

**Status:** Planning / license gate (no bulk vendor into `web/`)  
**Authority:** [CLAUDE.md](../CLAUDE.md) · [DASH_IA.md](DASH_IA.md) · [COMMIT_FACTORY.md](COMMIT_FACTORY.md) §7  
**Stack lock:** Next.js + Tailwind + **shadcn/ui** · free/MIT only · log `THIRD_PARTY.md`

## 0. What we will not do

| Request | Response |
|---|---|
| “Download all Tremor templates into the repo” | **No vendoring.** Tremor Blocks are MIT and cloneable for reference; dumping full SaaS dashboards into Chime invites trading-terminal creep and fights our brand shell. |
| “Spawn 100 sub-agents across bookmark sites” | **No.** Factory concurrency cap is **8 preferred / 16 hard**. We ran a capped parallel survey instead. |
| “Copy everything from 21st / Shadcnblocks / Cult Pro / Watermelon Premium” | **No dump-all.** Marketplace/Pro catalogs need **per-item** license checks; Pro = reject. |
| “Replace thin dash with Tremor Planner/Overview/Dashboard” | **Reject.** Those templates are KPI/chart walls (retention, billing, scenario analysis) — out of fence. |

**Reference clone (local agent disk only, not committed):**  
`tremorlabs/tremor-blocks` — MIT — ~323 TSX blocks in 28 categories (inventoried 2026-07-12).

---

## 1. Chime dash today (so we don’t duplicate)

Already in `web/`:

- Routes: `/`, `/login`, `/watchlist`, `/alerts`, `/alerts/history`, `/symbols/[symbol]`, `/health`
- shadcn primitives: `Button`, `Input`, `Label` only
- Custom: `EmptyState`, `Sparkline` (SVG), toasts, stacked mobile lists, `AppNav`, NFA chrome
- **No** recharts, Tremor, DataTable, sidebar shell

Gaps worth filling (from DASH_IA): Badge for armed/active + delivery status; Select parity; optional Alert for health notices; symbol shortcuts; history limit control — **not** a new chart stack.

---

## 2. Tremor Blocks inventory → filter

Source: [blocks.tremor.so/templates](https://blocks.tremor.so/templates) + GitHub `tremorlabs/tremor-blocks` (MIT).

### Full templates on the marketing page

| Template | Verdict for Chime |
|---|---|
| Planner / Overview / Dashboard / Insights | **REJECT as wholesale import** — chart/KPI/admin walls |
| Solar / Database (marketing sites) | **REJECT** — SaaS marketing, not our Telegram-first product |

Cherry-pick **patterns** from blocks below; do not scaffold a second app from these templates.

### Block categories (ACCEPT / MAYBE / REJECT)

| Category | ~files | Gate | Use in Chime? |
|---|---|---|---|
| `spark-charts` | 6 | **ACCEPT (pattern)** | Study API; prefer keep hand-rolled `sparkline.tsx` unless Tremor Raw spark is thinner |
| `empty-states` | 10 | **ACCEPT** | Inspiration for watchlist/alerts empties (adapt to existing `EmptyState`) |
| `badges` | 13 | **ACCEPT** | Armed / delivery / health chips → prefer **shadcn Badge** first |
| `banners` | 5 | **ACCEPT (minimal)** | Ops notices on `/health` only |
| `status-monitoring` | 10 | **ACCEPT** | Poller health / circuit status patterns |
| `logins` | 10 | **MAYBE** | Demo login already branded; Telegram Login later — don’t paste SaaS login |
| `form-layouts` | 6 | **ACCEPT** | Alert create / watchlist add layout polish |
| `tables` + `table-actions` + `table-pagination` | 30 | **MAYBE** | Mobile-first lists beat terminal tables; only if desktop density needed |
| `filterbar` | 16 | **MAYBE** | Alerts history symbol + limit filters |
| `dialogs` | 9 | **MAYBE** | Confirm unwatch / cancel alert |
| `kpi-cards` | 29 | **REJECT default** | Quote/KPI walls → trading-terminal smell |
| `area/bar/line/donut-charts` + compositions + tooltips | 83+ | **REJECT default** | TA / analytics walls — **exception:** one in-tree SVG **Price compare** (≤4 symbols, indexed overlay; Tremor/shadcn chart *pattern*) on symbol detail only |
| `billing-usage` / `pricing-sections` | 18 | **REJECT** | Payments fence |
| `feature-sections` / `onboarding-feed` | 28 | **REJECT** | Marketing |
| `account-and-user-management` | 15 | **REJECT for now** | Multi-user admin ≠ thin dash |
| `page-shells` / `grid-lists` | 21 | **REJECT default** | Duplicate `AppNav` / densify UI |
| `file-upload` | 7 | **REJECT** | No upload surface |
| `bar-lists` | 7 | **MAYBE** | Disclosure / fire history ranked list |

**Tremor takeaway:** MIT is fine; **~70% of the catalog is fence-illegal or redundant**. Useful slice ≈ empty states, badges, status monitoring, light forms, optional spark — not “all templates.”

---

## 3. Bookmark sites (from your WebDev list) → filter

| Source | License | Bulk OK? | Chime action |
|---|---|---|---|
| **Tremor Blocks / Raw** | MIT | Clone yes; vendor selectively | Cherry-pick patterns above |
| **HyperUI** | MIT | Yes | Empty/list/badge HTML → adapt to React |
| **daisyUI** | MIT core / paid templates | Core yes | **Do not install** beside shadcn (second design system) |
| **21st.dev** | Per-item (often MIT) | **No dump-all** | Cherry-pick empty/auth/nav; verify each |
| **Shadcnblocks** | Pro proprietary; free SPDX weak | Pro **no** | Free only if LICENSE clear; else skip |
| **Cult UI** | Free MIT / Pro paid | Free yes | Skip Pro hero panels; light status only |
| **Watermelon UI** | MIT claimed + “Premium” marketing | Confirm per block | Thin tables/login only |
| **React Bits** | MIT + **Commons Clause** | App use ≠ pure MIT | **Constitution fail — skip** |
| **Apple Cards Carousel / Footers / FAQ / Animated Beam** | Usually marketing demos | N/A | **Reject** (landing chrome; dash isn’t a brochure) |
| **Better Design Tips** | Tips, not components | N/A | Skip as kit |
| **Icons** | Prefer existing `lucide-react` | — | Already in `web/` |

---

## 4. What we *can* do (ranked adoption queue)

Prefer **extend shadcn in-tree** over importing Tremor wholesale.

| Priority | Change | Source | Why |
|---|---|---|---|
| P0 | Add shadcn **`Badge`** | ui.shadcn | Armed/active + history delivery — DASH_IA gap |
| P0 | Add shadcn **`Select`** | ui.shadcn | Replace native selects in login/alert forms |
| P1 | Add shadcn **`Alert`** (or keep `OpsNotice`) | ui.shadcn | Health stale/unreachable notices |
| P1 | Symbol page shortcuts: Watch + New alert | existing patterns | DASH_IA gap; no kit needed |
| P1 | History **limit** control | HyperUI/Tremor filterbar *pattern* | DASH_IA gap |
| P2 | Polish `EmptyState` variants | Tremor empty-states / HyperUI | Copy UX, not dependency |
| P2 | Health status chips | Tremor `status-monitoring` *pattern* | Still Postgres/health API only |
| P3 | Optional Tremor Raw **SparkChart** | MIT | Only if it beats `sparkline.tsx` on a11y/size; else keep SVG |
| P3 | **Symbol price compare** (scale 1–4) | Tremor/shadcn chart *pattern* → SVG | Indexed overlay; max 4; Postgres snapshots only — not TA |
| — | Full Tremor template apps | — | **Do not** |
| — | Chart walls / KPI dashboards | — | **Do not** |
| — | React Bits / Pro shadcnblocks | — | **Do not** |

---

## 5. How to use Tremor *without* wrecking the product

1. Keep Chime brand shell (`globals.css`, Fraunces/Sora, `AppNav`).  
2. Copy **one** block at a time into `web/src/components/…`, strip unused chart deps.  
3. Log in `THIRD_PARTY.md`: name, MIT URL, date.  
4. Verify: `make factory-verify` / dash smoke.  
5. Adversarial check: “Does this look like a trading terminal?” → revert if yes.
6. **Test loop (required):** `cd web && npm run typecheck && npm run lint`, then
   `pytest tests/test_web_route_regressions.py -q --tb=short` (kit/badge/select/
   history/symbol contracts). Do not land polish without green verify.

---

## 6. One-line answer

> Tremor’s templates are free MIT but mostly **wrong shape** for Chime; we inventory and cherry-pick thin patterns (badges, empties, status, forms), extend **shadcn** first, and skip dump-all / 100-agent / Pro / chart-wall imports.
