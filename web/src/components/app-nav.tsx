"use client";

import Link from "next/link";
import { useState } from "react";

import { NavSession } from "@/components/nav-session";

const links = [
  { href: "/watchlist", label: "Watchlist" },
  { href: "/alerts", label: "Alerts" },
  { href: "/alerts/history", label: "History" },
  { href: "/health", label: "Health" },
] as const;

export function AppNav({ active }: { active?: string }) {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/80 backdrop-blur-sm">
      <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Link
          href="/"
          className="rounded-sm font-display text-xl font-semibold tracking-tight text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
          onClick={() => setOpen(false)}
        >
          Chime
        </Link>

        {/* Desktop / tablet */}
        <nav className="hidden items-center gap-x-5 text-sm sm:flex">
          {links.map((link) => {
            const isActive = active === link.href;
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

      {open ? (
        <nav
          id="chime-mobile-nav"
          className="border-t border-border/60 px-4 py-2 sm:hidden"
        >
          <ul className="flex flex-col">
            {links.map((link) => {
              const isActive = active === link.href;
              return (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    aria-current={isActive ? "page" : undefined}
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
      ) : null}
    </header>
  );
}
