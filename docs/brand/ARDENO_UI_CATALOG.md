# Ardeno UI Elements → Chime

Catalog of the bookmark folder vs what Chime will actually ship.
**Authority:** `docs/factory/DASH_COMPONENT_FILTER.md` (no dump-all, no Pro, shadcn-first).

| Bookmark | Source | Chime action |
|---|---|---|
| WebDev | web.dev | Inspiration only (a11y) |
| Better Design Tips | better-design.com | Optional later theme study |
| HyperUI | hyperui.dev MIT | **Ported** via Ceyfi adapt: StatCard, AlertBanner |
| DaisyUI | daisyui.com MIT | **Patterns only** (no plugin): ChatBubble, Steps |
| Tremor Charts | tremor.so Apache | Defer — keep SVG sparkline |
| Apple Cards Carousel | Aceternity | Skip (marketing carousel creep) |
| Footers | Aceternity / blocks | Keep NfaFooter |
| FAQ Sections | HyperUI / shadcn | **Ported** FaqSection (details/summary) |
| Animated Beam | Magic UI MIT | Defer (optional architecture diagram later) |
| React Bits | reactbits.dev MIT+Clause | Skip heavy BG toys |
| 21st.dev | community | Per-item only; none bulk |
| shadcn/ui | ui.shadcn.com | **Extend** primitives as needed |
| Shadcnblocks | freemium | Free only if SPDX clear — skip Pro |
| Icons | lucide-react | Already in package.json |
| Cult UI Hero Panels | cult-ui MIT | Study structure only — no shader hero |
| Watermelon UI | registry MIT | Thin tables later if needed |

## Shipped in this pass (from Ceyfi ports, Chime tokens)
- `components/kit/chat-bubble.tsx` — Telegram proof on landing
- `components/kit/steps.tsx` — how it works
- `components/kit/stat-card.tsx` — health KPIs
- `components/kit/alert-banner.tsx` — ops notices
- `components/kit/faq-section.tsx` — landing FAQ
- `components/kit/status-badge.tsx` — armed + delivery chips (alerts / history)
- `components/ui/badge.tsx` + `select.tsx` — shadcn P0 gaps from DASH_COMPONENT_FILTER

Ceyfi already adapted HyperUI / DaisyUI-style / Aceternity under `frontend/components/{hyperui,daisyui-style,aceternity,blocks}` — we reuse that approach, not scrape marketplaces.

## Dash polish (agentic loop 2)
- Alerts / History: `PageHeader`, `ArmedBadge` / `DeliveryBadge`, history **limit** control
- Alert create: Radix `Select` with fail-closed `isAlertType`
- Symbol detail: Watch + New alert shortcuts (DASH_IA gap)
