# Workstream catalog (WS-001 … WS-100)

Planning phase catalog for the [Commit Factory](../COMMIT_FACTORY.md).
Executed by **8 concurrent planning agents**; reviewed by **8 adversarial agents** (see [../review/IMPROVEMENTS.md](../review/IMPROVEMENTS.md)). Status: `epoch1` | `backlog` | `kill/defer` (hard concurrency cap); not 100 simultaneous processes.

| ID | Lane | Title | Status | Detail |
|---|---|---|---|---|
| WS-001 | CORE | Parse `dateOfAnnouncement` when `createdDate` is null | epoch1 | [doc](WAVE1_CORE.md) |
| WS-002 | CORE | Fail-closed disclosure eval when `rule.created_at` is missing | epoch1 | [doc](WAVE1_CORE.md) |
| WS-003 | CORE | Bulk `approvedAnnouncement` path for large watchlists | backlog | [doc](WAVE1_CORE.md) |
| WS-004 | CORE | Company-name → symbol mapping for bulk disclosures | backlog | [doc](WAVE1_CORE.md) |
| WS-005 | CORE | Verify and harden disclosure deep-link URLs | backlog | [doc](WAVE1_CORE.md) |
| WS-006 | CORE | Dead-letter unsent alerts after N permanent Telegram failures | backlog | [doc](WAVE1_CORE.md) |
| WS-007 | CORE | Disarm price rules on successful unsent retry | kill/defer | [doc](WAVE1_CORE.md) |
| WS-008 | CORE | Same-minute rearm + identical-price `event_key` collision | backlog | [doc](WAVE1_CORE.md) |
| WS-009 | CORE | Concurrent identical `/alert` IntegrityError handling | epoch1 | [doc](WAVE1_CORE.md) |
| WS-010 | CORE | Advisory-lock pool footgun (`max_size=1` / held connection) | backlog | [doc](WAVE1_CORE.md) |
| WS-011 | CORE | Automated dual-poller kill / leader-election test | backlog | [doc](WAVE1_CORE.md) |
| WS-012 | CORE | `both` SIGTERM polish + honest `tick --force` | epoch1 | [doc](WAVE1_CORE.md) |
| WS-013 | CORE | Honest `/unwatch` when orphan rules exist | backlog | [doc](WAVE1_CORE.md) |
| WS-014 | CORE | Bot UX: `/start` ≤3 lines + tighter help surface | backlog | [doc](WAVE1_CORE.md) |
| WS-015 | CORE | `/myalerts` shows armed / fire state + cancel hint | backlog | [doc](WAVE1_CORE.md) |
| WS-016 | CORE | Bare-ticker normalization (`.N0000` / common CSE forms) | backlog | [doc](WAVE1_CORE.md) |
| WS-017 | CORE | Adapter: disclosure circuit-open must not look like empty success | epoch1 | [doc](WAVE1_CORE.md) |
| WS-018 | CORE | Adapter resilience: partial bulk + schema drift logging | backlog | [doc](WAVE1_CORE.md) |
| WS-019 | CORE | Daily-move day-boundary and `previous_close` edge cases | backlog | [doc](WAVE1_CORE.md) |
| WS-020 | CORE | Poll only disclosure symbols that have disclosure rules | epoch1 | [doc](WAVE1_CORE.md) |
| WS-021 | DASH | Amend constitution for thin dashboard | epoch1 | [doc](WAVE1_DASH.md) |
| WS-022 | DASH | IA, sitemap, and page inventory | backlog | [doc](WAVE1_DASH.md) |
| WS-023 | DASH | Auth approach: shared secret + telegram scope | epoch1 | [doc](WAVE1_DASH.md) |
| WS-024 | DASH | Formalize Postgres → JSON API contract | epoch1 | [doc](WAVE1_DASH.md) |
| WS-025 | DASH | Scaffold `web/` Next.js + Tailwind + shadcn | backlog | [doc](WAVE1_DASH.md) |
| WS-026 | DASH | App shell, brand, and design tokens | backlog | [doc](WAVE1_DASH.md) |
| WS-027 | DASH | Mobile layout system | backlog | [doc](WAVE1_DASH.md) |
| WS-028 | DASH | Compliance NFA chrome on every page | backlog | [doc](WAVE1_DASH.md) |
| WS-029 | DASH | Empty states system | backlog | [doc](WAVE1_DASH.md) |
| WS-030 | DASH | API: health + me + read watchlist | backlog | [doc](WAVE1_DASH.md) |
| WS-031 | DASH | Watchlist page (read + add/remove) | backlog | [doc](WAVE1_DASH.md) |
| WS-032 | DASH | API: alerts CRUD | backlog | [doc](WAVE1_DASH.md) |
| WS-033 | DASH | Alerts page UI | backlog | [doc](WAVE1_DASH.md) |
| WS-034 | DASH | API + UI: fire history | backlog | [doc](WAVE1_DASH.md) |
| WS-035 | DASH | Symbol detail: price + sparkline | backlog | [doc](WAVE1_DASH.md) |
| WS-036 | DASH | Symbol detail: disclosures list | backlog | [doc](WAVE1_DASH.md) |
| WS-037 | DASH | Ops health page | backlog | [doc](WAVE1_DASH.md) |
| WS-038 | DASH | Login stub + Telegram Login placeholder | backlog | [doc](WAVE1_DASH.md) |
| WS-039 | DASH | Dash smoke tests and TTFB budget | backlog | [doc](WAVE1_DASH.md) |
| WS-040 | DASH | DASH Pass-1 report template and lane checklist | backlog | [doc](WAVE1_DASH.md) |
| WS-041 | OPS | GitHub Actions CI (lint + typecheck + unit tests) | epoch1 | [doc](WAVE1_OPS.md) |
| WS-042 | OPS | docker-compose Postgres for local DX | epoch1 | [doc](WAVE1_OPS.md) |
| WS-043 | OPS | Seed / demo data script | backlog | [doc](WAVE1_OPS.md) |
| WS-044 | OPS | Coverage reporting in CI | backlog | [doc](WAVE1_OPS.md) |
| WS-045 | OPS | Release checklist | backlog | [doc](WAVE1_OPS.md) |
| WS-046 | OPS | Structured log fields standard | backlog | [doc](WAVE1_OPS.md) |
| WS-047 | OPS | Latency metric export | backlog | [doc](WAVE1_OPS.md) |
| WS-048 | OPS | Migrate against ephemeral Postgres in CI | epoch1 | [doc](WAVE1_OPS.md) |
| WS-049 | OPS | Optional pre-commit hooks | backlog | [doc](WAVE1_OPS.md) |
| WS-050 | OPS | CONTRIBUTING guide | backlog | [doc](WAVE1_OPS.md) |
| WS-051 | OPS | Branch and PR templates | backlog | [doc](WAVE1_OPS.md) |
| WS-052 | OPS | Secret scanning notes | backlog | [doc](WAVE1_OPS.md) |
| WS-053 | OPS | Healthcheck probe script | backlog | [doc](WAVE1_OPS.md) |
| WS-054 | OPS | One-command Make targets | backlog | [doc](WAVE1_OPS.md) |
| WS-055 | OPS | justfile companion targets | backlog | [doc](WAVE1_OPS.md) |
| WS-056 | OPS | CI integration job (DB-backed pytest) | backlog | [doc](WAVE1_OPS.md) |
| WS-057 | OPS | Compose stack health + poller tick smoke | backlog | [doc](WAVE1_OPS.md) |
| WS-058 | OPS | Action pinning and Dependabot for OPS surface | backlog | [doc](WAVE1_OPS.md) |
| WS-059 | OPS | Structured CI job summaries / failure taxonomy | backlog | [doc](WAVE1_OPS.md) |
| WS-060 | OPS | OPS runbook + one-command DX verification matrix | backlog | [doc](WAVE1_OPS.md) |
| WS-061 | QUALITY | Inventory missing tests vs quality bar | backlog | [doc](WAVE1_QUALITY.md) |
| WS-062 | QUALITY | Property tests for price crossing primitives | kill/defer | [doc](WAVE1_QUALITY.md) |
| WS-063 | QUALITY | Property tests for evaluate + rearm cycles | kill/defer | [doc](WAVE1_QUALITY.md) |
| WS-064 | QUALITY | Daily-move crossing properties | kill/defer | [doc](WAVE1_QUALITY.md) |
| WS-065 | QUALITY | Integration: dual-poller single claim (DB) | backlog | [doc](WAVE1_QUALITY.md) |
| WS-066 | QUALITY | Dual-poller without optional DB (in-process fake lock) | epoch1 | [doc](WAVE1_QUALITY.md) |
| WS-067 | QUALITY | Bot handler unit tests: watch / alert / my\* | backlog | [doc](WAVE1_QUALITY.md) |
| WS-068 | QUALITY | Bot handler unit tests: cancel / unwatch edges | epoch1 | [doc](WAVE1_QUALITY.md) |
| WS-069 | QUALITY | Adapter junk / partial-row fixtures | backlog | [doc](WAVE1_QUALITY.md) |
| WS-070 | QUALITY | Coverage gate beyond `rules.py` | backlog | [doc](WAVE1_QUALITY.md) |
| WS-071 | QUALITY | Mutation-test thought experiment (documented) | backlog | [doc](WAVE1_QUALITY.md) |
| WS-072 | QUALITY | Honest load / latency harness | backlog | [doc](WAVE1_QUALITY.md) |
| WS-073 | QUALITY | Market-hours / timezone edge tests | backlog | [doc](WAVE1_QUALITY.md) |
| WS-074 | QUALITY | Disclosure `created_at` / timezone compare cases | backlog | [doc](WAVE1_QUALITY.md) |
| WS-075 | QUALITY | Same-minute rearm `event_key` collision test | backlog | [doc](WAVE1_QUALITY.md) |
| WS-076 | QUALITY | Idempotency + unsent retry under test expansion | backlog | [doc](WAVE1_QUALITY.md) |
| WS-077 | QUALITY | Health honesty regression suite | epoch1 | [doc](WAVE1_QUALITY.md) |
| WS-078 | QUALITY | Notify message contract tests | backlog | [doc](WAVE1_QUALITY.md) |
| WS-079 | QUALITY | Pytest markers, CI skip policy, slow/integration split | backlog | [doc](WAVE1_QUALITY.md) |
| WS-080 | QUALITY | QUALITY wave verify + proof pack | backlog | [doc](WAVE1_QUALITY.md) |
| WS-081 | ADVERSARIAL | Market open/close inclusive boundary | backlog | [doc](WAVE1_ADVERSARIAL.md) |
| WS-082 | ADVERSARIAL | Asia/Colombo has no DST (ZoneInfo honesty) | backlog | [doc](WAVE1_ADVERSARIAL.md) |
| WS-083 | ADVERSARIAL | Telegram RetryAfter storm under burst fires | epoch1 | [doc](WAVE1_ADVERSARIAL.md) |
| WS-084 | ADVERSARIAL | Neon pool exhaustion while advisory lock held | backlog | [doc](WAVE1_ADVERSARIAL.md) |
| WS-085 | ADVERSARIAL | Dashboard auth bypass (future thin web) | kill/defer | [doc](WAVE1_ADVERSARIAL.md) |
| WS-086 | ADVERSARIAL | CSE returns HTML error page as 200 | backlog | [doc](WAVE1_ADVERSARIAL.md) |
| WS-087 | ADVERSARIAL | Clock skew between app host and Postgres / CSE | backlog | [doc](WAVE1_ADVERSARIAL.md) |
| WS-088 | ADVERSARIAL | Duplicate bot + poller processes (split deploy) | backlog | [doc](WAVE1_ADVERSARIAL.md) |
| WS-089 | ADVERSARIAL | Same-minute rearm `event_key` collision | kill/defer | [doc](WAVE1_ADVERSARIAL.md) |
| WS-090 | ADVERSARIAL | Unbounded unsent Telegram retry / no dead-letter | backlog | [doc](WAVE1_ADVERSARIAL.md) |
| WS-091 | ADVERSARIAL | Concurrent identical `/alert` IntegrityError | backlog | [doc](WAVE1_ADVERSARIAL.md) |
| WS-092 | ADVERSARIAL | `both` SIGTERM / tick `--force` polish | backlog | [doc](WAVE1_ADVERSARIAL.md) |
| WS-093 | ADVERSARIAL | Null `createdDate` / undated disclosure fail-closed | backlog | [doc](WAVE1_ADVERSARIAL.md) |
| WS-094 | ADVERSARIAL | Disclosure deep-link `#announcementId` on cse.lk | backlog | [doc](WAVE1_ADVERSARIAL.md) |
| WS-095 | ADVERSARIAL | Health endpoint unauthenticated exposure | backlog | [doc](WAVE1_ADVERSARIAL.md) |
| WS-096 | ADVERSARIAL | Circuit half-open stampede after CSE outage | backlog | [doc](WAVE1_ADVERSARIAL.md) |
| WS-097 | ADVERSARIAL | Weekend / holiday poll skip vs CSE special sessions | backlog | [doc](WAVE1_ADVERSARIAL.md) |
| WS-098 | ADVERSARIAL | Overnight gap crossing at first open tick | kill/defer | [doc](WAVE1_ADVERSARIAL.md) |
| WS-099 | ADVERSARIAL | Advisory unlock failure / connection drop mid-tick | backlog | [doc](WAVE1_ADVERSARIAL.md) |
| WS-100 | ADVERSARIAL | Dashboard session fixation / CSRF on alert mutations | backlog | [doc](WAVE1_ADVERSARIAL.md) |

## Wave files

- [WAVE1_CORE.md](WAVE1_CORE.md) — WS-001–020
- [WAVE1_DASH.md](WAVE1_DASH.md) — WS-021–040
- [WAVE1_OPS.md](WAVE1_OPS.md) — WS-041–060
- [WAVE1_QUALITY.md](WAVE1_QUALITY.md) — WS-061–080
- [WAVE1_ADVERSARIAL.md](WAVE1_ADVERSARIAL.md) — WS-081–100

## Related

- [DASH_IA.md](../DASH_IA.md)
- [ORCHESTRATOR_PROMPTS.md](../ORCHESTRATOR_PROMPTS.md)
- [METRICS.md](../METRICS.md)
