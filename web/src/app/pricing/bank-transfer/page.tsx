import Link from "next/link";

import { QuiverlyWordmark } from "@/components/brand/quiverly-brand";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import { QuiverlyFooter } from "@/components/marketing/quiverly-footer";
import { NfaInline } from "@/components/nfa-inline";
import { Button } from "@/components/ui/button";
import { telegramBotUrl } from "@/lib/marketing";

export const metadata = {
  title: "Pro bank transfer · Quiverly",
  description:
    "Pay for Quiverly Pro by bank transfer — manual admin activate. Not financial advice.",
};

const PRO_MAILTO =
  "mailto:hello@quiverly.app?subject=Quiverly%20Pro%20bank%20transfer%20%E2%80%94%20activation";

/**
 * Phase B stub — bank details + reference format before PayHere.
 * Placeholder account fields are clearly marked; ops replace before public launch.
 */
export default function BankTransferPage() {
  const botUrl = telegramBotUrl();

  return (
    <div className="chime-atmosphere flex min-h-full flex-1 flex-col">
      <MarketingNav />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-2xl flex-1 flex-col px-6 py-14"
      >
        <QuiverlyWordmark size="lg" priority />
        <p className="mt-8 text-xs font-semibold tracking-[0.18em] text-primary uppercase">
          Pro · bank transfer
        </p>
        <h1 className="mt-3 font-display text-4xl font-semibold tracking-tight sm:text-5xl">
          Pay by bank transfer
        </h1>
        <p className="mt-4 max-w-lg text-base leading-relaxed text-muted-foreground">
          Pro is activated manually after we see your transfer. No card checkout
          yet — this is the intentional Phase B path.
        </p>
        <NfaInline className="mt-4" />

        <section className="mt-10 space-y-6" aria-labelledby="transfer-steps">
          <h2 id="transfer-steps" className="sr-only">
            Transfer steps
          </h2>

          <ol className="list-decimal space-y-4 pl-5 text-sm leading-relaxed text-foreground">
            <li>
              Transfer{" "}
              <span className="font-mono tabular-nums">Rs 490</span> (monthly)
              or <span className="font-mono tabular-nums">Rs 4,900</span>{" "}
              (yearly) to the account below.
            </li>
            <li>
              Use reference{" "}
              <span className="font-mono">QV-PRO-&lt;your Telegram id&gt;</span>{" "}
              so we can match the payment (example:{" "}
              <span className="font-mono">QV-PRO-9001001</span>).
            </li>
            <li>
              Email the slip / screenshot to{" "}
              <a
                href={PRO_MAILTO}
                className="underline underline-offset-4"
              >
                hello@quiverly.app
              </a>{" "}
              with the same reference. We activate Pro on your account and reply
              when live.
            </li>
          </ol>

          <dl className="rounded-lg border border-border/70 bg-card/70 p-6 text-sm">
            <div className="grid gap-1 sm:grid-cols-[8rem_1fr]">
              <dt className="text-muted-foreground">Bank</dt>
              <dd>Commercial Bank of Ceylon (placeholder — replace before launch)</dd>
            </div>
            <div className="mt-3 grid gap-1 sm:grid-cols-[8rem_1fr]">
              <dt className="text-muted-foreground">Account name</dt>
              <dd>Quiverly (ops TBD)</dd>
            </div>
            <div className="mt-3 grid gap-1 sm:grid-cols-[8rem_1fr]">
              <dt className="text-muted-foreground">Account no.</dt>
              <dd className="font-mono tabular-nums">XXXX-XXXX-XXXX</dd>
            </div>
            <div className="mt-3 grid gap-1 sm:grid-cols-[8rem_1fr]">
              <dt className="text-muted-foreground">Branch</dt>
              <dd>TBD</dd>
            </div>
          </dl>

          <p className="text-xs text-muted-foreground">
            Status after email: awaiting admin activate. You keep Free-tier
            delivery until Pro is flipped on — we never hold a fire behind a
            paywall.
          </p>
        </section>

        <div className="mt-10 flex flex-wrap gap-3">
          <Button asChild size="lg">
            <a href={PRO_MAILTO}>Email activation request</a>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link href="/pricing">Back to pricing</Link>
          </Button>
        </div>
      </main>
      <QuiverlyFooter telegramHref={botUrl} />
    </div>
  );
}
