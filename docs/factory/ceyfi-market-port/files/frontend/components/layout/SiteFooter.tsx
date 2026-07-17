"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CeyfiMark } from "@/components/brand/CeyfiMark";
import { cn } from "@/lib/utils";

/** HyperUI "Simple stacked" footer pattern — adapted for CEYFI app navigation. */
const FOOTER_LINKS = [
  { href: "/wallet", label: "Wallet" },
  { href: "/market", label: "Market" },
  { href: "/loans", label: "Loans" },
  { href: "/assistant", label: "Assistant" },
  { href: "/transactions", label: "Transactions" },
  { href: "/profile", label: "Profile" },
  { href: "/status", label: "Status" },
] as const;

export function SiteFooter() {
  const pathname = usePathname();

  const isActive = (href: string) =>
    pathname === href || (href !== "/" && pathname.startsWith(href));

  return (
    <footer className="mt-auto border-t border-ceyfi-line/70 bg-ceyfi-paper dark:border-white/10 dark:bg-white/[0.03]">
      <div className="mx-auto max-w-7xl space-y-8 px-4 py-10 sm:px-6 lg:space-y-10 lg:px-8 lg:py-12">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
          <div>
            <Link href="/" className="inline-flex items-center gap-3 text-ceyfi-green">
              <span className="grid size-10 place-items-center rounded-[14px] bg-ceyfi-sprout dark:bg-ceyfi-green/15">
                <CeyfiMark className="size-5" title="" aria-hidden />
              </span>
              <span className="font-heading text-base font-bold tracking-[0.16em] text-ceyfi-ink dark:text-white">
                CEYFI
              </span>
            </Link>

            <p className="mt-4 max-w-xs text-sm leading-relaxed text-ceyfi-muted dark:text-white/55">
              AI-powered financial clarity for Sri Lankan families, borrowers, and
              business owners.
            </p>

            <p className="mt-4 text-xs text-ceyfi-muted dark:text-white/45">
              Built for clear, confident financial decisions.
            </p>
          </div>

          <div className="lg:col-span-2">
            <p className="text-sm font-medium text-ceyfi-ink dark:text-white">
              Navigate
            </p>

            <ul className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
              {FOOTER_LINKS.map((item) => {
                const active = isActive(item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "transition hover:text-ceyfi-green dark:hover:text-ceyfi-mint",
                        active
                          ? "font-semibold text-ceyfi-green dark:text-ceyfi-mint"
                          : "text-ceyfi-muted dark:text-white/55",
                      )}
                    >
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>

        <p className="text-xs text-ceyfi-faint dark:text-white/35">
          &copy; {new Date().getFullYear()} CEYFI. Demo environment — mock
          financial data only.
        </p>
      </div>
    </footer>
  );
}
