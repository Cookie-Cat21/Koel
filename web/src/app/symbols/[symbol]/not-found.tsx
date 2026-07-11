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
              That ticker isn’t in Chime’s known stocks list. Add a symbol from
              your watchlist only after the poller has seen it, or use{" "}
              <code className="font-mono text-xs">/watch SYMBOL</code> in
              Telegram.
            </>
          }
          action={
            <Button asChild variant="outline">
              <Link href="/watchlist">← Back to watchlist</Link>
            </Button>
          }
        />
      </main>
      <NfaFooter />
    </div>
  );
}
