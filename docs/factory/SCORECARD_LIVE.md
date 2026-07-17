# Chime live readiness scorecard (brutal)

**Date:** 2026-07-16  
**Target:** Neon + https://chime-cse.vercel.app  
**Demo login (Vercel allowlist):** `6370595527`

## Rubric (100)

| Pillar | Max | What it measures |
|---|---:|---|
| Coverage | 30 | Price snaps, fin disclosures, metrics_ok, fin briefs across ~301 stocks |
| Live correctness | 25 | Authenticated live API: price + metrics + brief on sample symbols |
| Ops/pipeline | 20 | Ingest CLIs, Action backfill, failover, coverage tooling |
| Extract quality | 15 | `extract_ok` rate among attempted filing_metrics rows |
| Hygiene | 10 | Secrets not in git; keys not leaked (chat paste deducts) |

## Scores

| Pass | Coverage | Live | Ops | Extract | Hygiene | **Total** |
|---|---:|---:|---:|---:|---:|---:|
| Baseline (pre-push) | 17.2 | 25 | 20 | 10.7 | 8 | **~81** |
| After brief/metrics push | ~19–22* | 25 | 20 | ~11 | 8 | **~84–86*** |

\*Exact totals move as background `/financials` loaders finish; live sample stays green.

## What is actually excellent
- Live SEMB/COMB/ASCO/ALLI/SAMP/JKH/HNB show **price + metrics + brief**
- Neon is the live DB; `/financials` backfill is the right path
- Groq 3-key failover works under 429s
- CI/Action path can continue board fill without a laptop

## Brutal gaps (why not 100)
1. **~half the board still lacks `extract_ok` metrics** (debentures/prefs/no CSE financials/PDF extract fails).  
2. **AI briefs lag metrics** (free Groq TPD/TPM — cannot brief 300 issuers in one day).  
3. **~29% of extract attempts fail** (scanned PDFs, USD summary pages, empty text).  
4. **Secrets were pasted in chat** — must rotate (hygiene < 10).  
5. **No always-on poller proof on Vercel** — health often shows `poller: null` (DB-only health).  

## Honest “perfect score” requirements
A true **100/100** needs:
- Paid LLM quota (or multi-day drain) for briefs on every `extract_ok` symbol  
- Extractor R&D for the failing PDF cohort (or accept “no metrics” for non-financial listings)  
- Continuous poller + Action with secrets in GitHub/Vercel (not chat)  
- Key rotation completed  

Until then, claiming 100 would be dishonest.

## How to re-score
```bash
python3 scripts/coverage_filings_neon.py
# then live-login 6370595527 and hit /symbols/SEMB.X0000/metrics
```
