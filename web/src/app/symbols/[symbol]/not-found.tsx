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
              already seen. Add it to your watchlist first, or use{" "}
              <code className="font-mono text-xs">/watch SYMBOL</code> in
              Telegram, and Chime will keep watching in the background. Not
              financial advice.
            </>
          }
          action={
            <Button asChild variant="outline">
              <Link href="/watchlist">Go to watchlist</Link>
            </Button>
          }
        />
      </main>
      <NfaFooter />
    </div>
  );
}
