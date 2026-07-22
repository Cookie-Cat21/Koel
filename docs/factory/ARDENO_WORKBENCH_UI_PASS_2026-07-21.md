# Ardeno UI → koel workbench pass — 2026-07-21

**Source:** Ardeno UI Elements bookmarks + chart expand dialog screenshot.  
**Authority:** [DASH_COMPONENT_FILTER.md](DASH_COMPONENT_FILTER.md) · [ARDENO_BOOKMARK_AUDIT_2026-07-21.md](ARDENO_BOOKMARK_AUDIT_2026-07-21.md)

## Bookmark filter (this pass)

| Bookmark | Verdict | Used how |
|---|---|---|
| HyperUI | **ACCEPT patterns** | Segment groups, active filter chip strip, kbd hint |
| Shadcn / Shadcnblocks (free patterns) | **In-tree only** | `Badge` for Live / counts — no Pro blocks |
| Icons (lucide) | Keep | Already on Expand / Close |
| DaisyUI | **REJECT** | — |
| Tremor Charts | **REJECT** | Stay on Lightweight Charts |
| React Bits / Animated Beam | **REJECT** for workbench | — |
| Watermelon Premium / Cult Pro / Apple Cards | **REJECT** | — |
| 21st.dev dumps | **REJECT** | — |

## Improvements shipped

1. `chart-workbench-controls.tsx` — reusable `ChartSegmentGroup`, `ChartSegmentButton`, `ChartToggleChip` (legend dots), `ChartActiveStrip`, `ChartShortcutsHint`
2. Overlay toggles use color dots + shadcn `Badge` counts (Disclosures / Fires / Alert lines)
3. Forecast: hide noisy “— none”; show dashed “Forecast unavailable” when empty
4. Live / few-ticks → shadcn `Badge`
5. Active session strip under toolbar (range · style · overlays · indicators)
6. Keyboard: `1–5` ranges, `D`/`F`/`A` overlays, `Esc` close
7. Focus-visible rings on all workbench controls

## Verify

`scripts/workbench_ui_loop.py` → 50 iterations (fence + a11y + no forbidden imports).
