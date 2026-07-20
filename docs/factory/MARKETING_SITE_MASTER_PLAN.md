# Quiverly marketing site — master plan

**Status:** Planning (survey complete 2026-07-15)  
**Authority:** [CLAUDE.md](../CLAUDE.md) · [KOEL_BRAND.md](../brand/KOEL_BRAND.md) · [ARDENO_STEAL_SHEET.md](../brand/ARDENO_STEAL_SHEET.md) · [DASH_COMPONENT_FILTER.md](DASH_COMPONENT_FILTER.md)  
**Product rule:** Telegram = product. Site = front door + trust. Dash = daily cake.

This plan expands the thin `/` landing into a real marketing surface (including FAQ densify, pricing stub, blog later) **without** turning Quiverly into a broker dashboard or generic SaaS wallpaper.

---

## 0. Why this exists

Unsigned visitors need one clear story:

> CSE alerts on Telegram. Manage watchlist/rules in a thin dash. Not a portfolio tracker.

We already ship a branded landing (`web/src/app/page.tsx`: wordmark → headline → CTA → Telegram proof → Steps → FAQ). Signed-in users redirect to `/overview`. This plan densifies the **public** site and defines which Ardeno bookmark kits we may steal from.

---

## 1. Survey method

Three parallel explore agents covered the Ardeno UI bookmark folder:

| Agent | Kits |
|---|---|
| A | HyperUI · daisyUI · Tremor Blocks/Charts |
| B | 21st.dev · Cult UI · Shadcnblocks · Watermelon UI |
| C | React Bits · Apple Cards · FAQ/Footer kits · Animated Beam · Icons |

Cross-checked against factory license fence + brand rules (cool paper, near-black ink, Fraunces/Sora, no purple spa / cream terracotta).

---

## 2. License & kit gate (hard)

| Source | License | Bulk? | Quiverly action |
|---|---|---|---|
| **HyperUI** | MIT | Pattern OK | **Primary steal** for marketing HTML → React |
| **shadcn/ui** | MIT | Yes | Stack lock — Accordion, etc. as needed |
| **Tremor Blocks** | MIT | Selective | Status/empty/badge **patterns only** — no Planner/Dashboard templates |
| **21st.dev** | Per-item (often MIT) | No dump | Cherry-pick 1 announcement bar after SPDX check |
| **Cult UI free** | MIT | Selective | Structure only; **no shader heroes** |
| **Watermelon registry** | MIT claimed | Selective | Accordion/login polish only — skip `dashboards/` |
| **Shadcnblocks Free** | SPDX weak / “end product” | Cautious | At most banner + CTA; **Pro = reject** |
| **daisyUI** | MIT core / paid store | No install | **Do not add plugin** beside shadcn; steal chat/steps *patterns* (already in kit) |
| **React Bits** | MIT + Commons Clause | No | **Constitution fail — skip** |
| **Cult Pro / Shadcnblocks Pro** | Paid | No | Reject |
| **Aceternity Apple Cards / Beam on `/`** | Mixed | No | Reject for landing (brochure chrome) |

Log every pasted block in `THIRD_PARTY.md` (name, URL, MIT/SPDX, date).

---

## 3. ACCEPT / REJECT cherry-picks

### ACCEPT (build from these)

| # | Pattern | Source | Use on Quiverly |
|---|---|---|---|
| 1 | FAQ divided + chevrons | HyperUI FAQs | Harden `FaqSection` (lucide chevron, hairline rules) |
| 2 | Feature **list** (not 3-card grid) | HyperUI Feature Grids — list | “What you can alert on” as rows |
| 3 | Simple footer row | HyperUI Footers | Marketing footer: NFA · Sign in · Bot · Privacy stub |
| 4 | CTA left copy (+ optional proof) | HyperUI CTAs | Mid-page “Open Telegram” / “Open dash” |
| 5 | Empty “get started” 3-step | HyperUI Empty States | Reuse rhythm for landing Steps (already close) |
| 6 | Daisy chat bubble | Pattern (already shipped) | Keep Telegram proof as product demo |
| 7 | Daisy steps | Pattern (already shipped) | Keep how-it-works |
| 8 | Thin announcement bar | 21st Announcements **or** Shadcnblocks `banner1` | “Market hours · bot live” — one only |
| 9 | Quiet end CTA | Shadcnblocks `cta34` pattern | Bottom dual CTA without tinted hero card |
| 10 | Status trackers | Tremor Status Monitoring | `/health` only — not marketing KPI wall |

