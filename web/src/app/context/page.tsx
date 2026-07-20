import Link from "next/link";

import { AppNav } from "@/components/app-nav";
import { HelpLink } from "@/components/help-link";
import { ContextModule } from "@/components/context/context-module";
import { TapePulseStrip } from "@/components/tape/tape-pulse-strip";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { PageHeader } from "@/components/page-header";
import { SoftPageRefresh } from "@/components/soft-page-refresh";
import { Button } from "@/components/ui/button";
import {
  deltaVs,
  headlineDay,
  headlineIndex,
  queryAppetiteHistory,
} from "@/lib/api/appetite";
import { queryContextNews } from "@/lib/api/context-news";
import { queryContextBundle } from "@/lib/api/macro-context";
import { queryTapePulse } from "@/lib/api/tape";
import { requirePageSession } from "@/lib/auth/page-session";
import { getPool } from "@/lib/db";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Context · koel",
  description:
    "CSE tape pulse plus official FX, oil, tourism, and food context. Not financial advice.",
};

export default async function ContextPage() {
  await requirePageSession();
  const pool = getPool();

  let appetiteHistory: Awaited<ReturnType<typeof queryAppetiteHistory>> = [];
  let tape: Awaited<ReturnType<typeof queryTapePulse>> | null = null;
  let macros: Awaited<ReturnType<typeof queryContextBundle>> | null = null;
  let news: Awaited<ReturnType<typeof queryContextNews>> = [];

  try {
    appetiteHistory = await queryAppetiteHistory(pool, {
      limit: 90,
      source: "cse",
    });
  } catch {
    appetiteHistory = [];
  }
  try {
    tape = await queryTapePulse(pool);
  } catch {
    tape = null;
  }
  try {
    macros = await queryContextBundle(pool);
  } catch {
    macros = null;
  }
  try {
    news = await queryContextNews(pool, 12);
  } catch {
    news = [];
  }

  const appetiteLatest = headlineDay(appetiteHistory);
  const appetiteDelta1 = deltaVs(
    appetiteHistory,
    1,
    headlineIndex(appetiteHistory),
  );

  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <AppNav active="/context" />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10"
      >
        <PageHeader
          eyebrow="Research"
          title="Context"
          description="Official Sri Lanka + energy context around the CSE tape. Attribution on every card. Not a Macro terminal clone."
          action={
            <div className="flex flex-wrap items-center gap-2">
              <HelpLink topic="context-macros">Context help</HelpLink>
              <SoftPageRefresh />
              <Button asChild variant="outline" size="sm">
                <Link href="/overview">Overview</Link>
              </Button>
              <Button asChild size="sm">
                <Link href="/alerts">Arm Telegram</Link>
              </Button>
            </div>
          }
        />

        <TapePulseStrip
          className="mt-6"
          appetiteLatest={appetiteLatest}
          appetiteHistory={appetiteHistory}
          appetiteDelta1={appetiteDelta1}
          foreign={tape?.foreign ?? null}
          foreignHistory={tape?.foreign_history ?? []}
          foreignDelta={tape?.foreign_delta ?? null}
          book={
            tape?.book ?? {
              imbalance_pct: null,
              bid_share_pct: null,
              sample_n: 0,
              as_of: null,
              label: "unknown",
            }
          }
        />

        <div className="mt-8 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Macro modules
            </p>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
              Fill when flagged adapters ingest into{" "}
              <span className="font-mono text-xs">macro_series</span>. Empty
              cards stay empty — not fake demo numbers.
            </p>
          </div>
          <NfaInline />
        </div>

        <div className="mt-5 grid items-stretch gap-4 sm:grid-cols-2">
          <ContextModule
            title="USD / LKR"
            subtitle="CBSL commercial bank TT mid (buy/sell average)."
            card={
              macros?.usd_lkr ?? {
                series_id: "USD_LKR",
                latest: null,
                history: [],
                delta_pct: null,
              }
            }
            emptyHint="Enable CBSL_FX_ENABLED and run macro-tick (daily GitHub workflow)."
            sectorHref="/market"
            sectorLabel="Browse CSE"
          />
          <ContextModule
            title="EUR / LKR"
            subtitle="Same CBSL sheet — euro leg for import-sensitive names."
            card={
              macros?.eur_lkr ?? {
                series_id: "EUR_LKR",
                latest: null,
                history: [],
                delta_pct: null,
              }
            }
            emptyHint="Populates with USD/LKR when CBSL FX ingest runs."
          />
          <ContextModule
            title="Brent crude"
            subtitle="EIA Europe Brent spot — energy sector bridge."
            card={
              macros?.brent ?? {
                series_id: "BRENT_SPOT",
                latest: null,
                history: [],
                delta_pct: null,
              }
            }
            formatDigits={2}
            emptyHint="Enable EIA_OIL_ENABLED and run macro-tick (API key optional — PET bulk zip fallback)."
            sectorHref="/market?q=energy"
            sectorLabel="Energy-related browse"
          />
          <ContextModule
            title="WTI crude"
            subtitle="EIA Cushing WTI spot (companion to Brent)."
            card={
              macros?.wti ?? {
                series_id: "WTI_SPOT",
                latest: null,
                history: [],
                delta_pct: null,
              }
            }
            emptyHint="Same EIA oil adapter as Brent (API or PET bulk)."
          />
          <ContextModule
            title="Tourism earnings"
            subtitle="CBSL monthly tourism earnings (USD mn) — Hotels / Travel bridge."
            card={
              macros?.tourism_arrivals ?? {
                series_id: "TOURISM_ARRIVALS",
                latest: null,
                history: [],
                delta_pct: null,
              }
            }
            formatDigits={1}
            emptyHint="Enable SLTDA_TOURISM_ENABLED and run macro-tick (CBSL earnings sheet)."
            sectorHref="/market?q=hotel"
            sectorLabel="Hotels / leisure"
          />
          <ContextModule
            title="Food pressure"
            subtitle="CBSL headline CCPI (2021=100) — consumer / food sector bridge."
            card={
              macros?.food_pressure ?? {
                series_id: "FOOD_PRESSURE",
                latest: null,
                history: [],
                delta_pct: null,
              }
            }
            formatDigits={1}
            emptyHint="Enable DCS_FOOD_ENABLED and run macro-tick (CBSL CCPI sheet)."
            sectorHref="/market?q=food"
            sectorLabel="Food / consumer"
          />
        </div>

        <div className="mt-10 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              World markets
            </p>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
              ≤5 research / delayed EOD tiles (FRED + Yahoo). Not CSE official
              — enable{" "}
              <span className="font-mono text-xs">
                WORLD_INDEX_RESEARCH_ENABLED
              </span>{" "}
              via macro-tick.
            </p>
          </div>
        </div>

        <div className="mt-5 grid items-stretch gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <ContextModule
            title="S&P 500"
            subtitle="US overnight tape — research / delayed (FRED)."
            card={
              macros?.world_spx ?? {
                series_id: "WORLD_SPX",
                latest: null,
                history: [],
                delta_pct: null,
              }
            }
            formatDigits={0}
            emptyHint="Enable WORLD_INDEX_RESEARCH_ENABLED and run macro-tick."
          />
          <ContextModule
            title="FTSE 100"
            subtitle="Europe proxy — research / delayed (Yahoo)."
            card={
              macros?.world_ftse ?? {
                series_id: "WORLD_FTSE",
                latest: null,
                history: [],
                delta_pct: null,
              }
            }
            formatDigits={0}
            emptyHint="Populates with world-index research ingest."
          />
          <ContextModule
            title="Nikkei 225"
            subtitle="Asia proxy — research / delayed (FRED)."
            card={
              macros?.world_nikkei ?? {
                series_id: "WORLD_NIKKEI",
                latest: null,
                history: [],
                delta_pct: null,
              }
            }
            formatDigits={0}
            emptyHint="Populates with world-index research ingest."
          />
          <ContextModule
            title="Nifty 50"
            subtitle="India proxy — research / delayed (Yahoo)."
            card={
              macros?.world_nsei ?? {
                series_id: "WORLD_NSEI",
                latest: null,
                history: [],
                delta_pct: null,
              }
            }
            formatDigits={0}
            emptyHint="Populates with world-index research ingest."
          />
          <ContextModule
            title="VIX"
            subtitle="US vol proxy — research / delayed (FRED)."
            card={
              macros?.world_vix ?? {
                series_id: "WORLD_VIX",
                latest: null,
                history: [],
                delta_pct: null,
              }
            }
            formatDigits={2}
            emptyHint="Populates with world-index research ingest."
          />
        </div>

        <section className="mt-10">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                CSE disclosure feed
              </p>
              <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
                Disclosure-first from koel Postgres (filings + market notices).
                No social-feed clone, no third-party full-text scrape.
              </p>
            </div>
            <div className="flex flex-wrap gap-3 text-xs">
              <Link
                href="/signals"
                className="font-medium underline-offset-4 hover:underline"
              >
                Signal Board
              </Link>
              <Link
                href="/appetite"
                className="font-medium underline-offset-4 hover:underline"
              >
                Appetite methodology
              </Link>
            </div>
          </div>

          {news.length === 0 ? (
            <p className="mt-4 rounded-xl border border-dashed border-border/80 px-4 py-6 text-sm text-muted-foreground">
              No recent CSE disclosures or notices in the last 45 days.
            </p>
          ) : (
            <ul className="mt-4 divide-y divide-border/60 rounded-xl border border-border">
              {news.map((item) => {
                const when = item.as_of
                  ? item.as_of.slice(0, 10)
                  : "—";
                const body = (
                  <>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-[10px] tracking-wide text-muted-foreground uppercase">
                          {item.kind}
                        </span>
                        {item.symbol ? (
                          <span className="font-mono text-xs text-foreground">
                            {item.symbol}
                          </span>
                        ) : null}
                        <span className="font-mono text-[11px] text-muted-foreground">
                          {when}
                        </span>
                      </div>
                      <p className="mt-1 text-sm leading-snug text-foreground">
                        {item.title}
                      </p>
                    </div>
                  </>
                );
                return (
                  <li key={`${item.kind}-${item.id}`}>
                    {item.href ? (
                      <a
                        href={item.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex gap-3 px-4 py-3 transition-colors hover:bg-muted/40"
                      >
                        {body}
                      </a>
                    ) : item.symbol ? (
                      <Link
                        href={`/symbols/${encodeURIComponent(item.symbol)}`}
                        className="flex gap-3 px-4 py-3 transition-colors hover:bg-muted/40"
                      >
                        {body}
                      </Link>
                    ) : (
                      <div className="flex gap-3 px-4 py-3">{body}</div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <div className="mt-10">
          <NfaFooter />
        </div>
      </main>
    </div>
  );
}
