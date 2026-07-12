import Link from "next/link";
import { notFound } from "next/navigation";

import { AppNav } from "@/components/app-nav";
import { EmptyState } from "@/components/empty-state";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { Sparkline } from "@/components/sparkline";
import { finiteSparklinePoints } from "@/lib/sparkline";
import { Button } from "@/components/ui/button";
import { safeFilingHref, safePdfUrl, sanitizeBriefText } from "@/lib/api/disclosure-safe";
import { serverApiGet } from "@/lib/api/server-fetch";
import { normalizeSymbol } from "@/lib/api/symbol";
import { requirePageSession } from "@/lib/auth/page-session";
import { formatNumber, formatPct, formatTs } from "@/lib/format";

export const dynamic = "force-dynamic";

/** Snapshots older than this are treated as stale for empty-copy (E11-D02). */
const STALE_MS = 24 * 60 * 60 * 1000;

function isStaleTs(ts: string | null | undefined): boolean {
  if (!ts) return false;
  const t = Date.parse(ts);
  if (Number.isNaN(t)) return false;
  return Date.now() - t > STALE_MS;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ symbol: string }>;
}) {
  const { symbol: raw } = await params;
  const symbol = normalizeSymbol(decodeURIComponent(raw)) ?? raw;
  return {
    title: `${symbol} · Chime`,
    description: `Last price and disclosures for ${symbol}.`,
  };
}

type SymbolPayload = {
  symbol: string;
  name: string | null;
  sector: string | null;
  last: {
    price: number;
    change: number | null;
    change_pct: number | null;
    volume: number | null;
    ts: string | null;
  } | null;
};

type SnapshotsPayload = {
  points: { ts: string | null; price: number | null; change_pct: number | null }[];
};

type DisclosuresPayload = {
  items: {
    id: number;
    external_id: string;
    title: string;
    category: string | null;
    url: string | null;
    published_at: string | null;
    company_name: string | null;
    pdf_url: string | null;
    brief: string | null;
    brief_status:
      | "pending"
      | "processing"
      | "ready"
      | "failed"
      | "skipped"
      | null;
  }[];
};

