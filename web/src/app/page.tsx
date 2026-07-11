import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { NfaFooter } from "@/components/nfa-footer";
import { Button } from "@/components/ui/button";
import { getDashAuthConfig, SESSION_COOKIE } from "@/lib/auth/config";
import { verifySessionToken } from "@/lib/auth/session";

/**
 * Brand entry. Signed-in users land on watchlist (DASH_IA sitemap).
 * Unauthenticated keep the hero; CTA → /login.
 */
export default async function HomePage() {
  const cfg = getDashAuthConfig();
  const jar = await cookies();
  const raw = jar.get(SESSION_COOKIE)?.value;
  const session =
    raw && cfg.sessionSecret
      ? verifySessionToken(raw, cfg.sessionSecret)
      : null;

  if (session) {
    redirect("/watchlist");
  }

  return (
    <main id="main-content" tabIndex={-1} className="chime-atmosphere flex min-h-full flex-1 flex-col">
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center px-6 py-16 sm:py-24">
        <p className="chime-rise font-display text-6xl font-semibold tracking-tight text-foreground sm:text-7xl md:text-8xl">
          Chime
        </p>
        <h1 className="chime-rise chime-rise-delay-1 mt-6 max-w-xl text-2xl font-medium leading-snug text-foreground sm:text-3xl">
          CSE alerts that reach you on Telegram
        </h1>
        <p className="chime-rise chime-rise-delay-2 mt-4 max-w-md text-base text-muted-foreground sm:text-lg">
          Set price and disclosure watches here; pushes fire when conditions
          match — no terminal left open.
        </p>
        <div className="chime-rise chime-rise-delay-3 mt-10 flex flex-wrap items-center gap-3">
          <Button
            asChild
            size="lg"
            className="min-w-36 motion-safe:transition-transform motion-safe:hover:-translate-y-0.5"
          >
            <Link href="/login">Sign in</Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link href="/login">Manage alerts</Link>
          </Button>
        </div>
      </div>
      <NfaFooter />
    </main>
  );
}
