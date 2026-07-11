import Link from "next/link";
import { notFound } from "next/navigation";

import { AppNav } from "@/components/app-nav";
import { EmptyState } from "@/components/empty-state";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { Sparkline } from "@/components/sparkline";
import { Button } from "@/components/ui/button";
import { serverApiGet } from "@/lib/api/server-fetch";
import { normalizeSymbol } from "@/lib/api/symbol";
import { requirePageSession } from "@/lib/auth/page-session";
import { formatNumber, formatPct, formatTs } from "@/lib/format";

export const dynamic = "force-dynamic";

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
  points: { ts: string | null; price: number; change_pct: number | null }[];
};

type DisclosuresPayload = {
  items: {
    id: number;
    external_id: string;
    title: string;
    category: string | null;
    url: string;
    published_at: string | null;
    company_name: string | null;
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
            title="No price yet"
            description={
              <>
                The poller hasn’t stored a snapshot for {data.symbol}. Once
                market hours tick, the last price will show here. Not financial
                advice.
              </>
            }
            action={
              <Button asChild variant="outline" size="sm">
                <Link href="/alerts">Set an alert</Link>
              </Button>
            }
          />
        )}
        {data.last?.ts ? (
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
          ) : snaps.points.length < 2 ? (
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

      <section className="mt-8 border-t border-border/60 pt-6">
        <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
          Disclosures
        </h2>
        {discsFailed ? (
          <p className="mt-3 text-sm text-muted-foreground" role="status">
            Couldn’t load disclosures right now.
          </p>
        ) : discs.items.length === 0 ? (
          <EmptyState
            className="mt-4"
            title="No disclosures yet"
            description={
              <>
                Nothing stored for {data.symbol}. New CSE announcements the
                poller sees will list here with a link to the source.
              </>
            }
            action={
              <Button asChild variant="outline" size="sm">
                <Link href="/alerts">Alert on disclosures</Link>
              </Button>
            }
          />
        ) : (
          <ul className="mt-4 divide-y divide-border/60">
            {discs.items.map((item) => (
              <li key={item.id} className="py-3 first:pt-0">
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block rounded-sm text-sm font-medium text-foreground underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                >
                  {item.title}
                </a>
                <p className="mt-1 text-xs text-muted-foreground">
                  {formatTs(item.published_at)}
                  {item.category ? ` · ${item.category}` : ""}
                </p>
              </li>
            ))}
          </ul>
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
