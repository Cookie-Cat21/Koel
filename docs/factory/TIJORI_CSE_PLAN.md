# Quiverly — Tijori-for-CSE Plan

**Branch intent:** `cursor/tijori-cse-phase1-e44e`  
**Updated:** 2026-07-12  
**Product bet:** Be Sri Lanka’s exchange-filing + alert layer (Tijori play), with a thin CSE browse dash, then optional scenario AI. Not a Tracker Pro clone. Not a price oracle.

**Constraint note:** “1000 subagents × 100 loops” is not an execution strategy. Factory fence = quality over count, hard max ~16 concurrent agents, STOP when two passes find nothing above minor. This plan uses a **bounded agentic improve loop** (discover → implement → test → fix → re-test) until gates are green.

---

## 0. What we already have (deep dive)

| Layer | Status |
|---|---|
| CSE adapter + poller + rules + Telegram | Production-hardened |
| Disclosure alerts | Title + announcements link; optional AI brief attach / follow-up (flag-gated) |
| Thin dash | Watchlist / alerts / history / symbol / health / **Browse** |
| Market browse | **Landed** — full `tradeSummary` persist + `/market` (+ thin movers) |
| LLM / PDF pipeline | Schema + enricher + PDF extract + Gemini provider; **default off** |
| Scenario AI | **None** (Phase 3) |

Competitive gap in CSE: Tracker Pro owns portfolio; InvestNow/Rovana own analysis dashboards. Nobody cleanly owns **official filing → plain-language brief → real push**.

---

## 1. Phases

### Phase 1 — Foundations ✅ done (waves 1–2)

1. **Market-wide persist** — every poll stores all `tradeSummary` rows into `stocks` + `price_snapshots`; rule eval stays watchlist-scoped. Fetch even when watchlist empty (browse needs data).
2. **Thin browse** — `GET /api/v1/symbols` + `/market` page (Symbols · name · last · change_pct). Not a screener / OHLC board.
3. **Filing-brief schema + worker stub** — `disclosures.pdf_url`, `disclosure_briefs` table; `koel/briefs/` with provider interface; `AI_BRIEFS_ENABLED=0` default.
4. **Tests** — poller market persist, API list shape, briefs disabled-by-default, web still never calls cse.lk.
5. **Docs** — this plan + contract/IA amendments.

### Phase 2 — Tijori core (mostly landed; live LLM still flag-gated)

1. ✅ **Done** — Legacy `POST /announcements` enricher → resolve `filePath` → `cdn.cse.lk` PDF URL (SSRF/rate hardened).
2. ✅ **Done** — PDF fetch + text extract (size/rate capped; `koel/briefs/extract.py`).
3. ◐ **Partial** — Free-tier LLM brief (Gemini Flash provider wired) on **new** disclosures only; default `AI_BRIEFS_ENABLED=0` until keyed/enabled in prod.
4. ✅ **Done** — Append brief to Telegram disclosure alert when ready, or follow-up: primary alert attaches a ready brief at claim time; if the brief becomes ready later, `claim_pending_briefs` notifies via durable `claim_brief_followups` (`brief_followup:{rule}:{external_id}` in `alert_log`) only when a primary disclosure alert already fired without that brief (fail-soft; always NFA-suffixed; no ready-before-alert double send).
5. ✅ **Done** — Dash symbol page / disclosures API shows brief when `status=ready` (egress-sanitized).
6. ✅ **Done** — Optional category filter on `/alert SYMBOL disclosure [CATEGORY]`.

### Phase 3 — Optional scenario AI (later)

1. On-demand only (“Run scenario” on symbol / filing).
2. Small panel (≤15 personas × ≤8 rounds), queued, daily caps.
3. Label: simulated reactions from public info — **not advice**.
4. MiroFish inspiration / rewrite — avoid AGPL entanglement until legal review.

### Explicit non-goals (still)

Portfolio/P&L, tax, heavy TA, screener, payments, native app, always-on swarm, price targets as product.

---

## 2. Architecture (Phase 1–2)

```
cse.lk tradeSummary ──► poller ──► stocks + price_snapshots (ALL symbols)
cse.lk announcements ──► poller ──► disclosures (+ pdf_url Phase 2)
                                         │
                                         ├─► rules ──► Telegram alert
                                         └─► briefs worker (Phase 2; stub Phase 1)
                                                   └─► disclosure_briefs
                                                         └─► dash / Telegram
web/ ──► Postgres only (ADR 001) ──► /market browse + symbol briefs
```

---

## 3. Acceptance criteria (Phase 1)

| ID | Criterion | Proof |
|---|---|---|
| P1-A | Poller persists non-watched symbols from tradeSummary | unit/integration test |
| P1-B | Empty watchlist still market-persists (no rule fires) | test |
| P1-C | `GET /api/v1/symbols` returns paginated slim quotes from Postgres | route + test / smoke |
| P1-D | `/market` page lists symbols; nav link “Browse” | UI + lint |
| P1-E | Migration adds `pdf_url` + `disclosure_briefs`; migrate applies | migrate dry-run / SQL |
| P1-F | Briefs module importable; disabled without `AI_BRIEFS_ENABLED=1` | unit test |
| P1-G | `web/` still has zero cse.lk calls | existing regression |
| P1-H | ruff + mypy + pytest green on touched paths | CI commands |

---

