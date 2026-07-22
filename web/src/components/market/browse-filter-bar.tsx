import Link from "next/link";

/**
 * HyperUI-inspired light filter density for Browse — active pills + toggles.
 * Server component: all links are GET navigation (no client state).
 */
export function BrowseFilterBar({
  q,
  sector,
  hasEps,
  browseHref,
}: {
  q: string;
  sector: string;
  hasEps: boolean;
  browseHref: (
    q: string,
    page: number,
    opts?: { sector?: string; hasEps?: boolean },
  ) => string;
}) {
  const browseOnly = Boolean(q || sector || hasEps);

  return (
    <div
      className="flex flex-wrap items-center gap-2"
      aria-label="Light browse filters"
    >
      <Link
        href={browseHref(q, 1, {
          sector: sector || undefined,
          hasEps: !hasEps,
        })}
        className={`rounded-md border px-2.5 py-1 text-xs transition-colors focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none ${
          hasEps
            ? "border-foreground/30 bg-foreground/5 font-medium text-foreground"
            : "border-border text-muted-foreground hover:text-foreground"
        }`}
      >
        Has EPS
      </Link>

      {q ? (
        <Link
          href={browseHref("", 1, {
            sector: sector || undefined,
            hasEps,
          })}
          className="inline-flex max-w-[14rem] items-center gap-1.5 truncate rounded-md border border-foreground/30 bg-foreground/5 px-2.5 py-1 text-xs text-foreground transition-colors hover:bg-foreground/10 focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
          title={`Clear search: ${q}`}
        >
          <span className="truncate">Search: {q}</span>
          <span aria-hidden="true" className="text-muted-foreground">
            ×
          </span>
          <span className="sr-only">Clear search</span>
        </Link>
      ) : null}

      {sector ? (
        <Link
          href={browseHref(q, 1, { hasEps })}
          className="inline-flex max-w-[16rem] items-center gap-1.5 truncate rounded-md border border-foreground/30 bg-foreground/5 px-2.5 py-1 text-xs text-foreground transition-colors hover:bg-foreground/10 focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
          title={`Clear sector filter: ${sector}`}
        >
          <span className="truncate">Sector: {sector}</span>
          <span aria-hidden="true" className="text-muted-foreground">
            ×
          </span>
          <span className="sr-only">Clear sector filter</span>
        </Link>
      ) : null}

      {browseOnly ? (
        <Link
          href="/market"
          className="rounded-md border border-border px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          Clear all
        </Link>
      ) : null}
    </div>
  );
}
