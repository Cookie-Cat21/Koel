# Third-party *market data* checklist (not npm/PyPI)

Runtime open-source packages stay in [`THIRD_PARTY.md`](THIRD_PARTY.md) / [`docs/THIRD_PARTY.md`](THIRD_PARTY.md).  
This file tracks **external market / macro feeds** considered for Signal Board factors.

## Rules (locked)

1. Python adapter only → Postgres → `web/` reads DB (never calls the feed).
2. Feature-flagged + rate-limited + circuit-breaker shared patterns.
3. Log ToS / license / attribution here **before** enabling in prod.
4. No competitor scrape (`csetracker.lk` etc.).
5. Not a Finnhub / TradingView **data spine** ([CHIME_MASTER_PLAN.md](factory/CHIME_MASTER_PLAN.md)).

## Tiers

| Tier | Status | Examples |
|---|---|---|
| A — CSE / in-house | **Primary** | Path bars, tradeSummary, sectors, indexes, disclosures, filing_metrics |
| B — public macro | Candidate later | CBSL policy rate / inflation; ToS-clean USD/LKR; WB/IMF open series |
| C — text | Partial | Filing PDF extract + optional Gemini briefs (existing flags) |
| D — commercial | Deferred | Finnhub, Polygon, Bloomberg, … |
| E — banned | Never | Competitor HTML/APIs; dash→upstream scrapers |

## Adapter intake checklist (copy per source)

- [ ] Source name + official URL  
- [ ] ToS / license allows redistribution into Postgres for product use  
- [ ] Auth model (none / API key) + secret env name  
- [ ] Rate limit / politeness  
- [ ] Schema table(s) + migration id  
- [ ] Feature flag default `0`  
- [ ] Fail-soft behavior when feed down  
- [ ] NFA: factors describe data, never “buy/sell”

**No Tier B+ adapters shipped yet** — Signal Board v0 uses Tier A only.
