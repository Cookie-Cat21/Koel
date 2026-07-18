import Link from "next/link";
import { Suspense } from "react";
import { Info } from "lucide-react";

import { AppNav } from "@/components/app-nav";
import { PeopleGraphClient } from "@/components/company-graph/people-client";
import { AlertBanner } from "@/components/kit/alert-banner";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { queryPeopleGraph } from "@/lib/api/people-graph";
import { requirePageSession } from "@/lib/auth/page-session";
import { getPool } from "@/lib/db";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "People · Chime",
  description:
    "CSE directors ranked by linked company market value × role. Open a dossier for seats and co-director network. Not personal net worth.",
};

export default async function PeoplePage() {
  await requirePageSession();

  let people: Awaited<ReturnType<typeof queryPeopleGraph>>["people"] = [];
  let loadError = false;
  try {
    const graph = await queryPeopleGraph(getPool(), {
      limit: 1500,
      minConfidence: "high",
      leadershipOnly: false,
    });
    people = graph.people;
  } catch {
    loadError = true;
  }

  return (
    <div className="min-h-screen bg-background">
      <AppNav active="/people" />
      <main className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8 sm:px-6">
        <PageHeader
          eyebrow="Chime · Research"
          title="People"
          description="Official CSE boards (companyProfile) ranked by linked market value × role. Open a dossier for seats, network, and issuer filings. Not personal net worth — and not auto-updated; run directors-backfill to refresh."
          action={
            <div className="flex flex-wrap gap-2">
              <Button asChild variant="outline" size="sm">
                <Link href="/graph">Ownership</Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link href="/market">Browse</Link>
              </Button>
            </div>
          }
        />
        <NfaInline />
        <AlertBanner
          tone="info"
          icon={Info}
          title="Boards are a snapshot — not auto-updated"
          description="People ranks use the last directors-backfill from CSE companyProfile. Re-run backfill to refresh seats; linked volume/turnover come from the latest poller quotes on those issuers."
        />
        {loadError ? (
          <p className="text-sm text-muted-foreground">
            People map is temporarily unavailable.
          </p>
        ) : (
          <Suspense
            fallback={
              <p className="text-sm text-muted-foreground">Loading people…</p>
            }
          >
            <PeopleGraphClient people={people} />
          </Suspense>
        )}
        <NfaFooter />
      </main>
    </div>
  );
}
