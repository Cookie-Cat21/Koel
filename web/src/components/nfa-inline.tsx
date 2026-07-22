import { NFA_INLINE } from "@/lib/nfa";
import { cn } from "@/lib/utils";

/**
 * Short NFA line for price-adjacent UI surfaces.
 * Uses ``span`` (block) so callers can wrap it in ``<p>`` without nested-p
 * hydration errors (Next DevTools Issues).
 */
export function NfaInline({ className }: { className?: string }) {
  return (
    <span
      className={cn("block text-xs text-muted-foreground", className)}
    >
      {NFA_INLINE}
    </span>
  );
}
