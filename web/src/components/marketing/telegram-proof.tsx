import { cn } from "@/lib/utils";

/**
 * Large iPhone — hard-clipped by the proof band (`overflow-hidden`).
 * Tall on purpose so the cut lands mid-body where the band colour ends.
 */
export function TelegramProof({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "relative w-[300px] sm:w-[340px] lg:w-[380px]",
        className,
      )}
      aria-label="Example Telegram alert notification on a phone"
    >
      <div className="rounded-[2.75rem] border border-foreground/25 bg-foreground p-[10px] shadow-sm">
        <div className="relative h-[640px] overflow-hidden rounded-[2.2rem] bg-[oklch(0.13_0.012_260)] text-white">
          <div
            aria-hidden
            className="absolute inset-0 bg-[radial-gradient(120%_60%_at_50%_0%,oklch(0.28_0.02_250)_0%,transparent_55%)]"
          />

          <div className="relative px-5 pt-5">
            <div className="mx-auto mb-3.5 h-[28px] w-[7rem] rounded-full bg-black" />

            <div className="mb-6 flex items-center justify-between px-0.5 text-xs font-medium tracking-wide text-white/80">
              <span>09:31</span>
              <span className="flex items-center gap-1.5" aria-hidden>
                <span className="inline-block h-1.5 w-3.5 rounded-sm bg-white/70" />
                <span className="inline-block h-2 w-2 rounded-full bg-white/70" />
                <span className="inline-block h-2.5 w-[18px] rounded-sm border border-white/70">
                  <span className="ml-px block h-full w-3 rounded-[1px] bg-white/70" />
                </span>
              </span>
            </div>

            <div className="rounded-[1.35rem] border border-white/12 bg-white/[0.17] px-4 py-3.5 shadow-sm backdrop-blur-md">
              <div className="flex items-start gap-3">
                <span
                  aria-hidden
                  className="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-[11px] bg-[#2AABEE] text-xs font-bold tracking-tight text-white"
                >
                  TG
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-2">
                    <p className="text-xs font-semibold tracking-wide text-white/90 uppercase">
                      Telegram
                    </p>
                    <p className="text-[11px] text-white/55">now</p>
                  </div>
                  <p className="mt-0.5 text-base font-semibold text-white">
                    Chime CSE
                  </p>
                  <p className="mt-1.5 text-sm leading-snug text-white/90">
                    JKH.N0000 crossed above{" "}
                    <span className="font-mono font-semibold tabular-nums">
                      22.50
                    </span>
                  </p>
                  <p className="mt-1.5 text-[11px] text-white/50">
                    Last 22.75 · Not financial advice
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
