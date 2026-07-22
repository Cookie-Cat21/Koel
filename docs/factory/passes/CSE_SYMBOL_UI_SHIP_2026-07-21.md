# CSE symbol UI ship — session quote + issuer identity (2026-07-21)

**Authority:** [CSE_COMPANY_PAGE_VS_KOEL.md](../CSE_COMPANY_PAGE_VS_KOEL.md) · [DASH_COMPONENT_FILTER.md](../DASH_COMPONENT_FILTER.md) · Ardeno UI Elements bookmarks.

## What we can do (beyond prior koel)

From official CSE company page gaps, ranked and shipped this pass:

1. **Session quote strip** — day range, open, trades, turnover (already in `price_snapshots`, now shown)
2. **Issuer identity** — ISIN, Main Board, β ASPI / SL20, % of market, shares/par, contact, auditors, secretaries, top posts
3. Help topics for quote session + issuer source

## Ardeno bookmark filter (this pass)

| Bookmark | Verdict | Used |
|---|---|---|
| HyperUI | **ACCEPT** | Dense stats grid (`SessionQuoteStrip`) |
| Shadcn / Badge | **In-tree** | ISIN / beta / board chips |
| Tremor Charts / KPI walls | **REJECT** | — |
| DaisyUI | **REJECT** | — |
| React Bits / Animated Beam | **REJECT** | — |
| Watermelon Premium / Apple Cards / 21st dumps | **REJECT** | — |

## Code

| Piece | Path |
|---|---|
| Migration | `db/migrations/035_issuer_profiles.sql` |
| Backfill CLI | `python3 -m koel issuer-profile-backfill --force` |
| Adapter | `fetch_company_info_bundle` + richer `fetch_company_profile` |
| UI | `session-quote-strip.tsx`, `issuer-identity-strip.tsx` |
| Loop | `scripts/cse_symbol_ui_loop.py` → **50/50 PASS** |

## Ops

```bash
DATABASE_URL=postgresql://koel:koel@localhost:5432/koel python3 -m koel migrate
DATABASE_URL=… python3 -m koel issuer-profile-backfill --force --limit 20
```

Dash remains Postgres-only (never calls cse.lk).

## Stills

`/opt/cursor/artifacts/ui-stills/cse-vs-koel/2{0,1,2,3}-koel-*.png`
