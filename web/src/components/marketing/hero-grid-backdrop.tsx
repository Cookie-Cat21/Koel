import { cn } from "@/lib/utils";

const CELL_COUNT = 216;

/**
 * Thin square-grid texture, radially masked so it fades out toward the
 * edges. Adapted from Watermelon UI's newsletter-5 BackgroundGrid —
 * structure kept, accent color swapped to koel's `primary` token (no
 * green in this palette).
 */
export function HeroGridBackdrop({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
      style={{
        maskImage:
          "radial-gradient(60% 60% at 50% 40%, black 0%, transparent 75%)",
        WebkitMaskImage:
          "radial-gradient(60% 60% at 50% 40%, black 0%, transparent 75%)",
      }}
    >
      <div className="grid h-full w-full grid-cols-12">
        {Array.from({ length: CELL_COUNT }).map((_, index) => (
          <div
            key={index}
            className={cn(
              "aspect-square border border-border/40",
              index % 7 === 0 && "bg-primary/10",
              index % 17 === 0 && "bg-foreground/[0.03]",
            )}
          />
        ))}
      </div>
    </div>
  );
}
