import Link from "next/link";
import { Suspense } from "react";

import { AppNav } from "@/components/app-nav";
import { PeopleGraphClient } from "@/components/company-graph/people-client";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { queryPeopleGraph } from "@/lib/api/people-graph";
import { requirePageSession } from "@/lib/auth/page-session";
import { getPool } from "@/lib/db";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "People map · Chime",
  description:
    "Directors and CEOs from official CSE company profiles, sized by linked company market value. Not personal net worth. Not advice.",
};

export default async function PeopleGraphPage() {
  await requirePageSession();

  let people: Awaited<ReturnType<typeof queryPeopleGraph>>["people"] = [];
  let loadError = false;
  try {
    const pool = getPool();
    const graph = await queryPeopleGraph(pool, {
      limit: 180,
      // CSE companyProfile seats are stored as high confidence
      minConfidence: "high",
      // Full board seats (not only chair/CEO) so the map is dense
      leadershipOnly: false,
    });
    people = graph.people;
  } catch {
    loadError = true;
  }

  return (
    <div className="min-h-screen bg-background">
      <AppNav active="/graph" />
      <main className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-8 sm:px-6">
        <PageHeader
          eyebrow="Research"
          title="People map"
          description="Board lists from official CSE company profiles (cse.lk). Bubble size reflects linked company market value × role — not anyone’s personal net worth."
          action={
            <div className="flex flex-wrap gap-2">
              <Button asChild variant="outline" size="sm">
                <Link href="/graph">Companies</Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link href="/market">Browse</Link>
              </Button>
            </div>
          }
        />
        <NfaInline />
        {loadError ? (
          <p className="text-sm text-muted-foreground">
            People graph is temporarily unavailable.
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
