"use client";

import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { motion, type Transition, useReducedMotion } from "motion/react";

import { cn } from "@/lib/utils";

export type FireNotification = {
  id: number | string;
  title: string;
  subtitle: string;
  time: string;
  href?: string;
};

const transition: Transition = {
  type: "spring",
  stiffness: 300,
  damping: 26,
};

/**
 * Watermelon notification-list — stacked cards, expand on hover.
 * Fed with real alert fires (not npm/build demo toasts).
 */
export function NotificationList({
  items,
  viewAllHref = "/alerts/history",
  className,
}: {
  items: FireNotification[];
  viewAllHref?: string;
  className?: string;
}) {
  const reduceMotion = useReducedMotion();
  const list = items.slice(0, 5);

  if (list.length === 0) {
    return (
      <div
        className={cn(
          "rounded-2xl border border-border bg-muted/40 p-4 text-sm text-muted-foreground",
          className,
        )}
      >
        No fires recorded yet. When a rule matches, Telegram gets the push and
        the audit trail shows up here.
      </div>
    );
  }

  const getCardVariants = (i: number) => ({
    collapsed: {
      marginTop: i === 0 ? 0 : -40,
      scaleX: 1 - i * 0.04,
    },
    expanded: {
      marginTop: i === 0 ? 0 : 4,
      scaleX: 1,
    },
  });

  return (
    <motion.div
      className={cn(
        "w-full max-w-md space-y-3 rounded-2xl border border-border bg-muted/50 p-3 shadow-sm",
        className,
      )}
      initial="collapsed"
      whileHover={reduceMotion ? undefined : "expanded"}
      animate={reduceMotion ? "expanded" : undefined}
    >
      <div>
        {list.map((notification, i) => {
          const body = (
            <div className="relative rounded-xl border border-border/60 bg-background px-4 py-2.5 shadow-sm transition-shadow duration-200 hover:shadow-md">
              <div className="flex items-center justify-between gap-2">
                <p className="truncate font-mono text-sm font-medium text-foreground">
                  {notification.title}
                </p>
              </div>
              <p className="mt-0.5 text-xs font-medium text-muted-foreground">
                <span>{notification.time}</span>
                &nbsp;·&nbsp;
                <span>{notification.subtitle}</span>
              </p>
            </div>
          );

          return (
            <motion.div
              key={notification.id}
              className="relative"
              variants={reduceMotion ? undefined : getCardVariants(i)}
              transition={transition}
              style={{ zIndex: list.length - i }}
            >
              {notification.href ? (
                <Link
                  href={notification.href}
                  className="block rounded-xl focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                >
                  {body}
                </Link>
              ) : (
                body
              )}
            </motion.div>
          );
        })}
      </div>

      <div className="flex items-center gap-2 px-1">
        <div className="flex size-5 items-center justify-center rounded-full bg-foreground text-[10px] font-medium text-background">
          {list.length}
        </div>
        <Link
          href={viewAllHref}
          className="inline-flex items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground"
        >
          View all fires
          <ArrowUpRight className="size-4" />
        </Link>
      </div>
    </motion.div>
  );
}
