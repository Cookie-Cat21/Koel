# Third-party open-source dependencies

Chime does **not** vendor upstream source trees into this repo. Runtime
dependencies come from PyPI (Python package) and npm (`web/`).

## Python (`pyproject.toml`)

| Package | License | Role |
|---|---|---|
| [httpx](https://github.com/encode/httpx) | BSD-3-Clause | HTTP client for cse.lk adapter |
| [tenacity](https://github.com/jd/tenacity) | Apache-2.0 | Retries / backoff on flaky upstream calls |
| [pydantic](https://github.com/pydantic/pydantic) | MIT | Internal schemas / validation |
| [structlog](https://github.com/hynek/structlog) | MIT / Apache-2.0 | Structured logging |
| [APScheduler](https://github.com/agronholm/apscheduler) | MIT | Market-hours poller schedule |
| [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) | LGPL-3.0 | Telegram bot |
| [psycopg](https://github.com/psycopg/psycopg) (v3) | LGPL-3.0 | Postgres driver |

Dev extras (`pytest`, `ruff`, `mypy`, etc.) are listed in `pyproject.toml`
`[project.optional-dependencies]` and follow their own upstream licenses.

A shorter copy also lives at repo-root [`THIRD_PARTY.md`](../THIRD_PARTY.md)
(kept for historical layout). Prefer this file for dashboard + bot together.

## Dashboard (`web/package.json`)

| Package | License | Role |
|---|---|---|
| [next](https://github.com/vercel/next.js) | MIT | App Router UI + Route Handlers |
| [react](https://github.com/facebook/react) / react-dom | MIT | UI |
| [tailwindcss](https://github.com/tailwindlabs/tailwindcss) | MIT | Styling |
| [@tailwindcss/postcss](https://github.com/tailwindlabs/tailwindcss) | MIT | PostCSS integration (dev) |
| [tw-animate-css](https://github.com/Wombosvideo/tw-animate-css) | MIT | Animation utilities used by shadcn |
| [pg](https://github.com/brianc/node-postgres) | MIT | Postgres client (no cse.lk from `web/`) |
| [shadcn/ui](https://ui.shadcn.com/) (copied components + CLI) | MIT | Button / Input / Label / Badge / Select primitives |
| [radix-ui](https://www.radix-ui.com/) | MIT | Accessible primitives (via shadcn) |
| [class-variance-authority](https://github.com/joe-bell/cva) | Apache-2.0 | Variant helpers |
| [clsx](https://github.com/lukeed/clsx) / [tailwind-merge](https://github.com/dcastil/tailwind-merge) | MIT | className utilities |
| [lucide-react](https://github.com/lucide-icons/lucide) | ISC | Icons |
| [d3-force](https://github.com/d3/d3-force) | ISC | Ownership map force-directed layout (repulsion / collide) |
| [@xyflow/react](https://github.com/xyflow/xyflow) | MIT | Graph canvas (ownership + people) |

### Fonts

| Face | License | Role | How loaded |
|---|---|---|---|
| [Cal Sans](https://github.com/calcom/sans) | OFL-1.1 | Display / headings (`font-display`) | `next/font/local` — `web/src/fonts/CalSans-*.woff2` |
| [Inter](https://fonts.google.com/specimen/Inter) | OFL-1.1 | UI body / small type (`font-sans`) | `next/font/google` |
| [JetBrains Mono](https://fonts.google.com/specimen/JetBrains+Mono) | OFL-1.1 | Code / IDs (`font-mono`) | `next/font/google` |

Cal Sans OFL copy: `web/src/fonts/OFL.txt`.

Exact versions: see `web/package-lock.json`. ESLint / TypeScript tooling is
dev-only.

### Marketing UI patterns (adapted in-tree — no new npm deps)

| Pattern | Source | License | Date | Notes |
|---|---|---|---|---|
| FAQ divided + chevrons | [HyperUI FAQs](https://www.hyperui.dev/components/marketing/faqs) | MIT | 2026-07-15 | `FaqSection` — native `<details>`, lucide chevron |
| Feature list rows | [HyperUI Feature Grids](https://www.hyperui.dev/components/marketing/feature-grids) | MIT | 2026-07-15 | `FeatureList` — rows, not card wall |
| Simple footer | [HyperUI Footers](https://www.hyperui.dev/components/marketing/footers) | MIT | 2026-07-15 | `SiteFooter` — NFA + thin links |
| Announcement bar | Banner pattern (21st / Shadcnblocks-inspired) | MIT pattern only | 2026-07-15 | `AnnouncementBar` — no upstream copy-paste |
| End CTA band | Shadcnblocks `cta34` rhythm | Pattern only | 2026-07-15 | `EndCta` — dual CTA, no tinted hero card |
| 2-tier pricing stub | [HyperUI Pricing](https://www.hyperui.dev/components/marketing/pricing) | MIT | 2026-07-15 | `/pricing` — Free / Later, **no checkout** |
| Split hero structure | Cult Hero Color Panels (structure only) | Pattern only | 2026-07-15 | Copy left / proof right — **no shaders** |
| Mid CTA left/right | [HyperUI CTAs](https://www.hyperui.dev/components/marketing/ctas) | MIT | 2026-07-15 | `MidCta` — ink band, dual actions |
| Telegram proof panel | Daisy chat pattern (in-tree) | Pattern | 2026-07-15 | `TelegramProof` — not a device-frame hero |

### Dash kit patterns (adapted in-tree — no new npm deps)

| Pattern | Source | License | Date | Notes |
|---|---|---|---|---|
| Rank bar list | [Tremor Bar List](https://tremor.so/docs/ui/bar-list) | Apache-2.0 pattern | 2026-07-17 | `RankBarList` — influence / shared seats; Chime tokens |
| Filter chips | HyperUI filter density | MIT pattern | 2026-07-17 | `FilterChip` — All / Leadership on `/people` |
| Event timeline | [HyperUI timelines](https://www.hyperui.dev/) | MIT pattern | 2026-07-17 | `EventTimeline` — dossier Across years |
| KPI strip | HyperUI stats / IndexStrip density | MIT pattern | 2026-07-17 | `KpiStrip` — ownership map summary |
| Stat cards | HyperUI stats | MIT pattern | 2026-07-15 | `StatCard` — overview / health / dossier |
| Alert banner | Tremor / Watermelon thin alert | Pattern | 2026-07-15 | `AlertBanner` — ops + people snapshot honesty |
| Movers bar list | Tremor bar-list | Apache-2.0 pattern | 2026-07-15 | `MoversBarList` — market % movers only |
| Disclosure timeline | HyperUI timeline | MIT pattern | 2026-07-15 | `DisclosureTimeline` — symbol filings |

**Rejected (do not add):** React Bits (Commons Clause), DaisyUI npm plugin, 21st Financial Dashboard packs, Cult Pro/shaders, Apple Cards Carousel on signed-in dash. See `docs/factory/ARDENO_UI_MASTER_PLAN.md`.

For usage notes and related bookmarks, see [RESOURCES.md](RESOURCES.md).
