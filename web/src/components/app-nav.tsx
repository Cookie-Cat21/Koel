"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { KoelWordmark } from "@/components/brand/koel-brand";
import { CommandPalette } from "@/components/command-palette";
import { NavSession } from "@/components/nav-session";
import { Button } from "@/components/ui/button";

type NavLink = { href: string; label: string };

/**
 * Primary nav — Scenarios stays off primary until Phase 3 AI is live.
 * Daily surface stays in the bar; research/ops fold under More.
 */
const primaryLinks = [
  { href: "/overview", label: "Overview" },
  { href: "/market", label: "Browse" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/activity", label: "Activity" },
  { href: "/alerts", label: "Alerts" },
] as const satisfies readonly NavLink[];

/** Research / ops — folded under More so the bar stays readable. */
const moreLinks = [
  { href: "/events", label: "Events" },
  { href: "/signals", label: "Signals" },
  { href: "/appetite", label: "Appetite" },
  { href: "/context", label: "Context" },
  { href: "/people", label: "People" },
  { href: "/graph", label: "Graph" },
  { href: "/dividends", label: "Dividends" },
  { href: "/alerts/history", label: "History" },
  { href: "/settings", label: "Settings" },
  { href: "/health", label: "Health" },
  { href: "/help", label: "Help" },
] as const satisfies readonly NavLink[];

/** Full set for active-path resolution (primary + more). */
const links = [...primaryLinks, ...moreLinks] as const;

/**
 * Cap nav path strings — multi-MB forged ``active`` / pathname used to burn
 * CPU in prefix matching before any href could win.
 */
export const MAX_NAV_PATH_LENGTH = 512;

/**
 * Resolve which nav href is active. Prefers the explicit `active` prop, else
 * the current pathname. Longest prefix wins so `/alerts/history` highlights
 * History (not Alerts), and `/scenarios` exact-matches Scenarios.
 */
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

function linkClass(isActive: boolean, dense = false): string {
  const base = dense
    ? "block rounded-sm px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
    : "rounded-sm focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none";
  return isActive
    ? `${base} font-medium text-foreground`
    : `${base} text-muted-foreground transition-colors hover:text-foreground`;
}

function NavMoreMenu({
  activeHref,
  onNavigate,
}: {
  activeHref: string | undefined;
  onNavigate?: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const moreActive = moreLinks.some((l) => l.href === activeHref);

  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-expanded={menuOpen}
        aria-controls={menuId}
        aria-haspopup="menu"
        onClick={() => setMenuOpen((v) => !v)}
        className={
          moreActive || menuOpen
            ? "rounded-sm font-medium text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
            : "rounded-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
        }
      >
        More
        <span className="ml-1 text-xs text-muted-foreground" aria-hidden>
          ▾
        </span>
      </button>
      <div
        id={menuId}
        role="menu"
        hidden={!menuOpen}
        className="absolute top-full left-0 z-50 mt-2 min-w-[11rem] rounded-md border border-border bg-background py-1 shadow-sm"
      >
        {moreLinks.map((link) => {
          const isActive = activeHref === link.href;
          return (
            <Link
              key={link.href}
              href={link.href}
              role="menuitem"
              aria-current={isActive ? "page" : undefined}
              tabIndex={menuOpen ? undefined : -1}
              className={linkClass(isActive, true)}
              onClick={() => {
                setMenuOpen(false);
                onNavigate?.();
              }}
            >
              {link.label}
            </Link>
          );
        })}
      </div>
    </div>
  );
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
          aria-label="koel home"
          className="shrink-0 rounded-sm focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
          onClick={() => setOpen(false)}
        >
          <KoelWordmark
            size="sm"
            priority
            className="motion-safe:transition-opacity motion-safe:hover:opacity-80"
          />
        </Link>

        {/* Desktop / tablet — primary destinations + More */}
        <nav
          className="hidden min-w-0 items-center gap-x-4 text-sm md:flex lg:gap-x-5"
          aria-label="Primary"
        >
          {primaryLinks.map((link) => {
            const isActive = activeHref === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={isActive ? "page" : undefined}
                className={linkClass(isActive)}
              >
                {link.label}
              </Link>
            );
          })}
          <NavMoreMenu activeHref={activeHref} />
        </nav>

        <div className="flex shrink-0 items-center gap-2">
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
            <span className="ml-1 hidden text-xs text-muted-foreground lg:inline">
              Ctrl K
            </span>
          </Button>
          <NavSession />

          {/* Mobile / narrow menu toggle */}
          <button
            type="button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-md text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none md:hidden"
            aria-expanded={open}
            aria-controls="koel-mobile-nav"
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
        id="koel-mobile-nav"
        className="border-t border-border/60 px-4 py-2 md:hidden"
        hidden={!open}
        aria-label="Mobile"
      >
        <p className="px-0 pt-1 pb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Main
        </p>
        <ul className="flex flex-col">
          {primaryLinks.map((link) => {
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
        <p className="mt-2 border-t border-border/60 px-0 pt-3 pb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
          More
        </p>
        <ul className="flex flex-col">
          {moreLinks.map((link) => {
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
