# Ardeno UI Elements → Koel

Catalog of the bookmark folder vs what Koel will actually ship.
**Authority:** `docs/factory/DASH_COMPONENT_FILTER.md` (no dump-all, no Pro, shadcn-first).  
**Marketing site plan:** `docs/factory/MARKETING_SITE_MASTER_PLAN.md` (Waves 1–4: densify `/`, pricing stub, light blog).

| Bookmark | Source | Koel action |
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

## Shipped in this pass (from Ceyfi ports, Koel tokens)
- `components/kit/chat-bubble.tsx` — Telegram proof on landing
- `components/kit/steps.tsx` — how it works
- `components/kit/stat-card.tsx` — health KPIs
- `components/kit/alert-banner.tsx` — ops notices
- `components/kit/faq-section.tsx` — landing FAQ
- `components/kit/status-badge.tsx` — armed + delivery chips (alerts / history)
- `components/ui/badge.tsx` + `select.tsx` — shadcn P0 gaps from DASH_COMPONENT_FILTER

Also see: `docs/brand/FINANCE_DASH_INSPIRATION.md` — OSS stock dash repos +
Ardeno bookmark filter + ranked next ports (2026-07-14 survey).


## Dash polish (agentic loop 2)
- Alerts / History: `PageHeader`, `ArmedBadge` / `DeliveryBadge`, history **limit** control
- Alert create: Radix `Select` with fail-closed `isAlertType`
- Symbol detail: Watch + New alert shortcuts (DASH_IA gap)

## Agentic loop gate (required each polish pass)

Do **not** ship UI kit/dash changes without this verify loop:

1. `cd web && npm run typecheck && npm run lint`
2. `python3 -m pytest tests/test_web_route_regressions.py tests/test_wave34_medium_bugs.py::test_alert_type_select_uses_is_alert_type -q --tb=short --no-cov`
3. Prefer `make factory-verify` when touching Python + web together

Regression contracts live in `tests/test_web_route_regressions.py`:
- `test_ardeno_kit_components_exist_and_are_wired`
- `test_dash_status_badges_and_page_headers`
- `test_alert_create_uses_radix_select_fail_closed`
- `test_history_limit_control_native_get_form`
- `test_symbol_page_watch_and_new_alert_shortcuts`

