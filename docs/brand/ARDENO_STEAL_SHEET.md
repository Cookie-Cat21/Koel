# Ardeno steal sheet — Dinaya (site) + Ceyfi (dash) → Chime

**Date:** 2026-07-14  
**Brand assets:** `branding/` + `web/public/brand/` (PR #14) — lowercase geometric `chime` wordmark + `C` mark.

## Dinaya (website) — steal
- Wordmark as **asset lockup**, not CSS text (`Logo.tsx` pattern)
- Floating/sticky chrome with blur on **nav only** (not content cards)
- Landing: brand → one headline → one sentence → CTA group → product proof
- Eyebrow + 3px left rule for section hierarchy
- CTA micro-lift on hover; respect `prefers-reduced-motion`
- Semantic status colors (pending amber / fired emerald) — not decorative purple

## Ceyfi (dashboard) — steal
- `CeyfiMark` / `CeyfiLogoIcon` two-tier brand API → `ChimeMark` / `ChimeWordmark`
- Sticky topbar `bg-background/80 backdrop-blur` (already close)
- `PageHeader` (eyebrow + title + description + action) — ported without green orbs
- `LiveIndicator` for `/health` poller state
- Login: hero mark/wordmark + form card + NFA footer; theme toggle optional later
- Do **not** port sidebar / wallet / loan domain chrome (Chime stays top-nav)

## Chime application
| Surface | Treatment |
|---|---|
| Nav | Wordmark image → `/brand/chime-logo.svg` |
| Login / home hero | Large wordmark; keep `aria-label="Chime home"` |
| Favicon | `/brand/chime-mark.svg` |
| Health | `LiveIndicator` next to status |
| Pages | Optional `PageHeader` with Dinaya-style eyebrow |

## Non-goals
Copying Dinaya cobalt/violet or Ceyfi green palettes wholesale — Chime keeps its own tokens, aligned to near-black `#1e1e1e` ink from the logo.
