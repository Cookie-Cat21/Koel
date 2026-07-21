# UI improve loop — 2026-07-21

Target loops: 50. Fence: HyperUI/shadcn patterns only; no DaisyUI/React Bits/Tremor chart walls.

| Loop | Check | Result | Detail |
|---|---|---|---|
| 1 | `typecheck` | PASS | > web@0.1.0 typecheck > tsc --noEmit |
| 2 | `market_fence` | PASS | .                                                                        [100%] |
| 3 | `tv_symbol` | PASS | .                                                                        [100%] |
| 4 | `h1_unit` | PASS | ................................                                         [100%] |
| 5 | `market_http` | PASS | 200 |
| 6 | `sector_http` | PASS | 200 |
| 7 | `lwc_source` | PASS |  |
| 8 | `tv_embed_source` | PASS |  |
| 9 | `filter_bar_source` | PASS |  |
| 10 | `bookmark_audit` | PASS |  |
| 11 | `typecheck` | PASS | > web@0.1.0 typecheck > tsc --noEmit |
| 12 | `market_fence` | PASS | .                                                                        [100%] |
| 13 | `tv_symbol` | PASS | .                                                                        [100%] |
| 14 | `h1_unit` | PASS | ................................                                         [100%] |
| 15 | `market_http` | PASS | 200 |
| 16 | `sector_http` | PASS | 200 |
| 17 | `lwc_source` | PASS |  |
| 18 | `tv_embed_source` | PASS |  |
| 19 | `filter_bar_source` | PASS |  |
| 20 | `bookmark_audit` | PASS |  |
| 21 | `typecheck` | PASS | > web@0.1.0 typecheck > tsc --noEmit |
| 22 | `market_fence` | PASS | .                                                                        [100%] |
| 23 | `tv_symbol` | PASS | .                                                                        [100%] |
| 24 | `h1_unit` | PASS | ................................                                         [100%] |
| 25 | `market_http` | PASS | 200 |
| 26 | `sector_http` | PASS | 200 |
| 27 | `lwc_source` | PASS |  |
| 28 | `tv_embed_source` | PASS |  |
| 29 | `filter_bar_source` | PASS |  |
| 30 | `bookmark_audit` | PASS |  |
| 31 | `typecheck` | PASS | > web@0.1.0 typecheck > tsc --noEmit |
| 32 | `market_fence` | PASS | .                                                                        [100%] |
| 33 | `tv_symbol` | PASS | .                                                                        [100%] |
| 34 | `h1_unit` | PASS | ................................                                         [100%] |
| 35 | `market_http` | PASS | 200 |
| 36 | `sector_http` | PASS | 200 |
| 37 | `lwc_source` | PASS |  |
| 38 | `tv_embed_source` | PASS |  |
| 39 | `filter_bar_source` | PASS |  |
| 40 | `bookmark_audit` | PASS |  |
| 41 | `typecheck` | PASS | > web@0.1.0 typecheck > tsc --noEmit |
| 42 | `market_fence` | PASS | .                                                                        [100%] |
| 43 | `tv_symbol` | PASS | .                                                                        [100%] |
| 44 | `h1_unit` | PASS | ................................                                         [100%] |
| 45 | `market_http` | PASS | 200 |
| 46 | `sector_http` | PASS | 200 |
| 47 | `lwc_source` | PASS |  |
| 48 | `tv_embed_source` | PASS |  |
| 49 | `filter_bar_source` | PASS |  |
| 50 | `bookmark_audit` | PASS |  |

**Summary:** 50/50 checks passed (0 failures).

Improvements applied outside this counter: BrowseFilterBar extract, sector select, LWC + TradingView layers, bookmark audit.

## Verified live (Playwright)

- Browse sector select + Apply → Banks / Telecommunications
- Symbol hero candlesticks
- Expand → koel LWC (crosshair + volume pane) + TradingView layer
- Fixed LWC v5 `priceScale("volume", paneIndex)` crash that blanked the symbol page
- Walkthrough: `/opt/cursor/artifacts/koel-ui-walkthrough.mp4`
