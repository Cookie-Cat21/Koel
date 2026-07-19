# UI Pattern Mining — koel Competitive Edge vs CSEPal

**Date:** 2026-07-19  
**Sources:** 21st.dev, cult-ui.com, daisyui.com, magicui.design (animated-beam)  
**Scope:** Fence-legal (MIT/Apache only), brand-aligned patterns for koel CSE dashboard  
**Competitive target:** Beat CSEPal screener density via clarity/trust/research UX, not more columns

---

## Executive summary

**Core finding:** All four sources offer fence-legal structure patterns, but most specific components carry brand anti-patterns or wrong use case. koel's competitive edge (Telegram push + ownership/people research + clean decision UX) demands **information hierarchy patterns** over generic SaaS dashboards.

**Key keep:** daisyUI semantic color system, Cult UI shift-card hover detail, magicui animated-beam for system health. **Key reject:** 21st.dev dashboard packs (Financial Dashboard = wholesale violation), Cult UI Pro shaders/textures (purple glow magnet), daisyUI plugin installation (pattern-only scope).

---

## 1. 21st.dev — Community UI components

### License check

- **Repository:** MIT-licensed open source
- **Financial Dashboard packs:** Mixed licenses; many are Pro/paid. Per instruction: **REJECT wholesale Financial Dashboard packs.**
- **Individual components:** Check each; many dashboard/chart blocks are paid or have undeclared licenses.

### Keep (free structure only)

| Pattern | Reason | koel application |
|---------|--------|------------------|
| **Stat card minimal** | Clean KPI presentation without dashboard clutter | Market overview ASPI/S&P SL20 index cards |
| **Empty state patterns** | First-run UX for new users | Empty watchlist / no fired alerts yet |
| **Button loading states** | Accessible feedback during mutations | Add-to-watchlist, create alert rule |

### Adapt (strip decorations)

| Pattern | Original | koel adaptation |
|---------|----------|-----------------|
| **Hero sections** | Gradient backgrounds, large type | Strip gradients; keep layout grid for Overview intro card ("CSE snapshots from koel's poller…") |
| **Announcement cards** | Often purple/indigo accent | Use koel's cool monochrome (`oklch(0.48 0.012 255)` muted-foreground for metadata) |

### Reject

| Pattern | Reason |
|---------|--------|
| **Financial Dashboard template packs** | Mixed licenses; wholesale dashboard = screener-density anti-pattern for koel |
| **Pricing sections / CTAs with gradients** | Purple-glow SaaS aesthetic; koel brand = cool paper + near-black ink |
| **Chart library integrations (Recharts/Chart.js kits)** | koel uses minimal sparklines (lightweight canvas/SVG), not heavy charting libraries |
| **Sidebar navigation with nested accordions** | koel IA = flat 6-tab nav (Overview, Browse, Watchlist, Alerts, Health, Settings) — no nesting |

**Brand violation flags:** Many 21st.dev community templates use purple/indigo accents, glow effects on cards, and "SaaS dashboard" chrome. These directly conflict with koel's locked bans: "purple SaaS" and broadsheet readability focus.

---

## 2. Cult UI — Shadcn/ui animated components

### License check

- **Free components (78+):** MIT (built on shadcn/ui)
- **AI SDK Agents blocks:** Appear free but check each (some reference Upstash/paid APIs)
- **Cult Pro:** PAID — Premium marketing components (reject for this analysis)

### Keep (MIT structure only)

| Pattern | Reason | koel application |
|---------|--------|------------------|
| **Shift Card** ("shows more detail on hover") | Progressive disclosure without navigation | Symbol card: ticker + last price surface; hover reveals 24h range, volume, sector |
| **Empty state illustrations** | Friendly first-run UX | Empty watchlist / alerts — more polished than plain text |
| **Table Editor Artifact** (if truly MIT) | Inline editing with AI chat | **Deferred** — not MVP, but precedent for future ownership/people research tables |

### Adapt (strip AI/glow effects)

