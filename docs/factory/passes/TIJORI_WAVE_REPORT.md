# Tijori CSE — Waves 1–91 report

**Branch:** `cursor/tijori-cse-phase1-e44e`  
**Date:** 2026-07-13  
**Plan:** [TIJORI_CSE_PLAN.md](../TIJORI_CSE_PLAN.md)  
**Ops:** [docs/runbooks/TIJORI.md](../../runbooks/TIJORI.md)  
**Range:** `a802cb7` … wave 91 (post-100% harden → soft ~100)

---

## Parallelism honesty (wave 12)

This Tijori multi-wave was **not** “1000 concurrent agents × 100 empty loops.” Actual shape:

- **~15 max-width waves** of bounded parallel agents (disjoint `OWNED_FILES` per lane; factory soft caps still apply unless a wave explicitly raised them).
- **~100+ agent tasks** across the scoped `wave` / `waveN` / `wN` inventory below — real commits that ship code, tests, or docs, not empty improve-loop iterations.
- **Quality-gated:** one concern per commit; stop when gates are green / two passes find nothing above minor — no always-on swarm or commit farming.
- **Wave 14+:** continue the same bounded improve loop toward a soft ~100 quality-gated loop horizon (discover → implement → test → fix → re-test). Not empty concurrency theater; early STOP still wins when CLEAN×2.

Matches the plan constraint note in [TIJORI_CSE_PLAN.md](../TIJORI_CSE_PLAN.md). Treat any “1000×100” framing as aspiration rhetoric, not an execution log.

---

## Verdict

Phase 1 foundations and Phase 2 Tijori-core plumbing are **landed** across waves 1–5. Waves 6–7 add sectors browse, storage/SQL harden, retention/sectors coverage, Groq provider, disclosure baseline watermark, and briefs PDF grace / late follow-up sweep. Waves 8–9 add OpenRouter provider, brief drain pacing, market UX/a11y polish, adversarial grace/storage close, env-example completeness, storage brief-method coverage, and a Phase 3 scenario stub fence (`AI_SCENARIOS_ENABLED=0`). Wave 10 hardens briefs ops (smoke, rate limits, CDN requeue, poller/disclosure coverage) and audits poll↔brief advisory locks as a non-issue. Wave 11 aligns `/brief` empty-state test copy with AI-off messaging. Wave 12 records parallelism honesty (plus follow-on fix/docs/test lanes). Wave 13 closes browse API examples, env sync, Telegram/dash URL egress caps, web adversarial harden, and coverage pushes (migrate / storage / CSE / poller / bot). Wave 14 ships coverage/harden lanes (web regress, health/circuit, config/migrate, main, rules format fuzz, worker) plus fail-closed non-finite float env knobs. Wave 15 adds `make tijori-report`, briefs extra-install docs, help-budget / web movers / briefs / residual coverage, and ops-knob harden. **Wave 16 milestone:** full-package `pytest --cov=chime` at **100%** (3427 stmts / 0 miss) — coverage ratchet complete; post-milestone CSE pacing, brief egress, NFA chrome, and integration-collect harden. **Wave 17** closes post-100% harden (loop status, storage NaN defense, CSE pace concurrency, login a11y, factory verify, health proxy timeout, DL/`myalerts`/lease floor, finite price egress). **Wave 18** hardens dash/ops (brief-queue health UI, category cancel, watchlist duplicate soft flag, sparkline finite filter, category confirm / history egress / nested health). **Wave 19** documents dash CSRF, aligns `/unwatch` copy, adds dash disclosure category, and hardens history/watchlist/browse egress. **Wave 20** advances loop status + report, START browse note, and cancel-id / category-read / dash egress harden. **Wave 21** hardens alerts history/list/forms symbol filters (`normalizeSymbol` / `invalid_symbol`), disclosure SafeInteger ids, and logout hard-redirect UX. **Wave 22** pushes loop status + symbol not-found Browse link (late sectors/alerts/health egress pin). **Wave 23** hardens sectors/health/browse egress + safe ids and rolls the report. **Wave 24** points `/market` empty state at `make tick` / poller seed (late history/watchlist/login SafeInteger pin). **Wave 25** hard-redirects mid-use 401 / missing CSRF to `/login?expired=1` and pins egress harden. **Wave 26** advances loop status (late mapRule/alerts/watchlist fail-closed pin). **Wave 27** hardens toIso/delivery/SafeInteger egress and rolls the report. **Wave 28** restores web `tsc` (`BigInt()` / sanitize string guards) + loop status (late sector ids / browse limits / toIso / session pin). **Wave 29** hardens demo auth telegram_id / allowlist via digits-only `toSafePositiveInt`. **Wave 30** keeps alert-form disclosure category a11y (`aria-describedby` / maxLength / `aria-busy`) (late symbol/health/nav fail-closed pin). **Wave 31** rolls the report (late session exp/sid / market numbers / health timeout / labels pin). **Wave 32** advances loop status + hardens `toFiniteNumber` / health SafeInt / alert thresholds. **Wave 33** resolves AppNav active state for `/scenarios` (longest-prefix) (late session/CSRF token caps + health body bound). **Wave 34** extends loading NFA chrome to browse/health/symbol shells (late history pagination / strict booleans / client finite). **Wave 35** hardens SSRF host / session mint / CSRF+symbol decode / formatTs. **Wave 36** advances loop status + hardens SSR loopback / HEALTH_URL SSRF / JSON body / CSRF path. **Wave 37** gates `apiMutate` to `/api/v1/*` and fails closed NavSession `/me` timestamps/CSRF. **Wave 38** bounds SSR fetch timeout/body and caps alert thresholds. **Wave 39** hardens `/me` parse, cancel id, session TTL, threshold, and SSR bounds. **Wave 40** pins SSR origin / HEALTH_URL / JSON body / CSRF path. **Wave 41** advances loop status + caps CSRF cookie / mapRule threshold / SSR Content-Length early-reject. **Wave 42** caps `jsonError` egress + pins SSR Cookie/CT/CL. **Wave 43** centralizes session/CSRF cookie Secure+SameSite helpers. **Wave 44** caps mapRule thresholds (parity GET `/alerts`). **Wave 45** bounds client mutate/login/NavSession, gates Unwatch, fail-closed SYMBOL_RE egress. **Wave 46** advances loop status + SYMBOL_RE page egress / health watched+CL. **Wave 47** early-rejects client Content-Length before body allocate. **Wave 48** aligns alerts empty CTAs with Browse + sectors SYMBOL_RE / SSR statusText / client CL. **Wave 49** sanitizes sparkline timestamps + pins circuit/sectors. **Wave 50** caps toast/inline copy, fail-closes format digits, bounds sparkline series, and appends the 46–50 rollup. **Wave 51** advances loop status + fail-closes bounded-reader `maxBytes`. **Wave 52** bounds GET `/alerts`/`/watchlist` SQL LIMITs + toast tone/timers + demo allowlist. **Wave 53** stream-bounds response bodies (`readBoundedResponseText`) so missing/understated Content-Length cannot bypass allocate caps. **Wave 54** fail-closes sanitize `maxLen`, caps EmptyState titles, typeof-guards InlineError, clamps skeleton rows, and caps page list parsers. **Wave 55** fail-closes format abs-caps + `alertTypeLabel` typeof and appends the 51–55 rollup. **Wave 56** advances loop status + fail-closed brief/PDF max caps. **Wave 57** typeof/length-caps API path/nav/CSRF. **Wave 58** history pagination a11y + threshold/sanitize. **Wave 59** sparkline abs-cap + toIso range. **Wave 60** toFiniteNumber abs-cap + report. **Wave 61** advances loop status + body abs-cap / formatTs range / session+category typeof. **Wave 62** bot threshold abs-cap + HEALTH_URL typeof. **Wave 63** sparkline/stale ts range + attempt cap. **Wave 64** health age range + dash auth env. **Wave 65** filing URL isinstance + notify symbol + mint secret. **Wave 66** advances loop status + pins briefs/scenarios/bot env + list isinstance. **Wave 67** bot/poller/storage/brief env isinstance. **Wave 68** brief prompt / resolve / alert parse / storage symbol isinstance. **Wave 69** isinstance/typeof fail-closed + price/log + env typeof. **Wave 70** config/poller/guardrails/browse/session + disclosure/DoA/sanitize guards. **Wave 71** advances loop status + wave67 pin import hygiene. **Wave 72** pins cancel/brief/CSE/persist isinstance/typeof fail-closed. **Wave 73** adds layout viewport meta and broad state/CSE/web fail-closed guards. **Wave 74** pins rule.type getattr + stock-name/board persist guards. **Wave 75** rolls 71–75 and late rate/row-mapper harden. **Wave 76** advances loop status + wraps the wave75 pin + fail-closed soft-accept pin (cmd_brief / claim / unsent / category / row mappers). **Wave 77** closes late w71 brief follow-up `str()` soft-accept (+ late health ok / DL attempts / ensure_user id). **Wave 78** restores isinstance pins and fail-closes persist/disclosure ids + promote counts. **Wave 79** lands the soft-accept implementation (cmd_brief / claim / unsent / category / row ids). **Wave 80** pins the soft-accept contract and appends the 76–80 rollup toward soft ~100 — not cov gap-fill. **Wave 81** advances loop status (+ late notify/CSE soft-accept close). **Wave 82** pins claim/attempt/lock/health/count soft-accepts. **Wave 83** adversarial CLEAN (diminishing returns on further `int(True)` / `True==1` pin churn) + late CDN status/length/redirect soft-accept. **Wave 84** lands claim/lock/health/count fail-closed helpers + pins. **Wave 85** pins the same contract and appends the 81–85 rollup. **Wave 86** advances loop status + post-CDN adversarial CLEAN. **Wave 87** CLEANs WS-087 clock-skew claim invariant (+ lands CSE HTTP classify fail-closed). **Wave 88** ops-polish runbook + brief daily-cap/lease soft-accept harden. **Wave 89** records the CSE status/CT/pace soft-accept close. **Wave 90** pins CSE status/CT/pace and appends this 86–90 rollup toward soft ~100. Live LLM briefs remain **flag/key gated** (`AI_BRIEFS_ENABLED=0` default; `AI_PROVIDER=gemini|groq|openrouter`). Phase 3 scenario AI is **stub only** — no LLM wiring yet.

Wave 91 lands focused bool numeric / CLI / disclosure / health harden and refreshes the loop snapshot toward w92–w100.

| Track | Status |
|---|---|
| Phase 1 foundations | ✅ done |
| Phase 2 Tijori core | ◐ mostly done — live LLM still off until keyed |
| Phase 3 scenario AI | ◐ stub fence only (`AI_SCENARIOS_ENABLED=0`) |
| `chime` unit coverage | ✅ **100%** (wave 16 milestone) |
| Improve-loop / CI on touched paths | ongoing — wave 91 post-100% harden → soft ~100 loops |

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

## Wave 10 — Smoke, harden, coverage, lock audit

**Theme:** Tijori smoke; API contract sync; brief rate limit; advisory-lock audit; poller/disclosure coverage; CDN requeue + `/brief` egress + scenario fence.

| SHA | Commit |
|---|---|
| `35b1b97` | chore(wave10): tijori smoke script |
| `821bbbb` | docs(wave10): contract sync |
| `c251b00` | chore(wave10): clear todos |
| `aa87ed9` | fix/test(wave10): brief rate limit push |
| `303ffbc` | docs(wave10): defer poll/brief advisory lock deadlock |
| `c6eb42f` | test(wave10): disclosure rules fuzz push |
| `0070ea1` | test(wave10): poller coverage push |
| `cd5b5f3` | fix(wave10): brief CDN requeue, /brief egress, scenario fence |

**Shipped**

- Tijori smoke script; API contract sync; drop leftover Phase-1 stub naming in briefs worker/docs.
- `/brief` behind the same per-user cmd rate limit as other handlers (+ shared-budget / structural gate tests).
- Audit: poll `4_201_337` (session try) vs brief-cap `4_201_339` (xact) — **no deadlock**; pin `BRIEF_CAP_LOCK_ID` + docs ([ADVISORY_LOCK_DEADLOCK.md](ADVISORY_LOCK_DEADLOCK.md)). Do not unify IDs.
- Disclosure-rules fuzz; poller coverage wave-10 suite.
- CDN miss requeues pending (no daily-cap burn); hostile `pdf_url` fails closed; `/brief` strips non-CSE URLs, caps Telegram body, splits AI-off vs none-yet; scenario guardrails reject accumulate/short/long/exit/take-profit phrasing.

---

## Wave 11 — /brief polish, smoke make, dash headers, wave report

**Theme:** Align `/brief` empty-state; Makefile tijori-smoke; brief-command docs; dash security headers; append waves 10–11 to this report.

