# Ceyfi-hosted Quiverly integration master plan

**Date:** 2026-07-17 (rev: Ceyfi-as-host)  
**Status:** Planning — product UX builds in **[ArdenoStudio/ceyfi](https://github.com/ArdenoStudio/ceyfi)**; Quiverly stays the CSE data/alert engine.  
**Spine:** **Ceyfi is the app people open. Quiverly is the market nervous system underneath.**

---

## 0. Direction (locked)

| Layer | Lives in | Role |
|---|---|---|
| **Host product** | **Ceyfi** | Where users watch, get alert UX, see cash, decide |
| **Market engine** | **Quiverly** | Poller, rules, snapshots, disclosures, Telegram fire plumbing |
| **Money / wallet** | **Ceyfi** | Already owned — balances, FX, family wallet |
| **Trade execution** | Broker / CDS partner (later) | Not Quiverly, not Ceyfi today |

Earlier twin-app draft had Quiverly as the primary surface. **That is flipped:**
we do **not** grow the invest journey inside the Quiverly dash. We add a
**Market / Alerts** module to Ceyfi that consumes Quiverly.

```
┌──────────────────────────────────────────┐
│  CEYFI (host — what users open)          │
│  Wallet · Loans · SME · Assistant        │
│  + NEW: Market / Watch / Alerts UI       │
│  + cash context next to CSE pings        │
└─────────────────� Alerts UI       │
│  + cash context next to CSE pings        │
└─────────────────┬────────────────────────┘
                  │ APIs / webhooks / bot
┌─────────────────▼────────────────────────┐
│  CHIME (engine — mostly headless)        │
│  cse.lk poller · rules · Postgres truth  │
│  Telegram delivery · health              │
└──────────────────────────────────────────┘
```

---

## 1. Reception (still true with Ceyfi as host)

| Audience | Take |
|---|---|
| Diaspora / Ceyfi users | **Best fit** — “my money app also watches CSE names I care about” |
| Pure CSE power users | May still want Quiverly-thin dash; keep engine APIs; don’t force wallet chrome on them |
| Brokers / compliance | Same rule: **no “Buy now” from an alert** without a licensed handoff |
| Seylan | Market module must stay **info + cash clarity**, not unlicensed IB |

**Safe one-liner**

> **Ceyfi is where your rupees live. Quiverly watches the CSE for you. Together
> you see the move and whether you can act — you still trade with your broker.**

---

## 2. North-star journey (Ceyfi-first)

```
1. In Ceyfi: watch COMB (Market module → Quiverly API creates watch/rule)
2. Quiverly poller matches rule → fires Telegram (and/or Ceyfi in-app bell)
3. Deep link opens Ceyfi /market/alerts/{id} — symbol + trigger + NFA
4. Same screen: wallet liquid cash from Ceyfi snapshot (“dry powder”)
5. CTA: “Open my broker” / later partner handoff — never “Buy in Ceyfi”
```

---

## 3. Where code goes

| Work | Repo |
|---|---|
| Market nav, watchlist UI, alert inbox, cash+alert panel | **ceyfi** (`frontend/`) |
| Persona login bridge to Quiverly `telegram_id` / API keys | **ceyfi** + thin Quiverly auth endpoint |
| Poller, rules, snapshots, disclosure store | **Quiverly** (this repo) — keep hardening |
| Public/read APIs for Ceyfi (`/api/v1/...` symbols, watch, alerts, fires) | **Quiverly** |
| Telegram CSE fires | **Quiverly** bot (or Ceyfi bot calling Quiverly send) |
| Ownership / people research graphs | Stay Quiverly research (optional deep link); don’t dump into Ceyfi wallet chrome |

**This Quiverly workspace** is for engine APIs + docs. **Implement the product
surface in the Ceyfi repo** once Phase 0 is unlocked.

---

## 4. Phased plan (Ceyfi host)

### Phase 0 — Fence + wording (both repos, light)

- [ ] Ceyfi README / pitch: Market = research + alerts, **not** brokerage  
- [ ] Quiverly `CLAUDE.md`: “Ceyfi may consume Quiverly APIs; Quiverly dash not the invest host”  
- [ ] NFA copy pack shared  
- [ ] Reception mock in **Ceyfi** UI (alert + cash panel, no Buy)

### Phase 1 — Quiverly APIs Ceyfi can call

Quiverly exposes (auth’d) roughly:

- `GET /api/v1/symbols` / quote / disclosures (already partial on dash)
- `POST /api/v1/watchlist` · `POST /api/v1/alerts` · `GET /api/v1/alerts/fires`
- Service or user token Ceyfi backend can hold (never put CSE poller in Ceyfi)

Ceyfi adds:

- Nav: **Market**
- Thin pages: Watchlist, Alerts, Alert detail (NFA footer)
- Writes go Ceyfi BFF → Quiverly API (Ceyfi never scrapes cse.lk)

### Phase 2 — Alert → cash on one Ceyfi screen

On alert detail in Ceyfi:

1. Quiverly payload: symbol, trigger, price, disclosure link  
2. Ceyfi `financial-snapshot`: liquid estimate  
3. Layout: market column + cash column + NFA  
4. Primary CTA: deep link broker / “Review wallet” — **not** Buy

### Phase 3 — Telegram + Ceyfi inbox

- Keep Quiverly Telegram for reliability of CSE fires  
- Link opens **Ceyfi** alert detail (not Quiverly dash)  
- Optional: Ceyfi in-app notification mirror

### Phase 4 — Broker handoff (partner required)

- Prefill / lead from Ceyfi alert detail  
- Compliance pack; still no custody in Ceyfi/Quiverly

### Phase 5 — Optional: retire Quiverly public dash

Only if Ceyfi Market fully covers setup UX. Quiverly remains poller + DB + bot.

---

## 5. What we are *not* doing on Quiverly

- Building the invest journey UI in `web/` as the primary surface  
- Porting Ceyfi wallet/loan sidebar into Quiverly  
- Hard-merging repos into one Next app in v1  
- Order entry without a licensed partner  

Quiverly dash can stay for ops/research (health, people, ownership) — that’s
fine. **Consumer “invest easier” path = Ceyfi.**

---

## 6. Decision gate

1. [ ] Confirm Ceyfi-as-host (this doc)  
2. [ ] Clone/work in `ArdenoStudio/ceyfi` for UI  
3. [ ] Quiverly API auth design for Ceyfi BFF  
4. [ ] No Buy CTA in mocks  
5. [ ] Human unlock to start Phase 1 in Ceyfi  

---

## 7. Next concrete step (when you say go)

**In the Ceyfi repo (not Quiverly):** scaffold `/market` with watchlist + alert
inbox wired to mocked Quiverly payloads + real Ceyfi cash snapshot side-by-side.
**In Quiverly:** only add the minimal authenticated API Ceyfi needs.

Until then this file is the roadmap.