| Pattern | Original | koel adaptation |
|---------|----------|-----------------|
| **Stat cards** | Often have animated counters / gradient borders | Static values; cool monochrome borders |
| **Accessibility Audit Agent patterns** | AI tool outputs with color coding | Color-coding for alert rule status (pending amber / fired emerald) — semantic, not decorative |

### Reject

| Pattern | Reason |
|---------|--------|
| **Cult Pro Premium Components** | PAID license |
| **Hero sections with shaders** (Warp, Simplex Dithering, Neuro Noise, Moss) | GPU shaders = performance cost; purple-glow aesthetic; koel uses CSS gradients + grain texture only |
| **Marketing CTA sections** (Particles, Cosmic, Waves) | Cream/terracotta palettes in examples; heavy animation violates `prefers-reduced-motion` |
| **Branding Agent / AI blocks** | Wrong use case (koel is not a design-system extractor) |
| **Fluid AI Workloads / Gateway illustrations** | Generic SaaS/infra metaphors; CSE is a regulated market, not a dev platform |

**Brand violation flags:** Cult Pro sections extensively use purple gradients, glow effects, and shader-based backgrounds. The "Marketing Hero with Warp Shader" and similar are direct violations of koel's "no purple glow" ban. Free components are safer but still need glow-strip.

---

## 3. daisyUI — Tailwind CSS component library

### License check

- **Plugin itself:** MIT
- **Instruction scope:** "patterns only, NO npm plugin" — extract semantic structure, don't install daisyUI as a dependency.

### Keep (semantic patterns, implement manually)

| Pattern | Reason | koel application |
|---------|--------|------------------|
| **Semantic color system** | `primary`, `secondary`, `accent`, `neutral`, `info`, `success`, `warning`, `error` with `-content` pairs | koel already uses shadcn tokens; validate that alert-rule status colors (pending amber / fired emerald) map to semantic intent |
| **Component class abstraction** | `btn`, `card`, `toggle` instead of 100 utility classes | koel already does this via shadcn — validate existing `Button`, `Card` abstractions are sufficient |
| **Theme switching via CSS variables** | No new class names for dark mode; variable re-binding | koel is light-mode-only for MVP, but precedent if dark mode becomes a research request |
| **Form patterns** (toggle, checkbox, input with minimal markup) | Accessible, clean DOM | Watchlist add-symbol input, alert rule form |

### Adapt (translate to koel tokens)

| Pattern | Original | koel tokens |
|---------|----------|-------------|
| **Neutral color** | daisyUI default = gray-500 family | koel `--muted` (`oklch(0.965 0.003 250)`) + `--muted-foreground` |
| **Primary/Secondary** | Often blue/purple in daisyUI themes | koel `--primary` = near-black (`oklch(0.22 0.01 260)`), `--secondary` = cool light (`oklch(0.96 0.004 250)`) |
| **Success/Warning/Error** | Bright semantic colors | koel chart tokens already define these (`--chart-2` green, `--chart-3` orange, `--destructive` red) |

### Reject

| Pattern | Reason |
|---------|--------|
| **daisyUI npm plugin installation** | Per instruction: "NO npm plugin" — patterns only |
| **Pre-built theme packs** (Halloween, Cyberpunk, etc.) | Wrong aesthetic; koel = monochrome broadsheet, not theme playground |
| **Component JS behavior** | daisyUI is CSS-only, but docs show JS examples for modals/dropdowns — koel uses Radix (shadcn) for behavior |

**Brand violation flags:** daisyUI's default color palettes often include purple/indigo (`primary` in many themes). The "Cyberpunk" and "Synthwave" themes are direct violations of koel's cool-paper aesthetic. Semantic structure is valuable; default colors are not.

---

## 4. magicui.design — Animated Beam component

### License check

- **Animated Beam:** MIT (confirmed in docs: "shadcn@latest add @magicui/animated-beam")
- **Dependencies:** Framer Motion (MIT)

