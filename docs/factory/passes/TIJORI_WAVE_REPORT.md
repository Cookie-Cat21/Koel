# Tijori CSE — Waves 1–9 report

**Branch:** `cursor/tijori-cse-phase1-e44e`  
**Date:** 2026-07-12  
**Plan:** [TIJORI_CSE_PLAN.md](../TIJORI_CSE_PLAN.md)  
**Ops:** [docs/runbooks/TIJORI.md](../../runbooks/TIJORI.md)  
**Range:** `a802cb7` … `6be6430` (+ this wave-9 report refresh)

---

## Verdict

Phase 1 foundations and Phase 2 Tijori-core plumbing are **landed** across waves 1–5. Waves 6–7 add sectors browse, storage/SQL harden, retention/sectors coverage, Groq provider, disclosure baseline watermark, and briefs PDF grace / late follow-up sweep. Waves 8–9 add OpenRouter provider, brief drain pacing, market UX/a11y polish, adversarial grace/storage close, env-example completeness, storage brief-method coverage, and a Phase 3 scenario stub fence (`AI_SCENARIOS_ENABLED=0`). Live LLM briefs remain **flag/key gated** (`AI_BRIEFS_ENABLED=0` default; `AI_PROVIDER=gemini|groq|openrouter`). Phase 3 scenario AI is **stub only** — no LLM wiring yet.

| Track | Status |
|---|---|
| Phase 1 foundations | ✅ done |
| Phase 2 Tijori core | ◐ mostly done — live LLM still off until keyed |
| Phase 3 scenario AI | ◐ stub fence only (`AI_SCENARIOS_ENABLED=0`) |
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

## Wave 5 — Wave report + Tijori surface polish

**Theme:** Wave rollup, bot copy, briefs coverage, optional retention/sectors ingest, movers/follow-up harden.

| SHA | Commit |
|---|---|
| `67ee2cf` | docs(wave5): wave report |
| `1240f80` | feat(wave5): bot copy tijori surfaces push |
| `0c075d9` | test(wave5): briefs extract provider coverage |
| `81d7dc4` | feat(wave5): optional non-watchlist snapshot retention |
| `a45b306` | fix(wave5): movers harden push |
| `44bbc3a` | feat(wave5): optional sectors ingest |
| `2e4514e` | fix(wave5): brief followup idempotency push |

**Shipped**

- Initial `TIJORI_WAVE_REPORT.md` rollup (waves 1–4).
- Bot copy for Tijori surfaces; briefs extract/provider coverage.
- Optional non-watchlist snapshot retention; optional sectors ingest.
- Movers harden; brief follow-up idempotency.

---

## Wave 6 — Sectors browse + harden + coverage

**Theme:** Seed/browse docs, sectors UI, follow-up isolation, SQL harden, CI, retention/sectors tests, adversarial briefs/PDF sweep.

| SHA | Commit |
|---|---|
| `46cb49e` | docs(wave6): seed browse via tick --force |
| `74473fe` | feat(wave6): sectors browse surface |
| `29d923b` | test(wave6): followup key isolation |
| `4da7397` | chore(wave6): dead code cleanup |
| `18a1969` | fix(wave6): storage sql harden push |
| `c2cca70` | fix(wave6): ci |
| `1bd98be` | test(wave6): retention sectors poller coverage |
| `02d4d59` | fix(wave6): adversarial sweep |

**Shipped**

- Ops/docs: seed browse via `tick --force` (Makefile / README / TIJORI runbook).
- `/market` sectors browse surface.
- Follow-up key isolation tests; dead-code cleanup.
- Parameterized UNNEST inserts for market snapshots + sectors (no f-string VALUES).
- CI: fence tokens, sectors route pins, dash_smoke + migrate 007/008 notes.
- Retention log + `SECTORS_INGEST` fail-soft poller coverage.
- Adversarial harden: honor `SendResult` on brief follow-up; reject CDN PDF redirects / non-200; primary-alert + paragraph-bounded brief skip; PDF page/char caps; batch retention deletes; `processing` `brief_status` in dash egress.

---

## Wave 7 — Assert harden + Groq + briefs grace

**Theme:** Flake-proof retention/sectors asserts; Groq provider; disclosure baseline; PDF grace / late follow-up / env harden; wave report append.

| SHA | Commit |
|---|---|
| `c016b06` | fix(wave7): assert retention/sectors via mocks not stdout logs |
| `a3ae6e4` | docs(wave7): makefile readme tijori pointers |
| `76bfce4` | docs(wave7): wave report append |
| `af4ad49` | test(wave7): alert parse fuzz |
| `75b8dc9` | feat(wave7): groq brief provider |
| `c0d5d60` | test(wave7): disclosure baseline push |
| `c483c83` | fix(wave7): briefs PDF grace, late follow-up sweep, env harden |

**Shipped**

