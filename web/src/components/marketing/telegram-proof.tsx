import { ChatBubble } from "@/components/kit/chat-bubble";
import { cn } from "@/lib/utils";

/**
 * Product proof — Daisy chat + Signal Ice red rail.
 * Cult Visual slot without device frames / shaders.
 */
export function TelegramProof({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl border border-[#d1d5db] bg-white p-5 sm:p-6",
        className,
      )}
    >
      <div
        aria-hidden
        className="absolute top-0 left-0 h-full w-1 bg-[var(--fired)]"
      />
      <div className="relative pl-2">
        <div className="mb-5 flex items-center justify-between gap-3">
          <p className="text-xs font-semibold tracking-[0.16em] text-[var(--ink)] uppercase">
            Live on Telegram
          </p>
          <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <span
              aria-hidden
              className="size-1.5 rounded-full bg-[var(--fired)] motion-safe:animate-pulse"
            />
            Push · tab closed OK
          </span>
        </div>

        <ChatBubble
          variant="fired"
          header={
            <span className="flex w-full items-baseline justify-between gap-3">
              <span>Chime CSE</span>
              <span className="font-normal text-muted-foreground">
                09:31 SLT
              </span>
            </span>
          }
          footer="Delivered · Not financial advice"
        >
          <p className="text-xs font-semibold tracking-[0.14em] text-[var(--fired)] uppercase">
            Fired
          </p>
          <p className="mt-2 font-medium text-[var(--ink)]">
            JKH.N0000 crossed above
          </p>
          <p className="mt-1 font-mono text-3xl font-semibold tracking-tight text-[var(--ink)] tabular-nums sm:text-4xl">
            22.50
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            Last 22.75 · rule #184
          </p>
        </ChatBubble>
      </div>
    </div>
  );
}
