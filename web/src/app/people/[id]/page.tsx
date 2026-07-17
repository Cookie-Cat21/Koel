import Link from "next/link";
import { notFound } from "next/navigation";

import { AppNav } from "@/components/app-nav";
import { NfaFooter } from "@/components/nfa-footer";
import { PersonDossierView } from "@/components/people/person-dossier";
import { Button } from "@/components/ui/button";
import { queryPersonDossier } from "@/lib/api/person-dossier";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { requirePageSession } from "@/lib/auth/page-session";
import { getPool } from "@/lib/db";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Props) {
  const { id: raw } = await params;
  const id = toSafePositiveInt(raw);
  if (id == null) return { title: "Person · Chime" };
  try {
    const dossier = await queryPersonDossier(getPool(), id);
    if (!dossier) return { title: "Person · Chime" };
    return {
      title: `${dossier.name} · People · Chime`,
      description: `CSE board seats and co-director network for ${dossier.name}. Research proxy — not personal net worth.`,
    };
  } catch {
    return { title: "Person · Chime" };
  }
}

export default async function PersonDossierPage({ params }: Props) {
  await requirePageSession();
  const { id: raw } = await params;
  const id = toSafePositiveInt(raw);
  if (id == null) notFound();

  let dossier: Awaited<ReturnType<typeof queryPersonDossier>> = null;
  try {
    dossier = await queryPersonDossier(getPool(), id);
  } catch {
    dossier = null;
  }
  if (!dossier) notFound();

  return (
    <div className="min-h-screen bg-background">
      <AppNav active="/people" />
      <main className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8 sm:px-6">
        <nav
          aria-label="Breadcrumb"
          className="flex flex-wrap items-center gap-2 text-[12px] text-muted-foreground"
        >
          <Link href="/people" className="hover:text-foreground hover:underline">
            People
          </Link>
          <span aria-hidden>/</span>
          <span className="truncate text-foreground">{dossier.name}</span>
        </nav>
        <PersonDossierView dossier={dossier} />
        <div className="flex flex-wrap gap-2 border-t border-border/60 pt-4">
          <Button asChild variant="outline" size="sm">
            <Link href="/people">← People map</Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link href="/graph">Ownership graph</Link>
          </Button>
        </div>
        <NfaFooter />
      </main>
    </div>
  );
}