| SHA | Commit |
|---|---|
| `bee6aee` | fix(wave11): align /brief empty-state assertion with AI-off copy |
| `4e4967e` | chore(wave11): make tijori-smoke |
| `cbcf3d2` | docs(wave11): brief command docs |
| `36f9ec6` | docs(wave11): wave report append |
| `6ff1cc5` | feat(wave11): dash security headers |

**Shipped**

- `/brief` empty-state assertion matches AI-off bot copy (`tests/test_bot_rate_limit.py`).
- `make tijori-smoke` target; README + TIJORI runbook document `/brief SYMBOL` (AI-off vs none-yet).
- Dash security headers (`web/next.config.ts` + README note).
- `TIJORI_WAVE_REPORT.md` — waves 10–11 inventory + updated totals.

---

## Wave 12 — Parallelism honesty

**Theme:** Document actual multi-wave shape vs “1000 concurrent / 100 empty loops” rhetoric.

| SHA | Commit |
|---|---|
| _(this)_ | docs(wave12): parallelism honesty |

**Shipped**

- Honest parallelism note at top of this report: bounded max-width waves, real agent tasks, quality-gated — not 1000 concurrent × 100 empty loops (counts refreshed in later waves).

---

## Wave 13 — Browse examples, egress, coverage

**Theme:** Thin browse API curl examples; env sync; Telegram/dash URL egress caps; web adversarial harden; migrate/storage/CSE/poller/bot coverage.

| SHA | Commit |
|---|---|
| `b06d960` | docs(wave13): browse api examples |
| `9c65e59` | test(w13): migrate sanity |
| `4cf7d66` | docs(w13): wave report start + env sync |
| `c853677` | test(w13): storage coverage push |
| `75aceb1` | test(w13): cse coverage push |
| `f22081c` | fix(w13): Telegram brief/PDF URL egress caps |
| `86b7f32` | fix(w13): web push |
| `24b3f58` | test(w13): poller coverage push |
| `cd6cd73` | test(w13): bot coverage push |

**Shipped**

- [API_BROWSE_EXAMPLES.md](../API_BROWSE_EXAMPLES.md) — session + `/api/v1/symbols|market|sectors` curl companions to the v1 contract.
- Root `.env.example` aligned with `Settings` / `BriefSettings`; `web/.env.example` gained `BRIEF_CDN_BACKOFF_SECONDS` on the poller/briefs exclusion list.
- Migrate sanity without `DATABASE_URL`; storage / CSE adapter / poller / bot coverage pushes.
- Telegram brief/PDF URL egress caps (length/control rejects; title strip; 4096 body budget); mirrored on dash egress.
- Web adversarial close for `/market`, `/scenarios`, movers, and sectors (coerce JSON, movers sides/sign, bound sectors).

---

## Wave 14 — Continue to ~100 loops

**Theme:** Open the long improve-loop continuation toward a soft ~100 quality-gated loop horizon (plan override: max parallelism + long loops; still STOP on CLEAN×2).

| SHA | Commit |
|---|---|
| `40f59f3` | docs(w14): push |
| `62f08b0` | test(w14): web regress push |
| `337de60` | test(w14): health circuit push |
| `cc99daf` | test(w14): config migrate push |
| `4e28006` | test(w14): main coverage push |
| `588ff0c` | test(w14): rules format fuzz |
| `f54c2ee` | test(w14): worker coverage push |
| `1b2e87b` | fix(w14): reject non-finite float env knobs |

**Shipped**

- `TIJORI_WAVE_REPORT.md` — close wave 13 inventory; open wave 14 continue-to-~100 framing.
- `/scenarios` stub + `next.config.ts` security-header web regressions.
- Health + circuit breaker coverage to 100% line/branch; config `_float` + migrate `__main__` coverage; `chime.__main__` remaining branches.
- Rules format fuzz: fail-closed non-finite price-rule eval; Telegram-safe `format_alert_message` clamp; never-raise corpus.
- Briefs worker coverage: title-only fallback, empty PDF extract, follow-up/promote/CDN edges.
- Fail-closed env parse: `nan`/`inf`/invalid floats (and invalid ints) → defaults (`POLL_INTERVAL_SECONDS`, BriefSettings timeout/sleep).

---

## Wave 15 — Continue improve loops

**Theme:** Next bounded quality-gated lane toward the soft ~100 loop horizon (STOP on CLEAN×2; no empty farming).

| SHA | Commit |
|---|---|
| `116125c` | chore(w15): make tijori-report |
| `729afd4` | docs(w15): briefs extra install |
| `634f7a0` | docs(w15): report |
| `8cf1643` | test(w15): web movers finite push |
| `5b0ba38` | test(w15): help budget push |
| `35360c7` | test(w15): briefs package push |
| `d6b4a59` | fix(w15): clamp ops knobs, DL egress, alert threshold |
| `fdf8153` | test(w15): residual coverage push |

**Shipped**

- `make tijori-report` — cat `TIJORI_WAVE_REPORT.md` from Makefile help.
- README Setup: optional `pip install -e ".[briefs]"` (pypdf) for PDF extract.
- `TIJORI_WAVE_REPORT.md` — close wave 14 inventory; open/continue wave 15 toward ~100 (honest: real commits only).
- Web movers/symbols unit coverage for finite filters (NaN/±Infinity egress, down-sign, price-null).
- Help/START budget pins after Wave12 scenarios note; briefs extract package coverage.
- Fail-closed ops knobs (non-positive poll/timeout/circuit/health → defaults); DL Telegram symbol sanitize; RetryAfter sleep bound; bot rate env harden; `POST /alerts` reject `threshold<=0`.
- Residual coverage push (`test_coverage_wave15.py`) closing remaining bot / extract / provider / config branches — sets up wave 16 100% milestone.

---

## Wave 16 — 100% coverage milestone + CSE soft pacing

**Theme:** Record the full-package coverage milestone after wave 15 residual push; post-milestone harden/ops (CSE soft pacing, egress, NFA, integration collect).

| SHA | Commit |
|---|---|
| `5130bb4` | feat(w16): watchlist CTA polish |
| `e6f55cf` | fix(w16): scripts lint |
| `72e3e3e` | docs(w16): report push |
| `314bdc4` | fix(w16): symbol brief a11y push |
| `1af2917` | fix(w16): nfa chrome push |
| `766b10b` | feat/docs(w16): cse pacing push |
| `5f6ed7e` | fix(w16): brief egress, HELP category, NaN persist |
| `552e4f7` | test(w16): integration collect push |

**Shipped**

- **Milestone:** `pytest --cov=chime` → **TOTAL 3427 stmts / 0 miss / 100%** across every `chime` module (adapters, bot, briefs, circuit, config, domain, health, migrate, notify, poller, rules, scenarios, storage, `__main__`).
- `TIJORI_WAVE_REPORT.md` — close wave 15 inventory; note 100% coverage milestone; post-milestone improve-loops are harden/ops (not cov gap-fill).
- Floor remains `--cov-fail-under=85` in `pyproject.toml` (ratchet-to-100 measured here; keep CI floor unless a later lane intentionally raises it).
- Watchlist empty-state CTA aligns with Browse nav; `scripts/` in factory-verify ruff; symbol brief a11y (`aria-labelledby` + filing-link announce).
- Dash NFA chrome on home + list skeletons; **`CSE_MIN_INTERVAL_SECONDS`** soft gap on shared `CSEClient` (default off).
- Brief Telegram hard-clamp / hostile-symbol strip; HELP CATEGORY copy; skip non-finite market persist; pytest `integration` mark + CI no-skip collect gate.

---

## Wave 17 — Post-100% harden continue

**Theme:** Bounded quality-gated lane after wave 16 close (STOP on CLEAN×2; no empty farming). Loop status, storage NaN defense, CSE pace concurrency, login a11y, factory verify, health proxy timeout, DL/`myalerts`/lease floor, finite price egress.

| SHA | Commit |
|---|---|
| `63555b4` | docs(w17): loop status push |
| `f781df7` | test(w17): storage line 145 push |
| `0f3b8d7` | test(w17): cse pace concurrent push |
| `2692a1b` | fix(w17): login a11y push |
| `fe1c2fc` | fix(w17): factory verify push |
| `e26f98c` | docs(w17): report push |
| `0be994f` | fix(w17): health proxy push |
| `9da9640` | fix(w17): health proxy push |
| `0a659df` | fix(w17): dead-letter egress, myalerts, lease floor |

**Shipped**

- [LOOP_STATUS.md](LOOP_STATUS.md) — waves-completed / coverage / loop-posture snapshot pointing at this report.
- Storage unit coverage: `persist_market_snapshots` skips NaN/±Inf prices (defense-in-depth after adapter filter).
- CSE `_pace()` concurrent coverage; login a11y (explainer list, Telegram ID `aria-describedby`/`aria-invalid`, busy submit, DASH_IA pins).
- Factory-verify harden push.
- Health proxy: keep `AbortSignal` armed through body parse; always `clearTimeout` in finally; fail-closed `HEALTH_PROXY_TIMEOUT_MS`; abort→503 pin; timer-ref so Promise-only hangs still abort.
- Dead-letter Telegram egress cap (hostile symbols / attempts); `/myalerts` null/NaN threshold harden + list clamp; `claim` lease floor `>=1`; finite-only price egress on symbol/watchlist/snapshots/alerts APIs.
- `TIJORI_WAVE_REPORT.md` — close wave 16 inventory; open/close wave 17 toward soft ~100.

---

## Wave 18 — Post-100% harden continue

**Theme:** Bounded quality-gated lane after wave 17 close (STOP on CLEAN×2; no empty farming). Loop status + report rollup; dash brief-queue health UI; category cancel; watchlist duplicate soft flag; sparkline finite filter; category confirm / history egress / nested health harden.

| SHA | Commit |
|---|---|
| `961fa32` | docs(w18): loop status push |
| `62521e2` | docs(w18): report push |
| `98cdbc6` | feat(w18): health brief queue UI push |
| `3c14320` | test/fix(w18): category cancel push |
| `8ade230` | fix(w18): watchlist duplicate push |
| `fee830c` | fix(w18): sparkline harden push |
| `98da2ec` | fix(w18): category confirm, history egress, health nested |

**Shipped**

- [LOOP_STATUS.md](LOOP_STATUS.md) — waves-completed through w17; status push **w18**; horizon still soft ~100.
- `TIJORI_WAVE_REPORT.md` — close wave 17 inventory; open wave 18 continue toward soft ~100.
- Health proxy forwards loopback `brief_queue`; `/health` renders ops-only Brief queue when present (hint never degrades status).
- Category-cancel coverage + bot harden; `POST /watchlist` `created` soft flag (200 when already watched) + dash toast.
- Sparkline / snapshots drop null/NaN/±Inf; empty-state when fewer than two finite ticks.
- Disclosure category cap/sanitize for Telegram confirm + storage; alerts history finite-id / message sanitize; stop `HEALTH_URL` nested poller raw-spread from overwriting typed booleans/`watched_missing`.

---

## Wave 19 — CSRF, unwatch, disclosure category, egress

**Theme:** Document dash double-submit CSRF contract; align `/unwatch` Telegram copy; dash disclosure category; history/watchlist/browse egress + safe ids.

| SHA | Commit |
|---|---|
| `5fb63c4` | docs(w19): csrf note |
| `d063d24` | feat(w19): unwatch copy |
| `cfca204` | feat(w19): dash disclosure category push |
| `c0a8acf` | fix(w19): history/watchlist/browse egress, safe ids |

**Shipped**

- `web/README.md` — CSRF section: non-HttpOnly `chime_csrf`, `X-CSRF-Token` on mutating `/api/v1/*`, session validated before CSRF (`401` vs `400 csrf_failed`), pointer to `scripts/factory/test_csrf_contract.md`.
- `/unwatch` copy: “Stopped watching …”; deactivated/orphan alerts called out as no longer firing.
- Dash new-disclosure alert form: optional category through `POST`/`GET /api/v1/alerts` + `createAlertRule` (bot-parity substring filter).
- Sanitize stock name/sector on watchlist, symbol detail, and market browse; harden alerts history (symbol/event_key controls+cap, SafeInteger ids) and alerts GET SafeInteger drop.

---

## Wave 20 — Loop status, START note, cancel/egress harden

**Theme:** Loop status + report rollup toward soft ~100; START browse note; cancel-id / category-read / dash egress harden.

| SHA | Commit |
|---|---|
| `6144b42` | docs(w20): loop status push |
| `58fe15d` | docs(w20): report push |
| `96ee2b0` | feat(w20): start browse note push |
| `a719e62` | fix(w20): cancel id, category read, dash egress |

**Shipped**

- [LOOP_STATUS.md](LOOP_STATUS.md) — waves-completed through w19; status push **w20**; horizon still soft ~100.
- `TIJORI_WAVE_REPORT.md` — close wave 18 inventory; append waves 19–20 toward soft ~100.
- `/start` copy: Browse dash mirrors watchlists; push stays on Telegram.
- `/cancel` digits-only ≤18 (Telegram 4096 + bigint-safe); sanitize poisoned disclosure categories on storage read; `DELETE /alerts/{id}` SafeInteger; `GET /me` fail-closed on non-finite ids; disclosures API strips C0 and caps title/category/company/external_id.

