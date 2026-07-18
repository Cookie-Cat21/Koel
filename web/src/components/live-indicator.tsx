import { cn } from "@/lib/utils";

/** Poller / live status chip — adapted from Ceyfi LiveIndicator. */
export function LiveIndicator({
  label = "Live",
  tone = "ok",
  className,
}: {
  label?: string;
  tone?: "ok" | "stale" | "down" | "closed";
  className?: string;
}) {
  const tones = {
    ok: "bg-emerald-50 text-emerald-800",
    stale: "bg-amber-50 text-amber-900",
    down: "bg-red-50 text-red-800",
    closed: "bg-slate-100 text-slate-700",
  } as const;
  const dots = {
    ok: "bg-emerald-500",
    stale: "bg-amber-500",
    down: "bg-red-500",
    closed: "bg-slate-400",
  } as const;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]",
        tones[tone],
        className,
      )}
    >
      <span className="relative flex h-2 w-2">
        {tone === "ok" ? (
          <span
            className={cn(
              "absolute inline-flex h-full w-full rounded-full opacity-60 motion-safe:animate-ping",
              dots[tone],
            )}
          />
        ) : null}
        <span className={cn("relative inline-flex h-2 w-2 rounded-full", dots[tone])} />
      </span>
      {label}
    </span>
  );
}
