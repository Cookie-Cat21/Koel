# Tijori CSE — Waves 1–5 report

**Branch:** `cursor/tijori-cse-phase1-e44e`  
**Date:** 2026-07-12  
**Plan:** [TIJORI_CSE_PLAN.md](../TIJORI_CSE_PLAN.md)  
**Ops:** [docs/runbooks/TIJORI.md](../../runbooks/TIJORI.md)  
**Range:** `a802cb7` … `49e5c0b` (+ this wave-5 report)

---

## Verdict

Phase 1 foundations and Phase 2 Tijori-core plumbing are **landed** across waves 1–4 (36 commits + foundation). Live Gemini briefs remain **flag/key gated** (`AI_BRIEFS_ENABLED=0` default). Phase 3 scenario AI is **not started**. Wave 5 is this rollup.

| Track | Status |
|---|---|
| Phase 1 foundations | ✅ done |
| Phase 2 Tijori core | ◐ mostly done — live LLM still off until keyed |
| Phase 3 scenario AI | not started |
| Improve-loop / CI on touched paths | ongoing |

---

## Wave 1 — Phase 1 foundations + PDF enrich kickoff

**Theme:** Market-wide persist, thin browse, briefs schema/stub, legacy PDF URL enrich.

| SHA | Commit |
|---|---|
| `a802cb7` | fix(tijori): phase1 market persist + browse; harden empty-watchlist health |
| `447a74b` | perf(wave): batch market snapshot persist |
| `04d5931` | test(wave): market persist browse coverage |
| `cc3b503` | feat(wave): enqueue disclosure_briefs rows |
| `03f3917` | fix(wave): harden market browse q/LIKE, a11y, fence |
| `6e1137d` | fix(wave): document symbols GET as session-only (no CSRF) |
| `dbbf262` | test(wave): regress symbols CSRF exemption and error disclosure |
| `5517988` | feat(wave): legacy PDF URL enrichment |
| `b3d9ae0` | fix(wave): harden market persist health and snapshot dedupe |
| `ac648c6` | docs(wave): tijori plan wave log |

**Shipped**

- Full `tradeSummary` → `stocks` + `price_snapshots`; empty watchlist still persists (no rule fires).
- Batch snapshot persist; market health / snapshot dedupe harden.
- `GET /api/v1/symbols` + `/market` Browse (session-only GET; CSRF documented).
- Browse harden (`q`/LIKE, a11y, dash fence — no cse.lk from `web/`).
- `pdf_url` + `disclosure_briefs` schema; `chime/briefs/` stub (`AI_BRIEFS_ENABLED=0`).
- Enqueue `disclosure_briefs` on new disclosures.
- Legacy `POST /announcements` → CDN `pdf_url` enrichment.
- Tests: market persist / browse / symbols CSRF regression.

---

## Wave 2 — Phase 2 surface + ops

**Theme:** Ops runbook, optional brief-in-alert, bulk feed, category filter, dash brief/pdf fields, harden.

| SHA | Commit |
|---|---|
| `07b1f82` | docs(wave2): tijori ops enablement |
| `365543c` | feat(wave2): optional brief in alert message |
| `07ebae4` | feat(wave2): optional bulk disclosure feed |
| `90a76e0` | fix(wave2): drop accidental category bleed from bulk feed |
| `a8b4e10` | test(wave2): briefs pdf integration coverage |
| `1d02d3a` | feat(wave2): disclosure category filter |
| `3d45cbe` | feat(wave2): dash disclosure brief+pdf fields |
| `d793a30` | fix(wave2): harden alert parse and disclosure gating |
| `77c4dc0` | fix(wave2): harden legacy PDF enrichment against SSRF and rate gaps |

**Shipped**

- Tijori ops enablement (`docs/runbooks/TIJORI.md`).
- Optional brief text on disclosure Telegram when ready at claim time.
- Optional `DISCLOSURE_BULK_FEED` (no category bleed into bulk path).
- `/alert SYMBOL disclosure [CATEGORY]` filter.
- Dash disclosure API/UI: `brief` + `pdf_url`.
- Legacy PDF enrich SSRF allowlist + rate-gap harden.
- Alert parse / disclosure gating harden; briefs/PDF integration tests.

