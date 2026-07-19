import { cn } from "@/lib/utils";

const COLS = 8;
const ROWS = 6;
const CELL_COUNT = COLS * ROWS;

/**
 * Soft large-square checker atmosphere for koel brand surfaces.
 * Filled tiles only (no hairline borders), radially faded at the edges.
 */
export function HeroGridBackdrop({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "pointer-events-none absolute inset-0 overflow-hidden",
        className,
      )}
      style={{
        maskImage:
          "radial-gradient(75% 70% at 40% 30%, black 10%, transparent 80%)",
        WebkitMaskImage:
          "radial-gradient(75% 70% at 40% 30%, black 10%, transparent 80%)",
      }}
    >
      <div
        className="grid h-full w-full"
        style={{
          gridTemplateColumns: `repeat(${COLS}, minmax(0, 1fr))`,
          gridTemplateRows: `repeat(${ROWS}, minmax(0, 1fr))`,
        }}
      >
        {Array.from({ length: CELL_COUNT }).map((_, index) => {
          const col = index % COLS;
          const row = Math.floor(index / COLS);
          const filled = (col + row) % 2 === 0;
          return (
            <div
              key={index}
              className={cn(filled && "bg-foreground/[0.07]")}
            />
          );
        })}
      </div>
    </div>
  );
}