---

## Wave 21 — History filter, forms, logout UX

**Theme:** Harden alerts history/list/create/watchlist symbol filters to CSE `normalizeSymbol`; disclosure SafeInteger ids; hard-redirect logout so soft nav cannot bounce back to `/watchlist`.

| SHA | Commit |
|---|---|
| `e3a100c` | fix(w21): history filter push |
| `d1a068b` | fix(w21): logout UX |
| `5485120` | fix(w21): alerts filter, forms, disclosure ids |

**Shipped**

- `GET /api/v1/alerts/history` rejects non-CSE symbols via `normalizeSymbol` (`400 invalid_symbol`) — no bare trim/uppercase into SQL params.
- History page + alerts/watchlist forms normalize `symbol` the same way (hostile params never forwarded).
- Disclosures GET drops non-SafeInteger ids (no precision-loss row aliasing).
- Pin: `tests/test_wave21_medium_bugs.py`.
- Logout: clear session/CSRF with `expires` epoch; client drops readable CSRF cookie; `window.location.assign("/login")` (treat 401 as already-out).

---

## Wave 22 — Loop status + not-found Browse (+ late egress pin)

**Theme:** Next bounded docs/UX lane after wave 21 close (STOP on CLEAN×2; no empty farming). Loop status + symbol not-found Browse CTA; late sectors/alerts/health egress pin.

| SHA | Commit |
|---|---|
| `029ef6d` | docs(w22): status push |
| `7dadda8` | feat(w22): not-found browse link push |
| `16e93a4` | fix(w22): sectors/alerts/health egress harden |

**Shipped**

- [LOOP_STATUS.md](LOOP_STATUS.md) — waves-completed through w21; this status push **w22**; horizon still soft ~100.
- Symbol not-found: inline Browse link + primary Browse / secondary watchlist actions (poller-seen tickers only; NFA retained).
- Late pin: sanitize sectors name/symbol/index_* + SafeInteger `sector_id`; alert/browse/watchlist/symbol text egress; drop unknown alert types; allowlist `HEALTH_URL` circuits + cap timestamps — `tests/test_wave22_medium_bugs.py`.

---

## Wave 23 — Egress harden + report rollup

**Theme:** Sectors/health/browse egress + safe ids; docs lane append waves 21–23 toward soft ~100 (STOP on CLEAN×2; no empty farming).

| SHA | Commit |
|---|---|
| `92227ee` | fix(w23): sectors/health egress, symbol sanitize, safe ids |
| `19b4979` | docs(w23): report push |

**Shipped**

- Sanitize sectors name/symbol/index_* + SafeInteger `sector_id`; harden `HEALTH_URL` timestamps/circuits; sanitize symbols on alerts/browse/watchlist/detail + `mapRule` SafeInteger; drop unknown alert types; disclosures SafeInteger ids.
- Pin: `tests/test_wave23_medium_bugs.py`.
- `TIJORI_WAVE_REPORT.md` — close waves 19–20 inventory (late follow-ons); append waves 21–23 toward soft ~100.

---

## Wave 24 — Market empty tick hint (+ late history/login pin)

**Theme:** Point `/market` empty state at operator seed path (`make tick` / poller) so browse emptiness is actionable — not a dead “check back later.” Late history/watchlist/login SafeInteger pin.

| SHA | Commit |
|---|---|
| `de41fad` | docs/feat(w24): market empty tick hint push |
| `d8c2b0c` | fix(w24): history fail-closed, watchlist decode, login ids |

**Shipped**

- `/market` empty copy: run `make tick` (or leave poller/both running) to seed browse, then refresh; Health still the persistence path.
- `DASH_IA.md` + [TIJORI.md](../../runbooks/TIJORI.md) empty-board notes aligned; pin in `tests/test_web_route_regressions.py`.
- Late pin: history page JSON SafeInteger ids + sanitized symbol/event_key + allowlisted `delivery_status`; watchlist DELETE symbol decode; demo login digits-only `toSafePositiveInt` — `tests/test_wave24_medium_bugs.py`.

---

## Wave 25 — Session expiry + egress pin

**Theme:** Mid-use 401 / missing CSRF must hard-redirect to login with an expiry notice; pin toIso / history / market SafeInteger egress harden.

| SHA | Commit |
|---|---|
| `033f030` | fix(w25): session expiry push |
| `2a7f8f5` | fix(w25): toIso/history/market egress + SafeInteger harden |

**Shipped**

- Hard-redirect to `/login?expired=1` on mid-use 401 or missing CSRF (`client-fetch` + `session-redirect` + nav session); login expiry notice.
- Pin: fail-closed `toIso`, capped history OFFSET, honest `delivered_unmarked`, digits-only SafeInteger helpers, market browse sanitize, SafeInteger browse limits — `tests/test_wave25_session_expiry.py` + `tests/test_wave25_medium_bugs.py`.

---

## Wave 26 — Loop status push (+ late mapRule/fail-closed pin)

**Theme:** Honest loop-status advance after waves 24–25 (STOP on CLEAN×2; no empty farming). Late mapRule SafeInteger + alerts/watchlist fail-closed parse.

| SHA | Commit |
|---|---|
| `b1ddfa0` | docs(w26): loop status push |
| `f1bf191` | fix(w26): mapRule safe ids, alerts/watchlist fail-closed |

**Shipped**

- [LOOP_STATUS.md](LOOP_STATUS.md) — waves-completed through w25; this status push **w26**; horizon still soft ~100.
- Late pin: digits-only SafeInteger + `isAlertType` in `mapRule` (no `Number()` precision-loss alias); fail-closed alerts/watchlist page JSON parse — `tests/test_wave26_medium_bugs.py`.

---

## Wave 27 — Egress harden + report rollup

**Theme:** Fail-closed timestamp/history/SafeInteger egress; docs lane append waves 24–27 toward soft ~100 (STOP on CLEAN×2; no empty farming).

| SHA | Commit |
|---|---|
| `a3ba2fc` | fix(w27): toIso/delivery/safe-int egress harden |
| `31363ff` | docs(w27): report push |

**Shipped**

- Fail-closed `toIso` (no raw unparseable timestamp echo); honest `delivered_unmarked` history status + UI; capped history OFFSET; digits-only SafeInteger id/attempt helpers (`safe-int.ts`); `ensureUser` SafeInteger gate; market symbol sanitize; SafeInteger browse limits.
- Pin: `tests/test_wave27_medium_bugs.py`.
- `TIJORI_WAVE_REPORT.md` — close wave 22 late egress pin + wave 23 inventory SHAs; append waves 24–27 toward soft ~100.

---

## Wave 28 — Web tsc restore + loop status (+ late sector/browse/session pin)

**Theme:** Restore web `tsc --noEmit` after SafeInteger helpers; honest loop-status advance (STOP on CLEAN×2; no empty farming). Late sector ids / browse limits / toIso / session pin.

| SHA | Commit |
|---|---|
| `8c300c3` | fix(w28): restore web tsc — BigInt() and sanitize string guards |
| `8a249c0` | docs(w28): loop status push |
| `198b3bd` | fix(w28): sector ids, browse limits, toIso timestamps, session |
| `4d6ce9e` | fix(w28): align symbols list regression with digits-only limits |

**Shipped**

- `safe-int.ts`: prefer `BigInt(0)` over `0n` literal so TS target stays happy; market/sectors browse only pass strings into `sanitizeDisclosureText`.
- [LOOP_STATUS.md](LOOP_STATUS.md) — waves-completed through w27; this status push **w28**; horizon still soft ~100.
- Late pin: market `sector_id` via `toSafePositiveInt`; symbols/movers limits+offset digits-only; page timestamps fail-closed via `toIso`; session verify digits-only `user_id` + sid cap — `tests/test_wave28_medium_bugs.py` (+ symbols-list regression align).

---

## Wave 29 — Demo auth SafeInteger

**Theme:** Demo auth telegram_id / allowlist must not precision-lose oversized/float/sci-notation values into an allowlisted session mint.

| SHA | Commit |
|---|---|
| `0e596d4` | fix(w29): demo auth push |

**Shipped**

- `POST /api/v1/auth/demo` + `getDashAuthConfig` allowlist/default parse via digits-only `toSafePositiveInt` (no bare `Number(...)` / `isSafeInteger` gate alone).
- Pin: `tests/test_wave29_medium_bugs.py`.

---

## Wave 30 — Alert form a11y (+ late symbol/health/nav pin)

**Theme:** Disclosure category field stays announced when invalid; length-capped; busy submit announced. Late symbol/health/nav fail-closed + SafeInteger limits pin.

| SHA | Commit |
|---|---|
| `39169a8` | fix(w30): alert form a11y push |
| `843910c` | fix(w30): symbol/health/nav fail-closed + SafeInteger limits |

**Shipped**

- Alert create form: keep `alert_category_hint` in `aria-describedby` when invalid; `maxLength={DISCLOSURE_CATEGORY_MAX}`; submit `aria-busy` while pending.
- `DASH_IA.md` + `tests/test_web_route_regressions.py` pin the contract.
- Late pin: symbol detail / health page fail-closed JSON parse; NavSession `/me` digits-only; snapshots/disclosures/history limits + `DELETE /alerts/{id}` via SafeInteger helpers — `tests/test_wave30_medium_bugs.py`.

---

## Wave 31 — Report rollup (+ late session/market/health pin)

**Theme:** Docs lane append waves 28–31 toward soft ~100 (STOP on CLEAN×2; no empty farming). Close late w24/w26 inventory SHAs. Late session exp/sid / market numbers / health timeout / labels pin.

| SHA | Commit |
|---|---|
| `7aa0a93` | docs(w31): report push |
| `423e8dd` | fix(w31): session exp/sid, market numbers, health timeout, labels |

**Shipped**

- `TIJORI_WAVE_REPORT.md` — close wave 24 late history/login pin + wave 26 late mapRule pin; append waves 28–31 toward soft ~100.
- Late pin: session verify SafeInteger `exp` + hex-only `sid`; market `finiteOrNull` numbers-only (no string `Number()`); health proxy timeout via `toSafePositiveInt`; `alertTypeLabel` fail-closed — `tests/test_wave31_medium_bugs.py`.

---

## Wave 32 — Loop status + toFiniteNumber / health SafeInt

**Theme:** Honest loop-status advance after wave 31 close (STOP on CLEAN×2; no empty farming). Harden `toFiniteNumber`, health brief/circuit SafeInt, health timestamps, alert-form thresholds.

| SHA | Commit |
|---|---|
| `f6302b7` | docs(w32): loop status push |
| `f44a6a8` | fix(w32): toFiniteNumber, health SafeInt, alert thresholds |

**Shipped**

- [LOOP_STATUS.md](LOOP_STATUS.md) — waves-completed through w31; this status push **w32**; horizon still soft ~100.
- `toFiniteNumber` accepts finite number primitives or plain decimal strings only (reject empty/bool/array/sci-notation); health API `brief_queue`/circuits via `toNonNegativeSafeInt`; health page timestamps via `toIso`; alert create thresholds via `toFiniteNumber`.
- Pin: `tests/test_wave32_medium_bugs.py`.

---

## Wave 33 — Nav scenarios active (+ late session/CSRF/health body pin)

**Theme:** AppNav must highlight Scenarios on `/scenarios` and prefer longest-prefix matches so `/alerts/history` does not leave Alerts marked current. Late session/CSRF token length caps + HEALTH_URL body bound.

| SHA | Commit |
|---|---|
| `fd5e9a7` | fix(w33): nav scenarios active push |
| `00b00d5` | fix(w33): session/CSRF token caps + health body bound |

**Shipped**

- `resolveActiveNavHref` + `usePathname` (explicit `active` prop or path); longest-prefix wins; `/scenarios` page passes `active="/scenarios"`.
- Pin: `tests/test_wave33_nav_scenarios_active.py`.
- Late pin: `verifySessionToken` / `csrfTokensMatch` reject overlong forged tokens before HMAC/Buffer; HEALTH_URL proxy bounds body bytes before JSON.parse — `tests/test_wave33_medium_bugs.py`.

---

## Wave 34 — Loading NFA chrome (+ late history pagination / strict booleans pin)

**Theme:** Route `loading.tsx` shells keep NFA footer while content pulses — extend shared `ListPageSkeleton` beyond watchlist/alerts. Late history pagination UI, strict `=== true` delivery/armed flags, client-safe `toFiniteNumber`.

| SHA | Commit |
|---|---|
| `f4dff55` | fix(w34): loading nfa push |
| `09b27da` | fix(w34): history pagination, strict booleans, client finite |

**Shipped**

