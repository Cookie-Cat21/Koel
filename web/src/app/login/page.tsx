import Link from "next/link";
import { redirect } from "next/navigation";
import { cookies } from "next/headers";

import { KoelLockup } from "@/components/brand/koel-brand";
import { LoginForm } from "@/components/login-form";
import { HeroGridBackdrop } from "@/components/marketing/hero-grid-backdrop";
import { NfaFooter } from "@/components/nfa-footer";
import { NfaInline } from "@/components/nfa-inline";
import {
  getDashAuthConfig,
  publicDemoAllowlist,
  SESSION_COOKIE,
} from "@/lib/auth/config";
import { verifySessionToken } from "@/lib/auth/session";

export const metadata = {
  title: "Sign in · koel",
  description: "Sign in to the koel CSE dashboard — Telegram alerts on top.",
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ expired?: string | string[] }>;
}) {
  const cfg = getDashAuthConfig();
  const jar = await cookies();
  const raw = jar.get(SESSION_COOKIE)?.value;
  const session =
    raw && cfg.sessionSecret
      ? verifySessionToken(raw, cfg.sessionSecret)
      : null;
  if (session) {
    redirect("/overview");
  }

  const sp = await searchParams;
  const expiredRaw = sp.expired;
  const expiredFlag = Array.isArray(expiredRaw) ? expiredRaw[0] : expiredRaw;
  const sessionExpired = expiredFlag === "1" || expiredFlag === "true";

  const allowlist = publicDemoAllowlist(cfg);
  const defaultId =
    cfg.defaultTelegramId && cfg.allowlist.has(cfg.defaultTelegramId)
      ? cfg.defaultTelegramId
      : null;
  const telegramLoginEnabled = process.env.DASH_TELEGRAM_LOGIN === "1";

  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="chime-atmosphere relative flex min-h-full flex-1 flex-col"
    >
      <HeroGridBackdrop className="opacity-70" />
      <div className="relative mx-auto flex w-full max-w-lg flex-1 flex-col justify-center px-6 py-16 sm:py-20">
        <div className="chime-rise">
          <Link
            href="/"
            className="inline-flex motion-safe:transition-opacity motion-safe:hover:opacity-80"
            aria-label="koel home"
          >
            <KoelLockup
              size="hero"
              priority
              className="[&_img:last-child]:h-14 [&_img:last-child]:sm:h-16 [&_img:last-child]:md:h-[4.5rem] [&_img:first-child]:h-14 [&_img:first-child]:sm:h-16 [&_img:first-child]:md:h-[4.5rem]"
            />
          </Link>
        </div>

        <h1 className="chime-rise chime-rise-delay-1 mt-10 max-w-md font-display text-3xl font-semibold tracking-tight text-foreground sm:text-4xl sm:leading-[1.1]">
          CSE alerts on Telegram.
          <span className="mt-2 block text-muted-foreground">
            Dash when you need to manage.
          </span>
        </h1>

        {sessionExpired ? (
          <p
            role="status"
            data-testid="session-expired-notice"
            className="chime-rise chime-rise-delay-1 mt-5 text-sm text-foreground"
          >
            Your session expired. Sign in again to open the dashboard.
          </p>
        ) : null}

        <p
          id="login-explainer"
          className="chime-rise chime-rise-delay-2 mt-5 max-w-md text-base leading-relaxed text-muted-foreground"
        >
          Browse the market, watch symbols, and manage rules here. Telegram is
          the cherry — you still get the ping when a rule fires with the tab
          closed.
        </p>

        <ul
          className="chime-rise chime-rise-delay-2 mt-6 max-w-md space-y-2.5 text-sm text-muted-foreground"
          aria-labelledby="login-explainer"
        >
          <li className="flex gap-2.5">
            <span
              aria-hidden
              className="mt-2 size-1 shrink-0 rounded-full bg-foreground/55"
            />
            <span>Overview of movers, watchlist, and armed rules</span>
          </li>
          <li className="flex gap-2.5">
            <span
              aria-hidden
              className="mt-2 size-1 shrink-0 rounded-full bg-foreground/55"
            />
            <span>Price, move, and disclosure alerts</span>
          </li>
          <li className="flex gap-2.5">
            <span
              aria-hidden
              className="mt-2 size-1 shrink-0 rounded-full bg-foreground/55"
            />
            <span>Push on Telegram when something matches</span>
          </li>
        </ul>

        <NfaInline className="chime-rise chime-rise-delay-2 mt-5" />

        <div className="chime-rise chime-rise-delay-3 mt-10 max-w-sm rounded-xl border border-border/70 bg-background/70 p-5 shadow-sm backdrop-blur-sm sm:p-6">
          <LoginForm
            allowlist={allowlist}
            defaultTelegramId={defaultId}
            demoEnabled={cfg.demoAuthEnabled}
          />
          {telegramLoginEnabled ? (
            <p
              aria-disabled="true"
              className="mt-4 rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm text-muted-foreground"
            >
              Telegram Login Widget when{" "}
              <code className="font-mono text-xs">DASH_TELEGRAM_LOGIN=1</code>
            </p>
          ) : null}
        </div>
      </div>
      <div className="relative">
        <NfaFooter />
      </div>
    </main>
  );
}
