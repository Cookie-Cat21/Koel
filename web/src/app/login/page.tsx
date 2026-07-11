import Link from "next/link";
import { redirect } from "next/navigation";
import { cookies } from "next/headers";

import { LoginForm } from "@/components/login-form";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import {
  getDashAuthConfig,
  publicDemoAllowlist,
  SESSION_COOKIE,
} from "@/lib/auth/config";
import { verifySessionToken } from "@/lib/auth/session";

export const metadata = {
  title: "Sign in · Chime",
  description: "Sign in to manage Chime CSE alerts that push to Telegram.",
};

export default async function LoginPage() {
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

  const allowlist = publicDemoAllowlist(cfg);
  const defaultId =
    cfg.defaultTelegramId && cfg.allowlist.has(cfg.defaultTelegramId)
      ? cfg.defaultTelegramId
      : null;

  return (
    <main id="main-content" tabIndex={-1} className="chime-atmosphere flex min-h-full flex-1 flex-col">
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-16">
        <p className="chime-rise font-display text-5xl font-semibold tracking-tight text-foreground sm:text-6xl">
          <Link href="/" className="transition-opacity hover:opacity-80">
            Chime
          </Link>
        </p>
        <h1 className="chime-rise chime-rise-delay-1 mt-5 text-xl font-medium text-foreground sm:text-2xl">
          CSE alerts, Telegram first
        </h1>
        <p className="chime-rise chime-rise-delay-2 mt-3 text-sm text-muted-foreground sm:text-base">
          Use this thin page to manage symbols and rules. Chime watches in the
          background and pings Telegram when a price, move, or disclosure rule
          fires.
        </p>
        <ul className="chime-rise chime-rise-delay-2 mt-4 space-y-2 text-sm text-muted-foreground">
          <li>- Price crosses above or below your threshold</li>
          <li>- Daily moves exceed your chosen percent</li>
          <li>- New company disclosures appear for watched symbols</li>
        </ul>
        <NfaInline className="chime-rise chime-rise-delay-2 mt-4" />
        <div className="chime-rise chime-rise-delay-3 mt-8">
          <LoginForm
            allowlist={allowlist}
            defaultTelegramId={defaultId}
            demoEnabled={cfg.demoAuthEnabled}
          />
        </div>
      </div>
      <NfaFooter />
    </main>
  );
}