- Add `loading.tsx` for market / health / symbol detail / alert history using `ListPageSkeleton` (NFA footer via shared chrome).
- Pin: `tests/test_web_route_regressions.py` asserts every route `loading.tsx` keeps NFA footer.
- Late pin: fire-history Previous/Next with digits-only `offset`; history/alerts `message_sent`/`dead_lettered`/`active`/`armed` via `=== true` (not `Boolean(...)`); alert-type `<select>` gated by `isAlertType`; `toFiniteNumber` in client-safe `finite-number.ts` — `tests/test_wave34_medium_bugs.py`.

---

## Wave 35 — SSRF/session harden + report rollup

**Theme:** Harden cookie-bearing SSR fetch against host SSRF; SafeInteger session mint; fail-closed CSRF/symbol decode + formatTs. Docs lane append waves 32–35 toward soft ~100 (STOP on CLEAN×2; no empty farming). Close late w28/w30/w31 inventory SHAs.

| SHA | Commit |
|---|---|
| `29779aa` | fix(w35): SSRF host, session mint, CSRF/symbol decode, formatTs |
| `9f587b6` | docs(w35): report push |

**Shipped**

- `serverApiGet` rejects absolute/scheme-relative paths; host from `Host` only (no spoofable `X-Forwarded-Host`); `mintSessionToken` requires positive SafeInteger `userId`; CSRF cookie + `[symbol]` decode fail-closed (`normalizeSymbolParam`); `formatTs` rejects overlong/control timestamps.
- Pin: `tests/test_wave35_medium_bugs.py`.
- `TIJORI_WAVE_REPORT.md` — close wave 28 late sector/browse/session pin + wave 30 late symbol/health/nav pin + wave 31 late session/market/health pin; append waves 32–35 toward soft ~100.

---

## Wave 36 — Loop status + SSR loopback / HEALTH_URL / JSON body

**Theme:** Honest loop-status advance after wave 35 close (STOP on CLEAN×2; no empty farming). Harden cookie-bearing SSR to loopback/`DASH_INTERNAL_ORIGIN`; allowlist HEALTH_URL; stream-bound mutation JSON; share CSRF length cap; sanitize disclosure parse + alert `active=` + login error egress.

| SHA | Commit |
|---|---|
| `cee4c4b` | docs(w36): loop status push |
| `e69b1e5` | fix(w36): SSR loopback, HEALTH_URL SSRF, JSON body, CSRF/path |

**Shipped**

- [LOOP_STATUS.md](LOOP_STATUS.md) — waves-completed through w35; this status push **w36**; horizon still soft ~100.
- `serverApiGet` via `resolveInternalOrigin` (loopback only) + `isSafeServerApiPath` + `redirect: "error"`; HEALTH_URL `isAllowedHealthProxyUrl`; `readJsonBody` / `MAX_JSON_BODY_BYTES` on demo/alerts/watchlist; `apiMutate` rejects absolute paths; `MAX_CSRF_TOKEN_LENGTH` in client-safe `config.ts`.
- Pin: `tests/test_wave36_medium_bugs.py`.

---

## Wave 37 — apiMutate /api/v1 gate + NavSession toIso

**Theme:** Browser mutations must stay on `/api/v1/*` so `X-CSRF-Token` cannot ship to arbitrary same-origin routes; NavSession `/me` parse fails closed on `created_at` / CSRF length.

| SHA | Commit |
|---|---|
| `ff6e262` | fix(w37): apiMutate /api/v1 gate, nav toIso CSRF cap |

**Shipped**

- `isSafeClientApiPath` gates `apiMutate` to root-relative `/api/v1/*` only.
- NavSession `/me`: `toIso(created_at)` + `MAX_CSRF_TOKEN_LENGTH` cap (no raw timestamp echo).
- Pin: `tests/test_wave37_medium_bugs.py`.

---

## Wave 38 — SSR fetch timeout/body + alert threshold cap

**Theme:** Bound cookie-bearing `serverApiGet` so a stuck/hostile `/api` cannot hang or OOM SSR; reject absurd alert thresholds that used to persist useless rules.

| SHA | Commit |
|---|---|
| `4b3ceda` | fix(w38): SSR fetch timeout/body bound + alert threshold cap |

**Shipped**

- `SERVER_API_TIMEOUT_MS` + `SERVER_API_BODY_MAX_BYTES` + `AbortController` before page `res.json()` (fail closed → 502).
- Alert create (API + form) rejects thresholds above `MAX_ALERT_THRESHOLD`; `CancelAlertButton` re-validates `ruleId` via SafeInteger.
- Pin: `tests/test_wave38_medium_bugs.py`.

---

## Wave 39 — /me parse, cancel id, session TTL, threshold, SSR bound

**Theme:** Fail-closed NavSession `/me` body parse; gate cancel ids; require SafeInteger session TTL; keep threshold + SSR bounds pinned.

| SHA | Commit |
|---|---|
| `86c092c` | fix(w39): /me parse, cancel id, session TTL, threshold, SSR bound |

**Shipped**

- NavSession: `toIso` + CSRF cap + `MAX_ME_BODY_CHARS` before JSON.parse.
- `CancelAlertButton` gates `ruleId` via `toSafePositiveInt`; `mintSessionToken` requires positive SafeInteger `ttlSeconds`.
- Alert threshold cap + `serverApiGet` timeout/body bound retained.
- Pin: `tests/test_wave39_medium_bugs.py`.

---

## Wave 40 — SSR origin pin + report rollup

**Theme:** Pin SSR origin / HEALTH_URL SSRF / JSON body / CSRF path contracts (overlap with w36 harden). Docs lane append waves 36–40 toward soft ~100 (STOP on CLEAN×2; no empty farming). Close late w33 session/CSRF/health body and w34 history/strict-boolean inventory SHAs.

| SHA | Commit |
|---|---|
| `27639fa` | fix(w40): SSR origin, HEALTH_URL SSRF, JSON body, CSRF path |
| `082a362` | docs(w40): report push |

**Shipped**

- Pin suite for loopback SSR origin, HEALTH_URL allowlist, `apiMutate` absolute-path reject, streamed `readJsonBody`, client-safe CSRF cap, disclosure href allowlist, login error sanitize — `tests/test_wave40_medium_bugs.py` (code landed in w36; this wave locks the contract).
- `TIJORI_WAVE_REPORT.md` — close wave 33 late session/CSRF/health body pin + wave 34 late history pagination / strict booleans pin; append waves 36–40 toward soft ~100.

---

## Wave 41 — Loop status + CSRF cookie / mapRule / SSR CL

**Theme:** Honest loop-status advance after wave 40 close (STOP on CLEAN×2; no empty farming). Cap CSRF cookie length before compare; cap mapRule thresholds; early-reject oversized SSR `Content-Length` before body allocate.

| SHA | Commit |
|---|---|
| `f0c8fca` | docs(w41): loop status push |
| `9f842ac` | fix(w41): CSRF cookie cap, mapRule threshold, SSR CL early-reject |

**Shipped**

- [LOOP_STATUS.md](LOOP_STATUS.md) — waves-completed through w40; this status push **w41**; horizon still soft ~100.
- `readCsrfCookie` rejects overlong values via `MAX_CSRF_TOKEN_LENGTH`; `mapRule` caps thresholds at `MAX_ALERT_THRESHOLD`; `serverApiGet` early-rejects oversized claimed `Content-Length`.
- Pin: `tests/test_wave41_medium_bugs.py`.

---

## Wave 42 — jsonError egress + SSR Cookie/CT pin

**Theme:** Cap `jsonError` code/message so misbuilt callers cannot balloon API JSON; lock SSR Cookie header cap, forced `application/json` Content-Type, and Content-Length early-reject.

| SHA | Commit |
|---|---|
| `81023ac` | fix(w42): jsonError egress caps + SSR Cookie/CT pin |

**Shipped**

- `jsonError` strips controls + length-caps `code`/`message` (`MAX_JSON_ERROR_*`).
- `serverApiGet`: `SERVER_API_COOKIE_MAX_CHARS` gate; force JSON Content-Type (never reflect upstream); CL early-reject retained.
- Pin: `tests/test_wave42_medium_bugs.py`.

---

## Wave 43 — Cookie Secure + SameSite helpers

**Theme:** Session/CSRF set+clear must share Secure (prod) + SameSite=Lax + Path=/ so production Secure cookies actually drop on logout / browser CSRF clear.

| SHA | Commit |
|---|---|
| `c45d877` | fix(w43): cookie flags push |

**Shipped**

- `cookieSecure()` + `COOKIE_SAME_SITE` helpers; session/CSRF set uses them; logout clear via `clearAuthCookieOptions`; browser CSRF clear includes SameSite (+ Secure in prod).
- Pin: `tests/test_wave43_cookie_flags.py`.

---

## Wave 44 — mapRule threshold cap

**Theme:** Poisoned / out-of-band `alert_rules` rows must not egress absurd thresholds via create/idempotent `mapRule` JSON — parity with GET `/api/v1/alerts`. Keep SYMBOL_RE fail-closed pin.

| SHA | Commit |
|---|---|
| `ded4c35` | fix(w44): mapRule threshold cap (parity GET /alerts) |

**Shipped**

- `mapRule` caps thresholds at `MAX_ALERT_THRESHOLD` via `toFiniteNumber`; symbol egress stays `normalizeSymbol` (no sanitize `"?"`).
- Pin: `tests/test_wave44_medium_bugs.py`.

---

## Wave 45 — Client mutate bound + SYMBOL_RE egress + report rollup

**Theme:** Bound browser `apiMutate`/login/NavSession like SSR; gate Unwatch; sanitize alert category; fail-closed SYMBOL_RE on alerts/watchlist/history pages + GET APIs (drop sanitize `"?"`). Docs lane append waves 41–45 toward soft ~100 (STOP on CLEAN×2; no empty farming).

| SHA | Commit |
|---|---|
| `3e59993` | fix(w45): client mutate bound, unwatch gate, symbol egress |
| `2817789` | fix(w45): symbol egress + category sanitize close |
| `3a0308e` | fix(w45): residual SYMBOL_RE egress + pin realign |
| `aefae3e` | docs(w45): report push |

**Shipped**

- `CLIENT_API_TIMEOUT_MS` + `CLIENT_API_BODY_MAX_CHARS` on `apiMutate`/login (502 oversize); NavSession `/me` aborts; `UnwatchButton` via `normalizeSymbol`; alert form `sanitizeDisclosureCategory`.
- Pages + GET APIs fail-closed on `normalizeSymbol` / threshold caps; residual history/browse/mapRule/symbol-detail SYMBOL_RE (realign w22/w23/w26 pins).
- Pin: `tests/test_wave45_medium_bugs.py`.
- `TIJORI_WAVE_REPORT.md` — append waves 41–45 toward soft ~100.

---

## Wave 46 — Loop status + SYMBOL_RE page egress / health CL

**Theme:** Honest loop-status advance after wave 45 close (STOP on CLEAN×2; no empty farming). Fail-closed `normalizeSymbol` on market/health/symbol-detail parsers; health proxy watched-missing via SYMBOL_RE; early-reject oversize Content-Length before body allocate.

| SHA | Commit |
|---|---|
| `28b4bd6` | docs(w46): loop status push |
| `737e67a` | fix(w46): SYMBOL_RE page egress + health watched/CL |

**Shipped**

- [LOOP_STATUS.md](LOOP_STATUS.md) — waves-completed through w45; this status push **w46**; horizon still soft ~100.
- Market / health / symbol-detail page parsers drop sanitize length-cap fallback; use fail-closed `normalizeSymbol`.
- Health proxy `sanitizeWatchedMissing` via SYMBOL_RE; early-reject oversize `Content-Length` before body allocate (parity `serverApiGet`).
- Pin: `tests/test_wave46_medium_bugs.py` (+ wave25 / health unit realign).

---

## Wave 47 — Client Content-Length early-reject

**Theme:** Browser mutate/login/NavSession must early-reject oversize claimed Content-Length before body allocate (parity with SSR `serverApiGet` / HEALTH_URL proxy).

| SHA | Commit |
|---|---|
| `bdf1f4e` | fix(w47): client Content-Length early-reject |

**Shipped**

- `apiMutate`, demo login, and NavSession `/me` early-reject oversize claimed `Content-Length` before body allocate; body-length gate retained after the header check.
- Pin: `tests/test_wave47_medium_bugs.py`.

---

## Wave 48 — Alerts empty CTA + sectors SYMBOL_RE / SSR statusText

**Theme:** Align empty-alerts CTAs with Browse discovery; normalize sector board symbols via SYMBOL_RE; stop `serverApiGet` reflecting upstream `statusText`; client CL early-reject (overlap with w47).

| SHA | Commit |
|---|---|
| `95744c1` | feat(w48): alerts empty CTA push |
| `4bb7d08` | fix(w48): sectors SYMBOL_RE, SSR statusText, client CL |
| `7bc32e5` | fix(w48): realign wave22/23 sector SYMBOL_RE pins |

**Shipped**