export default async function SymbolDetailPage({
  params,
}: {
  params: Promise<{ symbol: string }>;
}) {
  await requirePageSession();

  const { symbol: raw } = await params;
  const symbol = normalizeSymbol(decodeURIComponent(raw));
  if (!symbol) {
    notFound();
  }

  const encoded = encodeURIComponent(symbol);
  const [symRes, snapRes, discRes] = await Promise.all([
    serverApiGet(`/api/v1/symbols/${encoded}`),
    serverApiGet(`/api/v1/symbols/${encoded}/snapshots?limit=60`),
    serverApiGet(`/api/v1/symbols/${encoded}/disclosures?limit=20`),
  ]);

  if (symRes.status === 404) {
    notFound();
  }
  if (!symRes.ok) {
    return (
      <Shell>
        <EmptyState
          title={`Couldn’t load ${symbol}`}
          description={
            <>
              Chime couldn’t fetch this symbol from Postgres just now. Check
              your connection, then try again — or open it from your{" "}
              <Link href="/watchlist" className="underline underline-offset-4">
                watchlist
              </Link>
              .
            </>
          }
          action={
            <div className="flex flex-wrap gap-2">
              <Button asChild variant="outline">
                <Link href={`/symbols/${encoded}`}>Try again</Link>
              </Button>
              <Button asChild variant="ghost">
                <Link href="/watchlist">← Watchlist</Link>
              </Button>
            </div>
          }
        />
      </Shell>
    );
  }

  const data = (await symRes.json()) as SymbolPayload;
  const snaps = snapRes.ok
    ? ((await snapRes.json()) as SnapshotsPayload)
    : { points: [] };
  const discs = discRes.ok
    ? ((await discRes.json()) as DisclosuresPayload)
    : { items: [] };

  const snapsFailed = !snapRes.ok;
  const discsFailed = !discRes.ok;

  const changePct = data.last?.change_pct ?? null;
  const changeTone =
    changePct == null
      ? "text-muted-foreground"
      : changePct > 0
        ? "text-[oklch(0.42_0.09_165)]"
        : changePct < 0
          ? "text-destructive"
          : "text-muted-foreground";

  return (
    <Shell>
      <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
        <div className="min-w-0">
          <p className="font-mono text-xs tracking-wide text-muted-foreground uppercase">
            Symbol
          </p>
          <h1 className="font-display truncate text-3xl font-semibold tracking-tight sm:text-4xl">
            {data.symbol}
          </h1>
          {data.name ? (
            <p className="mt-1 text-sm text-muted-foreground sm:text-base">
              {data.name}
              {data.sector ? (
                <span className="text-muted-foreground/80"> · {data.sector}</span>
              ) : null}
            </p>
          ) : null}
        </div>
        <Link
          href="/watchlist"
          className="mt-3 rounded-sm text-sm text-muted-foreground underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none sm:mt-0"
        >
          ← Watchlist
        </Link>
      </div>

      <section className="mt-8 border-t border-border/60 pt-6">
        <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
          Last snapshot
        </h2>
        {data.last ? (
          <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label="Price" value={formatNumber(data.last.price)} mono />
            <Stat
              label="Change"
              value={formatNumber(data.last.change)}
              className={changeTone}
              mono
            />
            <Stat
              label="Change %"
              value={formatPct(data.last.change_pct)}
              className={changeTone}
              mono
            />
            <Stat
              label="Volume"
              value={
                data.last.volume == null
                  ? "—"
                  : Math.round(data.last.volume).toLocaleString("en-LK")
              }
              mono
            />
          </div>
        ) : (
          <EmptyState
            className="mt-4"
            title="No snapshot yet"
            description={
              <>
                Chime hasn’t stored a price tick for {data.symbol}. During
                market hours (09:30–14:30 SLT, weekdays) the poller writes
                snapshots here. Outside those hours this stays empty until the
                next session. Not financial advice.
              </>
            }
            action={
              <Button asChild variant="outline" size="sm">
                <Link href="/alerts">Set an alert</Link>
              </Button>
            }
          />
        )}
        {data.last && isStaleTs(data.last.ts) ? (
          <EmptyState
            className="mt-4"
            title="Snapshot looks stale"
            description={
              <>
                Last tick was {formatTs(data.last.ts)} (SLT) — more than a day
                ago. If market hours have passed without a refresh, the poller
                may be paused or this symbol wasn’t watched. Not financial
                advice.
              </>
            }
            action={
              <Button asChild variant="outline" size="sm">
                <Link href="/watchlist">Back to watchlist</Link>
              </Button>
            }
          />
        ) : null}
        {data.last?.ts && !isStaleTs(data.last.ts) ? (
          <p className="mt-3 text-xs text-muted-foreground">
            As of {formatTs(data.last.ts)} (SLT)
          </p>
        ) : null}
        <NfaInline className="mt-2" />
      </section>

      <section className="mt-8 border-t border-border/60 pt-6">
        <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
          Recent ticks
        </h2>
        <div className="mt-3">
          {snapsFailed ? (
            <p className="text-sm text-muted-foreground" role="status">
              Couldn’t load recent ticks right now.
            </p>
          ) : finiteSparklinePoints(snaps.points).length < 2 ? (
            <EmptyState
              className="mt-1"
              title="Not enough ticks"
              description={
                <>
                  Need at least two stored snapshots for a sparkline. Chime
                  keeps polling during market hours (09:30–14:30 SLT).
                </>
              }
            />
          ) : (
            <Sparkline points={snaps.points} />
          )}
        </div>
      </section>

      <section
        className="mt-8 border-t border-border/60 pt-6"
        aria-labelledby="disclosures-heading"
      >
        <h2
          id="disclosures-heading"
          className="text-sm font-medium tracking-wide text-muted-foreground uppercase"
        >
          Disclosures
        </h2>
        {discsFailed ? (
          <EmptyState
            className="mt-4"
            title="Couldn’t load disclosures"
            description={
              <>
                Chime couldn’t read stored filings for{" "}
                <code className="font-mono text-xs">{data.symbol}</code> just
                now. Check your connection, then try again — this is not an
                empty list.
              </>
            }
            action={
              <Button asChild variant="outline" size="sm">
                <Link href={`/symbols/${encoded}`}>Try again</Link>
              </Button>
            }
          />
        ) : discs.items.length === 0 ? (
          <EmptyState
            className="mt-4"
            title="No disclosures yet"
            description={
              <>
                Nothing stored for{" "}
                <code className="font-mono text-xs">{data.symbol}</code>. When
                the poller sees a new CSE announcement, it lists here with a
                link to the source. Or set{" "}
                <code className="font-mono text-xs">
                  /alert {data.symbol} disclosure
                </code>{" "}
                in Telegram to get pinged.
              </>
            }
            action={
              <Button asChild variant="outline" size="sm">
                <Link
                  href={`/alerts?symbol=${encodeURIComponent(data.symbol)}`}
                >
                  Alert on disclosures
                </Link>
              </Button>
            }
          />
        ) : (
          <>
            <ul
              className="mt-4 divide-y divide-border/60"
              aria-labelledby="disclosures-heading"
            >
              {discs.items.map((item) => {
                const href = safeFilingHref(item.pdf_url, item.url);
                const pdfOk = Boolean(safePdfUrl(item.pdf_url));
                const briefText = sanitizeBriefText(
                  item.brief,
                  item.brief_status,
                );
                const briefHeadingId = `disclosure-brief-${item.id}`;
                const titleClass =
                  "block rounded-sm text-sm font-medium text-foreground underline-offset-4 focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none";
                return (
                  <li key={item.id} className="py-3 first:pt-0">
                    {href ? (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`${titleClass} hover:underline`}
                      >
                        {item.title}
                        {pdfOk ? (
                          <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                            (PDF)
                          </span>
                        ) : null}
                        <span className="sr-only"> (opens in new tab)</span>
                      </a>
                    ) : (
                      <span className={titleClass}>
                        {item.title}
                      </span>
                    )}
                    <p className="mt-1 text-xs text-muted-foreground">
                      {formatTs(item.published_at)}
                      {item.category ? ` · ${item.category}` : ""}
                    </p>
                    {briefText ? (
                      <div
                        className="mt-2"
                        role="group"
                        aria-labelledby={briefHeadingId}
                      >
                        <p
                          id={briefHeadingId}
                          className="text-xs font-medium tracking-wide text-muted-foreground uppercase"
                        >
                          Filing brief
                        </p>
                        <p className="mt-1 text-sm leading-relaxed text-foreground/90">
                          {briefText}
                        </p>
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ul>
            <NfaInline className="mt-3" />
          </>
        )}
      </section>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <AppNav />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10"
      >
        {children}
      </main>
      <NfaFooter />
    </div>
  );
}

function Stat({
  label,
  value,
  className,
  mono,
}: {
  label: string;
  value: string;
  className?: string;
  mono?: boolean;
}) {
  return (
    <div className="min-w-0">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p
        className={`mt-0.5 truncate text-lg font-medium sm:text-xl ${mono ? "font-mono" : ""} ${className ?? ""}`}
      >
        {value}
      </p>
    </div>
  );
}
