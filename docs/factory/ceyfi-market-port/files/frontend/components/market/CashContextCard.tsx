"use client";

import Link from "next/link";
import { Wallet } from "lucide-react";
import { formatLKR } from "@/lib/utils";

export function CashContextCard({
  liquidLkr,
  label,
  loading,
}: {
  liquidLkr: number | null;
  label?: string;
  loading?: boolean;
}) {
  return (
    <section className="rounded-[1.25rem] border border-ceyfi-line bg-card p-4 shadow-sm dark:border-white/10">
      <div className="flex items-start gap-3">
        <span className="grid size-10 place-items-center rounded-xl bg-ceyfi-sprout text-ceyfi-green dark:bg-ceyfi-green/15">
          <Wallet className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-ceyfi-muted">
            Cash context
          </p>
          <p className="mt-1 font-heading text-2xl font-semibold tabular-nums text-ceyfi-ink dark:text-white">
            {loading
              ? "…"
              : liquidLkr != null
                ? formatLKR(liquidLkr)
                : "Unavailable"}
          </p>
          <p className="mt-1 text-[12px] text-muted-foreground">
            {label ?? "Liquid estimate from your Ceyfi snapshot — not a buy signal."}
          </p>
          <Link
            href="/wallet"
            className="mt-3 inline-flex text-sm font-medium text-ceyfi-green underline-offset-2 hover:underline"
          >
            Review cash in Wallet
          </Link>
        </div>
      </div>
    </section>
  );
}