## 4. Agentic improve loop (bounded)

```
LOOP i = 1..N (N soft-cap 8; STOP early on two clean passes):
  1. Run: ruff, mypy, pytest (unit), web lint/tsc if web touched
  2. Adversarial pass: empty watchlist, huge market list, briefs-off, CSRF, NFA
  3. Fix findings above minor
  4. Re-test
  5. If zero findings above minor twice → STOP
```

No commit farming. One concern per commit where practical.

---

## 5. Env (Phase 1 stub / Phase 2 live)

Ops enablement (poller → browse, briefs flag, PDF sleep): [docs/runbooks/TIJORI.md](../runbooks/TIJORI.md).

```bash
# Phase 1: market browse needs no new env — just run the poller

# PDF enrich (legacy filePath → pdf_url; after alerts, outside poll lock;
# polite sleep before each symbol's legacy /announcements call; default 0.5)
PDF_ENRICH_SLEEP_SECONDS=0.5

# Optional bulk disclosure discovery (exists in poller; default off).
# DISCLOSURE_BULK_FEED=1 → POST /approvedAnnouncement + stocks name map;
# fail-soft to per-symbol getAnnouncementByCompany. Not DISCLOSURE_BULK.
DISCLOSURE_BULK_FEED=0

# Phase 2 (documented now, default off)
AI_BRIEFS_ENABLED=0
AI_PROVIDER=gemini
# AI_PROVIDER=groq|openrouter
AI_API_KEY=
AI_MODEL=gemini-2.0-flash
# AI_MODEL=llama-3.3-70b-versatile  # groq
# AI_MODEL=openai/gpt-4o-mini      # openrouter
AI_MAX_BRIEFS_PER_DAY=50
AI_MAX_INPUT_CHARS=12000
PDF_MAX_BYTES=5242880
```

---

## 6. Success metric (product)

User can: browse CSE symbols in dash → watch → set disclosure alert → get Telegram ping when filing lands → (Phase 2) read a short AI brief of the official filing. Scenario AI is optional polish, not the wedge.

---

## Wave execution log

**2026-07-12** — User override for this Tijori multi-wave: allow **max parallelism** and **long improve loops** beyond the usual factory soft caps (still prefer disjoint OWNED_FILES; stop early when gates are green).

### Progress rollup

| Track | Status |
|---|---|
| Phase 1 foundations | ✅ done |
| Phase 2 Tijori core | ◐ mostly done — live Gemini still flag/key gated |
| Phase 3 scenario AI | not started |
| Improve-loop / CI on touched paths | ongoing (wave harden passes) |

### Wave 1 — Phase 1 foundations + PDF enrich kickoff

- [x] Market-wide `tradeSummary` persist (`a802cb7`); empty-watchlist still persists
- [x] Batch market snapshot persist + health/dedupe harden
- [x] `GET /api/v1/symbols` + `/market` Browse (session-only GET; CSRF docs)
- [x] Market browse harden (`q`/LIKE, a11y, fence)
- [x] `pdf_url` + `disclosure_briefs` schema; `koel/briefs/` stub (`AI_BRIEFS_ENABLED=0`)
- [x] Enqueue `disclosure_briefs` rows on new disclosures
- [x] Legacy `POST /announcements` → CDN `pdf_url` enrichment (Phase 2 #1 start)
- [x] Tests: market persist / browse / symbols CSRF regression

### Wave 2 — Phase 2 surface + ops

- [x] Tijori ops enablement runbook (`docs/runbooks/TIJORI.md`)
- [x] Optional brief text in disclosure alert message
- [x] Optional bulk disclosure feed (`DISCLOSURE_BULK_FEED`; no category bleed)
- [x] Disclosure category filter (`/alert SYMBOL disclosure [CATEGORY]`)
- [x] Dash disclosure API/UI: `brief` + `pdf_url` fields
- [x] Legacy PDF enrich harden (SSRF allowlist, rate gaps)
- [x] Alert parse / disclosure gating harden
- [x] Briefs/PDF integration test coverage

### Wave 3 — Gemini stub + Telegram attach

- [x] Gemini brief provider stub (`koel/briefs/provider.py`)
- [x] Attach ready brief to disclosure Telegram push
- [x] Health brief-queue hint
- [x] Harden disclosure brief/pdf egress against XSS (dash)
- [x] Migrations 005/006 presence tests; alert-parse edge coverage
- [x] Bulk-feed ops docs sync; lint/type sweep

### Wave 4 — PDF extract + follow-up + browse polish

- [x] Env example parity for Tijori flags
- [x] Thin `GET /api/v1/market/movers` + `/market` top-movers strip
- [x] Poller shutdown-safe briefs push
- [x] PDF text extract for briefs (`koel/briefs/extract.py` + worker drain)
- [x] Brief follow-up Telegram when ready after alert (`claim_pending_briefs(..., notify=)`)
- [x] Wire brief-ready notify through worker; provider harden (timeouts / empty candidates)
- [x] Post-wave consistency pass

### Wave 5 — Follow-up idempotency

- [x] Brief follow-up claim-gated via `alert_log` (`brief_followup:…`); skip ready-before-alert / brief-already-attached

**Remaining for Phase 2 “live”:** enable `AI_BRIEFS_ENABLED=1` + `AI_API_KEY` in a controlled env; watch rate caps / daily brief budget; no Phase 3 work yet.
