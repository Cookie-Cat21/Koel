import Link from "next/link";

import { AppNav } from "@/components/app-nav";
import { EmptyState } from "@/components/empty-state";
import { NfaFooter } from "@/components/nfa-footer";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <AppNav />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10"
      >
        <EmptyState
          title="Page not found"
          description="That route isn’t part of the Chime dash. Head back to Overview, Browse, or your watchlist."
          action={
            <div className="flex flex-wrap gap-2">
              <Button asChild>
                <Link href="/overview">Overview</Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/market">Browse</Link>
              </Button>
              <Button asChild variant="ghost">
                <Link href="/watchlist">Watchlist</Link>
              </Button>
            </div>
          }
        />
        <NfaFooter />
      </main>
    </div>
  );
}
