# Tijori CSE — Waves 1–31 report

**Branch:** `cursor/tijori-cse-phase1-e44e`  
**Date:** 2026-07-12  
**Plan:** [TIJORI_CSE_PLAN.md](../TIJORI_CSE_PLAN.md)  
**Ops:** [docs/runbooks/TIJORI.md](../../runbooks/TIJORI.md)  
**Range:** `a802cb7` … wave 31 (post-100% harden → soft ~100)

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

Phase 1 foundations and Phase 2 Tijori-core plumbing are **landed** across waves 1–5. Waves 6–7 add sectors browse, storage/SQL harden, retention/sectors coverage, Groq provider, disclosure baseline watermark, and briefs PDF grace / late follow-up sweep. Waves 8–9 add OpenRouter provider, brief drain pacing, market UX/a11y polish, adversarial grace/storage close, env-example completeness, storage brief-method coverage, and a Phase 3 scenario stub fence (`AI_SCENARIOS_ENABLED=0`). Wave 10 hardens briefs ops (smoke, rate limits, CDN requeue, poller/disclosure coverage) and audits poll↔brief advisory locks as a non-issue. Wave 11 aligns `/brief` empty-state test copy with AI-off messaging. Wave 12 records parallelism honesty (plus follow-on fix/docs/test lanes). Wave 13 closes browse API examples, env sync, Telegram/dash URL egress caps, web adversarial harden, and coverage pushes (migrate / storage / CSE / poller / bot). Wave 14 ships coverage/harden lanes (web regress, health/circuit, config/migrate, main, rules format fuzz, worker) plus fail-closed non-finite float env knobs. Wave 15 adds `make tijori-report`, briefs extra-install docs, help-budget / web movers / briefs / residual coverage, and ops-knob harden. **Wave 16 milestone:** full-package `pytest --cov=chime` at **100%** (3427 stmts / 0 miss) — coverage ratchet complete; post-milestone CSE pacing, brief egress, NFA chrome, and integration-collect harden. **Wave 17** closes post-100% harden (loop status, storage NaN defense, CSE pace concurrency, login a11y, factory verify, health proxy timeout, DL/`myalerts`/lease floor, finite price egress). **Wave 18** hardens dash/ops (brief-queue health UI, category cancel, watchlist duplicate soft flag, sparkline finite filter, category confirm / history egress / nested health). **Wave 19** documents dash CSRF, aligns `/unwatch` copy, adds dash disclosure category, and hardens history/watchlist/browse egress. **Wave 20** advances loop status + report, START browse note, and cancel-id / category-read / dash egress harden. **Wave 21** hardens alerts history/list/forms symbol filters (`normalizeSymbol` / `invalid_symbol`), disclosure SafeInteger ids, and logout hard-redirect UX. **Wave 22** pushes loop status + symbol not-found Browse link (late sectors/alerts/health egress pin). **Wave 23** hardens sectors/health/browse egress + safe ids and rolls the report. **Wave 24** points `/market` empty state at `make tick` / poller seed (late history/watchlist/login SafeInteger pin). **Wave 25** hard-redirects mid-use 401 / missing CSRF to `/login?expired=1` and pins egress harden. **Wave 26** advances loop status (late mapRule/alerts/watchlist fail-closed pin). **Wave 27** hardens toIso/delivery/SafeInteger egress and rolls the report. **Wave 28** restores web `tsc` (`BigInt()` / sanitize string guards) + loop status. **Wave 29** hardens demo auth telegram_id / allowlist via digits-only `toSafePositiveInt`. **Wave 30** keeps alert-form disclosure category a11y (`aria-describedby` / maxLength / `aria-busy`). **Wave 31** appends this rollup toward soft ~100 — not cov gap-fill. Live LLM briefs remain **flag/key gated** (`AI_BRIEFS_ENABLED=0` default; `AI_PROVIDER=gemini|groq|openrouter`). Phase 3 scenario AI is **stub only** — no LLM wiring yet.

| Track | Status |
|---|---|
| Phase 1 foundations | ✅ done |
| Phase 2 Tijori core | ◐ mostly done — live LLM still off until keyed |
| Phase 3 scenario AI | ◐ stub fence only (`AI_SCENARIOS_ENABLED=0`) |
| `chime` unit coverage | ✅ **100%** (wave 16 milestone) |
| Improve-loop / CI on touched paths | ongoing — wave 31 post-100% harden → soft ~100 loops |

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

## Wave 28 — Web tsc restore + loop status

**Theme:** Restore web `tsc --noEmit` after SafeInteger helpers; honest loop-status advance (STOP on CLEAN×2; no empty farming).

| SHA | Commit |
|---|---|
| `8c300c3` | fix(w28): restore web tsc — BigInt() and sanitize string guards |
| `8a249c0` | docs(w28): loop status push |

**Shipped**

- `safe-int.ts`: prefer `BigInt(0)` over `0n` literal so TS target stays happy; market/sectors browse only pass strings into `sanitizeDisclosureText`.
- [LOOP_STATUS.md](LOOP_STATUS.md) — waves-completed through w27; this status push **w28**; horizon still soft ~100.

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

## Wave 30 — Alert form a11y

**Theme:** Disclosure category field stays announced when invalid; length-capped; busy submit announced.

| SHA | Commit |
|---|---|
| `39169a8` | fix(w30): alert form a11y push |

**Shipped**

- Alert create form: keep `alert_category_hint` in `aria-describedby` when invalid; `maxLength={DISCLOSURE_CATEGORY_MAX}`; submit `aria-busy` while pending.
- `DASH_IA.md` + `tests/test_web_route_regressions.py` pin the contract.

---

## Wave 31 — Report rollup

**Theme:** Docs lane append waves 28–31 toward soft ~100 (STOP on CLEAN×2; no empty farming). Close late w24/w26 inventory SHAs.

| SHA | Commit |
|---|---|
| _(this)_ | docs(w31): report push |

**Shipped**

- `TIJORI_WAVE_REPORT.md` — close wave 24 late history/login pin + wave 26 late mapRule pin; append waves 28–31 toward soft ~100.

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
| 28 (`w28`) | 2 (web tsc restore + loop status) |
| 29 (`w29`) | 1 (demo auth SafeInteger) |
| 30 (`w30`) | 1 (alert form a11y) |
| 31 (`w31`) | 1 (report rollup) |
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

- Wave 31+ post-100% harden/ops only (STOP early on CLEAN×2); do not farm commits to pad loops.
- Optionally raise `--cov-fail-under` toward 100 once CI owners agree (measured 100% already).
- Controlled briefs-on soak (not default-on in prod).
- Keep `AI_SCENARIOS_ENABLED=0` until Phase 2 live brief path is proven.
- Prefer quality-gated max-width waves over empty concurrency theater.
- Keep [LOOP_STATUS.md](LOOP_STATUS.md) honest as the soft ~100 horizon advances.
