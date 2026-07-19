# Activity alerts — competitor research notes (2026-07)

Peers that inform Quiverly's activity alert set (Telegram/WhatsApp-first watchers,
not full trading terminals):

| Product | Useful signals we mirrored |
|---|---|
| **Tijori Alerts** (Zerodha) | Filing categories, price **and volume** thresholds, customized watchlist push |
| **Stock Alarm** | Volume spike / dip, gap alerts, % move, price crosses |
| **Stock Alerts / Signa** | Unusual volume, block/big prints, halt-style market notices (US options flow N/A for CSE) |

## What we shipped in Quiverly

| Alert | Bot | Meaning |
|---|---|---|
| `volume_spike` | `/alert SYM volume N` | Today’s share volume ≥ N× recent daily average |
| `volume_up` | `/alert SYM volup N` | Volume spike **and** price up (buy-pressure proxy) |
| `volume_down` | `/alert SYM voldown N` | Volume spike **and** price down (dump proxy) |
| `crossing_volume` | `/alert SYM crossing N` | CSE crossing volume ≥ N× recent average |
| `big_print` | `/alert SYM print QTY` | Single day-tape print ≥ QTY shares |
| `gap` | `/alert SYM gap P` | \|open − previous close\| / previous close ≥ P% |
| `buy_in` | `/alert SYM buyin` | Symbol appears on CSE buy-in board |
| `non_compliance` | `/alert SYM noncompliance` | Non-compliance announcement for symbol |
| `halt` | `/alert MARKET halt` | Market-wide halt / system notice banner |

## Honest limits

CSE public JSON does **not** label trades as buy vs sell. `volup` / `voldown`
are **proxies** (volume × price direction), not order-flow attribution. Quiverly
does not scrape competitors and does not add a volume screener to the thin dash.


## Order-book imbalance (deeper CSE dive — 2026-07-13)

Public `POST /api/orderBook` with form `symbol=` returns:

- `reqOrderBookTotal.totalBids` / `totalAsks` — **aggregate bid vs ask size**
- `reqOrderBook[]` — depth ladder (public feed currently returns **one bid level**, `buySell=1`)

This is **not** the paid Level-2 product (IAL2MD / RTEMD). Full multi-level depth and trade aggressor tags are still commercial. But public bid/ask **totals** let Quiverly alert on real book imbalance:

| Alert | Bot | Meaning |
|---|---|---|
| `bid_heavy` | `/alert SYM bidheavy N` | totalBids / totalAsks ≥ N |
| `ask_heavy` | `/alert SYM askheavy N` | totalAsks / totalBids ≥ N |

`volup` / `voldown` remain price×volume proxies; book alerts are the honest side-aware upgrade from public CSE data.
