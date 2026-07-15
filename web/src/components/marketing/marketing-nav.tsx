"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { ChimeWordmark } from "@/components/brand/chime-brand";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Public-only chrome — not the dash AppNav. */
export function MarketingNav() {
  const pathname = usePathname();
  const onPricing = pathname === "/pricing";

  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/75 backdrop-blur-sm">
      <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Link
          href="/"
          aria-label="Chime home"
          className="rounded-sm focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          <ChimeWordmark size="sm" priority />
        </Link>
        <nav
          aria-label="Marketing"
          className="flex items-center gap-4 text-sm text-muted-foreground"
        >
          <Link
            href="/#how-it-works"
            className="hidden hover:text-foreground sm:inline"
          >
            How it works
          </Link>
          <Link
            href="/pricing"
            aria-current={onPricing ? "page" : undefined}
            className={cn(
              "hover:text-foreground",
              onPricing && "font-medium text-foreground",
            )}
          >
            Pricing
          </Link>
          <Button asChild size="sm" variant="outline">
            <Link href="/login">Sign in</Link>
          </Button>
        </nav>
      </div>
    </header>
  );
}