- Retention/sectors tests assert via mocks (not `capsys` stdout logs) to avoid full-suite capture flakes.
- Makefile / README Tijori pointers; `TIJORI_WAVE_REPORT.md` waves 6–7 append.
- Alert-parse fuzz coverage; disclosure create-watermark baseline (no historical flood).
- `AI_PROVIDER=groq` OpenAI-compatible chat path (+ httpx-mocked coverage).
- Briefs PDF grace (wait for `pdf_url` before title-only summarize), late follow-up retry after primary delivery, promote recent skipped rows when AI enabled, soft-parse `BriefSettings`, aclose owned providers after drain.

---

## Wave 8 — OpenRouter + pacing + adversarial close

**Theme:** OpenRouter provider, brief drain pacing, market UX polish, grace/storage adversarial close, docs.

| SHA | Commit |
|---|---|
| `8bf12b0` | docs(wave8): third party pypdf |
| `8b5e28a` | docs(wave8): claude status tijori |
| `f854cb2` | feat(wave8): market UX polish |
| `371c72a` | test(wave8): poller brief pdf coverage |
| `cb6bad8` | feat(wave8): brief drain pacing |
| `6539563` | feat(wave8): openrouter brief provider |
| `bd61382` | fix(wave8): briefs grace, late follow-up, groq defaults |
| `e264242` | docs(wave8): mention openrouter in BriefSettings |
| `78f536d` | fix(wave8): storage grace + follow-up sweep starvation |

**Shipped**

- Third-party `pypdf` note; CLAUDE.md Tijori status; OpenRouter in `BriefSettings` docs.
- `/market` movers **Watch** links + “Add via watchlist” note (no inline watch POST).
- Poller brief/PDF fail-soft coverage (worker errors, cancel re-raise, enrich edge cases).
- `AI_BRIEF_SLEEP_SECONDS` pacing between consecutive LLM drain calls.
- `AI_PROVIDER=openrouter` OpenAI-compatible path (+ soft-default model when unset).
- Adversarial close: grace keyed off `updated_at` (promote-safe); reject empty `pdf_url`; late follow-up sweep only ready briefs missing a follow-up row (oldest-first); Groq soft-default model; list content-part parse.

---

## Wave 9 — Format, env docs, scenario stub, coverage, a11y

**Theme:** Ruff format; complete `.env.example`; scenario AI stub fence; storage brief-method coverage; market a11y; wave report refresh.

| SHA | Commit |
|---|---|
| `d46e3ea` | style(wave9): ruff format chime and tests |
| `b67c559` | chore(wave9): env example complete |
| `9530172` | docs(wave9): wave report refresh |
| `b438154` | feat(wave9): scenario AI stub fence |
| `f652f9d` | test(wave9): storage brief methods coverage |
| `6be6430` | fix(wave9): market a11y push |
| _(this)_ | docs(wave9): wave report refresh |

**Shipped**

- `ruff format` over `chime/` and related tests (style-only).
- Root + `web/.env.example`: remaining `Settings` knobs (`HTTP_TIMEOUT_SECONDS`, `MARKET_*`) and annotated `BriefSettings` AI/PDF/BRIEF flags.
- `chime/scenarios/` stub gated by `AI_SCENARIOS_ENABLED=0` with NFA guardrails (reject buy/sell language); no LLM wiring.
- Unit coverage for claim/list/mark/count/promote brief storage paths.
- `/market` a11y: merged movers symbol+Watch labelled link; list headings via `aria-labelledby`; sectors empty/truncation + change-direction cues.
- `TIJORI_WAVE_REPORT.md` — waves 8–9 inventory + updated totals.

---

## Commit counts

| Wave | Commits (scoped) |
|---|---|
| 1 (`tijori` + `wave`) | 10 |
| 2 (`wave2`) | 9 |
| 3 (`wave3`) | 9 |
| 4 (`wave4`) | 9 |
| 5 (`wave5`) | 7 |
| 6 (`wave6`) | 8 |
| 7 (`wave7`) | 7 |
| 8 (`wave8`) | 9 |
| 9 (`wave9` + this report) | 7 |
| **Total** | **75** |

---

## Remaining

### Phase 2 “live” (ops, not more code required for stub path)

1. Enable `AI_BRIEFS_ENABLED=1` + `AI_API_KEY` in a controlled env (`AI_PROVIDER=gemini|groq|openrouter`).
2. Watch rate caps / `AI_MAX_BRIEFS_PER_DAY` + `AI_BRIEF_SLEEP_SECONDS` under real CSE traffic.
3. Confirm follow-up notify + NFA suffix in production Telegram.

### Still deferred

| Item | Notes |
|---|---|
| Phase 3 scenario AI (beyond stub) | On-demand only; daily caps; legal review before MiroFish-style reuse |
| Portfolio / P&L / tax / screener / TA / payments / native app | Explicit non-goals |
| Always-on swarm / commit farming | Factory fence; stop when gates green |

### Suggested next improve-loop focus

- CI green on touched Python/web paths after wave 9.
- Controlled briefs-on soak (not default-on in prod).
- Keep `AI_SCENARIOS_ENABLED=0` until Phase 2 live brief path is proven.