### Keep (MIT, single-use case)

| Pattern | Reason | koel application |
|---------|--------|------------------|
| **Animated Beam (uni/bi-directional)** | Visual feedback for system connections | **Health page:** Poller → Postgres → Dashboard data flow; Telegram bot → alert engine status |
| **SVG path animation with gradient** | Lightweight; accessible (no critical info, decorative enhancement) | Show poller heartbeat when active; static when idle |

### Adapt (brand colors)

| Original | koel adaptation |
|----------|-----------------|
| `gradientStartColor="#ffaa40"` (orange) | Use koel `--ring` (`oklch(0.4 0.015 260)`) — cool teal |
| `gradientStopColor="#9c40ff"` (purple) | **REJECT purple** — use koel `--primary` (`oklch(0.22 0.01 260)`) — near-black |
| `pathColor="gray"` | koel `--border` (`oklch(0.9 0.006 250)`) |

### Reject (wrong use case)

| Pattern | Reason |
|---------|--------|
| **Multiple-input/output beam networks** | Over-engineering; koel Health is 3 nodes (poller, DB, dash), not a microservices graph |
| **Continuous animation on data pages** | Violates `prefers-reduced-motion`; reserve for Health status only |

**Brand violation flags:** Default gradient is orange-to-purple (`#ffaa40` → `#9c40ff`). Purple endpoint is a direct brand violation. Orange is acceptable but not koel's palette. Substitute with cool monochrome or teal accent.

---

## 6 Patterns That Beat CSEPal on Clarity / Trust / Research

CSEPal's strength = screener density (multi-column tables, heavy filters). koel's wedge = **Telegram push + ownership/people research + clean decision UX.** These patterns amplify that wedge:

### 1. Shift Card (Cult UI) — Progressive disclosure without navigation

**Problem:** CSEPal shows 12 columns at once; users scan but don't absorb.  
**koel solution:** Symbol card shows ticker + last price + 1d% at rest. Hover reveals 24h high/low, volume, sector, last-disclosure date. Click navigates to detail. Progressive detail = faster scan, deeper trust.

**Implementation:** Adapt Cult UI's hover-reveal pattern; use koel monochrome (no glow borders). Surface state: 3 data points. Hover state: +4 secondary metrics. Click: full symbol detail page.

---

### 2. Semantic Status Colors (daisyUI pattern) — Trust through consistency

**Problem:** CSEPal uses decorative colors (blue buttons, green up-arrows inconsistently).  
**koel solution:** Alert rule status = **pending amber** / **fired emerald** / **cancelled gray**. Always same color for same state. Disclosure urgency = **info blue** / **warning amber** / **critical red** (if filing type implies action).

**Implementation:** Map daisyUI's `info`/`success`/`warning`/`error` to koel's chart tokens (`--chart-1` through `--chart-5`). Use sparingly; most UI is monochrome. Color = signal, not decoration.

---

### 3. Animated Beam (magicui) — Health transparency builds trust

**Problem:** CSEPal's data freshness is opaque; users don't know if prices are stale.  
**koel solution:** Health page shows live data flow: **Poller (last tick timestamp) → Postgres (snapshot count) → Dashboard (symbols on watchlists).** Animated beam when poller is active (market hours); static gray when idle.

**Implementation:** 3-node layout (poller, DB, dash). Beam color = koel `--ring` (cool teal) when healthy, `--destructive` (red) when poller is down. Gradient animation only during market hours (09:30–14:30 SLT).

---

### 4. Empty State with Next Action (21st.dev + Cult UI pattern) — Convert first-run users

**Problem:** CSEPal dumps new users into a full market table; no onboarding.  
**koel solution:** Empty watchlist shows illustration + **"Add your first symbol"** CTA + example (e.g., "Try JKH.N0000"). Empty alerts shows **"Set a price alert"** + link to docs. Empty = opportunity, not dead-end.

