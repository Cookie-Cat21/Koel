"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { ChimeWordmark } from "@/components/brand/chime-brand";
import { CommandPalette } from "@/components/command-palette";
import { NavSession } from "@/components/nav-session";
import { Button } from "@/components/ui/button";

const links = [
  { href: "/overview", label: "Overview" },
  { href: "/market", label: "Browse" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/alerts", label: "Alerts" },
  { href: "/alerts/history", label: "History" },
  { href: "/scenarios", label: "Scenarios" },
  { href: "/settings", label: "Settings" },
  { href: "/health", label: "Health" },
] as const;

/**
 * Resolve which nav href is active. Prefers the explicit `active` prop, else
 * the current pathname. Longest prefix wins so `/alerts/history` highlights
 * History (not Alerts), and `/scenarios` exact-matches Scenarios.
 */
/**
 * Cap nav path strings — multi-MB forged ``active`` / pathname used to burn
 * CPU in prefix matching before any href could win.
 */
export const MAX_NAV_PATH_LENGTH = 512;

export function resolveActiveNavHref(
  current: string | null | undefined,
): (typeof links)[number]["href"] | undefined {
  // Fail closed — non-strings used to throw on .startsWith / .endsWith.
  if (typeof current !== "string" || !current) return undefined;
  if (current.length > MAX_NAV_PATH_LENGTH) return undefined;
  const path =
    current.length > 1 && current.endsWith("/") ? current.slice(0, -1) : current;
  let best: (typeof links)[number]["href"] | undefined;
  for (const { href } of links) {
    if (path === href || path.startsWith(`${href}/`)) {
      if (best === undefined || href.length > best.length) {
        best = href;
      }
    }
  }
  return best;
}

export function AppNav({ active }: { active?: string }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const activeHref = resolveActiveNavHref(active ?? pathname);

  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/80 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Link
          href="/"
          aria-label="Chime home"
          className="rounded-sm focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
          onClick={() => setOpen(false)}
        >
          <ChimeWordmark size="sm" className="motion-safe:transition-opacity motion-safe:hover:opacity-80" />
        </Link>

        {/* Desktop / tablet */}
        <nav className="hidden items-center gap-x-5 text-sm sm:flex">
          {links.map((link) => {
            const isActive = activeHref === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={isActive ? "page" : undefined}
                className={
                  isActive
                    ? "rounded-sm font-medium text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                    : "rounded-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                }
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              setSearchOpen(true);
              setOpen(false);
            }}
            aria-haspopup="dialog"
          >
            Search
            <span className="ml-1 hidden text-xs text-muted-foreground md:inline">
              Ctrl K
            </span>
          </Button>
          <NavSession />

          {/* Mobile menu toggle */}
          <button
            type="button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-md text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none sm:hidden"
            aria-expanded={open}
            aria-controls="chime-mobile-nav"
            aria-label={open ? "Close menu" : "Open menu"}
            onClick={() => setOpen((v) => !v)}
          >
            <span className="sr-only">{open ? "Close" : "Menu"}</span>
            <span className="flex w-5 flex-col gap-1.5" aria-hidden>
              <span
                className={`h-0.5 w-full bg-foreground motion-safe:transition-transform ${open ? "translate-y-2 rotate-45" : ""}`}
              />
              <span
                className={`h-0.5 w-full bg-foreground motion-safe:transition-opacity ${open ? "opacity-0" : ""}`}
              />
              <span
                className={`h-0.5 w-full bg-foreground motion-safe:transition-transform ${open ? "-translate-y-2 -rotate-45" : ""}`}
              />
            </span>
          </button>
        </div>
      </div>

      {/* Keep in DOM so aria-controls stays valid when the menu is closed. */}
      <nav
        id="chime-mobile-nav"
        className="border-t border-border/60 px-4 py-2 sm:hidden"
        hidden={!open}
      >
        <ul className="flex flex-col">
          {links.map((link) => {
            const isActive = activeHref === link.href;
            return (
              <li key={link.href}>
                <Link
                  href={link.href}
                  aria-current={isActive ? "page" : undefined}
                  tabIndex={open ? undefined : -1}
                  onClick={() => setOpen(false)}
                  className={`block rounded-sm py-3 text-base focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none ${
                    isActive
                      ? "font-medium text-foreground"
                      : "text-muted-foreground"
                  }`}
                >
                  {link.label}
                </Link>
              </li>
            );
          })}
        </ul>
        <div className="border-t border-border/60 py-3">
          <NavSession compact />
        </div>
      </nav>
      <CommandPalette open={searchOpen} onOpenChange={setSearchOpen} />
    </header>
  );
}