### MAYBE (phase 2+)

| Pattern | Source | Condition |
|---|---|---|
| 2-tier pricing | HyperUI Pricing | Stub Free / Later — **no checkout** |
| Cult hero **structure** | Cult Hero Color Panels | Copy left / proof right; **strip shaders** |
| shadcn Accordion FAQ | ui.shadcn | Only if HyperUI details isn’t enough |
| Blog card list | HyperUI Blog Cards | Phase 3 — ops notes / CSE endpoint changes |
| Watermelon accordion | MIT registry | FAQ motion polish only |

### REJECT (do not import)

- Tremor Planner / Overview / Dashboard / Insights / KPI / chart walls  
- React Bits (any)  
- Cult Pro / shader heroes / aurora / spline / container-scroll  
- Shadcnblocks Pro + device-frame heroes + logo clouds + stats strips  
- Watermelon dashboard packs  
- Apple Cards Carousel, Animated Beam on `/`  
- Newsletter mega-footers, fake testimonials, broker comparison tables  
- daisyUI as npm/plugin dependency  

---

## 4. Information architecture

### Public routes (marketing)

| Route | Job | Wave |
|---|---|---|
| `/` | Brand hero + proof + how it works + what alerts + FAQ + end CTA | W1–W2 |
| `/login` | Demo / Telegram login (existing) | — |
| `/pricing` | Stub: Free via Telegram · Paid later “coming later” · NFA | W2 |
| `/blog` | Index of short posts | W3 |
| `/blog/[slug]` | MDX or markdown posts | W3 |
| `/legal/privacy` · `/legal/terms` | Thin stubs | W2 |

Signed-in users: keep redirect `/` → `/overview`. Marketing chrome must not wrap the dash shell.

### First viewport rules (hard)

Brand wordmark hero-level · one headline · one supporting sentence · one CTA group · atmosphere plane.  
**Not** in first viewport: FAQ, pricing table, blog cards, stats, logo cloud, schedule chips.

---

## 5. Page composition (target `/`)

```
[optional announcement bar]
[atmosphere]
  Hero: QuiverlyWordmark + headline + sentence + [Open Telegram] [Open dash]
  Proof: one Telegram ChatBubble (fired alert) — not a carousel
  How it works: 3 Steps
  What you can watch: HyperUI-style feature LIST (price / move / disclosure / YoY)
  Mid CTA: open bot
  FAQ: divided details
  End CTA: dual buttons
[marketing footer: NFA + links]
```

Motion budget (keep ≤3): atmosphere drift · hero rise · one micro (CTA lift **or** FAQ chevron).

---

## 6. Build waves

### Wave 1 — Densify the door (no new routes)
1. Announcement bar (dismissible, sessionStorage)  
2. Feature list section (alert types) — HyperUI list pattern  
3. FAQ polish (chevron + divided)  
4. Marketing footer component (replace lone `NfaFooter` on `/` only)  
5. End CTA strip  
6. Primary CTA → real Telegram bot URL when `NEXT_PUBLIC_TELEGRAM_BOT_URL` set; else `/login`

**Done when:** unsigned `/` tells cake/cherry story without scrolling past fold for brand+CTA; screenshot desktop+mobile.

