import Link from "next/link";

import { formatTs } from "@/lib/format";
import { cn } from "@/lib/utils";

export type DisclosureTimelineItem = {
  id: string | number;
  title: string;
  published_at: string | null;
  url: string | null;
  category?: string | null;
  brief?: string | null;
  brief_status?: string | null;
};

/**
 * HyperUI-style vertical timeline for CSE disclosures.
 * Time-ordered filings only — not a news terminal.
 */
export function DisclosureTimeline({
  items,
  className,
  empty = "No disclosures yet for this symbol.",
}: {
  items: DisclosureTimelineItem[];
  className?: string;
  empty?: string;
}) {
  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground">{empty}</p>;
  }

  return (
    <ol
      className={cn("relative space-y-0 border-l border-border pl-4", className)}
      aria-labelledby="disclosures-heading"
    >
      {items.map((item) => {
        const titleNode =
          item.url && /^https?:\/\//i.test(item.url) ? (
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium underline-offset-4 hover:underline"
            >
              {item.title}
              <span className="sr-only"> (opens in new tab)</span>
            </a>
          ) : (
            <span className="text-sm font-medium">{item.title}</span>
          );
        const briefId = `disclosure-brief-${item.id}`;
        const showBrief =
          item.brief_status === "ready" && Boolean(item.brief?.trim());
        return (
          <li key={item.id} className="relative pb-5 last:pb-0">
            <span
              className="absolute top-1.5 -left-[1.28rem] size-2.5 rounded-full border-2 border-background bg-foreground/60"
              aria-hidden
            />
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
              <time className="text-xs text-muted-foreground">
                {formatTs(item.published_at)}
              </time>
              {item.category ? (
                <span className="text-xs text-muted-foreground">
                  · {item.category}
                </span>
              ) : null}
              {item.brief_status === "processing" ? (
                <span className="text-xs text-muted-foreground">
                  · processing
                </span>
              ) : null}
            </div>
            <div className="mt-0.5">{titleNode}</div>
            {showBrief ? (
              <div
                role="group"
                aria-labelledby={briefId}
                className="mt-2 rounded-md border border-border/60 bg-muted/30 px-3 py-2"
              >
                <p
                  id={briefId}
                  className="text-xs font-medium text-muted-foreground"
                >
                  Filing brief
                </p>
                <p className="mt-1 line-clamp-4 text-xs text-foreground/90">
                  {item.brief}
                </p>
              </div>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

/** Optional filter chip — selected state via visual + aria-current. */
export function DisclosureCategoryHint({
  href,
  label,
  selected = false,
}: {
  href: string;
  label: string;
  selected?: boolean;
}) {
  return (
    <Link
      href={href}
      aria-current={selected ? "true" : undefined}
      className={
        selected
          ? "inline-flex min-h-9 items-center rounded-md bg-foreground px-3 text-xs font-medium text-background"
          : "inline-flex min-h-9 items-center rounded-md border border-border/70 px-3 text-xs text-muted-foreground hover:bg-muted/40"
      }
    >
      {label}
    </Link>
  );
}
