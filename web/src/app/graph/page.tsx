import Link from "next/link";
import { Suspense } from "react";

import { AppNav } from "@/components/app-nav";
import { CompanyGraphClient } from "@/components/company-graph/graph-client";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { queryCompanyGraph } from "@/lib/api/graph";
import { normalizeSymbol } from "@/lib/api/symbol";
import { requirePageSession } from "@/lib/auth/page-session";
import { getPool } from "@/lib/db";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Ownership map · koel",
  description:
    "Company relationships and equity from public CSE annual filings. Research only — not advice.",
};

export default async function GraphPage({
  searchParams,
}: {
  searchParams: Promise<{ symbol?: string; min_confidence?: string }>;
}) {
  await requirePageSession();
  const sp = await searchParams;
  const focus = normalizeSymbol(sp.symbol);

  let nodes: Awaited<ReturnType<typeof queryCompanyGraph>>["nodes"] = [];
  let edges: Awaited<ReturnType<typeof queryCompanyGraph>>["edges"] = [];
  let loadError = false;

  try {
    const pool = getPool();
    // Medium+ only — CSE has no ownership JSON; low/group_mention is noise.
    const graph = await queryCompanyGraph(pool, {
      minConfidence: "medium",
      limit: 300,
      focusSymbol: null,
      includeIsolates: true,
    });
    nodes = graph.nodes;
    edges = graph.edges;
  } catch {
    loadError = true;
  }

  return (
    <div className="min-h-screen bg-background">
      <AppNav active="/graph" />
      <main className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-8 sm:px-6">
        <PageHeader
          eyebrow="Research"
          title="Ownership map"
          description="Subsidiaries and associates parsed from public CSE annual-report PDFs — CSE has no ownership API. Research map, not a complete register."
          action={
            <div className="flex flex-wrap gap-2">
              <Button asChild variant="secondary" size="sm">
                <Link href="/people">People</Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link href="/market">Browse market</Link>
              </Button>
            </div>
          }
        />
        <NfaInline />
        {loadError ? (
          <p className="text-sm text-muted-foreground">
            Graph data is temporarily unavailable.
          </p>
        ) : (
          <Suspense
            fallback={
              <p className="text-sm text-muted-foreground">Loading map…</p>
            }
          >
            <CompanyGraphClient
              nodes={nodes}
              edges={edges}
              initialFocus={focus}
            />
          </Suspense>
        )}
        <NfaFooter />
      </main>
    </div>
  );
}