- `/alerts` empty: dual Create/Browse actions, focusable inline Browse link, filter-empty create affordance (watchlist-parity discovery).
- Sectors route `normalizeSymbol` (drop sanitize length-cap junk); `serverApiGet` stops reflecting upstream `statusText`.
- Client CL early-reject on mutate/login/NavSession retained (parity SSR + HEALTH_URL).
- Pin: `tests/test_wave48_medium_bugs.py` (+ wave22/23 sectors realign).

---

## Wave 49 — Sparkline ts sanitize + circuit/sectors pin

**Theme:** Fail-closed sparkline timestamps so hostile snapshot JSON cannot park overlong / non-string `ts` in series; pin health CIRCUIT_STATES allowlist + sectors normalizeSymbol after w48.

| SHA | Commit |
|---|---|
| `ff9cec1` | fix(w49): sparkline ts sanitize + circuit/sectors pin |
| `8e94287` | fix(w49): escape sparkline CTRL_RE (no embedded NUL) |

**Shipped**

- Sparkline timestamps: string-only, strip controls, cap via `MAX_ISO_INPUT_LENGTH`.
- Health page `CIRCUIT_STATES` allowlist pin; wave22/23 sectors `normalizeSymbol` realign after w48.
- Follow-up: rewrite `sparkline.ts` CTRL_RE escape so source stays valid UTF-8 (no embedded NUL).
- Pin: `tests/test_wave49_medium_bugs.py` (+ sparkline unit).

---

## Wave 50 — Toast/inline caps + format/sparkline bound + report rollup

**Theme:** Sanitize+cap toast and InlineError copy (parity `apiErrorMessage`); fail-closed `formatNumber` fraction digits; cap sparkline series at `MAX_SPARKLINE_POINTS`. Docs lane append waves 46–50 toward soft ~100 (STOP on CLEAN×2; no empty farming).

| SHA | Commit |
|---|---|
| `2e0cfe3` | fix(w50): toast/inline caps, format digits, sparkline bound |
| `a9724f6` | docs(w50): report push |

**Shipped**

- Toast + `InlineError`: sanitize+length-cap so misbuilt callers cannot balloon live/alert regions.
- `formatNumber` rejects non-finite / out-of-range fraction digits (`RangeError` footgun).
- Sparkline series capped at `MAX_SPARKLINE_POINTS` (snapshots API max 200).
- Pin: `tests/test_wave50_medium_bugs.py`.
- `TIJORI_WAVE_REPORT.md` — append waves 46–50 toward soft ~100.

---

## Wave 51 — Loop status + fail-closed maxBytes

**Theme:** Honest loop-status advance after wave 50 close; fail-closed `maxBytes` for stream/request body readers (`Math.max(1, NaN)` used to disable the length gate).

| SHA | Commit |
|---|---|
| `5d47022` | docs(w51): loop status push |
| `177abb3` | fix(w51): fail-closed maxBytes for bounded body readers |

**Shipped**

- [LOOP_STATUS.md](LOOP_STATUS.md) — waves-completed through w50; status push **w51**; horizon still soft ~100; commits-ahead-of-main refreshed.
- `readBoundedResponseText` / `readJsonBody` resolve caps via `Number.isInteger` + `>=1` fail-closed (parity sanitize `maxLen`) so hostile/misbuilt `maxBytes` cannot allocate unbounded buffers.
- Pin: `tests/test_wave51_medium_bugs.py`.

---

## Wave 52 — Alerts/watchlist LIMIT + toast tone/timers

**Theme:** Bound GET `/alerts` and `/watchlist` with `MAX_*` SQL LIMITs (unbounded SELECT ballooned JSON/SSR); allowlist toast tones and clear overflow dismiss timers; cap demo Telegram allowlist parse.

| SHA | Commit |
|---|---|
| `6a068ed` | fix(w52): alerts/watchlist LIMIT, toast tone/timers, allowlist |
| `e5e1992` | fix(w52): realign wave50 toast pin after safeTone |

**Shipped**

- `GET /api/v1/alerts` / `/watchlist` `LIMIT` via `MAX_ALERT_RULES` / `MAX_WATCHLIST_ITEMS`; matching page parsers break at 500.
- Toast `push` allowlists tones via `safeTone` / `normalizeToastTone` and clears dismiss timers on overflow (`MAX_VISIBLE_TOASTS`).
- Demo allowlist parse capped at `MAX_DEMO_ALLOWLIST`.
- Realign wave50 toast pin for `safeTone` shape.
- Pin: `tests/test_wave52_medium_bugs.py`.

---

## Wave 53 — Stream-bound response bodies

**Theme:** Content-Length early-reject alone still let `res.text()` allocate a full hostile body when CL was missing or understated — stream-bound reads cancel past the byte cap.

| SHA | Commit |
|---|---|
| `24f9ca5` | fix(w53): stream-bound response bodies (CL understate bypass) |

**Shipped**

- `readBoundedResponseText` (stream + cancel past cap) for `apiMutate`, `serverApiGet`, HEALTH_URL proxy, demo login, and NavSession `/me`.
- Realign wave33–48 body-bound pins to the shared helper.
- Pin: `tests/test_wave53_medium_bugs.py`.

---

## Wave 54 — Sanitize maxLen + empty/skeleton/page caps

**Theme:** Fail-closed `sanitizeDisclosureText` maxLen (NaN disabled the length gate); cap EmptyState titles; typeof-guard InlineError; clamp ListPageSkeleton rows; cap symbol/history/market page parsers so hostile SSR JSON cannot allocate unbounded React lists.

| SHA | Commit |
|---|---|
| `285bbd1` | fix(w54): sanitize maxLen, empty title, skeleton + page list caps |

**Shipped**

- `sanitizeDisclosureText` rejects non-integer / non-finite / oversized `maxLen` (no more `length > NaN` uncapped path).
- EmptyState title sanitize+cap (parity toast / inline-error); InlineError typeof-guard before `.replace`.
- `ListPageSkeleton` clamps `rows` (`Array.from({ length: Inf })` / huge N).
- Symbol / history / market page JSON parsers break at API-parity caps.
- Pin: `tests/test_wave54_medium_bugs.py`.

---

## Wave 55 — Format abs-cap + alertTypeLabel + report rollup

**Theme:** Fail-closed `formatNumber`/`formatPct` on absurd finite magnitudes (`MAX_FORMAT_ABS_VALUE`); typeof-guard `alertTypeLabel`. Docs lane append waves 51–55 toward soft ~100 (STOP on CLEAN×2; no empty farming).

| SHA | Commit |
|---|---|
| `0723337` | fix(w55): sanitize maxLen, empty title, inline typeof |
| `5d1da00` | fix(w55): format abs-cap + alertTypeLabel typeof |
| `e90d1d3` | docs(w55): report push |

**Shipped**

- Early pin for sanitize/EmptyState/InlineError (superseded pin suite; implementation retained in w54).
- `formatNumber` / `formatPct` reject absurd finite magnitudes via `MAX_FORMAT_ABS_VALUE` (hostile `1e308` no longer balloons locale/`toFixed` labels).
- `alertTypeLabel` typeof-guards non-string inputs (no hostile fallthrough echo).
- Pin: `tests/test_wave55_medium_bugs.py`.
- `TIJORI_WAVE_REPORT.md` — append waves 51–55 toward soft ~100.

---

## Wave 56 — Loop status + fail-closed brief/PDF caps

**Theme:** Honest loop-status advance after wave 55 close; fail-closed positive-int caps for brief/PDF paths (`max(1, int(x))` raised on None/NaN/inf mid Telegram format / CDN fetch / prompt build).

| SHA | Commit |
|---|---|
| `5f6be2e` | docs(w56): loop status push |
| `7e4fb1a` | fix(w56): fail-closed brief/PDF max caps + brief typeof |

**Shipped**

- [LOOP_STATUS.md](LOOP_STATUS.md) — waves-completed through w55; status push **w56**; horizon still soft ~100; commits-ahead-of-main refreshed.
- `resolve_positive_int_cap` wired into `sanitize_brief_body`, title truncate, `build_brief_prompt`, provider sanitize, and `fetch_cdn_pdf`.
- Dash `sanitizeBriefText` typeof-guards non-string brief status/body.
- Pin: `tests/test_wave56_medium_bugs.py`.

---

## Wave 57 — API path / nav / CSRF typeof + length caps

**Theme:** Typeof-guard and length-cap mutation/SSR API paths, nav active resolution, CSRF compare/read, and internal-host helpers so non-strings / multi-MB forged inputs cannot throw or burn CPU before gates.

| SHA | Commit |
|---|---|
| `f7d8d47` | fix(w59): realign toIso/age pins after range-gated helper |

**Shipped**

- `isSafeClientApiPath` / `isSafeServerApiPath`: unknown + `MAX_*_API_PATH_LENGTH`.
- `resolveActiveNavHref`: typeof + `MAX_NAV_PATH_LENGTH`.
- `csrfTokensMatch` / `readCsrfCookie`: typeof-guard (no `Buffer.from(number)` alloc footgun).
- `isSafeInternalHost` / `hostnameOnly`: typeof-guard.
- Pin: `tests/test_wave57_medium_bugs.py` (landed under a w59-labeled SHA).

---

## Wave 58 — History pagination a11y + threshold/sanitize harden

**Theme:** Label fire-history Previous/Next for a11y; abs-cap alert thresholds (upper-bound-only let `-1e308` through); typeof-guard history/toast/jsonError/filing URL/brief status/LIKE sanitizers; sanitize apiErrorMessage fallbacks + EmptyState descriptions.

| SHA | Commit |
|---|---|
| `9f723e0` | fix(w58): history pagination a11y |
| `60f608b` | fix(w58): abs-cap thresholds + typeof sanitize guards |

**Shipped**

- History pagination: page aria-labels, `rel=prev/next`, `aria-disabled` on unavailable sides (DASH_IA + wave34 pin).
- `cappedAlertThreshold` via `Math.abs` vs `MAX_ALERT_THRESHOLD` for mapRule / GET `/alerts` / alerts page.
- Typeof-guards across history/toast/jsonError/filing URL/brief status/LIKE escape; EmptyState description sanitize+cap.
- Pin: `tests/test_wave58_medium_bugs.py` (+ wave41/44/45 realign).

---

## Wave 59 — Sparkline abs-cap + toIso range + decode/age

**Theme:** Reject absurd finite sparkline prices; fail-closed `toIso` on out-of-range Date/number + overlong ISO egress; typeof-guard `safeDecodeURIComponent`; cap health `formatAge` day labels.

| SHA | Commit |
|---|---|
| `a3808b5` | fix(w59): sparkline abs-cap, toIso range, decode/age guards |
| `11846c2` | fix(w59): realign wave25/59 pins for safeToIsoString + 9_999 |

**Shipped**

- Sparkline prices abs-capped via `MAX_SPARKLINE_ABS_PRICE` (hostile `1e308` no longer balloons SVG polyline coords).
- `safeToIsoString` / `MAX_DATE_MS` range gate + ISO length egress cap.
- `safeDecodeURIComponent` typeof-guard; health age labels capped at `MAX_HEALTH_AGE_DAYS` (`9_999`).
- Pin: `tests/test_wave59_medium_bugs.py` (+ wave25 toIso realign).

---

## Wave 60 — toFiniteNumber abs-cap + API path typeof + report rollup

**Theme:** Abs-cap `toFiniteNumber` so hostile finite extremes cannot reach market/watchlist/sectors/page a11y paths after display/sparkline fail-closed; reinforce API path typeof. Docs lane append waves 56–60 toward soft ~100 (STOP on CLEAN×2; no empty farming).

| SHA | Commit |
|---|---|
| `d6e4059` | fix(w60): toFiniteNumber abs-cap + API path typeof |
| `f1b18b5` | fix(w60): narrow resolve_positive_int_cap for mypy |
| `ec1b87a` | docs(w60): report push |
| `4dacd09` | fix(w60): cover resolve_positive_int_cap bool branch |

**Shipped**

- `toFiniteNumber` rejects via `MAX_FINITE_ABS_VALUE`; market/symbol page parsers route through it (drop finite-only `finiteOrNull`).
- `isSafeClientApiPath` / `isSafeServerApiPath` typeof pin realign (parity w57).
- Pin: `tests/test_wave60_medium_bugs.py` (+ wave25/31/59/movers realign).
- `TIJORI_WAVE_REPORT.md` — append waves 56–60 toward soft ~100.
- Late: mypy-narrow + bool-branch cover for `resolve_positive_int_cap`.

---

## Wave 61 — Loop status + body abs-cap / formatTs / session typeof

**Theme:** Honest loop-status advance after wave 60 close; abs-cap bounded body readers; fail-closed `formatTs` date range; typeof-guard session verify + disclosure category (no `String()` coerce).

| SHA | Commit |
|---|---|
| `735c3b30` | docs(w61): loop status push |
| `372656ae` | fix(w61): body abs-cap, formatTs range, session/category typeof |
| `7249b697` | fix(w61): realign wave43 cookieSecure typeof pin |

**Shipped**

