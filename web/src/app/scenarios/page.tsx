import { AppNav } from "@/components/app-nav";
import { EmptyState } from "@/components/empty-state";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { requirePageSession } from "@/lib/auth/page-session";
import { scenariosEnabled } from "@/lib/scenarios";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Scenarios · koel",
  description:
    "Optional on-demand scenario reactions from public CSE filings — stub only.",
};

/**
 * Phase 3 dash stub: coming soon while AI_SCENARIOS_ENABLED≠1.
 * Even when opted in, no LLM runs are wired — informational fence only.
 */
export default async function ScenariosPage() {
  await requirePageSession();

  const enabled = scenariosEnabled();

  return (
    <div className="flex min-h-full flex-1 flex-col bg-background">
      <AppNav active="/scenarios" />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10"
      >
        <h1 className="font-display text-3xl font-semibold tracking-tight">
          Scenarios
        </h1>
        <p className="mt-2 max-w-lg text-sm text-muted-foreground">
          Optional on-demand simulated reactions from public filings. Not a
          trading terminal — alerts stay on Telegram.
        </p>

        <NfaInline className="mt-3" />

        <Alert className="mt-6">
          <AlertTitle>Phase 3 stub</AlertTitle>
          <AlertDescription>
            Not in primary nav yet. Deep-link only — no AgentChat, no personas,
            no model calls from the dash.
          </AlertDescription>
        </Alert>

        {enabled ? (
          <EmptyState
            title="Scenarios opted in — runs not wired"
            description={
              <>
                <code className="font-mono text-xs">AI_SCENARIOS_ENABLED=1</code>{" "}
                is set, but koel has no LLM scenario runner yet. This page stays
                a thin stub: no personas, no queued runs, no model calls. Simulated
                reactions from public info only — never advice.
              </>
            }
          />
        ) : (
          <EmptyState
            title="Coming soon"
            description={
              <>
                Scenario AI is disabled. Set{" "}
                <code className="font-mono text-xs">AI_SCENARIOS_ENABLED=1</code>{" "}
                to opt into the Phase 3 fence when ready. Until then this surface
                stays off — no LLM calls, no buy/sell language, not financial
                advice.
              </>
            }
          />
        )}
      </main>
      <NfaFooter />
    </div>
  );
}
