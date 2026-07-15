import Link from "next/link";

import { NFA_FOOTER } from "@/lib/nfa";
import { cn } from "@/lib/utils";

/** HyperUI simple footer — NFA first, thin legal/nav links. */
export function SiteFooter({
  telegramHref,
  className,
}: {
  telegramHref?: string | null;
  className?: string;
}) {
  return (
    <footer
      className={cn(
        "mt-auto border-t border-border/60 px-4 py-8 sm:px-6",
        className,
      )}
    >
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
        <p className="text-center text-xs leading-relaxed text-muted-foreground">
          {NFA_FOOTER}
        </p>
        <nav
          aria-label="Marketing footer"
          className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs text-muted-foreground"
        >
          <Link
            href="/login"
            className="underline-offset-4 hover:text-foreground hover:underline"
          >
            Sign in
          </Link>
          <Link
            href="/pricing"
            className="underline-offset-4 hover:text-foreground hover:underline"
          >
            Pricing
          </Link>
          {telegramHref ? (
            <a
              href={telegramHref}
              target="_blank"
              rel="noopener noreferrer"
              className="underline-offset-4 hover:text-foreground hover:underline"
            >
              Telegram
            </a>
          ) : null}
          <Link
            href="/legal/privacy"
            className="underline-offset-4 hover:text-foreground hover:underline"
          >
            Privacy
          </Link>
          <Link
            href="/legal/terms"
            className="underline-offset-4 hover:text-foreground hover:underline"
          >
            Terms
          </Link>
        </nav>
      </div>
    </footer>
  );
}