- [LOOP_STATUS.md](LOOP_STATUS.md) — waves-completed through w60; status push **w61**; horizon still soft ~100.
- `resolveBoundedBodyCap` / `MAX_BOUNDED_BODY_BYTES` abs-cap for `readBoundedResponseText` / `readJsonBody`.
- `formatTs` fail-closes via `MAX_DATE_MS` (parity `safeToIsoString`).
- `verifySessionToken` typeof-guards token/secret; category sanitize / `_row_to_rule` stop `String()`-coercing non-strings.
- Pin: `tests/test_wave61_medium_bugs.py` (+ wave33/35/43/51 realign).

---

## Wave 62 — Bot threshold abs-cap + HEALTH_URL typeof

**Theme:** Cap Telegram `/alert` thresholds at shared `MAX_ALERT_THRESHOLD` (parity dash POST); typeof-guard health-proxy URL SSRF gate.

| SHA | Commit |
|---|---|
| `dea4e4ce` | fix(w62): bot threshold abs-cap + HEALTH_URL typeof |

**Shipped**

- `_parse_threshold_token` rejects magnitudes above `MAX_ALERT_THRESHOLD` (hostile `1e308` / `1e20` no longer persist useless rules).
- `isAllowedHealthProxyUrl` typeof-guards non-strings (no `.trim` throw mid SSRF gate).
- Pin: `tests/test_wave62_medium_bugs.py`.

---

## Wave 63 — Sparkline/stale ts range + typeof + attempt cap

**Theme:** Fail-closed sparkline/stale timestamps via `MAX_DATE_MS`; typeof-guard loopback/scenarios; abs-cap fire-history attempt display.

| SHA | Commit |
|---|---|
| `dce2e839` | fix(w63): sparkline/stale ts range + typeof + attempt cap |
| `432b8a6d` | fix(w63): keep opaque sparkline ts labels on range gate |

**Shipped**

- `sanitizeSparklineTs` + symbol `isStaleTs` range-gate via `MAX_DATE_MS`; opaque labels retained on reject.
- `isLoopbackHost` / `scenariosEnabled` typeof-guards.
- History `attempt_count` abs-capped at `1_000_000` (API + page display).
- Pin: `tests/test_wave63_medium_bugs.py`.

---

## Wave 64 — Health age range + dash auth env + alert code typeof

**Theme:** Health `timestampAge` typeof + date-range gate; dash auth / cookieSecure typeof-guard env; alert form typeof-guards API `error.code`.

| SHA | Commit |
|---|---|
| `4d807eed` | fix(w64): health age range, dash auth env, alert code typeof |

**Shipped**

- Health `timestampAge` typeof-guards + `MAX_DATE_MS` range (parity formatTs / isStaleTs).
- `getDashAuthConfig` / `cookieSecure` typeof-guard env values (no `.trim` throw on mocks).
- Alert create form typeof-guards `error.code` (no `[object Object]` field mis-route).
- Pin: `tests/test_wave64_medium_bugs.py`.

---

## Wave 65 — Filing URL isinstance + notify symbol + mint secret + report rollup

**Theme:** isinstance-guard filing/CDN PDF URLs + notify/format symbol; typeof-guard session mint secret. Docs lane append waves 61–65 toward soft ~100 (STOP on CLEAN×2; no empty farming).

| SHA | Commit |
|---|---|
| `04297d24` | fix(w65): filing URL isinstance + notify symbol + mint secret |
| `760a27dd` | docs(w65): report push |

**Shipped**

- `allowed_cdn_pdf_url` / `allowed_filing_url` / `resolve_pdf_url` isinstance-guard non-strings.
- Dead-letter / brief-followup formatters isinstance-guard `symbol` (no `re.sub` raise).
- `mintSessionToken` typeof-guards secret (fail closed before HMAC).
- Pin: `tests/test_wave65_medium_bugs.py`.
- `TIJORI_WAVE_REPORT.md` — append waves 61–65 toward soft ~100.

---

## Wave 66 — Loop status + briefs/scenarios/bot env isinstance

**Theme:** Honest loop-status advance after wave 65 close; pin BriefSettings/ScenarioSettings getenv isinstance, cmd-rate + alert kind/threshold guards, `/myalerts`/`/mywatchlist` symbol egress, delivery-ok ledger getenv.

| SHA | Commit |
|---|---|
| `751402ff` | docs(w66): loop status push |
| `3f5e24f3` | fix(w66): pin briefs/scenarios/bot env + list isinstance |

**Shipped**

- [LOOP_STATUS.md](LOOP_STATUS.md) — waves-completed through w65; status push **w66**; horizon still soft ~100.
- Pin locks BriefSettings / ScenarioSettings getenv isinstance before `.strip`.
- `_env_cmd_rate_per_minute` / alert kind / threshold isinstance; list-command symbol egress guards.
- Poller delivery-ok ledger getenv isinstance False branch.
- Pin: `tests/test_wave66_medium_bugs.py`.

---

## Wave 67 — Bot/poller/storage/brief env isinstance

**Theme:** Fail-closed getenv / brief claim-lookup / list-command symbol isinstance (parity Settings). Pin landed alongside parallel w70 lane (`f6fb5402`); late follow-on hardens provider factory / bulk symbols / PDF extract.

| SHA | Commit |
|---|---|
| `f6fb5402` | fix(w70): pin config/poller/guardrails browse session *(adds `test_wave67_medium_bugs.py` + bot/briefs/poller/scenarios/storage isinstance)* |
| `c15639df` | fix(w67): brief provider factory + bulk symbols + PDF extract |

**Shipped**

- `_env_cmd_rate_per_minute` / delivery-ok ledger getenv isinstance before `.strip`.
- `/myalerts` / `/mywatchlist` isinstance-guard symbols before `re.sub`.
- Storage brief claim/lookup isinstance-guards `external_id` / `symbol` / `brief` / `message_text`.
- `BriefSettings.from_env` / `ScenarioSettings.from_env` isinstance-guard env values.
- `make_brief_provider` isinstance-guards `BriefSettings.provider`; bulk disclosure watchlist/name pairs + PDF extract pieces isinstance-guard before `.strip`.
- Pin: `tests/test_wave67_medium_bugs.py`.

---

## Wave 68 — Brief prompt / resolve / alert parse / storage symbols

**Theme:** isinstance-guard brief prompt fields, announcement symbol resolve, alert kind parse, and storage symbol mutators/lookups.

| SHA | Commit |
|---|---|
| `433e59c9` | fix(w68): brief/resolve/alert/storage isinstance guards |

**Shipped**

- `build_brief_prompt` isinstance-guards `symbol` / `title` / `extracted_text`.
- `resolve_announcement_symbol` isinstance-guards allowed-set members + row symbol/company.
- `parse_alert_args` typeof-guards kind; threshold parse fail-closed.
- Storage upsert/watch/unwatch/snapshot/create/deactivate isinstance-guard symbol (empty-after-strip fail-closed).
- Pin: `tests/test_wave68_medium_bugs.py`.

---

## Wave 69 — isinstance/typeof fail-closed + price/log + env typeof

**Theme:** Broad fail-closed isinstance on alert/brief/name/host paths; `format_price_lkr` non-numeric reject; logging level guard; web env typeof before `.trim`; late pin realigns.

| SHA | Commit |
|---|---|
| `2a9852cd` | fix(w69): isinstance/typeof fail-closed + price/log guards |
| `6435db8c` | fix(w69): realign wave25 session expiry pin |
| `3af22297` | fix(w69): restore wave70 medium pin for 100% cov |

**Shipped**

- `format_price_lkr` rejects non-numeric/bool before `math.isfinite`.
- `configure_logging` isinstance-guards level; alert/brief/name/host/cancel isinstance-guards.
- Settings/poller/guardrails getenv isinstance; browse `opts.q` + page-session cookie typeof.
- `resolveInternalOrigin` / `healthProxyTimeoutMs` / HEALTH_URL / `getPool` typeof-guard env.
- Pin: `tests/test_wave69_medium_bugs.py` (+ wave25 realign; restore wave70 pin for cov).

---

## Wave 70 — Config/poller/guardrails browse session + disclosure + report

**Theme:** Pin Settings getenv / poller symbol+hhmm / scenario text / browse q / page-session cookie fail-closed guards; disclosure category / DoA / brief sanitize isinstance. Docs lane append waves 66–70 toward soft ~100 (STOP on CLEAN×2; no empty farming).

| SHA | Commit |
|---|---|
| `fde0a2b4` | fix(w70): config/poller/guardrails browse session typeof |
| `f6fb5402` | fix(w70): pin config/poller/guardrails browse session |
| `3af22297` | fix(w69): restore wave70 medium pin for 100% cov |
| `3b032624` | fix(w70): disclosure/DoA/sanitize isinstance fail-closed |
| `688f8a39` | docs(w70): report push |

**Shipped**

- Settings `_require` / `_float` / `_int` / string knobs isinstance-guard getenv mocks.
- Poller `_symbol_from_alert_message` / `parse_hhmm` isinstance-guard non-strings.
- Scenario guardrail text isinstance; `queryMarketBrowse` typeof-guards `opts.q`.
- `requirePageSession` typeof-guards cookie before verify / expired redirect.
- Disclosure eval treats non-string `rule.category` as unrestricted; DoA / brief sanitize isinstance-guard before `.strip` / `.replace`.
- Pin: `tests/test_wave70_medium_bugs.py`.
- `TIJORI_WAVE_REPORT.md` — append waves 66–70 toward soft ~100.

---

## Wave 71 — Loop status + wave67 pin import hygiene (+ late follow-up soft-accept)

**Theme:** Honest loop-status advance after wave 70 close; move `pytest` import to top in wave67 pin (ruff E402). Late: reject `str()` soft-accept on brief follow-up / worker paths.

| SHA | Commit |
|---|---|
| `c226f055` | fix(w71): move pytest import to top in wave67 pin |
| `7f97b700` | docs(w71): loop status push |
| `e3abfffc` | fix(w71): reject str() soft-accept on brief follow-up paths |

**Shipped**

- [LOOP_STATUS.md](LOOP_STATUS.md) — waves-completed through w70; status push **w71**; horizon still soft ~100.
- `tests/test_wave67_medium_bugs.py` — `pytest` import at module top (no mid-file import).
- Late: `format_brief_followup` isinstance-guards url; brief worker title/symbol/external_id/url paths isinstance-guard (no `str()` soft-accept) — pin `tests/test_wave71_medium_bugs.py`.

---

## Wave 72 — Cancel/brief/CSE/persist isinstance/typeof pin

**Theme:** Pin fail-closed cancel args, brief follow-ups/delivery tokens, brief env ints, CSE symbols/base_url, persist/previous_state, and dash searchParams/Content-Length typeof guards.

| SHA | Commit |
|---|---|
| `5101ea0d` | fix(w72): isinstance/typeof fail-closed cancel/brief/CSE/persist |

**Shipped**

- Pin locks cancel/brief/CSE/persist + dash searchParams typeof fail-closed paths (implementation shared with parallel w73 lane).
- Pin: `tests/test_wave72_medium_bugs.py`.

---

## Wave 73 — Layout viewport + state/CSE/web fail-closed

**Theme:** Root layout `lang=en` + explicit viewport export; broad isinstance/typeof fail-closed on previous_state / persist / CSE normalize+fetch / base_url, delivery-ok encode, brief env parsers, cancel args, and dash searchParams/Content-Length/active.

| SHA | Commit |
|---|---|
| `d50e7b0d` | fix(w73): layout meta |
| `68e9d7d1` | fix(w73): isinstance/typeof fail-closed for state/CSE/web |

**Shipped**

- `web/src/app/layout.tsx` — `Viewport` export (`width=device-width`, `initialScale=1`); `lang="en"` retained.
- Non-string symbols fail closed in `get_previous_state` / persist / CSE normalize+fetch / `CSEClient` base_url.
- Delivery-ok message encode, brief `_env_int`/`_env_float`, cancel args isinstance-guarded.
- Dash searchParams / Content-Length / active typeof-guarded before `.trim`.
- Pin: `tests/test_wave73_medium_bugs.py`.

---

## Wave 74 — rule.type getattr + stock-name/board persist pin

**Theme:** Poller `getattr(type, "value")` so non-enum rule/event types cannot abort the tick; pin `list_stock_names` isinstance + board persist/normalize/CSE fail-closed cov lock.

| SHA | Commit |
|---|---|
| `6f4bf63c` | fix(w74): isinstance/typeof fail-closed + rule.type getattr |

**Shipped**

- Poller tick / disclosure filter / ready-filing brief use `getattr(..., "value", ...)` for non-enum types.
- `list_stock_names` isinstance-guards PG symbol/name (no `str()` soft-accept).
- Board persist/normalize / CSE fetch / previous_state / base_url fail-closed cov lock.
- Pin: `tests/test_wave74_medium_bugs.py`.

---

## Wave 75 — Report rollup (71–75) (+ late rate/row-mapper harden)

