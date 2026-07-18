"use client";

import { ChevronDown } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { QuiverlyWordmark } from "@/components/brand/quiverly-brand";
import { CommandPalette } from "@/components/command-palette";
import { NavSession } from "@/components/nav-session";
import { Button } from "@/components/ui/button";

/** Primary nav — Scenarios stays off primary until Phase 3 AI is live. */
const primaryLinks = [
  { href: "/overview", label: "Overview" },
  { href: "/market", label: "Browse" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/alerts", label: "Alerts" },
  { href: "/alerts/history", label: "History" },
  { href: "/settings", label: "Settings" },
  { href: "/health", label: "Health" },
] as const;

/** Research surfaces — secondary disclosure so alert core stays obvious. */
const researchLinks = [
  { href: "/appetite", label: "Appetite" },
  { href: "/signals", label: "Signals" },
  { href: "/people", label: "People" },
  { href: "/graph", label: "Graph" },
] as const;

const allNavLinks = [...primaryLinks, ...researchLinks] as const;

type NavHref = (typeof allNavLinks)[number]["href"];

/**
 * Resolve which nav href is active. Prefers the explicit `active` prop, else
 * the current pathname. Longest prefix wins so `/alerts/history` highlights
 * History (not Alerts), and research routes still resolve under Research.
 */
/**
 * Cap nav path strings — multi-MB forged ``active`` / pathname used to burn
 * CPU in prefix matching before any href could win.
 */
export const MAX_NAV_PATH_LENGTH = 512;

export function resolveActiveNavHref(
  current: string | null | undefined,
): NavHref | undefined {
  // Fail closed — non-strings used to throw on .startsWith / .endsWith.
  if (typeof current !== "string" || !current) return undefined;
  if (current.length > MAX_NAV_PATH_LENGTH) return undefined;
  const path =
    current.length > 1 && current.endsWith("/") ? current.slice(0, -1) : current;
  let best: NavHref | undefined;
  for (const { href } of allNavLinks) {
    if (path === href || path.startsWith(`${href}/`)) {
      if (best === undefined || href.length > best.length) {
        best = href;
      }
    }
  }
  return best;
}

function isResearchHref(href: string | undefined): boolean {
  return researchLinks.some((l) => l.href === href);
}

function navLinkClass(isActive: boolean, base = ""): string {
  return [
    base,
    "rounded-sm focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none",
    isActive
      ? "font-medium text-foreground"
      : "text-muted-foreground transition-colors hover:text-foreground",
  ]
    .filter(Boolean)
    .join(" ");
}

export function AppNav({ active }: { active?: string }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [researchOpen, setResearchOpen] = useState(false);
  const researchWrapRef = useRef<HTMLDivElement>(null);
  const researchMenuId = useId();
  const activeHref = resolveActiveNavHref(active ?? pathname);
  const researchActive = isResearchHref(activeHref);

  useEffect(() => {
    if (!researchOpen) return;
    function onPointerDown(e: MouseEvent) {
      if (
        researchWrapRef.current &&
        !researchWrapRef.current.contains(e.target as Node)
      ) {
        setResearchOpen(false);
      }
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setResearchOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [researchOpen]);

  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/80 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Link
          href="/"
          aria-label="Quiverly home"
          className="shrink-0 rounded-sm focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
          onClick={() => setOpen(false)}
        >
          <QuiverlyWordmark
            size="sm"
            priority
            className="motion-safe:transition-opacity motion-safe:hover:opacity-80"
          />
        </Link>

        {/* Desktop / tablet */}
        <nav className="hidden items-center gap-x-5 text-sm sm:flex">
          {primaryLinks.map((link) => {
            const isActive = activeHref === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={isActive ? "page" : undefined}
                className={navLinkClass(isActive)}
              >
                {link.label}
              </Link>
            );
          })}
          <div className="relative" ref={researchWrapRef}>
            <button
              type="button"
              className={navLinkClass(
                researchActive,
                "inline-flex items-center gap-1",
              )}
              aria-expanded={researchOpen}
              aria-controls={researchMenuId}
              aria-haspopup="menu"
              onClick={() => setResearchOpen((v) => !v)}
            >
              Research
              <ChevronDown
                aria-hidden
                className={`size-3.5 opacity-70 motion-safe:transition-transform ${researchOpen ? "rotate-180" : ""}`}
              />
            </button>
            {researchOpen ? (
              <ul
                id={researchMenuId}
                role="menu"
                className="absolute top-full left-0 z-50 mt-2 min-w-[10rem] rounded-md border border-border/70 bg-background py-1 shadow-sm"
              >
                {researchLinks.map((link) => {
                  const isActive = activeHref === link.href;
                  return (
                    <li key={link.href} role="none">
                      <Link
                        role="menuitem"
                        href={link.href}
                        aria-current={isActive ? "page" : undefined}
                        onClick={() => setResearchOpen(false)}
                        className={navLinkClass(
                          isActive,
                          "block px-3 py-2 text-sm",
                        )}
                      >
                        {link.label}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            ) : null}
          </div>
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
            aria-controls="quiverly-mobile-nav"
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
        id="quiverly-mobile-nav"
        className="border-t border-border/60 px-4 py-2 sm:hidden"
        hidden={!open}
      >
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
        <div className="border-t border-border/60 pt-2 pb-1">
          <p className="px-0 py-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Research
          </p>
          <ul className="flex flex-col">
            {researchLinks.map((link) => {
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
        </div>
        <div className="border-t border-border/60 py-3">
          <NavSession compact />
        </div>
      </nav>
      <CommandPalette open={searchOpen} onOpenChange={setSearchOpen} />
    </header>
  );
}
