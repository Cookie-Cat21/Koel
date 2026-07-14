# Dash UI/UX improve loops (2026-07-14)

Surveyed via 4 parallel explore agents (symbol, shell/lists, a11y/mobile, empty/error).
Thin-dash fence intact — no portfolio / TA / screener.

## Plan (3 loops)

### Loop 1 — correctness & primary CTAs
1. Symbol Watch / Unwatch state from watchlist membership
2. Alert deep-link `?type=` (disclosure / price_above…)
3. Filing metrics: fail vs empty distinction + human YoY labels
4. Overview: filter “Armed alerts” to armed-only

### Loop 2 — scan path & settings clarity
5. Disclosure category chips (selected state + touch)
6. Stale snapshot coherent in hero
7. Overview + settings `loading.tsx` skeletons
8. Quiet-hours SLT / overnight helper copy

### Loop 3 — a11y & recovery polish
9. ChangeBadge direction `sr-only` + truncated names `title`
10. Symbol sticky bar safe-area inset
11. Root `not-found.tsx` + brief expand toggle
12. Sparkline aria summary (first→last)

Each loop: implement → typecheck/lint → targeted pytest → commit/push.