**Theme:** Ruff-clean wave72 pin; docs lane append waves 71–75 toward soft ~100 (STOP on CLEAN×2; no empty farming). Late: fail-closed rate/row mappers / brief egress / ledger URL.

| SHA | Commit |
|---|---|
| `b5da998a` | fix(w75): ruff wave72 pin SIM117 |
| `dafe0afc` | docs(w75): report push *(truncated mid-write; superseded)* |
| `e5c6b934` | docs(w75): restore full wave report body |
| `ae9e7780` | docs(w75): pin report SHAs after restore |
| `75a54fd1` | fix(w75): fail-closed rate/row mappers/brief egress/ledger URL |

**Shipped**

- `tests/test_wave72_medium_bugs.py` — combine nested `with` patches (ruff SIM117).
- `TIJORI_WAVE_REPORT.md` — append waves 71–75 toward soft ~100; header Waves 1–75 (full body restored after mid-write truncate); SHA table pinned after restore.
- Late: `_cmd_rate_limit` isinstance-guards bot_data rates; brief lookup URL isinstance; delivery-ok ledger isinstance-guards `database_url`; `get_latest_ready_brief` drops `str()` soft-accept; `_row_to_rule`/`_row_to_snapshot` fail closed on poisoned type/symbol/price — pin `tests/test_wave75_medium_bugs.py`.

---


## Wave 76 — Loop status + soft-accept pin

**Theme:** Honest loop-status advance after wave 75 close; wrap long lines in wave75 pin; pin fail-closed soft-accept on cmd_brief / claim / unsent / category / row mappers (implementation shared with parallel w79 lane).

| SHA | Commit |
|---|---|
| `3fc5b57e` | fix(w76): wrap long lines in wave75 pin |
| `21bf38ae` | docs(w76): loop status push |
| `e012e46f` | fix(w76): fail-closed soft-accept on brief/claim/unsent/mappers |

**Shipped**

- [LOOP_STATUS.md](LOOP_STATUS.md) — waves-completed through w75; status push **w76**; horizon still soft ~100.
- `tests/test_wave75_medium_bugs.py` — wrap long lines (ruff).
- Pin: `tests/test_wave76_medium_bugs.py` — cmd_brief / brief follow-up claim / drain disclosure_id / unsent retry / category haystack / row-mapper bool-id fail-closed (impl via w79).

---

## Wave 77 — Late w71 brief follow-up soft-accept close (+ late health/DL/ensure_user)

**Theme:** Close late w71 inventory after the w75 rollup — reject `str()` soft-accept on brief follow-up Telegram + worker title/symbol/external_id/url paths (STOP on CLEAN×2; no empty farming). Late (post-w80): fail-closed health ok / DL attempts / ensure_user id.

| SHA | Commit |
|---|---|
| `e3abfffc` | fix(w71): reject str() soft-accept on brief follow-up paths |
| `a105856b` | fix(w77): fail-closed health ok / DL attempts / ensure_user id |

**Shipped**

- `format_brief_followup` isinstance-guards url before allowlist (no `str(url)` soft-accept).
- Brief worker title/symbol/external_id/url paths isinstance-guard so hostile PG shapes cannot coerce via `str()` mid drain/follow-up.
- Pin: `tests/test_wave71_medium_bugs.py`.
- Late: `HealthState.update` isinstance-guards ok (no `bool("false")`/1 soft-accept); `format_dead_letter_notify` isinstance-guards attempts (no `int(True)==1`); `ensure_user` isinstance-guards RETURNING id — pin `tests/test_wave77_medium_bugs.py`.

---

## Wave 78 — isinstance pin restore + persist/disclosure id + promote

**Theme:** Restore storage brief claim/lookup isinstance pins dropped in the wave67 rewrite; lock remaining recent fail-closed guards; fail-closed persist/disclosure RETURNING ids and promote counts.

| SHA | Commit |
|---|---|
| `7b1e0613` | test(w78): isinstance pins push |
| `f1bdf0f9` | fix(w78): fail-closed persist/disclosure id + promote count |

**Shipped**

- Restore/complete source pins: `claim_brief_followups` / `get_ready_filing_brief` / `get_latest_ready_brief` PG fields; `_row_to_rule`/`_row_to_snapshot`; CSE sector/name + symbol_info; `BriefSettings.model_raw`.
- `persist_market_snapshots` isinstance-guards RETURNING ids; `upsert_disclosure` isinstance-guards id + requires `inserted is True`; `_promote_skipped_if_needed` rejects bool promote counts.
- Pin: `tests/test_wave78_medium_bugs.py`.

---

## Wave 79 — Soft-accept implementation (cmd_brief / claim / unsent / rows)

**Theme:** Land the fail-closed soft-accept implementation shared with parallel w76/w80 pin lanes — cmd_brief, brief follow-up claim/drain, unsent retry, disclosure category haystack, row mappers / create_alert.

| SHA | Commit |
|---|---|
| `a52d1d80` | fix(w79): fail-closed cmd_brief/claim/unsent/category/row ids |

**Shipped**

- `cmd_brief` rejects `str()` soft-accept of PG symbol/brief.
- Brief follow-up claim rows + drain `disclosure_id` isinstance-guard ints (no bool→1 / list abort); `message_text` no longer `str()`-coerces.
- `_disclosure_category_matches` rejects non-string haystacks; `_retry_unsent` skips poisoned unsent ids/message_text.
- `_row_to_rule` / `_row_to_snapshot` reject bool ids/price/flags; `create_alert_rule` reuses `_row_to_rule`; bad ISO ts/created_at fail closed.
- Pin: `tests/test_wave79_medium_bugs.py`.

---

## Wave 80 — Soft-accept pin + report rollup (76–80)

**Theme:** Pin the soft-accept contract (parity w76/w79); docs lane append waves 76–80 toward soft ~100 (STOP on CLEAN×2; no empty farming). Close late w71/w75 inventory SHAs.

| SHA | Commit |
|---|---|
| `d5c350d6` | fix(w80): fail-closed brief/unsent/category/row-id soft-accepts |
| _(this)_ | docs(w80): report push |

**Shipped**

- Pin: `tests/test_wave80_medium_bugs.py` — cmd_brief / follow-up claim / unsent / category / row-id fail-closed (impl via w79).
- `TIJORI_WAVE_REPORT.md` — close late w71 brief follow-up + late w75 rate/row-mapper inventory; append waves 76–80 toward soft ~100; header Waves 1–80.

---

## Wave 81 — Loop status (+ late notify/CSE soft-accept)

**Theme:** Honest loop-status advance after wave 80 rollup (STOP on CLEAN×2; no empty farming). Late: fail-closed notify RetryAfter/chat_id + CSE disclosure external_id / legacy PDF map keys.

| SHA | Commit |
|---|---|
| `b1c7a060` | docs(w81): loop status push |
| `8c7b4e59` | fix(w81): fail-closed notify RetryAfter/chat_id + disclosure ids |

**Shipped**

- [LOOP_STATUS.md](LOOP_STATUS.md) — waves-completed through w80; status push **w81**; horizon still soft ~100.
- Late: `_retry_delay_seconds` rejects bool (`float(True)==1.0`); `send_message` isinstance-guards chat_id/text; `announcement_to_disclosure` / `legacy_pdf_urls_by_id` reject bool/non-int ids before `str()`.

---

## Wave 82 — Soft-accept pin (claim/attempt/lock/health/count)

**Theme:** Pin fail-closed claim/attempt/lock/health/count soft-accepts (parity w76/w80; implementation shared with parallel w84 lane).

| SHA | Commit |
|---|---|
| `943fa6c0` | fix(w82): fail-closed claim/attempt/lock/health/count soft-accepts |

**Shipped**

- Pin: `tests/test_wave82_medium_bugs.py` — `claim_alert` / `claim_and_disarm` RETURNING ids; `mark_alert_attempt` attempt_count; `try_advisory_lock` `locked is True`; `health_check` rejects `True == 1`; PG COUNT + pool stats reject bool soft-accepts (impl via w84).

---

## Wave 83 — Adversarial CLEAN (diminishing returns) (+ late CDN)

**Theme:** Adversarial re-probe after w82/w84/w85 soft-accept closes. **CLEAN — 0 findings above minor.** Docs-only diminishing returns on further `int(True)` / `True==1` pin churn; late: fail-closed CDN PDF status/length/redirect soft-accepts (STOP on CLEAN×2; no empty farming).

| SHA | Commit |
|---|---|
| `9546849b` | docs(w83): CLEAN pass noting diminishing returns |
| `862295ed` | fix(w83): fail-closed CDN status/length/redirect soft-accepts |

**Shipped**

- [W83_ADVERSARIAL.md](W83_ADVERSARIAL.md) — CLEAN verdict at `e8070d0d`; soft-accept isinstance hunting on claim/lock/health/count surfaces called exhausted.
- [LOOP_STATUS.md](LOOP_STATUS.md) — adversarial CLEAN + diminishing-returns posture; prefer briefs soak / user-visible fuel over duplicate pins.
- Late: `fetch_cdn_pdf` isinstance-guards `status_code` (no `int(True)==1`), requires `is_redirect is True`, rejects bool/non-digit content-length — pin `tests/test_wave83_medium_bugs.py`.

---

## Wave 84 — Soft-accept implementation (claim/lock/health/count)

**Theme:** Land fail-closed claim/lock/health/count helpers shared with parallel w82/w85 pin lanes — `_require_pg_int` / `_pg_count`, RETURNING ids, advisory lock, health ok, COUNT / pool stats.

| SHA | Commit |
|---|---|
| `a99f3e80` | fix(w84): fail-closed claim/lock/health/count soft-accepts |

**Shipped**

- `_require_pg_int` / `_pg_count` helpers; `claim_alert` / `claim_and_disarm` / `mark_alert_attempt` / `ensure_user` RETURNING guards.
- `try_advisory_lock` requires `locked is True`; `health_check` rejects `True == 1`; pool stats skip bools; COUNT helpers reject bool/negative `n`.
- Pins: `tests/test_wave83_medium_bugs.py`, `tests/test_wave84_medium_bugs.py` (+ wave77 ensure_user pin realign).

---

## Wave 85 — Soft-accept pin + report rollup (81–85)

**Theme:** Pin the claim/lock/health/count soft-accept contract (parity w82/w84); docs lane append waves 81–85 toward soft ~100 (STOP on CLEAN×2; no empty farming). Close late w77 health/DL/ensure_user inventory SHA.

| SHA | Commit |
|---|---|
| `e8070d0d` | fix(w85): fail-closed claim/lock/health/count soft-accepts |
| `fb72504f` | docs(w85): report push |

**Shipped**

- Pin: `tests/test_wave85_medium_bugs.py` — claim/disarm/attempt/lock/health/count fail-closed (impl via w84).
- `TIJORI_WAVE_REPORT.md` — close late w77 health/DL/ensure_user inventory; append waves 81–85 toward soft ~100; header Waves 1–85.

---

## Wave 86 — Loop status + post-CDN adversarial CLEAN

**Theme:** Honest loop-status advance after wave 85 rollup; adversarial re-probe after late `fix(w83)` CDN status/length/redirect close. **CLEAN — 0 findings above minor.** Soft-accept / post-CDN lane CLEAN×2 with w83 (w87 separately CLEANs clock-skew).

| SHA | Commit |
|---|---|
| `afafc3f9` | docs(w86): loop status push |
| `89e52480` | docs(w86): CLEAN after CDN soft-accept close |

**Shipped**

- [LOOP_STATUS.md](LOOP_STATUS.md) — waves-completed through w85; status push **w86**; horizon still soft ~100.
- [W86_ADVERSARIAL.md](W86_ADVERSARIAL.md) — CLEAN verdict post-CDN re-probe; no new medium+; leave parallel w87–w90 fuel alone.

---

## Wave 87 — Clock-skew claim invariant CLEAN (+ CSE classify land)

**Theme:** WS-087 adversarial probe (shrunk per R1): disclosure/price claim eligibility keys off snapshot & disclosure timestamps, not host wall-clock. **CLEAN — 0 findings above minor.** Same commit also lands CSE `_request` status/CT/pace fail-closed + `tests/test_wave89_medium_bugs.py` (documented under w89/w90).

| SHA | Commit |
|---|---|
| `c578d60a` | docs(w87): CLEAN clock-skew claim invariant |

**Shipped**

- [W87_ADVERSARIAL.md](W87_ADVERSARIAL.md) — CLEAN; `chime/rules.py` has no `datetime.now`; ±5m/±1h data-stamp injection still gates correctly.
- Characterization pin: `tests/test_wave87_clock_skew.py`.
- CLEAN×2 with w83 on distinct fuel (clock-skew vs PG soft-accept).
- Cross-wave land (impl for w89): `CSEClient._request` / `_retryable` / `min_interval_seconds` fail-closed + `tests/test_wave89_medium_bugs.py`.

---

