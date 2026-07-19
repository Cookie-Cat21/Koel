"use client";

import { Bell } from "lucide-react";
import { motion } from "motion/react";
import Image from "next/image";
import { useState } from "react";

import { cn } from "@/lib/utils";

const bentoCardClass = cn(
  "group relative flex flex-col justify-between overflow-hidden rounded-xl border border-border/70 bg-card/60 p-4 duration-300 antialiased lg:p-6",
);

const POLL_BARS = [40, 70, 45, 90, 65, 85, 35, 60, 50, 80, 55, 75];

const HEALTH_ROWS = [
  { name: "Price feed", delay: 0.2 },
  { name: "Disclosures", delay: 0.5 },
  { name: "Rule engine", delay: 0.8 },
] as const;

const HUB = { top: 62, left: 50 };

const WATCHED_SYMBOLS = [
  { symbol: "JKH.N0000", top: 14, left: 12, delay: 0 },
  { symbol: "COMB.N0000", top: 40, left: 58, delay: 0.4 },
  { symbol: "DIAL.N0000", top: 8, left: 72, delay: 0.2 },
  { symbol: "LOLC.N0000", top: 62, left: 30, delay: 0.6 },
] as const;

/** koel bento grid — remap of Watermelon UI's Bento 2 block, restyled to product tokens. */
export function KoelBento({ className }: { className?: string }) {
  const [hoveredCard, setHoveredCard] = useState<number | null>(null);

  return (
    <div
      className={cn(
        "grid w-full grid-cols-1 gap-4 md:grid-cols-3",
        className,
      )}
    >
      {/* Card 1: Poller activity (large) */}
      <div
        className={cn(bentoCardClass, "min-h-[320px] justify-end md:col-span-2")}
        onMouseEnter={() => setHoveredCard(1)}
        onMouseLeave={() => setHoveredCard(null)}
      >
        <div className="relative z-10 flex w-full flex-1 items-start justify-center overflow-visible">
          <motion.div className="flex w-full flex-col">
            <div className="mb-8 flex items-center justify-between">
              <div className="flex flex-col">
                <span className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
                  Poller activity
                </span>
                <span className="text-2xl font-bold tabular-nums">
                  1,240{" "}
                  <span className="text-sm font-medium text-muted-foreground">
                    checks today
                  </span>
                </span>
              </div>
            </div>

            <div className="flex h-30 items-end gap-1.5 overflow-hidden">
              {POLL_BARS.map((height, i) => (
                <motion.div
                  key={i}
                  className="w-full rounded-t-sm bg-primary dark:bg-primary/60"
                  initial={{ height: `${height}%` }}
                  animate={
                    hoveredCard === 1
                      ? {
                          height: [
                            `${height}%`,
                            `${Math.max(15, height - 30)}%`,
                            `${height}%`,
                          ],
                        }
                      : { height: `${height}%` }
                  }
                  transition={{
                    duration: 2,
                    repeat: hoveredCard === 1 ? Infinity : 0,
                    delay: i * 0.05,
                    ease: "easeInOut",
                  }}
                />
              ))}
            </div>
          </motion.div>
        </div>

        <div className="relative z-10 flex flex-col gap-2 pt-4">
          <h3 className="text-xl font-semibold text-foreground">
            Every tick, checked.
          </h3>
          <p className="max-w-sm text-sm text-muted-foreground">
            Every snapshot the poller takes during market hours is checked
            against your rules the moment it lands.
          </p>
        </div>
      </div>

      {/* Card 2: Always watching (small) */}
      <div
        className={cn(bentoCardClass, "min-h-[320px] justify-start md:col-span-1")}
        onMouseEnter={() => setHoveredCard(2)}
        onMouseLeave={() => setHoveredCard(null)}
      >
        <div className="relative z-10 flex flex-col gap-2 pb-4">
          <h3 className="text-xl font-semibold text-foreground">
            Always watching
          </h3>
          <p className="max-w-[200px] text-sm text-muted-foreground">
            Poller status, live — same data as the health page.
          </p>
        </div>

        <div className="relative z-10 flex w-full flex-1 items-end justify-center overflow-visible pt-6 pb-2">
          <motion.div className="relative z-10 flex w-full flex-col gap-3 overflow-hidden">
            <div className="flex items-center justify-between border-b border-border/50 pb-2">
              <span className="text-[9px] font-bold tracking-widest text-muted-foreground uppercase">
                koel poller
              </span>
              <div className="flex items-center gap-1.5">
                <motion.div
                  className="size-1.5 rounded-full bg-primary shadow-[0_0_8px_var(--primary)]"
                  animate={
                    hoveredCard === 2 ? { opacity: [1, 0.3, 1] } : { opacity: 1 }
                  }
                  transition={{ duration: 1.5, repeat: Infinity }}
                />
                <span className="text-[9px] font-bold tracking-wider text-primary uppercase">
                  Healthy
                </span>
              </div>
            </div>

            <div className="flex flex-col gap-3">
              {HEALTH_ROWS.map((service) => (
                <div key={service.name} className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-semibold text-foreground">
                      {service.name}
                    </span>
                    <div className="flex items-center gap-2">
                      <motion.span
                        className="font-mono text-[9px] text-primary drop-shadow-[0_0_4px_var(--primary)]"
                        initial={{ opacity: 0, x: -5 }}
                        animate={
                          hoveredCard === 2
                            ? { opacity: 1, x: 0 }
                            : { opacity: 0, x: -5 }
                        }
                        transition={{
                          type: "spring",
                          delay: hoveredCard === 2 ? service.delay + 0.4 : 0,
                        }}
                      >
                        online
                      </motion.span>
                      <div className="relative h-1 w-12 overflow-hidden rounded-full bg-muted">
                        <motion.div
                          className="absolute top-0 bottom-0 left-0 bg-primary shadow-[0_0_8px_var(--primary)]"
                          initial={{ width: "0%" }}
                          animate={
                            hoveredCard === 2
                              ? { width: "100%" }
                              : { width: "0%" }
                          }
                          transition={{
                            duration: 0.6,
                            delay: hoveredCard === 2 ? service.delay : 0,
                            ease: "easeOut",
                          }}
                        />
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    {[...Array(14)].map((_, j) => (
                      <motion.div
                        key={j}
                        className="h-2 flex-1 rounded-[1px] bg-primary"
                        initial={{ opacity: 0.2 }}
                        animate={
                          hoveredCard === 2
                            ? { opacity: [0.2, 0.9, 0.2] }
                            : { opacity: 0.2 }
                        }
                        transition={{
                          duration: 0.4,
                          delay:
                            hoveredCard === 2 ? service.delay + j * 0.03 : 0,
                          ease: "easeOut",
                        }}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>

      {/* Card 3: Smart alerts (small) */}
      <div
        className={cn(bentoCardClass, "min-h-[320px] justify-end md:col-span-1")}
        onMouseEnter={() => setHoveredCard(3)}
        onMouseLeave={() => setHoveredCard(null)}
      >
        <div className="relative z-10 flex w-full flex-1 items-start justify-center overflow-visible pt-8">
          <div className="relative flex w-full flex-col items-center">
            <motion.div
              className="relative z-30 flex size-12 items-center justify-center rounded-2xl border border-border/50 bg-background/50 shadow-sm backdrop-blur-md"
              animate={hoveredCard === 3 ? { y: -10 } : { y: 0 }}
              transition={{ type: "spring", stiffness: 300 }}
            >
              <motion.div
                animate={
                  hoveredCard === 3
                    ? { rotate: [0, -15, 15, -15, 15, 0] }
                    : { rotate: 0 }
                }
                transition={{ duration: 0.5, delay: 0.1 }}
              >
                <Bell className="size-5 text-foreground" />
              </motion.div>

              <motion.div
                className="absolute top-3 right-3 size-2 rounded-full bg-primary"
                initial={{ scale: 0 }}
                animate={hoveredCard === 3 ? { scale: 1 } : { scale: 0 }}
                transition={{ type: "spring", delay: 0.3 }}
              />
              <motion.div
                className="absolute top-3 right-3 size-2 rounded-full bg-primary"
                initial={{ scale: 0, opacity: 0 }}
                animate={
                  hoveredCard === 3
                    ? { scale: 2.5, opacity: 0 }
                    : { scale: 0, opacity: 0 }
                }
                transition={{
                  duration: 1,
                  delay: 0.3,
                  repeat: hoveredCard === 3 ? Infinity : 0,
                }}
              />
            </motion.div>

            <div className="absolute top-6 flex w-full flex-col items-center justify-center pt-8">
              <motion.div
                className="relative z-20 flex w-[220px] items-center gap-3 rounded-xl border border-border/40 bg-background/80 p-3 shadow-lg backdrop-blur-md"
                initial={{ opacity: 0, y: -20, scale: 0.95 }}
                animate={
                  hoveredCard === 3
                    ? { opacity: 1, y: 0, scale: 1 }
                    : { opacity: 0, y: -20, scale: 0.95 }
                }
                transition={{
                  type: "spring",
                  stiffness: 400,
                  damping: 25,
                  delay: 0.2,
                }}
              >
                <div className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10">
                  <div className="size-1.5 rounded-full bg-primary" />
                </div>
                <div className="flex flex-col">
                  <span className="text-[11px] font-semibold text-foreground">
                    JKH.N0000 crossed above
                  </span>
                  <span className="text-[10px] text-muted-foreground">
                    22.50 · Not financial advice
                  </span>
                </div>
              </motion.div>
            </div>
          </div>
        </div>

        <div className="relative z-10 flex flex-col gap-2 pt-4">
          <h3 className="text-xl font-semibold text-foreground">
            Get pinged the instant it matters.
          </h3>
          <p className="max-w-[200px] text-sm text-muted-foreground">
            Price crosses, % moves, new disclosures — the bot messages you the
            moment a rule fires.
          </p>
        </div>
      </div>

      {/* Card 4: Telegram delivery (large) */}
      <div
        className={cn(
          bentoCardClass,
          "min-h-[320px] items-end justify-start text-right md:col-span-2",
        )}
        onMouseEnter={() => setHoveredCard(4)}
        onMouseLeave={() => setHoveredCard(null)}
      >
        <div className="relative z-10 flex flex-col items-end gap-2 pb-4">
          <h3 className="text-xl font-semibold tracking-tight text-foreground">
            Telegram delivery, no tab required.
          </h3>
          <p className="max-w-sm text-sm leading-relaxed text-muted-foreground">
            Rules live in the dash. Delivery is Telegram — the ping finds you
            even if the browser is closed.
          </p>
        </div>

        <div className="relative z-10 flex min-h-[200px] w-full flex-1 items-end justify-center overflow-hidden">
          <motion.div
            className="absolute inset-0 z-0"
            animate={{ opacity: hoveredCard === 4 ? 1 : 0.5 }}
            transition={{ duration: 0.8 }}
          >
            <div className="absolute bottom-0 left-1/2 h-[100px] w-[55%] -translate-x-1/2 rounded-[100%] bg-[#2AABEE]/20 blur-3xl" />
          </motion.div>

          {/* Connector lines from each watched symbol to the Telegram hub */}
          <svg
            className="absolute inset-0 h-full w-full"
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            aria-hidden
          >
            {WATCHED_SYMBOLS.map((item) => (
              <motion.line
                key={item.symbol}
                x1={item.left}
                y1={item.top}
                x2={HUB.left}
                y2={HUB.top}
                stroke="currentColor"
                strokeWidth="0.45"
                strokeDasharray="1.2 2.2"
                className="text-[#2AABEE]/35"
                initial={{ opacity: 0.45 }}
                animate={{ opacity: hoveredCard === 4 ? 0.9 : 0.45 }}
                transition={{ duration: 0.6 }}
              />
            ))}
          </svg>

          <div className="absolute inset-0 h-full w-full">
            {WATCHED_SYMBOLS.map((item) => (
              <motion.div
                key={item.symbol}
                className="absolute flex flex-col items-center"
                style={{ top: `${item.top}%`, left: `${item.left}%` }}
                initial={{ y: 0 }}
                animate={hoveredCard === 4 ? { y: [0, -6, 0] } : { y: 0 }}
                transition={{
                  y:
                    hoveredCard === 4
                      ? {
                          duration: 3,
                          repeat: Infinity,
                          ease: "easeInOut",
                          delay: item.delay,
                        }
                      : { duration: 0.5, ease: "easeOut" },
                }}
              >
                <div className="relative z-10 flex -translate-x-1/2 items-center justify-center rounded-full border border-border/70 bg-background/95 px-3 py-1.5 shadow-sm backdrop-blur-sm">
                  <span className="font-mono text-[10px] font-semibold tracking-tight text-foreground">
                    {item.symbol}
                  </span>
                  <motion.div
                    className="absolute -top-0.5 -right-0.5 size-2 rounded-full border-[1.5px] border-background bg-[#2AABEE]"
                    animate={
                      hoveredCard === 4 ? { scale: [1, 1.25, 1] } : { scale: 1 }
                    }
                    transition={
                      hoveredCard === 4
                        ? { duration: 2, repeat: Infinity, delay: item.delay }
                        : { duration: 0.3 }
                    }
                  />
                </div>
              </motion.div>
            ))}

            {/* Telegram hub — Brandfetch mark (telegram.org symbol) */}
            <div
              className="absolute flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-2"
              style={{ top: `${HUB.top}%`, left: `${HUB.left}%` }}
            >
              <motion.div
                className="relative z-10 size-14 overflow-hidden rounded-full shadow-[0_8px_24px_-8px_rgba(42,171,238,0.55)] ring-1 ring-[#2AABEE]/25"
                animate={
                  hoveredCard === 4 ? { scale: [1, 1.06, 1] } : { scale: 1 }
                }
                transition={{
                  duration: 1.6,
                  repeat: hoveredCard === 4 ? Infinity : 0,
                }}
              >
                <Image
                  src="/brand/telegram-mark.svg"
                  alt="Telegram"
                  width={56}
                  height={56}
                  className="size-full object-cover"
                  priority={false}
                />
                <motion.div
                  className="pointer-events-none absolute inset-0 rounded-full bg-[#2AABEE]"
                  initial={{ opacity: 0.35, scale: 1 }}
                  animate={
                    hoveredCard === 4
                      ? { opacity: 0, scale: 1.85 }
                      : { opacity: 0, scale: 1 }
                  }
                  transition={{
                    duration: 1.6,
                    repeat: hoveredCard === 4 ? Infinity : 0,
                    ease: "easeOut",
                  }}
                />
              </motion.div>
              <span className="text-[9px] font-semibold tracking-[0.14em] text-muted-foreground uppercase">
                Delivered
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
