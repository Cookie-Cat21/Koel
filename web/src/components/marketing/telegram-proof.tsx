import { TelegramIcon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";

import { cn } from "@/lib/utils";

/**
 * Floating Telegram notification cards — no phone/device chrome.
 * A dimmed prior alert sits behind the live example for depth.
 */
export function TelegramProof({ className }: { className?: string }) {
  return (
    <div
      className={cn("relative w-full", className)}
      aria-label="Example Telegram alert notifications"
    >
      <div
        aria-hidden
        className="absolute -inset-x-6 -inset-y-10 -z-10 rounded-[2.5rem] bg-[radial-gradient(60%_60%_at_50%_40%,oklch(0.55_0.08_250_/_0.14)_0%,transparent_72%)]"
      />

      <div
        aria-hidden
        className="absolute inset-x-6 -top-4 -z-10 -rotate-2 scale-[0.96] rounded-[1.35rem] border border-white/10 bg-[oklch(0.16_0.014_260)] px-4 py-3.5 opacity-60 shadow-md"
      >
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-[10px] bg-[#2AABEE] text-white">
            <HugeiconsIcon icon={TelegramIcon} size={18} />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline justify-between gap-2">
              <p className="text-[11px] font-semibold tracking-wide text-white/70 uppercase">
                Telegram
              </p>
              <p className="text-[10px] text-white/45">2m ago</p>
            </div>
            <p className="mt-0.5 text-sm font-semibold text-white/90">
              koel CSE
            </p>
            <p className="mt-1 text-xs leading-snug text-white/70">
              New disclosure for JKH.N0000
            </p>
          </div>
        </div>
      </div>

      <div className="relative rounded-[1.35rem] border border-white/12 bg-[oklch(0.13_0.012_260)] px-4 py-3.5 text-white shadow-xl shadow-black/10 backdrop-blur-md">
        <div className="flex items-start gap-3">
          <span
            aria-hidden
            className="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-[11px] bg-[#2AABEE] text-white"
          >
            <HugeiconsIcon icon={TelegramIcon} size={20} />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline justify-between gap-2">
              <p className="text-xs font-semibold tracking-wide text-white/90 uppercase">
                Telegram
              </p>
              <p className="text-[11px] text-white/55">now</p>
            </div>
            <p className="mt-0.5 text-base font-semibold text-white">
              koel CSE
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
  );
}