## Wave 88 — Ops polish + brief daily-cap/lease soft-accept

**Theme:** Runbook ops polish (`make tijori-smoke`, sectors tick, retention/ingest, briefs soak); fail-closed brief daily-cap / lease soft-accepts (`True==1` understated use → over-claim; `int(True)==1` reclaim races).

| SHA | Commit |
|---|---|
| `a2d54b0f` | docs(w88): ops polish |
| `8f14dcfa` | fix(w88): fail-closed brief daily-cap/lease soft-accepts |

**Shipped**

- [TIJORI.md](../../runbooks/TIJORI.md) — `make tijori-smoke`; `SECTORS_INGEST=1 make tick`; retention/ingest sections; brief env table + soak checklist.
- Reject bool `count_briefs_today` / `max_briefs_per_day` before drain arithmetic; guard promote hours, prompt max_chars, HTTP timeout/sleep, claim grace/backoff, lease seconds.
- Pin: `tests/test_wave88_medium_bugs.py`.

---

## Wave 89 — CSE status/CT/pace soft-accept close

**Theme:** Record medium+ CSE HTTP classify soft-accepts closed (impl + pin landed under w87 commit): bool `status_code` (`True >= 400` success), non-str content-type, `float(True)` pace, `_retryable` bool status.

| SHA | Commit |
|---|---|
| `c0726e65` | docs(w89): CSE status/CT/pace soft-accept close |

**Shipped**

- [W89_ADVERSARIAL.md](W89_ADVERSARIAL.md) — FIXED (medium+); four CSE soft-accept findings closed.
- Pin: `tests/test_wave89_medium_bugs.py` (impl via `c578d60a` / w87 land).
- [LOOP_STATUS.md](LOOP_STATUS.md) — w89 FIXED; new fuel distinct from exhausted PG soft-accept lane.

---

## Wave 90 — CSE soft-accept pin + report rollup (86–90)

**Theme:** Pin CSE status/CT/pace soft-accept contract (parity w89); docs lane append waves 86–90 toward soft ~100 (STOP on CLEAN×2; no empty farming). Close late w83 CDN inventory SHA.

| SHA | Commit |
|---|---|
| `029f46f6` | fix(w90): fail-closed CSE status/CT/pace soft-accepts |
| _(this)_ | docs(w90): report push |

**Shipped**

- Pin: `tests/test_wave90_medium_bugs.py` — CSE `_request` status/CT, `_retryable`, `min_interval_seconds` fail-closed (impl via w87/w89).
- `TIJORI_WAVE_REPORT.md` — close late w83 CDN soft-accept inventory; append waves 86–90 toward soft ~100; header Waves 1–90.

---

## Wave 91 — Bool numeric / CLI / disclosure / health harden

**Theme:** Document the real Wave 91 sibling fixes that landed after the wait/pull: bool numeric rule coercion, CLI/migrate arg soft-accepts, disclosure watermark conflict, and health poller merge. No fake SHAs; uncommitted parallel work is not counted here.

| SHA | Commit |
|---|---|
| `26a8da00` | Fix bool numeric rule coercion |
| `1f0b21b1` | fix(w91): fail closed CLI arg soft accepts |
| `abd0e736` | fix(w91): disclosure watermark conflict |
| `d84ad695` | fix(w91): fail closed health poller merge |
| _(this)_ | docs(w91): loop status + report |

**Shipped**

- Rule bool numeric coercion harden in `chime/domain.py` with `tests/test_wave91_rules_medium_bugs.py`.
- CLI/migrate arg soft-accept guards in `chime/__main__.py` / `chime/migrate.py` with `tests/test_wave91_config_medium_bugs.py`.
- Disclosure watermark conflict harden in `chime/storage.py` with `tests/test_wave91_storage_medium_bugs.py`.
- Health poller merge harden in `web/src/app/api/v1/health/route.ts`.
- `LOOP_STATUS.md` — waves completed through w91; pre-docs HEAD `26a8da00`; commits ahead of `main` `303+`; next steps point at w92–w100.

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
| 9 (`wave9`) | 7 |
| 10 (`wave10`) | 8 |
| 11 (`wave11`) | 5+ |
| 12 (`wave12`) | 1+ (docs + follow-ons) |
| 13 (`wave13` / `w13`) | 9 |
| 14 (`w14`) | 8 |
| 15 (`w15`) | 8 |
| 16 (`w16`) | 8 (100% coverage + CSE pacing / harden) |
| 17 (`w17`) | 9 (loop status + harden + health/DL/egress) |
| 18 (`w18`) | 7 (loop status + report + dash/ops harden) |
| 19 (`w19`) | 4 (CSRF + unwatch + category + egress) |
| 20 (`w20`) | 4 (loop status + report + START note + cancel/egress) |
| 21 (`w21`) | 3 (history/forms filter + logout + disclosure ids) |
| 22 (`w22`) | 3 (loop status + not-found Browse + late egress pin) |
| 23 (`w23`) | 2 (egress harden + report rollup) |
| 24 (`w24`) | 2 (market empty tick hint + late history/login pin) |
| 25 (`w25`) | 2 (session expiry + egress pin) |
| 26 (`w26`) | 2 (loop status + late mapRule/fail-closed pin) |
| 27 (`w27`) | 2 (egress harden + report rollup) |
| 28 (`w28`) | 4 (web tsc + loop status + late sector/browse/session pin) |
| 29 (`w29`) | 1 (demo auth SafeInteger) |
| 30 (`w30`) | 2 (alert form a11y + late symbol/health/nav pin) |
| 31 (`w31`) | 2 (report rollup + late session/market/health pin) |
| 32 (`w32`) | 2 (loop status + toFiniteNumber/health SafeInt) |
| 33 (`w33`) | 2 (nav scenarios active + late session/CSRF/health body pin) |
| 34 (`w34`) | 2 (loading NFA chrome + late history/strict-boolean pin) |
| 35 (`w35`) | 2 (SSRF/session harden + report rollup) |
| 36 (`w36`) | 2 (loop status + SSR loopback/HEALTH_URL/JSON body) |
| 37 (`w37`) | 1 (apiMutate /api/v1 gate + NavSession toIso) |
| 38 (`w38`) | 1 (SSR timeout/body + alert threshold cap) |
| 39 (`w39`) | 1 (/me parse, cancel id, session TTL, threshold, SSR bound) |
| 40 (`w40`) | 2 (SSR origin pin + report rollup) |
| 41 (`w41`) | 2 (loop status + CSRF/mapRule/SSR CL) |
| 42 (`w42`) | 1 (jsonError egress + SSR Cookie/CT) |
| 43 (`w43`) | 1 (cookie Secure/SameSite helpers) |
| 44 (`w44`) | 1 (mapRule threshold cap) |
| 45 (`w45`) | 4 (client mutate/SYMBOL_RE + residual + report) |
| 46 (`w46`) | 2 (loop status + SYMBOL_RE page egress / health CL) |
| 47 (`w47`) | 1 (client Content-Length early-reject) |
| 48 (`w48`) | 3 (alerts empty CTA + sectors/SSR/CL + pin realign) |
| 49 (`w49`) | 2 (sparkline ts sanitize + CTRL_RE escape) |
| 50 (`w50`) | 2 (toast/inline/format/sparkline + report) |
| 51 (`w51`) | 2 (loop status + fail-closed maxBytes) |
| 52 (`w52`) | 2 (alerts/watchlist LIMIT + toast tone + pin realign) |
| 53 (`w53`) | 1 (stream-bound response bodies) |
| 54 (`w54`) | 1 (sanitize maxLen + empty/skeleton/page caps) |
| 55 (`w55`) | 3 (sanitize pin + format abs-cap + report) |
| 56 (`w56`) | 2 (loop status + brief/PDF fail-closed caps) |
| 57 (`w57`) | 1 (API path/nav/CSRF typeof + length caps) |
| 58 (`w58`) | 2 (history pagination a11y + threshold/sanitize) |
| 59 (`w59`) | 2 (sparkline/toIso/decode/age + pin realign) |
| 60 (`w60`) | 4 (toFiniteNumber abs-cap + report + late caps cover) |
| 61 (`w61`) | 3 (loop status + body/formatTs/session + cookie pin) |
| 62 (`w62`) | 1 (bot threshold abs-cap + HEALTH_URL typeof) |
| 63 (`w63`) | 2 (sparkline/stale ts range + opaque label) |
| 64 (`w64`) | 1 (health age + dash auth + alert code) |
| 65 (`w65`) | 2 (filing URL/notify/mint + report) |
| 66 (`w66`) | 2 (loop status + briefs/scenarios/bot pin) |
| 67 (`w67`) | 2 (bot/poller/storage/brief env isinstance + provider/bulk/PDF; pin via w70 lane) |
| 68 (`w68`) | 1 (brief/resolve/alert/storage isinstance) |
| 69 (`w69`) | 3 (isinstance/typeof + price/log + pin realigns) |
| 70 (`w70`) | 4 (config/poller/guardrails/browse/session + disclosure + report) |
| 71 (`w71`) | 3 (loop status + wave67 pin import + late follow-up soft-accept) |
| 72 (`w72`) | 1 (cancel/brief/CSE/persist isinstance pin) |
| 73 (`w73`) | 2 (layout viewport + state/CSE/web fail-closed) |
| 74 (`w74`) | 1 (rule.type getattr + stock-name/board pin) |
| 75 (`w75`) | 5 (ruff + report/restore/SHA pin + late rate/row-mapper) |
| 76 (`w76`) | 3 (loop status + wrap pin + soft-accept pin) |
| 77 (`w77`) | 2 (late w71 brief follow-up + late health/DL/ensure_user) |
| 78 (`w78`) | 2 (isinstance pin restore + persist/disclosure/promote) |
| 79 (`w79`) | 1 (soft-accept implementation) |
| 80 (`w80`) | 2 (soft-accept pin + report rollup) |
| 81 (`w81`) | 2 (loop status + late notify/CSE soft-accept) |
| 82 (`w82`) | 1 (claim/attempt/lock/health/count soft-accept pin) |
| 83 (`w83`) | 2 (adversarial CLEAN + late CDN soft-accept) |
| 84 (`w84`) | 1 (claim/lock/health/count soft-accept + pins) |
| 85 (`w85`) | 2 (soft-accept pin + report rollup) |
| 86 (`w86`) | 2 (loop status + post-CDN adversarial CLEAN) |
| 87 (`w87`) | 1 (clock-skew CLEAN + CSE classify land) |
| 88 (`w88`) | 2 (ops polish + brief daily-cap/lease soft-accept) |
| 89 (`w89`) | 1 (CSE status/CT/pace soft-accept close docs) |
| 90 (`w90`) | 2 (CSE soft-accept pin + report rollup) |
| 91 (`w91`) | 4+ (bool numeric rule coercion + CLI/disclosure/health harden + report) |
| **Total** | **100+** |

---

## Remaining

### Phase 2 “live” (ops, not more code required for stub path)

1. Enable `AI_BRIEFS_ENABLED=1` + `AI_API_KEY` in a controlled env (`AI_PROVIDER=gemini|groq|openrouter`).
2. Watch rate caps / `AI_MAX_BRIEFS_PER_DAY` + `AI_BRIEF_SLEEP_SECONDS` under real CSE traffic; raise `CSE_MIN_INTERVAL_SECONDS` if cse.lk rate-limits.
3. Confirm follow-up notify + NFA suffix in production Telegram.

### Still deferred

| Item | Notes |
|---|---|
| Phase 3 scenario AI (beyond stub) | On-demand only; daily caps; legal review before MiroFish-style reuse |
| Portfolio / P&L / tax / screener / TA / payments / native app | Explicit non-goals |
| Always-on swarm / commit farming | Factory fence; stop when gates green — see [Parallelism honesty](#parallelism-honesty-wave-12) |
| Empty “100 loops” theater | Soft horizon only; wave 14+ continues quality-gated loops, not pad-to-N |
| Poll↔brief advisory deadlock “fix” | Audited non-issue; keep distinct lock IDs ([ADVISORY_LOCK_DEADLOCK.md](ADVISORY_LOCK_DEADLOCK.md)) |

### Suggested next improve-loop focus

- Wave 92+ only on **new** medium+ fuel — PG claim/lock/health/count soft-accept hunting exhausted (w83); CDN soft-accept closed (late w83); CSE HTTP classify soft-accepts closed (w89/w90); clock-skew claim CLEAN (w87); Wave 91 bool/CLI/disclosure/health fixes landed. Do not farm duplicate pins.
- Optionally raise `--cov-fail-under` toward 100 once CI owners agree (measured 100% already).
- Controlled briefs-on soak (not default-on in prod) — see runbook soak checklist.
- Keep `AI_SCENARIOS_ENABLED=0` until Phase 2 live brief path is proven.
- Prefer quality-gated max-width waves over empty concurrency theater.
- Keep [LOOP_STATUS.md](LOOP_STATUS.md) honest as the soft ~100 horizon advances.