### Wave 2 — Pricing + legal stubs
1. `/pricing` — 2 columns Free / Later (HyperUI 2-tier, recolored)  
2. Explicit “no payments in v1”  
3. `/legal/privacy` + `/legal/terms` thin pages  
4. Footer links wired  

**Done when:** no checkout, no Stripe; NFA on pricing.

### Wave 3 — Blog (light)
1. `content/blog/*.mdx` or markdown  
2. `/blog` list (HyperUI blog cards — max 3 featured, no magazine wall)  
3. First posts: “Why Telegram”, “What Quiverly is not”, “Filing YoY alerts”  
4. No comments, no CMS  

**Done when:** 2–3 posts live; dash routes untouched.

### Wave 4 — Polish / optional
1. Cult-style split hero **structure** (proof column) if Wave 1 feels thin  
2. Accordion FAQ if a11y needs it  
3. Skip Beam / carousels unless user re-opens that gate  

---

## 7. Stack & file map

```
web/src/app/page.tsx                 # landing composition
web/src/app/pricing/page.tsx         # W2
web/src/app/blog/page.tsx            # W3
web/src/app/blog/[slug]/page.tsx
web/src/app/legal/...
web/src/components/marketing/        # NEW — public-only chrome
  announcement-bar.tsx
  feature-list.tsx
  site-footer.tsx
  end-cta.tsx
web/src/components/kit/              # existing ChatBubble, Steps, FaqSection
content/blog/                        # W3
```

Do **not** put marketing mega-nav into `AppNav` (dash shell stays management links).

Optional public `MarketingNav`: Wordmark · How it works (anchor) · Pricing · Blog · Sign in.

---

## 8. Copy principles

- Lead with Telegram push job; dash is secondary  
- Name competitors only to differentiate (CSE Tracker Pro = browser-open alerts)  
- Always NFA near price/recommendation-adjacent copy  
- No fake “10k users” / logo clouds  
- Non-goals section or FAQ: no portfolio, tax, screener, TA charts, native app  

---

## 9. Adversarial checks (every wave)

1. Remove the nav — is the brand still obvious?  
2. Does this look like a trading terminal or KPI SaaS? → cut  
3. Would someone think Quiverly replaces Telegram? → rewrite CTAs  
4. Any Pro/Commons-Clause import? → remove  
5. `prefers-reduced-motion` still honored?  

---

## 10. Test plan (per wave)

- `cd web && npm run typecheck && npm run lint`  
- Manual: unsigned `/` desktop + mobile screenshots  
- Signed-in `/` still redirects to Overview  
- Pricing has no payment forms  
- Blog builds with 0 posts (empty state) and with posts  
- Regression pin in `tests/test_web_route_regressions.py` for marketing routes when added  

---

## 11. Out of scope (still)

- Payment integration / Stripe  
- Native app store pages  
- CSE Tracker Pro scrape  
- Full Tremor dashboard templates  
- Replacing thin dash with marketing layout  

---

## 12. One-line summary

> Steal HyperUI marketing patterns + keep in-tree Telegram proof; ship denser `/`, then stub pricing/legal, then a tiny blog — Telegram stays the product, kits never become a second design system.

---

## Appendix A — Bookmark folder → decision

| Bookmark | Decision |
|---|---|
| WebDev / Better Design Tips | Tips only — skip as kit |
| HyperUI | **Primary** marketing steal |
| daisyUI | Pattern only (chat/steps already); no plugin |
| Tremor – Charts | Reject chart walls; status blocks for `/health` |
| Apple Cards Carousel | Reject |
| Footers / FAQ Sections | Steal HyperUI variants |
| Animated Beam | Reject on `/` |
| React Bits | Reject (Commons Clause) |
| 21st (new + featured) | One announcement bar max, SPDX each |
| UI component library | Ignore vague |
| Shadcnblocks | Free banner/CTA only; Pro no |
| Icons | lucide-react only |
| Cult UI Hero Color Panels | Structure maybe; shaders no |
| Watermelon UI | Accordion/login maybe; dashboards no |
