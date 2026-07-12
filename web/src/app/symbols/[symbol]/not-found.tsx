import Link from "next/link";

import { AppNav } from "@/components/app-nav";
import { EmptyState } from "@/components/empty-state";
import { NfaFooter } from "@/components/nfa-footer";
import { Button } from "@/components/ui/button";

export default function SymbolNotFound() {
  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <AppNav />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10"
      >
        <EmptyState
          title="Symbol not found"
          description={
            <>
              Chime only opens symbol pages for CSE tickers the poller has
              already seen.{" "}
              <Link
                href="/market"
                className="rounded-sm underline underline-offset-4 focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                Browse
              </Link>{" "}
              the market list to pick a known symbol, add it to your watchlist,
              or use{" "}
              <code className="font-mono text-xs">/watch SYMBOL</code> in
              Telegram — Chime keeps watching in the background. Not financial
              advice.
            </>
          }
          action={
            <div className="flex flex-wrap gap-2">
              <Button asChild>
                <Link href="/market">Browse</Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/watchlist">Go to watchlist</Link>
              </Button>
            </div>
          }
        />
      </main>
      <NfaFooter />
    </div>
  );
}