**Implementation:** Cult UI's empty-state illustration style (simple, not cartoon). koel's near-black ink on cool paper. CTA button = `--primary` with clear label. Include 1-sentence explainer: "Get pinged on Telegram when this fires."

---

### 5. Hover Detail without Click (21st.dev stat card pattern) — Faster research

**Problem:** CSEPal requires drilling into each symbol to see disclosures; slow research loop.  
**koel solution:** Disclosure cards on symbol detail page show headline + date. Hover reveals 2-line excerpt from PDF brief. Click opens full disclosure. Faster triage = more symbols researched.

**Implementation:** Card surface = disclosure title + date + PDF icon. `:hover` reveals `<p class="line-clamp-2">` brief excerpt. CSS-only; no JS tooltip. Respects `prefers-reduced-motion` (no slide-in).

---

### 6. Single-Job Sections (koel existing pattern, validated by daisyUI simplicity) — Readability wins

**Problem:** CSEPal's screener packs 20 filters + 12 columns + pagination into one viewport.  
**koel solution:** Each page does **one job.** Overview = market snapshot. Browse = symbol discovery. Watchlist = your tracked symbols. Alerts = rule management. No multi-tool pages.

**Implementation:** Already shipped in koel. Pattern validated by daisyUI's "semantic class names" philosophy: `btn` does one thing (trigger action), `card` does one thing (group content). koel extends this to page-level IA.

---

## Brand Violation Summary

### Direct violations (REJECT these)

| Source | Pattern | Violation |
|--------|---------|-----------|
| 21st.dev | Dashboard template packs with purple/indigo gradients | "purple SaaS" ban |
| Cult UI Pro | Hero sections with shaders (Warp, Moss, Simplex Dithering) | "purple glow" ban |
| Cult UI Pro | Marketing CTA sections (some with cream/terracotta) | "cream/terracotta" ban |
| daisyUI | Pre-built themes (Cyberpunk, Synthwave, Halloween) | Wrong aesthetic; not broadsheet |
| magicui | Default gradient `gradientStopColor="#9c40ff"` | Purple endpoint |

### Subtle risks (ADAPT with caution)

| Source | Pattern | Risk | Mitigation |
|--------|---------|------|------------|
| 21st.dev | Community component CSS often includes `shadow-lg` + `ring-purple-500` | Purple accent creep | Strip all `ring-*` and `shadow-*`; use koel `--ring` and `--border` |
| Cult UI | Animated components default to indigo/purple in examples | Copy-paste hazard | Replace all color props with koel tokens before use |
| daisyUI | `primary` color in many themes is purple/blue | Semantic name ≠ koel aesthetic | Map `primary` to koel `--primary` (near-black), not daisyUI's default |

### Safe (brand-aligned)

| Source | Pattern | Reason |
|--------|---------|--------|
| 21st.dev | Empty state structure (no color deps) | Monochrome-first |
| Cult UI | Shift Card hover logic (CSS-only) | No color assumptions; pure layout |
| daisyUI | Semantic color naming system | Abstraction layer = safe; just rebind to koel tokens |
| magicui | Animated Beam structure (SVG path + motion) | Color-agnostic; gradient colors are props |

---

## Recommendations

1. **Implement Shift Card hover pattern** on Browse + Watchlist symbol cards — biggest clarity win vs CSEPal.
2. **Add Animated Beam to Health page** — trust/transparency differentiator.
3. **Audit existing shadcn components** against daisyUI's semantic color system — ensure alert status colors map to `info`/`success`/`warning`/`error` intent.
4. **Reject all Cult UI Pro shader/texture sections** — performance + brand violation.
5. **Reject 21st.dev dashboard template packs** — licensing + anti-pattern for koel's "one job per page" IA.
6. **Strip all purple/indigo/glow CSS** from any adapted patterns — koel = cool monochrome + teal accent only.

**Next:** Prototype Shift Card on one symbol card; validate hover UX before rolling out to Browse/Watchlist. Health page Animated Beam is low-risk (decorative enhancement); ship after Shift Card.
