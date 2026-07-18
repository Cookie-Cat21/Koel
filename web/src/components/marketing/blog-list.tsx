import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

import { cn } from "@/lib/utils";

export type BlogPost = {
  date: string;
  title: string;
  author: { name: string; role: string };
  href?: string;
};

/**
 * Watermelon blog-1 — header + post cards.
 * Softened inset shadows; koel tokens.
 */
export function BlogList({
  heading,
  description,
  ctaText = "All posts",
  ctaHref = "/blog",
  posts,
  className,
}: {
  heading: string;
  description: string;
  ctaText?: string;
  ctaHref?: string;
  posts: BlogPost[];
  className?: string;
}) {
  return (
    <section className={cn("w-full", className)}>
      <div className="mb-10 flex flex-col gap-6 md:mb-14 md:flex-row md:items-end md:justify-between">
        <h1 className="max-w-xl font-display text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
          {heading}
        </h1>
        <div className="flex shrink-0 flex-col items-start gap-3 md:items-end md:text-right">
          <p className="max-w-xs text-sm leading-relaxed text-muted-foreground">
            {description}
          </p>
          <Link
            href={ctaHref}
            className="group/cta inline-flex items-center gap-1.5 text-sm font-semibold text-foreground transition-colors hover:text-foreground/80"
          >
            {ctaText}
            <ArrowUpRight className="size-4 transition-transform group-hover/cta:translate-x-0.5 group-hover/cta:-translate-y-0.5" />
          </Link>
        </div>
      </div>

      {posts.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border bg-muted/30 px-6 py-10 text-sm text-muted-foreground">
          No posts yet — ops notes and CSE endpoint changes will land here.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {posts.map((post) => {
            const card = (
              <div className="group relative flex min-h-[220px] flex-col justify-between rounded-xl border border-border/70 bg-muted/40 p-6 transition-colors hover:bg-muted/60 sm:min-h-[240px]">
                <span className="text-sm font-medium text-muted-foreground/80">
                  {post.date}
                </span>
                <h2 className="mt-6 text-base font-medium leading-snug text-foreground sm:text-lg">
                  {post.title}
                </h2>
                <div className="mt-auto flex items-end justify-between pt-8">
                  <div className="leading-tight">
                    <p className="text-sm font-medium text-foreground">
                      {post.author.name}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {post.author.role}
                    </p>
                  </div>
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-md border border-border bg-background text-muted-foreground transition-colors group-hover:border-foreground/20 group-hover:text-foreground">
                    <ArrowUpRight className="size-3.5" />
                  </div>
                </div>
              </div>
            );

            if (post.href) {
              return (
                <Link
                  key={post.title}
                  href={post.href}
                  className="rounded-xl focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                >
                  {card}
                </Link>
              );
            }
            return <div key={post.title}>{card}</div>;
          })}
        </div>
      )}
    </section>
  );
}
