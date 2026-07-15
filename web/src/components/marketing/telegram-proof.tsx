import { cn } from "@/lib/utils";

/**
 * Phone peek — top of an iPhone only, lock-screen Telegram notification.
 * Clipped so the band stays the same size; not a full device-frame hero.
 */
export function TelegramProof({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "relative mx-auto h-[230px] w-full max-w-[320px] overflow-hidden sm:h-[250px] sm:max-w-none lg:ml-auto lg:mr-0",
        className,
      )}
      aria-label="Example Telegram alert notification on a phone"
    >
      {/* Soft fade into the proof band so the clip reads as a peek */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 z-20 h-16 bg-gradient-to-t from-[oklch(0.975_0.004_245)] via-[oklch(0.975_0.004_245_/0.85)] to-transparent"
      />

      <div className="relative mx-auto w-[240px] -mt-1 sm:w-[268px]">
        {/* Bezel */}
        <div className="rounded-[2.1rem] border border-foreground/15 bg-foreground p-[7px] shadow-sm">
          {/* Screen */}
          <div className="relative overflow-hidden rounded-[1.7rem] bg-[oklch(0.16_0.012_260)] text-white">
            {/* Lock-screen wash */}
            <div
              aria-hidden
              className="absolute inset-0 bg-[radial-gradient(120%_80%_at_50%_-10%,oklch(0.32_0.02_250)_0%,transparent_55%)]"
            />

            <div className="relative px-3.5 pt-3 pb-32">
              {/* Dynamic Island */}
              <div className="mx-auto mb-2.5 h-[22px] w-[5.25rem] rounded-full bg-black" />

              {/* Status row */}
              <div className="mb-3.5 flex items-center justify-between px-1 text-[10px] font-medium tracking-wide text-white/80">
                <span>09:31</span>
                <span className="flex items-center gap-1" aria-hidden>
                  <span className="inline-block h-1.5 w-3 rounded-sm bg-white/70" />
                  <span className="inline-block h-2 w-2 rounded-full bg-white/70" />
                  <span className="inline-block h-2.5 w-4 rounded-sm border border-white/70">
                    <span className="ml-px block h-full w-2.5 rounded-[1px] bg-white/70" />
                  </span>
                </span>
              </div>

              {/* Lock-screen notification — sits at the top of the peek */}
              <div className="rounded-2xl border border-white/10 bg-white/[0.14] px-3 py-2.5 shadow-sm backdrop-blur-md">
                <div className="flex items-start gap-2.5">
                  <span
                    aria-hidden
                    className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-[9px] bg-[#2AABEE] text-[10px] font-bold tracking-tight text-white"
                  >
                    TG
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-2">
                      <p className="text-[11px] font-semibold tracking-wide text-white/90 uppercase">
                        Telegram
                      </p>
                      <p className="text-[10px] text-white/55">now</p>
                    </div>
                    <p className="mt-0.5 text-[13px] font-semibold text-white">
                      Chime CSE
                    </p>
                    <p className="mt-1 text-[12px] leading-snug text-white/85">
                      JKH.N0000 crossed above{" "}
                      <span className="font-mono font-semibold tabular-nums">
                        22.50
                      </span>
                    </p>
                    <p className="mt-1 text-[10px] text-white/50">
                      Last 22.75 · Not financial advice
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