---

## Wave 3 — Gemini stub + Telegram attach

**Theme:** Provider stub, attach ready brief on push, health hint, XSS egress, coverage.

| SHA | Commit |
|---|---|
| `c70c00c` | fix(wave3): align bot threshold error assertion with finite check |
| `aa8dfd8` | docs(wave3): sync bulk feed ops docs |
| `388d0ca` | fix(wave3): lint type sweep |
| `68608a7` | test(wave3): migration 005 006 presence |
| `722f00e` | test(wave3): alert parse edge coverage |
| `de45bb4` | fix(wave3): harden disclosure brief/pdf egress against XSS |
| `1202399` | feat(wave3): health brief queue hint |
| `6891df4` | feat(wave3): attach ready brief to disclosure Telegram and push |
| `0b22246` | feat(wave3): gemini brief provider stub |

**Shipped**

- Gemini brief provider stub (`chime/briefs/provider.py`).
- Attach ready brief to disclosure Telegram at alert claim.
- Health brief-queue hint.
- Dash brief/pdf egress XSS harden.
- Migrations 005/006 presence tests; alert-parse edge coverage.
- Bulk-feed ops docs sync; lint/type sweep.

---

## Wave 4 — PDF extract + follow-up + browse polish

**Theme:** PDF text extract, brief-ready follow-up notify, movers, shutdown-safe drain, provider harden.

| SHA | Commit |
|---|---|
| `ded9ef4` | chore(wave4): env example parity |
| `18fa33e` | feat(wave4): thin movers endpoint push |
| `c090a5f` | fix(wave4): poller shutdown briefs push |
| `0e45991` | feat(wave4): pdf text extract for briefs push |
| `2c4fb6a` | feat(wave4): brief follow-up Telegram when ready after alert |
| `5cd424e` | feat(wave4): wire brief-ready follow-up notify in worker |
| `e5b9155` | fix(wave4): brief provider harden |
| `8af85da` | fix(wave4): post-wave consistency |
| `49e5c0b` | docs(wave4): plan progress checklist |

**Shipped**

- `.env.example` parity for Tijori flags.
- Thin `GET /api/v1/market/movers` + `/market` top-movers strip.
- Poller shutdown-safe briefs push.
- PDF text extract (`chime/briefs/extract.py`) + worker drain.
- Brief follow-up Telegram via `claim_pending_briefs(..., notify=)` when ready after primary alert.
- Worker wiring for brief-ready notify; provider harden (timeouts / empty candidates).
- Post-wave consistency + plan progress checklist.

---

## Wave 5 — Wave report (this doc)

**Theme:** Single rollup of waves 1–4 commits, what shipped, and what remains.

| SHA | Commit |
|---|---|
| _(this)_ | docs(wave5): wave report |

**Shipped**

- `docs/factory/passes/TIJORI_WAVE_REPORT.md` — commit inventory + remaining backlog.

---

## Commit counts

| Wave | Commits (scoped) |
|---|---|
| 1 (`tijori` + `wave`) | 10 |
| 2 (`wave2`) | 9 |
| 3 (`wave3`) | 9 |
| 4 (`wave4`) | 9 |
| 5 (`wave5` report) | 1 |
| **Total** | **38** |

---

## Remaining

### Phase 2 “live” (ops, not more code required for stub path)

1. Enable `AI_BRIEFS_ENABLED=1` + `AI_API_KEY` in a controlled env.
2. Watch rate caps / `AI_MAX_BRIEFS_PER_DAY` budget under real CSE traffic.
3. Confirm follow-up notify + NFA suffix in production Telegram.

### Still deferred

| Item | Notes |
|---|---|
| Phase 3 scenario AI | On-demand only; daily caps; legal review before MiroFish-style reuse |
| Portfolio / P&L / tax / screener / TA / payments / native app | Explicit non-goals |
| Always-on swarm / commit farming | Factory fence; stop when gates green |

### Suggested next improve-loop focus

- CI green on touched Python/web paths after wave 4.
- Controlled briefs-on soak (not default-on in prod).
- No Phase 3 until Phase 2 live brief path is proven.
