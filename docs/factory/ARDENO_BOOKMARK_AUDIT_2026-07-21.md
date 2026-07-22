# Ardeno UI Elements bookmark audit — 2026-07-21

Source: browser folder **Ardeno UI Elements** (screenshot).  
Authority: [DASH_COMPONENT_FILTER.md](DASH_COMPONENT_FILTER.md) · [ARDENO_UI_MASTER_PLAN.md](ARDENO_UI_MASTER_PLAN.md).

| Bookmark | Verdict | Action for koel |
|---|---|---|
| WebDev | Tips | Skip |
| Better Design Tips | Tips | Skip |
| HyperUI | MIT — **ACCEPT patterns** | Filter bar / empty / pagination density (in use) |
| DaisyUI | MIT core / paid templates | **REJECT plugin** beside shadcn |
| Tremor – Charts | MIT/Apache | **REJECT chart stack** — koel uses Lightweight Charts on Postgres (Layer A) |
| Apple Cards Carousel | Marketing | **REJECT** for signed-in dash |
| Footers / FAQ Sections | Marketing demos | Already adapted on landing; skip re-vendor |
| Animated Beam | MIT (Magic UI family) | Optional `/health` only — skip for this pass |
| React Bits | Commons Clause | **REJECT** |
| 21st.dev community | Per-item | No dump-all; no Financial Dashboard packs |
| Shadcnblocks | Free weak / Pro proprietary | Extend **shadcn in-tree** only |
| Icons | — | Keep lucide / Hugeicons |
| Cult UI Hero Color Panels | Free / Pro | **Skip Pro heroes** |
| Watermelon UI Dashboards | MIT + Premium | Thin patterns only — no Premium dashboards |

**This pass ports:** HyperUI-style filter-bar density + active filter chips on Browse; chart layer tabs already ship LWC + TradingView (not Tremor charts).

**Workbench follow-up (same day):** [ARDENO_WORKBENCH_UI_PASS_2026-07-21.md](ARDENO_WORKBENCH_UI_PASS_2026-07-21.md) — HyperUI segments + shadcn Badge chips + Active strip + keyboard shortcuts on the expand chart dialog (`chart-workbench-controls.tsx`). Still reject DaisyUI / Tremor / React Bits.

**CSE company-page follow-up (same day):** [passes/CSE_SYMBOL_UI_SHIP_2026-07-21.md](passes/CSE_SYMBOL_UI_SHIP_2026-07-21.md) — HyperUI session stats grid + shadcn Badge issuer chips (ISIN/beta/board) from `issuer_profiles`. Loop `scripts/cse_symbol_ui_loop.py` → 50/50.
