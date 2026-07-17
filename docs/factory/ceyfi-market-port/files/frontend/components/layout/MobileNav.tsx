"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, useReducedMotion } from "motion/react";
import {
  Activity,
  ArrowUpDown,
  BriefcaseBusiness,
  CreditCard,
  FlaskConical,
  LayoutDashboard,
  Lightbulb,
  LineChart,
  MoreHorizontal,
  Sparkles,
  User,
  Wallet,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";

const MOBILE_PRIMARY = [
  { href: "/wallet", label: "Wallet", icon: Wallet },
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/decisions", label: "Decide", icon: Zap },
  { href: "/assistant", label: "AI", icon: Sparkles },
];

const MOBILE_MORE = [
  { href: "/market", label: "Market", icon: LineChart },
  { href: "/transactions", label: "Activity", icon: ArrowUpDown },
  { href: "/loans", label: "Loans", icon: CreditCard },
  { href: "/business", label: "Business", icon: BriefcaseBusiness },
  { href: "/intelligence", label: "Intel", icon: Lightbulb },
  { href: "/scenarios", label: "Scenarios", icon: FlaskConical },
  { href: "/profile", label: "Profile", icon: User },
  { href: "/metrics", label: "Metrics", icon: Activity },
];

export function MobileNav() {
  const pathname = usePathname();
  const reduceMotion = useReducedMotion();
  const { user } = useAuth();

  const isActive = (href: string) =>
    pathname === href || (href !== "/" && pathname.startsWith(href));

  const mobileMore = MOBILE_MORE.filter(
    (item) => item.href !== "/business" || user?.persona === "sme"
  );
  const moreActive = mobileMore.some((item) => isActive(item.href));

  return (
    <nav
      aria-label="Mobile navigation"
      className="fixed inset-x-3 bottom-3 z-30 flex rounded-[22px] border border-border/80 bg-card/92 p-1.5 shadow-[0_16px_44px_rgba(5,46,22,0.12)] backdrop-blur-xl dark:bg-card/88 dark:shadow-[0_16px_44px_rgba(0,0,0,0.45)] md:hidden"
    >
      {MOBILE_PRIMARY.map((item) => {
        const active = isActive(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "relative flex min-h-11 min-w-0 flex-1 flex-col items-center justify-center gap-1 rounded-[16px] py-2 text-[10px] font-medium transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30",
              active
                ? "text-primary"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {active && !reduceMotion ? (
              <motion.span
                layoutId="mobile-nav-pill"
                className="absolute inset-0 rounded-[16px] bg-primary/10 dark:bg-primary/15"
                transition={{ type: "spring", stiffness: 520, damping: 34 }}
              />
            ) : active ? (
              <span className="absolute inset-0 rounded-[16px] bg-primary/10 dark:bg-primary/15" />
            ) : null}
            <item.icon
              className="relative z-10 h-[18px] w-[18px]"
              strokeWidth={active ? 2.2 : 1.8}
            />
            <span className="relative z-10 truncate">{item.label}</span>
          </Link>
        );
      })}

      <Sheet>
        <SheetTrigger
          render={
            <Button
              variant="ghost"
              className={cn(
                "relative flex h-auto min-h-11 min-w-0 flex-1 flex-col items-center justify-center gap-1 rounded-[16px] py-2 text-[10px] font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30",
                moreActive ? "text-primary" : "text-muted-foreground",
              )}
            />
          }
        >
          {moreActive && !reduceMotion ? (
            <motion.span
              layoutId="mobile-nav-pill"
              className="absolute inset-0 rounded-[16px] bg-primary/10 dark:bg-primary/15"
              transition={{ type: "spring", stiffness: 520, damping: 34 }}
            />
          ) : moreActive ? (
            <span className="absolute inset-0 rounded-[16px] bg-primary/10 dark:bg-primary/15" />
          ) : null}
          <MoreHorizontal className="relative z-10 h-[18px] w-[18px]" />
          <span className="relative z-10">More</span>
        </SheetTrigger>
        <SheetContent side="bottom" className="rounded-t-[22px]">
          <SheetHeader>
            <SheetTitle>More pages</SheetTitle>
          </SheetHeader>
          <div className="grid grid-cols-3 gap-3 px-4 pb-6">
            {mobileMore.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "interactive-card flex flex-col items-center gap-2 rounded-xl border p-4 text-center text-xs font-medium",
                  isActive(item.href)
                    ? "border-primary/30 bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:text-foreground",
                )}
              >
                <item.icon className="h-5 w-5" />
                {item.label}
              </Link>
            ))}
          </div>
        </SheetContent>
      </Sheet>
    </nav>
  );
}
